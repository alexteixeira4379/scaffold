"""Preserve OTP correlation and verified destination timestamps at microsecond precision."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

CHALLENGE_COLUMNS = (
    ("requested_at", False),
    ("expires_at", False),
    ("screen_observed_at", True),
    ("code_expires_at", True),
    ("reserved_at", True),
    ("used_at", True),
    ("finished_at", True),
    ("created_at", False),
    ("updated_at", False),
)


def upgrade():
    # SQLite DateTime already roundtrips microseconds; do not rebuild its tables.
    if op.get_context().dialect.name != "mysql":
        return
    for column, nullable in CHALLENGE_COLUMNS:
        kwargs = {
            "existing_type": sa.DateTime(),
            "type_": mysql.DATETIME(fsp=6),
            "existing_nullable": nullable,
        }
        if column in {"created_at", "updated_at"}:
            kwargs["existing_server_default"] = sa.text("CURRENT_TIMESTAMP")
            kwargs["server_default"] = sa.text("CURRENT_TIMESTAMP(6)")
        op.alter_column("application_email_challenges", column, **kwargs)
    op.alter_column(
        "email_deliveries",
        "destination_verified_at",
        existing_type=sa.DateTime(),
        type_=mysql.DATETIME(fsp=6),
        existing_nullable=True,
    )


def downgrade():
    raise RuntimeError("Email challenge timestamp precision must not be reduced")
