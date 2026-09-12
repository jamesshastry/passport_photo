"""CLI error paths: bad input exits 2, --strict exits 1 on failure."""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "passportphoto", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_specs_lists_review_dates():
    proc = run_cli("specs")
    assert proc.returncode == 0
    assert proc.stdout.count("reviewed 20") >= 11


def test_pick_writes_standalone_page(tmp_path):
    out = tmp_path / "landmarks.html"
    proc = run_cli(
        "pick", "--input", "subjects/example/source/portrait.jpg",
        "--out", str(out), "--spec", "us", "--name", "example",
    )
    assert proc.returncode == 0
    html = out.read_text()
    assert "data:image/jpeg;base64," in html
    assert 'src="http' not in html and 'href="http' not in html


def test_pick_rejects_bad_spec_and_landmarks(tmp_path):
    bad_spec = run_cli(
        "pick", "--input", "subjects/example/source/portrait.jpg",
        "--out", str(tmp_path / "x.html"), "--spec", "atlantis",
    )
    assert bad_spec.returncode == 2
    bad_lm = run_cli(
        "pick", "--input", "subjects/example/source/portrait.jpg",
        "--out", str(tmp_path / "y.html"), "--landmarks", "crown=oops",
    )
    assert bad_lm.returncode == 2


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


def test_detect_fails_cleanly_on_a_faceless_image(tmp_path):
    # Hermetic whether or not the [auto] packages are installed: without
    # them the error names the extra, with them the detector finds no face.
    blank = tmp_path / "blank.png"
    Image.new("RGB", (400, 400), "#808080").save(blank)
    proc = run_cli(
        "detect", "--input", str(blank),
        "--outdir", str(tmp_path / "subject"),
    )
    assert proc.returncode == 2
    assert "passportphoto[auto]" in proc.stderr or "no face" in proc.stderr


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


def test_validate_command_passes_on_sample():
    proc = run_cli(
        "validate", "--photo", "samples/sample_us_2x2.png", "--spec", "us",
    )
    assert proc.returncode == 0
    assert "All checks passed" in proc.stdout


def test_validate_command_fails_on_wrong_spec():
    proc = run_cli(
        "validate", "--photo", "samples/sample_us_2x2.png", "--spec", "schengen",
    )
    assert proc.returncode == 1
    assert "[FAIL] dimensions" in proc.stdout


def test_validate_directory_mode_reports_summary(tmp_path):
    import shutil

    subjects = tmp_path / "prints"
    subjects.mkdir()
    shutil.copy("samples/sample_us_2x2.png", subjects / "good.png")
    Image.new("RGB", (100, 100), "#FFFFFF").save(subjects / "small.png")
    (subjects / "notes.txt").write_text("not an image")
    proc = run_cli("validate", "--photo", str(subjects), "--spec", "us")
    assert proc.returncode == 1
    assert proc.stdout.count("=== [") == 2
    assert "validate: 1/2 passed" in proc.stdout


def test_validate_empty_directory_is_an_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = run_cli("validate", "--photo", str(empty), "--spec", "us")
    assert proc.returncode == 2
    assert "no images" in proc.stderr


def test_validate_repeated_photo_flags(tmp_path):
    proc = run_cli(
        "validate", "--photo", "samples/sample_us_2x2.png",
        "--photo", "samples/sample_us_2x2.png", "--spec", "us",
    )
    assert proc.returncode == 0
    assert "validate: 2/2 passed" in proc.stdout


def test_validate_warns_but_passes_without_strict(tmp_path):
    tinted = tmp_path / "tinted.png"
    Image.new("RGB", (600, 600), "#FFE0C0").save(tinted)
    proc = run_cli("validate", "--photo", str(tinted), "--spec", "us")
    assert proc.returncode == 0
    strict = run_cli(
        "validate", "--photo", str(tinted), "--spec", "us", "--strict",
    )
    assert strict.returncode == 1


def test_batch_runs_each_config_and_reports(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", "subjects/example/subject.json",
        "--config", "subjects/example/subject.json",
        "--spec", "schengen",
        "--outdir", str(outdir), "--name", "twin",
        "--no-sheet", "--no-proof", "--no-spec-check",
    )
    assert proc.returncode == 0
    assert proc.stdout.count("=== [") == 2
    assert "batch: 2/2 compliant" in proc.stdout
    assert (outdir / "twin_schengen_300dpi.png").exists()


def test_batch_continues_past_a_bad_config(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", str(tmp_path / "missing.json"),
        "--config", "subjects/example/subject.json",
        "--outdir", str(outdir), "--name", "survivor",
        "--no-proof", "--no-spec-check", "--continue-on-error",
    )
    assert proc.returncode == 1
    assert "1 errored" in proc.stdout
    assert (outdir / "survivor_us_300dpi.png").exists()


def test_batch_aborts_on_first_bad_config_by_default(tmp_path):
    proc = run_cli(
        "make", "--config", str(tmp_path / "missing.json"),
        "--config", "subjects/example/subject.json",
        "--outdir", str(tmp_path / "out"),
    )
    assert proc.returncode == 2


def test_batch_warns_on_output_collision(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", "subjects/example/subject.json",
        "--config", "subjects/example/subject.json",
        "--outdir", str(outdir), "--name", "twin",
        "--no-proof", "--no-spec-check",
    )
    assert proc.returncode == 0
    assert "overwrites" in proc.stdout


def test_batch_strict_fails_when_any_job_fails(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", "subjects/example/subject.json",
        "--config", "subjects/example/subject.json",
        "--landmarks", "crown=900,chin=1900,eye=1850,center=1512",
        "--outdir", str(outdir), "--name", "bad",
        "--no-sheet", "--strict",
    )
    assert proc.returncode == 1
    assert "batch: 0/2 compliant" in proc.stdout


def test_pdf_flag_writes_upload_sheet(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", "subjects/example/subject.json",
        "--outdir", str(outdir), "--name", "pdf",
        "--sheet", "4x6", "--pdf",
        "--no-proof", "--no-spec-check",
    )
    assert proc.returncode == 0
    pdf = outdir / "pdf_us_sheet_4x6_6up_300dpi.pdf"
    assert pdf.read_bytes()[:5] == b"%PDF-"
    report = json.loads((outdir / "pdf_us_report.json").read_text())
    assert pdf.name in report["outputs"]


def test_pdf_config_file_option(tmp_path):
    import json as _json

    outdir = tmp_path / "out"
    cfg = _json.loads(
        (ROOT / "subjects" / "example" / "subject.json").read_text()
    )
    cfg["pdf"] = True
    example = ROOT / "subjects" / "example"
    cfg["input"] = str(example / "source" / "portrait.jpg")
    cfg["background"]["matte"] = str(example / "source" / "matte.png")
    config = tmp_path / "subject.json"
    config.write_text(_json.dumps(cfg))
    proc = run_cli(
        "make", "--config", str(config),
        "--outdir", str(outdir), "--name", "cfg",
        "--no-proof", "--no-spec-check",
    )
    assert proc.returncode == 0
    assert (outdir / "cfg_us_sheet_4x6_6up_300dpi.pdf").exists()


def test_no_pdf_by_default(tmp_path):
    outdir = tmp_path / "out"
    proc = run_cli(
        "make", "--config", "subjects/example/subject.json",
        "--outdir", str(outdir), "--name", "nopdf",
        "--no-proof", "--no-spec-check",
    )
    assert proc.returncode == 0
    assert list(outdir.glob("*.pdf")) == []


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
