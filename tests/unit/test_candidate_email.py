"""Durable inbox constraints and migration compatibility, without network access."""

import importlib.util
import io
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from scaffold.email.contracts import EmailForwardRequested, EmailInboundRequested
from scaffold.messaging.definitions import get_full_topology
from scaffold.messaging.definitions.domain import SUBSCRIPTIONS
from scaffold.models.email import (
    ApplicationEmailChallenge,
    CandidateMailbox,
    EmailAttachment,
    EmailDelivery,
    EmailMessage,
    EmailMessageRecipient,
    EmailRecoveryCursor,
    EmailWebhookEvent,
)

MODELS = (
    CandidateMailbox,
    EmailWebhookEvent,
    EmailMessage,
    EmailMessageRecipient,
    EmailAttachment,
    EmailDelivery,
    ApplicationEmailChallenge,
    EmailRecoveryCursor,
)
MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "migrations/core/versions/0053_candidate_email.py"
)


def migration():
    spec = importlib.util.spec_from_file_location("candidate_email_0053", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrated_connection():
    engine = create_engine("sqlite://")
    conn = engine.connect()
    conn.execute(text("PRAGMA foreign_keys=ON"))
    for parent in (
        "candidates",
        "auth_verified_identities",
        "job_applications",
        "application_runs",
    ):
        conn.execute(text(f"CREATE TABLE {parent} (id INTEGER PRIMARY KEY)"))
    with Operations.context(MigrationContext.configure(conn)):
        migration().upgrade()
    return conn


def test_migration_sqlite_and_mysql_ddl():
    conn = migrated_connection()
    try:
        schema = inspect(conn)
        for model in MODELS:
            name = model.__table__.name
            assert {c["name"] for c in schema.get_columns(name)} == set(
                model.__table__.columns.keys()
            )
            for dialect in (sqlite.dialect(), mysql.dialect()):
                ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
                assert name in ddl
        assert {"application_email", "mailbox_id"} <= {
            c["name"] for c in schema.get_columns("job_applications")
        }
    finally:
        conn.close()
    output = io.StringIO()
    with Operations.context(
        MigrationContext.configure(
            dialect_name="mysql", opts={"as_sql": True, "output_buffer": output}
        )
    ):
        migration().upgrade()
    assert "ALTER TABLE job_applications ADD COLUMN application_email" in output.getvalue()
    assert "CREATE TABLE application_email_challenges" in output.getvalue()


def test_webhook_deduplication_is_scoped_to_provider_account():
    conn = migrated_connection()
    try:
        stmt = text(
            "INSERT INTO email_webhook_events (resend_account_id,event_id,event_type,payload,received_at) VALUES (:account,'evt1','email.received','{}',CURRENT_TIMESTAMP)"
        )
        conn.execute(stmt, {"account": "one"})
        with pytest.raises(IntegrityError):
            conn.execute(stmt, {"account": "one"})
        conn.execute(stmt, {"account": "two"})
        assert conn.scalar(text("SELECT count(*) FROM email_webhook_events")) == 2
    finally:
        conn.close()


def test_tombstone_preserves_address_after_candidate_deletion():
    conn = migrated_connection()
    try:
        conn.execute(text("INSERT INTO candidates VALUES (1)"))
        conn.execute(
            text(
                "INSERT INTO candidate_mailboxes (candidate_id,environment,address,resend_account_id) VALUES (1,'test','c-one@test.resend.app','one')"
            )
        )
        conn.execute(text("DELETE FROM candidates WHERE id=1"))
        assert conn.scalar(text("SELECT candidate_id FROM candidate_mailboxes")) is None
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO candidate_mailboxes (environment,address,resend_account_id) VALUES ('test','c-one@test.resend.app','one')"
                )
            )
    finally:
        conn.close()


def test_message_deduplication_and_recipient_isolation():
    conn = migrated_connection()
    try:
        for cid in (1, 2):
            conn.execute(text("INSERT INTO candidates VALUES (:id)"), {"id": cid})
            conn.execute(
                text(
                    "INSERT INTO candidate_mailboxes (id,candidate_id,environment,address,resend_account_id) VALUES (:id,:id,'test',:addr,'one')"
                ),
                {"id": cid, "addr": f"c-{cid}@test.resend.app"},
            )
        insert = text(
            "INSERT INTO email_messages (resend_account_id,provider_email_id,sender,subject,received_at,authentication,headers) VALUES ('one','mail1','sender@example.org','Hi',CURRENT_TIMESTAMP,'{}','{}')"
        )
        conn.execute(insert)
        with pytest.raises(IntegrityError):
            conn.execute(insert)
        for cid in (1, 2):
            conn.execute(
                text(
                    "INSERT INTO email_message_recipients (message_id,mailbox_id,candidate_id,recipient_address) VALUES (1,:id,:id,:addr)"
                ),
                {"id": cid, "addr": f"c-{cid}@test.resend.app"},
            )
        conn.execute(
            text(
                "UPDATE email_message_recipients SET read_at=CURRENT_TIMESTAMP WHERE candidate_id=1"
            )
        )
        assert (
            conn.scalar(text("SELECT read_at FROM email_message_recipients WHERE candidate_id=2"))
            is None
        )
        conn.execute(text("DELETE FROM email_message_recipients WHERE candidate_id=1"))
        assert conn.scalar(text("SELECT count(*) FROM email_messages")) == 1
        assert (
            conn.scalar(text("SELECT count(*) FROM email_message_recipients WHERE candidate_id=2"))
            == 1
        )
    finally:
        conn.close()


