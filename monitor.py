# -*- coding: utf-8 -*-
import json
import os
import sys

import requests

STATE_FILE = "state.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SB_URL = "https://www.softbank.jp/online-shop/products/stock/?device=ipad"

PIA_URL = ("https://cloak.pia.jp/resale/item/list"
           "?eventCd=2625378&perfCd=001")

URL_0831 = ("https://jba-ticket.jp/s/jbat/page/ticket_detail"
            "?ima=3255&game=men_20260827831&code=jba20260831_GS2"
            "&ct=jba20260801_02#/")

OFFICIAL_DAYS = [
    {"id": "official_0831", "name": "公式 8/31", "url": URL_0831, "label": None},
]


def notify(title, message, url):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC 未設定のため通知をスキップ")
        return
    try:
        requests.post(
            "https://ntfy.sh/" + NTFY_TOPIC,
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Click": url,
                "Priority": "urgent",
                "Tags": "loudspeaker",
            },
            timeout=15,
        )
        print("通知送信: " + title)
    except Exception as e:
        print("通知送信失敗: " + str(e))


def get_text(page, url):
    page.goto(url, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(5000)
    return page.inner_text("body")


def check_pia(page, state):
    try:
        body = get_text(page, PIA_URL)
    except Exception as e:
        print("[ぴあリセール] 取得失敗: " + str(e))
        return

    if "リセールチケット一覧" not in body:
        print("[ぴあリセール] ページを読み取れませんでした（スキップ）")
        return

    empty = "出品されたリセールチケットはありません" in body
    status = "出品なし" if empty else "出品あり"

    detail = ""
    if not empty:
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        try:
            s = lines.index("リセールチケット一覧") + 1
        except ValueError:
            s = 0
        picked = []
        for ln in lines[s:]:
            if "ページの上部へ" in ln or "操作ガイド" in ln:
                break
            picked.append(ln)
        detail = " / ".join(picked)[:200]

    print("[ぴあリセール] " + status + (" : " + detail if detail else ""))

    prev = state.get("pia_resale")
    if prev is None:
        print("[ぴあリセール] 初回記録 (" + status + ")")
    elif prev["hash"] != status:
        print("[ぴあリセール] 変更検知! " + prev["hash"] + " → " + status)
        if status == "出品あり":
            msg = "リセールチケットが出品されました！"
            if detail:
                msg = msg + "\n" + detail
            notify("【ぴあリセール】出品あり", msg, PIA_URL)
        else:
            print("[ぴあリセール] 出品が無くなりました（通知なし）")
    else:
        print("[ぴあリセール] 変更なし (" + status + ")")

    state["pia_resale"] = {"hash": status, "summary": status, "count": None}


def check_official(browser, day, state):
    page = browser.new_page(user_agent=UA, viewport={"width": 412, "height": 915})
    total = 0
    available = []
    try:
        page.goto(day["url"], wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(5000)

        if day["label"]:
            page.get_by_text(day["label"]).first.click()
            page.wait_for_timeout(6000)

        items = page.query_selector_all("li.p-ticket_in__list-item")
        total = len(items)
        for it in items:
            disabled = it.get_attribute("data-disabled")
            title_el = it.query_selector(".p-in-title")
            name = title_el.inner_text().strip() if title_el else "?"
            if disabled != "true":
                available.append(name)
    except Exception as e:
        print("[" + day["name"] + "] 取得失敗: " + str(e))
        page.close()
        return
    page.close()

    if total == 0:
        print("[" + day["name"] + "] 券種を読み取れませんでした（スキップ）")
        return

    cnt = len(available)
    print("[" + day["name"] + "] 全" + str(total) + "券種 / 購入可能 " + str(cnt) + "件 "
          + (str(available) if cnt else ""))

    prev = state.get(day["id"])
    if prev is None:
        print("[" + day["name"] + "] 初回記録")
    else:
        old_c = prev.get("count", 0) or 0
        if cnt > old_c:
            msg = "公式チケットに空きが出ました: " + "、".join(available)
            print("[" + day["name"] + "] 変更検知! " + msg)
            notify("【" + day["name"] + "】公式チケット空きあり", msg, day["url"])
        elif cnt < old_c:
            print("[" + day["name"] + "] 減少（通知なし）")

    state[day["id"]] = {"hash": str(cnt), "summary": str(cnt) + "券種", "count": cnt}


def check_softbank(page, state):
    try:
        body = get_text(page, SB_URL)
    except Exception as e:
        print("[ソフトバンク] 取得失敗: " + str(e))
        return

    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]

    def norm(s):
        return s.replace(" ", "").replace("　", "")

    idx = None
    for i in range(len(lines) - 1):
        n = norm(lines[i])
        if n.startswith("13インチ") or n.startswith("12.9インチ"):
            continue
        if "11インチiPadAir" in n and "M3" in n:
            nxt = norm(lines[i + 1])
            if "在庫なし" in nxt or "予約" in nxt or "購入する" in nxt:
                idx = i
                break

    if idx is None:
        print("[ソフトバンク] 対象機種が見つかりません")
        return

    nxt = norm(lines[idx + 1])
    status = "在庫なし" if "在庫なし" in nxt else "在庫あり"
    print("[ソフトバンク] 判定元: " + lines[idx] + " / " + lines[idx + 1])

    prev = state.get("softbank_ipad_air_m3")
    if prev is None:
        print("[ソフトバンク] 初回記録 (" + status + ")")
    elif prev["hash"] != status:
        print("[ソフトバンク] 変更検知! " + prev["hash"] + " → " + status)
        if status == "在庫あり":
            notify("【在庫あり】11インチiPad Air (M3)",
                   "在庫なし → 予約・購入できる状態になりました！", SB_URL)
        else:
            notify("【在庫なし】11インチiPad Air (M3)",
                   "在庫あり → 在庫なしに変わりました", SB_URL)
    else:
        print("[ソフトバンク] 変更なし (" + status + ")")

    state["softbank_ipad_air_m3"] = {"hash": status, "summary": status, "count": None}


def main():
    from playwright.sync_api import sync_playwright

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {}

    for old in ["jba1", "jba2", "jba3", "official_0815", "official_0816"]:
        state.pop(old, None)

    before = json.dumps(state, ensure_ascii=False, sort_keys=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])

        for day in OFFICIAL_DAYS:
            check_official(browser, day, state)

        page = browser.new_page(user_agent=UA, viewport={"width": 412, "height": 915})
        check_pia(page, state)
        check_softbank(page, state)
        page.close()

        browser.close()

    after = json.dumps(state, ensure_ascii=False, sort_keys=True)
    if before != after:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("state.json を更新しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
