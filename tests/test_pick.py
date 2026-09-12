"""Landmark picker page: embedded constants map display back to source px."""

import json
import re

import pytest
from PIL import Image

from passportphoto import pick as picker
from passportphoto.landmarks import Landmarks


def test_preview_scale_caps_the_long_edge():
    assert picker.preview_scale((3024, 4032)) == 1600 / 4032
    assert picker.preview_scale((600, 600)) == 1.0


def test_default_landmarks_span_the_frame():
    lm = picker.default_landmarks((1000, 2000))
    assert lm.crown_y < lm.eye_y < lm.chin_y
    assert lm.center_x == 500


def test_page_embeds_source_mapping():
    source = Image.open("subjects/example/source/portrait.jpg")
    landmarks = Landmarks.from_dict(
        {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512}
    )
    html = picker.build_page(source, landmarks, "us", "example")
    assert "data:image/jpeg;base64," in html
    assert "__INIT__" not in html and "__IMAGE__" not in html
    init = json.loads(re.search(r"const INIT = (\{.*?\});", html).group(1))
    assert init["sourceSize"] == [3024, 4032]
    assert init["spec"] == "us" and init["name"] == "example"
    # Display lines are source landmarks times the embedded scale ...
    scale = init["scale"]
    assert init["lines"]["crown"] == pytest.approx(900 * scale)
    assert init["lines"]["center"] == pytest.approx(1512 * scale)
    # ... so dividing display by scale recovers source pixels to 0.1px.
    assert init["lines"]["chin"] / scale == pytest.approx(1900, abs=0.11)


def test_page_has_no_external_dependencies():
    source = Image.open("subjects/example/source/portrait.jpg")
    html = picker.build_page(
        source, picker.default_landmarks(source.size), "us", "example"
    )
    assert re.search(r'src="https?://', html) is None
    assert re.search(r'href="https?://', html) is None
