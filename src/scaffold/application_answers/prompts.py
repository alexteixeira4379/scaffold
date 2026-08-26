"""Prompt templates for the AI responder."""

from __future__ import annotations

import json

from scaffold.application_answers.contracts import CandidateContext, Question


SYSTEM_PROMPT = (
    "You are a professional assistant specialized in filling job application forms. "
    "You answer questions precisely based on the candidate's profile data. "
    "Be concise, direct, and professional. Never explain your reasoning — just provide the answer."
)


def build_single_question_prompt(
    question: Question,
    context: CandidateContext,
) -> str:
    """Build a prompt for answering a single question."""
    candidate_data = _context_to_dict(context)
    parts: list[str] = [
        "Based on the candidate profile below, answer the following application question.",
        "",
        "CANDIDATE PROFILE:",
        json.dumps(candidate_data, ensure_ascii=False, indent=2),
        "",
        f"QUESTION: {question.question}",
    ]

    if question.question_complement:
        parts.append(f"CONTEXT: {question.question_complement}")

    if question.options:
        parts.append("")
        parts.append("AVAILABLE OPTIONS (choose EXACTLY one):")
        for i, opt in enumerate(question.options, 1):
            parts.append(f"  {i}. {opt.label}")
        parts.append("")
        parts.append("IMPORTANT: Return ONLY the exact text of the chosen option.")

    parts.append("")
    parts.append("INSTRUCTIONS:")

    # Detect question type
    q_lower = question.question.lower()
    is_numeric = _is_numeric_question(q_lower)
    is_salary = _is_salary_question(q_lower)

    if is_numeric:
        parts.append("- This is a NUMERIC question. Return ONLY the number, nothing else.")
    elif is_salary:
        parts.append(
            "- This is a SALARY question. Return ONLY the numeric value (no currency symbol, no commas)."
        )
        parts.append("- Example: if salary is $90,000, return: 90000")
    elif question.options:
        parts.append("- Choose the option that best matches the candidate's profile.")
        parts.append("- Return ONLY the exact text of the chosen option.")
    else:
        parts.append("- Provide a concise, professional answer.")
        parts.append("- Maximum 100 characters unless the question requires more detail.")

    if question.is_required:
        parts.append("- This is a REQUIRED question. You MUST provide an answer.")

    parts.append("")
    parts.append("ANSWER:")

    return "\n".join(parts)


def build_batch_prompt(
    questions: list[Question],
    context: CandidateContext,
) -> str:
    """Build a prompt for answering multiple questions at once."""
    candidate_data = _context_to_dict(context)
    parts: list[str] = [
        "Based on the candidate profile below, answer ALL the following application questions.",
        "",
        "CANDIDATE PROFILE:",
        json.dumps(candidate_data, ensure_ascii=False, indent=2),
        "",
        "QUESTIONS:",
        "",
    ]

    for i, question in enumerate(questions, 1):
        parts.append(f"{i}. [ID: {question.id}] {question.question}")
        if question.question_complement:
            parts.append(f"   Context: {question.question_complement}")
        if question.options:
            parts.append("   Options:")
            for opt in question.options[:8]:
                parts.append(f"      - {opt.label}")
            if len(question.options) > 8:
                parts.append(f"      ... and {len(question.options) - 8} more options")
        parts.append("")

    parts.append("INSTRUCTIONS:")
    parts.append(
        "- For questions with options, choose the best matching option (return exact text)."
    )
    parts.append("- For numeric questions, return only the number.")
    parts.append("- For salary questions, return only the numeric value (no $ or commas).")
    parts.append("- Be concise and professional.")
    parts.append('- Return answers as JSON: {"question_id": "answer", ...}')
    parts.append("")
    parts.append("ANSWERS (JSON format):")

    return "\n".join(parts)


def _context_to_dict(context: CandidateContext) -> dict:
    """Convert context to a serializable dict for the prompt."""
    data: dict = {
        "full_name": context.full_name,
        "email": context.email,
    }
    if context.phone:
        data["phone"] = context.phone
    if context.country:
        data["country"] = context.country
    if context.location:
        data["location"] = context.location
    if context.linkedin_url:
        data["linkedin_url"] = context.linkedin_url
    if context.target_country:
        data["target_country"] = context.target_country
    if context.target_location:
        data["target_location"] = context.target_location
    if context.min_salary is not None:
        data["min_salary"] = context.min_salary
        if context.currency:
            data["currency"] = context.currency
    if context.years_of_experience is not None:
        data["years_of_experience"] = context.years_of_experience
    if context.work_authorization:
        data["work_authorization"] = context.work_authorization
    if context.citizenship:
        data["citizenship"] = context.citizenship
    if context.education_level:
        data["education_level"] = context.education_level
    if context.languages:
        data["languages"] = context.languages
    if context.availability:
        data["availability"] = context.availability
    if context.gender:
        data["gender"] = context.gender
    if context.veteran_status:
        data["veteran_status"] = context.veteran_status
    if context.disability_status:
        data["disability_status"] = context.disability_status
    return data


def _is_numeric_question(text: str) -> bool:
    """Detect if a question expects a numeric answer."""
    patterns = ["how many", "number of", "scale", "1-10", "1 to 10", "rate"]
    return any(p in text for p in patterns)


def _is_salary_question(text: str) -> bool:
    """Detect if a question is about salary/compensation."""
    patterns = ["salary", "compensation", "expectation", "pretensão", "remuneração"]
    return any(p in text for p in patterns)
