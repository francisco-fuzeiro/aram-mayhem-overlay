"""V1.1b real-model controlled experiment on the ORIGINAL frozen 26 only.

No live League use, no runtime/OCR changes, and NO independent holdout claim.
CI outputs contain limited archived public fixture identifiers and OCR titles,
not new captures or local machine paths.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from benchmarks.ocr_v11.runner import (
    DirectONNX, RapidV4, REFERENCE_SHA, V4_SHA, V5_SHA, canon, diagnostics,
    read_cases, run_ocr, stats,
)
from benchmarks.ocr_v11b.controlled import AblationRecognizer, CONFIGS, prepare_input
from benchmarks.ocr_v11b.validation import classify_evidence,decision_counts,validate_manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reference",type=Path,required=True)
    parser.add_argument("--models",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--holdout-manifest",type=Path,default=None,
                        help="Optional approved LOCAL metadata; never submitted to CI")
    a=parser.parse_args()
    ref=a.reference.resolve()
    head=subprocess.check_output(["git","-C",str(ref),"rev-parse","HEAD"],
                                 text=True).strip()
    if head!=REFERENCE_SHA:
        raise ValueError("reference SHA mismatch")
    sys.path.insert(0,str(ref))
    from backend.collectors.slot_title_ocr import strict_match_title,_normalize
    cases,catalog=read_cases(ref)
    original_hashes={c["sha256"] for c in cases}
    if a.holdout_manifest:
        manifest=json.loads(a.holdout_manifest.read_text(encoding="utf8"))
        gate=validate_manifest(manifest,original_hashes)
        # No holdout pixel data are processed or written in this command.
    else:
        gate=validate_manifest({"samples":[]},original_hashes)
    v4=DirectONNX(a.models/"ppocrv4.onnx","v4",a.models/"ppocr_keys_v1.txt")
    v5=DirectONNX(a.models/"ppocrv5_en.onnx","v5")
    rapid=RapidV4(a.models/"ppocrv4.onnx",a.models/"ppocr_keys_v1.txt")
    engines={}
    for name,(version,color,resize,rounding,dynamic_width) in CONFIGS.items():
        engines[name]=AblationRecognizer(v4 if version=="v4" else v5,
                                         color=color,resize=resize,
                                         rounding=rounding,dynamic_width=dynamic_width)
    engines["rapidocr_v4"]=rapid
    from PIL import Image
    base=ref/"tests"/"fixtures"/"ocr_titles"
    warm=Image.open(base/cases[0]["file"]).convert("RGB")
    for engine in engines.values():
        for _ in range(2):
            run_ocr(engine,warm,strict_match_title,catalog)
    # Verify actual pinned RapidOCR 1.4.4 input tensors against a direct
    # BGR / cv2 / ceil / dynamically widened reproduction, not assumptions.
    import math
    import numpy as np
    from benchmarks.ocr_v11.runner import split_lines
    rapid_input_parity={"checked":0,"exact":0,"max_abs_difference":0.0,
                        "wider_than_fixed_448":0}
    for case in cases:
        with Image.open(base/case["file"]) as opened:
            chunks=split_lines(opened.convert("RGB"))
        for chunk in chunks:
            bgr=np.asarray(chunk.convert("RGB"))[:,:,::-1].copy()
            img_height=rapid.engine.rec_image_shape[1]
            img_width=rapid.engine.rec_image_shape[2]
            max_wh_ratio=max(img_width/img_height,chunk.width/chunk.height)
            rapid_tensor=rapid.engine.resize_norm_img(bgr,max_wh_ratio)
            expected_width=rapid_tensor.shape[2]
            custom=prepare_input(chunk,height=img_height,width=expected_width,
                                 color="bgr",resize="cv2",rounding="ceil")[0]
            difference=float(np.max(np.abs(rapid_tensor-custom)))
            rapid_input_parity["checked"]+=1
            rapid_input_parity["exact"]+=int(np.array_equal(rapid_tensor,custom))
            rapid_input_parity["max_abs_difference"]=max(
                rapid_input_parity["max_abs_difference"],difference)
            rapid_input_parity["wider_than_fixed_448"]+=int(expected_width>img_width)
    rows=[]
    group=defaultdict(list)
    for c in cases:
        with Image.open(base/c["file"]) as original:
            img=original.convert("RGB")
        for name,engine in engines.items():
            start=time.perf_counter()
            raw,match,pre,infer,match_ms=run_ocr(engine,img,strict_match_title,catalog)
            total_ms=1000*(time.perf_counter()-start)
            actual=match[1] if match else None
            d=classify_evidence(c["expected"],actual,c["category"],c["slot"] or "centre")
            norm=_normalize(raw)
            diag=diagnostics(raw,strict_match_title,catalog,_normalize)
            row={
                "file":c["file"],"kind":"original","sha256":c["sha256"],
                "engine":name,"slot":c["slot"],"two_line":c["two_line"],
                "rarity":c["rarity"],"category":c["category"],
                "expected":c["expected"],"raw":raw,"normalized":norm,
                "normalized_exact":bool(c["expected"] and norm==_normalize(c["expected"])),
                "raw_exact":bool(c["expected"] and canon(raw)==canon(c["expected"])),
                "best_score":diag["best_score"],"margin":diag["margin"],
                "match_score":match[2] if match else None,
                "actual":actual,"status":d["status"],
                "preprocess_ms":round(pre,3),"inference_ms":round(infer,3),
                "matching_ms":round(match_ms,3),"total_ms":round(total_ms,3),
            }
            rows.append(row)
            group[name].append(row)
    # Same 3 physical slots, original frozen 1440p event; artificial
    # consecutive batch, NOT a live/temporal detector measurement.
    three=["1440p/ocr_1795025241_"+s+".png" for s in ("left","centre","right")]
    checked=set(c["file"] for c in cases)
    if not set(three)<=checked:
        raise ValueError("3-crop sample missing from frozen dataset")
    triple={}
    for name,engine in engines.items():
        times=[]
        for _ in range(8):
            start=time.perf_counter()
            for filename in three:
                with Image.open(base/filename) as original:
                    run_ocr(engine,original.convert("RGB"),strict_match_title,catalog)
            times.append(1000*(time.perf_counter()-start))
        triple[name]=stats(times)
    summaries={}
    for name,rr in group.items():
        summary=decision_counts(rr)
        positives=[r for r in rr if r["category"]=="title"]
        summary.update({
            "original_images":len(rr),"original_positive":len(positives),
            "original_negatives":len(rr)-len(positives),
            "raw_exact":sum(r["raw_exact"] for r in positives),
            "normalized_exact":sum(r["normalized_exact"] for r in positives),
            "mean_crop_ms":stats([r["total_ms"] for r in rr]),
            "preprocess_ms":stats([r["preprocess_ms"] for r in rr]),
            "matching_ms":stats([r["matching_ms"] for r in rr]),
            "three_crop_ms":triple[name],
            "two_line_correct":sum(r["status"]=="correct" for r in positives if r["two_line"]),
            "two_line_total":sum(r["two_line"] for r in positives),
            "per_slot":{s:decision_counts([r for r in rr if r["slot"]==s])
                        for s in ("left","centre","right")},
        })
        summaries[name]=summary
    # An exact catalog title in an absent-offer dialog could pass the title
    # matcher alone: explicit synthetic policy probe, NEVER an independent image
    # nor an observed engine FP. Presence/capture gates remain mandatory.
    synthetic_match=strict_match_title("Donation",catalog)
    synthetic={
       "kind":"synthetic_matching_only","raw":"Donation",
       "context":"hypothetical dialog/no offer; no image, no OCR inference",
       "catalog_match":synthetic_match[1] if synthetic_match else None,
       "risk":"A title matcher alone cannot prove three-card offer visibility.",
    }
    info={
        "reference_sha":REFERENCE_SHA,"model_sha256":{"v4":V4_SHA,"v5_en":V5_SHA},
        "runtime":"isolated real ONNX CPU, single thread",
        "platform":platform.platform(),"python":sys.version.split()[0],
        "dataset":{"original":26,"derived":0,"synthetic_image":0,
                   "independent":0,"holdout":gate["holdout_status"]},
        "variants":{k:{"base_model":v[0],"channel":v[1],"interpolation":v[2],
                       "rounding":v[3],"dynamic_width":v[4],
                       "base_input_width":(v4 if v[0]=="v4" else v5).width}
                    for k,v in CONFIGS.items()},
        "rapidocr_v14_input_parity":rapid_input_parity,
        "model_load_ms":{"v4":v4.load_ms,"v5_en":v5.load_ms,"rapidocr":rapid.load_ms},
        "model_sizes_bytes":{"v4":(a.models/"ppocrv4.onnx").stat().st_size,
                             "v5_en":(a.models/"ppocrv5_en.onnx").stat().st_size},
    }
    report={"metadata":info,"summaries":summaries,"synthetic_guard_probe":synthetic,
            "rows":rows}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"v11b_results.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    lines=["# V1.1b preprocessing and ID-safety audit","",
           "Measured on the original 26 approved images only; **NOT independent holdout**.",
           "No private user screenshots. New independent holdout: **BLOCKED**.",
           "All comparisons use the pinned 90/8 strict matcher and exact model SHA256.",
           "",
           "| Candidate | Correct titles /19 | Negative rejects /7 | Wrong nonnull | False positives | False rejects | Raw exact /19 | Norm exact /19 | Mean crop ms | 3 crops mean ms |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name,s in summaries.items():
        lines.append(f"| {name} | {s['correct']}/19 | {s['correct_rejection']}/7 | {s['wrong_id']} | {s['false_positive']} | {s['false_rejection']} | {s['raw_exact']}/19 | {s['normalized_exact']}/19 | {s['mean_crop_ms']['mean_ms']} | {s['three_crop_ms']['mean_ms']} |")
    lines.extend(["","## Individual non-correct observations (including safe abstentions)",""])
    errs=[r for r in rows if r["status"] not in ("correct","correct_rejection")]
    if not errs:
        lines.append("None in original retrospective crops.")
    for r in errs:
        lines.append(f"- `{r['engine']}` `{r['file']}`: {r['status']} expected={r['expected']!r}; raw={r['raw']!r}; normalized={r['normalized']!r}; actual={r['actual']!r}; score={r['best_score']}; margin={r['margin']}")
    lines.extend(["","## Interpretation","",
                  "- RGB/BGR, PIL/OpenCV, round/ceil and adaptive width are deliberate controlled ablations, not new model architectures.",
                  f"- Pinned RapidOCR v1.4.4 preprocessor tensor parity versus direct BGR/cv2/ceil/adaptive: {rapid_input_parity['exact']}/{rapid_input_parity['checked']} bit-identical, max absolute delta {rapid_input_parity['max_abs_difference']:.8f}; {rapid_input_parity['wider_than_fixed_448']} required width >448.",
                  "- RapidOCR uses the same v4 model but may have additional internal resize, normalization and decoding differences; equal weights do not imply equal preprocessing.",
                  "- The English v5 model and its CTC dictionary stay pinned; a better original-set preprocessing variant would be a tuning hypothesis only.",
                  "- The synthetic matching-only probe demonstrates that title recognition alone is not an offer-presence proof; original no-offer results must not be extrapolated to arbitrary dialogs containing augment names.",
                  "- No calibration for unseen offers, rerolls, League/WGC, focus, DPI or user Windows PC is established.",
                  ""])
    (a.out/"V11B_AUDIT.md").write_text("\n".join(lines),encoding="utf8")
    print("V11B_RESEARCH_RESULT "+json.dumps({
        "original":26,"independent":0,"holdout":"BLOCKED",
        "summaries":{n:{k:s[k] for k in ("correct","correct_rejection","wrong_id",
                                        "false_positive","false_rejection")}
                     for n,s in summaries.items()},
        "error_rows":len(errs)}),flush=True)

if __name__=="__main__":
    main()
