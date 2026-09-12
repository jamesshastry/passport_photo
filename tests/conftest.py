"""Shared fixtures: repo-root-relative paths to the synthetic example subject."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def example_dir() -> Path:
    return ROOT / "subjects" / "example"


@pytest.fixture()
def example_config(example_dir: Path) -> Path:
    return example_dir / "subject.json"


@pytest.fixture()
def example_landmarks() -> dict:
    # Ground truth from subjects/example/make_source.py constants.
    return {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512}
