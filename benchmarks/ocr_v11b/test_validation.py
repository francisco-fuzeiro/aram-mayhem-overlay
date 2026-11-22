"""V1.1b test-first safety gates; deliberately RED until audit module exists."""
import hashlib
import json
import pytest
from benchmarks.ocr_v11b.validation import (
    validate_manifest, classify_evidence, decision_counts, benchmark_stats,
)
ORIGINALS = {"a"*64}
def sample(**kw):
    row = {"id":"offer-001-left","kind":"independent","sha256":"b"*64,
           "source_session":"new-session-001","expected":"Donation",
           "category":"title","slot":"left","privacy_approved":True,
           "file":"approved/crop.png"}
    row.update(kw)
    return row

def test_new_holdout_requires_real_independence_and_approval():
    r=validate_manifest({"samples":[sample()]},ORIGINALS)
    assert r["independent"]==1 and r["derived"]==0

@pytest.mark.parametrize("override",[
    {"sha256":"a"*64},
    {"kind":"derived","parent_sha256":"a"*64},
    {"kind":"synthetic"},
    {"privacy_approved":False},
    {"source_session":""},
    {"file":"../private.png"},
    {"id":"offer-001-left","sha256":"not-a-sha"},
])
def test_nonindependent_or_unapproved_rejected_for_holdout(override):
    with pytest.raises(ValueError):
        validate_manifest({"samples":[sample(**override)]},ORIGINALS,require_independent=True)

def test_duplicate_image_across_sessions_is_not_independent():
    with pytest.raises(ValueError,match="duplicate"):
        validate_manifest({"samples":[sample(),sample(id="offer-002-left",source_session="another")]},ORIGINALS)

def test_empty_holdout_explicitly_blocked():
    assert validate_manifest({"samples":[]},ORIGINALS)["holdout_status"]=="BLOCKED"

def test_wrong_identity_never_hidden_by_acceptance_count():
    records=[classify_evidence("Donation","Goliath","title","left"),
             classify_evidence("Donation",None,"title","centre"),
             classify_evidence(None,"Donation","dialog","right"),
             classify_evidence(None,None,"no_offer","left")]
    c=decision_counts(records)
    assert (c["wrong_id"],c["false_positive"],c["false_rejection"],c["correct_rejection"])==(1,1,1,1)
    assert c["safety_pass"] is False

def test_correct_does_not_mask_negative_false_positive():
    c=decision_counts([classify_evidence("Donation","Donation","title","left"),
                       classify_evidence(None,"Donation","no_offer","right")])
    assert c["wrong_id"]==0 and c["false_positive"]==1 and c["safety_pass"] is False

def test_percentiles_from_real_samples_not_guessed():
    got=benchmark_stats([10,20,30,40,50])
    assert got["mean_ms"]==30 and got["p50_ms"]==30 and got["p95_ms"]==50 and got["max_ms"]==50

def test_synthetic_is_separate_not_independent():
    r=validate_manifest({"samples":[sample(kind="synthetic",file="synth.png")]},ORIGINALS)
    assert r["synthetic"]==1 and r["independent"]==0 and r["holdout_status"]=="BLOCKED"
