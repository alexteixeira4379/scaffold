"""Resolve personal declarations without guessing or fuzzy option selection."""

from __future__ import annotations

import re
import unicodedata

from scaffold.candidate_profile import DECLINED
from scaffold.application_answers.contracts import Answer, AnswerType, CandidateContext, Question


def normalized(value: str) -> str:
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


DECLINE_LABELS = {
    normalized(x)
    for x in (
        DECLINED,
        "Prefiro não responder",
        "Prefiro não informar",
        "Não desejo informar",
        "Prefer not to say",
        "Prefer not to answer",
        "Decline to self identify",
        "I do not wish to answer",
    )
}


def match_personal_fact(question: Question, context: CandidateContext) -> Answer | None:
    label = normalized(question.question)
    field = None
    patterns = (
        ("min_salary", r"pretensao|salary|remuneracao|compensation"),
        ("cpf", r"\bcpf\b"),
        ("disability_cids", r"\bcid\b|\bicd\b"),
        ("accessibility_resources", r"acessibilidade|accessibility|accommodation"),
        ("disability_types", r"tipo.*deficiencia|qual.*deficiencia|disability type"),
        ("disability_status", r"deficiencia|\bpcd\b|disability|disabled"),
        ("race_color", r"\braca\b|\bcor\b|\brace\b|ethnic|etnia"),
        ("sexual_orientation", r"orientacao sexual|sexual orientation"),
        ("gender", r"\bgenero\b|\bgender\b"),
        ("sex_unavailable", r"\bsexo\b|biological sex|sex assigned"),
        (
            "employment_preference",
            r"\bclt\b|\bpj\b|tipo de contratacao|employment type|contract type",
        ),
        ("remote_preferences", r"regime de trabalho|modalidade de trabalho|work model|work mode"),
    )
    for candidate, pattern in patterns:
        if re.search(pattern, label):
            field = candidate
            break
    if field is None:
        return None
    unresolved = Answer(question.id, AnswerType.SKIP, "", 0.0, "unresolved")
    if any(word in label for word in ("familiar", "family", "colega", "colleague", "parentes")):
        return unresolved
    value = getattr(context, field, None)
    if value is None or value == "" or value == []:
        return unresolved
    aliases: set[str] = set()
    # Keep contract preferences as the platform convention, never as employment history.
    if field == "min_salary":
        if not (
            "pretensao" in label
            or "expect" in label
            or label in {"remuneracao desejada", "salario desejado"}
        ):
            return unresolved
        if any(
            word in label
            for word in (
                "anual",
                "annual",
                "year",
                "hora",
                "hour",
                "atual",
                "current",
                "anterior",
                "previous",
            )
        ):
            return unresolved
        asked_currency = next(
            (
                code
                for code in ("brl", "usd", "eur", "gbp")
                if re.search(r"\b" + code + r"\b", label)
            ),
            None,
        )
        if asked_currency and asked_currency != (context.currency or "").lower():
            return unresolved
        value = format(value, ".2f").rstrip("0").rstrip(".")
    elif field == "employment_preference":
        if label not in {
            "tipo de contratacao",
            "modalidade de contratacao",
            "employment type",
            "contract type",
            "clt pj",
            "clt ou pj",
            "preferencia de contratacao",
            "qual sua preferencia de contratacao",
            "qual a sua preferencia de contratacao",
            "qual o tipo de contratacao desejado",
        }:
            return unresolved
        value = {"full_time": "CLT", "contract": "PJ", "unknown": "Todas"}.get(value, value)
        aliases = (
            {"todas", "ambos", "clt e pj", "sem preferencia"}
            if value == "Todas"
            else {normalized(value)}
        )
    elif field == "remote_preferences":
        names = {
            "remote": "Remoto",
            "hybrid": "Híbrido",
            "onsite": "Presencial",
            "flexible": "Flexível",
        }
        value = ", ".join(names.get(v, v) for v in value)
        if len(context.remote_preferences) == 3:
            aliases = {"todos", "todas", "sem preferencia", "remoto hibrido presencial"}
    elif normalized(str(value)) in DECLINE_LABELS:
        value = "Prefiro não responder"
        aliases = DECLINE_LABELS
    elif field == "disability_status":
        if normalized(str(value)) in {"yes", "sim"}:
            aliases = {"yes", "sim"}
            value = str(value)
        elif normalized(str(value)) in {"no", "nao"}:
            aliases = {"no", "nao"}
            value = str(value)
    # CPF is a number, not an answer to e.g. 'Você possui CPF?'.
    if field == "cpf" and label not in {
        "cpf",
        "seu cpf",
        "numero do cpf",
        "informe seu cpf",
        "informe o cpf",
        "cpf apenas numeros",
    }:
        return unresolved
    # A diagnosis or identity is not a yes/no answer to arbitrary compound questions.
    if field in {
        "gender",
        "race_color",
        "sexual_orientation",
        "disability_types",
        "disability_cids",
        "accessibility_resources",
    }:
        if any(
            x in label
            for x in ("experiencia", "experience", "familiar", "family", "colega", "colleague")
        ):
            return unresolved
    aliases.add(normalized(str(value)))
    if question.options:
        matches = [
            option
            for option in question.options
            if normalized(option.label) in aliases or normalized(option.value) in aliases
        ]
        if len(matches) != 1:
            return unresolved
        return Answer(question.id, AnswerType.OPTION, matches[0].value, 1.0, "database")
    return Answer(question.id, AnswerType.TEXT, str(value), 1.0, "database")
