"""Framing maths against the synthetic subject's ground-truth landmarks.

The example portrait's landmarks are exact (they are the constants the drawing
code positioned the features with), so any regression here is measurable.
"""

import pytest
from PIL import Image

from passportphoto import compose
from passportphoto.landmarks import Landmarks
from passportphoto.specs import get_spec


def _landmarks(extra: dict | None = None) -> Landmarks:
    return Landmarks.from_dict(
        {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512, **(extra or {})}
    )


def test_us_ground_truth_passes_all_checks():
    spec = get_spec("us")
    source = Image.open("subjects/example/source/portrait.jpg")
    framing = compose.plan(spec, _landmarks(), source.size)
    assert all(check.ok for check in compose.validate(spec, framing)), [
        check.format() for check in compose.validate(spec, framing)
    ]


def test_eye_rule_pins_eye_line_to_spec_midpoint():
    spec = get_spec("us")
    framing = compose.plan(spec, _landmarks(), (3024, 4032))
    assert spec.mm(framing.eye_from_bottom_px) == spec.eye_target_mm


def test_scale_comes_from_head_height_rule():
    spec = get_spec("us")
    framing = compose.plan(spec, _landmarks(), (3024, 4032))
    assert framing.scale == spec.px(spec.head_target_mm) / 1000.0


def test_face_midline_lands_on_photo_centre():
    spec = get_spec("us")
    framing = compose.plan(spec, _landmarks(), (3024, 4032))
    assert framing.center_x == spec.width_px / 2


def test_crown_gap_fallback_for_specs_without_eye_rule():
    spec = get_spec("schengen")
    assert spec.eye_target_mm is None
    framing = compose.plan(spec, _landmarks(), (3024, 4032))
    assert framing.crown_y == pytest.approx(framing.out_h * spec.crown_gap_frac)
    assert all(check.ok for check in compose.validate(spec, framing))


def test_all_specs_frame_without_padding_on_example():
    source = Image.open("subjects/example/source/portrait.jpg")
    for key in (
        "us", "india_passport", "india_visa", "schengen", "uk", "canada",
        "australia", "japan", "china_visa", "icao", "linkedin_headshot",
    ):
        spec = get_spec(key)
        framing = compose.plan(spec, _landmarks(), source.size)
        assert not framing.padded, key


def test_crop_off_source_edge_pads_instead_of_nudging():
    spec = get_spec("us")
    framing = compose.plan(spec, _landmarks({"center": 100}), (3024, 4032))
    assert framing.padded
    # The midline still maps to the photo centre: framing stays correct.
    assert framing.center_x == spec.width_px / 2
