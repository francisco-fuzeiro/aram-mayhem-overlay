"""AramMeta local snapshot: few requests per patch, nothing outside the folder."""
import json

from backend.tierdb import arammeta

DOC = {"patch_prefix": "16.23", "champs": {"107": {"alias": "Rengar"}, "103": {"alias": "Ahri"}}}


def _server(calls):
    def fetch(url):
        calls.append(url)
        if url.endswith("tier-list.json"):
            return json.dumps(DOC).encode()
        return b'{"poolAugments": []}'
    return fetch


def test_tier_list_once_a_day_and_one_file_per_champion(tmp_path, monkeypatch):
    monkeypatch.setattr(arammeta, "MIN_GAP_S", 0.0)
    calls = []
    f = _server(calls)
    assert arammeta.refresh_tier_list(root=tmp_path, fetch=f, now=1000.0) == "16.23"
    assert arammeta.refresh_tier_list(root=tmp_path, fetch=f, now=2000.0) == "16.23"
    assert arammeta.ensure_champion("rengar", root=tmp_path, fetch=f)
    assert arammeta.ensure_champion("rengar", root=tmp_path, fetch=f)
    assert not arammeta.ensure_champion("unknownchamp", root=tmp_path, fetch=f)
    assert [c.rsplit("/", 1)[-1] for c in calls] == ["tier-list.json", "107.json"]
    assert (tmp_path / "16.23" / "champions" / "107.json").exists()
    assert (tmp_path / "16.23" / "tier-list.json").exists()


def test_bad_patch_prefix_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(arammeta, "MIN_GAP_S", 0.0)
    bad = lambda _u: json.dumps({"patch_prefix": "../x"}).encode()
    try:
        arammeta.refresh_tier_list(root=tmp_path, fetch=bad, now=1.0)
    except ValueError:
        pass
    assert not any(tmp_path.parent.glob("x"))
