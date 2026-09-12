"""Validate a finished photo: dimensions are hard, the rest is advisory."""

from PIL import Image, ImageFilter

from passportphoto import validate as check
from passportphoto.specs import get_spec


def test_correct_photo_passes_all():
    photo = Image.open("samples/sample_us_2x2.png")
    findings = check.validate_photo(photo, get_spec("us"))
    assert all(f.status == "PASS" for f in findings)
    assert {f.label for f in findings} == {
        "dimensions", "background colour", "sharpness",
    }


def test_wrong_spec_fails_dimensions_only():
    photo = Image.open("samples/sample_us_2x2.png")
    findings = check.validate_photo(photo, get_spec("schengen"))
    by_label = {f.label: f for f in findings}
    assert by_label["dimensions"].status == "FAIL"
    assert "413x531" in by_label["dimensions"].detail
    assert by_label["sharpness"].status == "PASS"


def test_tinted_background_warns_not_fails():
    photo = Image.new("RGB", (600, 600), "#FFE0C0")
    findings = check.validate_photo(photo, get_spec("us"))
    by_label = {f.label: f for f in findings}
    assert by_label["dimensions"].status == "PASS"
    assert by_label["background colour"].status == "WARN"
    assert all(f.ok for f in findings)


def test_blurry_photo_warns_on_sharpness():
    photo = Image.open("samples/sample_us_2x2.png").filter(ImageFilter.GaussianBlur(8))
    findings = check.validate_photo(photo, get_spec("us"))
    by_label = {f.label: f for f in findings}
    assert by_label["sharpness"].status == "WARN"
    assert "retake" in by_label["sharpness"].detail


def test_finding_format_and_ok():
    assert check.Finding("x", "y", "PASS").ok
    assert check.Finding("x", "y", "WARN").ok
    assert not check.Finding("x", "y", "FAIL").ok
    assert check.Finding("dims", "600x600", "PASS").format() == (
        "[PASS] dims: 600x600"
    )
