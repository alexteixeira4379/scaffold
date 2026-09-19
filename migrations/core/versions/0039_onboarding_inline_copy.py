"""Highlight formats/actions with inline code; preserve layout and journey state."""
import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

# Frozen copy-only replacements. Do not reseed workflows or reset existing answers.
REPLACEMENTS = {
    "*áudio* ou *texto*": "`áudio` ou `texto`",
    "Empresa: *[content]*": "Empresa: `[content]`",
    "*currículo em PDF*": "currículo em `PDF`",
    "*áudio ou texto*": "`áudio` ou `texto`",
    "toque em *Quero corrigir*": "toque em `Quero corrigir`",
}


def _replace(replacements):
    bind = op.get_bind()
    table = sa.Table("resume_build_steps", sa.MetaData(), autoload_with=bind)
    for row in bind.execute(sa.select(table.c.id, table.c.options)).mappings():
        options = row["options"] or {}
        question = options.get("question", "")
        updated = question
        for before, after in replacements.items():
            updated = updated.replace(before, after)
        if updated != question:
            bind.execute(table.update().where(table.c.id == row["id"]).values(
                options={**options, "question": updated}))


def upgrade():
    _replace(REPLACEMENTS)


def downgrade():
    _replace({after: before for before, after in REPLACEMENTS.items()})
