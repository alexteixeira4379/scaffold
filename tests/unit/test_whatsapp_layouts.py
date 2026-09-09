"""Wave 1 — Contrato de layouts no scaffold.

Cobre a construção, validação e renderização dos 7 kinds de layout WhatsApp,
os limites da Cloud API (Meta) e a paridade entre ``LayoutKind`` e
``OnboardStepLayoutKind``.

Notas de caminho de erro (pydantic v2):
- Validações em ``model_validator(mode="after")`` de ``Option``/``Section``/
  ``TextHeader`` disparam na CONSTRUÇÃO e o pydantic encapsula o ``LayoutError``
  dentro de ``pydantic.ValidationError``.
- Validações dentro de ``.render()``/``render_layout`` lançam ``LayoutError``
  diretamente.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scaffold.constants.schema_enums import OnboardStepLayoutKind
from scaffold.whatsapp import (
    CtaUrlLayout,
    DocumentLayout,
    ImageLayout,
    LayoutError,
    LayoutKind,
    ListLayout,
    MultiChoiceLayout,
    Option,
    ReplyButtonsLayout,
    Section,
    TextHeader,
    TextLayout,
    render_layout,
)

# =============================================================================
# 1. Os 7 kinds constroem, validam e renderizam o payload nativo esperado
# =============================================================================


def test_text_render_produz_type_text():
    layout = TextLayout(body="Ola candidato")
    assert render_layout(layout) == {
        "type": "text",
        "text": {"body": "Ola candidato", "preview_url": False},
    }


def test_text_render_respeita_preview_url():
    layout = TextLayout(body="veja https://x.com", preview_url=True)
    assert render_layout(layout)["text"]["preview_url"] is True


def test_reply_buttons_render_produz_interactive_button():
    layout = ReplyButtonsLayout(
        body="Escolha",
        options=[
            Option(id="a", title="Sim"),
            Option(id="b", title="Nao"),
        ],
    )
    result = render_layout(layout)
    assert result == {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Escolha"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "a", "title": "Sim"}},
                    {"type": "reply", "reply": {"id": "b", "title": "Nao"}},
                ]
            },
        },
    }


def test_reply_buttons_render_inclui_header_e_footer():
    layout = ReplyButtonsLayout(
        body="Escolha",
        header=TextHeader(text="Titulo"),
        footer="rodape",
        options=[Option(id="a", title="Sim")],
    )
    interactive = render_layout(layout)["interactive"]
    assert interactive["header"] == {"type": "text", "text": "Titulo"}
    assert interactive["footer"] == {"text": "rodape"}


def test_list_render_produz_interactive_list():
    layout = ListLayout(
        body="Selecione um plano",
        button_label="Ver planos",
        sections=[
            Section(
                title="Planos",
                rows=[
                    Option(id="p1", title="Basico", description="R$ 10"),
                    Option(id="p2", title="Pro"),
                ],
            )
        ],
    )
    result = render_layout(layout)
    assert result == {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "Selecione um plano"},
            "action": {
                "button": "Ver planos",
                "sections": [
                    {
                        "title": "Planos",
                        "rows": [
                            {"id": "p1", "title": "Basico", "description": "R$ 10"},
                            {"id": "p2", "title": "Pro"},
                        ],
                    }
                ],
            },
        },
    }


def test_multi_choice_render_produz_interactive_list():
    layout = MultiChoiceLayout(
        body="Marque as areas",
        button_label="Selecionar",
        options=[
            Option(id="be", title="Backend"),
            Option(id="fe", title="Frontend"),
        ],
        min_select=1,
        max_select=2,
    )
    result = render_layout(layout)
    assert result["type"] == "interactive"
    assert result["interactive"]["type"] == "list"


def test_multi_choice_selection_bounds():
    layout = MultiChoiceLayout(
        body="Marque",
        options=[Option(id="a", title="A")],
        min_select=1,
        max_select=3,
    )
    assert layout.selection_bounds() == {"min_select": 1, "max_select": 3}


def test_image_render_produz_type_image_com_link():
    layout = ImageLayout(link="https://x.com/i.png", caption="foto")
    assert render_layout(layout) == {
        "type": "image",
        "image": {"link": "https://x.com/i.png", "caption": "foto"},
    }


def test_document_render_produz_type_document_com_id():
    layout = DocumentLayout(id="media-123", filename="cv.pdf")
    assert render_layout(layout) == {
        "type": "document",
        "document": {"id": "media-123", "filename": "cv.pdf"},
    }


def test_cta_url_render_produz_interactive_cta_url():
    layout = CtaUrlLayout(
        body="Acesse agora",
        button_label="Abrir",
        url="https://jobito.com/x",
    )
    result = render_layout(layout)
    assert result == {
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": "Acesse agora"},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Abrir",
                    "url": "https://jobito.com/x",
                },
            },
        },
    }


# =============================================================================
# 2. Limites — reply_buttons
# =============================================================================


def test_reply_buttons_zero_opcoes_falha():
    layout = ReplyButtonsLayout(body="x", options=[])
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_reply_buttons_quatro_opcoes_falha():
    layout = ReplyButtonsLayout(
        body="x",
        options=[Option(id=str(i), title=f"o{i}") for i in range(4)],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_reply_buttons_option_title_maior_que_20_falha():
    layout = ReplyButtonsLayout(
        body="x",
        options=[Option(id="a", title="X" * 21)],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_reply_buttons_ids_duplicados_falha():
    layout = ReplyButtonsLayout(
        body="x",
        options=[Option(id="dup", title="A"), Option(id="dup", title="B")],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


# =============================================================================
# 3. Limites — list
# =============================================================================


def test_list_mais_de_10_linhas_somando_secoes_falha():
    sec1 = Section(rows=[Option(id=f"a{i}", title=f"A{i}") for i in range(6)])
    sec2 = Section(rows=[Option(id=f"b{i}", title=f"B{i}") for i in range(5)])
    layout = ListLayout(body="x", button_label="ver", sections=[sec1, sec2])
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_list_row_title_maior_que_24_falha():
    layout = ListLayout(
        body="x",
        button_label="ver",
        sections=[Section(rows=[Option(id="a", title="X" * 25)])],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_list_section_title_maior_que_24_falha():
    # section.title é validado na CONSTRUÇÃO de Section (model_validator after),
    # portanto o LayoutError é encapsulado em ValidationError.
    with pytest.raises((LayoutError, ValidationError)):
        Section(title="X" * 25, rows=[Option(id="a", title="A")])


def test_list_button_label_maior_que_20_falha():
    layout = ListLayout(
        body="x",
        button_label="X" * 21,
        sections=[Section(rows=[Option(id="a", title="A")])],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_list_row_id_duplicado_falha():
    layout = ListLayout(
        body="x",
        button_label="ver",
        sections=[
            Section(rows=[Option(id="dup", title="A")]),
            Section(rows=[Option(id="dup", title="B")]),
        ],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


# =============================================================================
# 4. Limites — multi_choice
# =============================================================================


def test_multi_choice_max_menor_que_min_falha():
    layout = MultiChoiceLayout(
        body="x",
        options=[Option(id="a", title="A")],
        min_select=3,
        max_select=1,
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_multi_choice_sem_opcoes_falha():
    layout = MultiChoiceLayout(body="x", options=[])
    with pytest.raises(LayoutError):
        render_layout(layout)


# =============================================================================
# 5. Limites — body / header / footer
# =============================================================================


def test_body_vazio_falha():
    layout = TextLayout(body="   ")
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_body_maior_que_1024_falha():
    layout = TextLayout(body="X" * 1025)
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_header_maior_que_60_falha():
    # header.text é validado na CONSTRUÇÃO de TextHeader (model_validator after),
    # portanto o LayoutError é encapsulado em ValidationError.
    with pytest.raises((LayoutError, ValidationError)):
        TextHeader(text="X" * 61)


def test_footer_maior_que_60_falha():
    layout = ReplyButtonsLayout(
        body="x",
        footer="X" * 61,
        options=[Option(id="a", title="A")],
    )
    with pytest.raises(LayoutError):
        render_layout(layout)


# =============================================================================
# 6. Limites — cta_url
# =============================================================================


def test_cta_url_nao_http_falha():
    layout = CtaUrlLayout(body="x", button_label="ok", url="ftp://x.com/y")
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_cta_url_button_label_maior_que_20_falha():
    layout = CtaUrlLayout(body="x", button_label="X" * 21, url="https://x.com")
    with pytest.raises(LayoutError):
        render_layout(layout)


# =============================================================================
# 7. Limites — image / document (fonte de mídia)
# =============================================================================


def test_image_sem_link_e_sem_id_falha():
    layout = ImageLayout()
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_image_com_link_e_id_simultaneamente_falha():
    layout = ImageLayout(link="https://x.com/i.png", id="media-1")
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_image_link_nao_http_falha():
    layout = ImageLayout(link="ftp://x.com/i.png")
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_image_apenas_link_passa():
    layout = ImageLayout(link="https://x.com/i.png")
    assert render_layout(layout) == {
        "type": "image",
        "image": {"link": "https://x.com/i.png"},
    }


def test_image_apenas_id_passa():
    layout = ImageLayout(id="media-1")
    assert render_layout(layout) == {"type": "image", "image": {"id": "media-1"}}


def test_document_sem_link_e_sem_id_falha():
    layout = DocumentLayout()
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_document_com_link_e_id_simultaneamente_falha():
    layout = DocumentLayout(link="https://x.com/d.pdf", id="media-1")
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_document_link_nao_http_falha():
    layout = DocumentLayout(link="ftp://x.com/d.pdf")
    with pytest.raises(LayoutError):
        render_layout(layout)


def test_document_apenas_link_passa():
    layout = DocumentLayout(link="https://x.com/d.pdf")
    assert render_layout(layout) == {
        "type": "document",
        "document": {"link": "https://x.com/d.pdf"},
    }


def test_document_apenas_id_passa():
    layout = DocumentLayout(id="media-1")
    assert render_layout(layout) == {
        "type": "document",
        "document": {"id": "media-1"},
    }


# =============================================================================
# 8. Paridade de enums — OnboardStepLayoutKind == LayoutKind
# =============================================================================


def test_onboard_step_layout_kind_tem_exatamente_os_7_valores_de_layout_kind():
    assert {m.value for m in OnboardStepLayoutKind} == {m.value for m in LayoutKind}
