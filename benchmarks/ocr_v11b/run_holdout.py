"""Local-only independent holdout validation and actual pinned OCR comparison.

Do not upload approved holdout files, manifests, raw OCR output or local logs.
Runs only after explicit privacy approval and original SHA256 verification.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from benchmarks.ocr_v11.runner import (
    REFERENCE_SHA, DirectONNX, RapidV4, read_cases, run_ocr, tesseract_ocr,
    canon, stats,
)
from benchmarks.ocr_v11b.validation import (
    classify_evidence,decision_counts,validate_manifest,
)

def main():
    ap=argparse.ArgumentParser(description="Offline PRIVATE holdout: never upload outputs")
    ap.add_argument("--reference",required=True,type=Path)
    ap.add_argument("--models",required=True,type=Path)
    ap.add_argument("--manifest",required=True,type=Path)
    ap.add_argument("--holdout-root",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    ref=a.reference.resolve()
    if subprocess.check_output(["git","-C",str(ref),"rev-parse","HEAD"],text=True).strip()!=REFERENCE_SHA:
        raise ValueError("pinned reference mismatch")
    sys.path.insert(0,str(ref))
    from backend.collectors.slot_title_ocr import strict_match_title,_normalize
    from backend.collectors import screen_ocr
    from benchmarks.ocr_v11.runner import ASSETS
    cases,catalog=read_cases(ref)
    manifest=json.loads(a.manifest.read_text(encoding="utf8"))
    gate=validate_manifest(manifest,{c["sha256"] for c in cases},require_independent=True)
    if gate["holdout_status"]!="READY_FOR_REVIEW":
        raise ValueError("no approved independent holdout; BLOCKED")
    root=a.holdout_root.resolve()
    samples=manifest["samples"]
    # Check ALL actual bytes before creating sessions / producing any inference.
    for item in samples:
        p=(root/item["file"]).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            raise ValueError("missing/outside holdout crop")
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest!=item["sha256"]:
            raise ValueError("holdout SHA256 mismatch")
        if item["category"]=="title" and item["expected"] not in catalog.values():
            raise ValueError("human ground truth absent from frozen catalog")
    v4=DirectONNX(a.models/"ppocrv4.onnx","v4",a.models/"ppocr_keys_v1.txt")
    v5=DirectONNX(a.models/"ppocrv5_en.onnx","v5")
    rapid=RapidV4(a.models/"ppocrv4.onnx",a.models/"ppocr_keys_v1.txt")
    engines={"tesseract":None,"ppocrv4_split":v4,
             "rapidocr_v4_split":rapid,"ppocrv5_en_split":v5}
    from PIL import Image
    results=defaultdict(list)
    by_offer=defaultdict(lambda:defaultdict(dict))
    for idx,item in enumerate(samples):
        p=(root/item["file"]).resolve()
        with Image.open(p) as image:
            img=image.convert("RGB")
        for name,engine in engines.items():
            start=time.perf_counter()
            if engine is None:
                raw,match,pre,infer,matching=tesseract_ocr(
                    img,strict_match_title,catalog,screen_ocr)
            else:
                raw,match,pre,infer,matching=run_ocr(
                    engine,img,strict_match_title,catalog)
            elapsed=1000*(time.perf_counter()-start)
            actual=match[1] if match else None
            evidence=classify_evidence(item["expected"],actual,
                                       item["category"],item["slot"])
            evidence.update({"sample_index":idx,"two_line":bool(item.get("two_line")),
                             "rare_group":item.get("rarity"),
                             "raw_exact":bool(item["expected"] and
                                              canon(raw)==canon(item["expected"])),
                             "normalized_exact":bool(item["expected"] and
                                              _normalize(raw)==_normalize(item["expected"])),
                             "total_ms":round(elapsed,3),
                             "preprocess_ms":round(pre,3),
                             "inference_ms":round(infer,3),
                             "matching_ms":round(matching,3)})
            results[name].append(evidence)
            # A full offer is counted only for 3 distinct physically labeled slots.
            if item.get("offer_id") and item.get("source_session"):
                key=(item["source_session"],str(item["offer_id"]))
                by_offer[name][key][item["slot"]]=evidence["status"]
    summary={}
    for name,rows in results.items():
        complete=[states for states in by_offer[name].values()
                  if set(states)=={"left","centre","right"}]
        summary[name]={
            "counts":decision_counts(rows),
            "raw_exact":sum(r["raw_exact"] for r in rows),
            "normalized_exact":sum(r["normalized_exact"] for r in rows),
            "latency_ms":stats([r["total_ms"] for r in rows]),
            "per_slot":{slot:decision_counts([r for r in rows if r["slot"]==slot])
                        for slot in ("left","centre","right")},
            "two_line":decision_counts([r for r in rows if r["two_line"]]),
            "full_three_slot_offers":len(complete),
            "all_three_correct":sum(all(s=="correct" for s in x.values()) for x in complete),
            # Local-only sample indexes preserve auditability without file paths.
            "errors":[{"sample_index":r["sample_index"],"status":r["status"],
                       "slot":r["slot"],"expected":r["expected"],"actual":r["actual"]}
                      for r in rows if r["status"] not in ("correct","correct_rejection")],
        }
    report={
      "visibility":"LOCAL_ONLY_DO_NOT_UPLOAD_WITHOUT_REVIEW",
      "dataset":"user-approved SHA256-verified unseen independent holdout",
      "independent_samples":len(samples),"original_samples":0,"derived_samples":0,
      "synthetic_samples":0,
      "source_reference_sha":REFERENCE_SHA,
      "safety_priority":"wrong nonnull or negative false positive prevents candidate promotion",
      "summary":summary,
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
    print("HOLDOUT_EVALUATED_LOCALLY "+json.dumps({
        "independent":len(samples),
        "counts":{name:s["counts"] for name,s in summary.items()}}),flush=True)

if __name__=="__main__":
    main()
