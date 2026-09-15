from scaffold.workflow import Presentation, build_presentation


def test_html_data_is_escaped_and_has_no_expression_evaluation():
    p = Presentation(text="Preview", template_html="<p>$value</p>", data={"value": '<script>${secret}</script>'})
    assert p.html() == "<p>&lt;script&gt;${secret}&lt;/script&gt;</p>"


def test_catalog_copy_wins_and_visual_truncation_keeps_full_text():
    p = build_presentation({"text_template": "$label: $body", "constants": {"label": "Demo"},
        "visual_limits": {"body": 4}}, {"label": "Fake", "body": "abcdefgh"})
    assert p.text == "Demo: abcdefgh"
    assert p.data["body"] == "abcd…"
