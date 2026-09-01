"""Seeder: Popula billing_plans com os planos oferecidos no step choose_plan.

O código (`code`) de cada plano é o slug que o candidato escolhe na conversa
(platinum/diamond/black — ver seederResumeBuildSteps.py, step "choose_plan").
O `stripe_price_id` é o Price ID real do Stripe, lido de variáveis de
ambiente — não é hardcoded porque depende da conta Stripe configurada.

Usage:
    STRIPE_PRICE_PLATINUM=price_xxx STRIPE_PRICE_DIAMOND=price_yyy STRIPE_PRICE_BLACK=price_zzz \
        python scripts/seederBillingPlans.py

Sem as envs, os planos são seedados com stripe_price_id=None — o checkout
falha de forma controlada (PlanMisconfiguredError → 502) até serem
configurados.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path

from sqlalchemy import select

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

importlib.import_module("scaffold.models")

from scaffold.db.session import close_engine, get_session_factory  # noqa: E402
from scaffold.models.billing.billing_plans import BillingPlan  # noqa: E402

PLANS: list[dict] = [
    {
        "code": "platinum",
        "name": "Jobito Platinum",
        "description": (
            "Análise de perfil e busca compatível, alertas e curadoria de vagas "
            "no WhatsApp, aviso de vagas recentes."
        ),
        "price": 19.90,
        "stripe_price_id_env": "STRIPE_PRICE_PLATINUM",
    },
    {
        "code": "diamond",
        "name": "Jobito Diamond",
        "description": (
            "Tudo do Platinum + envio automático de currículo, aplicação automática "
            "no LinkedIn, carta de apresentação personalizada, relatório semanal."
        ),
        "price": 49.90,
        "stripe_price_id_env": "STRIPE_PRICE_DIAMOND",
    },
    {
        "code": "black",
        "name": "Jobito Black",
        "description": "Tudo do Diamond + currículo reformulado para cada vaga.",
        "price": 79.90,
        "stripe_price_id_env": "STRIPE_PRICE_BLACK",
    },
]


async def get_or_create_plan(session, plan_data: dict) -> BillingPlan:
    stripe_price_id = os.getenv(plan_data["stripe_price_id_env"], "").strip() or None

    row = (
        await session.execute(
            select(BillingPlan).where(BillingPlan.code == plan_data["code"]).limit(1)
        )
    ).scalars().first()

    if row is not None:
        row.name = plan_data["name"]
        row.description = plan_data["description"]
        row.price = plan_data["price"]
        row.currency = "BRL"
        row.interval = "month"
        row.interval_count = 1
        row.active = True
        if stripe_price_id:
            row.stripe_price_id = stripe_price_id
        return row

    plan = BillingPlan(
        code=plan_data["code"],
        stripe_price_id=stripe_price_id,
        name=plan_data["name"],
        description=plan_data["description"],
        price=plan_data["price"],
        currency="BRL",
        interval="month",
        interval_count=1,
        features={},
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def run_seed() -> None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            missing_price_ids = []
            for plan_data in PLANS:
                plan = await get_or_create_plan(session, plan_data)
                if not plan.stripe_price_id:
                    missing_price_ids.append(plan_data["code"])

            await session.commit()

        print(f"✅ Seeded {len(PLANS)} billing_plans (platinum/diamond/black)")
        if missing_price_ids:
            print(
                "⚠️  Sem stripe_price_id configurado para: "
                f"{', '.join(missing_price_ids)} — checkout desses planos vai "
                "falhar com PlanMisconfiguredError até você definir as envs "
                "STRIPE_PRICE_PLATINUM/DIAMOND/BLACK e rodar o seed de novo."
            )
    finally:
        await close_engine()


def main() -> None:
    asyncio.run(run_seed())


if __name__ == "__main__":
    main()
