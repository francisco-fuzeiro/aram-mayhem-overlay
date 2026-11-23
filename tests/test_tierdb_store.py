"""F1 tier DB: schema and provenance contract.

Every stored value must carry its source, snapshot and sample size. Data is
never fabricated: values without a sample size are rejected, and the same
snapshot (by SHA-256) is never ingested twice.
"""
import sqlite3

import pytest

from backend.tierdb.store import (
    Observation,
    ProvenanceError,
    SnapshotMeta,
    SourceMeta,
    TierStore,
)


def _source(**overrides) -> SourceMeta:
    data = dict(
        name="synthetic-source",
        url="https://example.invalid/data",
        license="CC-BY-4.0",
        attribution="Synthetic fixture, not real data",
        commercial_ok=True,
    )
    data.update(overrides)
    return SourceMeta(**data)


def _snapshot(sha: str = "a" * 64, **overrides) -> SnapshotMeta:
    data = dict(
        patch="26.23",
        region="test",
        queue=2400,
        window_start="2026-11-18",
        window_end="2026-11-21",
        sha256=sha,
        metric_definitions={"win": "wins / games of the champion with augment"},
    )
    data.update(overrides)
    return SnapshotMeta(**data)


@pytest.fixture()
def store(tmp_path):
    s = TierStore(tmp_path / "tierdb.sqlite")
    yield s
    s.close()


def test_schema_creates_all_tables(store):
    tables = {
        row[0]
        for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {
        "source", "snapshot", "observation", "quarantine",
        "tier_run", "augment_tier", "champion_tier",
    } <= tables


def test_ingest_records_provenance_per_value(store):
    obs = [
        Observation(scope="champion", metric="win", champion_id="ahri", wins=520, n=1000),
        Observation(scope="champ_aug", metric="win", champion_id="ahri",
                    augment_id="1001", wins=60, n=100),
    ]
    snap_id = store.ingest(_source(), _snapshot(), obs)
    assert snap_id is not None

    rows = store.observations(patch="26.23", metric="win", champion_id="ahri")
    assert len(rows) == 2
    for row in rows:
        assert row.source_name == "synthetic-source"
        assert row.snapshot_sha256 == "a" * 64
        assert row.n > 0
    snap = store.snapshot(snap_id)
    assert snap.row_count == 2
    assert snap.fetched_at  # recorded automatically


def test_value_without_sample_size_is_rejected(store):
    with pytest.raises(ProvenanceError):
        store.ingest(
            _source(), _snapshot(),
            [Observation(scope="champion", metric="win", champion_id="ahri", wins=5, n=0)],
        )
    with pytest.raises(ProvenanceError):
        store.ingest(
            _source(), _snapshot(),
            [Observation(scope="champion", metric="win", champion_id="ahri", wins=5, n=None)],
        )


def test_wins_cannot_exceed_games(store):
    with pytest.raises(ProvenanceError):
        store.ingest(
            _source(), _snapshot(),
            [Observation(scope="champion", metric="win", champion_id="ahri", wins=11, n=10)],
        )


def test_scope_requires_matching_keys(store):
    # A champion+augment value must name both; a global one names no champion.
    with pytest.raises(ProvenanceError):
        store.ingest(
            _source(), _snapshot(),
            [Observation(scope="champ_aug", metric="win", champion_id="ahri", wins=1, n=2)],
        )
    with pytest.raises(ProvenanceError):
        store.ingest(
            _source(), _snapshot(),
            [Observation(scope="global_aug", metric="win", champion_id="ahri",
                         augment_id="1001", wins=1, n=2)],
        )


def test_snapshot_requires_sha256_and_patch(store):
    with pytest.raises(ProvenanceError):
        store.ingest(_source(), _snapshot(sha="not-a-sha"), [])
    with pytest.raises(ProvenanceError):
        store.ingest(_source(), _snapshot(patch=""), [])


def test_same_sha_is_idempotent(store):
    obs = [Observation(scope="champion", metric="win", champion_id="ahri", wins=5, n=10)]
    first = store.ingest(_source(), _snapshot(), obs)
    second = store.ingest(_source(), _snapshot(), obs)
    assert first == second
    assert len(store.observations(patch="26.23", metric="win")) == 1


def test_rejected_batch_writes_nothing(store):
    good = Observation(scope="champion", metric="win", champion_id="ahri", wins=5, n=10)
    bad = Observation(scope="champion", metric="win", champion_id="lux", wins=5, n=0)
    with pytest.raises(ProvenanceError):
        store.ingest(_source(), _snapshot(), [good, bad])
    assert store.observations(patch="26.23") == []
    count = store.connection.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0]
    assert count == 0


def test_low_sample_flag_is_kept(store):
    store.ingest(
        _source(), _snapshot(),
        [Observation(scope="champ_aug", metric="win", champion_id="ahri",
                     augment_id="1001", wins=2, n=3, low_sample=True)],
    )
    (row,) = store.observations(patch="26.23")
    assert row.low_sample is True


def test_unmapped_names_go_to_quarantine(store):
    snap_id = store.ingest(
        _source(), _snapshot(), [],
        quarantine=[("Unknown Augment Name", "no catalog match")],
    )
    rows = store.connection.execute(
        "SELECT snapshot_id, raw_name, reason FROM quarantine"
    ).fetchall()
    assert rows == [(snap_id, "Unknown Augment Name", "no catalog match")]


def test_non_commercial_source_is_flagged(store):
    store.ingest(_source(name="nc", license="CC-BY-NC-4.0", commercial_ok=False),
                 _snapshot(sha="b" * 64), [])
    assert store.sources(commercial_only=True) == []
    assert [s.name for s in store.sources()] == ["nc"]


def test_foreign_keys_enforced(store):
    with pytest.raises(sqlite3.IntegrityError):
        store.connection.execute(
            "INSERT INTO observation (snapshot_id, scope, metric, n) VALUES (999, 'champion', 'win', 1)"
        )
