# Durable worker delivery

The runtime owns broker acknowledgements. Handlers declare an outcome through
`delete`, `transfer`, a typed exception, or an owning local transaction. Existing
handlers can use `ManagedMessage` during adoption; returning without an outcome
is quarantined explicitly. New behavior is enabled per runner with
`delivery=DurableDelivery(...)`, rather than changing every legacy runner at once.

## Transaction and identity contract

- Use `delivery_transaction(factory)` once around the owning database effects.
  Inbox insertion, effects and `enqueue_output` commit together. Duplicate inbox
  entries raise `DuplicateEvent`, which the runner treats as completed work.
- Preparation and remote calls belong outside that transaction. Before commit,
  the runtime checks its delivery lease token under lock. An expired owner cannot
  commit after another process acquired the event.
- Maintenance callers can pass `consumer` and `event_id` explicitly to
  `delivery_transaction`. They get an atomic inbox without inventing a runtime
  lease. The active runtime context always takes precedence.
- Output IDs are deterministic UUID5 values. `enqueue` can attach a stable
  transport ID to legacy commands without modifying their bodies. Deferral of a
  new generation must have a new transport identity; the semantic send/run key
  remains owned by its domain.
- `DeliveryPolicy.identity_fields` selects legacy intent IDs such as
  `message_id`. These values are hashed with their field name, preserving case
  distinctions on MySQL databases with case-insensitive collation. Existing
  domain event IDs remain compatible with the previous inbox. MySQL control and
  inbox event keys use a binary NO PAD collation, preserving case, accents and
  trailing characters without changing existing identity values.
- Without an explicit ID, fallback identity includes queue, correlation and the
  full observation, including collection metadata. Identical legacy observations
  are indistinguishable; a URL alone is never an event ID.

`WorkerDelivery.attempts` counts executions monotonically. `failures` records the
application failure budget. Infrastructure pauses and `DeferredMessage` waits do
not spend that budget. The default is five failures, spaced by 10, 60, 300 and
900 seconds with jitter. Every schedule has its own durable generation key.

## Failures, external effects and shutdown

Permanent contract/data errors go to durable quarantine. Unknown local failures
have the same finite budget as other transient failures. Database connectivity
and pool exhaustion pause consumption with bounded exponential backoff; retries
do not sleep while holding a message transaction. Read and reconnect failures
also have backoff. A busy duplicate is copied durably for later recovery rather
than pausing unrelated work.

Use `DeferredMessage(delay_seconds, reason)` for a dependency or capacity gate.
It retains the original intention and schedules another delivery without
consuming the failure budget.

External-effect runners opt into `external_effects=True`. A timeout, unclassified
external error or expired execution after a crash requires reconciliation. A
handler may explicitly identify a proven pre-send failure as retryable or
infrastructure failure. Persisted domain execution fences/receipts remain the
authority for browser applications and provider APIs. `delete(receipt={...})`
stores a small technical receipt with the completed delivery; it must not contain
message bodies, tokens or personal data.

On shutdown, stop admitting new work, drain within the configured deadline, then
close the consumer channel. Remaining deliveries return to RabbitMQ. Expired
local leases can recover; uncertain external executions require evidence before
replay. Configure platform draining time above the runner deadline.

## Transport, outbox and resource bounds

Continuous mode uses `basic.consume` on a channel owned by that input queue,
with prefetch equal to bounded concurrency. Publication uses a separate channel
with publisher confirms, persistent messages, `mandatory` and a timeout. Input
channels are independent between domain subscriptions and the outbox relay.

The relay claims at most 16 rows, commits the claim, publishes up to four
concurrently, then records results with a claim-token condition. No broker wait
holds a database transaction. Expired claims recover after restart. Confirmation
followed by a crash can publish twice; downstream inboxes are required.

