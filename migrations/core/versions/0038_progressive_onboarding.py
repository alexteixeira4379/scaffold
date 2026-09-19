"""Progressive WhatsApp preparation, before checkout; preserve IDs and answers.

Deploy the compatible API/worker code before applying this catalog revision.
An already issued old-flow checkout must finish before migration: do not
silently move its candidate away from an outstanding payment.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def _definitions():
    scripts = str(Path(__file__).resolve().parents[3] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import seederCandidateWorkflowSteps as candidate
    import seederResumeBuildSteps as resume
    import seederBillingWorkflowSteps as billing
    from scaffold.workflow.onboarding_catalog import onboard_steps
    return candidate.STEPS, resume.STEPS, billing.STEPS, onboard_steps()


def _upsert(bind, name, definitions, scoped=False):
    table = sa.Table(name, sa.MetaData(), autoload_with=bind)
    for definition in definitions:
        values = {**definition, "active": True}
        values["input_type"] = values["input_type"].value
        query = sa.select(table.c.id).where(table.c.step_key == values["step_key"])
        if scoped:
            query = query.where(table.c.workflow_key == values["workflow_key"])
        row_id = bind.execute(query).scalar()
        if row_id is None:
            bind.execute(table.insert().values(**values))
        else:
            bind.execute(table.update().where(table.c.id == row_id).values(**values))


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    flows = sa.Table("profile_onboard_flows", metadata, autoload_with=bind)
    states = sa.Table("profile_onboard_step_states", metadata, autoload_with=bind)
    billing_sessions = sa.Table("billing_workflow_sessions", metadata, autoload_with=bind)
    template = sa.Table("onboard_flows", metadata, autoload_with=bind)
    active_ids = sa.select(template.c.id).where(
        template.c.flow_key == "candidate_onboarding", template.c.active.is_(True))
    unfinished = list(bind.execute(sa.select(flows).where(
        flows.c.flow_id.in_(active_ids), flows.c.status == "in_progress")).mappings())
    redirects = []
    for flow in unfinished:
        step_states = {row["step_key"]: row for row in bind.execute(
            sa.select(states).where(states.c.profile_flow_id == flow["id"])).mappings()}
        builder = step_states.get("resume_builder")
        payment = step_states.get("subscription")
        if not builder or builder["status"] == "completed" or (payment and payment["status"] == "completed"):
            continue
        if flow["current_step_key"] not in {"base_profile", "suspense_2", "activation_intro", "subscription"}:
            continue
        if payment and payment["api_session_id"]:
            pending = bind.execute(sa.select(billing_sessions.c.current_step_key).where(
                billing_sessions.c.id == payment["api_session_id"])).scalar()
            if pending == "await_payment":
                raise RuntimeError(
                    f"Finish outstanding legacy onboarding checkout for profile_flow={flow['id']} before 0038")
        redirects.append((flow["id"], builder["id"]))

    candidate, resume, billing, onboard = _definitions()
    _upsert(bind, "candidate_workflow_steps", candidate, scoped=True)
    _upsert(bind, "resume_build_steps", resume)
    _upsert(bind, "billing_workflow_steps", billing, scoped=True)
    path = Path(__file__).with_name("0035_billing_offer_and_onboarding_reseed.py")
    # Reuse the preceding data migration's idempotent natural-key upsert.
    spec = importlib.util.spec_from_file_location("onboarding_reseed_0035", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._reseed_onboarding(bind, "candidate_onboarding", onboard, {"suspense_1", "job_match"})
    for flow_id, builder_id in redirects:
        bind.execute(flows.update().where(flows.c.id == flow_id).values(current_step_key="resume_builder"))
        bind.execute(states.update().where(states.c.id == builder_id).values(status="in_progress"))


def downgrade():
    # Never erase prepared profiles or rewrite candidate history.
    pass
