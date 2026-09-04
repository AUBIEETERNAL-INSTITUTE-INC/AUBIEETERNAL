# AUBIEETERNAL QR Flag Spec v0.1

Public, shareable record for a flagged QR payload. Publish this — never
photos, never scanner identity, never GPS.

```json
{
  "spec": "aubieeternal-qr-flag/v0.1",
  "id": "flag_20260904_001",
  "status": "sighting",
  "verdict": "suspicious",
  "payload_sha256": "hex of exact decoded QR text (UTF-8, no extra whitespace)",
  "payload_kind": "url",
  "final_url": "https://example-phish.tld/pay",
  "registered_domain": "example-phish.tld",
  "claimed_as": "menu",
  "signals": ["url_shortener", "domain_age_under_7d", "login_form"],
  "venue": {
    "name": "optional public business name",
    "city": "optional",
    "note": "table sticker overlay — do not treat venue as the attacker"
  },
  "first_seen_utc": "2026-09-04T10:00:00Z",
  "sighting_count": 1,
  "publisher": "household | institute",
  "publisher_key_id": "optional pubkey id",
  "signature": null,
  "privacy": "no image, no scanner identity, no GPS"
}
```

## Rules

- Hash the **payload string** (`sha256_hex(payload.strip().encode('utf-8'))`),
  not the PNG. See `hash_payload.py`.
- Separate **payload** (the lie inside the square) from **venue** (the
  restaurant/business). A stolen sticker does not mean the business is a
  scam — the `venue.note` field exists specifically to say this out loud.
- `status` lifecycle: `sighting` → `confirmed` (institute key, or ≥3
  independent household publishers — see `CONFIRMED_SIGHTING_THRESHOLD`
  in `verdict.py`) → `withdrawn`.
- Grok / other AIs do **not** get a live feed pushed to them — they look
  this file up (or a cached copy) at scan time. No auto-share of one
  household's brain across the lattice.
- Future (not in v0.1): same record signed as a Nostr event; submission
  of `final_url` to existing public threat-intel buckets. v0.1 is a
  static JSON list only.

## File locations (institute repo)

- Public feed: `public/flags/qr-flags.json`
- This spec: co-located as `QR_FLAG_SPEC.md`
