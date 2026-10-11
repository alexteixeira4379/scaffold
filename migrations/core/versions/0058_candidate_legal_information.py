"""Generic candidate-declared legal and professional application information."""

from alembic import op
import sqlalchemy as sa

revision = "0058"
down_revision = "0057_linkedin_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "candidate_application_data", sa.Column("legal_information", sa.JSON(), nullable=True)
    )


def downgrade():
    raise RuntimeError("Candidate declarations must not be discarded during service rollback")
