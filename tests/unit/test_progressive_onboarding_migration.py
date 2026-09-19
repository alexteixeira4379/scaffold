import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def load_migration():
    path = Path(__file__).resolve().parents[2] / "migrations/core/versions/0038_progressive_onboarding.py"
    spec = importlib.util.spec_from_file_location("migration_0038", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema():
    m = sa.MetaData()
    for name in ("candidate_workflow_steps", "billing_workflow_steps", "resume_build_steps"):
        columns = [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("step_key", sa.String), sa.Column("step_order", sa.Integer),
            sa.Column("input_type", sa.String), sa.Column("is_required", sa.Boolean),
            sa.Column("active", sa.Boolean), sa.Column("options", sa.JSON),
        ]
        if name == "resume_build_steps":
            columns += [sa.Column("step_label", sa.String), sa.Column("description", sa.String)]
        else:
            columns += [sa.Column("workflow_key", sa.String)]
        sa.Table(name, m, *columns)
    sa.Table("onboard_flows", m, sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("flow_key", sa.String), sa.Column("subject_type", sa.String),
             sa.Column("version", sa.Integer), sa.Column("active", sa.Boolean))
    sa.Table("onboard_flow_steps", m, sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("flow_id", sa.Integer), sa.Column("step_key", sa.String),
             sa.Column("step_order", sa.Integer), sa.Column("kind", sa.String),
             sa.Column("required", sa.Boolean), sa.Column("active", sa.Boolean),
             sa.Column("config", sa.JSON))
    sa.Table("profile_onboard_flows", m, sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("flow_id", sa.Integer), sa.Column("status", sa.String),
             sa.Column("current_step_key", sa.String))
    sa.Table("profile_onboard_step_states", m, sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("profile_flow_id", sa.Integer), sa.Column("step_key", sa.String),
             sa.Column("status", sa.String), sa.Column("api_session_id", sa.Integer),
             sa.Column("local_answer", sa.JSON))
    sa.Table("billing_workflow_sessions", m, sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("current_step_key", sa.String))
    return m


@pytest.mark.parametrize("pending_checkout", [False, True])
def test_migration_preserves_history_and_guards_outstanding_checkouts(monkeypatch, pending_checkout):
    migration = load_migration()
    m = schema()
    engine = sa.create_engine("sqlite://")
    m.create_all(engine)
    with engine.begin() as conn:
        t = m.tables
        conn.execute(t["onboard_flows"].insert().values(id=1, flow_key="candidate_onboarding", version=1, active=True))
        conn.execute(t["profile_onboard_flows"].insert(), [
            {"id": 10, "flow_id": 1, "status": "in_progress", "current_step_key": "subscription"},
            {"id": 11, "flow_id": 1, "status": "completed", "current_step_key": None},
        ])
        conn.execute(t["profile_onboard_step_states"].insert(), [
            {"id": 20, "profile_flow_id": 10, "step_key": "resume_builder", "status": "pending", "api_session_id": None, "local_answer": None},
            {"id": 21, "profile_flow_id": 10, "step_key": "subscription", "status": "in_progress", "api_session_id": 30, "local_answer": {"accepted": False}},
        ])
        conn.execute(t["billing_workflow_sessions"].insert().values(
            id=30, current_step_key="await_payment" if pending_checkout else "accept_offer"))
        monkeypatch.setattr(migration.op, "get_bind", lambda: conn)
        if pending_checkout:
            with pytest.raises(RuntimeError, match="outstanding legacy"):
                migration.upgrade()
            assert conn.scalar(sa.select(sa.func.count()).select_from(t["resume_build_steps"])) == 0
            return
        migration.upgrade()
        migration.upgrade()
        flows = {r.id: r for r in conn.execute(sa.select(t["profile_onboard_flows"]))}
        assert flows[10].current_step_key == "resume_builder"
        assert flows[11].status == "completed"
        states = {r.id: r for r in conn.execute(sa.select(t["profile_onboard_step_states"]))}
        assert states[21].api_session_id == 30
        assert states[21].local_answer == {"accepted": False}
        resume = {r.step_key: r for r in conn.execute(sa.select(t["resume_build_steps"]))}
        assert resume["review_resume"].active
        assert resume["extra_section_intro"].options["answer_format"] == "optional_profile"
        assert resume["extra_certifications"].options["collection_mode"] == "import_only"
        onboard = {r.step_key: r for r in conn.execute(sa.select(t["onboard_flow_steps"]))}
        assert onboard["resume_builder"].step_order < onboard["subscription"].step_order
