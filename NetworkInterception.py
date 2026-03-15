from patchright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs

URL = "https://cd.captchaaiplus.com/turnstile.html"

INJECTED_TOKEN = "0.ywJS5qJ52JpXeHt9Xm9Afm_8f8YOOi4HojBUIBv-qbY8GnB4tcVSZN4h6x4aAuQhSNFP0U5lzhOxq68h5F_vivBwnw3NjgperDwIhRy5-09MtJesOj7xLS2sG9Ev-d7Hrk83W02hUUfrpIMs_wr_evkvsv7FRF7YPmzW_mnI4foSm4_UX-BSz42Es8vaAukx3VIemMWJQuG7OqaoIt0FQoPb28KRfNY1ZcaP1K9YjNMAi3OriFxO4aCNeYECCFDwZgBCX-7P2y86L3tQ2aJ5E5vfAdUPTpzj_QozB8Q7IELZ-IefnkhhTkkZ6E29iKLZay6qT-Qn-AT3MwsUXnxtL-0bi8wCz2YwR0Xg8aUfFDUhUILcS3nhePYal-_-LEV2uen2pvV3P62A49qWw5MyhkX0ytSnYhDYU7Hi64laEp6SdCSfjQC8ty3qCPsAmaTLCX3bF2sBuV9QtGjFdIAuUriU3B6eTE3aEVPmEkQ52GiklAjbQrgGXfSo3oCWplMQLb9EYegp0y7DrSrUrOABBNhnux6_JWqZQd0LYVvlRU5Fkeeh4VSgdjQzS9T8Z0NMMxEdxyyS-vVSFB02GazXFwQim017njt_LP8ql1UzYy2iXKRtgaKe3xz5RuRlyfm9XMnrH5Coyve_Xx9ZLJSJgxEvI9C3YejrNpzvDdw7uZe74uthWm3U2N5fcjwbSzxWG05G4Kt7m8XrdSXp7pkYep4IbLRZEXCKLo4dpk8C0bk-cgc53lTXrd7WLojtYPioweame4HEctoV_zJuGWXCNt75QaNkiKKA_9hcwTrikwn9ngd-IibjLewXTAibl_X65xbhbd4Pwx7Tq5BWVpTc-bPOzhfcDPvVcao8H_Y1FxOMbYGNjlGFfVPU_cqXSi7GnyAU3SMYbNs2h1cEHS4nCSR_0pCORe1VGNZe8JywQjE.Zp8AsXztW7O_D4ApCm8Pvg.7fcf43ee8640d1537c82f2f111cee4f4114ea774feada562c6da6b9a04636fa5"

BLOCK_PATTERNS = [
    "challenges.cloudflare.com",
    "cf-turnstile",
    "turnstile/v0",
]


def is_turnstile_url(url: str) -> bool:
    return any(p in url for p in BLOCK_PATTERNS)


def run_task2(playwright):

    browser = playwright.chromium.launch(
        channel="chrome",
        headless=False,
        args=[
            "--no-sandbox",
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    context = browser.new_context(no_viewport=True)
    page = context.new_page()

    captured = {
        "sitekey": None,
        "pageaction": None,
        "cdata": None,
        "pagedata": None,
        "blocked_urls": [],
    }

    def handle_route(route, request):
        url = request.url

        if is_turnstile_url(url):

            qs = parse_qs(urlparse(url).query)

            for key in ("pageaction", "cdata", "pagedata"):
                if key in qs and not captured[key]:
                    captured[key] = qs[key][0]

            captured["blocked_urls"].append(url)

            print(f"BLOCKED → {url[:110]}")

            route.abort()

        else:
            route.continue_()

    page.route("**/challenges.cloudflare.com/**", handle_route)
    page.route("**/*turnstile*", handle_route)

    try:

        print("\n" + "=" * 50)
        print("TASK 2 — Network Interception & Token Injection")
        print("=" * 50)

        page.goto(URL, wait_until="domcontentloaded", timeout=30000)

        page.wait_for_timeout(4000)

        captured["sitekey"] = page.evaluate(
            """
            () => {
                const el = document.querySelector('[data-sitekey]');
                return el ? el.getAttribute('data-sitekey') : null;
            }
        """
        )

        for attr, key in [
            ("data-action", "pageaction"),
            ("data-cdata", "cdata"),
            ("data-pagedata", "pagedata"),
        ]:

            val = page.evaluate(
                f"""
                () => {{
                    const el = document.querySelector('[{attr}]');
                    return el ? el.getAttribute('{attr}') : null;
                }}
            """
            )

            if val:
                captured[key] = val

        print("\nCAPTURED TURNSTILE DETAILS:")

        print(f"Sitekey: {captured['sitekey']}")
        print(f"Pageaction: {captured['pageaction'] or 'N/A'}")
        print(f"Cdata: {captured['cdata'] or 'N/A'}")
        print(f"Pagedata: {captured['pagedata'] or 'N/A'}")

        print(f"\nBlocked requests ({len(captured['blocked_urls'])}):")

        for u in captured["blocked_urls"]:
            print(f"• {u[:110]}")

        iframe_count = page.evaluate(
            """
            () => [...document.querySelectorAll('iframe')]
                    .filter(f => f.src && f.src.includes('cloudflare')).length
        """
        )

        print(f"\nCloudflare iframes rendered : {iframe_count}")
        print(
            f"Turnstile widget blocked : {'YES' if len(captured['blocked_urls']) > 0 else 'NO'}"
        )

        page.wait_for_timeout(2000)

        print("\nInjecting token…")

        injected_ok = page.evaluate(
            """
            (token) => {

                let el = document.querySelector('[name="cf-turnstile-response"]')

                if(!el){

                    el=document.createElement('input')
                    el.type='hidden'
                    el.name='cf-turnstile-response'
                    el.id='cf-turnstile-response'

                    const anchor =
                        document.querySelector('.cf-turnstile') ||
                        document.querySelector('form') ||
                        document.body

                    anchor.appendChild(el)
                }

                const nativeSetter =
                    Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype,'value'
                    ).set

                nativeSetter.call(el,token)

                el.dispatchEvent(new Event('input',{bubbles:true}))
                el.dispatchEvent(new Event('change',{bubbles:true}))

                return true
            }
        """,
            INJECTED_TOKEN,
        )

        if not injected_ok:
            print("Could not inject token")
            return

        written = page.evaluate(
            "() => document.querySelector('[name=\"cf-turnstile-response\"]')?.value?.slice(0,72)"
        )

        print(f"Field value : {written}…")

        page.wait_for_timeout(2000)

        print("\nClicking submit…")

        page.locator(
            "input[type='submit'], #submit-btn, button[type='submit']"
        ).first.click()

        page.wait_for_timeout(4000)

        result = ""

        try:
            result = page.locator("#result").inner_text(timeout=4000)
        except:
            pass

        if "success" in page.content().lower() or "success" in result.lower():
            print(f"\nSUCCESS — {result.strip()}")
        else:
            body = page.locator("body").inner_text()
            print(f"\nFAILED — response: {body[:400]}")

        page.wait_for_timeout(5000)

    except Exception as e:
        print(f"\nError: {e}")

    finally:
        context.close()
        browser.close()


with sync_playwright() as p:
    run_task2(p)
