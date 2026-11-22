"""Deterministic catalog-only OCR-text corruption study (NOT image evidence).

No model inference. Tests the frozen 90/8 title matcher against plausible
single-character errors; resulting errors are synthetic threat indicators,
not estimates of in-game false-ID probability.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys

from benchmarks.ocr_v11.runner import REFERENCE_SHA, read_cases
from benchmarks.ocr_v11b.validation import classify_evidence,decision_counts

def perturbations(title):
    """Deterministic OCR-like text noise; same title = same human truth."""
    s=title.strip()
    if len(s)<4:
        return
    middle=len(s)//2
    variations={
      "first_char_missing":s[1:],
      "last_char_missing":s[:-1],
      "middle_char_missing":s[:middle]+s[middle+1:],
      "middle_char_duplicate":s[:middle]+s[middle]+s[middle:],
      "adjacent_swap":s[:middle-1]+s[middle]+s[middle-1]+s[middle+1:],
      "spaces_removed":s.replace(" ",""),
      "punctuation_removed":re.sub(r"[^a-zA-Z0-9 ]","",s),
    }
    for name,altered in variations.items():
        if altered!=s:
            yield name,altered

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--reference",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    ref=a.reference.resolve()
    head=subprocess.check_output(["git","-C",str(ref),"rev-parse","HEAD"],
                                 text=True).strip()
    if head!=REFERENCE_SHA:
        raise ValueError("reference SHA mismatch")
    sys.path.insert(0,str(ref))
    from backend.collectors.slot_title_ocr import (
        strict_match_title,_normalize,MATCH_THRESHOLD,MIN_MARGIN,
    )
    from rapidfuzz import fuzz
    if (MATCH_THRESHOLD,MIN_MARGIN)!=(90,8):
        raise ValueError("matching policy altered")
    _,catalog=read_cases(ref)
    values=sorted(set(catalog.values()))
    report_rows=[]
    counts=defaultdict(Counter)
    exact_accepts=0
    for title in values:
        expected=strict_match_title(title,catalog)
        if expected is None:
            counts["exact_original"]["safe_rejection"]+=1
            continue
        exact_accepts+=1
        expected_id=expected[0]
        for kind,corrupted in perturbations(title):
            result=strict_match_title(corrupted,catalog)
            actual_id=result[0] if result else None
            status=("false_rejection" if actual_id is None
                    else "correct" if actual_id==expected_id else "wrong_id")
            counts[kind][status]+=1
            if status!="correct":
                report_rows.append({
                    "variant":kind,"synthetic_text":corrupted,
                    "human_expected_title":title,"expected_id":expected_id,
                    "actual_id":actual_id,"status":status,
                })
    candidate_pairs=[]
    for i,title in enumerate(values):
        for other in values[i+1:]:
            atext,btext=_normalize(title),_normalize(other)
            if atext==btext:
                continue
            ratio=float(fuzz.ratio(atext,btext))
            if ratio>=88:
                candidate_pairs.append({"a":title,"b":other,"ratio":round(ratio,3)})
    candidate_pairs.sort(key=lambda row:-row["ratio"])
    probe=strict_match_title("Donation",catalog)
    summary={
        "source":"synthetic text only, NOT images or independent offers",
        "reference_sha":head,"catalog_titles":len(values),
        "exact_original_titles_accepted":exact_accepts,
        "matcher_policy":{"threshold":MATCH_THRESHOLD,"margin":MIN_MARGIN},
        "variants":{key:dict(value) for key,value in counts.items()},
        "wrong_accepted_examples":[r for r in report_rows if r["status"]=="wrong_id"][:100],
        "safe_rejection_examples":[r for r in report_rows if r["status"]=="false_rejection"][:50],
        "accepted_wrong_total":sum(1 for r in report_rows if r["status"]=="wrong_id"),
        "safe_rejection_total":sum(1 for r in report_rows if r["status"]=="false_rejection"),
        "close_title_pairs_top25":candidate_pairs[:25],
        "presence_gate_adversarial_probe":{
            "context":"hypothetical absent-offer dialog with exact catalog title",
            "observed_text":"Donation","matcher_accepts":bool(probe),
            "must_be_blocked_by_separate_offer_presence_gate":True,
        },
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf8")
    print("SYNTHETIC_MATCHING_STRESS "+json.dumps({
        "titles":len(values),"accepted_exact":exact_accepts,
        "wrong_accepted":summary["accepted_wrong_total"],
        "safe_rejections":summary["safe_rejection_total"],
        "close_pairs":len(candidate_pairs)}),flush=True)

if __name__=="__main__":
    main()
