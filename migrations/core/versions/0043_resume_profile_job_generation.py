"""Allow job_generation as resume profile source.

Revision ID: 0043
Revises: 0042
"""

from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE resume_profiles "
        "MODIFY COLUMN source ENUM('workflow', 'direct_api', 'job_generation') NOT NULL"
    )


def downgrade():
    op.execute(
        "ALTER TABLE resume_profiles "
        "MODIFY COLUMN source ENUM('workflow', 'direct_api') NOT NULL"
    )
