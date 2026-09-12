"""The end-to-end job: source photo + landmarks + spec -> printable outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from . import background, compose, enhance, overlay, quality, sheet
from .landmarks import Landmarks
from .specs import Check, Spec, get_spec
from .validate import Finding


@dataclass
class Job:
    """Everything needed to produce one subject's photos for one standard."""

    input_path: Path
    spec: Spec
    landmarks: Landmarks
    outdir: Path
    name: str = "passport"
    bg_mode: str = "matte"
    matte_path: Path | None = None
    bg_color: str | None = None
    feather_px: float = 0.8
    choke_px: float = 1.0
    adjustments: enhance.Adjustments = field(default_factory=enhance.Adjustments)
    level_eyes: bool = True
    sheets: tuple[str, ...] = ("4x6",)
    copies: int | None = None
    sheet_margin_mm: float = 0.0
    sheet_gutter_mm: float = 0.0
    proof: bool = True
    spec_check: bool = True
    before_after: bool = True
    pdf: bool = False

    @property
    def background_color(self) -> str:
        return self.bg_color or self.spec.background


@dataclass
class Result:
    job: Job
    framing: compose.Framing
    checks: list[Check]
    written: list[Path]
    advisories: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def run(job: Job) -> Result:
    job.outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    source = Image.open(job.input_path)
    source.load()

    matte = background.resolve(
        source,
        mode=job.bg_mode,
        matte_path=str(job.matte_path) if job.matte_path else None,
        feather_px=job.feather_px,
        choke_px=job.choke_px,
    )

    # Background replacement happens at full source resolution, before the
    # downscale, so the resample averages subject pixels against the final
    # backdrop rather than against the original scene.
    flattened = background.composite(source, matte, job.background_color)

    # Straighten a tilted head before framing. Only possible when both pupils
    # were given; a single eye line carries no roll information.
    landmarks = job.landmarks
    roll = landmarks.roll_degrees if job.level_eyes else 0.0
    if abs(roll) > 0.05:
        pivot = (landmarks.center_x, landmarks.eye_y)
        flattened = flattened.rotate(
            roll,
            resample=Image.BICUBIC,
            center=pivot,
            fillcolor=job.background_color,
        )
        landmarks = landmarks.rotated(roll, pivot)

    framing = compose.plan(job.spec, landmarks, flattened.size)
    raw_crop = compose.render(flattened, framing, fill=job.background_color)
    photo = enhance.apply(raw_crop, job.adjustments)

    checks = compose.validate(job.spec, framing)
    advisories = quality.assess(photo, framing)

    report_extra = {"roll_corrected_degrees": round(roll, 3)}

    dpi = (job.spec.dpi, job.spec.dpi)
    stem = f"{job.name}_{job.spec.key}"

    main = job.outdir / f"{stem}_{job.spec.dpi}dpi.png"
    photo.save(main, dpi=dpi)
    written.append(main)

    if job.spec_check:
        path = job.outdir / f"{stem}_spec_check.png"
        overlay.spec_check(photo, job.spec, framing).save(path)
        written.append(path)

    if job.before_after and not job.adjustments.is_identity:
        path = job.outdir / f"{stem}_before_after.png"
        enhance.side_by_side(raw_crop, photo).save(path)
        written.append(path)

    for paper_key in job.sheets:
        tiled, placed = sheet.build(
            photo,
            paper_key,
            dpi=job.spec.dpi,
            copies=job.copies,
            margin_mm=job.sheet_margin_mm,
            gutter_mm=job.sheet_gutter_mm,
            background=job.background_color,
        )
        path = job.outdir / f"{stem}_sheet_{paper_key}_{placed}up_{job.spec.dpi}dpi.png"
        tiled.save(path, dpi=dpi)
        written.append(path)

        if job.pdf:
            pdf_path = job.outdir / f"{stem}_sheet_{paper_key}_{placed}up_{job.spec.dpi}dpi.pdf"
            tiled.save(pdf_path, "PDF", resolution=float(job.spec.dpi))
            written.append(pdf_path)

        if job.proof:
            proof = tiled.copy()
            proof.thumbnail((600, 600), Image.LANCZOS)
            proof_path = job.outdir / f"{stem}_sheet_{paper_key}_proof.png"
            proof.save(proof_path)
            written.append(proof_path)

    report = job.outdir / f"{stem}_report.json"
    report.write_text(
        json.dumps(
            _report(job, framing, checks, written, report_extra, advisories),
            indent=2,
        ),
        encoding="utf-8",
    )
    written.append(report)

    return Result(
        job=job, framing=framing, checks=checks, written=written,
        advisories=advisories,
    )


