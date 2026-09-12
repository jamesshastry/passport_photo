"""Background replacement.

Passport standards want a plain, evenly lit background. Three ways to get one,
in descending order of reliability:

``matte``   an external alpha matte aligned to the source image (hand-cut in
            Photoshop / GIMP, or produced by a segmentation tool). Always works.
``alpha``   the input is already RGBA with a usable alpha channel.
``keep``    the photo was shot against a compliant wall; leave it alone.

There is intentionally no colour-key mode. Keying a real-world portrait against
a non-studio background produces halos around hair, and hair is the one region
the examiner measures.
"""

from __future__ import annotations

from PIL import Image, ImageFilter

MODES = ("matte", "alpha", "keep")


def load_matte(path: str, size: tuple[int, int]) -> Image.Image:
    """Load a matte as 8-bit greyscale, resized to the source image size.

    White (255) is subject, black (0) is background. RGBA inputs contribute
    their alpha channel so an already-cut-out PNG works as a matte too.
    """
    matte = Image.open(path)
    matte = matte.getchannel("A") if matte.mode in ("RGBA", "LA") else matte.convert("L")
    if matte.size != size:
        matte = matte.resize(size, Image.LANCZOS)
    return matte


def refine_matte(
    matte: Image.Image,
    feather_px: float = 0.0,
    choke_px: float = 0.0,
) -> Image.Image:
    """Soften and/or shrink a matte.

    ``choke_px`` pulls the edge inward before feathering, which removes the rim
    of original background colour that otherwise survives around hair. Feather
    then blends what is left. A choke slightly larger than the feather is the
    usual recipe for a dark-haired subject on a bright background.
    """
    if choke_px > 0:
        radius = max(1, int(round(choke_px)))
        matte = matte.filter(ImageFilter.MinFilter(size=radius * 2 + 1))
    if feather_px > 0:
        matte = matte.filter(ImageFilter.GaussianBlur(radius=feather_px))
    return matte


def composite(
    image: Image.Image,
    matte: Image.Image | None,
    color: str,
) -> Image.Image:
    """Lay the subject over a flat ``color``. Returns RGB."""
    backdrop = Image.new("RGB", image.size, color)
    if matte is None:
        return image.convert("RGB")
    return Image.composite(image.convert("RGB"), backdrop, matte)


def resolve(
    image: Image.Image,
    mode: str,
    matte_path: str | None,
    feather_px: float = 0.0,
    choke_px: float = 0.0,
) -> Image.Image | None:
    """Produce the matte implied by ``mode``, or None for ``keep``."""
    if mode not in MODES:
        raise ValueError(f"background mode must be one of {MODES}, got {mode!r}")
    if mode == "keep":
        return None
    if mode == "matte":
        if not matte_path:
            raise ValueError("background mode 'matte' requires --matte")
        matte = load_matte(matte_path, image.size)
    else:  # alpha
        if image.mode not in ("RGBA", "LA"):
            raise ValueError(
                "background mode 'alpha' needs an RGBA input; "
                f"{image.mode} has no alpha channel. Use --bg matte or --bg keep."
            )
        matte = image.getchannel("A")
    return refine_matte(matte, feather_px=feather_px, choke_px=choke_px)
