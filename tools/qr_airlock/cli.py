"""
cli.py — quick manual test: check a payload or an image file from disk.

    python cli.py --payload "https://paypa1-secure.tld/verify"
    python cli.py --image screenshot.png
"""
from __future__ import annotations

import argparse
import base64
import json

try:
    from .airlock import check_qr
except ImportError:
    # Allow `python tools/qr_airlock/cli.py ...` from the repo root, not just
    # `python -m tools.qr_airlock.cli ...`.
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from tools.qr_airlock.airlock import check_qr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", help="Raw decoded QR text to check directly.")
    ap.add_argument("--image", help="Path to an image file containing a QR code.")
    ap.add_argument("--claimed-as", default="", help="e.g. menu, wifi, payment, coupon")
    ap.add_argument("--who", default="cli")
    args = ap.parse_args()

    image_b64 = None
    if args.image:
        with open(args.image, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("ascii")

    result = check_qr(
        payload=args.payload,
        image_b64=image_b64,
        claimed_as=args.claimed_as,
        who=args.who,
        source="cli",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
