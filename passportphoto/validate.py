"""Validate a finished photo against a standard, without generating anything.

The print-shop use case: given a photo file (made by this tool or not), check
what can be checked without landmarks. Hard FAIL is reserved for what is
exactly measurable (pixel dimensions); everything else is a warning, because a
heuristic must never talk a user out of a compliant photo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .specs import Spec


@dataclass(frozen=True)
class Finding:
    """One verdict: ``status`` is PASS, WARN or FAIL."""

    label: str
    detail: str
    status: str

    @property
    def ok(self) -> bool:
        return self.status != "FAIL"

    def format(self) -> str:
        return f"[{self.status}] {self.label}: {self.detail}"


def _border_median(photo: Image.Image) -> tuple[float, float, float]:
    """Median colour of the frame edge, where the background should be."""
    rgb = np.asarray(photo.convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    strip = max(1, min(h, w) // 50)
    edge = np.concatenate([
        rgb[:strip].reshape(-1, 3),
        rgb[-strip:].reshape(-1, 3),
        rgb[:, :strip].reshape(-1, 3),
        rgb[:, -strip:].reshape(-1, 3),
    ])
    return tuple(float(v) for v in np.median(edge, axis=0))


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(float(int(value[i:i + 2], 16)) for i in (0, 2, 4))


def _laplacian_variance(photo: Image.Image) -> float:
    """Higher means sharper; a global blur metric, nothing face-specific."""
    grey = np.asarray(photo.convert("L"), dtype=np.float32)
    lap = (
        grey[:-2, 1:-1] + grey[2:, 1:-1] + grey[1:-1, :-2] + grey[1:-1, 2:]
        - 4 * grey[1:-1, 1:-1]
    )
    return float(lap.var())


# Mean-luminance gap between the left and right halves of the frame centre
# that earns a lighting warning. Calibrated: 0.2 on the even sample photo,
# ~12 on a mildly side-lit real portrait, ~40 on a harsh synthetic shadow.
# A warning, never a failure - faces are naturally asymmetric.
IMBALANCE_WARN = 12.0


def _side_imbalance(photo: Image.Image) -> float:
    """Left/right lighting gap over the central region, in luma units."""
    rgb = np.asarray(photo.convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    mid = luma[h // 5:4 * h // 5, w // 4:3 * w // 4]
    left, right = mid[:, :mid.shape[1] // 2], mid[:, mid.shape[1] // 2:]
    return float(abs(left.mean() - right.mean()))


def validate_photo(photo: Image.Image, spec: Spec) -> list[Finding]:
    """Inspect a finished photo. Pure function over pixels + spec."""
    findings: list[Finding] = []
    w, h = photo.size

    if (w, h) == (spec.width_px, spec.height_px):
        findings.append(Finding(
            "dimensions", f"{w}x{h}px matches {spec.describe_size()} @ {spec.dpi}dpi",
            "PASS",
        ))
    else:
        findings.append(Finding(
            "dimensions",
            f"{w}x{h}px, expected {spec.width_px}x{spec.height_px}px "
            f"({spec.describe_size()} @ {spec.dpi}dpi)",
            "FAIL",
        ))

    border = _border_median(photo)
    want = _hex_to_rgb(spec.background)
    distance = float(np.linalg.norm(np.subtract(border, want)))
    if distance <= 18.0:
        findings.append(Finding(
            "background colour",
            f"edge median #{int(border[0]):02X}{int(border[1]):02X}{int(border[2]):02X} "
            f"against required {spec.background}",
            "PASS",
        ))
    else:
        findings.append(Finding(
            "background colour",
            f"edge median looks off-spec (wanted {spec.background}) - "
            f"check for shadows or a tinted wall",
            "WARN",
        ))

    sharpness = _laplacian_variance(photo)
    if sharpness >= 20.0:
        findings.append(Finding("sharpness", "no significant blur detected", "PASS"))
    else:
        findings.append(Finding(
            "sharpness",
            "photo looks soft - it may have been upscaled or shot out of focus; "
            "retake rather than sharpen",
            "WARN",
        ))

    imbalance = _side_imbalance(photo)
    if imbalance <= IMBALANCE_WARN:
        findings.append(Finding("lighting balance", "evenly lit", "PASS"))
    else:
        findings.append(Finding(
            "lighting balance",
            f"one side is markedly brighter (gap {imbalance:.0f}) - "
            f"side shadows risk rejection; even out the light and retake",
            "WARN",
        ))

    return findings


def validate_file(path: Path | str, spec: Spec) -> tuple[list[Finding], Image.Image]:
    photo = Image.open(path)
    photo.load()
    return validate_photo(photo, spec), photo
