"""
wifi.py — parse `WIFI:` QR payloads for DISPLAY ONLY.

A Wi-Fi QR (the Android/iOS standard, `WIFI:T:WPA;S:MySSID;P:secret;H:false;;`)
is a network-join config, not a link. The airlock:

  * never joins it (there is nothing in this package that connects to Wi-Fi);
  * never runs it through the safe / unsafe verdict system — an SSID string
    carries no "safe link" meaning, so a WIFI payload gets its own display
    path and is out of scope for evaluate() entirely;
  * never returns a bare "safe" for it.

All this module does is pull out the parts a person needs to read before
typing a network in by hand: the SSID, and — the security-relevant bit —
whether the network is open (no password) or encrypted, worded plainly.

Fast, local, offline. No model call.
"""
from __future__ import annotations

from typing import Optional


def is_wifi_payload(payload: str) -> bool:
    return payload.strip().upper().startswith("WIFI:")


def _split_fields(body: str) -> list[tuple[str, str]]:
    """Split `T:WPA;S:My;Net;P:pw;;` into (key, value) pairs, honouring the
    spec's backslash escaping (`\\;` `\\,` `\\:` `\\\\`). An unescaped ';'
    ends a field; the first unescaped ':' in a field separates key from value.
    """
    fields: list[tuple[str, str]] = []
    buf: list[str] = []
    esc = False
    raw_fields: list[str] = []
    for ch in body:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ";":
            raw_fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        raw_fields.append("".join(buf))

    for rf in raw_fields:
        if not rf:
            continue
        # key is up to the first ':' (keys are single letters, never escaped)
        if ":" in rf:
            key, val = rf.split(":", 1)
        else:
            key, val = rf, ""
        fields.append((key.strip().upper(), val))
    return fields


def _encryption_wording(auth: str, password: str) -> tuple[str, bool]:
    """Return (plain-English encryption description, is_open)."""
    a = (auth or "").strip().lower()
    if a in ("", "nopass") or (not password and a in ("", "nopass")):
        return "Open network, no password", True
    if not password:
        # type claims encryption but no key travelled in the code
        base = _named(a)
        return f"{base} (marked encrypted, but no password is in this code)", False
    return _named(a), False


def _named(a: str) -> str:
    return {
        "wep": "WEP (weak, outdated encryption)",
        "wpa": "WPA/WPA2",
        "wpa2": "WPA2",
        "wpa2-eap": "WPA2-Enterprise",
        "wpa3": "WPA3",
        "sae": "WPA3 (SAE)",
    }.get(a, a.upper() or "unknown")


def parse_wifi_payload(payload: str) -> dict:
    """Parse a WIFI: payload into a display-only dict. Raises no exceptions —
    a malformed payload just yields blank/'unknown' fields."""
    stripped = payload.strip()
    body = stripped[5:] if stripped.upper().startswith("WIFI:") else stripped

    ssid = ""
    password = ""
    auth = ""
    hidden = False
    for key, val in _split_fields(body):
        if key == "S":
            ssid = val
        elif key == "P":
            password = val
        elif key == "T":
            auth = val
        elif key == "H":
            hidden = val.strip().lower() in ("true", "1", "yes")

    encryption, is_open = _encryption_wording(auth, password)

    return {
        "kind": "wifi",
        "verdict": None,  # deliberately NOT in the safe/unsafe verdict system
        "ssid": ssid,
        "ssid_display": ssid or "(no network name in code)",
        "hidden": hidden,
        "auth_type": (auth or "").strip(),
        "encryption": encryption,
        "is_open": is_open,
        "has_password_in_code": bool(password),
        "note": (
            "This QR code sets up Wi-Fi — it is not a link. Aubie will not "
            "join it for you. If you trust where the code came from, type the "
            "network name in by hand."
        ),
    }
