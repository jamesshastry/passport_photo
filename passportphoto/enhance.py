"""Tonal adjustments.

Deliberately conservative. Passport photos are rejected for looking retouched,
so nothing here reshapes the face or smooths skin - it only fixes exposure
problems that came from the original capture.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass(frozen=True)
class Adjustments:
    fill_light: float = 0.0  # 0..1  lift shadows only
    brightness: float = 1.0  # 1.0 = unchanged
    contrast: float = 1.0
    saturation: float = 1.0
    sharpen: float = 0.0  # 0..1  unsharp mask strength

    @property
    def is_identity(self) -> bool:
        return (
            self.fill_light == 0.0
            and self.brightness == 1.0
            and self.contrast == 1.0
            and self.saturation == 1.0
            and self.sharpen == 0.0
        )


def apply_fill_light(image: Image.Image, amount: float) -> Image.Image:
    """Open up shadows without blowing out the highlights.

    Works on luminance: a gamma lift is computed for the whole frame, then
    weighted by how dark each pixel already is. Highlights get a weight near
    zero, so a face lit from one side evens out while the white background
    stays white.
    """
    if amount <= 0:
        return image
    amount = float(np.clip(amount, 0.0, 1.0))
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

    gamma = 1.0 - 0.6 * amount  # <1 brightens
    lifted = np.power(np.clip(luma, 1e-6, 1.0), gamma)
    weight = (1.0 - luma) ** 2  # shadow-weighted, zero at pure white
    target = luma + (lifted - luma) * weight

    gain = np.divide(target, luma, out=np.ones_like(luma), where=luma > 1e-4)
    out = np.clip(rgb * gain[..., None], 0.0, 1.0)
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), mode="RGB")


def apply(image: Image.Image, adj: Adjustments) -> Image.Image:
    """Run the full adjustment chain in a fixed, sensible order."""
    if adj.is_identity:
        return image
    out = apply_fill_light(image, adj.fill_light)
    if adj.brightness != 1.0:
        out = ImageEnhance.Brightness(out).enhance(adj.brightness)
    if adj.contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(adj.contrast)
    if adj.saturation != 1.0:
        out = ImageEnhance.Color(out).enhance(adj.saturation)
    if adj.sharpen > 0:
        out = out.filter(
            ImageFilter.UnsharpMask(radius=1.6, percent=int(120 * adj.sharpen), threshold=3)
        )
    return out


def side_by_side(before: Image.Image, after: Image.Image, gap: int = 16) -> Image.Image:
    """Stitch a before/after proof at a shared height."""
    height = max(before.height, after.height)

    def fit(img: Image.Image) -> Image.Image:
        if img.height == height:
            return img.convert("RGB")
        width = round(img.width * height / img.height)
        return img.convert("RGB").resize((width, height), Image.LANCZOS)

    left, right = fit(before), fit(after)
    canvas = Image.new("RGB", (left.width + gap + right.width, height), "#FFFFFF")
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))
    return canvas
