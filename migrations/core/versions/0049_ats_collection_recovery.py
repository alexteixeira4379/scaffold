"""Bound catalog restarts and retain sanitized collection diagnostics."""
from alembic import op
import sqlalchemy as sa
revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ats_discovery_sources", sa.Column("collection_restarts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ats_collection_runs", sa.Column("last_error_detail", sa.JSON(), nullable=True))
    op.add_column("ats_collection_runs", sa.Column("discarded", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("ats_collection_runs", "discarded")
    op.drop_column("ats_collection_runs", "last_error_detail")
    op.drop_column("ats_discovery_sources", "collection_restarts")
