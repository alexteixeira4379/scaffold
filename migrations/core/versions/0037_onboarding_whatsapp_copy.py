"""Apply WhatsApp onboarding copy without changing workflow behavior or history.

Only presentation fields are merged into existing rows. Step order, activity,
validation, actions, options, AI prompts and candidate answers are preserved.
The preceding 0035 revision establishes the billing/onboarding catalogs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def _seed_data():
    scripts = str(Path(__file__).resolve().parents[3] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import seed_all
    import seederBillingWorkflowSteps as billing
    import seederCandidateWorkflowSteps as candidate
    import seederResumeBuildSteps as resume

    return candidate.STEPS, resume.STEPS, billing.STEPS, seed_all.FLOW_KEY, seed_all.onboard_steps()


def _update_questions(bind, table_name, definitions, *, workflow_scoped=False):
    columns = [
        sa.column("id", sa.BigInteger),
        sa.column("step_key", sa.String),
        sa.column("options", sa.JSON),
    ]
    if workflow_scoped:
        columns.append(sa.column("workflow_key", sa.String))
    table = sa.table(table_name, *columns)
    for definition in definitions:
        question = (definition.get("options") or {}).get("question")
        if not question:
            continue
        query = sa.select(table).where(table.c.step_key == definition["step_key"])
        if workflow_scoped:
            query = query.where(table.c.workflow_key == definition["workflow_key"])
        for row in bind.execute(query).mappings().all():
            options = {**(row["options"] or {}), "question": question}
            bind.execute(table.update().where(table.c.id == row["id"]).values(options=options))


def _update_onboarding(bind, flow_key, definitions):
    flows = sa.table(
        "onboard_flows",
        sa.column("id", sa.BigInteger),
        sa.column("flow_key", sa.String),
        sa.column("active", sa.Boolean),
    )
    steps = sa.table(
        "onboard_flow_steps",
        sa.column("id", sa.BigInteger),
        sa.column("flow_id", sa.BigInteger),
        sa.column("step_key", sa.String),
        sa.column("config", sa.JSON),
    )
    flow_ids = sa.select(flows.c.id).where(
        flows.c.flow_key == flow_key, flows.c.active.is_(True)
    )
    for key, _kind, definition in definitions:
        # Only these copy fields changed; do not overwrite concurrently changed
        # bindings, HTML cards, prompts or domain routing configurations.
        copy = {k: definition[k] for k in ("text", "fallback_text") if k in definition}
        template = (definition.get("presentation") or {}).get("text_template")
        if not copy and template is None:
            continue
        rows = bind.execute(
            sa.select(steps).where(steps.c.flow_id.in_(flow_ids), steps.c.step_key == key)
        ).mappings().all()
        for row in rows:
            config = {**(row["config"] or {}), **copy}
            if template is not None:
                config["presentation"] = {
                    **(config.get("presentation") or {}), "text_template": template
                }
            bind.execute(steps.update().where(steps.c.id == row["id"]).values(config=config))


def upgrade():
    candidate, resume, billing, flow_key, onboard = _seed_data()
    bind = op.get_bind()
    _update_questions(bind, "candidate_workflow_steps", candidate, workflow_scoped=True)
    _update_questions(bind, "resume_build_steps", resume)
    _update_questions(bind, "billing_workflow_steps", billing, workflow_scoped=True)
    _update_onboarding(bind, flow_key, onboard)


def downgrade():
    # Copy only: leave the current messages in place, preserving live state.
    pass
