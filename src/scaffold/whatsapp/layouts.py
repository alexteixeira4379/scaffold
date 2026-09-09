"""High-level WhatsApp message layouts.

This module defines a *semantic* contract that producers (e.g. the
``conversation-worker``) publish on the queue, plus the translation of each
layout into the low-level WhatsApp Cloud API payload.

The goal is to let producers describe *what* they want to show a candidate
("ask with 3 reply buttons", "offer a menu of plans") without knowing the
shape and the limits of the official ``interactive`` payload. All of Meta's
constraints (max 3 reply buttons, max 10 list rows, title lengths, etc.) are
enforced here, in one place, at render time.

A layout arrives inside the existing versioned envelope with ``type="layout"``
and a ``layout`` block. ``render_layout`` converts that block into the same
dict shape the worker already sends to the Graph API for native types.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Union
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- Meta Cloud API limits (as of Graph API v20+) ------------------------------
# Kept explicit so the rules are auditable and testable in one place.
MAX_REPLY_BUTTONS = 3
REPLY_BUTTON_TITLE_MAX = 20
MAX_LIST_ROWS_TOTAL = 10
LIST_ROW_TITLE_MAX = 24
LIST_ROW_DESCRIPTION_MAX = 72
SECTION_TITLE_MAX = 24
LIST_BUTTON_LABEL_MAX = 20
CTA_BUTTON_LABEL_MAX = 20
BODY_TEXT_MAX = 1024
HEADER_TEXT_MAX = 60
FOOTER_TEXT_MAX = 60


class LayoutError(ValueError):
    """Raised when a layout violates the high-level contract or a Meta limit."""


class LayoutKind(StrEnum):
    TEXT = "text"
    REPLY_BUTTONS = "reply_buttons"
    LIST = "list"
    MULTI_CHOICE = "multi_choice"
    IMAGE = "image"
    DOCUMENT = "document"
    CTA_URL = "cta_url"


# --- Shared building blocks ----------------------------------------------------


class TextHeader(BaseModel):
    """Optional interactive header carrying plain text."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    text: str

    @model_validator(mode="after")
    def _validate(self) -> TextHeader:
        value = self.text.strip()
        if not value:
            raise LayoutError("header.text vazio")
        if len(value) > HEADER_TEXT_MAX:
            raise LayoutError(f"header.text excede {HEADER_TEXT_MAX} caracteres")
        return self


class Option(BaseModel):
    """A selectable option. ``id`` is the stable value echoed back on the
    inbound webhook when the candidate selects it."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Option:
        if not self.id.strip():
            raise LayoutError("option.id vazio")
        if not self.title.strip():
            raise LayoutError("option.title vazio")
        return self


class Section(BaseModel):
    """A group of rows inside a list layout."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    rows: list[Option]

    @model_validator(mode="after")
    def _validate(self) -> Section:
        if self.title is not None and len(self.title.strip()) > SECTION_TITLE_MAX:
            raise LayoutError(f"section.title excede {SECTION_TITLE_MAX} caracteres")
        if not self.rows:
            raise LayoutError("section.rows vazio")
        return self


def _validate_body(text: str) -> str:
    value = text.strip()
    if not value:
        raise LayoutError("body vazio")
    if len(value) > BODY_TEXT_MAX:
        raise LayoutError(f"body excede {BODY_TEXT_MAX} caracteres")
    return value


def _validate_footer(footer: str | None) -> None:
    if footer is not None and len(footer.strip()) > FOOTER_TEXT_MAX:
        raise LayoutError(f"footer excede {FOOTER_TEXT_MAX} caracteres")


def _interactive_shell(
    *,
    body: str,
    header: TextHeader | None,
    footer: str | None,
    action: dict[str, Any],
    interactive_type: str,
) -> dict[str, Any]:
    interactive: dict[str, Any] = {
        "type": interactive_type,
        "body": {"text": body},
        "action": action,
    }
    if header is not None:
        interactive["header"] = {"type": "text", "text": header.text.strip()}
    if footer is not None and footer.strip():
        interactive["footer"] = {"text": footer.strip()}
    return interactive


# --- Layout schemas ------------------------------------------------------------


class TextLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.TEXT] = LayoutKind.TEXT
    body: str
    preview_url: bool = False

    def render(self) -> dict[str, Any]:
        body = _validate_body(self.body)
        return {"type": "text", "text": {"body": body, "preview_url": self.preview_url}}


class ReplyButtonsLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.REPLY_BUTTONS] = LayoutKind.REPLY_BUTTONS
    body: str
    header: TextHeader | None = None
    footer: str | None = None
    options: list[Option]

    def render(self) -> dict[str, Any]:
        body = _validate_body(self.body)
        _validate_footer(self.footer)
        if not (1 <= len(self.options) <= MAX_REPLY_BUTTONS):
            raise LayoutError(
                f"reply_buttons requer entre 1 e {MAX_REPLY_BUTTONS} opcoes"
            )
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise LayoutError("reply_buttons com option.id duplicado")
        buttons: list[dict[str, Any]] = []
        for option in self.options:
            title = option.title.strip()
            if len(title) > REPLY_BUTTON_TITLE_MAX:
                raise LayoutError(
                    f"option.title '{title}' excede {REPLY_BUTTON_TITLE_MAX} caracteres"
                )
            buttons.append(
                {"type": "reply", "reply": {"id": option.id, "title": title}}
            )
        interactive = _interactive_shell(
            body=body,
            header=self.header,
            footer=self.footer,
            action={"buttons": buttons},
            interactive_type="button",
        )
        return {"type": "interactive", "interactive": interactive}


def _render_list_interactive(
    *,
    body: str,
    header: TextHeader | None,
    footer: str | None,
    button_label: str,
    sections: list[Section],
) -> dict[str, Any]:
    label = button_label.strip()
    if not label:
        raise LayoutError("button_label vazio")
    if len(label) > LIST_BUTTON_LABEL_MAX:
        raise LayoutError(f"button_label excede {LIST_BUTTON_LABEL_MAX} caracteres")
    if not sections:
        raise LayoutError("list requer ao menos uma secao")

    total_rows = 0
    seen_ids: set[str] = set()
    rendered_sections: list[dict[str, Any]] = []
    for section in sections:
        rendered_rows: list[dict[str, Any]] = []
        for row in section.rows:
            total_rows += 1
            if row.id in seen_ids:
                raise LayoutError(f"list com row.id duplicado: {row.id}")
            seen_ids.add(row.id)
            title = row.title.strip()
            if len(title) > LIST_ROW_TITLE_MAX:
                raise LayoutError(
                    f"row.title '{title}' excede {LIST_ROW_TITLE_MAX} caracteres"
                )
            rendered_row: dict[str, Any] = {"id": row.id, "title": title}
            if row.description is not None and row.description.strip():
                desc = row.description.strip()
                if len(desc) > LIST_ROW_DESCRIPTION_MAX:
                    raise LayoutError(
                        f"row.description excede {LIST_ROW_DESCRIPTION_MAX} caracteres"
                    )
                rendered_row["description"] = desc
            rendered_rows.append(rendered_row)
        rendered_section: dict[str, Any] = {"rows": rendered_rows}
        if section.title is not None and section.title.strip():
            rendered_section["title"] = section.title.strip()
        rendered_sections.append(rendered_section)

    if total_rows > MAX_LIST_ROWS_TOTAL:
        raise LayoutError(
            f"list excede {MAX_LIST_ROWS_TOTAL} linhas no total (tem {total_rows})"
        )

    interactive = _interactive_shell(
        body=body,
        header=header,
        footer=footer,
        action={"button": label, "sections": rendered_sections},
        interactive_type="list",
    )
    return {"type": "interactive", "interactive": interactive}


class ListLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.LIST] = LayoutKind.LIST
    body: str
    header: TextHeader | None = None
    footer: str | None = None
    button_label: str
    sections: list[Section]

    def render(self) -> dict[str, Any]:
        body = _validate_body(self.body)
        _validate_footer(self.footer)
        return _render_list_interactive(
            body=body,
            header=self.header,
            footer=self.footer,
            button_label=self.button_label,
            sections=self.sections,
        )


