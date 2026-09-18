"""Resume build steps reword — re-apply seederResumeBuildSteps.py::STEPS
(professional_brief résumé/áudio/texto copy + higher max_length)

Same gotcha as 0031, same table: the `professional_brief` question now
explicitly offers résumé upload / audio / free text (matching its new
position as the first substantive onboarding step — see 0032/0033), and its
`max_length` moved from 2000 to 8000 chars since a résumé's PDF-extracted
text (conversation-worker's MediaPipeline already handles the upload+extract
today, no code change needed there) would otherwise bounce with
INVALID_FORMAT. Neither change reaches production without a forced reseed,
exactly like 0031.

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-18
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
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
