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


def test_pipeline_reports_advisories_without_failing(tmp_path, example_dir):
    import json

    from passportphoto import pipeline
    from passportphoto.specs import get_spec

    source = Image.open(example_dir / "source" / "portrait.jpg").convert("RGB")
    draw = ImageDraw.Draw(source)
    draw.ellipse([1250, 1250, 1450, 1400], fill="white")
    draw.ellipse([1600, 1250, 1800, 1400], fill="white")
    glare_source = tmp_path / "glare.jpg"
    source.save(glare_source)
    job = pipeline.Job(
        input_path=glare_source,
        spec=get_spec("us"),
        landmarks=Landmarks.from_dict(
            {"crown": 900, "chin": 1900, "eye": 1380, "center": 1512}
        ),
        outdir=tmp_path / "out",
        name="glare",
        bg_mode="matte",
        matte_path=example_dir / "source" / "matte.png",
        sheets=(),
        before_after=False,
        spec_check=False,
        proof=False,
    )
    result = pipeline.run(job)
    # A warning is advisory: compliance and --strict are untouched.
    assert result.ok
    assert any("glare" in a.label for a in result.advisories)
    report = json.loads((tmp_path / "out" / "glare_us_report.json").read_text())
    assert any("glare" in line for line in report["advisories"])
    assert report["compliant"] is True
