"""Passport/visa photo specifications: loading, unit conversion, compliance checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MM_PER_INCH = 25.4
SPECS_PATH = Path(__file__).resolve().parent.parent / "specs.json"


def mm_to_px(mm: float, dpi: int) -> float:
    return mm * dpi / MM_PER_INCH


def px_to_mm(px: float, dpi: int) -> float:
    return px * MM_PER_INCH / dpi


@dataclass(frozen=True)
class Spec:
    """One photo standard, normalised to millimetres."""

    key: str
    name: str
    units: str
    photo_w_mm: float
    photo_h_mm: float
    dpi: int
    head_min_mm: float
    head_max_mm: float
    background: str
    notes: str = ""
    eye_min_mm: float | None = None
    eye_max_mm: float | None = None
    crown_gap_frac: float | None = None
    head_target_mm_override: float | None = None

    # --- derived -------------------------------------------------------

    @property
    def head_target_mm(self) -> float:
        if self.head_target_mm_override is not None:
            return self.head_target_mm_override
        return (self.head_min_mm + self.head_max_mm) / 2

    @property
    def eye_target_mm(self) -> float | None:
        """Eye line above the bottom edge, or None if the spec has no eye rule."""
        if self.eye_min_mm is None or self.eye_max_mm is None:
            return None
        return (self.eye_min_mm + self.eye_max_mm) / 2

    @property
    def width_px(self) -> int:
        return round(mm_to_px(self.photo_w_mm, self.dpi))

    @property
    def height_px(self) -> int:
        return round(mm_to_px(self.photo_h_mm, self.dpi))

    def px(self, mm: float) -> float:
        return mm_to_px(mm, self.dpi)

    def mm(self, px: float) -> float:
        return px_to_mm(px, self.dpi)

    def at_dpi(self, dpi: int) -> "Spec":
        """Same standard rendered at a different print resolution."""
        return Spec(**{**self.__dict__, "dpi": dpi})

    def describe_size(self) -> str:
        if self.units == "in":
            w = self.photo_w_mm / MM_PER_INCH
            h = self.photo_h_mm / MM_PER_INCH
            return f"{w:g}x{h:g} in"
        return f"{self.photo_w_mm:g}x{self.photo_h_mm:g} mm"


@dataclass(frozen=True)
class Check:
    """One measured dimension judged against the spec."""

    label: str
    actual_mm: float
    min_mm: float
    max_mm: float
    dpi: int

    @property
    def ok(self) -> bool:
        return self.min_mm <= self.actual_mm <= self.max_mm

    def format(self, units: str = "mm") -> str:
        status = "PASS" if self.ok else "FAIL"
        if units == "in":
            a, lo, hi = (
                self.actual_mm / MM_PER_INCH,
                self.min_mm / MM_PER_INCH,
                self.max_mm / MM_PER_INCH,
            )
            body = f'{a:.3f}" (allowed {lo:.3f}-{hi:.3f}")'
        else:
            body = f"{self.actual_mm:.2f} mm (allowed {self.min_mm:.2f}-{self.max_mm:.2f} mm)"
        return f"[{status}] {self.label}: {body}"


def load_specs(path: Path | str | None = None) -> dict[str, Spec]:
    """Read specs.json into Spec objects, skipping ``_``-prefixed comment keys."""
    path = Path(path) if path else SPECS_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    specs: dict[str, Spec] = {}
    for key, body in raw.items():
        if key.startswith("_"):
            continue
        specs[key] = Spec(
            key=key,
            name=body["name"],
            units=body.get("units", "mm"),
            photo_w_mm=float(body["photo_w_mm"]),
            photo_h_mm=float(body["photo_h_mm"]),
            dpi=int(body.get("dpi", 300)),
            head_min_mm=float(body["head_min_mm"]),
            head_max_mm=float(body["head_max_mm"]),
            background=body.get("background", "#FFFFFF"),
            notes=body.get("notes", ""),
            eye_min_mm=_opt_float(body.get("eye_min_mm")),
            eye_max_mm=_opt_float(body.get("eye_max_mm")),
            crown_gap_frac=_opt_float(body.get("crown_gap_frac")),
            head_target_mm_override=_opt_float(body.get("head_target_mm")),
        )
    return specs


def get_spec(key: str, path: Path | str | None = None) -> Spec:
    specs = load_specs(path)
    try:
        return specs[key]
    except KeyError:
        known = ", ".join(sorted(specs))
        raise KeyError(f"unknown spec {key!r}. Known specs: {known}") from None


def _opt_float(value) -> float | None:
    return None if value is None else float(value)
