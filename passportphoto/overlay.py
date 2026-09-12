"""Diagnostic overlays: the spec-check proof and the landmark-measuring grid."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .compose import Framing
from .specs import MM_PER_INCH, Spec

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fmt(spec: Spec, mm: float) -> str:
    if spec.units == "in":
        return f'{mm / MM_PER_INCH:.3f}"'
    return f"{mm:.1f}mm"


def spec_check(photo: Image.Image, spec: Spec, framing: Framing) -> Image.Image:
    """Annotate the finished photo with the lines an examiner would draw.

    Green = measured landmark. Blue = the tolerance band the landmark must fall
    inside. A green line outside its blue band is a reprint.
    """
    canvas = photo.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = load_font(max(11, canvas.width // 45))
    w, h = canvas.size

    def band(top_px: float, bottom_px: float, color: tuple[int, int, int]) -> None:
        draw.rectangle([0, top_px, w - 1, bottom_px], fill=(*color, 38), outline=(*color, 200))

    # Tolerance band for the eye line, measured up from the bottom edge.
    if spec.eye_min_mm is not None and spec.eye_max_mm is not None:
        band(h - spec.px(spec.eye_max_mm), h - spec.px(spec.eye_min_mm), (0, 120, 220))
        draw.text(
            (6, h - spec.px(spec.eye_max_mm) - font.size - 3),
            f"eye zone {_fmt(spec, spec.eye_min_mm)}-{_fmt(spec, spec.eye_max_mm)} from bottom",
            fill=(0, 90, 190),
            font=font,
        )

    # Tolerance band for head height, anchored at the measured chin. The crown
    # line has to land inside it.
    head_band_top = framing.chin_y - spec.px(spec.head_max_mm)
    head_band_bottom = framing.chin_y - spec.px(spec.head_min_mm)
    band(head_band_top, head_band_bottom, (150, 0, 180))
    draw.text(
        (6, max(2.0, head_band_bottom) + 3),
        f"crown zone: head {_fmt(spec, spec.head_min_mm)}-{_fmt(spec, spec.head_max_mm)}",
        fill=(130, 0, 160),
        font=font,
    )

    for y, color, label in (
        (framing.crown_y, (220, 30, 30), "crown"),
        (framing.eye_y, (0, 150, 60), "eye line"),
        (framing.chin_y, (0, 150, 60), "chin"),
    ):
        draw.line([(0, y), (w, y)], fill=color, width=2)
        draw.text((6, y + 3), label, fill=color, font=font)

    draw.line([(framing.center_x, 0), (framing.center_x, h)], fill=(255, 160, 0, 170), width=1)

    head_mm = spec.mm(framing.head_px)
    lines = [
        f"{spec.name}",
        f"print {spec.describe_size()} @ {spec.dpi}dpi = {w}x{h}px",
        f"head {_fmt(spec, head_mm)} (spec {_fmt(spec, spec.head_min_mm)}-{_fmt(spec, spec.head_max_mm)})",
    ]
    if spec.eye_min_mm is not None:
        eye_mm = spec.mm(framing.eye_from_bottom_px)
        lines.append(
            f"eye {_fmt(spec, eye_mm)} (spec {_fmt(spec, spec.eye_min_mm)}-{_fmt(spec, spec.eye_max_mm)})"
        )

    pad = 6
    box_h = len(lines) * (font.size + 4) + pad * 2
    draw.rectangle([0, h - box_h, w, h], fill=(255, 255, 255, 205))
    for i, line in enumerate(lines):
        draw.text((pad, h - box_h + pad + i * (font.size + 4)), line, fill=(20, 20, 20), font=font)
    return canvas


def coordinate_grid(image: Image.Image, step: int = 200, max_width: int = 1600) -> Image.Image:
    """Overlay a labelled pixel grid so landmarks can be read off by eye.

    Labels always carry SOURCE pixel coordinates even when the preview has been
    scaled down, so the numbers can be typed straight into ``--landmarks``.
    """
    src_w, src_h = image.size
    scale = min(1.0, max_width / src_w)
    preview = image.convert("RGB")
    if scale < 1.0:
        preview = preview.resize((round(src_w * scale), round(src_h * scale)), Image.LANCZOS)

    draw = ImageDraw.Draw(preview, "RGBA")
    font = load_font(13)
    minor = max(1, step // 4)

    for x in range(0, src_w, minor):
        px = x * scale
        major = x % step == 0
        draw.line([(px, 0), (px, preview.height)], fill=(255, 0, 0, 110 if major else 40), width=1)
        if major:
            draw.text((px + 2, 2), str(x), fill=(255, 255, 255), font=font,
                      stroke_width=2, stroke_fill=(0, 0, 0))

    for y in range(0, src_h, minor):
        py = y * scale
        major = y % step == 0
        draw.line([(0, py), (preview.width, py)], fill=(255, 0, 0, 110 if major else 40), width=1)
        if major:
            draw.text((2, py + 2), str(y), fill=(255, 255, 255), font=font,
                      stroke_width=2, stroke_fill=(0, 0, 0))

    return preview
