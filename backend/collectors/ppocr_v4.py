"""Opt-in PP-OCRv4 title recognition; isolated from screen capture and gameplay.

The exact SHA-pinned V1.1 fixed-width RGB/PIL ONNX configuration is
used here. Nothing is downloaded during gameplay. Existing strict 90/8
matching, three physical slots, capture proofs and epoch rules own acceptance.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import logging
import os
from pathlib import Path
import re
import statistics

from PIL import Image

MODEL_SHA256 = "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
MODEL_BYTES = 10_857_958
INPUT_HEIGHT = 48
INPUT_WIDTH = 448
_LOG = logging.getLogger("aram-oracle.ocr.v4")
_reported_unavailable = False


def default_model_path() -> Path:
    """Model remains in per-user data, outside the public Git repository."""
    override = os.environ.get("ARAM_ORACLE_PPOCRV4_MODEL")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return root / "ARAMOracle" / "models" / "ppocrv4.onnx"


def verify_model(path: Path) -> Path:
    """Refuse incorrect model bytes before building an inference session."""
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size != MODEL_BYTES:
            raise ValueError("PP-OCRv4 model integrity: size or file missing")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise ValueError("PP-OCRv4 model integrity: SHA-256 mismatch")
    except OSError as exc:
        raise ValueError("PP-OCRv4 model integrity: read failed") from exc
    return path


def split_title_lines(image: Image.Image) -> list[Image.Image]:
    """Historical V1.1 line projection, applied only to approved title bands."""
    import numpy as np

    gray = np.asarray(image.convert("L"), dtype=np.float32)
    if gray.ndim != 2 or not gray.size:
        return []
    rows = (gray > 150).sum(1) > 2
    segments: list[tuple[int, int]] = []
    start = None
    for y, active in enumerate(list(rows) + [False]):
        if active and start is None:
            start = y
        elif not active and start is not None:
            if y - start >= 6:
                segments.append((start, y))
            start = None
    if not segments:
        return []
    xs = np.where((gray > 150).sum(0) > 0)[0]
    if len(xs) == 0:
        return []
    return [
        image.crop((
            max(0, int(xs.min()) - 6), max(0, y0 - 4),
            min(image.width, int(xs.max()) + 6), min(image.height, y1 + 4),
        ))
        for y0, y1 in segments
    ]


def decode_ctc(logits, dictionary: list[str]) -> tuple[str, float]:
    """Only the pinned blank + dictionary + terminal-space CTC layout."""
    import numpy as np

    values = np.asarray(logits)
    if (values.ndim != 2 or values.shape[0] < 1
            or values.shape[1] != len(dictionary) + 2
            or not np.isfinite(values).all()):
        raise ValueError("PP-OCRv4 decoder incompatible with pinned model")
    chars = [""] + list(dictionary) + [" "]
    best = values.argmax(axis=1)
    scores = values.max(axis=1)
    last = 0
    emitted: list[str] = []
    confidence: list[float] = []
    for raw_index, raw_confidence in zip(best, scores):
        index = int(raw_index)
        if index != last and index != 0:
            emitted.append(chars[index])
            confidence.append(float(raw_confidence))
        last = index
    return "".join(emitted).strip(), (
        statistics.mean(confidence) if confidence else 0.0
    )


class PPOCRv4Recognizer:
    """One single-thread CPU session and a checked model-specific decoder."""

    def __init__(self, model_path: Path):
        path = verify_model(model_path)
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("PP-OCRv4 optional onnxruntime is missing") from exc

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs = session.get_inputs()
        if len(inputs) != 1:
            raise ValueError("PP-OCRv4 incompatible input count")
        shape = inputs[0].shape
        if (len(shape) != 4
                or (isinstance(shape[1], int) and shape[1] != 3)
                or (isinstance(shape[2], int) and shape[2] != INPUT_HEIGHT)
                or (isinstance(shape[3], int) and shape[3] != INPUT_WIDTH)):
            raise ValueError("PP-OCRv4 incompatible input shape")
        metadata = session.get_modelmeta().custom_metadata_map or {}
        if "character" not in metadata:
            raise ValueError("PP-OCRv4 decoder missing embedded dictionary")
        dictionary = metadata["character"].splitlines()
        if not dictionary:
            raise ValueError("PP-OCRv4 decoder empty embedded dictionary")
        self.session = session
        self.input_name = inputs[0].name
        self.dictionary = dictionary

    def rec(self, image: Image.Image) -> tuple[str, float]:
        import numpy as np

        image = image.convert("RGB")
        width = max(1, min(
            INPUT_WIDTH, round(image.width * INPUT_HEIGHT / image.height)
        ))
        resized = image.resize((width, INPUT_HEIGHT), Image.Resampling.BILINEAR)
        arr = np.asarray(resized, dtype=np.float32) / 255.0
        tensor = np.zeros((1, 3, INPUT_HEIGHT, INPUT_WIDTH), dtype=np.float32)
        tensor[0, :, :, :width] = ((arr - 0.5) / 0.5).transpose(2, 0, 1)
        outputs = self.session.run(None, {self.input_name: tensor})
        if not outputs:
            raise ValueError("PP-OCRv4 decoder empty inference output")
        logits = np.asarray(outputs[0])
        if logits.ndim != 3 or logits.shape[0] != 1:
            raise ValueError("PP-OCRv4 decoder incompatible output dimensions")
        return decode_ctc(logits[0], self.dictionary)


@lru_cache(maxsize=1)
def _session(model: str) -> PPOCRv4Recognizer:
    return PPOCRv4Recognizer(Path(model))


def engine_in_use() -> str:
    """Diagnostics: which title recognizer this process is actually using."""
    if _reported_unavailable:
        return "tesseract"
    return "ppocrv4" if _session.cache_info().currsize else "unknown"


def recognize_text(image: Image.Image) -> str | None:
    """Return None only if v4 cannot run, empty string for a safe OCR abstention.

    A failed/unavailable model falls back to the existing Tesseract path.
    Successfully executed v4 with unknown words must NOT silently accept a
    different engine's unverified guess.
    """
    global _reported_unavailable
    if _reported_unavailable:
        return None  # checked once per process; Tesseract keeps working
    try:
        recognizer = _session(str(default_model_path()))
        parts = []
        for segment in split_title_lines(image):
            raw, confidence = recognizer.rec(segment)
            if confidence >= 0.5 and len(re.sub(r"[^a-z0-9]", "", raw.casefold())) >= 2:
                parts.append(raw)
        return " ".join(parts).strip()
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        if not _reported_unavailable:
            _LOG.warning("PP-OCRv4 unavailable (%s); using existing OCR engine", type(exc).__name__)
            _reported_unavailable = True
        return None
