"""QR Airlock phase 2 - sandbox worker. Runs ONLY inside the bwrap jail built by sandbox.py.

Inside the jail there is no network at all (own empty netns, loopback only). The only way out
is the unix socket /sbx/run/proxy.sock, which this script exposes to Chromium as an HTTP proxy
on the jail's private 127.0.0.1:3128. The host side of that socket (sandbox.py) refuses every
destination that is not a public internet address on port 80/443, so the page can't reach the
rig, its LAN, the tailnet or the rig's localhost. Fresh in-memory profile, no cookies, downloads
refused, hard time budget. Prints one JSON object on stdout and exits.
"""
import asyncio, base64, json, os, sys, time

SOCK = "/sbx/run/proxy.sock"
PORT = 3128
BUDGET = float(os.environ.get("SBX_BUDGET", "15"))

FIELDS_JS = r"""() => {
  const out = {password:0, card:0, login:0, otp:0, forms:0, inputs:0};
  const card = /(card|cc-?num|ccnum|cvv|cvc|csc|security.?code|expir|exp-?date|cardholder)/i;
  const login = /(user(name)?|login|e-?mail|account|signin|sign-in)/i;
  const otp = /(otp|one.?time|verification.?code|2fa|mfa|sms.?code)/i;
  document.querySelectorAll('form').forEach(() => out.forms++);
  document.querySelectorAll('input,select').forEach(el => {
    out.inputs++;
    const t = (el.getAttribute('type') || '').toLowerCase();
    const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
    const s = [el.name, el.id, el.getAttribute('placeholder'), el.getAttribute('aria-label'), ac].join(' ');
    if (t === 'password' || ac.includes('password')) out.password++;
    if (ac.startsWith('cc-') || card.test(s)) out.card++;
    if (otp.test(s) || ac === 'one-time-code') out.otp++;
    if ((t === 'email' || t === 'text' || t === '') && login.test(s)) out.login++;
  });
  return out;
}"""

async def pump(r, w):
    try:
        while True:
            b = await r.read(65536)
            if not b:
                break
            w.write(b)
            await w.drain()
    except Exception:
        pass
    finally:
        try: w.close()
        except Exception: pass

async def forward(cr, cw):
    try:
        ur, uw = await asyncio.open_unix_connection(SOCK)
    except Exception:
        cw.close(); return
    await asyncio.gather(pump(cr, uw), pump(ur, cw))

async def main(url):
    t0 = time.monotonic()
    left = lambda: BUDGET - (time.monotonic() - t0)
    srv = await asyncio.start_server(forward, "127.0.0.1", PORT)
    out = {"ok": False, "start_url": url, "chain": [], "navigations": [], "downloads": [], "popups": [],
           "tls": [], "fields": {}, "title": "", "final_url": "", "error": None, "dialogs": 0}
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy={"server": f"http://127.0.0.1:{PORT}"},
            args=["--proxy-bypass-list=<-loopback>", "--disable-quic", "--no-first-run",
                  "--disable-background-networking", "--disable-sync", "--disable-extensions",
                  "--disable-features=PushMessaging,BackgroundFetch,InterestFeedContentSuggestions",
                  "--disable-webrtc-hw-encoding", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
        ctx = await browser.new_context(accept_downloads=False, ignore_https_errors=False,
                                        service_workers="block", viewport={"width": 1000, "height": 720},
                                        java_script_enabled=True, permissions=[], locale="en-US")
        page = await ctx.new_page()
        page.on("download", lambda d: out["downloads"].append({"url": d.url[:500], "file": d.suggested_filename[:200]}))
        page.on("popup", lambda pg: out["popups"].append(pg.url[:500]))
        page.on("framenavigated", lambda f: f == page.main_frame and out["navigations"].append(f.url[:500]))
        def _dialog(d):
            out["dialogs"] += 1
            asyncio.ensure_future(d.dismiss())
        page.on("dialog", _dialog)
        resp = None
        try:
            resp = await page.goto(url, wait_until="load", timeout=max(1000, (left() - 4) * 1000))
        except Exception as e:
            out["error"] = str(e).split("\n")[0][:300]
            if "Download is starting" in out["error"]:
                out["error"] = None
        # brief settle so meta-refresh / JS redirects show up, bounded by the budget
        try:
            await page.wait_for_timeout(max(0, min(2500, (left() - 3) * 1000)))
        except Exception:
            pass
        if resp is not None:
            hops, req = [], resp.request
            while req is not None:
                hops.append(req)
                req = req.redirected_from
            for rq in reversed(hops):
                r = await rq.response() if rq is not resp.request else resp
                hop = {"url": rq.url[:500], "status": r.status if r else None}
                if r is not None:
                    try:
                        sd = await r.security_details()
                    except Exception:
                        sd = None
                    if sd:
                        out["tls"].append({"url": rq.url[:200], **{k: sd.get(k) for k in ("subjectName", "issuer", "protocol", "validFrom", "validTo")}})
                out["chain"].append(hop)
        try:
            out["final_url"] = page.url[:500]
            out["title"] = (await page.title())[:200]
        except Exception:
            pass
        agg = {}
        for fr in page.frames[:15]:
            try:
                f = await asyncio.wait_for(fr.evaluate(FIELDS_JS), timeout=1.5)
                for k, v in f.items():
                    agg[k] = agg.get(k, 0) + v
            except Exception:
                pass
        out["fields"] = agg
        try:
            png = await page.screenshot(type="jpeg", quality=60, timeout=max(500, (left() - 0.5) * 1000))
            out["screenshot"] = "data:image/jpeg;base64," + base64.b64encode(png).decode()
        except Exception:
            out["screenshot"] = None
        out["ok"] = resp is not None or bool(out["downloads"])
        try:
            await asyncio.wait_for(browser.close(), timeout=2)
        except Exception:
            pass
    srv.close()
    out["ms"] = round((time.monotonic() - t0) * 1000)
    return out

if __name__ == "__main__":
    try:
        res = asyncio.run(asyncio.wait_for(main(sys.argv[1]), timeout=BUDGET + 2))
    except Exception as e:
        res = {"ok": False, "error": f"sandbox run failed: {type(e).__name__}: {str(e)[:200]}"}
    sys.stdout.write("\n@@SBX@@" + json.dumps(res) + "\n")
