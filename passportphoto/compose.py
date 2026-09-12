"""Framing: turn a source photo plus landmarks into a spec-compliant crop.

The whole job is one similarity transform. Scale is fixed by the head-height
rule, vertical offset by the eye-line rule (or by the crown-gap fallback for
standards that only specify head height), horizontal offset by the face
midline. Everything else - validation, overlays, print sheets - reads the
numbers this module produces.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .landmarks import Landmarks
from .specs import Check, Spec


@dataclass(frozen=True)
class Framing:
    """The resolved transform, plus where the landmarks land in the output."""

    scale: float
    crop_left: float
    crop_top: float
    crop_w: float
    crop_h: float
    out_w: int
    out_h: int
    crown_y: float
    chin_y: float
    eye_y: float
    center_x: float
    padded: bool

    @property
    def head_px(self) -> float:
        return self.chin_y - self.crown_y

    @property
    def eye_from_bottom_px(self) -> float:
        return self.out_h - self.eye_y


def plan(spec: Spec, lm: Landmarks, source_size: tuple[int, int]) -> Framing:
    """Work out the crop rectangle without touching pixels."""
    out_w, out_h = spec.width_px, spec.height_px
    scale = spec.px(spec.head_target_mm) / lm.head_px

    eye_target = spec.eye_target_mm
    if eye_target is not None:
        eye_out_y = out_h - spec.px(eye_target)
    else:
        gap = spec.crown_gap_frac if spec.crown_gap_frac is not None else 0.07
        crown_out_y = out_h * gap
        eye_out_y = crown_out_y + (lm.eye_y - lm.crown_y) * scale

    # Output point (center_x, eye_out_y) must map back to (lm.center_x, lm.eye_y).
    crop_left = lm.center_x - (out_w / 2) / scale
    crop_top = lm.eye_y - eye_out_y / scale
    crop_w = out_w / scale
    crop_h = out_h / scale

    src_w, src_h = source_size
    padded = (
        crop_left < 0 or crop_top < 0 or crop_left + crop_w > src_w or crop_top + crop_h > src_h
    )

    return Framing(
        scale=scale,
        crop_left=crop_left,
        crop_top=crop_top,
        crop_w=crop_w,
        crop_h=crop_h,
        out_w=out_w,
        out_h=out_h,
        crown_y=(lm.crown_y - crop_top) * scale,
        chin_y=(lm.chin_y - crop_top) * scale,
        eye_y=eye_out_y,
        center_x=out_w / 2,
        padded=padded,
    )


def render(image: Image.Image, framing: Framing, fill: str) -> Image.Image:
    """Apply the planned crop.

    ``Image.resize(box=...)`` accepts fractional coordinates and resamples in
    one pass, which keeps hair detail that a crop-then-resize would lose. When
    the crop runs off the edge of the source, the source is padded with the
    background colour first so the framing stays correct instead of being
    silently nudged back in bounds.
    """
    src = image.convert("RGB")
    left, top = framing.crop_left, framing.crop_top
    if framing.padded:
        pad_l = max(0, int(-left) + 1)
        pad_t = max(0, int(-top) + 1)
        pad_r = max(0, int(left + framing.crop_w - src.width) + 1)
        pad_b = max(0, int(top + framing.crop_h - src.height) + 1)
        padded = Image.new("RGB", (src.width + pad_l + pad_r, src.height + pad_t + pad_b), fill)
        padded.paste(src, (pad_l, pad_t))
        src = padded
        left += pad_l
        top += pad_t

    return src.resize(
        (framing.out_w, framing.out_h),
        Image.LANCZOS,
        box=(left, top, left + framing.crop_w, top + framing.crop_h),
    )


def validate(spec: Spec, framing: Framing) -> list[Check]:
    """Measure the rendered frame back against the standard."""
    checks = [
        Check(
            label="head height (chin to crown)",
            actual_mm=spec.mm(framing.head_px),
            min_mm=spec.head_min_mm,
            max_mm=spec.head_max_mm,
            dpi=spec.dpi,
        )
    ]
    if spec.eye_min_mm is not None and spec.eye_max_mm is not None:
        checks.append(
            Check(
                label="eye line above bottom edge",
                actual_mm=spec.mm(framing.eye_from_bottom_px),
                min_mm=spec.eye_min_mm,
                max_mm=spec.eye_max_mm,
                dpi=spec.dpi,
            )
        )
    # Every standard wants visible clearance above the hair.
    checks.append(
        Check(
            label="clearance above crown",
            actual_mm=spec.mm(framing.crown_y),
            min_mm=0.5,
            max_mm=spec.photo_h_mm * 0.25,
            dpi=spec.dpi,
        )
    )
    return checks
