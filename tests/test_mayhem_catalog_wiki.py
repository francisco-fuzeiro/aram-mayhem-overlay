"""Reference catalog from the League of Legends Wiki (CC BY-SA 3.0)."""
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "data" / "augments" / "mayhem_catalog_wiki.json"


def test_catalog_has_licence_and_valid_rarities():
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert doc["license"] == "CC BY-SA 3.0" and doc["attribution"]
    names = [a["name"] for a in doc["augments"]]
    assert len(names) == len(set(names)) >= 200
    assert {a["rarity"] for a in doc["augments"]} == {"silver", "gold", "prismatic"}
