"""Inspect and explicitly replay quarantined work, with durable operator evidence.

python -m scaffold.messaging.quarantine list --consumer job-registry-worker
python -m scaffold.messaging.quarantine replay ID --source job-registry-worker \
    --actor operator --reason description-capacity-fixed [--replacement corrected.json]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from scaffold.models.domain_delivery import WorkerDelivery, WorkerQuarantine


async def replay(factory, quarantine_id, *, source, actor, reason, replacement=None,
                 reconciliation_evidence=None, storage=None):
    from scaffold.messaging.domain import enqueue
    if not actor.strip() or not reason.strip() or not source.strip():
        raise ValueError("source, actor and reason are required")
    async with factory() as session, session.begin():
        record = await session.get(WorkerQuarantine, quarantine_id, with_for_update=True)
        if record is None:
            raise ValueError("quarantine_not_found")
        if record.replayed_at is not None:
            raise ValueError("quarantine_already_replayed")
        state = await session.get(WorkerDelivery, (record.consumer, record.event_id), with_for_update=True)
        if state is None or state.status not in {"quarantined", "uncertain"}:
            raise ValueError("delivery_not_quarantined")
        if state.status == "uncertain" and not reconciliation_evidence:
            raise ValueError("reconciliation_evidence_required")
        raw = record.raw_body
        if replacement is not None:
            raw = replacement
        elif record.storage_key:
            # Fetch before entering the caller's replay transaction when using
            # remote storage; CLI below explicitly preloads it as replacement.
            raise ValueError("export_external_payload_before_replay")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("replacement_must_be_json_object")
        state.status = "retry"
        state.failures = 0
        state.retry_generation += 1
        state.claim_token = state.claimed_until = None
        state.next_attempt_at = datetime.utcnow().replace(microsecond=0)
        state.updated_at = datetime.utcnow()
        record.replayed_at = datetime.utcnow()
        record.replayed_by = actor[:191]
        record.replay_metadata = dict(
            reason=reason, reconciliation_evidence=reconciliation_evidence,
            replacement_sha256=hashlib.sha256(raw).hexdigest(), source=source,
        )
        headers = dict(record.headers or {})
        headers.update({"x-event-id": record.event_id, "x-event-key": "sha256",
                        "x-quarantine-replay": record.id, "x-retry-generation": str(state.retry_generation)})
        if record.correlation_id:
            headers["x-correlation-id"] = record.correlation_id
        await enqueue(session, source, record.queue, payload, key=f"quarantine-replay:{record.id}",
                      available_at=state.next_attempt_at, headers=headers,
                      exchange=headers.get("x-original-exchange", ""))


async def inspect_records(factory, consumer=None, limit=20):
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    async with factory() as session:
        statement = select(WorkerQuarantine).order_by(WorkerQuarantine.created_at.desc()).limit(limit)
        if consumer:
            statement = statement.where(WorkerQuarantine.consumer == consumer)
        rows = list(await session.scalars(statement))
        return [dict(id=r.id, consumer=r.consumer, event_id=r.event_id, queue=r.queue,
                     reason=r.reason, attempts=r.attempts, created_at=str(r.created_at),
                     replayed_at=str(r.replayed_at) if r.replayed_at else None,
                     payload_sha256=r.payload_sha256, storage_key=r.storage_key) for r in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--consumer")
    listing.add_argument("--limit", type=int, default=20)
    redrive = commands.add_parser("replay")
    redrive.add_argument("id")
    for name in ("source", "actor", "reason"):
        redrive.add_argument("--" + name, required=True)
    redrive.add_argument("--replacement", type=Path)
    redrive.add_argument("--reconciliation-evidence")
    args = parser.parse_args()

    async def run():
        from scaffold.db.session import close_engine, get_session_factory
        try:
            if args.command == "list":
                print(json.dumps(await inspect_records(get_session_factory(), args.consumer, args.limit)))
            else:
                await replay(get_session_factory(), args.id, source=args.source, actor=args.actor,
                             reason=args.reason, replacement=args.replacement.read_bytes() if args.replacement else None,
                             reconciliation_evidence=args.reconciliation_evidence)
                print(json.dumps({"id": args.id, "status": "scheduled"}))
        finally:
            await close_engine()
    asyncio.run(run())


if __name__ == "__main__":
    main()
