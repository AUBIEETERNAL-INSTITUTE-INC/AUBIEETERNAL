"""
make_join_card.py — generates a printable join card for a community/
library AUBIEETERNAL deployment: a QR code + the plain URL, pointing
walk-up patrons straight at Community Mode (the real anonymous, no-login-
needed path built for exactly this - see app.py's "Community Mode" tab
and community_learners.py for its real name+PIN progress saving).

Usage:
    python make_join_card.py <server-url> [output.png]

Example:
    python make_join_card.py http://100.105.81.27:8501 join_card.png

The URL should be wherever this machine's Streamlit portal (aubie-portal.
service, port 8501 by default) is reachable on the location's network -
a LAN IP for a library with its own WiFi, or a Tailscale IP if patrons
are expected to join that tailnet first. Get the right IP for a given
machine with `ip addr` or `tailscale ip`.
"""

import sys
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont


def make_join_card(server_url: str, out_path: str = "join_card.png") -> str:
    # Point straight at Community Mode, not the bare portal root - that's
    # the real anonymous walk-up path (no family login needed), the one
    # community_learners.py's name+PIN system actually saves progress for.
    join_url = server_url.rstrip("/") + "/?tab=Community+Mode"

    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(join_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    card_w, card_h = 900, 1200
    card = Image.new("RGB", (card_w, card_h), "white")
    draw = ImageDraw.Draw(card)

    def _font(size, bold=False):
        candidates = (
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        )
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    title_font = _font(52, bold=True)
    sub_font   = _font(28)
    url_font   = _font(22)

    def _centered_text(y, text, font, fill="black"):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((card_w - w) / 2, y), text, font=font, fill=fill)

    _centered_text(50, "AUBIEETERNAL", title_font, fill="#00c9ff")
    _centered_text(120, "Free AI Tutor — Scan to Start Learning", sub_font, fill="#333333")

    qr_size = 600
    qr_img = qr_img.resize((qr_size, qr_size))
    card.paste(qr_img, ((card_w - qr_size) // 2, 190))

    _centered_text(820, join_url, url_font, fill="#555555")
    _centered_text(880, "No account needed — just a name and a PIN you'll remember.", sub_font, fill="#333333")
    _centered_text(930, "No email. No fees. Works fully offline.", sub_font, fill="#333333")

    card.save(out_path)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    url = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "join_card.png"
    result = make_join_card(url, out)
    print(f"Join card saved to: {result}")
