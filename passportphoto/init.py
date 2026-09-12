"""Scaffold a new subject folder: config starter plus next steps.

``passportphoto init`` creates the folder layout and a starter config with
no landmarks yet — measuring them is the job of ``pick`` (drag the lines)
or ``detect`` (first draft). Running ``make`` on a fresh scaffold fails
with a message saying exactly that, instead of a bare KeyError.
"""

from __future__ import annotations

import json
from pathlib import Path


def scaffold(dest: Path, name: str, spec_key: str) -> Path:
    """Create ``dest`` with source/ and a starter ``<name>.json``."""
    dest = Path(dest)
    (dest / "source").mkdir(parents=True, exist_ok=True)
    config = dest / f"{name}.json"
    config.write_text(
        json.dumps(
            {
                "_comment": [
                    f"Starter for '{name}'. Next steps:",
                    "  1. copy your portrait to source/portrait.jpg",
                    "  2. measure landmarks: `passportphoto pick` (precise)",
                    "     or `passportphoto detect` (first draft, needs .[auto])",
                    "  3. run `passportphoto make --config "
                    + config.name
                    + "`",
                ],
                "name": name,
                "spec": spec_key,
                "input": "source/portrait.jpg",
                "outdir": "output",
                "background": {"mode": "matte", "matte": "source/matte.png"},
                "sheets": ["4x6"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config
