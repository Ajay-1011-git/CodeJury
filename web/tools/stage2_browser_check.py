#!/usr/bin/env python3
"""HTTP-level checks of the served Stage 2 page (standard library only).

  python3 web/tools/stage2_browser_check.py --base-url http://127.0.0.1:8080

This does NOT drive a browser: no browser-automation package is part of the project, so DOM
behaviour was verified by hand in a real browser and recorded in web/docs/stage2/ui.md. What this
script verifies is that the page, its module graph and its safety properties are served intact.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

BANNED = [r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function"]


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            return res.status, res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""
    except OSError as err:
        return 0, str(err)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    checks = {}
    status, html = get(f"{base}/stage2.html")
    checks["page_served"] = status == 200
    checks["fixture_banner_element"] = 'id="fixture-banner"' in html
    checks["no_inline_script"] = not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html)
    modules = {"src/s2/app.mjs"}
    queue = ["src/s2/app.mjs"]
    sources = {}
    while queue:
        path = queue.pop()
        status, text = get(f"{base}/{path}")
        sources[path] = (status, text)
        for rel in re.findall(r"from '\./([\w.]+)'", text):
            nxt = f"src/s2/{rel}"
            if nxt not in modules:
                modules.add(nxt)
                queue.append(nxt)
    checks["module_graph_served"] = all(s == 200 for s, _ in sources.values())
    checks["modules"] = sorted(modules)
    checks["no_html_injection_paths"] = not any(re.search(p, t) for _, t in sources.values() for p in BANNED)
    status, body = get(f"{base}/styles.css")
    checks["stage1_assets_still_served"] = status == 200
    status, body = get(f"{base}/index.html")
    checks["stage1_page_preserved"] = status == 200 and "stage1.v1" in body
    checks["dom_behaviour"] = "manual: see web/docs/stage2/ui.md (not automated here)"
    ok = all(v for k, v in checks.items() if isinstance(v, bool))
    print(json.dumps({"ok": ok, **checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
