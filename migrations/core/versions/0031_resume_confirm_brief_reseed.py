"""Resume build steps reseed — re-apply seederResumeBuildSteps.py::STEPS
(confirm_professional_brief copy + button-label fix)

Same mechanism as 0029/0030: `alembic upgrade head` only runs a migration's
``upgrade()`` once, the first time it becomes head. The `resume_build_steps`
table was originally created (schema only, no data) by 0006, and its rows
are populated by ``scripts/seederResumeBuildSteps.py``'s ``run_seed()`` —
which is never invoked automatically by the `migration` service's start
command (only ``alembic upgrade head`` runs there). So editing that script
after its steps were first seeded does NOT get picked up in production
without a migration like this one to force it.

This revision re-applies the current ``STEPS`` list (upsert by ``step_key``,
same fields ``get_or_create_step`` touches) directly against the database,
picking up the ``confirm_professional_brief`` copy change (the "Perfil
identificado" / AI-agents framing) and its button label fix (dropped the
trailing emoji so "Começar minha busca" fits WhatsApp's 20-character reply
button title limit). No schema change — purely a forced data re-sync, exactly
like 0030 did for `onboard_flow_steps`.

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-17
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load_resume_steps():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import seederResumeBuildSteps  # local import: only needed at migration run time

    return seederResumeBuildSteps.STEPS, seederResumeBuildSteps.REMOVED_STEP_KEYS


_STEPS_TABLE = sa.table(
    "resume_build_steps",
    sa.column("id", sa.BigInteger),
    sa.column("step_key", sa.String),
    sa.column("step_label", sa.Text),
    sa.column("description", sa.Text),
    sa.column("step_order", sa.Integer),
    sa.column("input_type", sa.String),
    sa.column("options", sa.JSON),
    sa.column("is_required", sa.Boolean),
    sa.column("active", sa.Boolean),
)


def upgrade() -> None:
    steps, removed_step_keys = _load_resume_steps()
    bind = op.get_bind()

    for step_data in steps:
        existing_id = bind.execute(
            sa.select(_STEPS_TABLE.c.id).where(_STEPS_TABLE.c.step_key == step_data["step_key"])
        ).scalar()
        values = dict(
            step_label=step_data["step_label"],
            description=step_data["description"],
            step_order=step_data["step_order"],
            input_type=step_data["input_type"].value,
            options=step_data["options"],
            is_required=step_data["is_required"],
            active=True,
        )
        if existing_id is None:
            bind.execute(_STEPS_TABLE.insert().values(step_key=step_data["step_key"], **values))
        else:
            bind.execute(_STEPS_TABLE.update().where(_STEPS_TABLE.c.id == existing_id).values(**values))

    for removed_key in removed_step_keys:
        bind.execute(
            _STEPS_TABLE.update()
            .where(_STEPS_TABLE.c.step_key == removed_key)
            .values(active=False)
        )


def downgrade() -> None:
    # Data seed, not a schema change — nothing to structurally revert.
    pass
