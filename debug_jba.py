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
    pg.wait_for_timeout(6000)
    pg.get_by_text("2026年8月16日").first.click()
    pg.wait_for_timeout(8000)

    print("=== img要素 ===")
    for im in pg.query_selector_all("img"):
        src = im.get_attribute("src") or ""
        alt = im.get_attribute("alt") or ""
        cls = im.get_attribute("class") or ""
        print("src=" + src[-60:] + " | alt=" + alt + " | class=" + cls)

    print()
    print("=== 「コートサイド」を含むカードのHTML ===")
    el = pg.query_selector("text=コートサイド")
    if el:
        for _ in range(4):
            el = el.evaluate_handle("e => e.parentElement").as_element()
            if el is None:
                break
        if el:
            html = el.inner_html()
            print(html[:2500])

    b.close()
