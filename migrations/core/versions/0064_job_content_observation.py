"""Technical watermark for out-of-order catalog deliveries; no historical guess."""
from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("content_observed_at", sa.DateTime(), nullable=True))


def downgrade():
    raise RuntimeError("Keep freshness watermarks when rolling back code")
