"""D5a offline regression cases for truthful OCR setup diagnostics.

Dependency readiness is not evidence of accurate League card recognition.
"""
from types import SimpleNamespace

from backend.api import server
from backend.collectors import screen_ocr


def test_missing_python_ocr_dependencies_fail_closed(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", False)
    status = screen_ocr.readiness_status()
    assert status["available"] is False
    assert status["reason"] == "python_dependencies_missing"
    assert "application" in status["next_step"].lower()
    assert screen_ocr.is_available() is False


def test_missing_tesseract_executable_has_install_guidance(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.delenv("TESSERACT_PATH", raising=False)
    monkeypatch.setattr(screen_ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: (_ for _ in ()).throw(OSError("private path"))
    ))
    status = screen_ocr.readiness_status()
    assert status["available"] is False
    assert status["reason"] == "executable_unavailable"
    assert "Tesseract" in status["next_step"]
    assert "private path" not in str(status)
    assert screen_ocr.is_available() is False


def test_nonworking_explicit_tesseract_path_is_actionable_without_echoing_path(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setenv("TESSERACT_PATH", r"C:\\private\\player\\tesseract.exe")
    monkeypatch.setattr(screen_ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: (_ for _ in ()).throw(OSError("sensitive"))
    ))
    status = screen_ocr.readiness_status()
    assert status["reason"] == "configured_executable_unavailable"
    assert "TESSERACT_PATH" in status["next_step"]
    assert "private" not in str(status)
    assert "sensitive" not in str(status)


def test_detected_executable_reports_only_dependency_readiness(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: "5.5",
        get_languages=lambda config="": ["eng", "osd"],
    ))
    assert screen_ocr.readiness_status() == {
        "available": True,
        "reason": "ready",
        "next_step": "Tesseract is available. In-game card recognition still requires Windows validation.",
    }
    assert screen_ocr.is_available() is True


def test_status_endpoint_keeps_existing_fields_and_adds_bounded_guidance(monkeypatch):
    expected = {
        "available": False,
        "reason": "executable_unavailable",
        "next_step": "Install Tesseract and restart ARAM Oracle.",
    }
    monkeypatch.setattr(server.ocr_capture, "readiness_status", lambda: expected)
    response = server.ocr_status()
    assert response["available"] is False
    assert response["reason"] == expected["reason"]
    assert response["next_step"] == expected["next_step"]
    assert isinstance(response["enabled"], bool)
    assert "offer_state" in response


def test_executable_detected_without_english_traineddata_is_not_ocr_ready(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: "5.5",
        get_languages=lambda config="": ["osd"],
    ))
    status = screen_ocr.readiness_status()
    assert status["available"] is False
    assert status["reason"] == "english_language_missing"
    assert "eng" in status["next_step"]
    assert screen_ocr.is_available() is False


def test_language_probe_error_is_bounded_and_never_exposes_paths(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)

    def failing_languages(config=""):
        raise RuntimeError(r"C:\\private\\user\\tessdata")

    monkeypatch.setattr(screen_ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: "5.5",
        get_languages=failing_languages,
    ))
    status = screen_ocr.readiness_status()
    assert status["available"] is False
    assert status["reason"] == "language_probe_unavailable"
    assert "private" not in str(status)
    assert screen_ocr.is_available() is False
