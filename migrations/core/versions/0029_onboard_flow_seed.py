"""Onboard flow seed — candidate_onboarding, single self-cleaning version

Runs the same logic as scripts/seed_all.py (target ``onboard``) inside a
migration, so `alembic upgrade head` alone brings onboard_flows /
onboard_flow_steps up to date — no separate manual script run required.

Reuses scripts/seed_all.py's onboard_steps()/FLOW_KEY as the single source of
truth (imported, not duplicated here) so editing that file is enough; running
this migration again (or a future one that imports the same function) always
converges to whatever onboard_steps() currently returns.

Idempotent and self-cleaning, same as seed_all.py:
  - attaches to whichever flow version is already active (never reactivates
    a stale one);
  - upserts each step by (flow_id, step_key);
  - deletes every other onboard_flows row for this flow_key, unless a
    profile_onboard_flows row still references it (real candidate history
    always wins over a clean slate).

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-15
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
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
            # .inserted_primary_key relies on the Table's declared primary key
            # to know which column to report back; the lightweight sa.table()
            # proxy here has no such metadata, so it comes back empty on a
            # truly fresh DB (IndexError). .lastrowid reads MySQL's
            # LAST_INSERT_ID() directly off the cursor instead — works
            # regardless of what the proxy declares.
            flow_id = bind.execute(
                _FLOWS.insert().values(flow_key=flow_key, subject_type="candidate", version=1, active=True)
            ).lastrowid
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
