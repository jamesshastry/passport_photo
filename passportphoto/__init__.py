"""Generic passport / visa / ID photo generator.

Pipeline: source photo + hand-read landmarks + a published standard
          -> background replacement -> spec-driven crop -> tone
          -> printable photo, spec-check overlay and print sheets.
"""

from .enhance import Adjustments
from .landmarks import Landmarks
from .pipeline import Job, Result, load_job, run
from .specs import Spec, get_spec, load_specs

__all__ = [
    "Adjustments",
    "Job",
    "Landmarks",
    "Result",
    "Spec",
    "get_spec",
    "load_job",
    "load_specs",
    "run",
]
__version__ = "1.0.0"
