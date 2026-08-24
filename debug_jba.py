# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright

URL = ("https://cloak.pia.jp/resale/item/list"
       "?eventCd=2625378&perfCd=001&utm_source=mail20260822&utm_medium=resale_alt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(user_agent=UA, viewport={"width": 412, "height": 915})
    pg.goto(URL, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(8000)

    body = pg.inner_text("body")
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    print("=== テキスト " + str(len(lines)) + "行 ===")
    for i, ln in enumerate(lines):
        print(str(i) + ": " + ln)

    print()
    print("=== body先頭HTML ===")
    print(pg.inner_html("body")[:3000])

    b.close()