class MultiChoiceLayout(BaseModel):
    """Multiple-choice selection.

    The official Cloud API has no native multi-select widget, so this is
    rendered as a List Message. The ``min``/``max`` selection bounds are not
    enforced by WhatsApp; they are carried in the metadata block by the worker
    so the producer's accumulation logic can validate the collected answers.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.MULTI_CHOICE] = LayoutKind.MULTI_CHOICE
    body: str
    header: TextHeader | None = None
    footer: str | None = None
    button_label: str = "Selecionar"
    options: list[Option]
    min_select: int = 1
    max_select: int | None = None

    def render(self) -> dict[str, Any]:
        body = _validate_body(self.body)
        _validate_footer(self.footer)
        if not self.options:
            raise LayoutError("multi_choice requer ao menos uma opcao")
        if self.min_select < 0:
            raise LayoutError("min_select nao pode ser negativo")
        if self.max_select is not None and self.max_select < self.min_select:
            raise LayoutError("max_select nao pode ser menor que min_select")
        return _render_list_interactive(
            body=body,
            header=self.header,
            footer=self.footer,
            button_label=self.button_label,
            sections=[Section(rows=self.options)],
        )

    def selection_bounds(self) -> dict[str, int | None]:
        return {"min_select": self.min_select, "max_select": self.max_select}


class ImageLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.IMAGE] = LayoutKind.IMAGE
    link: str | None = None
    id: str | None = None
    caption: str | None = None

    def render(self) -> dict[str, Any]:
        media = _render_media_source(self.link, self.id, media="image")
        if self.caption is not None and self.caption.strip():
            media["caption"] = self.caption.strip()
        return {"type": "image", "image": media}


class DocumentLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.DOCUMENT] = LayoutKind.DOCUMENT
    link: str | None = None
    id: str | None = None
    filename: str | None = None
    caption: str | None = None

    def render(self) -> dict[str, Any]:
        media = _render_media_source(self.link, self.id, media="document")
        if self.filename is not None and self.filename.strip():
            media["filename"] = self.filename.strip()
        if self.caption is not None and self.caption.strip():
            media["caption"] = self.caption.strip()
        return {"type": "document", "document": media}


class CtaUrlLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[LayoutKind.CTA_URL] = LayoutKind.CTA_URL
    body: str
    header: TextHeader | None = None
    footer: str | None = None
    button_label: str
    url: str

    def render(self) -> dict[str, Any]:
        body = _validate_body(self.body)
        _validate_footer(self.footer)
        label = self.button_label.strip()
        if not label:
            raise LayoutError("button_label vazio")
        if len(label) > CTA_BUTTON_LABEL_MAX:
            raise LayoutError(f"button_label excede {CTA_BUTTON_LABEL_MAX} caracteres")
        parsed = urlparse(self.url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise LayoutError("cta_url.url deve ser uma URL http(s) valida")
        interactive = _interactive_shell(
            body=body,
            header=self.header,
            footer=self.footer,
            action={
                "name": "cta_url",
                "parameters": {"display_text": label, "url": self.url.strip()},
            },
            interactive_type="cta_url",
        )
        return {"type": "interactive", "interactive": interactive}


def _render_media_source(
    link: str | None, media_id: str | None, *, media: str
) -> dict[str, Any]:
    has_link = bool(link and link.strip())
    has_id = bool(media_id and media_id.strip())
    if has_link == has_id:
        raise LayoutError(f"{media} deve conter exatamente um entre link ou id")
    if has_link:
        parsed = urlparse(link.strip())  # type: ignore[union-attr]
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise LayoutError(f"{media}.link deve ser uma URL http(s) valida")
        return {"link": link.strip()}  # type: ignore[union-attr]
    return {"id": media_id.strip()}  # type: ignore[union-attr]


# Discriminated union so pydantic picks the right schema from ``kind``.
LayoutBlock = Annotated[
    Union[
        TextLayout,
        ReplyButtonsLayout,
        ListLayout,
        MultiChoiceLayout,
        ImageLayout,
        DocumentLayout,
        CtaUrlLayout,
    ],
    Field(discriminator="kind"),
]


def render_layout(layout: LayoutBlock) -> dict[str, Any]:
    """Translate a validated high-level layout into the Cloud API message body
    fragment (``type`` + the matching payload key)."""

    return layout.render()
