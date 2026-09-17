"""Onboard flow reseed — re-apply seed_all.py::onboard_steps() (job_match card fix)

Identical mechanism to 0029: `alembic upgrade head` only re-runs a migration's
``upgrade()`` once, the first time it becomes the head. Editing
``scripts/seed_all.py`` after 0029 already applied (e.g. the job_match card's
suspense_2 config — removing hardcoded profile/job defaults, wiring real
cargo/senioridade/modelo/pais bindings) does NOT get picked up by a bare
`alembic upgrade head` on an environment already at 0029: there is nothing
new to apply, so the updated Python is never executed against that database.

This migration exists purely to force that re-apply once, for the current
edit to seed_all.py. It is bit-for-bit the same body as 0029 (upsert by
step_key, converges to whatever onboard_steps() currently returns) — no new
schema, no new revision-specific logic. The next time seed_all.py changes
after this one is head, the same problem will recur, and the fix is the
same: bump a new trivial revision like this one. (A more permanent fix would
have the `migration` service run the seeder unconditionally instead of only
inside a versioned migration — worth considering if this becomes frequent.)

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-17
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load_onboard_steps():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import seed_all  # local import: only needed at migration run time

    return seed_all.FLOW_KEY, seed_all.onboard_steps()


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
_PROFILE_FLOWS = sa.table(
    "profile_onboard_flows",
    sa.column("id", sa.BigInteger),
    sa.column("flow_id", sa.BigInteger),
)


def upgrade() -> None:
    flow_key, steps = _load_onboard_steps()
    bind = op.get_bind()

    flow_id = bind.execute(
        sa.select(_FLOWS.c.id).where(_FLOWS.c.flow_key == flow_key, _FLOWS.c.active.is_(True))
    ).scalar()

    if flow_id is None:
        flow_id = bind.execute(
            sa.select(_FLOWS.c.id).where(_FLOWS.c.flow_key == flow_key, _FLOWS.c.version == 1)
        ).scalar()
        if flow_id is None:
            flow_id = bind.execute(
                _FLOWS.insert().values(flow_key=flow_key, subject_type="candidate", version=1, active=True)
            ).inserted_primary_key[0]
        else:
            bind.execute(_FLOWS.update().where(_FLOWS.c.id == flow_id).values(active=True))

    for order, (step_key, kind, config) in enumerate(steps, 1):
        existing_id = bind.execute(
            sa.select(_STEPS.c.id).where(_STEPS.c.flow_id == flow_id, _STEPS.c.step_key == step_key)
        ).scalar()
        values = dict(step_order=order * 10, kind=kind.value, required=True, active=True, config=config)
        if existing_id is None:
            bind.execute(_STEPS.insert().values(flow_id=flow_id, step_key=step_key, **values))
        else:
            bind.execute(_STEPS.update().where(_STEPS.c.id == existing_id).values(**values))

    stale_ids = bind.execute(
        sa.select(_FLOWS.c.id).where(_FLOWS.c.flow_key == flow_key, _FLOWS.c.id != flow_id)
    ).scalars().all()
    for stale_id in stale_ids:
        in_use = bind.execute(
            sa.select(_PROFILE_FLOWS.c.id).where(_PROFILE_FLOWS.c.flow_id == stale_id).limit(1)
        ).scalar()
        if in_use is not None:
            continue
        bind.execute(_STEPS.delete().where(_STEPS.c.flow_id == stale_id))
        bind.execute(_FLOWS.delete().where(_FLOWS.c.id == stale_id))


def downgrade() -> None:
    # Data seed, not a schema change — nothing to structurally revert.
    pass
