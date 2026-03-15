from patchright.sync_api import sync_playwright
import json
import os
import base64

URL = "https://egypt.blsspainglobal.com/Global/CaptchaPublic/GenerateCaptcha?data=4CDiA9odF2%2b%2bsWCkAU8htqZkgDyUa5SR6waINtJfg1ThGb6rPIIpxNjefP9UkAaSp%2fGsNNuJJi5Zt1nbVACkDRusgqfb418%2bScFkcoa1F0I%3d"

os.makedirs("task3_output", exist_ok=True)
os.makedirs("task3_output/images", exist_ok=True)


def fetch_image_as_base64(page, src: str) -> str:
    if not src or src.startswith("data:"):
        if "," in src:
            return src.split(",", 1)[1]
        return src

    try:
        b64 = page.evaluate("""
            async (url) => {
                try {
                    const resp = await fetch(url, { credentials: 'include' });
                    const buf  = await resp.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let binary = '';
                    for (let i = 0; i < bytes.byteLength; i++) {
                        binary += String.fromCharCode(bytes[i]);
                    }
                    return btoa(binary);
                } catch(e) {
                    return '';
                }
            }
        """, src)
        return b64 or ""
    except Exception as e:
        return ""


def save_image_file(b64_data, src, index, folder="task3_output/images"):
    try:
        if not b64_data:
            return
        ext = "jpg"
        for fmt in ["png", "gif", "webp", "jpeg", "jpg", "svg", "bmp"]:
            if fmt in src.lower():
                ext = fmt
                break
        if ext == "jpeg":
            ext = "jpg"
        fname = os.path.join(folder, f"img_{index:03d}.{ext}")
        with open(fname, "wb") as f:
            f.write(base64.b64decode(b64_data))
    except Exception as e:
        print(f"  couldn't save image {index}: {e}")


VISIBILITY_JS = """
    (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display    === 'none')    return false;
        if (style.visibility === 'hidden')  return false;
        if (parseFloat(style.opacity) === 0) return false;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        const inViewport = (
            rect.top    < window.innerHeight &&
            rect.bottom > 0 &&
            rect.left   < window.innerWidth  &&
            rect.right  > 0
        );
        return inViewport;
    }
"""

