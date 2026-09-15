# PassportPhoto Product Brief

## Overview

PassportPhoto is a local command-line tool that turns an ordinary portrait into a spec-compliant passport, visa, or ID photo: correctly scaled and positioned, on the required background, at print resolution, tiled onto a print sheet, with a measured proof the user checks before paying for prints. Everything runs on the user's machine — Pillow plus numpy, no accounts, no uploads.

The product is complete and verified: eleven photo standards ship as data, the full workflow from scaffolding to print sheet is tested (94 automated tests), CI runs the suite on Ubuntu and Windows across three Python versions, and real portraits have been used to validate the manual path, the detector's failure modes, and the review overlays end to end. It is a finished small tool in maintenance, not a prototype.

## Problem

Getting a passport photo made means trusting a photo booth, a drugstore clerk, or an upload-to-a-website service with both correctness and a biometric image. The failure modes are silent: a head 2mm too small, eyes outside the required band, a tinted background — each discovered only at the passport office, after paying for prints. Existing desktop alternatives either hide their measurements or "beautify" the photo, and retouched-looking photos are themselves a rejection reason.

The prior workflow for this tool's first subject was a hand-built Photoshop pass per photo: effective once, unrepeatable, and unverifiable by anyone else. The product replaces that craft step with a repeatable pipeline whose every claim is measured and displayed before money changes hands.

## Solution

The end-to-end workflow is: `init` scaffolds a subject folder; the user obtains an alpha matte (hand-cut, or auto-drafted); landmarks are measured with a coordinate grid, a drag-the-lines picker page, or auto-detection; `make` produces the photo, a spec-check overlay with tolerance bands, before/after proof, tiled print sheets (PNG and PDF), and a machine-readable report; `validate` independently re-checks any finished photo.

The load-bearing design choice is that detection is a *first draft* while the overlay is the confirmation. Face detectors track visible skin, not hair, and the crown — top of head including hair — is exactly the measurement rejections turn on. So the detector's crown guess is deliberately expanded upward into an editable config, and nothing prints without the user confirming the green lines sit inside the blue and purple bands. On a real portrait this contract caught a 50px mis-centering the compliance checks themselves could not see, because framing math pins head and eye positions by construction.

## Target Users

Primary: individuals preparing their own or their family's passport and visa photos who want lab-printable output without uploading biometric photos to a service. Secondary: small print shops and travel agents checking customer-supplied photos with `validate`. Operational: the repository owner, who re-checks each standard's `reviewed_on` date when national guidance changes — a discipline the test suite enforces by failing once a standard goes twelve months unreviewed.

## Product Decisions

- **Manual path first, detection as an extra.** The Pillow+numpy workflow functions with zero optional dependencies; `pip install passportphoto[auto]` adds OpenCV/YuNet and rembg behind lazy imports. Rationale: the reliable path must never break because an ML backend moved — and one did mid-project, when MediaPipe 1.x removed the API the detector was written against and its replacement segfaulted on ARM macOS.
- **Exposure-only tone.** Fill light, brightness, contrast, saturation, sharpen — nothing reshapes faces or smooths skin, since retouched-looking photos get rejected.
- **Background replacement before downscale, single-pass crop.** Compositing after the resample fringes hair; crop-then-resize loses hair detail. Both orderings are load-bearing and documented as such.
- **Heuristics warn, measurements fail.** Dimensions are hard PASS/FAIL; background colour, sharpness, lighting balance, and glasses glare are WARN-only advisories that never affect compliance or `--strict`. Two candidate heuristics (mouth-open detection, padding-aware background verdicts) were measured against real portraits, failed their false-positive gates, and were recorded as rejected rather than shipped.
- **Specs are data, not code.** Adding a country means appending to `passportphoto/specs.json` — each entry carrying its `reviewed_on` month — with no code change.
- **No fabricated pixels, ever.** Out-of-frame areas fill with background colour; the tool refuses to invent shirt, hair, or wall content, and refuses to reframe around a bad crop since that would silently break measured dimensions.

## Architecture

