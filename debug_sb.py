# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright

URL = "https://www.softbank.jp/online-shop/products/stock/?device=ipad"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(user_agent=UA, viewport={"width": 412, "height": 915})
    pg.goto(URL, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(5000)
    body = pg.inner_text("body")
    b.close()

lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
print("=== iPad Air を含む行と直後10行 ===")
for i, ln in enumerate(lines):
    if "iPad Air" in ln:
        print(f"--- {i}: {ln}")
        for j in range(i + 1, min(i + 11, len(lines))):
            print(f"    {j}: {lines[j]}")
        print()
