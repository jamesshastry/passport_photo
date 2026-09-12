"""Optional auto-detection of landmarks and cutout matte.

This module is a genuine extra: it imports ``cv2`` and ``rembg`` lazily, so
the manual Pillow+numpy path keeps working untouched when they are not
installed. Install with::

    pip install passportphoto[auto]

Landmarks come from a YuNet face detector (box + five keypoints); the model
is fetched once into the user cache on first use.

Accuracy caveat (read this): face detectors follow the *visible face*, not the
hair. They routinely clip dark or voluminous hair, and the crown — top of the
head *including hair* — is exactly the measurement a print rejection turns on.
So detection output is a **first draft**. The detected crown is deliberately
expanded upward by ``CROWN_EXPANSION_FRAC`` of the face height and flagged as
an estimate; always confirm with the spec-check overlay (``make`` draws it)
and fix the numbers with ``passportphoto grid`` before paying for prints.
"""

from __future__ import annotations

import importlib
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

from .landmarks import Landmarks

# YuNet face-detection model (OpenCV zoo), fetched once into the user cache.
MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
    "face_detection_yunet_2023mar.onnx"
)
MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
# Faces below this confidence are ignored; the best of the rest wins.
MIN_SCORE = 0.5

# How far above the detected face top to place the crown guess, as a fraction
# of the detected face height. Deliberately generous: an over-tall head-height
# fails loudly on the spec check, while a clipped crown fails silently at the
# passport office.
CROWN_EXPANSION_FRAC = 0.18


def _require(module: str, pip_name: str | None = None):
    try:
        return importlib.import_module(module)
    except ImportError:
        raise RuntimeError(
            f"auto-detection needs the {pip_name or module!r} package - "
            f"pip install 'passportphoto[auto]'"
        ) from None


def _model_path() -> Path:
    """The detector bundle, downloading it once on first use."""
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    dest = cache / "passportphoto" / MODEL_FILENAME
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print("downloading face-detector model (one time, ~1 MB) ...",
              file=sys.stderr)
        urllib.request.urlretrieve(MODEL_URL, dest)
    return dest


def detect_landmarks(source: Image.Image) -> tuple[Landmarks, dict]:
    """Estimate landmarks with a YuNet face detector.

    Returns (landmarks, meta) where meta records which values are estimates.
    Raises ValueError when no face is found.
    """
    cv2 = _require("cv2", pip_name="opencv-python")
    import numpy as np

    w, h = source.size
    detector = cv2.FaceDetectorYN.create(str(_model_path()), "", (w, h))
    _retval, faces = detector.detect(np.asarray(source.convert("RGB")))
    rows = faces if faces is not None else []
    faces = [f for f in rows if f[14] >= MIN_SCORE]
    if not faces:
        raise ValueError("no face found in the input image")
    # Best face wins; columns are x, y, w, h, right eye, left eye, nose,
    # mouth corners, score.
    box = max(faces, key=lambda f: f[14])
    # Order the eyes by image x rather than trusting the model's left/right
    # labels, so the roll sign is always geometrically correct.
    (ex1, ey1), (ex2, ey2) = sorted(
        [(box[4], box[5]), (box[6], box[7])], key=lambda p: p[0]
    )
    lx, ly, rx, ry = (float(v) for v in (ex1, ey1, ex2, ey2))
    eye_y = (ly + ry) / 2
    center_x = (lx + rx) / 2

    # The box tracks skin, not hair: top is roughly the forehead, chin is the
    # box bottom. Guess the crown above the box top.
    top = float(box[1])
    chin = float(box[1] + box[3])
    face_h = chin - top

    # The mesh tracks skin, not hair: guess the crown above the face top.
    crown = max(0.0, top - CROWN_EXPANSION_FRAC * face_h)

    landmarks = Landmarks(
        crown_y=crown,
        chin_y=chin,
        eye_y=eye_y,
        center_x=center_x,
        eye_left_x=lx,
        eye_left_y=ly,
        eye_right_x=rx,
        eye_right_y=ry,
    )
    meta = {"crown": "estimated (detectors clip hair - verify before printing)",
            "chin/eyes/midline": "detected"}
    return landmarks, meta


def detect_matte(source: Image.Image) -> Image.Image:
    """Cut the subject out with rembg. Returns a greyscale (L) matte."""
    rembg = _require("rembg")
    rgba = rembg.remove(source.convert("RGB"))
    return rgba.getchannel("A")


def draft_subject(
    name: str,
    spec_key: str,
    landmarks: Landmarks,
    with_matte: bool = True,
) -> dict:
    """Build a subject.json dict from detected values, for the user to edit."""
    lm: dict = {
        "crown": round(landmarks.crown_y, 1),
        "chin": round(landmarks.chin_y, 1),
        "eye": round(landmarks.eye_y, 1),
        "center": round(landmarks.center_x, 1),
    }
    if landmarks.eye_left_x is not None:
        lm["eyes"] = [
            [round(landmarks.eye_left_x, 1), round(landmarks.eye_left_y, 1)],
            [round(landmarks.eye_right_x, 1), round(landmarks.eye_right_y, 1)],
        ]
    background: dict = (
        {"mode": "matte", "matte": "source/matte.png"}
        if with_matte
        else {"mode": "keep"}
    )
    return {
        "_comment": [
            "DRAFT from `passportphoto detect` - the crown is an estimate,",
            "detectors clip hair. Confirm with the spec-check overlay and",
            "fix the numbers (see `passportphoto grid`) before printing.",
        ],
        "name": name,
        "spec": spec_key,
        "input": "source/portrait.jpg",
        "outdir": "output",
        "landmarks": lm,
        "background": background,
        "sheets": ["4x6"],
    }


def run_detect(
    input_path: Path,
    dest_dir: Path,
    name: str,
    spec_key: str,
    with_matte: bool = True,
) -> list[Path]:
    """Detect landmarks (+matte) and write a draft subject folder."""
    import json

    source = Image.open(input_path)
    source.load()
    landmarks, _meta = detect_landmarks(source)

    src_dir = dest_dir / "source"
    src_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if with_matte:
        matte = detect_matte(source)
        matte_path = src_dir / "matte.png"
        matte.save(matte_path)
        written.append(matte_path)

    config = dest_dir / f"{name}.json"
    config.write_text(
        json.dumps(draft_subject(name, spec_key, landmarks, with_matte), indent=2)
        + "\n",
        encoding="utf-8",
    )
    written.append(config)
    return written
