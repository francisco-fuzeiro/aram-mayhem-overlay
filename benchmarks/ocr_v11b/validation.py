"""Offline V1.1b dataset boundaries and identity-safety accounting.

This module never writes screenshots, changes production logic, or assumes
that repeated transforms are independent observations. Only metadata is emitted.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath
import re
import statistics

KINDS=("independent","original","derived","synthetic")
CATEGORIES=("title","dialog","no_offer")
SLOTS=("left","centre","right")
_HEX64=re.compile(r"^[a-f0-9]{64}$")

def validate_manifest(manifest: dict, original_hashes: set[str],
                      *, require_independent: bool=False) -> dict:
    """Validate user-approved local holdout. Never infer approval from filename."""
    if not isinstance(manifest,dict) or not isinstance(manifest.get("samples"),list):
        raise ValueError("invalid manifest")
    known=set(original_hashes)
    seen_hashes=set()
    seen_ids=set()
    categories=Counter()
    for item in manifest["samples"]:
        if not isinstance(item,dict):
            raise ValueError("invalid sample")
        kind=item.get("kind")
        if kind not in KINDS:
            raise ValueError("invalid kind")
        if require_independent and kind!="independent":
            raise ValueError("holdout must be independent")
        digest=item.get("sha256")
        if not isinstance(digest,str) or not _HEX64.fullmatch(digest):
            raise ValueError("invalid sha256")
        if digest in seen_hashes:
            raise ValueError("duplicate sha256")
        seen_hashes.add(digest)
        unique_id=item.get("id")
        if not isinstance(unique_id,str) or not unique_id or unique_id in seen_ids:
            raise ValueError("duplicate or invalid sample id")
        seen_ids.add(unique_id)
        filename=item.get("file")
        if not isinstance(filename,str) or not filename or "\\" in filename:
            raise ValueError("invalid relative file")
        path=PurePosixPath(filename)
        if path.is_absolute() or any(x in (".","..") for x in filename.split("/")):
            raise ValueError("invalid relative file")
        if item.get("privacy_approved") is not True:
            raise ValueError("privacy approval required")
        category=item.get("category")
        if category not in CATEGORIES:
            raise ValueError("invalid category")
        if (category=="title") != (isinstance(item.get("expected"),str) and bool(item.get("expected"))):
            raise ValueError("expected and category inconsistent")
        if item.get("slot") not in SLOTS:
            raise ValueError("physical slot required")
        if kind=="independent":
            if digest in known:
                raise ValueError("original duplicate cannot count as independent")
            if not isinstance(item.get("source_session"),str) or not item["source_session"].strip():
                raise ValueError("independent session provenance required")
            if item.get("parent_sha256"):
                raise ValueError("independent sample cannot have a parent")
        elif kind=="derived":
            if not _HEX64.fullmatch(str(item.get("parent_sha256",""))):
                raise ValueError("derived sample needs parent sha256")
        elif kind=="original":
            if digest not in known:
                raise ValueError("original must match frozen dataset")
        categories[kind]+=1
    counts={kind:categories[kind] for kind in KINDS}
    counts["total"]=sum(categories.values())
    counts["holdout_status"]="READY_FOR_REVIEW" if counts["independent"] else "BLOCKED"
    return counts

def classify_evidence(expected,actual,category,slot):
    if category not in CATEGORIES or slot not in SLOTS:
        raise ValueError("invalid category/slot")
    if expected is None:
        status="correct_rejection" if actual is None else "false_positive"
    elif actual is None:
        status="false_rejection"
    else:
        status="correct" if expected==actual else "wrong_id"
    return {"status":status,"category":category,"slot":slot,
            "expected":expected,"actual":actual}

def decision_counts(rows):
    counts=Counter(r["status"] for r in rows)
    result={k:counts[k] for k in ("correct","correct_rejection","false_rejection",
                                  "wrong_id","false_positive")}
    result["total"]=len(rows)
    result["safety_pass"]=bool(rows) and result["wrong_id"]==0 and result["false_positive"]==0
    return result

def benchmark_stats(values):
    ordered=sorted(float(x) for x in values)
    if not ordered:
        return None
    def p(q):
        return ordered[min(len(ordered)-1,max(0,int((len(ordered)-1)*q+0.5)))]
    return {"n":len(ordered),"mean_ms":round(statistics.mean(ordered),3),
            "p50_ms":round(p(.5),3),"p95_ms":round(p(.95),3),
            "max_ms":round(ordered[-1],3)}
