"""ATS discovery durable pipeline and canonical registry identity.

Ambiguous legacy groups are flagged and left untouched. Their identities are
blocked in the prospect registry until manually reconciled. No activation changes.
"""

# Frozen schema for this revision; do not replace with runtime metadata.
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Float,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
)

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


_metadata = MetaData()


def table(name, *columns, indexes=()):
    from sqlalchemy import Table

    return Table("ats_discovery_" + name, _metadata, *columns, *indexes)


def pk():
    return Column("id", String(64), primary_key=True)


def stamp(name, nullable=False):
    return Column(name, Float(53), nullable=nullable)


search_runs = table(
    "search_runs",
    pk(),
    Column("fingerprint", String(64), nullable=False),
    Column("engine", String(16), nullable=False),
    Column("config", JSON, nullable=False),
    Column("status", String(24), nullable=False),
    Column("search_id", String(128)),
    Column("snapshot", LargeBinary(length=16777215)),
    Column("snapshot_hash", String(64)),
    Column("result_count", Integer, nullable=False, default=0),
    stamp("created_at"),
    stamp("next_attempt_at", True),
    Column("attempts", Integer, nullable=False, default=0),
    indexes=(
        Index("ix_discovery_runs_query", "fingerprint", "created_at"),
        Index("ix_discovery_runs_due", "status", "next_attempt_at"),
    ),
)
budget_cycles = table(
    "budget_cycles",
    pk(),
    Column("account", String(64), nullable=False),
    stamp("renewal_at"),
    stamp("reconciled_at"),
    Column("external_used", Integer, nullable=False),
    Column("external_remaining", Integer, nullable=False),
    Column("hourly_limit", Integer, nullable=False, default=250),
    Column("hourly_used", Integer, nullable=False, default=0),
    Column("local_used", Integer, nullable=False, default=0),
    Column("warning_level", Integer, nullable=False, default=0),
    indexes=(Index("ix_discovery_budget_account", "account", "renewal_at"),),
)
budget_reservations = table(
    "budget_reservations",
    pk(),
    Column("cycle_id", String(64), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("state", String(24), nullable=False),
    stamp("created_at"),
    indexes=(Index("ix_discovery_budget_pending", "cycle_id", "state"),),
)
observations = table(
    "observations",
    pk(),
    Column("run_id", String(64), nullable=False),
    Column("position", String(64), nullable=False),
    Column("url", Text, nullable=False),
    Column("destination", Text),
    Column("prospect_id", String(64)),
    Column("status", String(32), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    stamp("created_at"),
    stamp("next_attempt_at", True),
    indexes=(Index("ix_discovery_observation_due", "status", "next_attempt_at"),),
)
prospects = table(
    "prospects",
    pk(),
    Column("identity", Text, nullable=False),
    Column("provider", String(32), nullable=False),
    Column("tenant", String(128), nullable=False),
    Column("url", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("source_id", BigInteger),
    Column("validation_id", String(64)),
    Column("attempts", Integer, nullable=False, default=0),
    stamp("next_attempt_at", True),
    stamp("created_at"),
    indexes=(Index("ix_discovery_prospect_due", "status", "next_attempt_at"),),
)
source_aliases = table(
    "source_aliases",
    pk(),
    Column("identity", Text, nullable=False),
    Column("prospect_id", String(64), nullable=False),
    Column("proof", JSON, nullable=False),
)
validations = table(
    "validations",
    pk(),
    Column("prospect_id", String(64), nullable=False),
    Column("identity", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("reason", String(128), nullable=False),
    Column("parser_version", String(24), nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("snapshot", LargeBinary(length=16777215)),
    Column("snapshot_hash", String(64)),
    stamp("created_at"),
    stamp("valid_until"),
    indexes=(Index("ix_discovery_validation_prospect", "prospect_id", "created_at"),),
)
outbox = table(
    "outbox",
    pk(),
    Column("queue", String(128), nullable=False),
    Column("body", JSON, nullable=False),
    stamp("created_at"),
    stamp("published_at", True),
    indexes=(Index("ix_discovery_outbox_pending", "published_at", "created_at"),),
)
processed_events = table(
    "processed_events",
    Column("consumer", String(24), primary_key=True),
    Column("event_id", String(64), primary_key=True),
    Column("result", String(64), nullable=False),
    stamp("created_at"),
)
leases = table(
    "leases",
    pk(),
    Column("owner", String(64), nullable=False),
    Column("token", Integer, nullable=False),
    stamp("expires_at"),
)

_schema = SimpleNamespace(
    search_runs=search_runs,
    budget_cycles=budget_cycles,
    budget_reservations=budget_reservations,
    observations=observations,
    prospects=prospects,
    source_aliases=source_aliases,
    validations=validations,
    outbox=outbox,
    processed_events=processed_events,
    leases=leases,
)


def upgrade():
    d = _schema
    import time

    from scaffold.ats_identity import identify

    for column in (
        sa.Column("canonical_identity_hash", sa.String(64)),
        sa.Column("canonical_identity", sa.Text()),
        sa.Column("qualification_status", sa.String(32)),
        sa.Column("qualification_validation_id", sa.String(64)),
        sa.Column("discovery_metadata", sa.JSON()),
    ):
        op.add_column("ats_discovery_sources", column)
    op.create_index(
        "uq_ats_discovery_sources_canonical_identity_hash",
        "ats_discovery_sources",
        ["canonical_identity_hash"],
        unique=True,
    )
    bind = op.get_bind()
    for table in (
        d.search_runs,
        d.budget_cycles,
        d.budget_reservations,
        d.observations,
        d.prospects,
        d.source_aliases,
        d.validations,
        d.outbox,
        d.processed_events,
        d.leases,
    ):
        table.create(bind)
    sources = sa.table(
        "ats_discovery_sources",
        sa.column("id"),
        sa.column("base_url"),
        sa.column("canonical_identity"),
        sa.column("canonical_identity_hash"),
        sa.column("qualification_status"),
    )
    groups = {}
    for row in bind.execute(sa.select(sources.c.id, sources.c.base_url)).mappings():
        try:
            identity = identify(row["base_url"] or "")
        except ValueError:
            identity = None
        if identity:
            groups.setdefault(identity.digest, (identity, []))[1].append(row["id"])
    for key, (identity, ids) in groups.items():
        if len(ids) == 1:
            bind.execute(
                sources.update()
                .where(sources.c.id == ids[0])
                .values(canonical_identity=identity.key, canonical_identity_hash=key)
            )
        else:
            bind.execute(
                sources.update()
                .where(sources.c.id.in_(ids))
                .values(qualification_status="legacy_ambiguous")
            )
        bind.execute(
            d.prospects.insert().values(
                id=key,
                identity=identity.key,
                provider=identity.provider,
                tenant=identity.tenant,
                url=identity.url,
                status="known" if len(ids) == 1 else "legacy_ambiguous",
                source_id=ids[0] if len(ids) == 1 else None,
                attempts=0,
                created_at=time.time(),
            )
        )

    if bind.dialect.name == "mysql":
        for operation in ("INSERT", "UPDATE"):
            # Legacy NULL identities remain writable, but every new source must
            # supply the shared canonical contract. Raw SQL cannot bypass it.
            required = (
                "NEW.canonical_identity_hash IS NULL OR NEW.canonical_identity IS NULL"
                if operation == "INSERT"
                else "OLD.canonical_identity_hash IS NOT NULL AND (NEW.canonical_identity_hash IS NULL OR BINARY NEW.canonical_identity_hash <> BINARY OLD.canonical_identity_hash)"
            )
            op.execute(f"""CREATE TRIGGER ats_discovery_identity_{operation.lower()}
                BEFORE {operation} ON ats_discovery_sources FOR EACH ROW
                BEGIN
                    IF {required} THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ATS canonical identity required/immutable';
                    END IF;
                    IF NEW.canonical_identity_hash IS NOT NULL AND
                       BINARY NEW.canonical_identity_hash <> BINARY SHA2(NEW.canonical_identity, 256) THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ATS canonical digest mismatch';
                    END IF;
                    IF NEW.canonical_identity_hash IS NOT NULL AND EXISTS (
                        SELECT 1 FROM ats_discovery_prospects p
                        WHERE p.id = NEW.canonical_identity_hash AND p.status = 'legacy_ambiguous'
                    ) THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ATS legacy identity requires reconciliation';
                    END IF;
                END""")


def downgrade():
    if op.get_bind().dialect.name == "mysql":
        op.execute("DROP TRIGGER IF EXISTS ats_discovery_identity_insert")
        op.execute("DROP TRIGGER IF EXISTS ats_discovery_identity_update")
    for name in (
        "leases",
        "processed_events",
        "outbox",
        "validations",
        "source_aliases",
        "prospects",
        "observations",
        "budget_reservations",
        "budget_cycles",
        "search_runs",
    ):
        op.drop_table("ats_discovery_" + name)
    op.drop_index(
        "uq_ats_discovery_sources_canonical_identity_hash", table_name="ats_discovery_sources"
    )
    for column in (
        "discovery_metadata",
        "qualification_validation_id",
        "qualification_status",
        "canonical_identity",
        "canonical_identity_hash",
    ):
        op.drop_column("ats_discovery_sources", column)
