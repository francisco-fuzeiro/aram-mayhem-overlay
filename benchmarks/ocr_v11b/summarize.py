"""Print only privacy-safe aggregates from completed real research runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    a=p.parse_args()
    root=a.input
    comparison=json.loads((root/"v11b_results.json").read_text(encoding="utf8"))
    m=comparison["metadata"]
    print("V11B_PINNED_PROVENANCE "+json.dumps({
        "reference_sha":m["reference_sha"],"model_sha256":m["model_sha256"],
        "dataset":m["dataset"],"rapidocr_input_tensor_parity":m.get("rapidocr_v14_input_parity"),
        "model_load_ms":m["model_load_ms"],"model_sizes_bytes":m["model_sizes_bytes"],
    }),flush=True)
    for name,s in comparison["summaries"].items():
        print("V11B_ORIGINAL_ENGINE "+json.dumps({
            "engine":name,"correct_titles":s["correct"],
            "correct_negatives":s["correct_rejection"],
            "wrong_ids":s["wrong_id"],"negative_false_positives":s["false_positive"],
            "safe_rejections":s["false_rejection"],"raw_exact":s["raw_exact"],
            "normalized_exact":s["normalized_exact"],
            "two_line_correct":s["two_line_correct"],
            "two_line_total":s["two_line_total"],
            "physical_slot_counts":s["per_slot"],
            "mean_p50_p95_max_crop_ms":s["mean_crop_ms"],
            "preprocessing_ms":s["preprocess_ms"],
            "matching_ms":s["matching_ms"],
            "three_crops_ms":s["three_crop_ms"],
        }),flush=True)
    for path in root.glob("*profile.json"):
        profile=json.loads(path.read_text(encoding="utf8"))
        for name,s in profile["runs"].items():
            print("V11B_ISOLATED_PROCESS_PROFILE "+json.dumps({
                "runner_platform":profile["platform"],
                "engine":name,
                "cold_ready_ms":s["cold_ready_wall_ms"],
                "model_load_ms":s["model_session_load_ms"],
                "crop_ms":s["crop_total_ms"],
                "three_crops_ms":s["three_consecutive_crops_ms"],
                "sampled_cpu_seconds":s["sampled_process_tree_cpu_seconds"],
                "sampled_cpu_one_core_percent":s["sampled_process_tree_cpu_one_core_percent"],
                "sampled_peak_rss_mib":round(s["sampled_peak_process_tree_rss_bytes"]/1048576,3),
                "observed_pids":s["observed_distinct_pids"],
            }),flush=True)
    synthetic=root/"synthetic_stress.json"
    if synthetic.exists():
        z=json.loads(synthetic.read_text(encoding="utf8"))
        print("V11B_SYNTHETIC_TEXT_NOT_IMAGES "+json.dumps({
            "catalog_titles":z["catalog_titles"],
            "accepted_exact":z["exact_original_titles_accepted"],
            "wrong_accepted":z["accepted_wrong_total"],
            "safe_rejections":z["safe_rejection_total"],
            "close_pairs":z["close_title_pairs_top25"],
            "presence_gate_needed":z["presence_gate_adversarial_probe"]["matcher_accepts"],
        }),flush=True)

if __name__=="__main__":
    main()
