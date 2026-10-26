"""Measure local durable commits; not a promise of full-pipeline throughput.

Only a dedicated localhost database ending _test is accepted. RabbitMQ confirm
and restart behavior are covered separately by tests/test_durable_transport.py.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import time
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, event, insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from scaffold.messaging.ports import FetchedMessage
from scaffold.messaging.processing import DurableDelivery, delivery_transaction, enqueue_output
from scaffold.messaging.worker import QueueWorkerRunner
from scaffold.models.domain_delivery import DomainInbox, DomainOutbox, WorkerDelivery, WorkerQuarantine

metadata = MetaData()
commits = Table("worker_benchmark_commits", metadata,
                Column("scenario", String(64), primary_key=True), Column("id", Integer, primary_key=True))


async def scenario(url, count, concurrency, poison_rate, run_id):
    engine = create_async_engine(url, pool_size=concurrency + 2, max_overflow=0)
    peak_connections = 0
    @event.listens_for(engine.sync_engine, "checkout")
    def checkout(*_):
        nonlocal peak_connections
        peak_connections = max(peak_connections, engine.pool.checkedout())
    async with engine.begin() as connection:
        for table in (DomainInbox.__table__, DomainOutbox.__table__, WorkerDelivery.__table__, WorkerQuarantine.__table__):
            await connection.run_sync(table.create, checkfirst=True)
        await connection.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    stop = asyncio.Event()
    latencies = []
    quarantined = 0
    rejected = 0
    interval = round(1 / poison_rate) if poison_rate else 0
    expected_bad = count // interval if interval else 0

    class Queue:
        index = 0
        async def read(self):
            self.index += 1
            if self.index > count:
                stop.set()
                return None
            index = self.index
            start = time.perf_counter()
            invalid = bool(interval and index % interval == 0)
            size = 256 * 1024 if index % 97 == 0 else 64 * 1024 if index % 19 == 0 else 4096 if index % 3 == 0 else 1024
            body = {"event_id": f"{run_id}-{index}", "id": index, "description": "x" * size}
            async def ack():
                nonlocal quarantined
                if invalid:
                    quarantined += 1
                else:
                    latencies.append(time.perf_counter() - start)
            async def nack(requeue=False):
                nonlocal rejected
                rejected += 1
            return FetchedMessage(body, 2, run_id, "benchmark.input", ack, nack,
                                  raw_body=b"{invalid" if invalid else None,
                                  decode_error="invalid_json" if invalid else None)

    async def handler(message):
        async with delivery_transaction(factory) as session:
            await session.execute(insert(commits).values(scenario=run_id, id=message.body["id"]))
            await enqueue_output(session, run_id, "benchmark.output", {"id": message.body["id"]})
        await message.delete()

    worker = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=lambda: asyncio.sleep(0),
                              delivery=DurableDelivery(factory, run_id), max_in_flight=concurrency)
    start = time.perf_counter()
    await worker.run(stop)
    duration = time.perf_counter() - start
    samples = sorted(latencies)
    assert len(samples) == count - expected_bad and quarantined == expected_bad and rejected == 0, (
        len(samples), quarantined, rejected, worker._delivery.counters.values)
    result = dict(messages=count, concurrency=concurrency, poison_rate=poison_rate,
                  useful_commits=len(samples), quarantined=quarantined, elapsed_s=round(duration, 3),
                  useful_commits_per_second=round(len(samples) / duration, 2),
                  p95_ms=round(samples[min(len(samples)-1, int(len(samples)*.95))] * 1000, 2),
                  p99_ms=round(samples[min(len(samples)-1, int(len(samples)*.99))] * 1000, 2),
                  peak_connections=peak_connections, peak_process_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2))
    await engine.dispose()
    return result


async def main(args):
    target = make_url(args.database_url)
    if target.host not in {"127.0.0.1", "localhost"} or not target.database.endswith("_test"):
        raise ValueError("only an isolated localhost *_test database is allowed")
    results = []
    stamp = str(time.time_ns())
    for concurrency in args.concurrency:
        for poison in (0, .01):
            run_id = f"bench-{stamp}-{concurrency}-{int(poison*100)}"
            item = await scenario(args.database_url, args.messages, concurrency, poison, run_id)
            results.append(item)
            print(json.dumps(item), flush=True)
    for concurrency in args.concurrency:
        healthy, poison = [row for row in results if row["concurrency"] == concurrency]
        poison["fraction_of_healthy_throughput"] = round(poison["useful_commits_per_second"] / healthy["useful_commits_per_second"], 3)
    args.output.write_text(json.dumps({"measurement": "local transactional commits and pending outbox, not end-to-end",
                                     "results": results}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("TEST_WORKER_DATABASE_URL"), required=not os.getenv("TEST_WORKER_DATABASE_URL"))
    parser.add_argument("--messages", type=int, default=10000)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
