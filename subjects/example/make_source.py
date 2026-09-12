#!/usr/bin/env python3
"""Generate the synthetic example subject.

Renders an illustrated portrait against a deliberately busy background, plus the
exact alpha matte for it. Nobody real is depicted and nothing needs a licence,
which is what makes this safe to ship in a public repo.

Two properties make it a better test fixture than a real photo would be:

  * The matte is exact. It is the alpha channel the subject was drawn on, not a
    hand-cut approximation, so any fringing in the output is the pipeline's
    fault rather than the matte's.
  * The landmarks are known exactly, because they are the same numbers the
    drawing code positioned the features with. `landmarks.json` is written from
    those constants, so the geometry can be checked against ground truth.

Everything is drawn at half size and upscaled with Lanczos, which is a cheap way
to antialias - PIL's shape primitives have hard edges.

    python3 make_source.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
OUT = HERE / "source"

SS = 2  # supersample factor
W, H = 3024 // SS, 4032 // SS  # drawing canvas; final is 3024x4032

# --- the subject's geometry, in DRAWING coordinates -----------------------
# Landmarks are derived from these, then scaled by SS for the final image.
CENTER_X = W // 2
CROWN_Y = 450  # top of the hair - this is what a passport spec measures to
HEAD_TOP = 505  # top of the skull itself; only hair sits above it
HAIRLINE_Y = 580
EYE_Y = 690
CHIN_Y = 950
HEAD_W = 370

SKIN = (232, 187, 152)
SKIN_SHADE = (214, 165, 130)
HAIR = (58, 42, 34)
HAIR_HI = (74, 55, 45)
SHIRT = (47, 74, 122)
SHIRT_DARK = (36, 57, 96)
LIP = (186, 107, 98)
EYE_WHITE = (246, 244, 240)
IRIS = (84, 102, 88)


def draw_background(size: tuple[int, int]) -> Image.Image:
    """A busy outdoor-ish scene, so the example genuinely needs a matte."""
    w, h = size
    bg = Image.new("RGB", size)
    draw = ImageDraw.Draw(bg)

    horizon = int(h * 0.62)
    for y in range(horizon):  # sky gradient
        t = y / max(1, horizon)
        draw.line([(0, y), (w, y)], fill=(int(150 + 85 * t), int(186 + 58 * t), int(222 + 28 * t)))
    for y in range(horizon, h):  # ground gradient
        t = (y - horizon) / max(1, h - horizon)
        draw.line([(0, y), (w, y)], fill=(int(120 - 40 * t), int(140 - 45 * t), int(86 - 30 * t)))

    rng = _rng(20260912)
    for _ in range(220):  # foliage and blossoms
        cx = int(next(rng) * w)
        cy = horizon - int(next(rng) * h * 0.30) + int(next(rng) * h * 0.38)
        r = int(18 + next(rng) * 70)
        pick = next(rng)
        if pick < 0.62:
            color = (int(48 + next(rng) * 55), int(92 + next(rng) * 70), int(44 + next(rng) * 40))
        elif pick < 0.85:
            color = (int(198 + next(rng) * 50), int(70 + next(rng) * 60), int(96 + next(rng) * 60))
        else:
            color = (int(228 + next(rng) * 25), int(214 + next(rng) * 35), int(206 + next(rng) * 40))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    return bg.filter(ImageFilter.GaussianBlur(radius=3))


def draw_subject(size: tuple[int, int]) -> Image.Image:
    """The person, on transparency. The alpha channel becomes the matte."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = CENTER_X
    half = HEAD_W // 2
    shoulder_y = CHIN_Y + 165

    # Back to front. Getting this order wrong is what makes the hair swallow
    # the face: the long hair has to sit behind the head, and only the fringe
    # in front of it.

    # 1. Torso and shoulders, running off the bottom of the frame.
    d.rounded_rectangle([cx - 580, shoulder_y, cx + 580, size[1]], radius=200, fill=SHIRT)

    # 2. Hair falling past the shoulders, behind everything above the shirt.
    d.ellipse([cx - 258, HEAD_TOP + 20, cx + 258, CHIN_Y + 480], fill=HAIR)

    # 3. Neckline of the shirt, over the hair that crosses the chest.
    d.ellipse([cx - 128, shoulder_y - 28, cx + 128, shoulder_y + 176], fill=SHIRT_DARK)

    # 4. Neck, drawn before the head so the jaw overlaps it.
    d.rounded_rectangle(
        [cx - 76, CHIN_Y - 96, cx + 76, shoulder_y + 30], radius=58, fill=SKIN_SHADE
    )

    # 5. Ears, at eye level, peeking out at the edge of the face.
    for side in (-1, 1):
        ex = cx + side * (half - 8)
        d.ellipse([ex - 25, EYE_Y - 26, ex + 25, EYE_Y + 66], fill=SKIN_SHADE)

    # 6. The face itself: skull top down to chin, as one rounded form.
    d.ellipse([cx - half, HEAD_TOP, cx + half, CHIN_Y], fill=SKIN)

    # 7. Hair cap over the skull, then the forehead painted back over it -
    #    the top edge of that skin ellipse becomes the hairline.
    d.ellipse([cx - half - 22, CROWN_Y, cx + half + 22, HAIRLINE_Y + 210], fill=HAIR)
    d.ellipse([cx - half + 8, HAIRLINE_Y, cx + half - 8, CHIN_Y], fill=SKIN)
    d.ellipse([cx - 140, CROWN_Y + 34, cx - 6, CROWN_Y + 96], fill=HAIR_HI)

    # 8. Features.
    for side in (-1, 1):
        ex = cx + side * 84
        d.arc([ex - 54, EYE_Y - 74, ex + 54, EYE_Y - 6], start=205, end=335, fill=HAIR, width=10)
        d.ellipse([ex - 45, EYE_Y - 22, ex + 45, EYE_Y + 22], fill=EYE_WHITE)
        d.ellipse([ex - 19, EYE_Y - 19, ex + 19, EYE_Y + 19], fill=IRIS)
        d.ellipse([ex - 8, EYE_Y - 8, ex + 8, EYE_Y + 8], fill=(26, 22, 20))

    nose_y = EYE_Y + 98
    d.polygon([(cx, EYE_Y + 26), (cx - 28, nose_y), (cx + 28, nose_y)], fill=SKIN_SHADE)
    mouth_y = EYE_Y + 172
    d.chord([cx - 66, mouth_y - 38, cx + 66, mouth_y + 30], start=0, end=180, fill=LIP)

    return layer


def _rng(seed: int):
    """Deterministic 0..1 stream, so the fixture is byte-reproducible."""
    state = seed

    def nxt() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) % (1 << 31)
        return state / (1 << 31)

    return iter(nxt, None)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    size = (W, H)
    final = (W * SS, H * SS)

    subject = draw_subject(size)
    scene = draw_background(size)
    scene.paste(subject, (0, 0), subject)

    scene.resize(final, Image.LANCZOS).save(OUT / "portrait.jpg", quality=94)
    subject.getchannel("A").resize(final, Image.LANCZOS).save(OUT / "matte.png", optimize=True)

    landmarks = {
        "crown": CROWN_Y * SS,
        "chin": CHIN_Y * SS,
        "eye": EYE_Y * SS,
        "center": CENTER_X * SS,
    }
    (OUT / "landmarks.json").write_text(json.dumps(landmarks, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {OUT/'portrait.jpg'}  {final[0]}x{final[1]}")
    print(f"wrote {OUT/'matte.png'}")
    print(f"ground-truth landmarks: {landmarks}")


if __name__ == "__main__":
    main()
