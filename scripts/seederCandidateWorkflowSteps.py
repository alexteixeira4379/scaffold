"""Seeder: Popula candidate_workflow_steps com os steps dos workflows de domínio do candidato.

Usage:
    python scripts/seederCandidateWorkflowSteps.py
    python scripts/seederCandidateWorkflowSteps.py --no-reset  # skip deletion phase
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from pathlib import Path

from sqlalchemy import select, func

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

importlib.import_module("scaffold.models")

from scaffold.constants.schema_enums import ResumeStepInputType  # noqa: E402
from scaffold.db.session import close_engine, get_session_factory  # noqa: E402
from scaffold.models.candidate.candidate_workflow_steps import CandidateWorkflowStep  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# STEPS DOS WORKFLOWS DE DOMÍNIO DO CANDIDATO
# ═══════════════════════════════════════════════════════════════════════════════

STEPS: list[dict] = [
    # ── workflow: base_profile ──────────────────────────────────────────────
    {
        "workflow_key": "base_profile",
        "step_key": "full_name",
        "step_order": 10,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "question": "Para começar, me diga seu nome completo.",
            "question_options": None,
            "question_type": "wk",
            "answer_format": "text",
            "answer_format_output": {
                "type": "string",
                "description": "Nome completo do candidato.",
            },
            "agent_prompt": "Analise a resposta do usuário e extraia o nome completo.",
        },
    },
    {
        "workflow_key": "base_profile",
        "step_key": "contact",
        "step_order": 20,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "question": "Agora me informe seu e-mail e, se tiver, o link do seu LinkedIn.",
            "question_options": None,
            "question_type": "wk",
            "answer_format": "text",
            "answer_format_output": {
                "type": "object",
                "properties": {
                    "email": {"type": ["string", "null"], "format": "email"},
                    "linkedin_url": {"type": ["string", "null"]},
                },
            },
            "agent_prompt": (
                "Analise a resposta do usuário e extraia o e-mail e a URL do LinkedIn. "
                "Se algum dos dois não for informado, retorne null no campo correspondente."
            ),
        },
    },
    # ── workflow: search_goal ───────────────────────────────────────────────
    {
        "workflow_key": "search_goal",
        "step_key": "role",
        "step_order": 10,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "question": "Qual cargo ou função você está buscando?",
            "question_options": None,
            "question_type": "wk",
            "answer_format": "text",
            "answer_format_output": {
                "type": "string",
                "description": "Cargo desejado pelo candidato.",
            },
            "agent_prompt": "Analise a resposta do usuário e extraia o cargo desejado.",
        },
    },
    {
        "workflow_key": "search_goal",
        "step_key": "country",
        "step_order": 20,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "question": "Em qual país você quer trabalhar?",
            "question_options": None,
            "question_type": "wk",
            "answer_format": "text",
            "answer_format_output": {
                "type": "string",
                "description": "País desejado (normalizado para código ISO de 2 letras quando possível).",
            },
            "agent_prompt": "Analise a resposta do usuário e extraia o país desejado.",
        },
    },
    {
        "workflow_key": "search_goal",
        "step_key": "work_model",
        "step_order": 30,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": True,
        "options": {
            "question": "Qual modelo de trabalho você prefere?",
            "question_options": ["Remoto", "Híbrido", "Presencial"],
            "question_type": "wk",
            "answer_format": "option",
            "answer_format_output": {
                "type": "string",
                "enum": ["Remoto", "Híbrido", "Presencial"],
            },
            "agent_prompt": "Analise a resposta do usuário e identifique o modelo de trabalho preferido.",
        },
    },
    {
        "workflow_key": "search_goal",
        "step_key": "seniority",
        "step_order": 40,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": True,
        "options": {
            "question": "Qual seu nível de senioridade?",
            "question_options": ["Júnior", "Pleno", "Sênior", "Especialista/Líder"],
            "question_type": "wk",
            "answer_format": "option",
            "answer_format_output": {
                "type": "string",
                "enum": ["Júnior", "Pleno", "Sênior", "Especialista/Líder"],
            },
            "agent_prompt": "Analise a resposta do usuário e identifique o nível de senioridade.",
        },
    },
    {
        "workflow_key": "search_goal",
        "step_key": "confirm_goal",
        "step_order": 50,
        "input_type": ResumeStepInputType.BOOLEAN,
        "is_required": True,
        "options": {
            "question": "Posso confirmar esse objetivo de busca e salvar no seu perfil?",
            "question_options": ["Sim", "Não"],
            "question_type": "wk",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o candidato confirmou o objetivo de busca.",
            "action": "upsert_target_profile",
        },
    },
]


async def get_or_create_step(session, step_data: dict) -> CandidateWorkflowStep:
    """Insert or update a step by (workflow_key, step_key)."""
    row = (
        (
            await session.execute(
                select(CandidateWorkflowStep)
                .where(
                    CandidateWorkflowStep.workflow_key == step_data["workflow_key"],
                    CandidateWorkflowStep.step_key == step_data["step_key"],
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )

    if row is not None:
        row.step_order = step_data["step_order"]
        row.input_type = step_data["input_type"]
        row.options = step_data["options"]
        row.is_required = step_data["is_required"]
        row.active = True
        return row

    step = CandidateWorkflowStep(
        workflow_key=step_data["workflow_key"],
        step_key=step_data["step_key"],
        step_order=step_data["step_order"],
        input_type=step_data["input_type"],
        options=step_data["options"],
        is_required=step_data["is_required"],
        active=True,
    )
    session.add(step)
    await session.flush()
    return step


async def run_seed(reset: bool) -> None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            if reset:
                existing_count_result = await session.execute(
                    select(func.count()).select_from(CandidateWorkflowStep)
                )
                existing_count = existing_count_result.scalar() or 0
                if existing_count > 0:
                    print(
                        f"  ⚠️  Found {existing_count} existing steps (updating in-place, not deleting)"
                    )

            for step_data in STEPS:
                await get_or_create_step(session, step_data)

            await session.commit()

            count_result = await session.execute(select(func.count()).select_from(CandidateWorkflowStep))
            total = count_result.scalar() or 0

        print(f"\n✅ Seeded {len(STEPS)} candidate_workflow_steps (total in DB: {total})")
    finally:
        await close_engine()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed candidate_workflow_steps with candidate domain workflow steps"
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        dest="no_reset",
        help="Skip any reset/cleanup (default behavior already preserves existing data)",
    )
    args = parser.parse_args()

    asyncio.run(run_seed(reset=not args.no_reset))


if __name__ == "__main__":
    main()
