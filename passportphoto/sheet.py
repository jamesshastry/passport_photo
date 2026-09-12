"""Print sheets: tile one finished photo into a paper size a lab will print."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from .specs import mm_to_px


@dataclass(frozen=True)
class Paper:
    key: str
    name: str
    w_mm: float
    h_mm: float


PAPERS: dict[str, Paper] = {
    "4x6": Paper("4x6", '4x6 in photo print', 101.6, 152.4),
    "5x7": Paper("5x7", '5x7 in photo print', 127.0, 177.8),
    "a6": Paper("a6", "A6", 105.0, 148.0),
    "a5": Paper("a5", "A5", 148.0, 210.0),
    "a4": Paper("a4", "A4", 210.0, 297.0),
    "letter": Paper("letter", "US Letter", 215.9, 279.4),
}


def build(
    photo: Image.Image,
    paper_key: str,
    dpi: int,
    copies: int | None = None,
    margin_mm: float = 0.0,
    gutter_mm: float = 0.0,
    cut_marks: bool = True,
    background: str = "#FFFFFF",
) -> tuple[Image.Image, int]:
    """Tile ``photo`` onto ``paper_key``. Returns (sheet, copies_placed).

    ``copies=None`` fills the sheet. Layout is tried in both paper orientations
    and the one that fits more photos wins.

    Margin and gutter default to zero because that is how a photo lab prints
    them: a 2x2 in photo tiles exactly 6-up edge to edge on a 4x6 print, and
    any margin at all drops that to 2. Raise them only for a home printer that
    cannot print to the edge.
    """
    try:
        paper = PAPERS[paper_key]
    except KeyError:
        raise KeyError(f"unknown paper {paper_key!r}. Known: {', '.join(sorted(PAPERS))}") from None

    gutter = round(mm_to_px(gutter_mm, dpi))
    margin = round(mm_to_px(margin_mm, dpi))
    pw, ph = photo.size

    best = None
    for w_mm, h_mm in ((paper.w_mm, paper.h_mm), (paper.h_mm, paper.w_mm)):
        sheet_w = round(mm_to_px(w_mm, dpi))
        sheet_h = round(mm_to_px(h_mm, dpi))
        cols = max(0, (sheet_w - 2 * margin + gutter) // (pw + gutter))
        rows = max(0, (sheet_h - 2 * margin + gutter) // (ph + gutter))
        if best is None or cols * rows > best[0] * best[1]:
            best = (cols, rows, sheet_w, sheet_h)

    cols, rows, sheet_w, sheet_h = best
    capacity = cols * rows
    if capacity == 0:
        raise ValueError(
            f"a {pw}x{ph}px photo does not fit on {paper.name} at {dpi}dpi "
            f"with a {margin_mm}mm margin"
        )
    placed = capacity if copies is None else min(copies, capacity)

    sheet = Image.new("RGB", (sheet_w, sheet_h), background)
    block_w = cols * pw + (cols - 1) * gutter
    block_h = rows * ph + (rows - 1) * gutter
    x0 = (sheet_w - block_w) // 2
    y0 = (sheet_h - block_h) // 2

    draw = ImageDraw.Draw(sheet)
    for index in range(placed):
        col, row = index % cols, index // cols
        x = x0 + col * (pw + gutter)
        y = y0 + row * (ph + gutter)
        sheet.paste(photo, (x, y))
        if cut_marks:
            draw.rectangle([x, y, x + pw - 1, y + ph - 1], outline=(190, 190, 190), width=1)

    return sheet, placed
