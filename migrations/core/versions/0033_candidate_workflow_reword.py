"""Candidate workflow steps reword — re-apply seederCandidateWorkflowSteps.py::STEPS
(base_profile transition copy)

Same gotcha as 0031/0032, different table: `candidate_workflow_steps` is
populated by `scripts/seederCandidateWorkflowSteps.py`'s `run_seed()`, which
is never invoked automatically on deploy (only `alembic upgrade head` runs
on the `migration` service, and no prior migration ever baked this seeder
in — this table has had no forced-reseed migration until now). Editing the
`base_profile` step's `full_name` question (now opens with "Já coloquei
meus agentes para trabalhar... vou aproveitar para confirmar alguns dados"
instead of a bare "Para começar, me diga seu nome completo.", to match its
new position after profile_brief in the onboarding flow — see 0032) and the
`contact` question copy would otherwise never reach production.

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-18
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load_candidate_steps():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import seederCandidateWorkflowSteps  # local import: only needed at migration run time

    return seederCandidateWorkflowSteps.STEPS


_STEPS_TABLE = sa.table(
    "candidate_workflow_steps",
    sa.column("id", sa.BigInteger),
    sa.column("workflow_key", sa.String),
    sa.column("step_key", sa.String),
    sa.column("step_order", sa.Integer),
    sa.column("input_type", sa.String),
    sa.column("options", sa.JSON),
    sa.column("is_required", sa.Boolean),
    sa.column("active", sa.Boolean),
)


def upgrade() -> None:
    steps = _load_candidate_steps()
    bind = op.get_bind()

    for step_data in steps:
        existing_id = bind.execute(
            sa.select(_STEPS_TABLE.c.id).where(
                _STEPS_TABLE.c.workflow_key == step_data["workflow_key"],
                _STEPS_TABLE.c.step_key == step_data["step_key"],
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
                _STEPS_TABLE.insert().values(
                    workflow_key=step_data["workflow_key"], step_key=step_data["step_key"], **values
                )
            )
        else:
            bind.execute(_STEPS_TABLE.update().where(_STEPS_TABLE.c.id == existing_id).values(**values))


def downgrade() -> None:
    # Data seed, not a schema change — nothing to structurally revert.
    pass