```
portrait + matte + landmarks + spec
  -> background.composite   (full-resolution cutout onto required colour)
  -> roll correction        (both pupils known; recorded in report)
  -> compose.plan/render    (one similarity transform; fractional single resample)
  -> enhance.apply          (exposure-only chain)
  -> photo + spec_check overlay + before/after + sheets (PNG/PDF) + report.json
```

Major components: `specs` (standards loading, unit conversion, compliance checks, freshness), `landmarks` (source-pixel geometry, roll math), `background` (matte refine, composite), `compose` (framing transform), `enhance`, `sheet` (paper tiling across orientations), `overlay` (spec-check bands, coordinate grid), `detect` (optional YuNet + rembg, checksum-pinned models), `pick` (static landmark-picker page generator), `validate` (finished-photo inspection), `quality` (WARN-only advisories), `pipeline` (job assembly and orchestration), `cli` (eleven subcommands), `init` (subject scaffolding). Persistence is files only: subject JSON recipes, source images and mattes, generated outputs, and a two-file user cache for detector models. There is no server, no database, and no network use except one-time model downloads. Deployment is `pip install .` with a `passportphoto` console entry point; CI runs pytest on Ubuntu and Windows.

## Design System

There is no visual product surface beyond diagnostic images, so the interface contract is the CLI plus the overlay language, kept consistent everywhere: green lines are measured landmarks, blue bands are eye tolerances, purple bands are head-height tolerances, orange is the face midline. The `pick` page is a single self-contained HTML file (embedded preview, no external requests, works from `file://`) with draggable lines that export source-pixel coordinates. CLI conventions hold across all eleven subcommands: rc 0 success, rc 1 compliance failure, rc 2 bad input, with `batch:` and `validate:` summary lines for multi-item runs.

## Current Capabilities

Generation: spec-driven framing for eleven standards (US, India passport and visa, Schengen, UK, Canada, Australia, Japan, China visa, ICAO generic, plus a profile headshot), roll correction from both pupils, matte/alpha/keep backgrounds, exposure adjustments, print sheets on nine paper sizes with edge-to-edge lab tiling, PDF sheet export, per-sheet proofs, and JSON reports with every measurement. Verification: spec-check overlays, standalone `validate` for single photos, folders, or repeated flags, and WARN-only advisories for lighting balance and glasses glare. Workflow: subject scaffolding, coordinate grid, drag-the-lines picker, auto-detection drafts, repeatable `--config` batches with `--continue-on-error` and collision warnings, `--strict` scripting mode, and spec listing with review dates. Quality gates: 94 tests covering framing math against ground-truth fixtures, spec loading and freshness boundaries, tiling counts per paper, roll correction, CLI error paths, and the warnings-never-fail contract; CI across six platform-version combinations plus a live-detection job.

## Roadmap

Near-term work is driven by real use, not speculation: keeping the Windows CI leg green, more faces through the detector to calibrate the crown expansion and eye-keypoint trust (currently proven on one real portrait plus synthetic fixtures), and the scheduled standards re-reviews the freshness gate will demand starting October 2027. Longer-term, the recorded rejections stand — zero-review full-auto, matte editing near hair, mouth-open detection, phone-camera capture, and baby mode stay out unless their blocking constraints change, and the reasons are documented in `ROADMAP.md` alongside everything shipped.

## My Role

Repository owner and sole author (git history shows a single author throughout): designed the framing mathematics and compliance workflow, set the no-retouching and warnings-never-fail constraints, made the backend swaps when dependencies broke, killed two heuristics on measured evidence, and verified the product on real portraits including background replacement, roll correction, and per-spec validation. Recent packaging, detection, test suite, CI, and feature work was developed with AI assistance; all verification runs and release decisions were the owner's.

## Portfolio Summary

This product demonstrates end-to-end ownership of a small, exact tool: a compliance domain reduced to pure functions, a test suite that measures rather than asserts, automation kept subordinate to human review where the cost of error is a rejected application, and the discipline to reject features — including the author's own — when measurement contradicts them.

---
Created: 2026-09-14
Last updated: 2026-09-14