def test_email_topology_is_durable_and_does_not_notify_whatsapp():
    topology = get_full_topology()
    queues = {q.name: q for q in topology.queues}
    for lane in ("email.inbound", "email.forwarding", "email.lifecycle"):
        assert queues[lane].durable
        assert queues[lane].arguments["x-dead-letter-routing-key"] == lane + ".dlq"
        assert queues[lane + ".retry"].arguments["x-dead-letter-routing-key"] == lane
        assert queues[lane + ".dlq"].durable
    assert SUBSCRIPTIONS["email.lifecycle"] == ("auth.contact.verified",)
    assert all(not event.startswith("email.") for event in SUBSCRIPTIONS["notification.lifecycle"])
    assert len(queues) == len(topology.queues)


def test_task_contracts_reject_code_or_body_payloads():
    EmailInboundRequested(event_id="evt", data={"webhook_event_id": 1})
    EmailForwardRequested(event_id="evt", candidate_id=1, data={"delivery_id": 1})
    with pytest.raises(ValidationError):
        EmailInboundRequested(event_id="evt", data={"webhook_event_id": 1, "code": "123456"})
    with pytest.raises(ValidationError):
        EmailForwardRequested(event_id="evt", candidate_id=1, data={"delivery_id": 0})


@pytest.mark.asyncio
async def test_webhook_and_outbox_roll_back_together_and_dedupe():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from scaffold.messaging.domain import enqueue
    from scaffold.models.domain_delivery import DomainOutbox

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(EmailWebhookEvent.__table__.create)
        await connection.run_sync(DomainOutbox.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            async with session.begin():
                session.add(
                    EmailWebhookEvent(
                        resend_account_id="one",
                        event_id="evt1",
                        event_type="email.received",
                        payload={},
                    )
                )
                first = await enqueue(
                    session, "email-api", "email.inbound", {"event_id": "evt1"}, key="one:evt1"
                )
                duplicate = await enqueue(
                    session, "email-api", "email.inbound", {"event_id": "evt1"}, key="one:evt1"
                )
                assert first.id == duplicate.id
        async with factory() as session:
            with pytest.raises(RuntimeError):
                async with session.begin():
                    session.add(
                        EmailWebhookEvent(
                            resend_account_id="one",
                            event_id="evt2",
                            event_type="email.received",
                            payload={},
                        )
                    )
                    await enqueue(
                        session, "email-api", "email.inbound", {"event_id": "evt2"}, key="one:evt2"
                    )
                    raise RuntimeError("database operation failed")
        async with factory() as session:
            assert await session.scalar(text("SELECT count(*) FROM email_webhook_events")) == 1
            assert await session.scalar(text("SELECT count(*) FROM domain_outbox")) == 1
    finally:
        await engine.dispose()


def test_mysql_identifier_names_stay_within_64_characters():
    import re
    for model in MODELS:
        ddl = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        for name in re.findall(r"CONSTRAINT\s+`?([a-zA-Z0-9_]+)`?", ddl):
            assert len(name) <= 64, name
        for index in model.__table__.indexes:
            assert len(index.name) <= 64
    output = io.StringIO()
    with Operations.context(MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": output})):
        migration().upgrade()
    for name in re.findall(r"(?:CONSTRAINT|INDEX)\s+`?([a-zA-Z0-9_]+)`?", output.getvalue()):
        assert len(name) <= 64, name


def test_private_object_migration_preserves_cleanup_references_after_deletion():
    from scaffold.models.email import EmailPrivateObject
    path = MIGRATION_PATH.with_name("0054_email_private_objects.py")
    spec = importlib.util.spec_from_file_location("candidate_email_0054", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    conn = migrated_connection()
    try:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        columns = inspect(conn).get_columns("email_private_objects")
        assert {c["name"] for c in columns} == set(EmailPrivateObject.__table__.columns.keys())
        conn.execute(text("INSERT INTO candidates VALUES (1)"))
        conn.execute(text("INSERT INTO email_messages (id,resend_account_id,provider_email_id,sender,subject,received_at,authentication,headers) VALUES (1,'one','mail1','sender@example.org','Hi',CURRENT_TIMESTAMP,'{}','{}')"))
        conn.execute(text("INSERT INTO email_private_objects (key,bucket,message_id,candidate_id,scope) VALUES ('forwarding/1/payload.json','private',1,1,'candidate')"))
        conn.execute(text("DELETE FROM candidates WHERE id=1"))
        conn.execute(text("DELETE FROM email_messages WHERE id=1"))
        orphan = conn.execute(text("SELECT key,candidate_id,message_id,status FROM email_private_objects")).one()
        assert orphan == ("forwarding/1/payload.json", None, None, "uploading")
    finally:
        conn.close()
    output = io.StringIO()
    with Operations.context(MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": output})):
        module.upgrade()
    import re
    for ddl in (output.getvalue(), str(CreateTable(EmailPrivateObject.__table__).compile(dialect=mysql.dialect()))):
        assert "SET NULL" in ddl
        for name in re.findall(r"(?:CONSTRAINT|INDEX)\s+`?([a-zA-Z0-9_]+)`?", ddl):
            assert len(name) <= 64, name
