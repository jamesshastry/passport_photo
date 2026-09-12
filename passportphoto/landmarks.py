"""Subject landmarks in source-image pixel coordinates.

There is deliberately no face detector here. Every measurement a passport office
cares about is defined against three landmarks a human can read off a photo in
about thirty seconds, and a hand-read crown is more reliable than a detected one
(detectors routinely clip dark or voluminous hair, which is exactly the
measurement that decides whether the print is rejected).

Use ``passportphoto grid`` to render a labelled coordinate grid over the input,
then read the numbers off it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Landmarks:
    """Pixel coordinates measured on the source image.

    crown_y     top of the head, including hair
    chin_y      bottom of the chin
    eye_y       the pupil line
    center_x    vertical midline of the face
    eye_left_x  optional pupil x coords; supplying both enables roll correction
    """

    crown_y: float
    chin_y: float
    eye_y: float
    center_x: float
    eye_left_x: float | None = None
    eye_right_x: float | None = None
    eye_left_y: float | None = None
    eye_right_y: float | None = None

    def __post_init__(self) -> None:
        if self.chin_y <= self.crown_y:
            raise ValueError("chin must sit below crown (larger y) in image coordinates")
        if not self.crown_y <= self.eye_y <= self.chin_y:
            raise ValueError("eye line must fall between crown and chin")

    @property
    def head_px(self) -> float:
        return self.chin_y - self.crown_y

    @property
    def roll_degrees(self) -> float:
        """Head tilt implied by the two pupils; 0 when they are not both given."""
        if None in (self.eye_left_x, self.eye_right_x, self.eye_left_y, self.eye_right_y):
            return 0.0
        dx = self.eye_right_x - self.eye_left_x
        dy = self.eye_right_y - self.eye_left_y
        if dx == 0:
            return 0.0
        return math.degrees(math.atan2(dy, dx))

    def rotated(self, degrees: float, pivot: tuple[float, float]) -> "Landmarks":
        """Landmarks as they fall after the image is rotated ``degrees`` CCW about ``pivot``."""
        if degrees == 0:
            return self
        rad = math.radians(-degrees)  # image rotate() is CCW; screen y grows downward
        cos_t, sin_t = math.cos(rad), math.sin(rad)
        px, py = pivot

        def turn(x: float, y: float) -> tuple[float, float]:
            ox, oy = x - px, y - py
            return px + ox * cos_t - oy * sin_t, py + ox * sin_t + oy * cos_t

        # Crown/chin/eye are read as horizontal lines, so rotate them on the midline.
        _, crown_y = turn(self.center_x, self.crown_y)
        _, chin_y = turn(self.center_x, self.chin_y)
        center_x, eye_y = turn(self.center_x, self.eye_y)
        updates = {
            "crown_y": crown_y,
            "chin_y": chin_y,
            "eye_y": eye_y,
            "center_x": center_x,
        }
        if self.eye_left_x is not None and self.eye_left_y is not None:
            lx, ly = turn(self.eye_left_x, self.eye_left_y)
            updates.update(eye_left_x=lx, eye_left_y=ly)
        if self.eye_right_x is not None and self.eye_right_y is not None:
            rx, ry = turn(self.eye_right_x, self.eye_right_y)
            updates.update(eye_right_x=rx, eye_right_y=ry)
        return replace(self, **updates)

    def to_dict(self) -> dict[str, float]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    # --- constructors --------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> "Landmarks":
        alias = {"crown": "crown_y", "chin": "chin_y", "eye": "eye_y", "center": "center_x"}
        clean = {alias.get(k, k): v for k, v in data.items()}
        eyes = clean.pop("eyes", None)
        if eyes:
            (lx, ly), (rx, ry) = eyes
            clean.setdefault("eye_left_x", lx)
            clean.setdefault("eye_left_y", ly)
            clean.setdefault("eye_right_x", rx)
            clean.setdefault("eye_right_y", ry)
            clean.setdefault("eye_y", (ly + ry) / 2)
            clean.setdefault("center_x", (lx + rx) / 2)
        known = set(cls.__dataclass_fields__)
        unknown = set(clean) - known
        if unknown:
            raise ValueError(f"unknown landmark field(s): {', '.join(sorted(unknown))}")
        return cls(**{k: float(v) for k, v in clean.items()})

    @classmethod
    def parse(cls, text: str) -> "Landmarks":
        """Parse ``crown=749,chin=1333,eye=1064,center=2012`` from the command line."""
        data: dict[str, float] = {}
        for part in re.split(r"[,\s]+", text.strip()):
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"expected key=value, got {part!r}")
            key, value = part.split("=", 1)
            data[key.strip()] = float(value)
        return cls.from_dict(data)
