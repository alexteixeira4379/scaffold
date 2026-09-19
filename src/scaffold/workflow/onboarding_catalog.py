"""Candidate-facing journey. Domain questions stay in their owning catalogs."""
from scaffold.constants.schema_enums import OrchestratorStepKind as Kind

PROFILE_CARD_HTML = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<style>body{margin:0;background:#101b27;color:#edf4f3;font:28px Arial;padding:56px;box-sizing:border-box}
.brand{color:#88e2c5;font-size:24px;letter-spacing:3px}.label{color:#a7bbb9;font-size:22px;margin-top:38px}
h1{font-size:46px;line-height:1.15;margin:32px 0}h2{font-size:34px;line-height:1.3}
.box{background:#1b2b39;border-radius:24px;padding:30px;margin:30px 0;overflow-wrap:anywhere}
.note{font-size:23px;line-height:1.5;color:#c4d4d2}</style>
<div class="brand">JOBITO · SUA BUSCA, COM DIREÇÃO</div>
<h1>$first_name, veja o que preparamos.</h1>
<div class="box"><div class="label">SEU OBJETIVO</div><h2>$cargo</h2>
<p>$modelo_trabalho · $pais</p></div>
<p class="note">Perfil organizado a partir das suas informações.<br>
Critérios definidos para selecionar oportunidades compatíveis.</p>
<div class="label">AO ATIVAR</div><p class="note">A Jobito inicia sua busca e prepara as candidaturas.
No LinkedIn, o envio depende da conexão da sua conta no painel.</p></html>"""


def compose_greeting():
    return {
        "action_key": "compose_presentation", "first_name_from_candidate": True,
        "bindings": {
            "cargo": {"step": "search_goal", "path": "outcome.data.title"},
            "modelo_trabalho": {"step": "search_goal", "path": "outcome.data.work_model"},
            "pais": {"step": "search_goal", "path": "outcome.data.country_label"},
        },
        "fallback_text": "*Sua busca está preparada.*\n\n- *Objetivo:* $cargo\n- *Modelo:* $modelo_trabalho\n- *País:* $pais",
        "presentation": {
            "text_template": "*$first_name, sua busca está preparada.*\n\n- *Objetivo:* $cargo\n- *Modelo:* $modelo_trabalho\n- *País:* $pais",
            "template_html": PROFILE_CARD_HTML, "height": 1000,
        },
    }


def activation_card():
    # No second image, repeated receipt, or new profile questions after checkout.
    return {"action_key": "compose_presentation", "defaults": {}, "presentation": {
        "text_template": "*Pagamento confirmado. Sua Jobito está ativa!* ✅\n\n"
                         "Seu perfil e sua busca estão configurados. Vou preparar seu currículo final "
                         "e selecionar oportunidades compatíveis. Você acompanha os próximos resultados por aqui.\n\n"
                         "_As candidaturas no LinkedIn começam quando sua conta estiver conectada no painel._"
    }}


def onboard_steps():
    # Existing natural keys are retained for in-progress instances and audit history.
    return [
        ("welcome", Kind.INFO, {"text": "Oi! Sou a *Jô, a IA da Jobito*. Vou organizar seu perfil e ajudar você a buscar oportunidades que façam sentido para você."}),
        ("welcome_intent", Kind.INFO, {"text": ""}),
        ("search_goal", Kind.API_WORKFLOW, {"domain": "candidate", "workflow_key": "search_goal", "accept_initial_input": True}),
        ("profile_brief", Kind.API_WORKFLOW, {"domain": "resume", "workflow_key": "profile_brief"}),
        ("resume_builder", Kind.API_WORKFLOW, {"domain": "resume", "workflow_key": "builder"}),
        ("base_profile", Kind.API_WORKFLOW, {"domain": "candidate", "workflow_key": "base_profile"}),
        ("suspense_2", Kind.ACTION, compose_greeting()),
        ("activation_intro", Kind.INFO, {"text": ""}),
        ("subscription", Kind.API_WORKFLOW, {"domain": "billing", "workflow_key": "subscription"}),
        ("resume_intro", Kind.ACTION, activation_card()),
    ]
