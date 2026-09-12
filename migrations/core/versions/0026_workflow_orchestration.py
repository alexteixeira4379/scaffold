"""Workflow orchestration tables

Wave 0 of the workflow refactor: each domain API owns its workflow process
(sessions/steps/answers, mirroring ``resume_build_*``), and the
conversation-worker becomes an orchestrator with its own tables.

* Orchestrator tables (owner: conversation-worker): ``onboard_flows``,
  ``onboard_flow_steps``, ``profile_onboard_flows``,
  ``profile_onboard_step_states``.
* Domain workflow trios: ``candidate_workflow_*`` (candidate-api) and
  ``billing_workflow_*`` (billing-api).

``input_type`` reuses the existing ``ResumeStepInputType`` value set (stored
as a per-table MySQL enum named ``workflow_step_input_type``).

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import (
    OrchestratorStepKind,
    OrchestratorStepStatus,
    ProfileOnboardFlowStatus,
    ResumeStepInputType,
    WorkflowSessionStatus,
)
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_orchestrator_step_kind = mysql_enum(OrchestratorStepKind, "orchestrator_step_kind")
_orchestrator_step_status = mysql_enum(OrchestratorStepStatus, "orchestrator_step_status")
_profile_onboard_flow_status = mysql_enum(ProfileOnboardFlowStatus, "profile_onboard_flow_status")
_workflow_session_status = mysql_enum(WorkflowSessionStatus, "workflow_session_status")
_workflow_step_input_type = mysql_enum(ResumeStepInputType, "workflow_step_input_type")


def _create_workflow_session_table(table: str) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("workflow_key", sa.String(128), nullable=False),
        sa.Column(
            "status",
            _workflow_session_status,
            server_default=mysql_default("workflow_session_status", WorkflowSessionStatus.STARTED),
            nullable=False,
        ),
        sa.Column("current_step_key", sa.String(128), nullable=True),
        sa.Column("session_metadata", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f(f"fk_{table}_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
    )
    op.create_index(f"ix_{table}_candidate_id", table, ["candidate_id"])
    op.create_index(f"ix_{table}_candidate_workflow", table, ["candidate_id", "workflow_key"])


def _create_workflow_step_table(table: str) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("workflow_key", sa.String(128), nullable=False),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "input_type",
            _workflow_step_input_type,
            server_default=mysql_default("workflow_step_input_type", ResumeStepInputType.TEXT),
            nullable=False,
        ),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("options", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint("workflow_key", "step_key", name=op.f(f"uq_{table}_workflow_key")),
    )
    op.create_index(f"ix_{table}_workflow_key", table, ["workflow_key"])


def _create_workflow_answer_table(table: str, sessions_table: str, steps_table: str) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("step_id", sa.BigInteger(), nullable=False),
        sa.Column("repeat_index", sa.Integer(), nullable=True),
        sa.Column("answer_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], [f"{sessions_table}.id"], name=op.f(f"fk_{table}_session_id_{sessions_table}")),
        sa.ForeignKeyConstraint(["step_id"], [f"{steps_table}.id"], name=op.f(f"fk_{table}_step_id_{steps_table}")),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint("session_id", "step_id", "repeat_index", name=op.f(f"uq_{table}_session_id")),
    )


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Orchestrator tables (owner: conversation-worker)                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "onboard_flows",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flow_key", sa.String(128), nullable=False),
        sa.Column("subject_type", sa.String(32), server_default="candidate", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboard_flows")),
        sa.UniqueConstraint("flow_key", "version", name=op.f("uq_onboard_flows_flow_key")),
    )

    op.create_table(
        "onboard_flow_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flow_id", sa.BigInteger(), nullable=False),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "kind",
            _orchestrator_step_kind,
            server_default=mysql_default("orchestrator_step_kind", OrchestratorStepKind.QUESTION),
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("config", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["onboard_flows.id"], name=op.f("fk_onboard_flow_steps_flow_id_onboard_flows")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboard_flow_steps")),
        sa.UniqueConstraint("flow_id", "step_key", name=op.f("uq_onboard_flow_steps_flow_id")),
    )
    op.create_index("ix_onboard_flow_steps_flow_id", "onboard_flow_steps", ["flow_id"])

    op.create_table(
        "profile_onboard_flows",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.String(191), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("flow_id", sa.BigInteger(), nullable=False),
        sa.Column("flow_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            _profile_onboard_flow_status,
            server_default=mysql_default("profile_onboard_flow_status", ProfileOnboardFlowStatus.IN_PROGRESS),
            nullable=False,
        ),
        sa.Column("current_step_key", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_profile_onboard_flows_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["flow_id"], ["onboard_flows.id"], name=op.f("fk_profile_onboard_flows_flow_id_onboard_flows")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_onboard_flows")),
    )
    op.create_index("ix_profile_onboard_flows_profile_id", "profile_onboard_flows", ["profile_id"])
    op.create_index("ix_profile_onboard_flows_candidate_id", "profile_onboard_flows", ["candidate_id"])

    op.create_table(
        "profile_onboard_step_states",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_flow_id", sa.BigInteger(), nullable=False),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column(
            "status",
            _orchestrator_step_status,
            server_default=mysql_default("orchestrator_step_status", OrchestratorStepStatus.PENDING),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("api_session_id", sa.BigInteger(), nullable=True),
        sa.Column("local_answer", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_flow_id"],
            ["profile_onboard_flows.id"],
            name=op.f("fk_profile_onboard_step_states_profile_flow_id_profile_onboard_flows"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_onboard_step_states")),
        sa.UniqueConstraint("profile_flow_id", "step_key", name=op.f("uq_profile_onboard_step_states_profile_flow_id")),
    )
    op.create_index(
        "ix_profile_onboard_step_states_profile_flow_id",
        "profile_onboard_step_states",
        ["profile_flow_id"],
    )

    # ------------------------------------------------------------------ #
    # Domain workflow trios (owners: candidate-api, billing-api)           #
    # ------------------------------------------------------------------ #
    for domain in ("candidate", "billing"):
        _create_workflow_session_table(f"{domain}_workflow_sessions")
        _create_workflow_step_table(f"{domain}_workflow_steps")
        _create_workflow_answer_table(
            f"{domain}_workflow_answers",
            f"{domain}_workflow_sessions",
            f"{domain}_workflow_steps",
        )


def downgrade() -> None:
    # NOTE: indexes are not dropped explicitly here — MySQL refuses to drop an
    # index that currently backs a FK constraint (errno 1553), and several of
    # these indexes (the ones covering an FK column) do exactly that. Plain
    # `op.drop_table()` removes the table's indexes and FKs together in one
    # DDL statement, so it is both sufficient and the only safe order.
    for domain in ("billing", "candidate"):
        op.drop_table(f"{domain}_workflow_answers")
        op.drop_table(f"{domain}_workflow_steps")
        op.drop_table(f"{domain}_workflow_sessions")

    op.drop_table("profile_onboard_step_states")
    op.drop_table("profile_onboard_flows")
    op.drop_table("onboard_flow_steps")
    op.drop_table("onboard_flows")
