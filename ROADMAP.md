# Roadmap

Where this tool goes next, ordered by value-to-risk. Standing rule: nothing
that weakens the compliance story ships. Diagnostics may warn; only exact
measurements may fail.

## Now (small, safe, tested like the rest)

- [x] **More paper sizes** — 9×13, 10×15 and 13×18 cm in `sheet.PAPERS`,
  with tiling counts pinned in tests.
- [x] **PDF print-sheet output** (`make --pdf`) — labs that take uploads often
  want PDF. Same tiling, different container; JPEG-encoded, so the PNG stays
  the exact artifact.
- [x] **Spec freshness** — `reviewed_on` per entry in `specs.json` plus a warning
  when a standard goes 12 months without re-checking. Data-only, no code per
  country.

## Next (bigger, still on-mission)

- [x] **Guided landmark picker** (`passportphoto pick`) — a single static local
  page with draggable crown/chin/eye lines that exports `subject.json`.
  Kills the read-numbers-off-a-grid friction without touching the pipeline.
  No server, no upload, no state.
- [x] **Lighting check (warnings only)** — side-lighting imbalance as a WARN
  finding in `validate`. Never auto-corrects the face. Background uniformity
  was dropped: on a finished crop the subject touches the frame edges, so no
  edge/corner sample separates backdrop from subject without a matte.

## Later / experimental

- [x] **Glasses-glare heuristic** — WARN-only advisory at `make` time,
  calibrated 0.03 clean / 0.37 glare against a 0.15 threshold. Mouth-open
  detection was measured and **rejected**: beard stubble reads as mouth
  interior under every band/threshold tried, so it failed the gate. No
  detector ships on vibes.

## Round 3

- [x] **Validate directory mode** — `--photo` repeatable, directories scanned
  for images, per-photo headers plus a `validate: x/y passed` summary.

## Round 2 (from the adversarial review of shipped features)

- [x] **Batch resilience** (`--continue-on-error`, per-job summary, collision
  warning). One bad config no longer kills a 20-person batch.
- [x] **Positive-path detection test in CI** (`test_detect_live.py` + CI job:
  opencv only, never rembg's 1 GB model). Records YuNet finding no face on
  the illustration — as predicted, detectors need real faces.
- [x] **Checksum-pinned model downloads** with re-download on mismatch and a
  clear refusal on unknown bytes.
- [x] **CI freshness gate** — the suite fails once any `reviewed_on` exceeds
  12 months. An intentional time bomb.
- [ ] **Padding-aware `validate`** — investigated and dropped: per-side border
  stats cannot separate padding fill from genuine white background (the clean
  sample's top edge is perfectly flat white too). `make` already prints the
  padding note at generation time, which is where the information lives.
- [x] **Picker structural test** — every JS-referenced element id exists in
  the template. (A headless-browser drag test was considered and rejected:
  a browser toolchain is disproportionate for a Pillow+numpy project; the
  coordinate mapping is already pinned in Python.)

## Rejected (adversarial review, kept as a record)

- **Zero-review full-auto `make`** — the crown decides rejections and detectors
  clip hair. Skipping review trades away the tool's core promise for
  convenience. The first-draft framing stays.
- **Auto matte refinement near hair** — any algorithmic edit to the measured
  region undermines the "exact matte" guarantee. Refinement stays manual and
  stays in the user's editor, not here.
- **Phone-camera capture guide** — a live overlay is a different product
  surface (mobile app, camera permissions). Out of scope for a CLI tool.
- **Baby/child mode** — babies face the same published specs; there is no
  separate standard to encode, so this would be docs, not a feature.
