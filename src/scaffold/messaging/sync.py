import asyncio
import sys

from scaffold.config import get_settings
from scaffold.messaging.definitions import get_full_topology
from scaffold.messaging.topology import MessagingTopology


def _import_aio_pika():
    try:
        import aio_pika
    except ModuleNotFoundError as exc:
        print(
            "RabbitMQ sync requires the 'aio-pika' package to be installed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return aio_pika


async def sync_topology(url: str, topology: MessagingTopology) -> None:
    aio_pika = _import_aio_pika()
    print("Connecting to RabbitMQ...")
    connection = await aio_pika.connect_robust(url)

    try:
        channel = await connection.channel()

        for exchange_def in topology.exchanges:
            print(f"  exchange  {exchange_def.name} ({exchange_def.type}, durable={exchange_def.durable})")
            try:
                await channel.declare_exchange(
                    exchange_def.name,
                    aio_pika.ExchangeType(exchange_def.type),
                    durable=exchange_def.durable,
                )
            except Exception as exc:
                _raise_if_drift(exc, f"exchange '{exchange_def.name}'")
                raise

        for queue_def in topology.queues:
            print(f"  queue     {queue_def.name} (durable={queue_def.durable})")
            try:
                await channel.declare_queue(
                    queue_def.name,
                    durable=queue_def.durable,
                    arguments=queue_def.arguments or None,
                )
            except Exception as exc:
                _raise_if_drift(exc, f"queue '{queue_def.name}'")
                raise

        for binding_def in topology.bindings:
            print(f"  binding   {binding_def.source} -> {binding_def.destination} [{binding_def.routing_key}]")
            queue = await channel.declare_queue(binding_def.destination, passive=True)
            exchange = await channel.get_exchange(binding_def.source, ensure=False)
            await queue.bind(exchange, routing_key=binding_def.routing_key)

        await channel.close()

    finally:
        await connection.close()


def _raise_if_drift(exc: Exception, entity: str) -> None:
    msg = str(exc)
    if "PRECONDITION_FAILED" in msg or "inequivalent" in msg.lower():
        print(
            f"\nDRIFT DETECTED on {entity}:\n  {exc}\n\n"
            "The broker has an existing entity with incompatible configuration.\n"
            "Options:\n"
            "  1. Delete the conflicting entity from the broker and re-run sync\n"
            "  2. Rename to a new versioned name (e.g. append .v2)\n",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    settings = get_settings()

    if settings.rabbitmq_url is None:
        print("RABBITMQ_URL is not set", file=sys.stderr)
        sys.exit(1)

    topology = get_full_topology()
    print(
        f"Syncing topology: {len(topology.exchanges)} exchanges, "
        f"{len(topology.queues)} queues, "
        f"{len(topology.bindings)} bindings"
    )

    asyncio.run(sync_topology(settings.rabbitmq_url, topology))
    print("Done.")


if __name__ == "__main__":
    main()
