# passportphoto

Turn an ordinary portrait into a **spec-compliant passport, visa or ID photo** —
correctly scaled, correctly positioned, on the right background, at print
resolution, tiled onto a print sheet, with a measured proof you can check before
you pay for prints.

Pillow + numpy only. No accounts, no uploads, everything runs locally.

![Sample US 2x2 output](samples/sample_us_2x2.png)

## Install

```bash
pip install .
# With optional auto-detection (see below):
pip install ".[auto]"
```

## Quickstart (manual path, always works)

**1. Cut the subject out.** You need an alpha matte: a greyscale PNG the same
shape as your photo, white where the subject is, black where the background is.
Make it in Photoshop (Select Subject → refine hair), GIMP, or any
background-removal app that exports transparency (an RGBA PNG works directly).
If the photo was shot against a compliant wall, skip this and use `--bg keep`.

**2. Read the landmarks.** The tool needs four numbers in source-pixel
coordinates: `crown` (top of the head, *including hair*), `chin`, `eye` (pupil
line) and `center` (face midline x). Render a labelled grid and read them off:

```bash
passportphoto grid --input photo.jpg --out /tmp/grid.png
```

**3. Generate:**

```bash
passportphoto make \
  --input photo.jpg --matte matte.png \
  --spec us --landmarks crown=749,chin=1333,eye=1064,center=2012 \
  --outdir output --name me --sheet 4x6
```

Or store the recipe in a JSON file and re-run it any time (`subjects/example/subject.json`
is an annotated example):

```bash
passportphoto make --config subjects/example/subject.json
```

Any flag overrides the config, so `--spec schengen` retargets a subject in one line.

For `--spec us --name me` you get: `me_us_300dpi.png` (the photo, 600×600 px),
`me_us_spec_check.png` (the examiner's lines drawn on it), `me_us_before_after.png`,
`me_us_sheet_4x6_6up_300dpi.png` (six copies on a 4×6 print), a low-res proof,
and `me_us_report.json` with every measurement and pass/fail.

**Read the spec check before you print.** Green lines are where your landmarks
landed; blue/purple bands are the tolerances. Print the *sheet*, not the photo —
order it as a standard 4×6 print, then cut along the guide lines. Sheets tile
edge-to-edge because that is how labs print; use `--margin`/`--gutter` only for a
home printer that can't print to the edge.

## Quickstart (auto-detection, first draft)

```bash
passportphoto detect --input photo.jpg --outdir subjects/me
# then, after checking the numbers:
passportphoto make --config subjects/me/me.json
```

Or in one step: `passportphoto make --input photo.jpg --spec us --auto`.

First run downloads the face-detector (~1 MB) and the rembg cutout model
(~1 GB) into your local cache — one time only, after which detection works
offline.

> **Accuracy caveat.** Detectors follow the visible face, not the hair — they
> clip dark and voluminous hair, and the crown is exactly the measurement a
> print rejection turns on. Detection output is a **first draft**: the crown is
> deliberately estimated upward and saved to an editable config. Always confirm
> with the spec-check overlay and fix the numbers (`passportphoto grid`) before
> paying for prints. If the extras aren't installed, the manual path above works
> untouched.

## Commands

```bash
passportphoto specs     # list standards, with sizes and head tolerances
passportphoto papers    # list print sheet sizes
passportphoto grid      # labelled coordinate grid for reading landmarks
passportphoto pick --input photo.jpg --out landmarks.html
                    # drag-the-lines picker page (works from file://)
passportphoto detect    # draft landmarks (+matte); needs .[auto]
passportphoto validate --photo me_us_300dpi.png --spec us
passportphoto make      # generate (add --strict to fail on any check failure)
```

`make --strict` exits non-zero when any compliance check fails, for scripting.

## Checking and batching

`validate` inspects a finished photo — yours or a lab's — without generating
anything. Dimensions are a hard PASS/FAIL; background colour and sharpness are
advisories (a heuristic must never talk you out of a compliant photo).

`--config` is repeatable, so one run covers the whole family — any other flag
still overrides every config:

```bash
passportphoto make --config subjects/ana/ana.json --config subjects/leo/leo.json
```

## Standards included

`us` · `india_passport` · `india_visa` · `schengen` · `uk` · `canada` ·
`australia` · `japan` · `china_visa` · `icao` · `linkedin_headshot`

**Add a country** by appending to `specs.json` — no code change needed. Every
measurement there is in millimetres; `units` only controls reporting. Stamp
`reviewed_on` with the month you checked the guidance — `make` warns once a
standard goes a year without re-checking, because requirements change.

## How the framing works

One similarity transform, fully determined by the standard: scale from the
head-height rule, vertical from the eye-line rule (or `crown_gap_frac` fallback),
horizontal from the face midline. Background replacement runs at full source
resolution *before* the downscale (compositing after fringes hair), the crop is
a single `Image.resize(box=...)` resample, and tone adjustments are
exposure-only — nothing reshapes faces or smooths skin, since retouched-looking
photos get rejected.

## Synthetic example

`subjects/example/` is a computer-drawn portrait against a busy background
(generated by `make_source.py`), so the matte path is genuinely exercised and
nothing needs a licence. Its landmarks and matte are exact — they come from the
same constants the drawing code used — so it doubles as the ground-truth fixture
for the geometry tests:

```bash
python3 subjects/example/make_source.py
passportphoto make --config subjects/example/subject.json
pytest
```

## License

MIT — see [LICENSE](LICENSE).
