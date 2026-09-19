"""Seeder único: popula TODAS as tabelas de configuração de workflow do sistema.

Substitui a necessidade de rodar múltiplos scripts separados (um por domínio)
e substitui o esquema de versão imutável do onboard_flow_steps (que vinha
gerando v1, v7, v8, v9... a cada ajuste, mesmo sem nada estabilizado ainda).

Padrão único para todos os domínios: upsert idempotente por chave natural.
Editou o dict de STEPS? Roda de novo. Não cria linha nova, atualiza a existente.

Domínios cobertos:
  - candidate_workflow_steps  (candidate-api)   -> STEPS em seederCandidateWorkflowSteps.py
  - billing_workflow_steps    (billing-api)     -> STEPS em seederBillingWorkflowSteps.py
  - resume_build_steps        (resume-api)      -> STEPS em seederResumeBuildSteps.py
  - onboard_flows / onboard_flow_steps (conversation-worker, orquestrador)
    -> definido abaixo, único lugar agora (antes vivia espalhado em
       scripts/seed_onboard_flow.py, seed_acquisition_flow.py e
       backfill_onboard_flows.py dentro do repo conversation-worker).

Usage:
    python scripts/seed_all.py
    python scripts/seed_all.py --only onboard
    python scripts/seed_all.py --only candidate,billing
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from pathlib import Path

from sqlalchemy import delete, select

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_SCRIPTS = Path(__file__).resolve().parent
_TEMPLATES = _SCRIPTS / "onboard_templates"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

importlib.import_module("scaffold.models")

from scaffold.constants.schema_enums import OrchestratorStepKind as Kind  # noqa: E402
from scaffold.db.session import close_engine, get_session_factory  # noqa: E402
from scaffold.models.onboard.onboard_flow_steps import OnboardFlowStep  # noqa: E402
from scaffold.models.onboard.onboard_flows import OnboardFlow  # noqa: E402
from scaffold.models.onboard.profile_onboard_flows import ProfileOnboardFlow  # noqa: E402

import seederCandidateWorkflowSteps as candidate_seeder  # noqa: E402
import seederBillingWorkflowSteps as billing_seeder  # noqa: E402
import seederResumeBuildSteps as resume_seeder  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARD FLOW (orquestrador do conversation-worker)
#
# Única versão viva: FLOW_VERSION nunca sobe. Ajustou um step? Edita o dict
# abaixo e roda o seeder de novo — ele faz update in-place por step_key.
# Quando o fluxo estabilizar de verdade (não antes), podemos voltar a versionar.
# ═══════════════════════════════════════════════════════════════════════════════

FLOW_KEY = "candidate_onboarding"


from scaffold.workflow.onboarding_catalog import onboard_steps, activation_card as _activation_card, compose_greeting as _compose_greeting

__all__ = ["onboard_steps", "_activation_card", "_compose_greeting"]

REMOVED_ONBOARD_STEP_KEYS = frozenset({"suspense_1", "job_match"})


async def get_or_create_flow(session) -> OnboardFlow:
    """Attach to whichever version is currently active in the DB — never pin a
    fixed version number here. Pinning one (e.g. always version=1) would make
    this seeder reactivate a stale historical version and deactivate whatever
    is actually live in production, which is the exact regression this
    unification must not cause. Fresh/empty DB: create version=1, active."""
    flow = await session.scalar(
        select(OnboardFlow).where(OnboardFlow.flow_key == FLOW_KEY, OnboardFlow.active.is_(True))
    )
    if flow is not None:
        return flow
    flow = await session.scalar(
        select(OnboardFlow).where(OnboardFlow.flow_key == FLOW_KEY, OnboardFlow.version == 1)
    )
    if flow is None:
        flow = OnboardFlow(flow_key=FLOW_KEY, subject_type="candidate", version=1, active=True)
        session.add(flow)
        await session.flush()
    else:
        flow.active = True
    return flow


async def get_or_create_onboard_step(session, flow_id: int, order: int, step_key: str, kind: Kind, config: dict) -> None:
    row = await session.scalar(
        select(OnboardFlowStep).where(OnboardFlowStep.flow_id == flow_id, OnboardFlowStep.step_key == step_key)
    )
    if row is None:
        session.add(OnboardFlowStep(
            flow_id=flow_id, step_key=step_key, step_order=order, kind=kind,
            required=True, active=True, config=config,
        ))
        return
    row.step_order = order
    row.kind = kind
    row.config = config
    row.required = True
    row.active = True


async def purge_stale_flows(session, keep_flow_id: int) -> list[int]:
    """Delete every other onboard_flows row for FLOW_KEY, so this seeder's
    config is always the only one that exists — no more historical versions
    piling up (v1, v3, v4... v8) while nothing has ever launched. A flow with
    candidates already materialized against it (profile_onboard_flows.flow_id
    FK) is left alone and reported, never force-deleted — real user history
    always wins over a clean slate."""
    stale = (
        await session.scalars(
            select(OnboardFlow).where(OnboardFlow.flow_key == FLOW_KEY, OnboardFlow.id != keep_flow_id)
        )
    ).all()
    skipped = []
    for flow in stale:
        in_use = await session.scalar(
            select(ProfileOnboardFlow.id).where(ProfileOnboardFlow.flow_id == flow.id).limit(1)
        )
        if in_use is not None:
            skipped.append(flow.version)
            continue
        await session.execute(delete(OnboardFlowStep).where(OnboardFlowStep.flow_id == flow.id))
        await session.delete(flow)
    return skipped


async def run_onboard_seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        flow = await get_or_create_flow(session)
        for order, (key, kind, config) in enumerate(onboard_steps(), 1):
            await get_or_create_onboard_step(session, flow.id, order * 10, key, kind, config)
        for removed_key in REMOVED_ONBOARD_STEP_KEYS:
            row = await session.scalar(
                select(OnboardFlowStep).where(
                    OnboardFlowStep.flow_id == flow.id, OnboardFlowStep.step_key == removed_key
                )
            )
            if row is not None:
                row.active = False
        skipped = await purge_stale_flows(session, flow.id)
        await session.commit()
        version = flow.version
    print(f"✅ Seeded onboard_flows/{FLOW_KEY} v{version} (active) ({len(onboard_steps())} steps)")
    if skipped:
        print(f"⚠️  kept stale versions {skipped} — candidates already exist on them")


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTRAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

SEEDERS = {
    "candidate": lambda reset: candidate_seeder.run_seed(reset=reset),
    "billing": lambda reset: billing_seeder.run_seed(reset=reset),
    "resume": lambda reset: resume_seeder.run_seed(reset=reset),
    "onboard": lambda _reset: run_onboard_seed(),
}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed único de todas as tabelas de workflow")
    parser.add_argument("--only", help="Lista separada por vírgula: candidate,billing,resume,onboard")
    parser.add_argument("--no-reset", action="store_true", dest="no_reset")
    args = parser.parse_args()

    targets = args.only.split(",") if args.only else list(SEEDERS.keys())
    try:
        for name in targets:
            name = name.strip()
            if name not in SEEDERS:
                raise SystemExit(f"seeder desconhecido: {name} (opções: {list(SEEDERS.keys())})")
            print(f"\n── {name} " + "─" * (60 - len(name)))
            await SEEDERS[name](not args.no_reset)
    finally:
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
