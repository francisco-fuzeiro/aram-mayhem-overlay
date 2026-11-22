"""F0: diagnostic physical card positions, client-relative and privacy-safe."""
from backend.workflow.f0_trace import emit_f0_geometry


def test_approved_geometry_records_only_verified_client_relative_bounds(monkeypatch):
    records = []
    size = (2544, 1353)
    bands = {
        "left": (643, 490, 340, 90),
        "centre": (1100, 490, 340, 90),
        "right": (1567, 490, 340, 90),
    }
    monkeypatch.delenv("ARAM_ORACLE_F0_TRACE", raising=False)
    assert not emit_f0_geometry(
        size, bands, writer=lambda **k: records.append(k) or True,
    )
    assert records == []
    monkeypatch.setenv("ARAM_ORACLE_F0_TRACE", "1")
    assert emit_f0_geometry(
        size, bands, writer=lambda **k: records.append(k) or True,
    )
    assert len(records) == 3
    assert [r["slot"] for r in records] == ["left", "centre", "right"]
    assert records[0] == {
        "slot": "left", "source": "wgc_geometry", "client_width": 2544,
        "client_height": 1353, "x": 643, "y": 490, "w": 340, "h": 90,
    }
    assert all(set(r) == set(records[0]) for r in records)
    assert all(isinstance(r[k], int) for r in records for k in
               ("x", "y", "w", "h", "client_width", "client_height"))


def test_bad_geometry_is_never_reported(monkeypatch):
    monkeypatch.setenv("ARAM_ORACLE_F0_TRACE", "1")
    calls = []
    emit = lambda size, bands: emit_f0_geometry(
        size, bands, writer=lambda **k: calls.append(k) or True,
    )
    valid = {
        "left": (643, 490, 340, 90),
        "centre": (1100, 490, 340, 90),
        "right": (1567, 490, 340, 90),
    }
    assert not emit((2544, 1353), {"left": valid["left"]})
    assert not emit((2544, 1353), {**valid, "left": (-1, 490, 340, 90)})
    assert not emit((2544, 1353), {**valid, "right": (2500, 490, 340, 90)})
    assert not emit((2544, 1353), {**valid, "right": ("player", 490, 340, 90)})
    assert not emit((9000, 1000), valid)
    assert calls == []
