"""Add repeat_index to resume_build_answers (repeat_for support)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-31

MySQL note: the old unique index uq_resume_build_answers_session_id on
(session_id, step_id) is the backing index for the session_id foreign key,
so MySQL refuses to drop it directly (errno 1553). We therefore drop both
foreign keys first, swap the unique index, then recreate the foreign keys.
Every step is guarded so the migration is safe to re-run after a partial
failure (repeat_index may already exist).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "resume_build_answers"
_OLD_UNIQUE = "uq_resume_build_answers_session_id"
_FK_SESSION = "fk_resume_build_answers_session_id_resume_build_sessions"
_FK_STEP = "fk_resume_build_answers_step_id_resume_build_steps"


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def _index_exists(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    names = {ix["name"] for ix in insp.get_indexes(table)}
    names |= {uc["name"] for uc in insp.get_unique_constraints(table)}
    return index in names


def _fk_exists(bind, table: str, fk: str) -> bool:
    insp = sa.inspect(bind)
    return fk in {f["name"] for f in insp.get_foreign_keys(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Drop FKs that rely on the old unique index as their backing index.
    if _fk_exists(bind, _TABLE, _FK_SESSION):
        op.drop_constraint(_FK_SESSION, _TABLE, type_="foreignkey")
    if _fk_exists(bind, _TABLE, _FK_STEP):
        op.drop_constraint(_FK_STEP, _TABLE, type_="foreignkey")

    # 2. Add the new column (guarded — may already exist from a partial run).
    if not _column_exists(bind, _TABLE, "repeat_index"):
        op.add_column(_TABLE, sa.Column("repeat_index", sa.Integer(), nullable=True))

    # 3. Swap the unique index (session_id, step_id) -> (session_id, step_id, repeat_index).
    if _index_exists(bind, _TABLE, _OLD_UNIQUE):
        op.drop_constraint(_OLD_UNIQUE, _TABLE, type_="unique")
    if not _index_exists(bind, _TABLE, op.f(_OLD_UNIQUE)):
        op.create_unique_constraint(
            op.f(_OLD_UNIQUE),
            _TABLE,
            ["session_id", "step_id", "repeat_index"],
        )

    # 4. Recreate the foreign keys.
    if not _fk_exists(bind, _TABLE, _FK_SESSION):
        op.create_foreign_key(
            _FK_SESSION, _TABLE, "resume_build_sessions", ["session_id"], ["id"]
        )
    if not _fk_exists(bind, _TABLE, _FK_STEP):
        op.create_foreign_key(
            _FK_STEP, _TABLE, "resume_build_steps", ["step_id"], ["id"]
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _fk_exists(bind, _TABLE, _FK_SESSION):
        op.drop_constraint(_FK_SESSION, _TABLE, type_="foreignkey")
    if _fk_exists(bind, _TABLE, _FK_STEP):
        op.drop_constraint(_FK_STEP, _TABLE, type_="foreignkey")

    if _index_exists(bind, _TABLE, op.f(_OLD_UNIQUE)):
        op.drop_constraint(op.f(_OLD_UNIQUE), _TABLE, type_="unique")
    op.create_unique_constraint(_OLD_UNIQUE, _TABLE, ["session_id", "step_id"])

    if _column_exists(bind, _TABLE, "repeat_index"):
        op.drop_column(_TABLE, "repeat_index")

    if not _fk_exists(bind, _TABLE, _FK_SESSION):
        op.create_foreign_key(
            _FK_SESSION, _TABLE, "resume_build_sessions", ["session_id"], ["id"]
        )
    if not _fk_exists(bind, _TABLE, _FK_STEP):
        op.create_foreign_key(
            _FK_STEP, _TABLE, "resume_build_steps", ["step_id"], ["id"]
        )
