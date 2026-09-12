"""Seeder: Popula billing_workflow_steps com os steps do workflow de assinatura.

Usage:
    python scripts/seederBillingWorkflowSteps.py
    python scripts/seederBillingWorkflowSteps.py --no-reset  # skip deletion phase
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
from scaffold.models.billing.billing_workflow_steps import BillingWorkflowStep  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# STEPS DO WORKFLOW DE ASSINATURA (BILLING)
# ═══════════════════════════════════════════════════════════════════════════════

STEPS: list[dict] = [
    {
        "workflow_key": "subscription",
        "step_key": "select_plan",
        "step_order": 10,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": True,
        "options": {
            "question": "Escolha o plano que faz mais sentido para você.",
            # Options are injected at runtime from the billing plan catalog;
            # the seed carries no fixed plan option.
            "options_source": "plan_catalog",
            "question_type": "wk",
            "answer_format": "option",
            "answer_format_output": {
                "type": "string",
                "description": "Código do plano escolhido (plan_code).",
            },
            "agent_prompt": "Analise a resposta do usuário e identifique o plano escolhido.",
        },
    },
    {
        "workflow_key": "subscription",
        "step_key": "confirm_checkout",
        "step_order": 20,
        "input_type": ResumeStepInputType.BOOLEAN,
        "is_required": True,
        "options": {
            "question": "Posso gerar seu link de pagamento para o plano escolhido?",
            "question_options": ["Sim", "Não"],
            "question_type": "wk",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o candidato confirmou a geração do checkout.",
            # Revalidated server-side: the API re-checks the chosen plan before
            # creating the checkout session.
            "action": "create_checkout",
        },
    },
    {
        "workflow_key": "subscription",
        "step_key": "await_payment",
        "step_order": 30,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "question": "Assim que o pagamento for confirmado, eu libero tudo por aqui. Pode deixar!",
            "question_options": None,
            "question_type": "info",
            "answer_format": "ack",
            "answer_format_output": None,
            "agent_prompt": "",
            # Completed by an external event (payment webhook), not by a user answer.
            "resolution": "external_event",
        },
    },
]


async def get_or_create_step(session, step_data: dict) -> BillingWorkflowStep:
    """Insert or update a step by (workflow_key, step_key)."""
    row = (
        (
            await session.execute(
                select(BillingWorkflowStep)
                .where(
                    BillingWorkflowStep.workflow_key == step_data["workflow_key"],
                    BillingWorkflowStep.step_key == step_data["step_key"],
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

    step = BillingWorkflowStep(
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
                    select(func.count()).select_from(BillingWorkflowStep)
                )
                existing_count = existing_count_result.scalar() or 0
                if existing_count > 0:
                    print(
                        f"  ⚠️  Found {existing_count} existing steps (updating in-place, not deleting)"
                    )

            for step_data in STEPS:
                await get_or_create_step(session, step_data)

            await session.commit()

            count_result = await session.execute(select(func.count()).select_from(BillingWorkflowStep))
            total = count_result.scalar() or 0

        print(f"\n✅ Seeded {len(STEPS)} billing_workflow_steps (total in DB: {total})")
    finally:
        await close_engine()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed billing_workflow_steps with the subscription workflow steps"
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
