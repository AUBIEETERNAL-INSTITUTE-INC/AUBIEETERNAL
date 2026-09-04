"""
AUBIEETERNAL QR Airlock v0.1 — household-local QR decode + hash + verdict.

Imported as a package: ``from tools.qr_airlock.api import router as qr_router``.
The one function the tutor / kiosk should call is ``check_qr``:

    from tools.qr_airlock import check_qr
    result = check_qr(payload="https://example.com/menu")

Never opens, fetches, or navigates to anything found inside a QR. No photos
leave the rig; no flag is published without an explicit human git step.
"""
from .airlock import check_qr

__all__ = ["check_qr"]
