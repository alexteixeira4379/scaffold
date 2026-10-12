"""Canonical legal declarations; legacy JSON remains an immutable migration snapshot."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade():
    precise = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    for name in (
        "information_adopted",
        "work_permissions_adopted",
        "accommodations_adopted",
        "credentials_adopted",
    ):
        op.add_column(
            "candidate_application_data",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    op.add_column(
        "candidate_application_data",
        sa.Column(
            "accommodation_requested", sa.String(8), nullable=False, server_default="unknown"
        ),
    )
    op.add_column(
        "candidate_application_data",
        sa.Column("application_context_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "candidate_application_data", sa.Column("information_declared_at", precise, nullable=True)
    )
    op.add_column(
        "candidate_application_data", sa.Column("information_source", sa.String(32), nullable=True)
    )
    op.create_table(
        "candidate_work_permissions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "candidate_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("authorization", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("sponsorship", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("declaration_source", sa.String(32), nullable=True),
        sa.Column("declared_at", precise, nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_work_permission_candidate",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("candidate_id", "country", name="uq_candidate_work_permission_country"),
        sa.CheckConstraint(
            "authorization IN ('yes','no','unknown')", name="work_permission_authorization"
        ),
        sa.CheckConstraint(
            "sponsorship IN ('yes','no','unknown')", name="work_permission_sponsorship"
        ),
    )
    for name, type_ in (
        ("issuer", sa.String(200)),
        ("reference", sa.String(200)),
        ("valid_until", sa.Date()),
        ("declaration_source", sa.String(32)),
        ("declared_at", precise),
    ):
        op.add_column("resume_profile_credentials", sa.Column(name, type_, nullable=True))
    if op.get_context().dialect.name == "mysql":
        op.alter_column(
            "resume_profile_credentials",
            "credential_type",
            existing_type=mysql.ENUM("course", "certification"),
            type_=mysql.ENUM("course", "certification", "license", "other"),
            existing_nullable=False,
        )
    if op.get_context().as_sql:
        return
    # Compatibility-only backfill. New enum credential records are intentionally
    # deferred until every reader has deployed the new scaffold enum.
    from scaffold.candidate_information import legacy_seed

    bind = op.get_bind()
    application = sa.table(
        "candidate_application_data",
        sa.column("candidate_id"),
        sa.column("work_authorization"),
        sa.column("legal_information"),
        sa.column("accessibility_resources"),
        *[
            sa.column(name)
            for name in (
                "information_adopted",
                "work_permissions_adopted",
                "accommodations_adopted",
                "credentials_adopted",
                "accommodation_requested",
                "application_context_notes",
                "information_source",
                "information_declared_at",
            )
        ],
    )
    permissions = sa.table(
        "candidate_work_permissions",
        *[
            sa.column(name)
            for name in (
                "candidate_id",
                "country",
                "authorization",
                "sponsorship",
                "valid_until",
                "declaration_source",
                "declared_at",
            )
        ],
    )
    records = (
        bind.execute(
            sa.select(
                application.c.candidate_id,
                application.c.work_authorization,
                application.c.legal_information,
                application.c.accessibility_resources,
            )
        )
        .mappings()
        .all()
    )
    for row in records:
        updates, rows = legacy_seed(dict(row))
        if updates:
            bind.execute(
                application.update()
                .where(application.c.candidate_id == row["candidate_id"])
                .values(**updates)
            )
        for permission in rows:
            bind.execute(
                permissions.insert().values(candidate_id=row["candidate_id"], **permission)
            )


def downgrade():
    raise RuntimeError(
        "Canonical candidate declarations and adoption barriers must survive rollback"
    )
