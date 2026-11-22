"""Test-first V1.1c local-only labeling and reporting contracts."""
import csv
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from benchmarks.ocr_v11c.manifest import prepare_manifests
from benchmarks.ocr_v11c.render_report import build_report


def fixture(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    img = root / "slot.png"
    Image.new("RGB", (12, 5), (125, 85, 42)).save(img)
    labels = root / "human_labels.csv"
    row = dict(file="slot.png", source_session="sessionA", source_frame="frame1",
               offer_id="offer1", slot="left", category="title",
               expected="Donation", rarity="Silver", two_line="false",
               split="development", privacy_approved="yes")
    return root, labels, row, img


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_prepares_local_independent_manifest_and_sealed_holdout(tmp_path):
    root, csv_path, row, image = fixture(tmp_path)
    Image.new("RGB", (12, 5), (20, 30, 40)).save(root / "second.png")
    other = {**row, "file": "second.png", "source_session": "sessionB",
             "source_frame": "frame2", "offer_id": "offer2",
             "slot": "right", "split": "holdout"}
    write_csv(csv_path, [row, other])
    result = prepare_manifests(csv_path, root, set())
    assert len(result["development"]["samples"]) == 1
    assert len(result["holdout"]["samples"]) == 1
    sample = result["holdout"]["samples"][0]
    assert sample["kind"] == "independent"
    assert len(sample["sha256"]) == 64
    assert sample["expected"] == "Donation" and sample["rarity"] == "Silver"
    assert "source_frame" in sample
    assert result["holdout_seal"] == hashlib.sha256(
        json.dumps(result["holdout"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize("mutate", [
    {"privacy_approved": "no"},
    {"split": ""},
    {"source_session": ""},
    {"source_frame": ""},
    {"slot": "top"},
    {"category": "title", "expected": ""},
    {"category": "no_offer", "expected": "Donation"},
    {"two_line": "maybe"},
    {"file": "../secret.png"},
])
def test_rejects_unapproved_invalid_or_unlabeled_rows(tmp_path, mutate):
    root, csv_path, row, _ = fixture(tmp_path)
    write_csv(csv_path, [{**row, **mutate}])
    with pytest.raises(ValueError):
        prepare_manifests(csv_path, root, set())


def test_rejects_frozen_original_reuse(tmp_path):
    root, csv_path, row, image = fixture(tmp_path)
    write_csv(csv_path, [row])
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="frozen"):
        prepare_manifests(csv_path, root, {digest})


def test_rejects_duplicated_pixels_even_with_different_encoding(tmp_path):
    root, csv_path, row, image = fixture(tmp_path)
    Image.open(image).save(root / "copy.bmp")
    write_csv(csv_path, [row, {**row, "file": "copy.bmp",
                               "source_session": "sessionB", "source_frame": "frame2"}])
    with pytest.raises(ValueError, match="duplicate"):
        prepare_manifests(csv_path, root, set())


def test_rejects_session_leakage_across_splits(tmp_path):
    root, csv_path, row, _ = fixture(tmp_path)
    Image.new("RGB", (12, 5), (20, 30, 40)).save(root / "second.png")
    write_csv(csv_path, [row, {**row, "file": "second.png",
                               "source_frame": "frame2", "split": "holdout"}])
    with pytest.raises(ValueError, match="session"):
        prepare_manifests(csv_path, root, set())


def test_rejects_same_frame_and_slot_even_with_new_pixels(tmp_path):
    root, csv_path, row, _ = fixture(tmp_path)
    Image.new("RGB", (12, 5), (20, 30, 40)).save(root / "second.png")
    write_csv(csv_path, [row, {**row, "file": "second.png"}])
    with pytest.raises(ValueError, match="frame"):
        prepare_manifests(csv_path, root, set())


def test_report_has_no_native_pass_without_user_evidence():
    payload = {"platform": "Windows-Actions-2022", "runs": {
        "ppocrv4_split": {
            "crop_total_ms": {"n": 26, "mean_ms": 50, "p50_ms": 40, "p95_ms": 70, "max_ms": 90},
            "three_consecutive_crops_ms": {"mean_ms": 210, "p50_ms": 200, "p95_ms": 240, "max_ms": 260},
            "counts": {"correct": 19, "correct_rejection": 7, "wrong_id": 0,
                       "false_positive": 0, "false_rejection": 0},
            "cold_ready_wall_ms": 390, "model_session_load_ms": 115,
            "sampled_process_tree_cpu_seconds": 2.3,
            "sampled_peak_process_tree_rss_bytes": 85 * 1048576,
            "observed_distinct_pids": 1, "model_bytes": {"ppocrv4.onnx": 10857958},
            "distributions": {"onnxruntime": {"version": "1.20.1",
                                             "installed_file_bytes": 12345}}
        }}}
    text = build_report(payload, device_origin="CI_RUNNER")
    assert "NOT A USER-PC VALIDATION" in text
    assert "50" in text and "70" in text
    assert "0 wrong IDs" in text
    assert "BLOCKED" in text
    assert "85.0" in text


def test_three_card_offers_require_same_session_frame_and_exact_slots():
    from benchmarks.ocr_v11c.grouping import group_offers
    def row(frame, slot, status="correct"):
        return {"source_session": "sessionA", "source_frame": frame,
                "offer_id": "offer1", "slot": slot, "status": status}
    rows = [row("frame1", s) for s in ("left", "centre", "right")]
    rows.append(row("frame2", "left", "false_rejection"))  # unilateral reroll
    got = group_offers(rows)
    assert got == {"complete": 1, "all_correct": 1, "incomplete": 1}
    # Never combine left from one frame with centre/right from another.
    got = group_offers([row("frame1", "left"), row("frame2", "centre"),
                        row("frame2", "right")])
    assert got == {"complete": 0, "all_correct": 0, "incomplete": 2}


def test_three_card_duplicate_slot_is_not_silently_overwritten():
    from benchmarks.ocr_v11c.grouping import group_offers
    row = {"source_session": "A", "source_frame": "F", "offer_id": "O",
           "slot": "left", "status": "correct"}
    with pytest.raises(ValueError, match="duplicate"):
        group_offers([row, row.copy()])


def test_unframed_legacy_samples_cannot_claim_complete_three_card_offers():
    from benchmarks.ocr_v11c.grouping import group_offers
    rows = [{"source_session": "A", "offer_id": "O", "slot": s,
             "status": "correct"} for s in ("left", "centre", "right")]
    assert group_offers(rows)["complete"] == 0


def test_sealed_holdout_detects_tampering_and_requires_explicit_unlock(tmp_path):
    from benchmarks.ocr_v11c.evaluate_local import validate_sealed_holdout
    manifest = tmp_path / "holdout.manifest.json"
    seal = tmp_path / "holdout.sha256"
    data = {"samples": [{"id": "new-image"}]}
    manifest.write_text(json.dumps(data), encoding="utf-8")
    expected = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    seal.write_text(expected + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="explicit"):
        validate_sealed_holdout(manifest, seal, unlock=False)
    assert validate_sealed_holdout(manifest, seal, unlock=True) == 1
    manifest.write_text(json.dumps({"samples": [{"id": "changed"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="seal"):
        validate_sealed_holdout(manifest, seal, unlock=True)


def test_private_capture_or_result_paths_inside_checkout_are_rejected(tmp_path):
    from benchmarks.ocr_v11c.evaluate_local import assert_private_paths
    repo = tmp_path / "public-checkout"
    repo.mkdir()
    private = tmp_path / "private"
    private.mkdir()
    assert_private_paths(repo, [private, private / "report.json"])
    with pytest.raises(ValueError, match="outside"):
        assert_private_paths(repo, [repo / "manifest.json"])


def test_adaptive_v4_has_its_own_profile_and_holdout_comparison():
    """Do not assign fixed-width v4 CPU/RSS to wider adaptive tensors."""
    from benchmarks.ocr_v11b.profile_windows import ENGINES
    assert "ppocrv4_split" in ENGINES
    assert "ppocrv4_adaptive_split" in ENGINES
    assert len(ENGINES) == 5
    from benchmarks.ocr_v11c.configurations import adaptive_v4
    class Session:
        height = 48
        width = 448
    variant = adaptive_v4(Session())
    assert variant.color == "bgr"
    assert variant.resize == "cv2"
    assert variant.rounding == "ceil"
    assert variant.dynamic_width is True
