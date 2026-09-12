"""Optional auto-detection of landmarks and cutout matte.

This module is a genuine extra: it imports ``mediapipe`` and ``rembg`` lazily,
so the manual Pillow+numpy path keeps working untouched when they are not
installed. Install with::

    pip install passportphoto[auto]

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
from pathlib import Path

from PIL import Image

from .landmarks import Landmarks

# How far above the detected face top to place the crown guess, as a fraction
# of the detected face height. Deliberately generous: an over-tall head-height
# fails loudly on the spec check, while a clipped crown fails silently at the
# passport office.
CROWN_EXPANSION_FRAC = 0.18


def _require(module: str):
    try:
        return importlib.import_module(module)
    except ImportError:
        raise RuntimeError(
            f"auto-detection needs the {module!r} package - "
            f"pip install 'passportphoto[auto]'"
        ) from None


def detect_landmarks(source: Image.Image) -> tuple[Landmarks, dict]:
    """Estimate landmarks with MediaPipe FaceMesh.

    Returns (landmarks, meta) where meta records which values are estimates.
    Raises ValueError when no face is found.
    """
    mp = _require("mediapipe")
    import numpy as np

    rgb = np.asarray(source.convert("RGB"))
    h, w = rgb.shape[:2]
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1, refine_landmarks=True
    ) as mesh:
        result = mesh.process(rgb)
    if not result.multi_face_landmarks:
        raise ValueError("no face found in the input image")
    pts = result.multi_face_landmarks[0].landmark
    xs = [p.x * w for p in pts]
    ys = [p.y * h for p in pts]

    # Face oval (MediaPipe's FACEMESH_FACE_OVAL connection set, as indices).
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
            397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
            172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    top = min(ys[i] for i in oval)
    chin = max(ys[i] for i in oval)
    face_h = chin - top

    def midpoint(a: int, b: int) -> tuple[float, float]:
        return ((xs[a] + xs[b]) / 2, (ys[a] + ys[b]) / 2)

    # Eye centres from the eye corners (outer, inner).
    lx, ly = midpoint(33, 133)
    rx, ry = midpoint(362, 263)
    eye_y = (ly + ry) / 2
    center_x = (lx + rx) / 2

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
