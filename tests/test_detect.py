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


def test_sha256_known_vector(tmp_path):
    target = tmp_path / "x.bin"
    target.write_bytes(b"abc")
    assert detect._sha256(target) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def _seed_cache(tmp_path, monkeypatch, payload: bytes):
    cache = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    dest = cache / "passportphoto" / detect.MODEL_FILENAME
    dest.parent.mkdir(parents=True)
    dest.write_bytes(payload)
    return dest


def test_model_path_accepts_matching_bytes_without_downloading(
    tmp_path, monkeypatch
):
    import hashlib

    payload = b"model bytes"
    monkeypatch.setattr(
        detect, "MODEL_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        detect, "_fetch",
        lambda dest: (_ for _ in ()).throw(AssertionError("must not download")),
    )
    dest = _seed_cache(tmp_path, monkeypatch, payload)
    assert detect._model_path() == dest


def test_model_path_refuses_tampered_bytes(tmp_path, monkeypatch):
    # Redownload disabled: a tampered file must fail loudly, not run.
    monkeypatch.setattr(detect, "_fetch", lambda dest: None)
    _seed_cache(tmp_path, monkeypatch, b"not the model")
    with pytest.raises(RuntimeError, match="checksum"):
        detect._model_path()


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
