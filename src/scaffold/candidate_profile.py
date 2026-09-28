"""Shared candidate facts and compatibility rules (no inference of declarations)."""

from __future__ import annotations

import re

WORK_MODES = ("remote", "hybrid", "onsite")
DECLINED = "prefer_not_to_answer"


def normalize_cpf(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    if re.search(r"[^0-9.\-\s]", value):
        raise ValueError("CPF deve conter apenas números e pontuação de formatação")
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValueError("CPF inválido")
    for size in (9, 10):
        check = (sum(int(digits[i]) * (size + 1 - i) for i in range(size)) * 10) % 11
        if int(digits[size]) != (0 if check == 10 else check):
            raise ValueError("CPF inválido")
    return digits


def effective_work_modes(legacy: str | None, selected: list[str] | None) -> list[str]:
    # null = legacy row; [] = explicitly all. Keep old flexible behavior for legacy rows.
    if selected is not None:
        return list(selected) or list(WORK_MODES)
    return list(WORK_MODES) if not legacy or legacy == "unknown" else [str(legacy)]


def normalize_work_modes(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    if any(value not in WORK_MODES for value in values):
        raise ValueError("Selecione remoto, híbrido ou presencial")
    return [mode for mode in WORK_MODES if mode in values]


def legacy_work_mode(values: list[str]) -> str:
    return values[0] if len(values) == 1 else "unknown"


def application_preparation(preferences, application_data):
    """Shared status for dashboard/chat; optional declarations do not block completion."""
    salary_done = bool(preferences and preferences.salary_reviewed_at)
    cpf_done = bool(application_data and application_data.cpf)
    return {
        "cpf_complete": cpf_done,
        "salary_reviewed": salary_done,
        "complete": cpf_done and salary_done,
        "pending_fields": (["cpf"] if not cpf_done else [])
        + (["min_salary"] if not salary_done else []),
        "href": "/app/respostas",
    }
