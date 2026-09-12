"""Guided landmark picker: a self-contained HTML page with draggable lines.

``passportphoto pick`` writes one HTML file embedding a downscaled preview of
the source photo. The user drags crown/chin/eye/centre lines over it and the
page exports a ``subject.json`` (download + copyable ``--landmarks`` string)
with coordinates already mapped back to *source* pixels.

No server, no upload, no state: the page runs from file:// and the preview
never leaves the machine. It replaces reading numbers off ``grid``; the
spec-check overlay remains the confirmation step.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from .landmarks import Landmarks

# Longest preview edge, px. Keeps the HTML small while staying precise: the
# export maps display pixels back to source pixels, so downscaling loses no
# landmark accuracy beyond rounding to 0.1px.
PREVIEW_MAX_EDGE = 1600


def preview_scale(source_size: tuple[int, int]) -> float:
    """Display scale so the longest edge fits PREVIEW_MAX_EDGE."""
    return min(1.0, PREVIEW_MAX_EDGE / max(source_size))


def default_landmarks(source_size: tuple[int, int]) -> Landmarks:
    """Sensible starting lines when the user supplies none."""
    w, h = source_size
    return Landmarks(
        crown_y=h * 0.15, chin_y=h * 0.80, eye_y=h * 0.48, center_x=w / 2
    )


def build_page(
    source: Image.Image,
    landmarks: Landmarks,
    spec_key: str,
    name: str,
) -> str:
    """Render the picker page. Pure function of image + landmarks + names."""
    w, h = source.size
    scale = preview_scale((w, h))
    preview = source.convert("RGB")
    if scale < 1.0:
        preview = preview.resize(
            (round(w * scale), round(h * scale)), Image.LANCZOS
        )
    buffer = io.BytesIO()
    preview.save(buffer, "JPEG", quality=82)
    uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()

    init = {
        "spec": spec_key,
        "name": name,
        "sourceSize": [w, h],
        "previewSize": list(preview.size),
        "scale": scale,
        "lines": {
            "crown": landmarks.crown_y * scale,
            "chin": landmarks.chin_y * scale,
            "eye": landmarks.eye_y * scale,
            "center": landmarks.center_x * scale,
        },
    }
    return _TEMPLATE.replace("__INIT__", json.dumps(init)).replace(
        "__IMAGE__", uri
    )


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>passportphoto landmark picker</title>
<style>
  body { font-family: sans-serif; max-width: 900px; margin: 1em auto; }
  #stage { position: relative; display: inline-block; cursor: crosshair; }
  #stage img { display: block; max-width: 100%; }
  .line { position: absolute; }
  .h { left: 0; right: 0; height: 0; border-top: 2px solid #0a0; cursor: ns-resize; }
  .v { top: 0; bottom: 0; width: 0; border-left: 2px solid #f80; cursor: ew-resize; }
  .tag { position: absolute; font-size: 12px; color: #fff; background: #000a;
         padding: 1px 5px; border-radius: 3px; pointer-events: none; }
  textarea { width: 100%; height: 14em; font-family: monospace; }
</style>
</head>
<body>
<h1>Drag the lines onto the landmarks</h1>
<p>Green: crown (hair top), chin, eye line. Orange: face midline.
Numbers below are <strong>source pixels</strong> — export, then confirm with the spec check.</p>
<div id="stage"><img id="photo" src="__IMAGE__"></div>
<p id="readout"></p>
<p><button id="export">Export subject.json</button>
<a id="download" style="display:none">download subject.json</a></p>
<textarea id="out" readonly placeholder="--landmarks string and subject.json appear here"></textarea>
<script>
const INIT = __INIT__;
const stage = document.getElementById('stage');
const photo = document.getElementById('photo');
const lines = {};
function addLine(id, vertical, pos, color) {
  const el = document.createElement('div');
  el.className = 'line ' + (vertical ? 'v' : 'h');
  el.style.borderColor = color;
  const tag = document.createElement('div');
  tag.className = 'tag'; tag.textContent = id;
  stage.appendChild(el); stage.appendChild(tag);
  const L = { id, vertical, pos, el, tag };
  lines[id] = L;
  el.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const r = photo.getBoundingClientRect();
      const shown = photo.clientWidth / INIT.previewSize[0];
      let p = vertical ? (ev.clientX - r.left) / shown : (ev.clientY - r.top) / shown;
      const max = vertical ? INIT.previewSize[0] : INIT.previewSize[1];
      L.pos = Math.max(0, Math.min(max, p));
      draw(); readout();
    };
    const up = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
  });
  return L;
}
function draw() {
  const shown = photo.clientWidth / INIT.previewSize[0];
  for (const id in lines) {
    const L = lines[id];
    const p = L.pos * shown;
    if (L.vertical) { L.el.style.left = p + 'px'; L.tag.style.left = (p + 4) + 'px'; L.tag.style.top = '4px'; }
    else { L.el.style.top = p + 'px'; L.tag.style.top = (p + 4) + 'px'; L.tag.style.left = '4px'; }
  }
}
function sourcePx() {
  const out = {};
  for (const id in lines) out[id] = Math.round(lines[id].pos / INIT.scale * 10) / 10;
  return out;
}
function readout() {
  const s = sourcePx();
  document.getElementById('readout').textContent =
    `crown=${s.crown} chin=${s.chin} eye=${s.eye} center=${s.center}`;
}
addLine('crown', false, INIT.lines.crown, '#0a0');
addLine('chin', false, INIT.lines.chin, '#0a0');
addLine('eye', false, INIT.lines.eye, '#0a0');
addLine('center', true, INIT.lines.center, '#f80');
draw(); readout();
window.addEventListener('resize', draw);
document.getElementById('export').addEventListener('click', () => {
  const s = sourcePx();
  const doc = {
    name: INIT.name, spec: INIT.spec,
    input: 'source/portrait.jpg', outdir: 'output',
    landmarks: { crown: s.crown, chin: s.chin, eye: s.eye, center: s.center },
    background: { mode: 'matte', matte: 'source/matte.png' },
    sheets: ['4x6'],
  };
  const text = `--landmarks crown=${s.crown},chin=${s.chin},eye=${s.eye},center=${s.center}\n\n`
    + JSON.stringify(doc, null, 2);
  const area = document.getElementById('out');
  area.value = text;
  const dl = document.getElementById('download');
  dl.href = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 2)],
    { type: 'application/json' }));
  dl.download = INIT.name + '.json';
  dl.style.display = 'inline';
});
</script>
</body>
</html>
"""


def write_page(
    input_path: Path,
    out_path: Path,
    landmarks: Landmarks | None = None,
    spec_key: str = "us",
    name: str = "me",
) -> Path:
    """Build the picker page for ``input_path`` and write it to ``out_path``."""
    source = Image.open(input_path)
    source.load()
    landmarks = landmarks or default_landmarks(source.size)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        build_page(source, landmarks, spec_key, name or input_path.stem),
        encoding="utf-8",
    )
    return out_path
