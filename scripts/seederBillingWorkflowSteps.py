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
        "step_key": "accept_offer",
        "step_order": 10,
        "input_type": ResumeStepInputType.BOOLEAN,
        "is_required": True,
        "options": {
            # billing-api renders the configured onboarding offer from the
            # live catalog, including price and recurrence, and injects one
            # explicit "Ir para pagamento" action. The plan code remains an
            # internal implementation detail; acceptance is always real input.
            "question": "",
            "question_options": ["Ir para pagamento"],
            "question_type": "wk",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["accepted"]},
            "offer_source": "onboarding_default",
            "action": "create_checkout",
        },
    },
    {
        "workflow_key": "subscription",
        "step_key": "await_payment",
        "step_order": 20,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "question": "Eu aviso aqui quando o pagamento for confirmado.\n"
                        "_Não precisa enviar comprovante._",
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

# Replaced by the single candidate-facing ``accept_offer`` step. Keeping the
# rows for historical answer FKs is intentional; they are only deactivated.
REMOVED_STEP_KEYS = frozenset({"select_plan", "confirm_checkout"})


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

            for step_key in REMOVED_STEP_KEYS:
                legacy = (
                    (
                        await session.execute(
                            select(BillingWorkflowStep)
                            .where(
                                BillingWorkflowStep.workflow_key == "subscription",
                                BillingWorkflowStep.step_key == step_key,
                            )
                            .limit(1)
                        )
                    )
                    .scalars()
                    .first()
                )
                if legacy is not None:
                    legacy.active = False

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
