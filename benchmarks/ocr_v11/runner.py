"""V1.1 isolated OCR benchmark. Test-first scaffold: intentionally incomplete."""
from pathlib import Path

def verify_asset(path: Path, sha256: str, size: int | None = None) -> None:
    return None

def validate_cases(cases: list[dict]) -> dict[str, int]:
    return {}

def validate_output_dimensions(model_version: str, labels: int, dictionary: int) -> None:
    return None

def classify(expected: str | None, actual: str | None, category: str) -> str:
    return "correct"

def assert_predictions(rows: list[dict]) -> None:
    return None
