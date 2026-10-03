"""Retire Lever only; export a typed backup before deleting its catalog subtree.

Run in the production discovery runtime (its Settings supply the database URL).
Modes: plan, backup, pause, purge. Purge requires the reviewed job count and the
SHA256 of a locally retrieved backup. Providers/sources remain inactive tombstones.
No schema changes or disabled foreign-key checks are used.
"""

import argparse
import base64
import datetime
import decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import MetaData, and_, create_engine, or_, select, text

HOSTS = {"jobs.lever.co", "jobs.eu.lever.co", "api.lever.co", "api.eu.lever.co"}
PROTECTED = {"candidates", "companies", "professional_entities", "application_entitlements"}
REFS = {"job_id": "jobs", "job_match_id": "job_matches", "match_id": "job_matches",
        "application_id": "job_applications", "job_application_id": "job_applications",
        "application_run_id": "application_runs"}


def retired_url(value):
    try:
        return urlsplit(value or "").hostname in HOSTS
    except ValueError:
        return False


def encode(value):
    if isinstance(value, (datetime.datetime, datetime.date, decimal.Decimal)):
        return {"__type__": type(value).__name__, "value": str(value)}
    if isinstance(value, bytes):
        return {"__type__": "bytes", "value": base64.b64encode(value).decode()}
    raise TypeError(type(value).__name__)


def key(table, row):
    return tuple(row[c.name] for c in table.primary_key)


def ids(selected, table):
    return {r["id"] for r in selected.get(table, []) if "id" in r}


def linked_payload(value, targets, parent=""):
    if isinstance(value, dict):
        for name, item in value.items():
            target = REFS.get(name)
            if name == "id":
                target = {"job": "jobs", "application": "job_applications",
                          "job_match": "job_matches"}.get(parent)
            if target and str(item) in targets[target]:
                return True
            if linked_payload(item, targets, name):
                return True
    elif isinstance(value, list):
        return any(linked_payload(item, targets, parent) for item in value)
    return False


def collect(conn, metadata):
    tables = metadata.tables
    providers = [dict(r) for r in conn.execute(select(tables["ats_providers"])).mappings()
                 if r["code"].lower() in {"lever", "auto_jobs.lever.co", "auto_jobs.eu.lever.co"}
                 or retired_url(r.get("base_url"))]
    provider_ids = {r["id"] for r in providers}
    jobs = tables["jobs"]
    host = "LOWER(SUBSTRING_INDEX(SUBSTRING_INDEX(canonical_url,'/',3),'/',-1))"
    root = or_(jobs.c.ats_provider_id.in_(provider_ids), text(
        host + " IN ('jobs.lever.co','jobs.eu.lever.co','api.lever.co','api.eu.lever.co')"))
    selected = {"jobs": [dict(r) for r in conn.execute(select(jobs).where(root)).mappings()]}
    # Discover all actual FK descendants, plus deliberate non-FK application references.
    for _ in range(len(tables)):
        changed = False
        for name, table in tables.items():
            if name == "jobs":
                continue
            conditions = []
            for column in table.columns:
                parent = REFS.get(column.name)
                if parent and selected.get(parent):
                    conditions.append(column.in_(ids(selected, parent)))
                for fk in column.foreign_keys:
                    parent = fk.column.table.name
                    if selected.get(parent):
                        conditions.append(column.in_({r[fk.column.name] for r in selected[parent]}))
            if name == "application_sessions" and provider_ids:
                conditions.append(table.c.ats_provider_id.in_(provider_ids))
            if not conditions:
                continue
            if name in PROTECTED or name.startswith(("resume_", "billing_", "candidate_")):
                raise RuntimeError("Refusing to select shared data: " + name)
            rows = [dict(r) for r in conn.execute(select(table).where(or_(*conditions))).mappings()]
            if len(rows) != len(selected.get(name, [])):
                changed = True
            if rows:
                selected[name] = rows
        if not changed:
            break
    else:
        raise RuntimeError("Dependency closure did not converge")
    targets = {name: {str(i) for i in ids(selected, name)} for name in set(REFS.values())}
    for name, field in [("domain_outbox", "payload"), ("domain_projections", "data")]:
        table = tables[name]
        rows = []
        for row in conn.execute(select(table)).mappings():
            aggregate = row.get("aggregate", "")
            aggregate_match = any(aggregate == f"{prefix}:{i}" for prefix, parent in
                                  [("job", "jobs"), ("application", "job_applications"),
                                   ("match", "job_matches")] for i in targets[parent])
            if aggregate_match or linked_payload(row[field], targets):
                rows.append(dict(row))
        if rows:
            selected[name] = rows
    controls = {"ats_providers": providers}
    for name in ["ats_discovery_sources", "ats_provider_configs", "ats_provider_domains",
                 "ats_provider_rules", "ats_provider_schedules"]:
        table = tables[name]
        controls[name] = [dict(r) for r in conn.execute(select(table)).mappings()
                          if r["ats_provider_id"] in provider_ids
                          or retired_url(r.get("base_url"))
                          or r.get("domain") in HOSTS]
    for name in ["ats_discovery_prospects", "ats_discovery_observations", "ats_discovery_search_runs"]:
        table = tables[name]
        controls[name] = [dict(r) for r in conn.execute(select(table)).mappings()
                          if r.get("provider") == "lever" or retired_url(r.get("url"))
                          or r.get("config", {}).get("provider") == "lever"]
    return selected, controls