COLLECT_ALL_IMAGES_JS = """
    () => {
        const results = [];
        const seen = new Set();

        function addResult(entry) {
            const key = entry.src + '|' + entry.type;
            if (!seen.has(key) && entry.src) {
                seen.add(key);
                results.push(entry);
            }
        }

        function visibilityInfo(el) {
            const s = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
                isVisible: s.display !== 'none'
                    && s.visibility !== 'hidden'
                    && parseFloat(s.opacity) > 0
                    && r.width > 0 && r.height > 0,
                width:  Math.round(r.width),
                height: Math.round(r.height),
                x: Math.round(r.left),
                y: Math.round(r.top),
            };
        }

        document.querySelectorAll('img').forEach((img, idx) => {
            const src = img.currentSrc || img.src
                || img.getAttribute('data-src')
                || img.getAttribute('data-lazy-src') || '';
            const vis = visibilityInfo(img);
            addResult({
                index: idx,
                src,
                alt: img.alt || '',
                id: img.id || '',
                className: img.className || '',
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight,
                type: 'img',
                ...vis,
            });
        });

        document.querySelectorAll('picture source').forEach((src_el, idx) => {
            const srcset = src_el.srcset || '';
            const firstUrl = srcset.split(',')[0].trim().split(' ')[0];
            if (firstUrl) {
                const parentPicture = src_el.closest('picture');
                const img = parentPicture ? parentPicture.querySelector('img') : null;
                const vis = img ? visibilityInfo(img) : { isVisible: false };
                addResult({
                    index: idx,
                    src: firstUrl,
                    alt: img ? img.alt : '',
                    id: src_el.id || '',
                    className: src_el.className || '',
                    type: 'picture-source',
                    ...vis,
                });
            }
        });

        document.querySelectorAll('canvas').forEach((canvas, idx) => {
            try {
                const dataUrl = canvas.toDataURL('image/png');
                if (dataUrl && dataUrl !== 'data:,') {
                    const vis = visibilityInfo(canvas);
                    addResult({
                        index: idx,
                        src: dataUrl,
                        alt: canvas.getAttribute('aria-label') || '',
                        id: canvas.id || '',
                        className: canvas.className || '',
                        naturalWidth: canvas.width,
                        naturalHeight: canvas.height,
                        type: 'canvas',
                        ...vis,
                    });
                }
            } catch(e) {}
        });

        document.querySelectorAll('*').forEach((el, idx) => {
            const bg = window.getComputedStyle(el).backgroundImage;
            if (bg && bg !== 'none' && bg.includes('url(')) {
                const matches = [...bg.matchAll(/url\(["']?([^"')]+)["']?\)/g)];
                matches.forEach(match => {
                    const src = match[1];
                    if (src) {
                        const vis = visibilityInfo(el);
                        addResult({
                            index: idx,
                            src,
                            alt: el.getAttribute('aria-label') || '',
                            id: el.id || '',
                            className: typeof el.className === 'string' ? el.className : '',
                            tagName: el.tagName,
                            type: 'background-image',
                            ...vis,
                        });
                    }
                });
            }
        });

        document.querySelectorAll('svg image').forEach((img, idx) => {
            const src = img.getAttribute('href')
                || img.getAttribute('xlink:href')
                || img.getAttribute('src') || '';
            if (src) {
                const vis = visibilityInfo(img);
                addResult({
                    index: idx,
                    src,
                    alt: img.getAttribute('alt') || '',
                    id: img.id || '',
                    className: img.getAttribute('class') || '',
                    type: 'svg-image',
                    ...vis,
                });
            }
        });

        function walkShadowRoots(root) {
            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) {
                    el.shadowRoot.querySelectorAll('img').forEach((img, idx) => {
                        const src = img.currentSrc || img.src || '';
                        if (src) {
                            const vis = visibilityInfo(img);
                            addResult({
                                index: idx,
                                src,
                                alt: img.alt || '',
                                id: img.id || '',
                                className: img.className || '',
                                type: 'shadow-img',
                                ...vis,
                            });
                        }
                    });
                    el.shadowRoot.querySelectorAll('canvas').forEach((canvas, idx) => {
                        try {
                            const dataUrl = canvas.toDataURL('image/png');
                            if (dataUrl && dataUrl !== 'data:,') {
                                const vis = visibilityInfo(canvas);
                                addResult({
                                    index: idx,
                                    src: dataUrl,
                                    alt: '',
                                    id: canvas.id || '',
                                    className: canvas.className || '',
                                    type: 'shadow-canvas',
                                    ...vis,
                                });
                            }
                        } catch(e) {}
                    });
                    walkShadowRoots(el.shadowRoot);
                }
            });
        }
        walkShadowRoots(document);

        const urlPattern = /https?:\/\/[^"'\s]+\.(?:png|jpg|jpeg|gif|webp|svg|bmp|ico)(?:\?[^"'\s]*)?/gi;
        document.querySelectorAll('script:not([src])').forEach((script, idx) => {
            const text = script.textContent || '';
            const matches = text.match(urlPattern) || [];
            matches.forEach(url => {
                addResult({
                    index: idx,
                    src: url,
                    alt: '',
                    id: '',
                    className: '',
                    type: 'script-embedded-url',
                    isVisible: false,
                    width: 0,
                    height: 0,
                    x: 0,
                    y: 0,
                });
            });
        });

        return results;
    }
"""


