"""Download ONLY pinned OCR weights for the isolated V1.1 benchmark.

No model is written to the Git tree or application's runtime.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

V4_SHA = "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
V4_BYTES = 10_857_958
V5_SHA = "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8"
V5_URL = ("https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/"
          "v3.9.2/onnx/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx")

def verify(path: Path, sha: str, size: int | None = None) -> dict:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != sha:
        raise ValueError("sha_mismatch: " + path.name + " expected " + sha + " actual " + digest)
    if size is not None and path.stat().st_size != size:
        raise ValueError("size_mismatch: " + path.name)
    return {"file": path.name, "sha256": digest, "bytes": path.stat().st_size}

def fetch(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    wheel_dir = out / "wheel"
    wheel_dir.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps",
                    "--only-binary=:all:", "-d", str(wheel_dir),
                    "rapidocr-onnxruntime==1.4.4"], check=True)
    wheels = list(wheel_dir.glob("rapidocr_onnxruntime-1.4.4-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected exactly one pinned RapidOCR 1.4.4 wheel")
    with zipfile.ZipFile(wheels[0]) as z:
        models = [n for n in z.namelist() if n.endswith("/models/ch_PP-OCRv4_rec_infer.onnx")]
        keys = [n for n in z.namelist() if n.endswith("/models/ppocr_keys_v1.txt")]
        if len(models) != 1:
            raise RuntimeError("Historical model absent from pinned wheel")
        (out / "ppocrv4.onnx").write_bytes(z.read(models[0]))
        if len(keys) == 1:
            (out / "ppocr_keys_v1.txt").write_bytes(z.read(keys[0]))
            print("V4_CHARSET_SOURCE pinned_wheel_dictionary",flush=True)
        else:
            print("V4_CHARSET_SOURCE embedded_ONNX_metadata_must_be_verified_at_inference",flush=True)
    v4 = verify(out / "ppocrv4.onnx", V4_SHA, V4_BYTES)
    print("PINNED_V4_VERIFIED " + json.dumps(v4), flush=True)

    v5 = out / "ppocrv5_en.onnx"
    tmp = out / "ppocrv5_en.part"
    try:
        req = urllib.request.Request(V5_URL, headers={"User-Agent":"aram-oracle-v1.1-research/1.0"})
        with urllib.request.urlopen(req, timeout=90) as response, tmp.open("wb") as dest:
            while True:
                data = response.read(1024 * 1024)
                if not data:
                    break
                dest.write(data)
        verify(tmp, V5_SHA)
        tmp.replace(v5)
        print("PINNED_V5_VERIFIED " + json.dumps(verify(v5, V5_SHA)), flush=True)
    finally:
        if tmp.exists():
            tmp.unlink()

if __name__ == "__main__":
    try:
        fetch(Path(sys.argv[1] if len(sys.argv) > 1 else ".benchmark_assets"))
    except Exception as exc:
        print("MODEL_FETCH_FAILED " + type(exc).__name__ + ": " + str(exc), file=sys.stderr, flush=True)
        raise
