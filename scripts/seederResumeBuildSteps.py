"""Seeder: Popula resume_build_steps com os steps do workflow de onboarding.

Usage:
    python scripts/seederResumeBuildSteps.py
    python scripts/seederResumeBuildSteps.py --no-reset  # skip deletion phase
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from pathlib import Path

from sqlalchemy import select, func

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

importlib.import_module("scaffold.models")

from scaffold.constants.schema_enums import ResumeStepInputType  # noqa: E402
from scaffold.db.session import close_engine, get_session_factory  # noqa: E402
from scaffold.models.resume.resume_build_steps import ResumeBuildStep  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# STEPS DO WORKFLOW DE ONBOARDING
# ═══════════════════════════════════════════════════════════════════════════════

STEPS: list[dict] = [
    {
        "step_key": "choose_plan",
        "step_label": "Escolha de plano",
        "description": "Candidato escolhe o plano: platinum, diamond ou black.",
        "step_order": 1,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": True,
        "options": {
            "legacy_id": 24,
            "question": "Olá! É um prazer, sou Jobito! 👋 Fique tranquilo, vamos automatizar sua busca por emprego.\n\nEscolha o plano que melhor combina com você:\n\n💼 *Jobito Platinum* — R$ 19,90/mês\n- Análise de perfil e busca compatível (aumenta chances de MATCH)\n- Alertas e curadoria de vagas compatíveis no WhatsApp\n- Aviso quando uma vaga recente for postada (chegue antes)\n\n🚀 *Jobito Diamond* — R$ 49,90/mês\n- Tudo do Platinum +\n- Envio automático do seu currículo para empresas compatíveis\n- Aplicação automática no LinkedIn\n- Carta de apresentação personalizada para cada vaga\n- Relatório semanal de envios\n\n👑 *Jobito Black* — R$ 79,90/mês\n- Tudo do Diamond +\n- Currículo reformulado para cada vaga, destacando competências alinhadas\n\nQual você escolhe?",
            "question_options": ["platinum", "diamond", "black"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["platinum", "diamond", "black"]},
            "agent_prompt": "Analise a resposta do usuário e identifique qual plano ele escolheu. Normalize para: platinum, diamond ou black.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "info_plan_platinum",
        "step_label": "Informativo plano Platinum",
        "description": "Mensagem informativa sobre o plano Platinum. Aguarda confirmação de leitura.",
        "step_order": 2,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 50,
            "question": "👋 Oi, eu sou o *Jobito*. É um prazer falar com você!\n\nEu vou buscar oportunidades que tenham a ver com o seu perfil e te avisar assim que aparecer algo interessante.\n\nVocê não precisa mais ficar procurando vaga manualmente: eu faço a curadoria e te envio os alertas direto no WhatsApp.\n\nTopa deixar o Jobito trabalhar por você?",
            "question_options": ["Continuar"],
            "question_type": "resume",
            "answer_format": "ack",
            "answer_format_output": {"type": "string", "enum": ["continuar"]},
            "agent_prompt": "Passo informativo. Avançar quando o usuário confirmar leitura.",
            "step_condition": {"wk_id": 24, "wk_option": "platinum"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "info_plan_diamond",
        "step_label": "Informativo plano Diamond",
        "description": "Mensagem informativa sobre o plano Diamond. Aguarda confirmação de leitura.",
        "step_order": 2,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 51,
            "question": "👋 Bem-vindo! Eu sou o *Jobito*.\n\nEu vou levar sua busca de emprego para outro nível.\n\nAnaliso seu perfil, encontro vagas que fazem sentido pra você, ajusto seu currículo para cada oportunidade e faço as candidaturas automaticamente nos principais sites de emprego.\n\nVocê recebe um resumo periódico com o que foi feito e só precisa acompanhar tudo pelo WhatsApp.",
            "question_options": ["Continuar"],
            "question_type": "resume",
            "answer_format": "ack",
            "answer_format_output": {"type": "string", "enum": ["continuar"]},
            "agent_prompt": "Passo informativo. Avançar quando o usuário confirmar leitura.",
            "step_condition": {"wk_id": 24, "wk_option": "diamond"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "info_plan_black",
        "step_label": "Informativo plano Black",
        "description": "Mensagem informativa sobre o plano Black. Aguarda confirmação de leitura.",
        "step_order": 2,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 53,
            "question": "👋 Oi, eu sou o *Jobito*. É um prazer falar com você!\n\nA partir de agora, sua busca por emprego fica no piloto automático. Nada de passar o dia no LinkedIn, Indeed, Catho, Google Jobs e outros portais.\n\nSeu tempo é valioso. Deixe que a gente cuida dessa parte pra você.",
            "question_options": ["Continuar"],
            "question_type": "resume",
            "answer_format": "ack",
            "answer_format_output": {"type": "string", "enum": ["continuar"]},
            "agent_prompt": "Passo informativo. Avançar quando o usuário confirmar leitura.",
            "step_condition": {"wk_id": 24, "wk_option": "black"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "welcome_upload_cv",
        "step_label": "Enviar CV ou criar do zero",
        "description": "Candidato escolhe entre enviar CV existente ou criar um novo com a IA.",
        "step_order": 10,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": True,
        "options": {
            "legacy_id": 1,
            "question": "Para isso funcionar da melhor forma, precisamos ter o seu currículo em mãos.\n\nNós vamos analisar o seu CV para selecionar as melhores vagas com base nas suas experiências e no seu perfil profissional.\n\nComo você prefere seguir?\n1) Enviar o seu currículo atual\n2) Criar um currículo do zero com a nossa IA",
            "question_options": ["Enviar meu currículo", "Criar CV com a IA"],
            "question_type": "wk",
            "answer_format": "text",
            "answer_format_output": {"type": "string", "enum": ["Enviar meu currículo", "Criar CV com a IA"]},
            "agent_prompt": "Analise a mensagem do usuário e identifique se ele respondeu 'Enviar meu currículo' ou 'Criar CV com a IA'.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": "15",
            "auto_import": True,
        },
    },
    {
        "step_key": "extract_cv_data",
        "step_label": "Envio do currículo em PDF",
        "description": "Candidato envia PDF. Texto extraído é repassado sem alteração.",
        "step_order": 20,
        "input_type": ResumeStepInputType.FILE,
        "is_required": False,
        "options": {
            "legacy_id": 2,
            "question": "Por favor, envie seu currículo em PDF para que possamos continuar sua análise. 📄",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": "simple_answer_output",
            "agent_prompt": "Este passo serve apenas para repassar o texto recebido sem alterar o conteúdo.",
            "step_condition": {"wk_id": 1, "wk_option": "Enviar meu currículo"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "no_cv_intro",
        "step_label": "Introdução criação manual",
        "description": "Informa que o processo continuará com perguntas manuais.",
        "step_order": 30,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 3,
            "question": "Tudo bem! Vamos fazer algumas perguntas agora. Fique à vontade para mandar **Áudio** ou **Texto**.",
            "question_options": None,
            "question_type": "info",
            "answer_format": "text",
            "answer_format_output": None,
            "agent_prompt": "Explique que o processo continuará com perguntas manuais.",
            "step_condition": {"wk_id": 1, "wk_option": "Criar CV com a IA"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "user_email",
        "step_label": "E-mail do candidato",
        "description": "Coleta o e-mail de contato do candidato.",
        "step_order": 40,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": True,
        "options": {
            "legacy_id": 4,
            "question": "Para começar, informe seu e-mail.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "email",
            "answer_format_output": {"type": ["string", "null"], "description": "Endereço de e-mail identificado.", "format": "email"},
            "agent_prompt": "Analise a mensagem do usuário e identifique se ela contém um endereço de e-mail válido.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "job_and_skills_summary",
        "step_label": "Cargo, salário e resumo profissional",
        "description": "Coleta cargo desejado, salário pretendido e resumo de habilidades.",
        "step_order": 50,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": True,
        "options": {
            "legacy_id": 5,
            "question": "Fale sobre o cargo que busca, seu salário desejado e um breve resumo das suas habilidades.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {
                "type": "object",
                "properties": {
                    "cargo": {"type": "string", "description": "Profissão ou título do cargo desejado"},
                    "salario": {"type": "integer", "description": "Valor numérico do salário pretendido"},
                    "moeda": {"type": "string", "enum": ["BRL", "USD", "EUR", "ARS"], "default": "BRL"},
                    "resumo": {"type": "string", "description": "Resumo sobre habilidades e experiência"},
                },
                "required": ["cargo", "salario", "resumo"],
            },
            "agent_prompt": "Analise a resposta do usuário e extraia: cargo desejado, salário pretendido (valor numérico), moeda e resumo profissional.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": True,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "previous_companies",
        "step_label": "Empresas anteriores",
        "description": "Coleta nomes de empresas onde o candidato já trabalhou.",
        "step_order": 60,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": True,
        "options": {
            "legacy_id": 6,
            "question": "Agora sobre seu histórico profissional — se não tiver, diga \"nenhum\". Caso tenha, mencione o nome das empresas onde já atuou (ex: Coca Cola, Microsoft, Enel etc).",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "array", "items": {"type": "string"}},
            "agent_prompt": "Analise a resposta do usuário e extraia o nome das empresas onde ele já trabalhou.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "job_details_per_company",
        "step_label": "Detalhes por empresa",
        "description": "Para cada empresa, coleta cargo, atividades e datas.",
        "step_order": 70,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 7,
            "question": "Para a empresa [content], pode nos contar qual era seu cargo, atividades, data de início e saída?",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {
                "type": "object",
                "properties": {
                    "empresa": {"type": "string"},
                    "cargo": {"type": "string"},
                    "atividades": {"type": "string"},
                    "data_inicio": {"type": ["string", "null"]},
                    "data_saida": {"type": ["string", "null"]},
                },
                "required": ["empresa", "cargo", "atividades"],
            },
            "agent_prompt": "Analise a resposta do usuário sobre sua experiência na empresa e extraia: cargo, atividades, data de início e saída.",
            "step_condition": {"wk_id": 6},
            "repeat_for": {"wk_id": 6, "wk_answer_splitter": ","},
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "education_level",
        "step_label": "Nível de escolaridade",
        "description": "Identifica o nível de escolaridade mais alto do candidato.",
        "step_order": 80,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": True,
        "options": {
            "legacy_id": 8,
            "question": "Qual seu nível de escolaridade?",
            "question_options": ["Médio Completo", "Médio Incompleto", "Superior Completo", "Superior Incompleto", "Pós Graduado"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Médio Completo", "Médio Incompleto", "Superior Completo", "Superior Incompleto", "Pós Graduado"]},
            "agent_prompt": "Analise a resposta do usuário e identifique o nível de escolaridade mais alto.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "highschool_details",
        "step_label": "Detalhes ensino médio (completo)",
        "description": "Coleta escola e ano de conclusão do ensino médio.",
        "step_order": 90,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 9,
            "question": "📚 Em qual escola você cursou o ensino médio?\n\n📅 Informe também o ano de conclusão.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"nivel": {"type": "string", "enum": ["Médio"]}, "instituicao": {"type": "string"}, "ano_conclusao": {"type": ["string", "null"]}}, "required": ["nivel", "instituicao"]},
            "agent_prompt": "Analise a resposta e extraia o nome da escola e o ano de conclusão do ensino médio.",
            "step_condition": {"wk_id": 8, "wk_option": ["Médio Completo"]},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "highschool_details_incomplete",
        "step_label": "Detalhes ensino médio (incompleto)",
        "description": "Coleta escola e previsão de conclusão do ensino médio incompleto.",
        "step_order": 91,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 26,
            "question": "📚 Em qual escola você cursou ou está cursando o ensino médio (mesmo que tenha interrompido)?\n\n📅 Se souber, informe também o ano em que concluiu, pretende concluir ou em que parou os estudos.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"nivel": {"type": "string", "enum": ["Médio"]}, "instituicao": {"type": "string"}, "ano_conclusao": {"type": ["string", "null"]}}, "required": ["nivel", "instituicao"]},
            "agent_prompt": "Analise a resposta e extraia nome da escola e ano de conclusão/previsão do ensino médio.",
            "step_condition": {"wk_id": 8, "wk_option": ["Médio Incompleto"]},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "college_details",
        "step_label": "Detalhes faculdade (completo)",
        "description": "Coleta faculdade, curso e datas do ensino superior completo.",
        "step_order": 100,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 10,
            "question": "🎓 Nos informe o nome da faculdade e o curso que você fez.\n\n📅 Informe também as datas de início e término.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"nivel": {"type": "string", "enum": ["Superior"]}, "instituicao": {"type": "string"}, "curso": {"type": "string"}, "data_inicio": {"type": ["string", "null"]}, "data_termino": {"type": ["string", "null"]}}, "required": ["nivel", "instituicao", "curso"]},
            "agent_prompt": "Analise a resposta e extraia nome da faculdade, curso e datas de início e término.",
            "step_condition": {"wk_id": 8, "wk_option": ["Superior Completo"]},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "college_details_incomplete",
        "step_label": "Detalhes faculdade (incompleto)",
        "description": "Coleta faculdade, curso e datas do ensino superior incompleto.",
        "step_order": 101,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 27,
            "question": "🎓 Nos informe o nome da faculdade e o curso que você está fazendo.\n\n📅 Também envie as datas de início e a previsão de término.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"nivel": {"type": "string", "enum": ["Superior"]}, "instituicao": {"type": "string"}, "curso": {"type": "string"}, "data_inicio": {"type": ["string", "null"]}, "data_termino": {"type": ["string", "null"]}}, "required": ["nivel", "instituicao", "curso"]},
            "agent_prompt": "Analise a resposta e extraia nome da faculdade, curso e datas de início e previsão de término.",
            "step_condition": {"wk_id": 8, "wk_option": ["Superior Incompleto"]},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "postgraduate_details_pos",
        "step_label": "Detalhes pós-graduação",
        "description": "Coleta instituição, curso e datas da pós-graduação.",
        "step_order": 110,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 20,
            "question": "🎓 Informe o nome da instituição onde você fez (ou está fazendo) a pós-graduação e o curso realizado.\n\n📅 Informe também as datas de início e término (ou a previsão de término, se ainda estiver cursando).",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"nivel": {"type": "string", "enum": ["Superior"]}, "instituicao": {"type": "string"}, "curso": {"type": "string"}, "data_inicio": {"type": ["string", "null"]}, "data_termino": {"type": ["string", "null"]}}, "required": ["nivel", "instituicao", "curso"]},
            "agent_prompt": "Analise a resposta e extraia nome da instituição, curso de pós-graduação e datas.",
            "step_condition": {"wk_id": 8, "wk_option": ["Pós Graduado"]},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "extra_section_intro",
        "step_label": "Introdução seção extras",
        "description": "Informa que a seção de informações extras é opcional.",
        "step_order": 111,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 12,
            "question": "Ótimo, seu CV está ficando excelente! Agora vamos para a sessão de informações extras. Todas são *opcionais*.",
            "question_options": None,
            "question_type": "info",
            "answer_format": "ack",
            "answer_format_output": "",
            "agent_prompt": "",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "extra_info_or_course",
        "step_label": "Deseja adicionar cursos extras?",
        "description": "Pergunta se o candidato quer adicionar cursos técnicos, livres ou online.",
        "step_order": 112,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 28,
            "question": "Você deseja adicionar algum curso extra ao seu currículo? (por exemplo: curso técnico, curso livre ou curso online).",
            "question_options": ["Sim", "Não"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o candidato quer adicionar cursos extras.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "extra_info_or_course_details",
        "step_label": "Lista de cursos extras",
        "description": "Coleta nomes dos cursos extras que o candidato quer adicionar.",
        "step_order": 113,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 29,
            "question": "Liste os cursos extras que você deseja adicionar ao currículo, informando apenas o nome de cada um.\nExemplo: Curso de Excel Avançado, Curso de Programação Web.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "array", "items": {"type": "string"}},
            "agent_prompt": "Analise a resposta e extraia os cursos extras mencionados.",
            "step_condition": {"wk_id": 28, "wk_option": "Sim"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "extra_certifications",
        "step_label": "Deseja adicionar certificações?",
        "description": "Pergunta se o candidato possui certificações profissionais.",
        "step_order": 114,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 30,
            "question": "Você possui alguma certificação que deseja adicionar ao seu currículo? (por exemplo: certificações profissionais ou exames de proficiência).",
            "question_options": ["Sim", "Não"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o candidato quer adicionar certificações.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "extra_certifications_details",
        "step_label": "Lista de certificações",
        "description": "Coleta nomes das certificações que o candidato quer adicionar.",
        "step_order": 115,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 31,
            "question": "Liste as certificações que você deseja adicionar ao currículo, informando apenas o nome de cada uma.\nExemplo: Certificação AWS Solutions Architect, Certificação ITIL Foundation.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "array", "items": {"type": "string"}},
            "agent_prompt": "Analise a resposta e extraia as certificações mencionadas.",
            "step_condition": {"wk_id": 30, "wk_option": "Sim"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "speaks_languages",
        "step_label": "Fala outros idiomas?",
        "description": "Pergunta se o candidato fala algum idioma além do português.",
        "step_order": 130,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 13,
            "question": "Fala algum idioma além do português?",
            "question_options": ["Sim", "Não"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o usuário fala outro idioma além do português.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "language_list",
        "step_label": "Lista de idiomas",
        "description": "Coleta quais idiomas o candidato fala.",
        "step_order": 140,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 14,
            "question": "Informe quais idiomas você fala.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "array", "items": {"type": "string"}},
            "agent_prompt": "Analise a resposta e extraia a lista de idiomas mencionados.",
            "step_condition": {"wk_id": 13, "wk_option": "Sim"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "language_fluency",
        "step_label": "Nível de fluência por idioma",
        "description": "Coleta o nível de proficiência para cada idioma informado.",
        "step_order": 150,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 15,
            "question": "Para o idioma [content], qual seu nível?",
            "question_options": ["básico", "intermediário", "avançado", "fluente"],
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "string", "enum": ["básico", "intermediário", "avançado", "fluente"]},
            "agent_prompt": "Analise a resposta e identifique o nível de conversação no idioma informado.",
            "step_condition": {"wk_id": 13, "wk_option": "Sim"},
            "repeat_for": {"wk_id": 14, "wk_answer_splitter": ","},
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "has_reference_letter",
        "step_label": "Tem carta de referência?",
        "description": "Pergunta se o candidato possui carta de referência ou indicação profissional.",
        "step_order": 160,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 16,
            "question": "Tem alguma carta de referência ou indicação profissional?",
            "question_options": ["Sim", "Não"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o candidato possui carta de referência ou indicação.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "reference_details",
        "step_label": "Detalhes da referência",
        "description": "Coleta informações sobre a carta de referência ou indicação.",
        "step_order": 170,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 17,
            "question": "Conte-nos sobre sua carta de referência ou quem te indicou e o cargo.",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"tipo": {"type": ["string", "null"], "enum": ["carta", "indicacao", None]}, "nome": {"type": ["string", "null"]}, "cargo": {"type": ["string", "null"]}, "descricao": {"type": "string"}}, "required": ["descricao"]},
            "agent_prompt": "Analise a resposta e extraia informações sobre a referência profissional.",
            "step_condition": {"wk_id": 16, "wk_option": "Sim"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "volunteer_work",
        "step_label": "Trabalho voluntário ou projeto?",
        "description": "Pergunta se o candidato tem trabalho voluntário ou projeto relevante.",
        "step_order": 180,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 18,
            "question": "Já realizou algum trabalho voluntário ou projeto relevante que gostaria de mencionar?",
            "question_options": ["Sim", "Não"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Sim", "Não"]},
            "agent_prompt": "Analise a resposta e determine se o candidato tem trabalho voluntário ou projeto relevante.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "volunteer_description",
        "step_label": "Detalhes do voluntariado/projeto",
        "description": "Coleta detalhes sobre o trabalho voluntário ou projeto.",
        "step_order": 190,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 19,
            "question": "Conte-nos sobre seu trabalho voluntário ou projeto",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "object", "properties": {"titulo": {"type": "string"}, "tipo": {"type": "string", "enum": ["projeto", "voluntariado"]}, "funcao": {"type": "string"}, "descricao": {"type": "string"}, "impacto": {"type": "string"}, "data_inicio": {"type": ["string", "null"]}, "data_fim": {"type": ["string", "null"]}}, "required": ["titulo", "tipo", "funcao", "descricao"]},
            "agent_prompt": "Analise a resposta e extraia informações sobre o projeto ou trabalho voluntário.",
            "step_condition": {"wk_id": 18, "wk_option": "Sim"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": True,
        },
    },
    {
        "step_key": "show_job_template",
        "step_label": "Mostrar vagas compatíveis",
        "description": "Exibe template de vagas compatíveis e pede confirmação para continuar.",
        "step_order": 199,
        "input_type": ResumeStepInputType.TEXT,
        "is_required": False,
        "options": {
            "legacy_id": 37,
            "question": "🚀 Encontramos vagas que combinam com você!\n\nSeu cadastro foi finalizado e agora o Jobito já pode começar a trabalhar por você — analisando seu perfil e te conectando automaticamente às melhores oportunidades.\n\nPara liberar tudo isso e ativar seu CV inteligente, basta finalizar a assinatura do seu plano. Assim que o pagamento for confirmado, nossa IA começa a agir imediatamente.\n\nEstou por aqui se precisar de ajuda!",
            "question_options": None,
            "question_type": "info",
            "answer_format": "ack",
            "answer_format_output": {"type": "string", "enum": ["Continuar", "Não"]},
            "agent_prompt": "Analise a resposta e identifique se o usuário deseja continuar o processo.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": False,
            "demo_template_html": True,
        },
    },
    {
        "step_key": "ask_payment_link",
        "step_label": "Gostaria de receber link de pagamento?",
        "description": "Pergunta se o candidato quer o link de pagamento para ativar o Jobito.",
        "step_order": 200,
        "input_type": ResumeStepInputType.SELECT,
        "is_required": False,
        "options": {
            "legacy_id": 22,
            "question": "Gostaria de receber o link de pagamento para ativar seu acesso ao Jobito e começar a receber vagas compatíveis automaticamente?",
            "question_options": ["Quero o Jobito", "Não quero"],
            "question_type": "resume",
            "answer_format": "option",
            "answer_format_output": {"type": "string", "enum": ["Quero o Jobito", "Não quero"]},
            "agent_prompt": "Analise a resposta e identifique se o candidato deseja receber o link de pagamento.",
            "step_condition": None,
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": False,
        },
    },
    {
        "step_key": "reason_no_payment",
        "step_label": "Motivo da recusa",
        "description": "Coleta motivo livre para não querer ativar o Jobito.",
        "step_order": 210,
        "input_type": ResumeStepInputType.TEXTAREA,
        "is_required": False,
        "options": {
            "legacy_id": 23,
            "question": "Tudo bem! Pode nos contar o motivo de não querer ativar o Jobito agora?",
            "question_options": None,
            "question_type": "resume",
            "answer_format": "text",
            "answer_format_output": {"type": "string", "description": "Texto livre com a justificativa do usuário."},
            "agent_prompt": "Registre o motivo livre informado para não querer ativar o Jobito.",
            "step_condition": {"wk_id": 22, "wk_option": "Não quero"},
            "repeat_for": None,
            "dispatch_job": False,
            "awaiting_time": None,
            "auto_import": False,
        },
    },
]


async def get_or_create_step(session, step_data: dict) -> ResumeBuildStep:
    """Insert or update a step by step_key."""
    row = (
        await session.execute(
            select(ResumeBuildStep)
            .where(ResumeBuildStep.step_key == step_data["step_key"])
            .limit(1)
        )
    ).scalars().first()

    options_json = step_data["options"]

    if row is not None:
        row.step_label = step_data["step_label"]
        row.description = step_data["description"]
        row.step_order = step_data["step_order"]
        row.input_type = step_data["input_type"]
        row.options = options_json
        row.is_required = step_data["is_required"]
        row.active = True
        return row

    step = ResumeBuildStep(
        step_key=step_data["step_key"],
        step_label=step_data["step_label"],
        description=step_data["description"],
        step_order=step_data["step_order"],
        input_type=step_data["input_type"],
        options=options_json,
        is_required=step_data["is_required"],
        active=True,
    )
    session.add(step)
    await session.flush()
    return step


async def run_seed(reset: bool) -> None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            if reset:
                # Delete existing steps (only if no answers reference them)
                existing_count_result = await session.execute(
                    select(func.count()).select_from(ResumeBuildStep)
                )
                existing_count = existing_count_result.scalar() or 0
                if existing_count > 0:
                    print(f"  ⚠️  Found {existing_count} existing steps (updating in-place, not deleting)")

            for step_data in STEPS:
                await get_or_create_step(session, step_data)

            await session.commit()

            # Final count
            count_result = await session.execute(
                select(func.count()).select_from(ResumeBuildStep)
            )
            total = count_result.scalar() or 0

        print(f"\n✅ Seeded {len(STEPS)} resume_build_steps (total in DB: {total})")
    finally:
        await close_engine()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed resume_build_steps with onboarding workflow steps"
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        dest="no_reset",
        help="Skip any reset/cleanup (default behavior already preserves existing data)",
    )
    args = parser.parse_args()

    asyncio.run(run_seed(reset=not args.no_reset))


if __name__ == "__main__":
    main()
