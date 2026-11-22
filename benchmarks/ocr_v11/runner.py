"""Reproducible, offline-only after asset download, V1.1 OCR comparison.

This file does not import or mutate gameplay state. All IDs are matched through
the current production strict_match_title read from an exact pinned reference SHA.
No model is allowed to be missing/invalid and no accuracy errors are hidden.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import statistics
import sys
import time

V4_SHA = "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
V5_SHA = "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8"
REFERENCE_SHA = "7624b27c1d025c4183c2a78aa11609dda45ecf71"
# Historical v3 fixture manifest: expected bytes and first 16 SHA256 nibbles.
ASSETS = {
 "1440p/ocr_1795024923_centre.png": (15268,"1815316477bf6480"),
 "1440p/ocr_1795024923_right.png": (12681,"8a3f62bd4b45a7b2"),
 "1440p/ocr_1795025002_centre.png": (35955,"c770eacd8573360d"),
 "1440p/ocr_1795025015_centre.png": (15275,"ed622cccf35a5e20"),
 "1440p/ocr_1795025015_left.png": (12644,"61b2a1cf57fd04c3"),
 "1440p/ocr_1795025015_right.png": (12286,"66a0b22eb986461a"),
 "1440p/ocr_1795025241_centre.png": (12713,"66f277cf31a842f3"),
 "1440p/ocr_1795025241_left.png": (12584,"1fb2da5c11ca8af4"),
 "1440p/ocr_1795025241_right.png": (12773,"77a05feeddd0f85c"),
 "1440p/ocr_1795025367_centre.png": (36361,"2f8cb80492ce6bbf"),
 "1440p/region_1795025142_centre.png": (12713,"dfbb0a1c966f5430"),
 "1440p/region_1795025142_left.png": (12644,"ad7373f0ec0c2f90"),
 "1440p/region_1795025142_right.png": (12269,"d6fd8840f87a4b5a"),
 "snips/snip_015021_takeemdowndowndown.png": (23539,"37f1fdbd9c902762"),
 "snips/snip_015907_takeemdowndowndown.png": (23167,"b004fa933c2620b3"),
 "snips/snip_023747_enpassant.png": (15581,"bcf5a97d06d5ff90"),
 "snips/snip_023747_itskillingtime.png": (17748,"0bc9386e7b3a7cbf"),
 "snips/snip_023747_ravenousbind.png": (18056,"e3a31f2f7029e71d"),
 "snips/snip_121107_backtobasics.png": (17601,"5709d7a4ca68b83c"),
 "snips/snip_121107_biggestsnowballever.png": (20045,"f5188d14ebb8763c"),
 "snips/snip_121107_goliath.png": (13758,"66a51aaad9b7fc56"),
 "no_offer/card_centre_1795134399156658000_1.png": (34112,"5ff58b0e19c6cb7d"),
 "no_offer/card_left_1795134399156658000_0.png": (41224,"3ce0daf3992ffd7a"),
 "no_offer/card_left_1795134416913524800_0.png": (24918,"ed9d083d1fd753ab"),
 "no_offer/card_right_1795134399156658000_2.png": (45015,"9dec9e402dce42a3"),
 "no_offer/card_right_1795134416913524800_2.png": (19997,"3ffc4b3921976267"),
}
META = {
 "1440p/ground_truth.json": (1547, "d5f9f88707f5a36d"),
 "snips/ground_truth.json": (1378, "b241845a0c449255"),
}
CATALOG_META = (9131, "458d2b7f81d680f5")

def verify_asset(path: Path, sha256: str, size: int | None = None) -> str:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    actual_size = path.stat().st_size
    if size is not None and actual_size != size:
        raise ValueError("size_mismatch: " + path.name)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if not sha.startswith(sha256.lower()):
        raise ValueError("sha_mismatch: " + path.name)
    return sha

def validate_cases(cases: list[dict]) -> dict[str,int]:
    counts = dict(Counter(c["category"] for c in cases))
    expected = {"title":19,"dialog":2,"no_offer":5}
    if counts != expected or len(cases) != 26:
        raise ValueError(f"count_mismatch {counts}; expected {expected}")
    if len({c.get("file") for c in cases}) != 26:
        raise ValueError("count_mismatch: duplicated case file")
    return counts

def validate_output_dimensions(model_version: str, labels: int, dictionary: int) -> None:
    if model_version not in ("v4","v5"):
        raise ValueError("version_incompatible: " + model_version)
    expected = dictionary + 2  # The exact 2026-11-22 v5 ONNX emits blank + 436 keys + space (438 logits).
    if labels != expected:
        raise ValueError(f"decoder_incompatible: version {model_version}, logits={labels}, dictionary={dictionary}; expected {expected}")

def classify(expected: str | None, actual: str | None, category: str) -> str:
    if category not in ("title","dialog","no_offer"):
        raise ValueError("invalid category")
    if expected is None:
        return "correct_rejection" if actual is None else "false_positive"
    if actual is None:
        return "false_rejection"
    return "correct" if expected==actual else "wrong_id"

def assert_predictions(rows: list[dict]) -> None:
    for row in rows:
        expected_status = classify(row["expected"],row["actual"],row["category"])
        if row["status"] != expected_status:
            raise AssertionError("classification_mismatch: " + str(row.get("file")))

def read_cases(ref: Path) -> tuple[list[dict],dict]:
    from PIL import Image
    base = ref/"tests"/"fixtures"/"ocr_titles"
    if not base.is_dir():
        raise FileNotFoundError("Pinned N1 fixture directory is missing")
    for name, (size, sha) in META.items():
        verify_asset(base/name, sha, size)
    catalog_path = ref/"tests"/"fixtures"/"expected_mayhem_catalog_2026-11-20.json"
    verify_asset(catalog_path, CATALOG_META[1], CATALOG_META[0])
    catalog_doc = json.loads(catalog_path.read_text(encoding="utf8"))
    catalog = catalog_doc["catalog"]
    if catalog_doc["count"]!=328 or len(catalog)!=328:
        raise ValueError("catalog count must be exactly 328")
    cases=[]
    for group in ("1440p","snips"):
        gt=json.loads((base/group/"ground_truth.json").read_text(encoding="utf8"))
        for c in gt["cases"]:
            cases.append({"file":group+"/"+c["file"],"category":"title" if c["expected_name"] is not None else "dialog",
                          "expected":c["expected_name"],"slot":c.get("slot"),"two_line":bool(c.get("two_line")),
                          "rarity":c.get("rarity")})
    for name in sorted(ASSETS):
        if name.startswith("no_offer/"):
            slot=next((s for s in ("left","centre","right") if "_"+s+"_" in name),None)
            cases.append({"file":name,"category":"no_offer","expected":None,"slot":slot,"two_line":False,"rarity":None})
    validate_cases(cases)
    if set(ASSETS)!={c["file"] for c in cases}:
        raise ValueError("count_mismatch: manifest names do not equal ground truths")
    for c in cases:
        path=base/c["file"]
        size,sha=ASSETS[c["file"]]
        c["sha256"]=verify_asset(path,sha,size)
        with Image.open(path) as img:
            c["dimensions"]=list(img.size)
            if img.size != ((340,90) if c["category"]=="no_offer" else (342,96)):
                raise ValueError("image dimensions unexpected: "+c["file"])
    return cases,catalog

def split_lines(img):
    # Exactly the historical horizontal projection, deliberately not production code.
    import numpy as np
    g=np.asarray(img.convert("L"),dtype=np.float32)
    rows=(g>150).sum(1)>2
    segs=[]; start=None
    for i,r in enumerate(list(rows)+[False]):
        if r and start is None: start=i
        if not r and start is not None:
            if i-start>=6: segs.append((start,i))
            start=None
    if not segs: return []
    x=np.where((g>150).sum(0)>0)[0]
    if len(x)==0: return []
    return [img.crop((max(0,int(x.min())-6),max(0,a-4),
                       min(img.width,int(x.max())+6),min(img.height,b+4))) for a,b in segs]

def canon(s): return " ".join(s.casefold().split())

class DirectONNX:
    def __init__(self,path,version,dict_path=None):
        import onnxruntime as ort
        from .fetch_models import V4_SHA,V5_SHA
        verify_asset(path,V4_SHA if version=="v4" else V5_SHA,
                     10_857_958 if version=="v4" else None)
        options=ort.SessionOptions()
        options.intra_op_num_threads=1
        options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        t=time.perf_counter()
        self.session=ort.InferenceSession(str(path),options,providers=["CPUExecutionProvider"])
        self.load_ms=(time.perf_counter()-t)*1000
        self.version=version
        shape=self.session.get_inputs()[0].shape
        self.height=48
        self.width=448 if version=="v4" else (shape[3] if isinstance(shape[3],int) else 320)
        metadata=self.session.get_modelmeta().custom_metadata_map
        if version=="v4" and Path(dict_path).is_file():
            self.dictionary=Path(dict_path).read_text(encoding="utf8").splitlines()
            self.charset_source="pinned_wheel_dictionary"
        else:
            if "character" not in metadata:
                raise ValueError("decoder_incompatible: missing embedded character dictionary")
            self.dictionary=metadata["character"].splitlines()
            self.charset_source="embedded_ONNX_metadata"
        # The logits count will also be checked at runtime; no guessing of charset indices.
        self.chars=[""]+self.dictionary+[" "]  # Both pinned v4 and v5 CTC heads include a terminal space class.
        self.input_name=self.session.get_inputs()[0].name
        self.output_labels=None

    def rec(self,img):
        import numpy as np
        from PIL import Image
        t=time.perf_counter()
        img=img.convert("RGB")
        width=max(1,min(self.width,round(img.width*self.height/img.height)))
        a=np.asarray(img.resize((width,self.height),Image.Resampling.BILINEAR),dtype=np.float32)/255.0
        x=np.zeros((1,3,self.height,self.width),dtype=np.float32)
        x[0,:,:,:width]=((a-0.5)/0.5).transpose(2,0,1)
        pre=(time.perf_counter()-t)*1000
        t=time.perf_counter()
        p=self.session.run(None,{self.input_name:x})[0][0]
        infer=(time.perf_counter()-t)*1000
        if p.ndim!=2:
            raise ValueError("decoder_incompatible: expected [time, classes] logits")
        validate_output_dimensions(self.version,int(p.shape[-1]),len(self.dictionary))
        self.output_labels=int(p.shape[-1])
        best=p.argmax(1)
        conf=p.max(1)
        emitted=[];scores=[];last=0
        for bi,ci in zip(best,conf):
            b=int(bi)
            if b!=last and b!=0:
                emitted.append(self.chars[b]);scores.append(float(ci))
            last=b
        return "".join(emitted).strip(), (statistics.mean(scores) if scores else 0.0),pre,infer

class RapidV4:
    def __init__(self,model,keys):
        from rapidocr_onnxruntime.ch_ppocr_rec.text_recognize import TextRecognizer
        from rapidocr_onnxruntime.utils import read_yaml
        import rapidocr_onnxruntime
        t=time.perf_counter()
        cfg=read_yaml(str(Path(rapidocr_onnxruntime.__file__).parent/"config.yaml"))
        rec_cfg=cfg["Rec"]
        rec_cfg.update({"model_path":str(model),"rec_keys_path":str(keys) if Path(keys).exists() else None,
                        "use_cuda":False,"rec_batch_num":1,"rec_img_shape":[3,48,448],
                        "intra_op_num_threads":1,"inter_op_num_threads":1})
        self.engine=TextRecognizer(rec_cfg)  # recognizer ONLY; detector and classifier never created
        self.load_ms=(time.perf_counter()-t)*1000
    def rec(self,img):
        import numpy as np
        t=time.perf_counter()
        # RapidOCR's historical preprocessing uses OpenCV-style BGR.
        bgr=np.asarray(img.convert("RGB"))[:,:,::-1].copy()
        pre=(time.perf_counter()-t)*1000
        t=time.perf_counter()
        result,_=self.engine([bgr])
        infer=(time.perf_counter()-t)*1000
        if len(result)!=1 or len(result[0])<2:
            raise ValueError("RapidOCR recognizer-only output contract changed")
        return str(result[0][0]),float(result[0][1]),pre,infer

def run_ocr(engine,img, matcher, catalog, mode="split"):
    t0=time.perf_counter()
    chunks=[img] if mode=="full" else split_lines(img)
    prep=(time.perf_counter()-t0)*1000
    parts=[]; inference=0.0
    for chunk in chunks:
        text,confidence,p,i=engine.rec(chunk)
        prep+=p;inference+=i
        if mode=="full" or (confidence>=0.5 and len(re.sub(r"[^a-z0-9]","",text.casefold()))>=2):
            parts.append(text)
    raw=" ".join(parts).strip()
    t=time.perf_counter()
    match=matcher(raw,catalog) if raw else None
    match_ms=(time.perf_counter()-t)*1000
    return raw,match,prep,inference,match_ms

def tesseract_ocr(img,matcher,catalog,reference_mod):
    import pytesseract
    t=time.perf_counter()
    prep=reference_mod.preprocess_for_ocr(img)
    p_ms=(time.perf_counter()-t)*1000
    infer_ms=0.0; match_ms=0.0; raw=""
    for psm in (7,6):
        t=time.perf_counter()
        raw=pytesseract.image_to_string(prep,lang="eng",config=f"--psm {psm} --oem 3")
        infer_ms+=(time.perf_counter()-t)*1000
        t=time.perf_counter()
        match=matcher(raw,catalog)
        match_ms+=(time.perf_counter()-t)*1000
        if match is not None:
            return raw,match,p_ms,infer_ms,match_ms
    return raw,None,p_ms,infer_ms,match_ms

def historical_match(text,catalog):
    """Exact historical v3-script fuzzy policy (removes ALL separators)."""
    import unicodedata
    from rapidfuzz import fuzz
    def n(s):
        value=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower()
        return re.sub(r"[^a-z0-9]","",value)
    scores=sorted(((fuzz.ratio(n(text),n(title)),aid) for aid,title in catalog.items()),reverse=True)
    (best,aid),(second,_) = scores[:2]
    if best>=90 and best-second>=8:
        return aid,catalog[aid],int(best)
    return None

def historical_normalize(s):
    import unicodedata
    return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower())

def diagnostics(raw,matcher,catalog,normalizer):
    from rapidfuzz import fuzz
    normalized=normalizer(raw)
    scores=sorted((float(fuzz.ratio(normalized,n)) for n in {normalizer(v) for v in catalog.values()}),reverse=True)
    return {"best_score":round(scores[0],3) if scores else 0,
            "margin":round(scores[0]-scores[1],3) if len(scores)>1 else 0,
            "normalized":normalized}

def variants(img):
    import io
    from PIL import Image
    for scale in (1.0,.75,.5,.4):
        resized=img.resize((round(img.width*scale),round(img.height*scale)),Image.Resampling.BILINEAR) if scale!=1.0 else img.copy()
        yield scale,"PNG",resized,scale==1.0
        buffer=io.BytesIO()
        resized.save(buffer,format="JPEG",quality=60)
        buffer.seek(0)
        yield scale,"JPEG60",Image.open(buffer).convert("RGB"),False

def stats(vals):
    if not vals:return None
    seq=sorted(vals)
    p=lambda k:seq[min(len(seq)-1,max(0,int((len(seq)-1)*k+.5)))]
    return {"n":len(seq),"mean_ms":round(statistics.mean(seq),3),"p50_ms":round(p(.5),3),
            "p95_ms":round(p(.95),3),"max_ms":round(seq[-1],3)}

def summary(rows,engine,scale,fmt):
    matching=[r for r in rows if r["engine"]==engine and r["scale"]==scale and r["format"]==fmt]
    counts=Counter(r["status"] for r in matching)
    positives=[r for r in matching if r["category"]=="title"]
    return {"engine":engine,"scale":scale,"format":fmt,"total":len(matching),
            "correct_titles":counts["correct"],"wrong_nonnull":counts["wrong_id"],
            "correct_negative_rejections":counts["correct_rejection"],"false_positives":counts["false_positive"],
            "false_rejections":counts["false_rejection"],
            "raw_exact":sum(r["raw_exact"] for r in positives),
            "raw_titles":len(positives),
            "two_line_errors":sum(r["status"]!="correct" for r in positives if r["two_line"]),
            "timing_ms":stats([r["total_ms"] for r in matching]),
            "preprocess_ms":stats([r["preprocess_ms"] for r in matching]),
            "matching_ms":stats([r["matching_ms"] for r in matching])}

def main():
    import numpy as np
    import onnxruntime as ort
    import psutil
    import rapidfuzz
    import pytesseract
    from PIL import Image
    from rapidfuzz.distance import Levenshtein
    parser=argparse.ArgumentParser()
    parser.add_argument("--reference",type=Path,required=True)
    parser.add_argument("--models",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    ref=a.reference.resolve()
    mod=a.models.resolve()
    if not (ref/".git").exists():
        raise ValueError("Pinned checkout required")
    import subprocess
    head=subprocess.check_output(["git","-C",str(ref),"rev-parse","HEAD"],text=True).strip()
    if head!=REFERENCE_SHA:raise ValueError("Reference SHA mismatch; expected "+REFERENCE_SHA+" actual "+head)
    sys.path.insert(0,str(ref))
    from backend.collectors.slot_title_ocr import strict_match_title, recognize_title_slot,_normalize
    from backend.collectors.screen_ocr import preprocess_for_ocr
    import backend.collectors.screen_ocr as screen_ocr
    cases,catalog=read_cases(ref)
    if not set((c["expected"] for c in cases if c["expected"])) <= set(catalog.values()):
        raise ValueError("Ground truth title absent from catalog")
    v4=DirectONNX(mod/"ppocrv4.onnx","v4",mod/"ppocr_keys_v1.txt")
    v5=DirectONNX(mod/"ppocrv5_en.onnx","v5")
    rapid=RapidV4(mod/"ppocrv4.onnx",mod/"ppocr_keys_v1.txt")
    engine_names=("tesseract","ppocrv4_split","ppocrv4_full","ppocrv4_historical_split",
                  "ppocrv4_historical_full","ppocrv5_en_split","rapidocr_v4_split")
    engines={"ppocrv4_split":(v4,"split"),"ppocrv4_full":(v4,"full"),
             "ppocrv4_historical_split":(v4,"split"),"ppocrv4_historical_full":(v4,"full"),
             "ppocrv5_en_split":(v5,"split"),"rapidocr_v4_split":(rapid,"split")}
    # Warm-up does not contribute to per-crop latency distribution.
    warm_image=Image.open(ref/"tests"/"fixtures"/"ocr_titles"/cases[0]["file"]).convert("RGB")
    for e,m in engines.values():
        for _ in range(2):run_ocr(e,warm_image,strict_match_title,catalog,m)
    for _ in range(2):tesseract_ocr(warm_image,strict_match_title,catalog,screen_ocr)
    process=psutil.Process()
    rows=[];resources={}
    for engine_name in engine_names:
        cpu_start=process.cpu_times();wall_start=time.perf_counter()
        before_rss=process.memory_info().rss
        for c in cases:
            source=ref/"tests"/"fixtures"/"ocr_titles"/c["file"]
            with Image.open(source) as opened:img=opened.convert("RGB")
            for scale,fmt,transformed,original in variants(img):
                if engine_name=="tesseract":
                    raw,match,pre,infer,match_ms=tesseract_ocr(transformed,strict_match_title,catalog,screen_ocr)
                    if original:
                        # Independent parity check against actual production entrypoint.
                        prod=recognize_title_slot(c["slot"] or "centre",transformed,catalog)
                        if (prod[0] if prod else None)!=(match[0] if match else None):
                            raise AssertionError("Tesseract path drift: "+c["file"])
                else:
                    ocr,mode=engines[engine_name]
                    comparator=historical_match if "historical" in engine_name else strict_match_title
                    raw,match,pre,infer,match_ms=run_ocr(ocr,transformed,comparator,catalog,mode)
                actual=match[1] if match else None
                status=classify(c["expected"],actual,c["category"])
                diag=diagnostics(raw,strict_match_title,catalog,historical_normalize if "historical" in engine_name else _normalize)
                row={"file":c["file"],"sha256":c["sha256"],"source_dimensions":c["dimensions"],
                     "engine":engine_name,"scale":scale,"format":fmt,"derived":not original,
                     "category":c["category"],"slot":c["slot"],"rarity":c["rarity"],
                     "two_line":c["two_line"],"expected":c["expected"],"raw":raw,
                     "raw_exact":canon(raw)==canon(c["expected"] or "") if c["category"]=="title" else None,
                     "cer_distance":Levenshtein.distance(canon(raw),canon(c["expected"])) if c["category"]=="title" else None,
                     "actual":actual,"actual_id":match[0] if match else None,"status":status,
                     "best_score":diag["best_score"],"margin":diag["margin"],
                     "normalized":diag["normalized"],"preprocess_ms":round(pre,3),
                     "inference_ms":round(infer,3),"matching_ms":round(match_ms,3),
                     "total_ms":round(pre+infer+match_ms,3)}
                rows.append(row)
        wall=time.perf_counter()-wall_start
        cpu_end=process.cpu_times()
        delta_cpu=(cpu_end.user+cpu_end.system)-(cpu_start.user+cpu_start.system)
        resources[engine_name]={"total_wall_s":round(wall,3),"cpu_time_s":round(delta_cpu,3),
                                "cpu_percent_one_core":round(100*delta_cpu/wall,2) if wall else None,
                                "rss_before_bytes":before_rss,"rss_after_bytes":process.memory_info().rss}
    assert_predictions(rows)
    for engine_name in engine_names:
        for scale in (1.0,.75,.5,.4):
            for fmt in ("PNG","JPEG60"):
                if sum(r["engine"]==engine_name and r["scale"]==scale and r["format"]==fmt for r in rows)!=26:
                    raise AssertionError("Missing per-engine transform cases")
    summaries=[summary(rows,e,s,f) for e in engine_names for s in (1.0,.75,.5,.4) for f in ("PNG","JPEG60")]
    loads={"ppocrv4":round(v4.load_ms,3),"ppocrv5_en":round(v5.load_ms,3),
           "rapidocr_v4":round(rapid.load_ms,3)}
    batch={}
    for name in engine_names:
        values=[]
        three=[Image.open(ref/"tests"/"fixtures"/"ocr_titles"/c["file"]).convert("RGB") for c in cases[:3]]
        for _ in range(8):
            t=time.perf_counter()
            for im in three:
                if name=="tesseract":tesseract_ocr(im,strict_match_title,catalog,screen_ocr)
                else:
                    obj,mode=engines[name]
                    run_ocr(obj,im,historical_match if "historical" in name else strict_match_title,catalog,mode)
            values.append(1000*(time.perf_counter()-t))
        batch[name]=stats(values)
    sizes={"v4_bytes":(mod/"ppocrv4.onnx").stat().st_size,"v5_en_bytes":(mod/"ppocrv5_en.onnx").stat().st_size}
    deps={name:importlib.metadata.version(name) for name in ("onnxruntime","rapidocr-onnxruntime",
                                                              "numpy","pillow","rapidfuzz","pytesseract","psutil")}
    package_disk_bytes={}
    for dist_name in deps:
        dist=importlib.metadata.distribution(dist_name)
        total=0
        for entry in dist.files or []:
            try:
                candidate=Path(dist.locate_file(entry))
                if candidate.is_file():
                    total+=candidate.stat().st_size
            except (OSError,ValueError):
                pass
        package_disk_bytes[dist_name]=total
    metadata={"reference_sha":head,"platform":platform.platform(),"cpu":platform.processor(),
              "cpu_logical_count":os.cpu_count(),"onnx_provider":ort.get_available_providers(),
              "onnx_threads":1,"python":sys.version.split()[0],
              "tesseract":str(pytesseract.get_tesseract_version()),"dependencies":deps,
              "installed_distribution_bytes":package_disk_bytes,
              "model_sha256":{"v4":V4_SHA,"v5_en":V5_SHA},"model_sizes":sizes,
              "model_load_ms":loads,"charset_sources":{"v4":v4.charset_source,"v5":v5.charset_source},
              "three_crops_ms":batch,"resources":resources,
              "cases":validate_cases(cases),"catalog":len(catalog),
              "original_images":26,"per_engine_variants":208,"warmups_per_engine":2,
              "single_core_cpu_percent_note":"process CPU time / wall time, not system utilisation during League"}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"cases.json").write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding="utf8")
    (a.out/"summary.json").write_text(json.dumps({"metadata":metadata,"summaries":summaries},indent=2),encoding="utf8")
    print("BENCHMARK_FINISHED "+json.dumps({"metadata":metadata,"base_png": [x for x in summaries if x["scale"]==1.0 and x["format"]=="PNG"]}),flush=True)

if __name__=="__main__":
    main()
