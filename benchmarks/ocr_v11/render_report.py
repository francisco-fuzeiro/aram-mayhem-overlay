"""Render reproducible measurement notes from real benchmark JSON only.

This report is an Actions artifact, not a source of simulated predictions.
No images, user paths or game telemetry are written here.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

def run(source: Path):
    data=json.loads((source/"summary.json").read_text(encoding="utf-8"))
    rows=json.loads((source/"cases.json").read_text(encoding="utf-8"))
    m=data["metadata"]
    names=sorted({r["engine"] for r in rows})
    original=[r for r in rows if not r["derived"]]
    if len(original)!=26*len(names):
        raise AssertionError("Not all base PNG model observations are present")
    if len(rows)!=208*len(names):
        raise AssertionError("Transformed evidence incomplete")
    out=[
        "# ARAM Oracle V1.1 — Measured OCR comparison",
        "",
        "Generated from real frozen-asset inference. This is not a historical estimate.",
        f"**Source snapshot:** `{m['reference_sha']}`",
        f"**CPU/OS:** {m['cpu']}, {m['cpu_logical_count']} logical cores, {m['platform']}",
        f"**Python/Tesseract:** {m['python']} / {m['tesseract']}",
        f"**ONNX:** {m['dependencies']['onnxruntime']}; CPUExecutionProvider, one thread",
        f"**Models:** v4 `{m['model_sha256']['v4']}`, v5 English `{m['model_sha256']['v5_en']}`",
        f"**Verified original fixtures:** {m['cases']} from a fixed 26-image set; 328 catalog names",
        "",
        "## Original 100% PNGs — decision-level accuracy",
        "",
        "| Engine | Titles correct/19 | Accepted wrong | Negative rejected/7 | False positive | False rejection | Raw exact/19 | Mean ms | P95 ms | Max ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for record in data["summaries"]:
        if record["scale"]==1 and record["format"]=="PNG":
            t=record["timing_ms"]
            out.append(f"| {record['engine']} | {record['correct_titles']}/19 | {record['wrong_nonnull']} | {record['correct_negative_rejections']}/7 | {record['false_positives']} | {record['false_rejections']} | {record['raw_exact']}/19 | {t['mean_ms']:.2f} | {t['p95_ms']:.2f} | {t['max_ms']:.2f} |")
    out+=["", "## Derived transformations (not independent samples)", "",
          "| Engine | Scale | Compression | Correct titles/19 | Wrong accepted | Negative rejection/7 | FP | Abstained title | Raw exact/19 | Mean ms | P95 ms |",
          "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for rec in data["summaries"]:
        t=rec["timing_ms"]
        out.append(f"| {rec['engine']} | {rec['scale']:.2f} | {rec['format']} | {rec['correct_titles']} | {rec['wrong_nonnull']} | {rec['correct_negative_rejections']} | {rec['false_positives']} | {rec['false_rejections']} | {rec['raw_exact']} | {t['mean_ms']:.2f} | {t['p95_ms']:.2f} |")
    out+=["","## Installed Python distribution sizes (isolated Linux executor)","",
          "| Distribution | Installed files MiB | Pinned version |",
          "|---|---:|---|"]
    for pkg,byte_count in sorted(m.get("installed_distribution_bytes",{}).items()):
        out.append(f"| {pkg} | {byte_count / 1048576:.2f} | {m['dependencies'][pkg]} |")
    out+=["","These distribution sizes include vendor code/models and possible shared dependencies; they are **not** incremental packaged executable sizes or Windows installation measurements.",""]
    out+=["","## Position and two-line comparisons (original only)","",
          "| Engine | Slot | Titles correct / titles | Negatives rejected / negatives | Wrong IDs |",
          "|---|---|---:|---:|---:|"]
    for name in names:
        rr=[r for r in original if r["engine"]==name]
        for slot in ("left","centre","right","unassigned_snip"):
            rs=[r for r in rr if (r["slot"] or "unassigned_snip")==slot]
            pos=[r for r in rs if r["category"]=="title"]
            neg=[r for r in rs if r["category"]!="title"]
            out.append(f"| {name} | {slot} | {sum(r['status']=='correct' for r in pos)}/{len(pos)} | {sum(r['status']=='correct_rejection' for r in neg)}/{len(neg)} | {sum(r['status']=='wrong_id' for r in rs)} |")
    out+=["","## Two-line original titles", "",
          "| Engine | Correct / 2 | Wrong ID | Rejection |",
          "|---|---:|---:|---:|"]
    for name in names:
        rr=[r for r in original if r["engine"]==name and r["two_line"]]
        out.append(f"| {name} | {sum(r['status']=='correct' for r in rr)}/{len(rr)} | {sum(r['status']=='wrong_id' for r in rr)} | {sum(r['status']=='false_rejection' for r in rr)} |")
    out+=["","## Resource usage and three consecutive crops","","| Engine | Model load ms | 3-crop mean ms | 3-crop p95 ms | 3-crop max ms | CPU time s | CPU share of one core % | RSS after run MiB |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in names:
        z=m["three_crops_ms"][name]
        rs=m["resources"][name]
        load=m["model_load_ms"].get({"ppocrv4_historical_split":"ppocrv4","ppocrv4_historical_full":"ppocrv4","ppocrv4_split":"ppocrv4","ppocrv4_full":"ppocrv4","ppocrv5_en_split":"ppocrv5_en","rapidocr_v4_split":"rapidocr_v4"}.get(name,name))
        out.append(f"| {name} | {load if load is not None else 'N/A'} | {z['mean_ms']} | {z['p95_ms']} | {z['max_ms']} | {rs['cpu_time_s']} | {rs['cpu_percent_one_core']} | {rs['rss_after_bytes']/1048576:.1f} |")
    out+=["","Resources use one shared Python process with all models loaded, so RSS is NOT isolated per-engine incremental memory or an installed Windows footprint. Cold model load is measured once, not a cold-start distribution. 3-crop batches are artificial consecutive fixture calls, not real offers.", "",
          "## Matching, raw recognition and safety diagnostics", ""]
    for name in names:
        pos=[r for r in original if r["engine"]==name and r["category"]=="title"]
        rescued=[r for r in pos if not r["raw_exact"] and r["status"]=="correct"]
        harmed=[r for r in pos if r["raw_exact"] and r["status"]!="correct"]
        norm_fixed=[r for r in rescued if r["best_score"]==100]
        fuzz_fixed=[r for r in rescued if r["best_score"]<100]
        out.append(f"- **{name}:** {len(norm_fixed)} raw mismatches recovered by normalization; {len(fuzz_fixed)} by fuzzy matching below 100; {len(harmed)} exact raw titles rejected or wrongly identified.")
        for r in rescued+harmed:
            out.append(f"  - `{r['file']}`: expected={r['expected']!r}, raw={r['raw']!r}, chosen={r['actual']!r}, score={r['best_score']}, margin={r['margin']}")
    out+=["","## Individual errors — all original images", ""]
    bad=[r for r in original if r["status"] not in ("correct","correct_rejection")]
    if not bad:out.append("No accepted wrong IDs, false positives or false rejections on the original 26 images.")
    for r in bad:
        out.append(f"- {r['engine']} `{r['file']}`: {r['status']} expected={r['expected']!r} raw={r['raw']!r} actual={r['actual']!r} score={r['best_score']} margin={r['margin']}")
    out+=["","## Individual errors — derived transformations", ""]
    bad=[r for r in rows if r["derived"] and r["status"] not in ("correct","correct_rejection")]
    out.append(f"Total transformed-case errors over all engines/conditions: **{len(bad)}**. These are correlated transformations of the same source crops.")
    for r in bad:
        out.append(f"- {r['engine']} `{r['file']}` scale={r['scale']} {r['format']}: {r['status']}; expected={r['expected']!r}; raw={r['raw']!r}; actual={r['actual']!r}; score={r['best_score']}; margin={r['margin']}")
    out+=["","## Paired divergences on original images", ""]
    keyed=defaultdict(dict)
    for r in original: keyed[r["file"]][r["engine"]]=r
    count=0
    for file,engines in sorted(keyed.items()):
        accepted={e:r["actual"] for e,r in engines.items()}
        if len(set(accepted.values()))>1:
            count+=1
            out.append(f"- `{file}` expected={next(iter(engines.values()))['expected']!r}: "+", ".join(f"{e}={v!r}" for e,v in sorted(accepted.items())))
    if count==0:out.append("No divergence among accepted matched IDs on original images.")
    out+=["","## Scope limitations", "",
          "- 26 retrospective, non-independent images; original data contain repeated titles, two dialogs and five no-offer negatives; no Silver offer, full new triple, live reroll, or native Windows in-game evidence.",
          "- The v5 English model has been evaluated with the benchmark's RGB resize / [-1,1] / CTC preprocessing and the same line splitter; do not infer all possible v5 production configurations from these measurements.",
          "- No result changes the production Tesseract, current 90/8 matcher, capture or game state.",
          "- Validate CPU/RSS/first-6-second behavior on the actual Windows/League/OP.GG device before contemplating promotion.",
    ]
    dest=source/"MEASURED_REPORT.md"
    dest.write_text("\n".join(out)+"\n",encoding="utf8")
    print(f"REPORT_WRITTEN {dest} original_errors={sum(r['status'] not in ('correct','correct_rejection') for r in original)} derived_errors={len(bad)}",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True)
    run(ap.parse_args().input)
