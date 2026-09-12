"""Subject scaffolding: folder layout plus a landmarks-free starter."""

import json
from pathlib import Path

from passportphoto import init as scaffolder
from passportphoto import pipeline


def test_scaffold_writes_layout_and_starter(tmp_path):
    config = scaffolder.scaffold(tmp_path / "me", "me", "schengen")
    assert config == tmp_path / "me" / "me.json"
    assert (tmp_path / "me" / "source").is_dir()
    starter = json.loads(config.read_text())
    assert starter["spec"] == "schengen"
    assert starter["name"] == "me"
    assert "landmarks" not in starter
    assert any("pick" in line for line in starter["_comment"])


def test_make_on_fresh_scaffold_guides_to_measuring(tmp_path):
    config = scaffolder.scaffold(tmp_path / "me", "me", "us")
    try:
        pipeline.load_job(config)
        raise AssertionError("should have raised")
    except KeyError as exc:
        assert "pick" in exc.args[0] and "detect" in exc.args[0]


def test_init_rejects_unknown_spec(tmp_path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "passportphoto", "init",
         "--outdir", str(tmp_path / "me"), "--spec", "atlantis"],
        cwd=root, capture_output=True, text=True,
    )
    assert proc.returncode == 2
