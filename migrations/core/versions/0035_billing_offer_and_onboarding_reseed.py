"""Reseed the subscription offer and candidate onboarding presentation.

The Railway migration service runs Alembic but does not execute
``scripts/seed_all.py``. This data-only revision therefore reapplies the
current billing workflow and onboarding seed definitions in production.

Existing rows are updated in place and legacy billing steps are only marked
inactive. No workflow answer, session, flow, or step row is deleted, so
historical foreign keys remain valid.

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-19
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load_seed_data():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))

    import seed_all
    import seederBillingWorkflowSteps

    return (
        seederBillingWorkflowSteps.STEPS,
        seederBillingWorkflowSteps.REMOVED_STEP_KEYS,
        seed_all.FLOW_KEY,
        seed_all.onboard_steps(),
        seed_all.REMOVED_ONBOARD_STEP_KEYS,
    )


_BILLING_STEPS = sa.table(
    "billing_workflow_steps",
    sa.column("id", sa.BigInteger),
    sa.column("workflow_key", sa.String),
    sa.column("step_key", sa.String),
    sa.column("step_order", sa.Integer),
    sa.column("input_type", sa.String),
    sa.column("options", sa.JSON),
    sa.column("is_required", sa.Boolean),
    sa.column("active", sa.Boolean),
)
_ONBOARD_FLOWS = sa.table(
    "onboard_flows",
    sa.column("id", sa.BigInteger),
    sa.column("flow_key", sa.String),
    sa.column("subject_type", sa.String),
    sa.column("version", sa.Integer),
    sa.column("active", sa.Boolean),
)
_ONBOARD_STEPS = sa.table(
    "onboard_flow_steps",
    sa.column("id", sa.BigInteger),
    sa.column("flow_id", sa.BigInteger),
    sa.column("step_key", sa.String),
    sa.column("step_order", sa.Integer),
    sa.column("kind", sa.String),
    sa.column("required", sa.Boolean),
    sa.column("active", sa.Boolean),
    sa.column("config", sa.JSON),
)


def _reseed_billing(bind, steps: list[dict], removed_step_keys: set[str]) -> None:
    for step_data in steps:
        existing_id = bind.execute(
            sa.select(_BILLING_STEPS.c.id).where(
                _BILLING_STEPS.c.workflow_key == step_data["workflow_key"],
                _BILLING_STEPS.c.step_key == step_data["step_key"],
            )
        ).scalar()
        values = dict(
            step_order=step_data["step_order"],
            input_type=step_data["input_type"].value,
            options=step_data["options"],
            is_required=step_data["is_required"],
            active=True,
        )
        if existing_id is None:
            bind.execute(
                _BILLING_STEPS.insert().values(
                    workflow_key=step_data["workflow_key"],
                    step_key=step_data["step_key"],
                    **values,
                )
            )
        else:
            bind.execute(
                _BILLING_STEPS.update()
                .where(_BILLING_STEPS.c.id == existing_id)
                .values(**values)
            )

    bind.execute(
        _BILLING_STEPS.update()
        .where(
            _BILLING_STEPS.c.workflow_key == "subscription",
            _BILLING_STEPS.c.step_key.in_(removed_step_keys),
        )
        .values(active=False)
    )


def _reseed_onboarding(
    bind,
    flow_key: str,
    steps: list[tuple],
    removed_step_keys: set[str],
) -> None:
    flow_id = bind.execute(
        sa.select(_ONBOARD_FLOWS.c.id).where(
            _ONBOARD_FLOWS.c.flow_key == flow_key,
            _ONBOARD_FLOWS.c.active.is_(True),
        )
    ).scalar()
    if flow_id is None:
        flow_id = bind.execute(
            sa.select(_ONBOARD_FLOWS.c.id).where(
                _ONBOARD_FLOWS.c.flow_key == flow_key,
                _ONBOARD_FLOWS.c.version == 1,
            )
        ).scalar()
        if flow_id is None:
            flow_id = bind.execute(
                _ONBOARD_FLOWS.insert().values(
                    flow_key=flow_key,
                    subject_type="candidate",
                    version=1,
                    active=True,
                )
            ).lastrowid
        else:
            bind.execute(
                _ONBOARD_FLOWS.update()
                .where(_ONBOARD_FLOWS.c.id == flow_id)
                .values(active=True)
            )

    for order, (step_key, kind, config) in enumerate(steps, 1):
        existing_id = bind.execute(
            sa.select(_ONBOARD_STEPS.c.id).where(
                _ONBOARD_STEPS.c.flow_id == flow_id,
                _ONBOARD_STEPS.c.step_key == step_key,
            )
        ).scalar()
        values = dict(
            step_order=order * 10,
            kind=kind.value,
            required=True,
            active=True,
            config=config,
        )
        if existing_id is None:
            bind.execute(
                _ONBOARD_STEPS.insert().values(
                    flow_id=flow_id,
                    step_key=step_key,
                    **values,
                )
            )
        else:
            bind.execute(
                _ONBOARD_STEPS.update()
                .where(_ONBOARD_STEPS.c.id == existing_id)
                .values(**values)
            )

    bind.execute(
        _ONBOARD_STEPS.update()
        .where(
            _ONBOARD_STEPS.c.flow_id == flow_id,
            _ONBOARD_STEPS.c.step_key.in_(removed_step_keys),
        )
        .values(active=False)
    )


def upgrade() -> None:
    billing_steps, removed_billing, flow_key, onboard_steps, removed_onboard = (
        _load_seed_data()
    )
    bind = op.get_bind()
    _reseed_billing(bind, billing_steps, removed_billing)
    _reseed_onboarding(bind, flow_key, onboard_steps, removed_onboard)


def downgrade() -> None:
    # Data reseed only: reverting rows could invalidate live workflow state.
    pass
