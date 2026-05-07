"""Job professional entities

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_professional_entities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("matched_text", sa.String(length=512), nullable=False),
        sa.Column("source_field", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("weight", sa.Numeric(6, 2), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_job_professional_entities_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_professional_entities_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_professional_entities")),
        sa.UniqueConstraint("job_id", "entity_id", "source_field", name=op.f("uq_job_professional_entities_job_id")),
    )
    op.create_index("ix_job_professional_entities_job_id", "job_professional_entities", ["job_id"])
    op.create_index("ix_job_professional_entities_entity_id", "job_professional_entities", ["entity_id"])
    op.create_index(
        "ix_job_professional_entities_job_id_source_field",
        "job_professional_entities",
        ["job_id", "source_field"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_professional_entities_job_id_source_field", "job_professional_entities")
    op.drop_index("ix_job_professional_entities_entity_id", "job_professional_entities")
    op.drop_index("ix_job_professional_entities_job_id", "job_professional_entities")
    op.drop_table("job_professional_entities")
