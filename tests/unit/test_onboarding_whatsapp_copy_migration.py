from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa


def test_copy_migration_preserves_workflow_rules_and_other_flows(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "migrations/core/versions/0037_onboarding_whatsapp_copy.py"
    spec = importlib.util.spec_from_file_location("migration_0037", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    tables = {}
    for name in ("candidate_workflow_steps", "resume_build_steps", "billing_workflow_steps"):
        tables[name] = sa.Table(
            name, metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("step_key", sa.String),
            sa.Column("workflow_key", sa.String),
            sa.Column("options", sa.JSON),
            sa.Column("active", sa.Boolean),
            sa.Column("step_order", sa.Integer),
        )
    flows = sa.Table(
        "onboard_flows", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("flow_key", sa.String),
        sa.Column("active", sa.Boolean),
    )
    onboard = sa.Table(
        "onboard_flow_steps", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("flow_id", sa.Integer),
        sa.Column("step_key", sa.String),
        sa.Column("config", sa.JSON),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    definitions = [{
        "workflow_key": "test", "step_key": "question",
        "options": {"question": "*Nova pergunta*", "action": "do_not_copy"},
    }]
    monkeypatch.setattr(migration, "_seed_data", lambda: (
        definitions, definitions, definitions, "candidate_onboarding",
        [("intro", None, {"presentation": {"text_template": "*Nova apresentação*"}})],
    ))
    original_options = {
        "question": "old", "action": "keep", "question_options": ["Sim", "Não"],
        "agent_prompt": "keep prompt", "step_condition": {"when_step": "previous"},
    }
    original_config = {
        "presentation": {"text_template": "old", "template_html": "keep HTML"},
        "bindings": {"name": {"step": "profile"}}, "generation": {"prompt": "keep"},
    }
    with engine.begin() as bind:
        for table in tables.values():
            bind.execute(table.insert(), [
                {"id": 1, "step_key": "question", "workflow_key": "test",
                 "options": original_options, "active": False, "step_order": 70},
                {"id": 2, "step_key": "other", "workflow_key": "unrelated",
                 "options": original_options, "active": True, "step_order": 20},
            ])
        bind.execute(flows.insert(), [
            {"id": 1, "flow_key": "candidate_onboarding", "active": True},
            {"id": 2, "flow_key": "other", "active": True},
        ])
        bind.execute(onboard.insert(), [
            {"id": 1, "flow_id": 1, "step_key": "intro", "config": original_config},
            {"id": 2, "flow_id": 2, "step_key": "intro", "config": original_config},
        ])
        monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
        migration.upgrade()
        migration.upgrade()
        for table in tables.values():
            rows = bind.execute(sa.select(table).order_by(table.c.id)).mappings().all()
            assert len(rows) == 2
            assert rows[0]["active"] is False
            assert rows[0]["step_order"] == 70
            assert rows[0]["options"] == {**original_options, "question": "*Nova pergunta*"}
            assert rows[1]["options"] == original_options
        configs = bind.execute(sa.select(onboard.c.config).order_by(onboard.c.id)).scalars().all()
        assert configs[0] == {
            **original_config,
            "presentation": {"text_template": "*Nova apresentação*", "template_html": "keep HTML"},
        }
        assert configs[1] == original_config
