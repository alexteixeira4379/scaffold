from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa


def _load_migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/core/versions/0035_billing_offer_and_onboarding_reseed.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0035", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema(metadata: sa.MetaData):
    billing = sa.Table(
        "billing_workflow_steps",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workflow_key", sa.String(64), nullable=False),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("input_type", sa.String(32), nullable=False),
        sa.Column("options", sa.JSON, nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
    )
    flows = sa.Table(
        "onboard_flows",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("flow_key", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
    )
    onboard = sa.Table(
        "onboard_flow_steps",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("flow_id", sa.Integer, nullable=False),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("required", sa.Boolean, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
    )
    return billing, flows, onboard


def test_upgrade_reseeds_in_place_and_is_idempotent(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    billing, flows, onboard = _schema(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            billing.insert(),
            [
                {
                    "id": 1,
                    "workflow_key": "subscription",
                    "step_key": "select_plan",
                    "step_order": 10,
                    "input_type": "select",
                    "options": {},
                    "is_required": True,
                    "active": True,
                },
                {
                    "id": 2,
                    "workflow_key": "subscription",
                    "step_key": "confirm_checkout",
                    "step_order": 20,
                    "input_type": "boolean",
                    "options": {},
                    "is_required": True,
                    "active": True,
                },
            ],
        )
        connection.execute(
            flows.insert().values(
                id=7,
                flow_key="candidate_onboarding",
                subject_type="candidate",
                version=1,
                active=True,
            )
        )
        connection.execute(
            onboard.insert(),
            [
                {
                    "id": 11,
                    "flow_id": 7,
                    "step_key": "activation_intro",
                    "step_order": 10,
                    "kind": "info",
                    "required": True,
                    "active": True,
                    "config": {"text": "old"},
                },
                {
                    "id": 12,
                    "flow_id": 7,
                    "step_key": "resume_intro",
                    "step_order": 20,
                    "kind": "action",
                    "required": True,
                    "active": True,
                    "config": {"presentation": {"text_template": "old"}},
                },
            ],
        )

        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        migration.upgrade()
        migration.upgrade()

        billing_rows = {
            row.step_key: row
            for row in connection.execute(sa.select(billing)).mappings()
        }
        assert billing_rows["accept_offer"].step_order == 10
        assert billing_rows["accept_offer"].active is True
        assert billing_rows["await_payment"].step_order == 20
        assert billing_rows["await_payment"].active is True
        assert billing_rows["select_plan"].id == 1
        assert billing_rows["select_plan"].active is False
        assert billing_rows["confirm_checkout"].id == 2
        assert billing_rows["confirm_checkout"].active is False
        assert len(billing_rows) == 4

        onboard_rows = {
            row.step_key: row
            for row in connection.execute(
                sa.select(onboard).where(onboard.c.flow_id == 7)
            ).mappings()
        }
        assert onboard_rows["activation_intro"].id == 11
        assert "preparar sua ativação" in onboard_rows["activation_intro"].config["text"]
        assert onboard_rows["resume_intro"].id == 12
        assert "completar seu currículo" in onboard_rows["resume_intro"].config[
            "presentation"
        ]["text_template"]
        assert len(onboard_rows) == 10
