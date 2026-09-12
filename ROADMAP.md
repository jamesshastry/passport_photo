# Roadmap

Where this tool goes next, ordered by value-to-risk. Standing rule: nothing
that weakens the compliance story ships. Diagnostics may warn; only exact
measurements may fail.

## Now (small, safe, tested like the rest)

- [ ] **More paper sizes** — 10×15 cm and other common lab sizes in `sheet.PAPERS`.
  Pure data + tiling counts, same tests as existing papers.
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
- [ ] **Lighting check (warnings only)** — background uniformity + face shadow
  asymmetry as WARN findings in `validate`. Never auto-corrects the face.

## Later / experimental

- [ ] **Glasses-glare and mouth-open heuristics** — warnings only, and only if
  false-positive rates can be measured against a labelled set. No detector
  ships on vibes.

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
