"""Onboard steps — real roteiro script

Replaces the placeholder seeds from 0024 with the real onboarding script that
previously lived hardcoded in the conversation-worker. The goal is that every
candidate-facing onboarding sentence lives in ``onboard_steps`` (editable
without a redeploy), and the worker only fills in dynamic values.

Design:

* Text-only phases carry their final sentence in ``prompt_text``/``layout_spec``
  (``base_profile`` variants, ``create_resume``, ``finish_resume``,
  ``wait_activation``).
* Phases with runtime data carry a *template* whose placeholders the worker
  fills, never a hardcoded value:
    - ``confirm_jobs``: ``{cargo}``/``{pais}``/``{modalidade}``/``{nivel}``.
    - ``select_plan``: the button options are injected at runtime from the
      billing plans, so the seed carries no fixed plan option.
    - ``generate_checkout``: the ``url`` is injected at runtime from the real
      checkout session, so the seed carries an empty url placeholder.
* ``base_profile`` has three variants (ask both / ask name / ask contact); the
  worker selects the variant by which base fields are missing — a business
  rule, not roteiro text — so no sentence stays in code.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import OnboardPhase, OnboardStepLayoutKind

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = sa.table(
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

# --------------------------------------------------------------------------- #
# Canonical roteiro text (previously hardcoded in the conversation-worker).    #
# --------------------------------------------------------------------------- #
_WELCOME = (
    "Sua próxima oportunidade começa com o que você já sabe fazer.\n\n"
    "Sou a Jô, assistente virtual da Jobito. Vamos concluir seu cadastro em "
    "poucos passos: escolher um plano, definir sua busca, montar seu currículo "
    "e ativar sua assinatura."
)
_ASK_ALL = _WELCOME + "\n\nMe conta seu nome completo e um e-mail (ou seu LinkedIn) pra eu dar sequência!"
_ASK_NAME = "Qual seu nome completo?"
_ASK_CONTACT = "Qual seu e-mail ou LinkedIn?"

# confirm_jobs collection prompts: the worker asks each missing goal field in
# order. These are plain questions (no placeholders); the worker only decides
# which one to ask based on what the candidate has already answered.
_ASK_CARGO = "Qual cargo ou área você procura?"
_PLAN_REGISTERED = (
    "Plano *{plan}* registrado.\n\nAgora vamos definir sua busca. "
    "Qual cargo ou área você procura?"
)
_ASK_PAIS = "Em qual país você quer trabalhar?"
_ASK_MODALIDADE = (
    "Você procura trabalho remoto, presencial ou híbrido? Se não tiver "
    "preferência, pode dizer."
)
_ASK_NIVEL = (
    "Qual nível descreve seu objetivo: primeiro emprego, júnior, pleno ou "
    "sênior? Se não souber, tudo bem."
)

# confirm_jobs is a template; the worker fills the placeholders with the
# candidate's confirmed search goal. No concrete value is stored here.
_CONFIRM_JOBS_TEMPLATE = (
    "Vou procurar oportunidades de *{cargo}*, em {pais}, {modalidade}, "
    "nível {nivel}. Confirma esse objetivo? Você poderá ajustá-lo depois."
)

_CREATE_RESUME = (
    "Agora vamos montar seu currículo. Vou te fazer algumas perguntas rápidas — "
    "responda cada uma e, quando quiser pausar, é só dizer \"pausar\"."
)
_RESUME_PAUSED = "Seu progresso ficou salvo. Diga \u2018continuar\u2019 quando quiser retomar o currículo."
_FINISH_RESUME = (
    "Estamos finalizando seu currículo. Vamos concluir as últimas perguntas para "
    "deixá-lo pronto."
)
_GENERATE_CHECKOUT = "Tudo pronto! Finalize seu pagamento para ativar sua assinatura."
_WAIT_ACTIVATION = (
    "Estou aguardando a confirmação do seu pagamento. Assim que for confirmado, "
    "sua assinatura é ativada. Você pode me avisar quando pagar ou pedir para "
    "consultar sua assinatura."
)
_WAIT_ACTIVATION_LINK = (
    "Estou aguardando a confirmação do pagamento.\n\n"
    "Se precisar, use novamente o link:\n{checkout_url}\n\n"
    "Depois que o pagamento for confirmado, me avise ou peça para consultar sua assinatura."
)


def _seed_rows() -> list[dict]:
    return [
        # --- base_profile: three variants selected by missing fields --------- #
        {
            "phase": OnboardPhase.BASE_PROFILE.value,
            "step_key": "base_profile_ask_all",
            "step_order": 1,
            "prompt_text": _ASK_ALL,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_ALL},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.BASE_PROFILE.value,
            "step_key": "base_profile_ask_name",
            "step_order": 2,
            "prompt_text": _ASK_NAME,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_NAME},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.BASE_PROFILE.value,
            "step_key": "base_profile_ask_contact",
            "step_order": 3,
            "prompt_text": _ASK_CONTACT,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_CONTACT},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        # --- select_plan: options injected at runtime from billing plans ----- #
        {
            "phase": OnboardPhase.SELECT_PLAN.value,
            "step_key": "select_plan",
            "step_order": 1,
            "prompt_text": "Estes são os planos disponíveis para continuar com a Jobito:",
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": "Estes são os planos disponíveis para continuar com a Jobito:"},
            "accepted_answers": [],
            "answer_format": "plan_name",
            "active": True,
        },
        {
            "phase": OnboardPhase.SELECT_PLAN.value,
            "step_key": "select_plan_registered",
            "step_order": 2,
            "prompt_text": _PLAN_REGISTERED,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _PLAN_REGISTERED},
            "accepted_answers": [],
            "answer_format": None,
            "active": True,
        },
        # --- confirm_jobs: collect each goal field, then confirm ------------- #
        {
            "phase": OnboardPhase.CONFIRM_JOBS.value,
            "step_key": "confirm_jobs_ask_cargo",
            "step_order": 1,
            "prompt_text": _ASK_CARGO,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_CARGO},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.CONFIRM_JOBS.value,
            "step_key": "confirm_jobs_ask_pais",
            "step_order": 2,
            "prompt_text": _ASK_PAIS,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_PAIS},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.CONFIRM_JOBS.value,
            "step_key": "confirm_jobs_ask_modalidade",
            "step_order": 3,
            "prompt_text": _ASK_MODALIDADE,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_MODALIDADE},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.CONFIRM_JOBS.value,
            "step_key": "confirm_jobs_ask_nivel",
            "step_order": 4,
            "prompt_text": _ASK_NIVEL,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _ASK_NIVEL},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        # confirm_jobs is a template; the worker fills the placeholders.
        {
            "phase": OnboardPhase.CONFIRM_JOBS.value,
            "step_key": "confirm_jobs",
            "step_order": 5,
            "prompt_text": _CONFIRM_JOBS_TEMPLATE,
            "layout_kind": OnboardStepLayoutKind.REPLY_BUTTONS.value,
            "layout_spec": {
                "body": _CONFIRM_JOBS_TEMPLATE,
                "options": [
                    {"id": "confirm", "title": "Confirmar"},
                    {"id": "decline", "title": "Ajustar"},
                ],
            },
            "accepted_answers": ["confirm", "decline"],
            "answer_format": "option_id",
            "active": True,
        },
        # --- create_resume / finish_resume: intro; questions come from resume-api
        {
            "phase": OnboardPhase.CREATE_RESUME.value,
            "step_key": "create_resume",
            "step_order": 1,
            "prompt_text": _CREATE_RESUME,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _CREATE_RESUME},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.FINISH_RESUME.value,
            "step_key": "finish_resume",
            "step_order": 1,
            "prompt_text": _FINISH_RESUME,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _FINISH_RESUME},
            "accepted_answers": [],
            "answer_format": "text",
            "active": True,
        },
        {
            "phase": OnboardPhase.CREATE_RESUME.value,
            "step_key": "resume_paused",
            "step_order": 2,
            "prompt_text": _RESUME_PAUSED,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _RESUME_PAUSED},
            "accepted_answers": [],
            "answer_format": None,
            "active": True,
        },
        # --- generate_checkout: url injected at runtime ---------------------- #
        {
            "phase": OnboardPhase.GENERATE_CHECKOUT.value,
            "step_key": "generate_checkout",
            "step_order": 1,
            "prompt_text": _GENERATE_CHECKOUT,
            "layout_kind": OnboardStepLayoutKind.CTA_URL.value,
            "layout_spec": {
                "body": _GENERATE_CHECKOUT,
                "button_label": "Pagar agora",
                "url": "{checkout_url}",
            },
            "accepted_answers": [],
            "answer_format": None,
            "active": True,
        },
        # --- wait_activation ------------------------------------------------- #
        {
            "phase": OnboardPhase.WAIT_ACTIVATION.value,
            "step_key": "wait_activation",
            "step_order": 1,
            "prompt_text": _WAIT_ACTIVATION,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _WAIT_ACTIVATION},
            "accepted_answers": [],
            "answer_format": None,
            "active": True,
        },
        {
            "phase": OnboardPhase.WAIT_ACTIVATION.value,
            "step_key": "wait_activation_link",
            "step_order": 2,
            "prompt_text": _WAIT_ACTIVATION_LINK,
            "layout_kind": OnboardStepLayoutKind.TEXT.value,
            "layout_spec": {"body": _WAIT_ACTIVATION_LINK},
            "accepted_answers": [],
            "answer_format": None,
            "active": True,
        },
    ]


# Placeholder seeds inserted by 0024, restored on downgrade.
_OLD_STEP_KEYS = (
    "base_profile",
    "select_plan",
    "confirm_jobs",
    "create_resume",
    "finish_resume",
    "generate_checkout",
    "wait_activation",
)


def _delete_all_steps() -> None:
    op.execute(_TABLE.delete())


def upgrade() -> None:
    # Reset the catalog and insert the real roteiro. A full replace keeps the
    # table authoritative regardless of what 0024 seeded.
    _delete_all_steps()
    op.bulk_insert(_TABLE, _seed_rows())


def downgrade() -> None:
    # Restore the 0024 placeholder seeds.
    _delete_all_steps()
    op.bulk_insert(
        _TABLE,
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
