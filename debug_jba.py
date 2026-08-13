# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright

URL = ("https://jba-ticket.jp/s/jbat/page/ticket_detail"
       "?ima=3849&game=men_20260815816&code=jba20260815_GS2&ct=jba202608150816_02#/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(user_agent=UA, viewport={"width": 412, "height": 915})
    pg.goto(URL, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(8000)
    body = pg.inner_text("body")
    b.close()

lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
print("=== 全" + str(len(lines)) + "行 ===")
for i, ln in enumerate(lines):
    print(str(i) + ": " + ln)