def run(playwright):
    browser = playwright.chromium.launch(
        channel="chrome",
        headless=False,
        slow_mo=100,
        args=[
            "--no-sandbox",
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
    )

    context = browser.new_context()
    page = context.new_page()

    image_requests = []

    def on_request(request):
        if any(ext in request.url for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', 'image', 'captcha']):
            image_requests.append(request.url)

    page.on("request", on_request)

    try:
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        page.evaluate("""
            () => new Promise(resolve => {
                let total = 0;
                const step = 200;
                const timer = setInterval(() => {
                    window.scrollBy(0, step);
                    total += step;
                    if (total >= document.body.scrollHeight) {
                        clearInterval(timer);
                        window.scrollTo(0, 0);
                        resolve();
                    }
                }, 60);
            })
        """)
        page.wait_for_timeout(3000)

        page.evaluate("""
            () => Promise.all(
                [...document.querySelectorAll('img')]
                    .filter(img => !img.complete)
                    .map(img => new Promise(res => {
                        img.onload = img.onerror = res;
                    }))
            )
        """)
        page.wait_for_timeout(1000)

        counts = page.evaluate("""
            () => ({
                img_tags:     document.querySelectorAll('img').length,
                canvas_tags:  document.querySelectorAll('canvas').length,
                svg_images:   document.querySelectorAll('svg image').length,
                bg_images:    [...document.querySelectorAll('*')].filter(el =>
                                  window.getComputedStyle(el).backgroundImage.includes('url(')).length,
                total_dom:    document.querySelectorAll('*').length,
            })
        """)
        print("DOM snapshot:", counts)
        print(f"\nNetwork image requests intercepted: {len(image_requests)}")
        for url in image_requests:
            print(" ", url)

        print("\nCollecting all images...")
        raw_images = page.evaluate(COLLECT_ALL_IMAGES_JS)
        print(f"Raw entries collected: {len(raw_images)}")

        from collections import Counter
        type_counts = Counter(img.get("type", "?") for img in raw_images)
        for t, count in type_counts.most_common():
            print(f"  {t:30s}: {count}")

        all_images_out = []
        for i, img in enumerate(raw_images):
            src = img.get("src", "")
            print(f"  [{i+1:03d}/{len(raw_images)}] [{img.get('type','?'):20s}] {src[:70]}")

            if src.startswith("data:"):
                b64 = src.split(",", 1)[1] if "," in src else ""
            else:
                b64 = fetch_image_as_base64(page, src)

            save_image_file(b64, src, i + 1)

            all_images_out.append({**img, "base64": b64})

        with open("task3_output/allimages.json", "w", encoding="utf-8") as f:
            json.dump(all_images_out, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(all_images_out)} images to task3_output/allimages.json")

        print("\nFiltering visible images...")

        img_elements = page.locator("img").all()
        canvas_elements = page.locator("canvas").all()
        visible_imgs = []

        def try_visible_element(el, src_attr_names, img_type="img"):
            try:
                is_visible = page.evaluate(VISIBILITY_JS, el.element_handle())
                if not is_visible:
                    return

                src = ""
                for attr in src_attr_names:
                    val = el.get_attribute(attr)
                    if val:
                        src = val
                        break

                if src and not src.startswith(("http", "data:")):
                    src = page.evaluate("(s) => new URL(s, document.baseURI).href", src)

                alt        = el.get_attribute("alt") or ""
                el_id      = el.get_attribute("id")  or ""
                class_name = el.get_attribute("class") or ""
                box        = el.bounding_box() or {}

                print(f"Visible {img_type}: {src[:70]}")

                if src.startswith("data:"):
                    b64 = src.split(",", 1)[1] if "," in src else ""
                else:
                    b64 = fetch_image_as_base64(page, src)

                visible_imgs.append({
                    "src":       src,
                    "alt":       alt,
                    "id":        el_id,
                    "className": class_name,
                    "type":      img_type,
                    "width":     box.get("width"),
                    "height":    box.get("height"),
                    "x":         box.get("x"),
                    "y":         box.get("y"),
                    "base64":    b64,
                })
            except Exception as e:
                print(f"Skipping {img_type} element: {e}")

        for el in img_elements:
            try_visible_element(el, ["src", "currentSrc", "data-src", "data-lazy-src"], img_type="img")

        for el in canvas_elements:
            try:
                is_visible = page.evaluate(VISIBILITY_JS, el.element_handle())
                if not is_visible:
                    continue
                box = el.bounding_box() or {}
                data_url = page.evaluate(
                    "(canvas) => { try { return canvas.toDataURL('image/png'); } catch(e) { return ''; } }",
                    el.element_handle()
                )
                if not data_url or data_url == "data:,":
                    continue
                b64 = data_url.split(",", 1)[1] if "," in data_url else ""
                el_id      = el.get_attribute("id")    or ""
                class_name = el.get_attribute("class") or ""
                print(f"Visible canvas: id={el_id} {int(box.get('width',0))}x{int(box.get('height',0))}")
                visible_imgs.append({
                    "src":       data_url,
                    "alt":       "",
                    "id":        el_id,
                    "className": class_name,
                    "type":      "canvas",
                    "width":     box.get("width"),
                    "height":    box.get("height"),
                    "x":         box.get("x"),
                    "y":         box.get("y"),
                    "base64":    b64,
                })
            except Exception as e:
                print(f"Skipping canvas: {e}")

        visible_imgs.sort(key=lambda v: (v.get("y") or 0, v.get("x") or 0))

        seen_positions = set()
        deduplicated = []
        for img in visible_imgs:
            pos_key = (round(img.get("x") or 0), round(img.get("y") or 0))
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                deduplicated.append(img)
        visible_imgs = deduplicated


        with open("task3_output/visible_images_only.json", "w", encoding="utf-8") as f:
            json.dump(visible_imgs, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(visible_imgs)} visible images to task3_output/visible_images_only.json")

        visible_texts = page.evaluate("""
            () => {
                const results = [];

                document.querySelectorAll('.box-label').forEach(el => {
                    const text = el.textContent.trim();
                    if (!text) return;
                    const s    = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const visible = (
                        s.display     !== 'none'   &&
                        s.visibility  !== 'hidden' &&
                        parseFloat(s.opacity) > 0  &&
                        rect.width  > 0 && rect.height > 0 &&
                        rect.top    >= 0 && rect.top < window.innerHeight &&
                        rect.bottom > 0
                    );
                    if (visible) {
                        const cx   = rect.left + rect.width  / 2;
                        const cy   = rect.top  + rect.height / 2;
                        const topEl = document.elementFromPoint(cx, cy);
                        const isOnTop = topEl === el || el.contains(topEl);
                        if (isOnTop) {
                            results.push({ text, tag: el.tagName, id: el.id || '', class: el.className || '', x: Math.round(rect.left), y: Math.round(rect.top) });
                        }
                    }
                });

                document.querySelectorAll('.img-action-text').forEach(el => {
                    const text = el.textContent.trim();
                    if (!text) return;
                    const s    = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    if (s.display !== 'none' && rect.width > 0) {
                        results.push({ text, tag: el.tagName, id: el.id || '', class: el.className || '', x: Math.round(rect.left), y: Math.round(rect.top) });
                    }
                });

                return results;
            }
        """)

        seen = set()
        unique_texts = []
        for t in visible_texts:
            key = t["text"]
            if key not in seen:
                seen.add(key)
                unique_texts.append(t)

        with open("task3_output/visible_texts.json", "w", encoding="utf-8") as f:
            json.dump(unique_texts, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(unique_texts)} visible text nodes to task3_output/visible_texts.json")
        print("-" * 60)
        for t in unique_texts:
            print(f"  [{t['tag']}] {t['text']}")
        print("-" * 60)

        print("\nDone.")
        print(f"  Total images scraped   : {len(all_images_out)}")
        print(f"  Visible images scraped : {len(visible_imgs)}")
        print(f"  Visible text nodes     : {len(unique_texts)}")

        page.wait_for_timeout(4000)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        context.close()
        browser.close()


with sync_playwright() as p:
    run(p)