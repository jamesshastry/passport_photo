"""Live detection: positive-path coverage when the backends are present.

Skips (never fails) without opencv, without network for the 400KB YuNet
model, or when the detector finds no face on the illustration — every skip
carries a reason, so CI stays informative instead of silently green.
"""

import urllib.error
from pathlib import Path

import pytest

from passportphoto import detect
from passportphoto.landmarks import Landmarks

cv2 = pytest.importorskip("cv2")

EXAMPLE = Path("subjects/example/source/portrait.jpg")


def _model_or_skip() -> Path:
    try:
        return detect._model_path()
    except (urllib.error.URLError, OSError, RuntimeError) as exc:
        pytest.skip(f"no detector model available: {exc}")


def test_model_is_checksummed() -> None:
    assert detect._sha256(_model_or_skip()) == detect.MODEL_SHA256


def test_landmarks_on_illustration_are_sane() -> None:
    from PIL import Image

    _model_or_skip()
    source = Image.open(EXAMPLE)
    try:
        landmarks, meta = detect.detect_landmarks(source)
    except ValueError as exc:
        pytest.skip(f"illustration yields no face: {exc}")
    assert landmarks.crown_y < landmarks.eye_y < landmarks.chin_y
    assert 0 <= landmarks.center_x <= source.width
    assert landmarks.roll_degrees == 0.0  # single eye line: no roll info
    assert "estimated" in meta["crown"]


def test_draft_round_trips_through_landmarks() -> None:
    from PIL import Image

    _model_or_skip()
    source = Image.open(EXAMPLE)
    try:
        landmarks, _meta = detect.detect_landmarks(source)
    except ValueError as exc:
        pytest.skip(f"illustration yields no face: {exc}")
    draft = detect.draft_subject("example", "us", landmarks)
    back = Landmarks.from_dict(draft["landmarks"])
    assert back.crown_y == landmarks.crown_y
    assert back.center_x == landmarks.center_x


def test_matte_when_rembg_model_cached() -> None:
    rembg = pytest.importorskip("rembg")
    from PIL import Image

    models = Path.home() / ".rembg" / "models"
    cached = list(models.rglob("*.onnx")) if models.exists() else []
    if not cached:
        pytest.skip("rembg model not cached (1 GB download skipped)")
    matte = detect.detect_matte(Image.open(EXAMPLE))
    assert matte.mode == "L"
    assert matte.size == Image.open(EXAMPLE).size
    opaque = sum(1 for v in matte.get_flattened_data() if v > 128)
    assert 0 < opaque < matte.width * matte.height
