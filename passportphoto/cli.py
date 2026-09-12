"""Command line interface.

    python -m passportphoto specs
    python -m passportphoto grid   --input photo.jpg --out grid.png
    python -m passportphoto make   --input photo.jpg --spec us \
                                   --landmarks crown=749,chin=1333,eye=1064,center=2012
    python -m passportphoto make   --config subjects/example/subject.json
    python -m passportphoto detect --input photo.jpg --outdir subjects/me
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import enhance, overlay, pipeline, sheet
from .landmarks import Landmarks
from .specs import MM_PER_INCH, freshness_note, get_spec, load_specs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="passportphoto",
        description="Generate spec-compliant passport, visa and ID photos from a portrait.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("specs", help="list the available photo standards")

    grid = sub.add_parser(
        "grid",
        help="render a labelled coordinate grid so landmarks can be read off the source",
    )
    grid.add_argument("--input", required=True, type=Path)
    grid.add_argument("--out", required=True, type=Path)
    grid.add_argument("--step", type=int, default=200, help="major gridline spacing in source px")

    papers = sub.add_parser("papers", help="list the available print sheet sizes")

    init = sub.add_parser(
        "init", help="scaffold a new subject folder with a starter config",
    )
    init.add_argument("--outdir", type=Path, default=Path("subjects/me"))
    init.add_argument("--name", default="me")
    init.add_argument("--spec", default="us",
                      help="standard key (see `passportphoto specs`)")

    detect = sub.add_parser(
        "detect",
        help="draft landmarks (+matte) with auto-detection; needs passportphoto[auto]",
    )
    detect.add_argument("--input", required=True, type=Path)
    detect.add_argument("--outdir", type=Path, default=Path("subjects/me"),
                        help="destination subject folder")
    detect.add_argument("--name", default="me", help="filename prefix for the outputs")
    detect.add_argument("--spec", default="us",
                        help="standard key (see `passportphoto specs`)")
    detect.add_argument("--no-matte", action="store_true",
                        help="skip the rembg cutout, draft landmarks only")

    validate = sub.add_parser(
        "validate",
        help="check finished photos against a standard without generating anything",
    )
    validate.add_argument("--photo", required=True, action="append", type=Path,
                          help="photo file or directory (scanned for images), repeatable")
    validate.add_argument("--spec", required=True,
                          help="standard key (see `passportphoto specs`)")
    validate.add_argument("--strict", action="store_true",
                          help="exit non-zero on warnings as well as failures")

    pick = sub.add_parser(
        "pick",
        help="write a drag-the-lines landmark picker page (works from file://)",
    )
    pick.add_argument("--input", required=True, type=Path)
    pick.add_argument("--out", type=Path, default=Path("landmarks.html"))
    pick.add_argument("--landmarks",
                      help="starting lines, e.g. crown=749,chin=1333,eye=1064,center=2012")
    pick.add_argument("--spec", default="us")
    pick.add_argument("--name", default="me")

    make = sub.add_parser("make", help="produce the photo, spec check and print sheets")
    make.add_argument("--config", dest="configs", action="append", type=Path,
                      help="subject JSON, repeatable for batch runs; other flags override it")
    make.add_argument("--input", type=Path)
    make.add_argument("--spec", help=f"standard key (see `{parser.prog} specs`)")
    make.add_argument(
        "--landmarks",
        help="source-pixel landmarks, e.g. crown=749,chin=1333,eye=1064,center=2012",
    )
    make.add_argument("--outdir", type=Path)
    make.add_argument("--name", help="filename prefix for the outputs")
    make.add_argument("--dpi", type=int, help="override the standard's print resolution")

    bg = make.add_argument_group("background")
    bg.add_argument("--bg", dest="bg_mode", choices=("matte", "alpha", "keep"))
    bg.add_argument("--matte", type=Path, help="greyscale/alpha matte aligned to the source")
    bg.add_argument("--bg-color", help="hex colour; defaults to the standard's requirement")
    bg.add_argument("--feather", type=float, help="matte edge blur in source px")
    bg.add_argument("--choke", type=float, help="shrink the matte inward in source px")

    tone = make.add_argument_group("tone")
    tone.add_argument("--fill-light", type=float, help="0..1, lift shadows only")
    tone.add_argument("--brightness", type=float)
    tone.add_argument("--contrast", type=float)
    tone.add_argument("--saturation", type=float)
    tone.add_argument("--sharpen", type=float, help="0..1 unsharp mask")
    tone.add_argument(
        "--no-level",
        action="store_true",
        help="skip roll correction (only applies when both pupils are given)",
    )

    out = make.add_argument_group("outputs")
    out.add_argument("--sheet", action="append", dest="sheets", help="repeatable, e.g. --sheet 4x6")
    out.add_argument("--no-sheet", action="store_true", help="skip print sheets entirely")
    out.add_argument("--copies", type=int, help="photos per sheet; default fills the sheet")
    out.add_argument("--margin", type=float, help="sheet edge margin in mm (default 0)")
    out.add_argument("--gutter", type=float, help="gap between photos in mm (default 0)")
    out.add_argument("--no-spec-check", action="store_true")
    out.add_argument("--no-proof", action="store_true")
    out.add_argument("--pdf", action="store_true",
                     help="also write each print sheet as PDF for lab upload")
    make.add_argument(
        "--continue-on-error", action="store_true",
        help="batch only: run the remaining configs when one fails to load; "
             "exits 1 if anything failed or errored",
    )
    out.add_argument("--strict", action="store_true", help="exit non-zero if any check fails")
    make.add_argument(
        "--auto", action="store_true",
        help="detect missing landmarks/matte automatically (needs passportphoto[auto]); "
             "detection is a first draft - verify the crown before printing",
    )

    del papers  # registered for its side effect only
    return parser


def cmd_specs() -> int:
    for key, spec in sorted(load_specs().items()):
        head = f"{spec.head_min_mm:g}-{spec.head_max_mm:g}mm"
        if spec.units == "in":
            head += (
                f' ({spec.head_min_mm / MM_PER_INCH:.3f}-{spec.head_max_mm / MM_PER_INCH:.3f}")'
            )
        print(f"{key:<20} {spec.describe_size():>12} @ {spec.dpi}dpi  "
              f"{spec.width_px}x{spec.height_px}px  head {head}")
        print(f"{'':<20} {spec.name}")
        if spec.notes:
            print(f"{'':<20} {spec.notes}")
        if spec.reviewed_on:
            print(f"{'':<20} reviewed {spec.reviewed_on}")
        print()
    return 0


def cmd_papers() -> int:
    for key, paper in sorted(sheet.PAPERS.items()):
        print(f"{key:<8} {paper.w_mm:g}x{paper.h_mm:g} mm   {paper.name}")
    return 0


def cmd_grid(args: argparse.Namespace) -> int:
    image = Image.open(args.input)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    overlay.coordinate_grid(image, step=args.step).save(args.out)
    print(f"wrote {args.out}  (source is {image.width}x{image.height}px)")
    print("Read crown / chin / eye / centre off the labels, then pass them to `make --landmarks`.")
    return 0


def _job_from_flags(args: argparse.Namespace) -> pipeline.Job:
    missing = [f for f in ("input", "spec", "landmarks") if getattr(args, f) is None]
    if missing:
        raise SystemExit(
            "error: without --config you must pass " + ", ".join("--" + m for m in missing)
        )
    spec = get_spec(args.spec)
    if args.dpi:
        spec = spec.at_dpi(args.dpi)
    return pipeline.Job(
        input_path=args.input,
        spec=spec,
        landmarks=Landmarks.parse(args.landmarks),
        outdir=args.outdir or Path("output"),
        name=args.name or args.input.stem,
    )


def _apply_overrides(job: pipeline.Job, args: argparse.Namespace) -> pipeline.Job:
    """Command-line flags win over whatever the config said."""
    if args.outdir:
        job.outdir = args.outdir
    if args.name:
        job.name = args.name
    if args.spec:
        job.spec = get_spec(args.spec)
    if args.dpi:
        job.spec = job.spec.at_dpi(args.dpi)
    if args.landmarks:
        job.landmarks = Landmarks.parse(args.landmarks)
    if args.input:
        job.input_path = args.input

    if args.bg_mode:
        job.bg_mode = args.bg_mode
    if args.matte:
        job.matte_path = args.matte
        job.bg_mode = "matte"
    if args.bg_color:
        job.bg_color = args.bg_color
    if args.feather is not None:
        job.feather_px = args.feather
    if args.choke is not None:
        job.choke_px = args.choke

    tone = {
        "fill_light": args.fill_light,
        "brightness": args.brightness,
        "contrast": args.contrast,
        "saturation": args.saturation,
        "sharpen": args.sharpen,
    }
    supplied = {k: v for k, v in tone.items() if v is not None}
    if supplied:
        job.adjustments = enhance.Adjustments(**{**job.adjustments.__dict__, **supplied})

    if args.no_level:
        job.level_eyes = False
    if args.sheets:
        job.sheets = tuple(args.sheets)
    if args.no_sheet:
        job.sheets = ()
    if args.copies is not None:
        job.copies = args.copies
    if args.margin is not None:
        job.sheet_margin_mm = args.margin
    if args.gutter is not None:
        job.sheet_gutter_mm = args.gutter
    if args.no_spec_check:
        job.spec_check = False
    if args.no_proof:
        job.proof = False
    if args.pdf:
        job.pdf = True
    return job


def cmd_init(args: argparse.Namespace) -> int:
    from . import init as scaffolder

    get_spec(args.spec)  # fail fast on an unknown spec
    config = scaffolder.scaffold(args.outdir, args.name, args.spec)
    print(f"wrote {config}")
    print(f"  1. copy your portrait to {args.outdir}/source/portrait.jpg")
    print("  2. measure landmarks: `passportphoto pick` (precise) or "
          "`passportphoto detect` (first draft)")
    print(f"  3. run `passportphoto make --config {config}`")
    return 0


def cmd_pick(args: argparse.Namespace) -> int:
    from . import pick as picker

    get_spec(args.spec)  # fail fast on an unknown spec
    landmarks = Landmarks.parse(args.landmarks) if args.landmarks else None
    path = picker.write_page(
        args.input, args.out, landmarks, args.spec, args.name,
    )
    print(f"wrote {path} - open it in a browser, drag the lines, export.")
    print("Then confirm with the spec-check overlay before printing.")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    from . import detect as auto

    get_spec(args.spec)  # fail fast on an unknown spec, before running detection
    written = auto.run_detect(
        args.input, args.outdir, args.name, args.spec,
        with_matte=not args.no_matte,
    )
    for path in written:
        print(f"wrote {path}")
    print("\nDetection is a FIRST DRAFT - the crown is estimated because detectors "
          "clip hair.")
    print(f"Copy your photo to {args.outdir}/source/portrait.jpg, fix the numbers in "
          f"{written[-1].name} (`passportphoto grid` helps), then run:")
    print(f"  passportphoto make --config {written[-1]}")
    return 0


def _job_from_auto(args: argparse.Namespace) -> pipeline.Job:
    """Build a job by detecting whatever flags/config did not supply."""
    from . import detect as auto
    from PIL import Image as _Image

    if args.input is None or args.spec is None:
        raise SystemExit("error: --auto needs at least --input and --spec")
    spec = get_spec(args.spec)
    if args.dpi:
        spec = spec.at_dpi(args.dpi)
    outdir = args.outdir or Path("output")
    outdir.mkdir(parents=True, exist_ok=True)
    name = args.name or args.input.stem

    source = _Image.open(args.input)
    source.load()
    if args.landmarks:
        landmarks = Landmarks.parse(args.landmarks)
    else:
        landmarks, _meta = auto.detect_landmarks(source)
        draft = outdir / f"{name}_detected.json"
        import json as _json
        draft.write_text(
            _json.dumps(auto.draft_subject(name, args.spec, landmarks), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"detected landmarks are a first draft - saved editable copy to {draft}")
        print("The crown is estimated (detectors clip hair): verify the spec check "
              "before printing.")

    matte_path = args.matte
    bg_mode = args.bg_mode or ("matte" if matte_path else None)
    if bg_mode is None:
        # Neither --bg nor --matte: cut out automatically.
        matte = auto.detect_matte(source)
        matte_path = outdir / f"{name}_matte.png"
        matte.save(matte_path)
        bg_mode = "matte"
        print(f"detected cutout saved to {matte_path}")
    return pipeline.Job(
        input_path=args.input,
        spec=spec,
        landmarks=landmarks,
        outdir=outdir,
        name=name,
        bg_mode=bg_mode or "matte",
        matte_path=matte_path,
    )


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def _collect_photos(paths: list[Path]) -> list[Path]:
    """Expand --photo entries: files as-is, directories scanned for images."""
    collected: list[Path] = []
    for path in paths:
        if path.is_dir():
            found = sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            )
            if not found:
                raise ValueError(f"no images in {path}")
            collected.extend(found)
        else:
            collected.append(path)
    return collected


def cmd_validate(args: argparse.Namespace) -> int:
    from . import validate as check

    spec = get_spec(args.spec)
    photos = _collect_photos(args.photo)

    failed = warned = 0
    for index, photo_path in enumerate(photos):
        if len(photos) > 1:
            print(f"=== [{index + 1}/{len(photos)}] {photo_path.name} ===")
        try:
            findings, _photo = check.validate_file(photo_path, spec)
        except OSError as exc:
            print(f"error: cannot read {photo_path}: {exc.strerror or exc}",
                  file=sys.stderr)
            return 2
        print(f"{spec.name}")
        print(f"  photo    {photo_path}")
        print()
        for finding in findings:
            print("  " + finding.format())
        if any(f.status == "FAIL" for f in findings):
            failed += 1
            print("\n  FAILED - photo does not match the standard.")
        elif any(f.status == "WARN" for f in findings):
            warned += 1
            print("\n  Passed with warnings - review them before printing.")
        else:
            print("\n  All checks passed.")
        if len(photos) > 1:
            print()

    if len(photos) > 1:
        summary = f"validate: {len(photos) - failed}/{len(photos)} passed"
        if warned:
            summary += f", {warned} with warnings"
        print(summary)
    if failed:
        return 1
    if warned and args.strict:
        return 1
    return 0


def _jobs_from_args(args: argparse.Namespace) -> list[pipeline.Job]:
    """One job per --config (batch), or a single flag-built job."""
    if args.configs:
        return [
            _apply_overrides(pipeline.load_job(config), args)
            for config in args.configs
        ]
    if args.auto and (
        args.landmarks is None or (args.bg_mode is None and args.matte is None)
    ):
        return [_apply_overrides(_job_from_auto(args), args)]
    return [_apply_overrides(_job_from_flags(args), args)]


def _warn_collisions(jobs: list[pipeline.Job]) -> None:
    """Warn when two jobs would write the same main photo (last one wins)."""
    seen: dict[tuple, str] = {}
    for job in jobs:
        key = (str(job.outdir), job.name, job.spec.key, job.spec.dpi)
        if key in seen:
            print(f"warning: {seen[key]} and {job.name} target the same "
                  f"outputs - the later job overwrites the earlier one")
        else:
            seen[key] = job.name


def _load_batch(
    args: argparse.Namespace,
) -> tuple[list[pipeline.Job], list[str]]:
    """Load one job per config, isolating per-config failures.

    Without --continue-on-error the first bad config raises as before;
    with it, the error is collected and the rest still run.
    """
    jobs: list[pipeline.Job] = []
    errors: list[str] = []
    for config in args.configs:
        try:
            jobs.append(_apply_overrides(pipeline.load_job(config), args))
        except (ValueError, KeyError, OSError, RuntimeError) as exc:
            if not args.continue_on_error:
                raise
            errors.append(f"{config}: {exc}")
            print(f"error: skipping {config}: {exc}")
    return jobs, errors


def cmd_make(args: argparse.Namespace) -> int:
    errors: list[str] = []
    if args.configs and args.continue_on_error:
        jobs, errors = _load_batch(args)
    else:
        jobs = _jobs_from_args(args)
    _warn_collisions(jobs)

    failures = 0
    for index, job in enumerate(jobs):
        if len(jobs) > 1 or errors:
            print(f"=== [{index + 1}/{len(jobs)}] {job.name} ({job.spec.key}) ===")
        result = pipeline.run(job)

        stale = freshness_note(job.spec)
        if stale:
            print(f"  {stale}")
        print(f"{job.spec.name}")
        print(f"  source   {job.input_path}")
        print(f"  photo    {job.spec.width_px}x{job.spec.height_px}px "
              f"({job.spec.describe_size()} @ {job.spec.dpi}dpi) on {job.background_color}")
        if result.framing.padded:
            print("  note     the crop ran past the edge of the source; "
                  "the shortfall was filled with the background colour")
        print()
        for check in result.checks:
            print("  " + check.format(job.spec.units))
        for advisory in result.advisories:
            print("  " + advisory.format())
        print()
        for path in result.written:
            print(f"  wrote {path}")

        if not result.ok:
            failures += 1
            print("\n  One or more checks FAILED - adjust the landmarks or pick a "
                  "different spec.")
        if len(jobs) > 1 or errors:
            print()

    if len(jobs) > 1 or errors:
        summary = f"batch: {len(jobs) - failures}/{len(jobs)} compliant"
        if errors:
            summary += f", {len(errors)} errored"
        print(summary)
    if errors:
        return 1
    if failures and args.strict:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "init": lambda: cmd_init(args),
        "specs": lambda: cmd_specs(),
        "papers": lambda: cmd_papers(),
        "grid": lambda: cmd_grid(args),
        "detect": lambda: cmd_detect(args),
        "pick": lambda: cmd_pick(args),
        "validate": lambda: cmd_validate(args),
        "make": lambda: cmd_make(args),
    }
    handler = handlers.get(args.command)
    if handler is None:
        return 1
    try:
        return handler()
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        # These are all "you gave me bad input" errors; a traceback adds nothing.
        # KeyError stringifies with quotes, OSError hides the path in .filename.
        if isinstance(exc, KeyError):
            message = exc.args[0] if exc.args else str(exc)
        elif isinstance(exc, OSError):
            message = f"{exc.strerror}: {exc.filename}" if exc.filename else str(exc)
        else:
            message = str(exc)
        print(f"error: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
