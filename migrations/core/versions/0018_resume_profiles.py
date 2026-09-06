"""Add structured resume profiles.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "resume_profiles"):
        op.create_table(
            "resume_profiles",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("candidate_id", sa.BigInteger, sa.ForeignKey("candidates.id"), nullable=False),
            sa.Column("summary", sa.Text, nullable=True),
            sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("source", sa.Enum("workflow", "direct_api", name="resume_profile_source"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("candidate_id"),
        )

    if not _table_exists(bind, "resume_profile_experiences"):
        op.create_table(
            "resume_profile_experiences",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("resume_profile_id", sa.BigInteger, sa.ForeignKey("resume_profiles.id"), nullable=False),
            sa.Column("empresa", sa.String(255), nullable=False),
            sa.Column("cargo", sa.String(255), nullable=False),
            sa.Column("atividades", sa.Text, nullable=False),
            sa.Column("data_inicio", sa.Date, nullable=True),
            sa.Column("data_saida", sa.Date, nullable=True),
            sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not any(index["name"] == "ix_resume_profile_experiences_profile_id"
               for index in sa.inspect(bind).get_indexes("resume_profile_experiences")):
        op.create_index("ix_resume_profile_experiences_profile_id", "resume_profile_experiences", ["resume_profile_id"])

    if not _table_exists(bind, "resume_profile_education"):
        op.create_table(
            "resume_profile_education",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("resume_profile_id", sa.BigInteger, sa.ForeignKey("resume_profiles.id"), nullable=False),
            sa.Column("nivel", sa.String(64), nullable=False),
            sa.Column("instituicao", sa.String(255), nullable=False),
            sa.Column("curso", sa.String(255), nullable=True),
            sa.Column("data_inicio", sa.Date, nullable=True),
            sa.Column("data_termino", sa.Date, nullable=True),
            sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not any(index["name"] == "ix_resume_profile_education_profile_id"
               for index in sa.inspect(bind).get_indexes("resume_profile_education")):
        op.create_index("ix_resume_profile_education_profile_id", "resume_profile_education", ["resume_profile_id"])

    if not _table_exists(bind, "resume_profile_languages"):
        op.create_table(
            "resume_profile_languages",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("resume_profile_id", sa.BigInteger, sa.ForeignKey("resume_profiles.id"), nullable=False),
            sa.Column("idioma", sa.String(64), nullable=False),
            sa.Column("nivel", sa.String(32), nullable=False),
            sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not any(index["name"] == "ix_resume_profile_languages_profile_id"
               for index in sa.inspect(bind).get_indexes("resume_profile_languages")):
        op.create_index("ix_resume_profile_languages_profile_id", "resume_profile_languages", ["resume_profile_id"])

    if not _table_exists(bind, "resume_profile_credentials"):
        op.create_table(
            "resume_profile_credentials",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("resume_profile_id", sa.BigInteger, sa.ForeignKey("resume_profiles.id"), nullable=False),
            sa.Column("credential_type", sa.Enum("course", "certification", name="resume_credential_type"), nullable=False),
            sa.Column("nome", sa.String(255), nullable=False),
            sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not any(index["name"] == "ix_resume_profile_credentials_profile_id"
               for index in sa.inspect(bind).get_indexes("resume_profile_credentials")):
        op.create_index("ix_resume_profile_credentials_profile_id", "resume_profile_credentials", ["resume_profile_id"])

    if not _table_exists(bind, "resume_profile_volunteer_entries"):
        op.create_table(
            "resume_profile_volunteer_entries",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("resume_profile_id", sa.BigInteger, sa.ForeignKey("resume_profiles.id"), nullable=False),
            sa.Column("titulo", sa.String(255), nullable=False),
            sa.Column("tipo", sa.Enum("projeto", "voluntariado", name="resume_volunteer_type"), nullable=False),
            sa.Column("funcao", sa.String(255), nullable=False),
            sa.Column("descricao", sa.Text, nullable=False),
            sa.Column("impacto", sa.Text, nullable=True),
            sa.Column("data_inicio", sa.Date, nullable=True),
            sa.Column("data_fim", sa.Date, nullable=True),
            sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not any(index["name"] == "ix_resume_profile_volunteer_entries_profile_id"
               for index in sa.inspect(bind).get_indexes("resume_profile_volunteer_entries")):
        op.create_index("ix_resume_profile_volunteer_entries_profile_id", "resume_profile_volunteer_entries", ["resume_profile_id"])

    if not _table_exists(bind, "resume_profile_references"):
        op.create_table(
            "resume_profile_references",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("resume_profile_id", sa.BigInteger, sa.ForeignKey("resume_profiles.id"), nullable=False),
            sa.Column("tipo", sa.Enum("carta", "indicacao", name="resume_reference_type"), nullable=True),
            sa.Column("nome", sa.String(255), nullable=True),
            sa.Column("cargo", sa.String(255), nullable=True),
            sa.Column("descricao", sa.Text, nullable=False),
            sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not any(index["name"] == "ix_resume_profile_references_profile_id"
               for index in sa.inspect(bind).get_indexes("resume_profile_references")):
        op.create_index("ix_resume_profile_references_profile_id", "resume_profile_references", ["resume_profile_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "resume_profile_references",
        "resume_profile_volunteer_entries",
        "resume_profile_credentials",
        "resume_profile_languages",
        "resume_profile_education",
        "resume_profile_experiences",
        "resume_profiles",
    ):
        if _table_exists(bind, table):
            op.drop_table(table)
