"""Preserve full job descriptions; type conversion may rebuild the table.

Run separately after checking actual MySQL version, metadata locks, table size,
and a timed rehearsal. Do not request INSTANT or promise LOCK=NONE.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "mysql":
        # Preserve attributes and compatible collation. utf8mb3 cannot preserve
        # supplementary Unicode, so upgrade only this description column.
        column = next(c for c in sa.inspect(op.get_bind()).get_columns("jobs") if c["name"] == "description")
        character_set, collation = op.get_bind().execute(sa.text(
            "SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name='jobs' AND column_name='description'"
        )).one()
        if character_set != "utf8mb4":
            candidate = collation.replace("utf8mb3_", "utf8mb4_", 1).replace("utf8_", "utf8mb4_", 1)
            supported = op.get_bind().scalar(sa.text(
                "SELECT COLLATION_NAME FROM information_schema.collations "
                "WHERE CHARACTER_SET_NAME='utf8mb4' AND COLLATION_NAME=:candidate"
            ), {"candidate": candidate})
            collation = supported or "utf8mb4_0900_ai_ci"
        op.alter_column(
            "jobs", "description", existing_type=column["type"],
            type_=MEDIUMTEXT(charset="utf8mb4", collation=collation),
            existing_nullable=column["nullable"], existing_server_default=column.get("default"),
            existing_comment=column.get("comment"),
        )


def downgrade():
    raise RuntimeError("MEDIUMTEXT must be preserved: descriptions may exceed TEXT capacity")
