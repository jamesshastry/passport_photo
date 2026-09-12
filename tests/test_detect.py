"""Auto-detect module: pure parts testable without mediapipe/rembg installed."""

import pytest

from passportphoto import detect
from passportphoto.landmarks import Landmarks


def test_require_points_at_the_extra_for_missing_packages():
    with pytest.raises(RuntimeError, match=r"passportphoto\[auto\]"):
        detect._require("mediapipe_nonexistent_package_xyz")


def test_crown_expansion_is_generous_but_bounded():
    # The crown guess must sit clearly above the face (hair margin) without
    # implying an absurdly tall head.
    assert 0.10 <= detect.CROWN_EXPANSION_FRAC <= 0.30


def test_draft_subject_carries_detected_values_with_eyes():
    landmarks = Landmarks.from_dict(
        {"crown": 800, "chin": 1900, "eye": 1380, "center": 1512,
         "eyes": [[1400, 1360], [1624, 1400]]}
    )
    draft = detect.draft_subject("me", "us", landmarks)
    assert draft["landmarks"]["crown"] == 800
    assert draft["landmarks"]["eyes"] == [[1400, 1360], [1624, 1400]]
    assert draft["background"]["mode"] == "matte"
    assert "DRAFT" in draft["_comment"][0]


def test_draft_subject_without_matte_keeps_background():
    landmarks = Landmarks.from_dict(
        {"crown": 800, "chin": 1900, "eye": 1380, "center": 1512}
    )
    draft = detect.draft_subject("me", "us", landmarks, with_matte=False)
    assert draft["background"] == {"mode": "keep"}
    assert "eyes" not in draft["landmarks"]


def test_run_detect_without_extras_fails_cleanly(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    # Hide the backend even when it is installed, to exercise the
    # missing-extra path hermetically.
    monkeypatch.setitem(sys.modules, "cv2", None)
    with pytest.raises(RuntimeError, match=r"passportphoto\[auto\]"):
        detect.run_detect(
            Path("subjects/example/source/portrait.jpg"),
            tmp_path / "me", "me", "us",
        )
