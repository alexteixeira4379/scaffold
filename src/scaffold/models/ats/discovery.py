"""Durable discovery state. Times are UTC Unix seconds, identities are SHA-256 keys."""

from sqlalchemy import JSON, BigInteger, Column, Float, Index, Integer, LargeBinary, String, Text

from scaffold.base import CoreBase


def table(name, *columns, indexes=()):
    from sqlalchemy import Table

    return Table("ats_discovery_" + name, CoreBase.metadata, *columns, *indexes)


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
