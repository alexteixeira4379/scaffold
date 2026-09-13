"""Post-refactor drops: billing_customers.pending_plan_code and onboard_steps.

Follow-up to migration 0026/0027 (workflow orchestration).

- `billing_customers.pending_plan_code` (added in 0020) is dropped: the plan
  selected during onboarding now lives in the billing workflow session tables
  (`billing_workflow_sessions` / `billing_workflow_step_states`), not as a
  pending flag on the customer row.
- `onboard_steps` (created in 0024, reseeded in 0025) is dropped: the
  onboarding roteiro now lives in the orchestrator tables (`onboard_flows` +
  `onboard_flow_steps`).

Downgrade re-adds `pending_plan_code` (nullable, values unrecoverable) and
recreates `onboard_steps` with its 0024 schema *without* the seed rows from
0024/0025 — re-run those migrations' data inserts manually if the roteiro
content is needed after a downgrade.

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import OnboardPhase, OnboardStepLayoutKind
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_onboard_phase = mysql_enum(OnboardPhase, "onboard_phase")
_onboard_step_layout_kind = mysql_enum(OnboardStepLayoutKind, "onboard_step_layout_kind")


def upgrade() -> None:
    op.drop_column("billing_customers", "pending_plan_code")
    op.drop_table("onboard_steps")


def downgrade() -> None:
    op.create_table(
        "onboard_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "phase",
            _onboard_phase,
            server_default=mysql_default("onboard_phase", OnboardPhase.BASE_PROFILE),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "layout_kind",
            _onboard_step_layout_kind,
            server_default=mysql_default("onboard_step_layout_kind", OnboardStepLayoutKind.TEXT),
            nullable=False,
        ),
        sa.Column("layout_spec", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("accepted_answers", sa.JSON(), server_default=sa.text("(JSON_ARRAY())"), nullable=False),
        sa.Column("answer_format", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboard_steps")),
        sa.UniqueConstraint("step_key", name=op.f("uq_onboard_steps_step_key")),
    )
    op.add_column(
        "billing_customers",
        sa.Column("pending_plan_code", sa.String(128), nullable=True),
    )
