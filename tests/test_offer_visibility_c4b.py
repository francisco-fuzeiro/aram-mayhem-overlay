"""M5/C4b RED: independent, calibration-gated negative evidence.

All cases are synthetic. No screenshot or assumed League UI anchor is supplied.
The production gate must remain disabled until real, reviewed negative fixtures
establish an independent visual marker.
"""
from backend.collectors.offer_visibility import IndependentCue, VerifiedAbsenceGate


KEY = (7, (8, 31, 2552, 1384))
OTHER = (8, (-1200, 0, 0, 900))


def cue(verdict="absent", calibration="fixture-only", key=KEY):
    return IndependentCue(verdict=verdict, calibration_id=calibration, key=key)


def test_default_negative_gate_cannot_claim_absence_without_calibration():
    gate = VerifiedAbsenceGate()
    gate.confirm_present(KEY)
    assert all(not gate.observe(cue(), KEY) for _ in range(8))


def test_absence_requires_three_consecutive_independent_calibrated_reads():
    gate = VerifiedAbsenceGate(approved_calibration="fixture-only")
    assert not gate.observe(cue(), KEY)  # Must first see a true offer
    gate.confirm_present(KEY)
    assert not gate.observe(cue(), KEY)
    assert not gate.observe(cue(), KEY)
    assert gate.observe(cue(), KEY)


def test_dialogue_and_animation_reset_negative_streak():
    gate = VerifiedAbsenceGate(approved_calibration="fixture-only")
    gate.confirm_present(KEY)
    assert not gate.observe(cue(), KEY)
    assert not gate.observe(cue("occluded"), KEY)
    assert not gate.observe(cue(), KEY)
    assert not gate.observe(cue(), KEY)
    assert gate.observe(cue(), KEY)


def test_mismatched_calibration_and_window_cannot_confirm():
    gate = VerifiedAbsenceGate(approved_calibration="fixture-only")
    gate.confirm_present(KEY)
    assert not gate.observe(cue(calibration="unreviewed"), KEY)
    assert not gate.observe(cue(key=OTHER), KEY)
    assert not gate.observe(cue(), OTHER)
    assert not gate.observe(cue(), KEY)  # Now requires fresh offer proof


def test_focus_loss_revokes_old_offer_presence():
    gate = VerifiedAbsenceGate(approved_calibration="fixture-only")
    gate.confirm_present(KEY)
    assert not gate.observe(cue(), KEY)
    gate.suspend()
    assert all(not gate.observe(cue(), KEY) for _ in range(8))


def test_positive_offer_cancels_absence_candidate():
    gate = VerifiedAbsenceGate(approved_calibration="fixture-only")
    gate.confirm_present(KEY)
    assert not gate.observe(cue(), KEY)
    assert not gate.observe(cue(), KEY)
    gate.confirm_present(KEY)
    assert not gate.observe(cue(), KEY)
    assert not gate.observe(cue(), KEY)
    assert gate.observe(cue(), KEY)


def test_no_untrusted_or_unrecognized_negative_signals():
    gate = VerifiedAbsenceGate(approved_calibration="fixture-only")
    gate.confirm_present(KEY)
    for item in (None, "absent", cue("unknown"), cue("visible"), cue("dialogue")):
        assert not gate.observe(item, KEY)
