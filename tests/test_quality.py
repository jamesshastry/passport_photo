"""Glasses-glare heuristic: quiet on clean photos, warns on reflections."""

from PIL import Image, ImageDraw

from passportphoto import compose, quality
from passportphoto.landmarks import Landmarks
from passportphoto.specs import get_spec


def _framing():
    spec = get_spec("us")
    return spec, compose.plan(
        spec,
        Landmarks.from_dict(
            {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512}
        ),
        (3024, 4032),
    )


def test_clean_sample_has_no_advisories():
    spec, framing = _framing()
    photo = Image.open("samples/sample_us_2x2.png")
    assert quality.assess(photo, framing) == []
    assert quality.glare_fraction(photo, framing) < quality.GLARE_WARN_FRAC


def test_glare_blobs_warn_but_never_fail():
    _spec, framing = _framing()
    photo = Image.open("samples/sample_us_2x2.png").convert("RGB")
    draw = ImageDraw.Draw(photo)
    draw.ellipse([220, 200, 300, 250], fill="white")
    draw.ellipse([320, 200, 400, 250], fill="white")
    advisories = quality.assess(photo, framing)
    assert len(advisories) == 1
    assert advisories[0].status == "WARN"
    assert "glare" in advisories[0].label
    assert all(a.ok for a in advisories)
