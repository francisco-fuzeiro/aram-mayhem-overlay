"""Opt-in V1.1b local benchmark. Run outside League from an isolated venv.

Windows native OCR throughput/resource test ONLY; no game, WGC, API, UI,
installer, runtime dependencies or production OCR calls are changed.
Models and frozen original fixtures must be supplied and are hash-verified.
No screen capture, usernames, absolute paths or raw OCR text are recorded.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ENGINES=("tesseract","ppocrv4_split","rapidocr_v4_split","ppocrv5_en_split")

def installed_bytes(package):
    try:
        dist=importlib.metadata.distribution(package)
        size=0
        for item in dist.files or []:
            try:
                file=Path(dist.locate_file(item))
                if file.is_file():
                    size+=file.stat().st_size
            except (OSError,ValueError):
                pass
        return {"version":dist.version,"installed_file_bytes":size}
    except importlib.metadata.PackageNotFoundError:
        return {"installed_file_bytes":None,"version":None}

def worker(args):
    # This process intentionally loads ONE model, unlike the shared V1.1
    # Linux benchmark. The parent measures import+startup wall time.
    from benchmarks.ocr_v11.runner import (
        REFERENCE_SHA, DirectONNX, RapidV4, read_cases, run_ocr,
        tesseract_ocr, stats,
    )
    from benchmarks.ocr_v11b.validation import classify_evidence,decision_counts
    t_load_start=time.perf_counter()
    ref=args.reference.resolve()
    if subprocess.check_output(["git","-C",str(ref),"rev-parse","HEAD"],
                               text=True).strip()!=REFERENCE_SHA:
        raise ValueError("Reference SHA mismatch")
    sys.path.insert(0,str(ref))
    from backend.collectors.slot_title_ocr import strict_match_title
    from backend.collectors import screen_ocr
    from PIL import Image
    cases,catalog=read_cases(ref)
    if args.engine=="tesseract":
        import pytesseract
        load_ms=0.0
        version=str(pytesseract.get_tesseract_version())
    elif args.engine=="ppocrv4_split":
        engine=DirectONNX(args.models/"ppocrv4.onnx","v4",args.models/"ppocr_keys_v1.txt")
        load_ms=engine.load_ms
        version="v4"
    elif args.engine=="rapidocr_v4_split":
        engine=RapidV4(args.models/"ppocrv4.onnx",args.models/"ppocr_keys_v1.txt")
        load_ms=engine.load_ms
        version="v4 RapidOCR wrapper"
    elif args.engine=="ppocrv5_en_split":
        engine=DirectONNX(args.models/"ppocrv5_en.onnx","v5")
        load_ms=engine.load_ms
        version="v5 English"
    else:
        raise ValueError("invalid engine")
    setup_ms=1000*(time.perf_counter()-t_load_start)
    base=ref/"tests"/"fixtures"/"ocr_titles"
    if args.startup_only:
        print("V11B_STARTUP_JSON="+json.dumps({
            "model_session_load_ms":round(load_ms,3),
            "setup_after_import_ms":round(setup_ms,3),
            "verified_original_images":len(cases),
        }),flush=True)
        return

    def run(img):
        t=time.perf_counter()
        if args.engine=="tesseract":
            raw,match,pre,inf,m=tesseract_ocr(img,strict_match_title,catalog,screen_ocr)
        else:
            raw,match,pre,inf,m=run_ocr(engine,img,strict_match_title,catalog)
        elapsed=1000*(time.perf_counter()-t)
        # Never return raw OCR or user data in resource report.
        return (match[0] if match else None,elapsed,pre,inf,m)

    with Image.open(base/cases[0]["file"]) as im:
        first=im.convert("RGB")
    for _ in range(2):
        run(first)
    rows=[]; per_crop=[];preprocess=[];match_times=[];inference=[]
    for c in cases:
        with Image.open(base/c["file"]) as im:
            actual,ms,pre,inf,m=run(im.convert("RGB"))
        expected_match=(strict_match_title(c["expected"],catalog)
                        if c["expected"] else None)
        expected_id=expected_match[0] if expected_match else None
        if c["expected"] and expected_id is None:
            raise ValueError("frozen catalog ground truth has no canonical ID")
        status=classify_evidence(expected_id,actual,c["category"],
                                  c["slot"] or "centre")["status"]
        rows.append({"category":c["category"],"slot":c["slot"],"status":status})
        per_crop.append(ms)
        preprocess.append(pre)
        inference.append(inf)
        match_times.append(m)
    triple=[]
    files=["1440p/ocr_1795025241_"+s+".png" for s in ("left","centre","right")]
    for _ in range(8):
        start=time.perf_counter()
        for file in files:
            with Image.open(base/file) as im:
                run(im.convert("RGB"))
        triple.append(1000*(time.perf_counter()-start))
    model_sizes={
        "ppocrv4.onnx":(args.models/"ppocrv4.onnx").stat().st_size if (args.models/"ppocrv4.onnx").is_file() else None,
        "ppocrv5_en.onnx":(args.models/"ppocrv5_en.onnx").stat().st_size if (args.models/"ppocrv5_en.onnx").is_file() else None,
    }
    payload={
        "engine":args.engine,"engine_version":version,
        "dataset":"original frozen 26, 19 title + 7 negative; NOT independent",
        "setup_after_import_ms":round(setup_ms,3),
        "model_session_load_ms":round(load_ms,3),
        "counts":decision_counts(rows),
        "crop_total_ms":stats(per_crop),
        "preprocess_ms":stats(preprocess),"inference_ms":stats(inference),
        "matching_ms":stats(match_times),"three_consecutive_crops_ms":stats(triple),
        "model_bytes":model_sizes,
        "distributions":{name:installed_bytes(name) for name in
                         ("onnxruntime","rapidocr-onnxruntime","numpy","Pillow",
                          "rapidfuzz","pytesseract","psutil","opencv-python-headless")},
    }
    print("V11B_CHILD_JSON="+json.dumps(payload),flush=True)

def profile(args):
    import psutil
    out={"measurement":"opt-in isolated Windows/CI resource test, not live League",
         "platform":platform.platform(),"python":sys.version.split()[0],
         "dataset_class":"original", "independent_holdout":"BLOCKED",
         "warnings":[
           "cold_ready_wall_ms measures a fresh Python process from launch through verified fixtures and model ready, before warmup; it is distinct from pure model load time.",
           "Full workload subprocess wall time includes import, fixture verification, warmup and 26+batch inferences; it is NOT just model initialization.",
           "Per-engine model_session_load_ms excludes Python import/startup.",
           "Sampled process-tree CPU and RSS can miss very short-lived Tesseract subprocesses; CPU is a lower bound, not League overhead.",
           "Peak summed RSS may double count shared mappings; not an incremental installer or game process footprint.",
           "GitHub Actions Windows runner performance is NOT the user's PC."
         ],"runs":{}}
    for engine in ENGINES:
        startup_cmd=[sys.executable,"-m","benchmarks.ocr_v11b.profile_windows",
                     "--child","--startup-only","--engine",engine,
                     "--reference",str(args.reference),"--models",str(args.models)]
        cold_start=time.perf_counter()
        startup=subprocess.run(startup_cmd,capture_output=True,text=True)
        cold_ready_ms=1000*(time.perf_counter()-cold_start)
        if startup.returncode:
            raise RuntimeError(f"{engine} cold-start failed (local-only): {startup.stderr[-3500:]}")
        starts=[line[len("V11B_STARTUP_JSON="):] for line in startup.stdout.splitlines()
                if line.startswith("V11B_STARTUP_JSON=")]
        if len(starts)!=1:
            raise ValueError("missing cold-start milestone for "+engine)
        cold_result=json.loads(starts[0])
        command=[sys.executable,"-m","benchmarks.ocr_v11b.profile_windows",
                 "--child","--engine",engine,"--reference",str(args.reference),
                 "--models",str(args.models)]
        start=time.perf_counter()
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              text=True)
        observed={}
        peak_tree_rss=0
        snapshots=0
        while proc.poll() is None:
            try:
                root=psutil.Process(proc.pid)
                processes=[root]+root.children(recursive=True)
                current_rss=0
                for p in processes:
                    try:
                        cpu=p.cpu_times()
                        current_rss+=p.memory_info().rss
                        # PID + creation time protects against PID reuse.
                        key=(p.pid,p.create_time())
                        observed[key]=max(observed.get(key,0.0),cpu.user+cpu.system)
                    except (psutil.NoSuchProcess,psutil.AccessDenied):
                        continue
                peak_tree_rss=max(peak_tree_rss,current_rss)
                snapshots+=1
            except (psutil.NoSuchProcess,psutil.AccessDenied):
                pass
            time.sleep(.01)
        stdout,stderr=proc.communicate()
        wall=1000*(time.perf_counter()-start)
        if proc.returncode:
            # Leave raw traceback local in terminal, never in uploaded JSON.
            raise RuntimeError(f"{engine} child exited {proc.returncode}; local-only stderr:\n{stderr[-3500:]}")
        lines=[l[len("V11B_CHILD_JSON="):] for l in stdout.splitlines()
               if l.startswith("V11B_CHILD_JSON=")]
        if len(lines)!=1:
            raise ValueError("missing child metric JSON for "+engine)
        result=json.loads(lines[0])
        result.update({
            "cold_ready_wall_ms":round(cold_ready_ms,3),
            "cold_ready_metadata":cold_result,
            "total_full_workload_process_wall_ms":round(wall,3),
            "sampled_process_tree_cpu_seconds":round(sum(observed.values()),3),
            "sampled_process_tree_cpu_one_core_percent":round(
                100*sum(observed.values())/(wall/1000),3) if wall else None,
            "sampled_peak_process_tree_rss_bytes":peak_tree_rss,
            "process_tree_observation_count":snapshots,
            "observed_distinct_pids":len(observed),
        })
        out["runs"][engine]=result
        print("PROFILED "+engine+" (original frozen 26; NOT game evidence)",flush=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2),encoding="utf8")
    print("WINDOWS_PROFILE_WRITTEN (review locally before sharing)",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--reference",type=Path,required=True)
    ap.add_argument("--models",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=Path("v11b_windows_profile.json"))
    ap.add_argument("--child",action="store_true",help=argparse.SUPPRESS)
    ap.add_argument("--startup-only",action="store_true",help=argparse.SUPPRESS)
    ap.add_argument("--engine",choices=ENGINES,help=argparse.SUPPRESS)
    args=ap.parse_args()
    if args.child:
        if not args.engine:
            raise ValueError("worker engine required")
        worker(args)
    else:
        profile(args)

if __name__=="__main__":
    main()
