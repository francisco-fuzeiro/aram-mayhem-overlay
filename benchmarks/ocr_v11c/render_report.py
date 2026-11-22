"""Human-readable, local-only report for V1.1b/V1.1c isolated OCR metrics.

This is not a native League acceptance certificate. Never upload local
reports or manifests without an explicit privacy review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MIB = 1048576
SELECTED = {
    "v4_rgb_pil": "PP-OCRv4 direct fixed",
    "v4_bgr_cv2_ceil_dynamic": "PP-OCRv4 direct adaptive",
    "rapidocr_v4": "RapidOCR v4 (same weights)",
    "v5_rgb_pil": "PP-OCRv5 English tested",
}


def _value(stats, key):
    if not isinstance(stats, dict):
        return "N/A"
    value = stats.get(key)
    return str(round(value, 2)) if isinstance(value, (float, int)) else "N/A"


def _mb(value):
    return f"{value / MIB:.2f}" if isinstance(value, (int, float)) else "N/A"


def build_report(profile: dict, *, device_origin: str,
                 controlled: dict | None = None) -> str:
    if device_origin not in ("CI_RUNNER", "LOCAL_USER_EXECUTION_UNATTESTED"):
        raise ValueError("untrusted provenance classification")
    lines = [
        "# ARAM Oracle — OCR V1.1c local benchmark report",
        "",
        f"**Origin:** {device_origin}.",
        "**Never automatically classify this as in-game League/OP.GG acceptance.**",
        "**NOT A USER-PC VALIDATION** if this was executed in CI.",
        "**Independent gameplay holdout: BLOCKED** until new human-labeled images are approved.",
        "**V1.2 integration: NO-GO; Tesseract stays in production.**",
        "",
        "## Isolated-process timing and safety",
        "",
        "Timing is milliseconds; CPU is sampled process-tree time in seconds,",
        "RSS is sampled peak process-tree MiB (shared mappings may be double counted).",
        "Cold-ready includes process launch, imports, fixture checks and model setup.",
        "",
        "| Engine | Correct titles | Safe negatives | Wrong accepted | False-positive negatives | Safe title rejects | Crop mean/p50/p95/max | 3 crops mean/p50/p95/max | Cold ready | Session load | CPU s | Peak RSS MiB | PIDs |",
        "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for name, r in profile.get("runs", {}).items():
        c = r.get("counts", {})
        crop = r.get("crop_total_ms", {})
        triple = r.get("three_consecutive_crops_ms", {})
        crop_values = "/".join(_value(crop, x) for x in
                               ("mean_ms", "p50_ms", "p95_ms", "max_ms"))
        triple_values = "/".join(_value(triple, x) for x in
                                 ("mean_ms", "p50_ms", "p95_ms", "max_ms"))
        lines.append(
            f"| {name} | {c.get('correct', 'N/A')} | {c.get('correct_rejection', 'N/A')} | "
            f"{c.get('wrong_id', 'N/A')} wrong IDs | {c.get('false_positive', 'N/A')} | "
            f"{c.get('false_rejection', 'N/A')} | {crop_values} | {triple_values} | "
            f"{_value(r, 'cold_ready_wall_ms')} | {_value(r, 'model_session_load_ms')} | "
            f"{_value(r, 'sampled_process_tree_cpu_seconds')} | "
            f"{_mb(r.get('sampled_peak_process_tree_rss_bytes'))} | "
            f"{r.get('observed_distinct_pids', 'N/A')} |"
        )
    lines.extend([
        "",
        "## Size / dependencies",
        "",
        "| Item | Version | Installed MiB or model MiB |",
        "|---|---|---:|",
    ])
    sizes = {}
    for r in profile.get("runs", {}).values():
        sizes.update(r.get("model_bytes", {}))
    for name, size in sorted(sizes.items()):
        lines.append(f"| {name} | ONNX pinned | {_mb(size)} |")
    distributions = {}
    for r in profile.get("runs", {}).values():
        distributions.update(r.get("distributions", {}))
    for name, info in sorted(distributions.items()):
        lines.append(f"| {name} | {info.get('version', 'N/A')} | "
                     f"{_mb(info.get('installed_file_bytes'))} |")
    if controlled is not None:
        lines.extend([
            "",
            "## Original frozen images — controlled preprocessing comparisons",
            "",
            "**The same 26 archived original crops (19 title + 7 negative), not independent.**",
            "RapidOCR v4 uses the exact same v4 model weights as direct v4.",
            "",
            "| Variant | Correct /19 | Negatives /7 | Wrong IDs | Neg. FP | Safe rejects | Raw exact /19 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for key, label in SELECTED.items():
            s = controlled.get("summaries", {}).get(key, {})
            if s:
                lines.append(f"| {label} | {s.get('correct', 'N/A')} | "
                             f"{s.get('correct_rejection', 'N/A')} | "
                             f"{s.get('wrong_id', 'N/A')} | "
                             f"{s.get('false_positive', 'N/A')} | "
                             f"{s.get('false_rejection', 'N/A')} | "
                             f"{s.get('raw_exact', 'N/A')} |")
    lines.extend([
        "",
        "## Interpretation and safety restrictions",
        "",
        "- The benchmark was performed outside League, using old approved crops;",
        "  actual game-capture timing, animation windows, FPS and OP.GG remain NOT TESTED.",
        "- The 26 samples and multiple engines/configurations are correlated.",
        "- A non-null incorrect canonical ID or a title accepted on a negative",
        "  sample is a safety failure; correct abstentions are preferred.",
        "- Child subprocesses shorter than sampling intervals may be missed.",
        "- Machine identity is not validated by GitHub Actions and is not",
        "  included in this report; verify local provenance before claiming PC results.",
        "- Binary model sizes do not equal incremental Windows installer sizes.",
        "- Independent multi-offer, rarities, reroll, focus and DPI checks: BLOCKED.",
        "- No OCR thresholds, WGC, geometry or production runtime were changed.",
        "",
    ])
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--controlled", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--origin", choices=("CI_RUNNER", "LOCAL_USER_EXECUTION_UNATTESTED"),
                    default="LOCAL_USER_EXECUTION_UNATTESTED")
    args = ap.parse_args()
    p = json.loads(args.profile.read_text(encoding="utf-8"))
    c = json.loads(args.controlled.read_text(encoding="utf-8")) if args.controlled else None
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_report(p, device_origin=args.origin, controlled=c),
                        encoding="utf-8")
    print("READABLE_REPORT_WRITTEN (LOCAL_ONLY; no private images uploaded)", flush=True)


if __name__ == "__main__":
    main()
