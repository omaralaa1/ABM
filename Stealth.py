from patchright.sync_api import sync_playwright
import time
import os
import random
import math

URL = "https://cd.captchaaiplus.com/turnstile.html"
ATTEMPTS = 10
success = 0

task2_token = None

STEALTH_SCRIPT = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    window.chrome = {
        app: { isInstalled: false, InstallState: {}, RunningState: {} },
        runtime: { PlatformOs: {}, PlatformArch: {}, PlatformNaclArch: {} },
        loadTimes: function() {},
        csi: function() {},
    };

    const pluginData = [
        { name: 'PDF Viewer',           filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer',    filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
        { name: 'Chromium PDF Viewer',  filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
        { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'WebKit built-in PDF',  filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
    ];
    const plugins = pluginData.map((p, i) => {
        const plugin = Object.create(Plugin.prototype);
        Object.defineProperties(plugin, {
            name:        { value: p.name,        enumerable: true },
            description: { value: p.description, enumerable: true },
            filename:    { value: p.filename,    enumerable: true },
            length:      { value: 0 },
        });
        return plugin;
    });
    const pluginArray = Object.create(PluginArray.prototype);
    Object.defineProperty(pluginArray, 'length', { value: plugins.length });
    plugins.forEach((p, i) => {
        Object.defineProperty(pluginArray, i, { value: p, enumerable: true });
        Object.defineProperty(pluginArray, p.name, { value: p });
    });
    pluginArray.item      = (i)    => plugins[i] || null;
    pluginArray.namedItem = (name) => plugins.find(p => p.name === name) || null;
    pluginArray.refresh   = () => {};
    Object.defineProperty(navigator, 'plugins', { get: () => pluginArray });

    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

    const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
    window.navigator.permissions.query = (params) => {
        if (['notifications', 'push', 'camera', 'microphone'].includes(params.name)) {
            return Promise.resolve({ state: 'prompt', onchange: null });
        }
        return origQuery(params);
    };

    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory',        { get: () => 8 });

    if (navigator.userAgentData) {
        Object.defineProperty(navigator.userAgentData, 'brands', {
            get: () => [
                { brand: 'Google Chrome',  version: '124' },
                { brand: 'Chromium',       version: '124' },
                { brand: 'Not-A.Brand',    version: '99'  },
            ]
        });
        Object.defineProperty(navigator.userAgentData, 'mobile', { get: () => false });
    }
}
"""


def human_mouse_move(page, target_x, target_y, steps=25):
    try:
        cur = page.evaluate("() => ({ x: window.innerWidth/2, y: window.innerHeight/2 })")
        sx, sy = cur['x'], cur['y']
        for i in range(1, steps + 1):
            t  = i / steps
            et = t * t * (3 - 2 * t)
            jx = random.uniform(-3, 3) * math.sin(t * math.pi)
            jy = random.uniform(-3, 3) * math.sin(t * math.pi)
            mx = sx + (target_x - sx) * et + jx
            my = sy + (target_y - sy) * et + jy
            page.mouse.move(mx, my)
            page.wait_for_timeout(random.randint(8, 22))
    except Exception:
        page.mouse.move(target_x, target_y)


def find_turnstile_frame(page, timeout_ms=20000):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                return frame
        page.wait_for_timeout(500)
    return None


def wait_for_token(page, max_wait_ms=20000):
    deadline = time.time() + max_wait_ms / 1000
    while time.time() < deadline:
        token = page.evaluate("""
            () => {
                const el = document.querySelector('[name="cf-turnstile-response"]');
                return (el && el.value.length > 10) ? el.value : null;
            }
        """)
        if token:
            return token
        page.wait_for_timeout(800)
    return None


def run_test(playwright, headless_mode, attempt, capture_only=False):
    global task2_token

    extra_args = [
        "--no-sandbox",
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--lang=en-US,en",
    ]
    if headless_mode:
        extra_args += [
            "--window-size=1280,720",
            "--disable-dev-shm-usage",
            "--use-gl=swiftshader",
            "--enable-webgl",
            "--ignore-gpu-blacklist",
        ]

    browser = playwright.chromium.launch(
        channel="chrome",
        headless=headless_mode,
        slow_mo=80,
        args=extra_args,
        ignore_default_args=["--enable-automation"],
    )

    context = browser.new_context()
    context.add_init_script(STEALTH_SCRIPT)
    page = context.new_page()

    try:
        label = "TOKEN CAPTURE (no submit)" if capture_only else f"Attempt {attempt:02d}/{ATTEMPTS}"
        print(f"\n{'='*50}")
        print(f"Cycle {attempt:02d} | {label} | headless={headless_mode}")
        print(f"{'='*50}")

        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(".cf-turnstile", timeout=15000)
        print("Page loaded — Turnstile container present")

        page.wait_for_timeout(random.randint(800, 1500))

        try:
            box = page.locator(".cf-turnstile").bounding_box()
            if box:
                cx = box['x'] + box['width'] / 2
                cy = box['y'] + box['height'] / 2
                human_mouse_move(page, cx, cy)
                page.wait_for_timeout(random.randint(300, 700))
        except Exception:
            pass

        token = wait_for_token(page, max_wait_ms=15000)

        if not token:
            print("   No auto-token — locating iframe...")
            frame = find_turnstile_frame(page, timeout_ms=10000)
            if frame:
                page.wait_for_timeout(random.randint(1500, 2500))
                for sel in ["input[type='checkbox']", ".ctp-checkbox-label", "label", "body"]:
                    try:
                        el = frame.locator(sel)
                        if el.count() > 0:
                            try:
                                fb = el.first.bounding_box()
                                if fb:
                                    human_mouse_move(page, fb['x'] + fb['width']/2,
                                                          fb['y'] + fb['height']/2)
                                    page.wait_for_timeout(random.randint(200, 500))
                            except Exception:
                                pass
                            el.first.click(force=True, timeout=3000)
                            print(f"   Clicked: '{sel}'")
                            break
                    except Exception:
                        continue
                token = wait_for_token(page, max_wait_ms=15000)
            else:
                print("iframe not found")

        if not token:
            print(f"FAILED — no token (headless={headless_mode})")
            return False, None

        print(f"Token : {token[:72]}...")

        if capture_only:
            task2_token = token
            print("Token saved for Task 2 — skipping submit to keep token valid")
            page.wait_for_timeout(2000)
            return True, token

        page.locator(
            "input[type='submit'], #submit-btn, button[type='submit']"
        ).first.click()
        page.wait_for_timeout(3000)

        result = ""
        try:
            result = page.locator("#result").inner_text(timeout=3000)
        except Exception:
            pass

        if "success" in page.content().lower() or "success" in result.lower():
            print(f"FORM SUCCESS — {result.strip()}")
            return True, token
        else:
            print(f"Form rejected — #result: '{result}'")
            return False, None

    except Exception as e:
        print(f"Error: {e}")
        return False, None
    finally:
        context.close()
        browser.close()


HEADLESS_SCHEDULE = [
    False, False, True, False, True,
    False, False, False, True, False,
]

with sync_playwright() as p:

    print("\n" + "="*50)
    print("CYCLE 0 — Capturing token for Task 2")
    print("="*50)
    _, task2_token = run_test(p, headless_mode=False, attempt=0, capture_only=True)

    if task2_token:
        print(f"\n{'='*50}")
        print("  TASK 2 TOKEN")
        print(f"{'='*50}")
        print(f"  {task2_token}")
        print(f"{'='*50}\n")
    else:
        print("Could not capture Task 2 token — re-run or proceed manually")

    for i in range(ATTEMPTS):
        headless = HEADLESS_SCHEDULE[i]
        ok, _ = run_test(p, headless, attempt=i + 1, capture_only=False)
        if ok:
            success += 1

rate = (success / ATTEMPTS) * 100
print("\n" + "="*50)
print("FINAL RESULTS:-")
print("="*50)
print(f"  Total Attempts : {ATTEMPTS}")
print(f"  Successful     : {success}")
print(f"  Failed         : {ATTEMPTS - success}")
print("="*50)
