"""Explicit, user-triggered installation of the pinned OCR v4 ONNX model.

Never invoked automatically by the desktop app. Downloads only the pinned
public Python wheel into a temporary folder; never uploads images or telemetry.
The model binary is never committed to the public repository.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from backend.collectors.ppocr_v4 import (
    MODEL_BYTES, MODEL_SHA256, default_model_path, verify_model
)


def extract_verified_model(wheel: Path, destination: Path) -> None:
    """Extract only the approved ONNX entry after whole-model hash checks."""
    with zipfile.ZipFile(wheel) as archive:
        candidates = [
            name for name in archive.namelist()
            if name.endswith("/models/ch_PP-OCRv4_rec_infer.onnx")
        ]
        if len(candidates) != 1:
            raise ValueError("Pinned OCR wheel has no unique PP-OCRv4 model")
        payload = archive.read(candidates[0])
    import hashlib
    if len(payload) != MODEL_BYTES or hashlib.sha256(payload).hexdigest() != MODEL_SHA256:
        raise ValueError("Pinned PP-OCRv4 model integrity mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(destination.name + ".staging")
    try:
        staged.write_bytes(payload)
        verify_model(staged)
        staged.replace(destination)
    finally:
        if staged.exists():
            staged.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Install verified PP-OCRv4 locally (opt-in)")
    parser.add_argument("--check", action="store_true",
                        help="Verify an already installed model, without network")
    args = parser.parse_args()
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        if args.check:
            print("ONNXRUNTIME_MISSING")
            return 1
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "--disable-pip-version-check", "onnxruntime==1.20.1"], check=True)
    destination = default_model_path()
    if destination.is_file():
        verify_model(destination)
        print("PPOCRV4_MODEL_VERIFIED")
        return 0
    if args.check:
        print("PPOCRV4_MODEL_MISSING")
        return 1
    with tempfile.TemporaryDirectory(prefix="aram-oracle-ppocr-") as folder:
        directory = Path(folder)
        subprocess.run([
            sys.executable, "-m", "pip", "download", "--no-deps",
            "--only-binary=:all:", "--disable-pip-version-check",
            "--dest", str(directory), "rapidocr-onnxruntime==1.4.4"
        ], check=True)
        wheels = list(directory.glob("rapidocr_onnxruntime-1.4.4-*.whl"))
        if len(wheels) != 1:
            raise ValueError("Expected exactly one pinned wheel")
        extract_verified_model(wheels[0], destination)
    print("PPOCRV4_MODEL_INSTALLED_AND_VERIFIED")
    print("Restart ARAM Oracle: PP-OCRv4 is used automatically "
          "(ARAM_ORACLE_OCR_ENGINE=tesseract forces the old engine).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