Malformed historical outbox envelopes are isolated per row rather than aborting
the batch. The original row has `quarantined_at` and no `delivered_at`; it retains
its data. Publisher quarantine uses consumer `outbox-publisher` and the same
audited replay interface. A `storage_key` of `domain-outbox:<id>` refers to the
intact SQL row for exceptional payloads above 16 MiB, not an S3 object. Export
that raw body/payload and provide an inspected replacement. Corrected publisher
replay completes its control only after confirm. Pending-age queries exclude
quarantined rows; the ready index includes quarantine status so old poison rows
do not accumulate in every ready-work scan.

Default application messages are limited to 8 MiB, transport bounds to 16 MiB,
and inline quarantine to 16 MiB. Quarantine/outbox raw bytes use a binary control
column so the 16 MiB boundary itself is preserved. Larger quarantine payloads
  require an injected durable storage client or `WORKER_QUARANTINE_BUCKET` with
  the existing S3 settings. Failure to preserve evidence keeps
the source unacknowledged and pauses consumption.

The runner's default wire-payload admission budget is 128 MiB. It rejects
concurrency whose configured transport bound exceeds that budget. Parsed Python
objects, extraction state and external-client buffers add memory beyond wire
bytes; measure RSS during load. Before rollout, verify the actual RabbitMQ
`max_message_size`, MySQL `max_allowed_packet`, memory limits and total pool size
across replicas. Transport settings above these defaults require explicit sizing
and storage configuration.

## Deployment and recovery

1. Inspect actual schema, MySQL version, broker settings and locks. Rehearse
   migrations `0062` (control state), `0063` (description capacity) and `0064`
   (catalog freshness). Description conversion may rebuild the table; do not
   assume `INSTANT` or `LOCK=NONE`. Nullability/default/comment are preserved.
   Compatible utf8mb4 collation is retained; a legacy description charset is
   upgraded only on that column, retaining a matching supported utf8mb4 collation
   when available, so supplementary Unicode is not discarded or rejected.
2. Run migrations through the migration service before starting new code. A wheel
   update does not run migrations. Keep the existing queues and backlog intact.
3. Roll out each source with old processes drained. A legacy outbox relay does
   not understand new claim tokens, so do not run old/new relay implementations
   concurrently for the same source. Ensure consumers deduplicate before
   enabling replay or expanding producer concurrency.
4. Start at concurrency one, verify useful progress, then apply measured limits.
   Continuous consumers replace cron drains; collection schedules remain owned
   by their existing services. New retries use the SQL scheduler, not broker TTL
   dead-letter transfer. Keep old retry queues until existing contents drain.
5. Inspect quarantine with `python -m scaffold.messaging.quarantine list`.
   Replay one canary with `replay ID --source SERVICE --actor OPERATOR --reason
   REASON`. Invalid JSON needs `--replacement corrected.json`. Externally stored
   evidence must first be retrieved for inspection. Uncertain external outcomes
   require `--reconciliation-evidence`. Each record can be replayed once; actor,
   reason, replacement hash and evidence are retained with the original bytes.
6. Roll back code without dropping control state or shrinking descriptions.
   Pause affected consumers before rollback; reconcile in-flight claims and keep
   the reliable relay running until pending events have a supported publisher.

Worker metrics are emitted every 30 seconds with bounded-cardinality outcomes.
Active or preserved unresolved deliveries with no completion for five minutes
emit `worker_no_progress`, including infrastructure pauses with no active task.
Full worker slots wake periodically so long handlers cannot suppress the alert.
These are delivery progress counters, not counts of unique
jobs or matching opportunities. Monitor pending outbox age, oldest queue message,
pool pressure, useful catalog commits and downstream completions separately.

## Validation

`tests/test_durable_processing.py` runs actual transactions on SQLite or an
isolated localhost MySQL `*_test` schema. `tests/test_durable_transport.py` adds
real RabbitMQ confirmations, malformed bytes and connection restart scenarios.
Use only dedicated localhost URLs in `TEST_WORKER_DATABASE_URL` and
`TEST_WORKER_RABBITMQ_URL`. `scripts/benchmark_worker_delivery.py` measures local
commits with a pending outbox and mixed payload sizes; it does not measure full
pipeline throughput or establish a production SLO.
