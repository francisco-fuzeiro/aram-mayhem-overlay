"""D3 Settings page structural contracts without Qt or a League client."""
from html.parser import HTMLParser
from pathlib import Path

SETTINGS = Path(__file__).resolve().parents[1] / "frontend" / "settings.html"
SECTIONS = (
    "general", "overlay", "preferences", "ocr",
    "diagnostics", "feedback", "about",
)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.elements[attributes["id"]] = (tag, attributes)


def test_settings_sections_are_accessible_and_unique():
    parser = Elements()
    parser.feed(SETTINGS.read_text(encoding="utf-8"))
    tabs = []
    panels = []
    for name in SECTIONS:
        tag, nav = parser.elements[f"tab-{name}"]
        panel_tag, panel = parser.elements[f"panel-{name}"]
        assert tag == "button" and nav["role"] == "tab"
        assert panel_tag == "section" and panel["role"] == "tabpanel"
        assert nav["aria-controls"] == f"panel-{name}"
        assert panel["aria-labelledby"] == f"tab-{name}"
        tabs.append(nav)
        panels.append(panel)
    assert sum(tab["aria-selected"] == "true" for tab in tabs) == 1
    assert sum("hidden" not in panel for panel in panels) == 1
    assert parser.elements["preferred-build"][1].get("disabled") is not None
    assert parser.elements["save-preferences"][1].get("disabled") is not None


def test_settings_has_no_active_controls_for_future_overlay_customization():
    contents = SETTINGS.read_text(encoding="utf-8")
    assert "Not available in this version" in contents
    assert "Alt + H" in contents and "Alt + O" in contents
    assert 'id="ocr-summary"' in contents
    assert 'id="feedback-description"' in contents
