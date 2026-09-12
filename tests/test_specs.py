"""Spec loading and validation: specs.json stays data, not code."""

import json
from pathlib import Path

import pytest

from passportphoto.specs import get_spec, load_specs

EXPECTED_KEYS = {
    "us", "india_passport", "india_visa", "schengen", "uk", "canada",
    "australia", "japan", "china_visa", "icao", "linkedin_headshot",
}


def test_all_eleven_standards_load():
    assert set(load_specs()) == EXPECTED_KEYS


def test_comment_keys_are_skipped():
    raw = json.loads(Path("specs.json").read_text())
    assert "_comment" in raw
    assert "_comment" not in load_specs()


def test_unknown_spec_names_the_known_ones():
    with pytest.raises(KeyError, match="us"):
        get_spec("atlantis")


def test_head_target_defaults_to_midpoint_but_can_be_overridden():
    us = get_spec("us")
    assert us.head_target_mm == pytest.approx((us.head_min_mm + us.head_max_mm) / 2)
    headshot = get_spec("linkedin_headshot")
    assert headshot.head_target_mm == pytest.approx(33.0)


def test_eye_target_is_none_without_an_eye_rule():
    assert get_spec("us").eye_target_mm is not None
    assert get_spec("schengen").eye_target_mm is None


def test_at_dpi_rescales_pixels_but_keeps_millimetres():
    spec = get_spec("us")
    low = spec.at_dpi(150)
    assert (low.width_px, low.height_px) == (spec.width_px // 2, spec.height_px // 2)
    assert (low.head_min_mm, low.head_max_mm) == (spec.head_min_mm, spec.head_max_mm)


def test_every_spec_has_a_background_and_positive_geometry():
    for key, spec in load_specs().items():
        assert spec.background.startswith("#"), key
        assert spec.head_min_mm < spec.head_max_mm, key
        assert spec.photo_w_mm > 0 and spec.photo_h_mm > 0, key
