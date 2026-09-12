"""Validate a finished photo: dimensions are hard, the rest is advisory."""

import numpy as np
from PIL import Image, ImageFilter

from passportphoto import validate as check
from passportphoto.specs import get_spec


def test_correct_photo_passes_all():
    photo = Image.open("samples/sample_us_2x2.png")
    findings = check.validate_photo(photo, get_spec("us"))
    assert all(f.status == "PASS" for f in findings)
    assert {f.label for f in findings} == {
        "dimensions", "background colour", "sharpness", "lighting balance",
    }


def test_side_shadow_warns_on_lighting_only():
    photo = Image.open("samples/sample_us_2x2.png").convert("RGB")
    shaded = np.asarray(photo, dtype=np.float32)
    shaded[:, :shaded.shape[1] // 2] *= 0.7
    findings = check.validate_photo(
        Image.fromarray(shaded.astype("uint8")), get_spec("us")
    )
    by_label = {f.label: f for f in findings}
    assert by_label["lighting balance"].status == "WARN"
    assert by_label["dimensions"].status == "PASS"
    assert all(f.ok for f in findings)


def test_lighting_never_fails():
    assert check.IMBALANCE_WARN > 0
    photo = Image.new("RGB", (600, 600), "#000000")
    findings = check.validate_photo(photo, get_spec("us"))
    assert all(f.ok for f in findings)


def test_strict_escalates_lighting_warning(tmp_path):
    import subprocess
    import sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parent.parent
    photo = Image.open(root / "samples" / "sample_us_2x2.png").convert("RGB")
    shaded = np.asarray(photo, dtype=np.float32)
    shaded[:, :shaded.shape[1] // 2] *= 0.7
    target = tmp_path / "shadow.png"
    Image.fromarray(shaded.astype("uint8")).save(target)

    def run(*extra: str) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            [sys.executable, "-m", "passportphoto",
             "validate", "--photo", str(target), "--spec", "us", *extra],
            cwd=root, capture_output=True, text=True,
        )

    assert run().returncode == 0
    strict = run("--strict")
    assert strict.returncode == 1
    assert "lighting balance" in strict.stdout


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