def row_filter(table, rows):
    columns = list(table.primary_key)
    if not columns:
        raise RuntimeError("Table has no primary key: " + table.name)
    return or_(*(and_(*(column == row[column.name] for column in columns)) for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "backup", "pause", "purge"])
    parser.add_argument("--backup", default="/tmp/lever-retirement-backup.json.gz")
    parser.add_argument("--expected-jobs", type=int)
    parser.add_argument("--backup-sha256")
    args = parser.parse_args()
    from ats_discovery.config import Settings

    engine = create_engine(Settings().database_url.get_secret_value())
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.begin() as conn:
        if args.mode in {"plan", "backup"}:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        selected, controls = collect(conn, metadata)
        counts = {name: len(rows) for name, rows in selected.items()}
        report = {"mode": args.mode, "database": conn.exec_driver_sql("SELECT DATABASE()").scalar(),
                  "rows": counts, "controls": {name: len(rows) for name, rows in controls.items()}}
        if args.mode == "backup":
            blob = gzip.compress(json.dumps({"schema_version": 1, "rows": selected, "controls": controls},
                                           default=encode, separators=(",", ":")).encode())
            fd = os.open(args.backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(blob)
                file.flush()
                os.fsync(file.fileno())
            report.update(backup=args.backup, sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob))
        elif args.mode in {"pause", "purge"}:
            blob = Path(args.backup).read_bytes()
            if not args.backup_sha256 or hashlib.sha256(blob).hexdigest() != args.backup_sha256:
                raise RuntimeError("Backup digest mismatch")
            backup = json.loads(gzip.decompress(blob))
            for name, rows in (selected | controls).items():
                originals = backup["rows"].get(name, backup["controls"].get(name, []))
                covered = {key(metadata.tables[name], row) for row in originals}
                if any(key(metadata.tables[name], row) not in covered for row in rows):
                    raise RuntimeError("New rows require a fresh backup: " + name)
            for name, rows in controls.items():
                if not rows:
                    continue
                table = metadata.tables[name]
                values = {"active": False} if "active" in table.c else {"status": "retired", "next_attempt_at": None}
                conn.execute(table.update().where(row_filter(table, rows)).values(**values))
            if selected.get("application_authorizations"):
                table = metadata.tables["application_authorizations"]
                conn.execute(table.update().where(row_filter(table, selected[table.name])).values(status="retired"))
            if args.mode == "purge":
                if args.expected_jobs is None or counts.get("jobs") != args.expected_jobs:
                    raise RuntimeError("Reviewed job count changed")
                # Actual FK order; non-FK outbox/authorization/execution rows also removed.
                order = list(reversed(metadata.sorted_tables))
                for table in order:
                    rows = selected.get(table.name, [])
                    for offset in range(0, len(rows), 300):
                        conn.execute(table.delete().where(row_filter(table, rows[offset:offset + 300])))
                remaining, _ = collect(conn, metadata)
                if any(remaining.values()):
                    raise RuntimeError("Retirement verification failed; rolling back")
                report["remaining_jobs"] = 0
        print(json.dumps(report, sort_keys=True))
    engine.dispose()


if __name__ == "__main__":
    main()
