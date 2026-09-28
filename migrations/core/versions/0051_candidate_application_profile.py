"""Add candidate application facts and multiple work modes without replacing legacy fields."""

from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade():
    for name, size in (
        ("cpf", 11),
        ("race_color", 100),
        ("sexual_orientation", 100),
        ("disability_types", 500),
        ("disability_cids", 250),
        ("accessibility_resources", 2000),
    ):
        op.add_column("candidate_application_data", sa.Column(name, sa.String(size), nullable=True))
    for table in ("candidate_preferences", "candidate_target_profiles"):
        op.add_column(table, sa.Column("remote_preferences", sa.JSON(), nullable=True))
    op.add_column(
        "candidate_preferences", sa.Column("salary_reviewed_at", sa.DateTime(), nullable=True)
    )
    # No backfill: a generic preferences update did not prove a salary review.


def downgrade():
    raise RuntimeError("Candidate declarations must be preserved; roll back application code only")
