import pytest


@pytest.fixture(autouse=True)
def _clear_scaling_specs():
    from backend.engine.scoring import set_scaling_specs
    set_scaling_specs({})
    yield
    set_scaling_specs({})


def require_tesseract_or_skip():
    """Require runnable English Tesseract in CI; skip only on local machines."""
    import os
    import shutil
    from pathlib import Path

    import pytesseract

    binary = shutil.which("tesseract")
    if binary is None and os.name == "nt":
        standard = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if standard.is_file():
            binary = str(standard)

    def unavailable(reason: str):
        message = f"A2 real-title OCR requires Tesseract with English data: {reason}"
        if os.environ.get("ARAM_REQUIRE_TESSERACT") == "1":
            pytest.fail(message, pytrace=False)
        pytest.skip(message)

    if binary is None:
        unavailable("executable not found")

    # Tesseract installed in Program Files may not yet be on the CI process
    # PATH. Point pytesseract at the validated executable explicitly.
    pytesseract.pytesseract.tesseract_cmd = binary
    try:
        pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages(config="")
    except (OSError, RuntimeError, pytesseract.TesseractError) as exc:
        unavailable(f"executable/language probe failed ({type(exc).__name__})")
    if "eng" not in languages:
        unavailable("missing eng traineddata")
