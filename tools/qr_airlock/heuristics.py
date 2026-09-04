"""
heuristics.py — cheap, offline suspicious-signal checks.

No network calls. No domain-age lookups (would require an external API —
left as a documented gap, not faked). These are the "hard-coded heuristics
first" from the handoff, meant to work even fully offline.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

# Known URL shorteners — not exhaustive, extend locally as needed.
KNOWN_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "tiny.cc", "rb.gy", "s.id",
    "qr.link", "qrco.de", "v.gd", "lnkd.in", "surl.li",
}

# A short list of high-value brands worth flagging lookalikes for.
# Extend this locally — this is intentionally small to avoid false positives.
WATCHED_BRANDS = [
    "paypal", "apple", "microsoft", "google", "amazon", "venmo", "zelle",
    "chase", "wellsfargo", "bankofamerica", "netflix", "instagram",
    "facebook", "usps", "fedex", "ups", "docusign",
]

# Common leetspeak/typo substitutions attackers use in lookalike domains.
_LOOKALIKE_SUBS = {
    "a": ["a", "4", "@"],
    "e": ["e", "3"],
    "i": ["i", "1", "l", "!"],
    "o": ["o", "0"],
    "s": ["s", "5", "$"],
}


@dataclass
class Signals:
    codes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add(self, code: str, note: str = ""):
        self.codes.append(code)
        if note:
            self.notes.append(note)


def _looks_like_brand_typo(host_label: str, brand: str) -> bool:
    """Very cheap fuzzy check: same length +/-1, mostly-matching chars,
    or a known char-substitution pattern (paypa1, arnaz0n, g00gle)."""
    if host_label == brand:
        return False  # exact match isn't a typo
    if abs(len(host_label) - len(brand)) > 1:
        return False
    # Normalize common substitutions back to letters and compare
    normalized = host_label
    for letter, subs in _LOOKALIKE_SUBS.items():
        for s in subs:
            if s != letter:
                normalized = normalized.replace(s, letter)
    if normalized == brand:
        return True
    # Simple edit-distance-1 check for same-length strings
    if len(host_label) == len(brand):
        diffs = sum(1 for a, b in zip(host_label, brand) if a != b)
        if diffs == 1:
            return True
    return False


def is_ip_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def analyze_url(url: str) -> Signals:
    sig = Signals()
    try:
        parsed = urlparse(url)
    except Exception:
        sig.add("unparseable_url", "URL could not be parsed at all — treat as suspicious.")
        return sig

    if parsed.scheme not in ("http", "https"):
        sig.add("non_http_scheme", f"Scheme is '{parsed.scheme}', not http/https.")

    netloc = parsed.netloc or ""

    # userinfo in URL (user:pass@host or plain user@host) — classic obfuscation
    if "@" in netloc:
        sig.add("userinfo_in_url", "URL contains '@' before the host — the real "
                 "destination is after the @, everything before it is decoration.")
        netloc = netloc.rsplit("@", 1)[-1]

    host = netloc.split(":")[0].lower()

    if not host:
        sig.add("no_host", "No host could be extracted from the URL.")
        return sig

    if is_ip_host(host):
        sig.add("ip_host", f"Destination is a raw IP address ({host}), not a domain name.")

    if host.startswith("xn--") or ".xn--" in host:
        sig.add("punycode_host", "Domain uses punycode (xn--...), often used to fake "
                 "look-alike letters from other alphabets.")

    if host in KNOWN_SHORTENERS:
        sig.add("url_shortener", f"'{host}' is a known link shortener — the real "
                 "destination is hidden until you click.")

    if host.count("-") >= 3:
        sig.add("many_hyphens", f"Domain has {host.count('-')} hyphens — common in "
                 "throwaway phishing domains.")

    labels = host.split(".")
    # crude "registered domain" guess: second-level label (ignores multi-part TLDs like .co.uk)
    if len(labels) >= 2:
        sld = labels[-2]
        for brand in WATCHED_BRANDS:
            if brand in sld and sld != brand:
                # e.g. "paypal-secure" — brand name plus extra text
                sig.add("brand_plus_extra", f"Domain '{host}' contains brand name "
                         f"'{brand}' plus extra text — official sites rarely do this.")
                break
            if _looks_like_brand_typo(sld, brand):
                sig.add("brand_lookalike", f"Domain label '{sld}' closely resembles "
                         f"'{brand}' — possible typosquat.")
                break

    path_q = (parsed.path or "") + "?" + (parsed.query or "")
    if re.search(r"(login|signin|verify|password|update.?billing|confirm.?account)", path_q, re.I):
        sig.add("credential_path", "URL path suggests a login/verification/billing page.")

    return sig


def analyze_payload(payload: str, claimed_as: str = "") -> Signals:
    """
    Top-level heuristic entry point. Handles both URL and non-URL payloads
    (QR codes can carry wifi configs, vCards, plain text, etc).
    """
    stripped = payload.strip()
    if re.match(r"^https?://", stripped, re.I):
        sig = analyze_url(stripped)
    elif stripped.upper().startswith("WIFI:"):
        sig = Signals()
        sig.add("wifi_payload", "This QR configures Wi-Fi, not a link — "
                 "review the network name before connecting.")
    else:
        sig = Signals()
        sig.add("non_url_payload", "Payload is not a standard http(s) link "
                 "(could be text, vCard, wifi, etc). Read it before acting on it.")

    if claimed_as and claimed_as.lower() in ("menu", "wifi", "payment", "coupon"):
        if "login" in stripped.lower() or "verify" in stripped.lower() or "@" in stripped:
            sig.add("mismatch_with_claim", f"Sticker claims to be a '{claimed_as}' but "
                     "payload content looks like a login/payment/redirect flow.")

    return sig
