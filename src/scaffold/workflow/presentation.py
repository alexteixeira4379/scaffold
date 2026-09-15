from html import escape
from string import Template
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Presentation(BaseModel):
    """Additive outcome.presentations item; contains no domain or channel rules."""
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=12000)
    template_html: str | None = None
    data: dict[str, str] = Field(default_factory=dict)
    width: int = Field(default=1080, ge=1, le=5000)
    height: int = Field(default=1080, ge=1, le=5000)

    def html(self) -> str:
        return Template(self.template_html or "").substitute(
            {key: escape(value, quote=True) for key, value in self.data.items()})


def build_presentation(config: dict[str, Any], data: dict[str, Any]) -> Presentation:
    """Fill text and visual fields from a trusted step definition, never evaluate code."""
    values = {key: str(value) for key, value in data.items()}
    # Constants/copy belong to the catalog and cannot be replaced by generated values.
    values.update({key: str(value) for key, value in config.get("constants", {}).items()})
    text = Template(config["text_template"]).substitute(values)
    visual = dict(values)
    for key, limit in config.get("visual_limits", {}).items():
        value = " ".join(visual.get(key, "").split())
        visual[key] = value[:int(limit)] + ("…" if len(value) > int(limit) else "")
    return Presentation(text=text, template_html=config.get("template_html"), data=visual,
                        width=config.get("width", 1080), height=config.get("height", 1080))
