import pytest

from scaffold.whatsapp.layouts import LayoutError, ReplyButtonsLayout, TextLayout, Option


def test_plain_text_accepts_up_to_4096_but_interactive_bodies_keep_1024():
    assert TextLayout(body="x" * 4096).render()["text"]["body"] == "x" * 4096
    with pytest.raises(LayoutError):
        TextLayout(body="x" * 4097).render()
    with pytest.raises(LayoutError):
        ReplyButtonsLayout(body="x" * 1025, options=[Option(id="a", title="A")]).render()