def _report(
    job: Job,
    framing: compose.Framing,
    checks: list[Check],
    written: list[Path],
    extra: dict,
    advisories: list[Finding] | None = None,
) -> dict:
    return {
        "input": str(job.input_path),
        "spec": {
            "key": job.spec.key,
            "name": job.spec.name,
            "print_size": job.spec.describe_size(),
            "dpi": job.spec.dpi,
            "pixels": [job.spec.width_px, job.spec.height_px],
            "background": job.background_color,
        },
        "landmarks_source_px": job.landmarks.to_dict(),
        **extra,
        "framing": {
            "scale": round(framing.scale, 6),
            "source_crop": [
                round(framing.crop_left, 2),
                round(framing.crop_top, 2),
                round(framing.crop_w, 2),
                round(framing.crop_h, 2),
            ],
            "padded_out_of_bounds": framing.padded,
        },
        "measurements_mm": {
            "head_height": round(job.spec.mm(framing.head_px), 3),
            "eye_from_bottom": round(job.spec.mm(framing.eye_from_bottom_px), 3),
            "crown_clearance": round(job.spec.mm(framing.crown_y), 3),
        },
        "checks": [
            {
                "label": c.label,
                "actual_mm": round(c.actual_mm, 3),
                "min_mm": c.min_mm,
                "max_mm": c.max_mm,
                "pass": c.ok,
            }
            for c in checks
        ],
        "compliant": all(c.ok for c in checks),
        "advisories": [a.format() for a in (advisories or [])],
        "outputs": [p.name for p in written],
    }


def load_job(config_path: Path, overrides: dict | None = None) -> Job:
    """Build a Job from a subject JSON file.

    Relative paths inside the config resolve against the config's own directory,
    so a subject folder stays portable.
    """
    config_path = Path(config_path).resolve()
    base = config_path.parent
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    cfg.update(overrides or {})

    def resolve(value: str | None) -> Path | None:
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else (base / path)

    spec = get_spec(cfg["spec"])
    if cfg.get("dpi"):
        spec = spec.at_dpi(int(cfg["dpi"]))

    adj_cfg = cfg.get("adjustments", {})
    sheets = cfg.get("sheets", ["4x6"])

    return Job(
        input_path=resolve(cfg["input"]),
        spec=spec,
        landmarks=Landmarks.from_dict(cfg["landmarks"]),
        outdir=resolve(cfg.get("outdir", "output")),
        name=cfg.get("name", config_path.stem),
        bg_mode=cfg.get("background", {}).get("mode", "matte"),
        matte_path=resolve(cfg.get("background", {}).get("matte")),
        bg_color=cfg.get("background", {}).get("color"),
        feather_px=float(cfg.get("background", {}).get("feather_px", 0.8)),
        choke_px=float(cfg.get("background", {}).get("choke_px", 1.0)),
        adjustments=enhance.Adjustments(
            fill_light=float(adj_cfg.get("fill_light", 0.0)),
            brightness=float(adj_cfg.get("brightness", 1.0)),
            contrast=float(adj_cfg.get("contrast", 1.0)),
            saturation=float(adj_cfg.get("saturation", 1.0)),
            sharpen=float(adj_cfg.get("sharpen", 0.0)),
        ),
        level_eyes=bool(cfg.get("level_eyes", True)),
        sheets=tuple(sheets),
        copies=cfg.get("copies"),
        sheet_margin_mm=float(cfg.get("sheet_margin_mm", 0.0)),
        sheet_gutter_mm=float(cfg.get("sheet_gutter_mm", 0.0)),
        proof=bool(cfg.get("proof", True)),
        spec_check=bool(cfg.get("spec_check", True)),
        before_after=bool(cfg.get("before_after", True)),
        pdf=bool(cfg.get("pdf", False)),
    )
