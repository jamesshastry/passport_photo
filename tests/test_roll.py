"""Roll correction: a synthetically tilted head gets straightened."""

import math

import pytest

from passportphoto import pipeline
from passportphoto.landmarks import Landmarks
from passportphoto.specs import get_spec


def test_roll_angle_comes_from_the_two_pupils():
    tilted = Landmarks.from_dict(
        {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512,
         "eyes": [[1400, 1360], [1624, 1400]]}
    )
    assert tilted.roll_degrees == math.degrees(math.atan2(40, 224))
    assert Landmarks.from_dict(
        {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512}
    ).roll_degrees == 0.0


def test_rotated_landmarks_level_the_pupils():
    tilted = Landmarks.from_dict(
        {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512,
         "eyes": [[1400, 1360], [1624, 1400]]}
    )
    pivot = (tilted.center_x, tilted.eye_y)
    levelled = tilted.rotated(tilted.roll_degrees, pivot)
    assert levelled.eye_left_y == levelled.eye_right_y == pytest.approx(
        tilted.eye_y
    )


def test_pipeline_records_roll_and_still_passes(tmp_path, example_dir):
    spec = get_spec("us")
    job = pipeline.Job(
        input_path=example_dir / "source" / "portrait.jpg",
        spec=spec,
        landmarks=Landmarks.from_dict(
            {"crown": 900, "chin": 1900, "center": 1512,
             "eyes": [[1400, 1360], [1624, 1400]]}
        ),
        outdir=tmp_path,
        name="tilted",
        bg_mode="matte",
        matte_path=example_dir / "source" / "matte.png",
        sheets=(),
        before_after=False,
        spec_check=False,
        proof=False,
    )
    result = pipeline.run(job)
    assert result.framing is not None
    report = (tmp_path / "tilted_us_report.json").read_text()
    assert '"roll_corrected_degrees"' in report
    assert all(check.ok for check in result.checks)
