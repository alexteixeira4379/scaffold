"""Onboard steps

Central catalog for the internal onboarding roteiro (script). Stores only the
internal script/prompts and their WhatsApp layout spec — never candidate
answers.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import OnboardPhase, OnboardStepLayoutKind
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_onboard_phase = mysql_enum(OnboardPhase, "onboard_phase")
_onboard_step_layout_kind = mysql_enum(OnboardStepLayoutKind, "onboard_step_layout_kind")


def upgrade() -> None:
    op.create_table(
        "onboard_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "phase",
            _onboard_phase,
            server_default=mysql_default("onboard_phase", OnboardPhase.BASE_PROFILE),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "layout_kind",
            _onboard_step_layout_kind,
            server_default=mysql_default("onboard_step_layout_kind", OnboardStepLayoutKind.TEXT),
            nullable=False,
        ),
        sa.Column("layout_spec", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("accepted_answers", sa.JSON(), server_default=sa.text("(JSON_ARRAY())"), nullable=False),
        sa.Column("answer_format", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboard_steps")),
        sa.UniqueConstraint("step_key", name=op.f("uq_onboard_steps_step_key")),
    )

    onboard_steps = sa.table(
        "onboard_steps",
        sa.column("phase", sa.String),
        sa.column("step_key", sa.String),
        sa.column("step_order", sa.Integer),
        sa.column("prompt_text", sa.Text),
        sa.column("layout_kind", sa.String),
        sa.column("layout_spec", sa.JSON),
        sa.column("accepted_answers", sa.JSON),
        sa.column("answer_format", sa.String),
        sa.column("active", sa.Boolean),
    )

    op.bulk_insert(
        onboard_steps,
        [
            {
                "phase": OnboardPhase.BASE_PROFILE.value,
                "step_key": "base_profile",
                "step_order": 1,
                "prompt_text": (
                    "Vamos comecar montando seu perfil base. Me conte seu objetivo "
                    "profissional, area de atuacao e localizacao desejada."
                ),
                "layout_kind": OnboardStepLayoutKind.TEXT.value,
                "layout_spec": {
                    "body": (
                        "Vamos comecar montando seu perfil base. Me conte seu objetivo "
                        "profissional, area de atuacao e localizacao desejada."
                    )
                },
                "accepted_answers": [],
                "answer_format": "text",
                "active": True,
            },
            {
                "phase": OnboardPhase.SELECT_PLAN.value,
                "step_key": "select_plan",
                "step_order": 2,
                "prompt_text": "Escolha o plano que faz mais sentido para voce agora.",
                "layout_kind": OnboardStepLayoutKind.REPLY_BUTTONS.value,
                "layout_spec": {
                    "body": "Escolha o plano que faz mais sentido para voce agora.",
                    "options": [
                        {"id": "plan_basic", "title": "Basico"},
                        {"id": "plan_pro", "title": "Pro"},
                        {"id": "plan_premium", "title": "Premium"},
                    ],
                },
                "accepted_answers": ["plan_basic", "plan_pro", "plan_premium"],
                "answer_format": "option_id",
                "active": True,
            },
            {
                "phase": OnboardPhase.CONFIRM_JOBS.value,
                "step_key": "confirm_jobs",
                "step_order": 3,
                "prompt_text": "Selecione as vagas que deseja confirmar para candidatura.",
                "layout_kind": OnboardStepLayoutKind.LIST.value,
                "layout_spec": {
                    "body": "Selecione as vagas que deseja confirmar para candidatura.",
                    "button_label": "Ver vagas",
                    "sections": [
                        {
                            "title": "Vagas sugeridas",
                            "rows": [
                                {"id": "job_1", "title": "Vaga 1"},
                                {"id": "job_2", "title": "Vaga 2"},
                                {"id": "job_3", "title": "Vaga 3"},
                            ],
                        }
                    ],
                },
                "accepted_answers": ["job_1", "job_2", "job_3"],
                "answer_format": "option_id",
                "active": True,
            },
            {
                "phase": OnboardPhase.CREATE_RESUME.value,
                "step_key": "create_resume",
                "step_order": 4,
                "prompt_text": (
                    "Agora vamos criar seu curriculo. Envie um resumo da sua experiencia "
                    "e principais habilidades."
                ),
                "layout_kind": OnboardStepLayoutKind.TEXT.value,
                "layout_spec": {
                    "body": (
                        "Agora vamos criar seu curriculo. Envie um resumo da sua experiencia "
                        "e principais habilidades."
                    )
                },
                "accepted_answers": [],
                "answer_format": "text",
                "active": True,
            },
            {
                "phase": OnboardPhase.FINISH_RESUME.value,
                "step_key": "finish_resume",
                "step_order": 5,
                "prompt_text": (
                    "Seu curriculo esta quase pronto. Confirme os dados finais para "
                    "concluirmos a montagem."
                ),
                "layout_kind": OnboardStepLayoutKind.TEXT.value,
                "layout_spec": {
                    "body": (
                        "Seu curriculo esta quase pronto. Confirme os dados finais para "
                        "concluirmos a montagem."
                    )
                },
                "accepted_answers": [],
                "answer_format": "text",
                "active": True,
            },
            {
                "phase": OnboardPhase.GENERATE_CHECKOUT.value,
                "step_key": "generate_checkout",
                "step_order": 6,
                "prompt_text": "Tudo pronto! Finalize seu pagamento para ativar sua conta.",
                "layout_kind": OnboardStepLayoutKind.CTA_URL.value,
                "layout_spec": {
                    "body": "Tudo pronto! Finalize seu pagamento para ativar sua conta.",
                    "button_label": "Pagar agora",
                    "url": "https://checkout.jobito.example/session",
                },
                "accepted_answers": [],
                "answer_format": None,
                "active": True,
            },
            {
                "phase": OnboardPhase.WAIT_ACTIVATION.value,
                "step_key": "wait_activation",
                "step_order": 7,
                "prompt_text": (
                    "Recebemos seu pagamento. Estamos ativando sua conta e voce sera "
                    "avisado assim que estiver tudo pronto."
                ),
                "layout_kind": OnboardStepLayoutKind.TEXT.value,
                "layout_spec": {
                    "body": (
                        "Recebemos seu pagamento. Estamos ativando sua conta e voce sera "
                        "avisado assim que estiver tudo pronto."
                    )
                },
                "accepted_answers": [],
                "answer_format": None,
                "active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("onboard_steps")
