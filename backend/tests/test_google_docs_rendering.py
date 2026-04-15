from app.application.connector.publish_service import _strip_flowchart_markdown_section
from app.infrastructure.integrations.google_docs_client import _markdown_to_docs_html, _markdown_to_docs_text


def test_markdown_to_docs_text_keeps_heading_lists_and_inline_styles() -> None:
    markdown = """# Title
## Section
- **Bold point** with [reference](https://example.com)
1. Numbered item
"""
    rendered = _markdown_to_docs_text(markdown)

    text = rendered["text"]
    assert "Title\n" in text
    assert "Section\n" in text
    assert "Bold point with reference\n" in text
    assert "Numbered item\n" in text

    paragraph_styles = rendered["styles"]
    assert any(s["named_style"] == "HEADING_1" for s in paragraph_styles)
    assert any(s["named_style"] == "HEADING_2" for s in paragraph_styles)

    bullets = rendered["bullets"]
    assert any(b["preset"] == "BULLET_DISC_CIRCLE_SQUARE" for b in bullets)
    assert any(b["preset"] == "NUMBERED_DECIMAL_ALPHA_ROMAN" for b in bullets)

    text_styles = rendered["text_styles"]
    assert any(s.get("bold") is True for s in text_styles)
    assert any(s.get("link") == "https://example.com" for s in text_styles)


def test_strip_flowchart_section_from_markdown() -> None:
    markdown = """# Title
## Context
Hello

## 🧩 Flowchart
- A -> B

## Immediate Next Actions
- Do X
"""
    cleaned = _strip_flowchart_markdown_section(markdown)

    assert "Flowchart" not in cleaned
    assert "## Context" in cleaned
    assert "## Immediate Next Actions" in cleaned


def test_strip_flow_at_a_glance_section_from_markdown() -> None:
    markdown = """# Title
## Context
Hello

## The flow at a glance
1. Capture lead -> validate
2. Route record -> notify team

## Delivery
- Done
"""
    cleaned = _strip_flowchart_markdown_section(markdown)

    assert "flow at a glance" not in cleaned.lower()
    assert "## Context" in cleaned
    assert "## Delivery" in cleaned


def test_markdown_to_docs_html_renders_tables_and_horizontal_rules() -> None:
    markdown = """## What you'll end up with

| Deliverable | Why it matters |
|---|---|
| n8n workflow | Repeatable automation backbone |

---
"""
    html = _markdown_to_docs_html(markdown)
    assert "<table>" in html
    assert "<th>Deliverable</th>" in html
    assert "<hr" in html
