"""Heuristic advisories for the finished photo: warnings only, never verdicts.

Shipped: glasses glare. Deliberately absent: mouth-open detection. It was
measured against a bearded real portrait and false-positived (dark stubble
reads as mouth interior under every band/threshold tried), so it failed the
gate this module sets for new heuristics: no detector ships on vibes.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from .compose import Framing
from .validate import Finding

# Fraction of very bright pixels inside the eye band that earns a warning.
# Calibrated on 600px US output: 0.03 on the clean sample, 0.00 on a real
# portrait, 0.37 with synthetic glare blobs.
GLARE_LUMA = 245.0
GLARE_WARN_FRAC = 0.15


def _crop(photo: Image.Image, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    rgb = np.asarray(photo.convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    xs = slice(max(0, int(x0)), min(w, int(x1)))
    ys = slice(max(0, int(y0)), min(h, int(y1)))
    return rgb[ys, xs]


def glare_fraction(photo: Image.Image, framing: Framing) -> float:
    """Share of near-white pixels in the eye band (glasses reflections)."""
    head = framing.head_px
    band = _crop(
        photo,
        framing.center_x - 0.21 * head,
        framing.eye_y - 0.08 * head,
        framing.center_x + 0.21 * head,
        framing.eye_y + 0.08 * head,
    )
    luma = band @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    return float((luma > GLARE_LUMA).mean())


def assess(photo: Image.Image, framing: Framing) -> list[Finding]:
    """Heuristic advisories. Empty when quiet; WARN at most, never FAIL."""
    findings: list[Finding] = []
    if glare_fraction(photo, framing) > GLARE_WARN_FRAC:
        findings.append(Finding(
            "glasses glare",
            "large bright patches across the eyes - reflections hide the eyes; "
            "retake without glasses or adjust the light",
            "WARN",
        ))
    return findings
