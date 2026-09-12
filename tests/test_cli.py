"""CLI error paths: bad input exits 2, --strict exits 1 on failure."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "passportphoto", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_unknown_spec_is_an_error():
    proc = run_cli(
        "make", "--input", "subjects/example/source/portrait.jpg",
        "--spec", "atlantis", "--landmarks", "crown=900,chin=1900,eye=1380,center=1512",
    )
    assert proc.returncode == 2
    assert "unknown spec" in proc.stderr


def test_missing_landmarks_is_an_error():
    proc = run_cli(
        "make", "--input", "subjects/example/source/portrait.jpg", "--spec", "us",
    )
    assert proc.returncode != 0


def test_malformed_landmarks_is_an_error():
    proc = run_cli(
        "make", "--input", "subjects/example/source/portrait.jpg", "--spec", "us",
        "--landmarks", "crown=900,chin=oops",
    )
    assert proc.returncode == 2


def test_eye_outside_head_is_an_error():
    proc = run_cli(
        "make", "--input", "subjects/example/source/portrait.jpg", "--spec", "us",
        "--landmarks", "crown=900,chin=1900,eye=50,center=1512",
    )
    assert proc.returncode == 2


def test_detect_without_extras_points_at_the_extra():
    proc = run_cli(
        "detect", "--input", "subjects/example/source/portrait.jpg",
        "--outdir", "/tmp/pp_test_detect",
    )
    assert proc.returncode == 2
    assert "passportphoto[auto]" in proc.stderr


def test_spec_flag_overrides_config(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", "subjects/example/subject.json",
        "--spec", "schengen",
        "--outdir", str(outdir), "--name", "example",
        "--no-sheet", "--no-proof", "--no-spec-check",
    )
    assert proc.returncode == 0
    assert (outdir / "example_schengen_300dpi.png").exists()


def test_strict_fails_on_non_compliant_framing(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--input", "subjects/example/source/portrait.jpg",
        "--matte", "subjects/example/source/matte.png",
        "--spec", "us",
        # Eye glued to the chin pushes the crown off the top of the frame.
        "--landmarks", "crown=900,chin=1900,eye=1850,center=1512",
        "--outdir", str(outdir), "--name", "bad",
        "--no-sheet", "--strict",
    )
    assert proc.returncode == 1
    assert "FAILED" in proc.stdout


def test_non_strict_still_writes_despite_failure(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--input", "subjects/example/source/portrait.jpg",
        "--matte", "subjects/example/source/matte.png",
        "--spec", "us",
        "--landmarks", "crown=900,chin=1900,eye=1850,center=1512",
        "--outdir", str(outdir), "--name", "bad",
        "--no-sheet",
    )
    assert proc.returncode == 0
    report = json.loads((outdir / "bad_us_report.json").read_text())
    assert report["compliant"] is False
