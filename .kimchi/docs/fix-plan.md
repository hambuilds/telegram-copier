# Fix Plan: ERR_HTTP2_PROTOCOL_ERROR on IRCTC

## Problem
Browser opens and closes quickly. Error:
```
Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://www.irctc.co.in/online-charts/
```

## Root Cause (Confirmed)
IRCTC detects headless Chromium via the `sec-ch-ua` header which includes `"HeadlessChrome"`. The server intentionally drops the HTTP/2 stream, causing the error. This is a documented anti-bot protection pattern.

## Fix
Modify `chart_scraper.py` `_new_page()` and `__aenter__()` to:

1. **Launch chromium with `--disable-http2`** flag (forces HTTP/1.1, avoids the HTTP/2 error entirely)
2. **Create page with modified headers:**
   - `sec-ch-ua`: `"\"Not.A/Brand\";v=\"99\", \"Chromium\";v=\"136\""` (note: no `HeadlessChrome`)
   - `User-Agent`: standard desktop Chrome UA (not headless)

## Why this works
- Disabling HTTP/2 bypasses the protocol error entirely
- Modified headers make the browser appear as regular Chrome, not headless
- Proven solution per Playwright GitHub issues #36001, #27600, #31216

## Files to change
- `irctc-vacancy-checker/chart_scraper.py` only

## Verification
1. Run `python3 -m pytest tests/ -v` — all 12 tests should still pass
2. Run the actual command with `--headless` — should successfully navigate the page
