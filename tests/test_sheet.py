"""Print-sheet tiling counts per paper size."""

import pytest
from PIL import Image

from passportphoto import sheet
from passportphoto.specs import get_spec


def _photo(spec_key: str) -> Image.Image:
    spec = get_spec(spec_key)
    return Image.new("RGB", (spec.width_px, spec.height_px), "#FFFFFF")


def test_us_2x2_tiles_6up_on_4x6():
    tiled, placed = sheet.build(_photo("us"), "4x6", dpi=300)
    assert placed == 6
    assert tiled.size == (1200, 1800)


def test_canada_50x70_tiling_count():
    # Portrait 4x6 fits 2x2=4; landscape fits 3x1=3; portrait wins.
    _, placed = sheet.build(_photo("canada"), "4x6", dpi=300)
    assert placed == 4


@pytest.mark.parametrize(
    ("paper", "placed", "size"),
    [
        ("9x13cm", 2, (1063, 1535)),
        # 10x15cm is 1.6mm narrower than 4x6, which costs a whole column.
        ("10x15cm", 2, (1181, 1772)),
        ("13x18cm", 6, (1535, 2126)),
    ],
)
def test_metric_lab_paper_tiling(paper: str, placed: int, size: tuple[int, int]):
    tiled, actual = sheet.build(_photo("us"), paper, dpi=300)
    assert actual == placed
    assert tiled.size == size


@pytest.mark.parametrize("paper", sorted(sheet.PAPERS))
def test_every_paper_holds_at_least_one_us_photo(paper: str):
    _, placed = sheet.build(_photo("us"), paper, dpi=300)
    assert placed >= 1


def test_copies_caps_the_count():
    _, placed = sheet.build(_photo("us"), "4x6", dpi=300, copies=2)
    assert placed == 2


def test_copies_above_capacity_clamps_to_capacity():
    _, placed = sheet.build(_photo("us"), "4x6", dpi=300, copies=99)
    assert placed == 6


def test_unknown_paper_names_the_known_ones():
    with pytest.raises(KeyError, match="4x6"):
        sheet.build(_photo("us"), "napkin", dpi=300)


def test_photo_larger_than_paper_is_an_error():
    huge = Image.new("RGB", (5000, 5000), "#FFFFFF")
    with pytest.raises(ValueError, match="does not fit"):
        sheet.build(huge, "4x6", dpi=300)


def test_margin_eats_capacity():
    _, full = sheet.build(_photo("us"), "4x6", dpi=300)
    _, margined = sheet.build(_photo("us"), "4x6", dpi=300, margin_mm=25.0)
    assert margined < full
