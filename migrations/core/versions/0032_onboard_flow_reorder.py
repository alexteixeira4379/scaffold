"""Onboard flow reorder — profile_brief moves before base_profile, suspense_1
folded away

Same mechanism as 0029/0030/0031: `alembic upgrade head` only re-runs a
migration's ``upgrade()`` once, the first time it becomes head. Editing
``scripts/seed_all.py::onboard_steps()`` after 0030 already applied (new
step order: search_goal -> profile_brief -> base_profile instead of
base_profile -> search_goal -> profile_brief; reworded welcome/welcome_intent
copy; suspense_1 removed and folded into base_profile's own opening line) is
a no-op on a bare `alembic upgrade head` against an already-migrated
database — nothing new to apply, so this migration exists purely to force
that re-apply.

Unlike 0030, this revision ALSO explicitly deactivates the `suspense_1` row:
``get_or_create_onboard_step`` only ever upserts step_keys present in the
current ``onboard_steps()`` list, it never deactivates a row whose step_key
stops appearing there. Without this, `suspense_1` would keep running for
every candidate forever, active but orphaned from the source list — the
exact "seeder never deletes" gotcha already seen with the legacy
country/seniority/confirm_goal candidate_workflow_steps rows.

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-18
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load_onboard_steps():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import seed_all  # local import: only needed at migration run time

    return seed_all.FLOW_KEY, seed_all.onboard_steps(), seed_all.REMOVED_ONBOARD_STEP_KEYS


_FLOWS = sa.table(
    "onboard_flows",
    sa.column("id", sa.BigInteger),
    sa.column("flow_key", sa.String),
    sa.column("subject_type", sa.String),
    sa.column("version", sa.Integer),
    sa.column("active", sa.Boolean),
)
_STEPS = sa.table(
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


def upgrade() -> None:
    flow_key, steps, removed_step_keys = _load_onboard_steps()
    bind = op.get_bind()

    flow_id = bind.execute(
        sa.select(_FLOWS.c.id).where(_FLOWS.c.flow_key == flow_key, _FLOWS.c.active.is_(True))
    ).scalar()
    if flow_id is None:
        flow_id = bind.execute(
            sa.select(_FLOWS.c.id).where(_FLOWS.c.flow_key == flow_key, _FLOWS.c.version == 1)
        ).scalar()

    for order, (step_key, kind, config) in enumerate(steps, 1):
        existing_id = bind.execute(
            sa.select(_STEPS.c.id).where(_STEPS.c.flow_id == flow_id, _STEPS.c.step_key == step_key)
        ).scalar()
        values = dict(step_order=order * 10, kind=kind.value, required=True, active=True, config=config)
        if existing_id is None:
            bind.execute(_STEPS.insert().values(flow_id=flow_id, step_key=step_key, **values))
        else:
            bind.execute(_STEPS.update().where(_STEPS.c.id == existing_id).values(**values))

    for removed_key in removed_step_keys:
        bind.execute(
            _STEPS.update()
            .where(_STEPS.c.flow_id == flow_id, _STEPS.c.step_key == removed_key)
            .values(active=False)
        )


def downgrade() -> None:
    # Data seed, not a schema change — nothing to structurally revert.
    pass
