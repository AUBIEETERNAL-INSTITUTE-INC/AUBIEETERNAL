"""
Regenerates the PWA / Add-to-Home-Screen icons in this folder.

    python assets/pwa/_generate_icons.py

Source mark: AUBIEETERNAL_extension/icons/eagle128.png (the existing brand
eagle), composited onto the app's dark ground with a faint cyan glow. Output:
  icon-192.png            any-purpose, transparent corners
  icon-512.png            any-purpose, transparent corners
  icon-512-maskable.png   maskable (mark kept inside the ~80% safe zone)
  apple-touch-icon-180.png opaque (iOS ignores transparency and rounds itself)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
EAGLE = HERE.parent.parent / "AUBIEETERNAL_extension" / "icons" / "eagle128.png"

BG_TOP = (10, 20, 32)     # ~#0a1420
BG_BOTTOM = (0, 22, 40)   # ~#001628
CYAN = (0, 201, 255)


def _ground(size: int, radius_frac: float = 0.18, rounded: bool = True) -> Image.Image:
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        grad.putpixel(
            (0, y),
            tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    img = grad.resize((size, size)).convert("RGBA")
    if rounded:
        mask = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(mask)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius_frac), fill=255)
        img.putalpha(mask)
    return img


def _compose(size: int, mark_frac: float, rounded: bool, opaque: bool) -> Image.Image:
    base = _ground(size, rounded=rounded)
    mark_px = int(size * mark_frac)
    eagle = Image.open(EAGLE).convert("RGBA").resize((mark_px, mark_px), Image.LANCZOS)
    pos = ((size - mark_px) // 2, (size - mark_px) // 2)

    # soft cyan glow behind the mark
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tint = Image.new("RGBA", (mark_px, mark_px), CYAN + (0,))
    tint.putalpha(eagle.split()[3].point(lambda a: int(a * 0.55)))
    glow.paste(tint, pos, tint)
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.03))

    out = Image.alpha_composite(base, glow)
    out.alpha_composite(eagle, pos)

    if opaque:
        flat = Image.new("RGB", (size, size), BG_TOP)
        flat.paste(out, (0, 0), out)
        return flat
    return out


def main() -> None:
    _compose(192, 0.62, rounded=True, opaque=False).save(HERE / "icon-192.png")
    _compose(512, 0.62, rounded=True, opaque=False).save(HERE / "icon-512.png")
    _compose(512, 0.50, rounded=False, opaque=False).save(HERE / "icon-512-maskable.png")
    _compose(180, 0.64, rounded=False, opaque=True).save(HERE / "apple-touch-icon-180.png")
    print("wrote:", *(p.name for p in sorted(HERE.glob("*.png"))))


if __name__ == "__main__":
    main()
