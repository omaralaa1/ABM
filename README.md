# ABM Egypt — Automation Engineer Assessment

Three automation tasks built with Python + Playwright (via `patchright`) covering stealth browser automation, network interception, and DOM scraping.

---

## Setup

```bash
pip install patchright
python -m patchright install chrome
```


---

## Task 1 — Stealth CAPTCHA Bypass (`Stealth.py`)

**Target:** https://cd.captchaaiplus.com/turnstile.html

Automates solving the Cloudflare Turnstile CAPTCHA without third-party solvers. The script spoofs browser fingerprints at the JS level (navigator properties, plugin list, permissions API, hardware concurrency, userAgentData brands) to appear as a real Chrome user.

**What it does:**
- Runs 10 attempts across a mixed headless/headed schedule
- On each attempt: loads the page, moves the mouse in a natural curved path toward the widget, waits for the token to auto-resolve, falls back to clicking the iframe checkbox if needed
- Prints the full token on success, then submits the form and checks for the "Success!" response
- A cycle 0 pass runs first in headed mode just to capture a clean token for Task 2 (without submitting, so the token stays valid)
- Prints a final summary with total attempts, passes, failures, and success rate




---

## Task 2 — Network Interception & Token Injection (`NetworkInterception.py`)

**Target:** https://cd.captchaaiplus.com/turnstile.html

Intercepts all Cloudflare Turnstile network requests before they reach the browser, preventing the widget from ever rendering. Then manually injects a pre-captured valid token directly into the hidden form field and submits.

**What it does:**
- Routes all requests matching `challenges.cloudflare.com`, `cf-turnstile`, and `turnstile/v0` through a handler that aborts them
- While blocking, extracts Turnstile metadata from query params and DOM attributes: `sitekey`, `pageaction`, `cdata`, `pagedata`
- Verifies zero Cloudflare iframes loaded in the DOM
- Injects the token via `HTMLInputElement.prototype` native setter (bypasses React/framework value tracking) and fires `input` + `change` events
- Submits the form and confirms the "Success! Verified" response

The token used (`INJECTED_TOKEN`) was captured from Task 1's cycle 0 run.



---

## Task 3 — DOM Scraping (`Scraping.py`)

**Target:** https://egypt.blsspainglobal.com/Global/CaptchaPublic/GenerateCaptcha?...

Scrapes every image on a page (100+) and separately identifies only the ones a human would actually see in their viewport.

**What it does:**

*All images → `task3_output/allimages.json`*
Walks the entire DOM collecting images from: `<img>` tags, `<picture>` source sets, `<canvas>` elements (via `toDataURL`), CSS `background-image` rules, `<svg image>` elements, and shadow roots. Each image is fetched and encoded as base64.

*Visible images only → `task3_output/visible_images_only.json`*
Filters down to elements that pass a strict visibility check: not `display:none`, not `visibility:hidden`, opacity > 0, non-zero dimensions, and inside the current viewport. Results are deduplicated by screen position and sorted top-to-bottom, left-to-right.

*Visible text → `task3_output/visible_texts.json`*
Scrapes `.box-label` and `.img-action-text` elements that are actually rendered on screen, with an `elementFromPoint` check to confirm nothing is covering them.

Individual image files are also saved to `task3_output/images/` as `img_001.jpg`, etc.



**Output files:**
```
task3_output/
├── allimages.json          # every image found
├── visible_images_only.json  # viewport-visible images only
├── visible_texts.json      # visible text labels
└── images/                 # viewable - all images found
```

---

## Notes

- All three scripts use `patchright` (a patched Playwright fork) with Chrome channel to avoid automation detection flags
- Task 1 and Task 2 work together — run Stealth.py first to generate a fresh token, then paste it into `task2_token` in NetworkInterception.py before running
