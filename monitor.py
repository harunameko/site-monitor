# -*- coding: utf-8 -*-
import json
import os
import re
import sys

import requests

STATE_FILE = "state.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SB_URL = "https://www.softbank.jp/online-shop/products/stock/?device=ipad"

JBA_SITES = [
    {
        "id": "jba1",
        "name": "JBAリセール(1)",
        "url": "https://resale.jba-ticket.jp/collections/resale/event_id:252a938a-c9be-4e67-9c70-49aad739fc1d",
    },
    {
        "id": "jba2",
        "name": "JBAリセール(2)",
        "url": "https://resale.jba-ticket.jp/collections/resale/event_id:42684d5a-6709-4953-b31a-99b2bd0e3197",
    },
    {
        "id": "jba3",
        "name": "JBAリセール(3)",
        "url": "https://resale.jba-ticket.jp/collections/resale/event_id:0647c25d-cb81-4cf1-8914-3a6b3393987c",
    },
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
    page.wait_for_timeout(4000)
    return page.inner_text("body")


def check_jba(page, site, state):
    try:
        body = get_text(page, site["url"])
    except Exception as e:
        print("[" + site["name"] + "] 取得失敗: " + str(e))
        return

    m = re.search(r"(\d+)\s*件", body)
    if not m:
        print("[" + site["name"] + "] 件数を読み取れませんでした（スキップ）")
        return

    total = int(m.group(1))
    sold = body.count("リセール成立")
    available = total - sold
    if available < 0:
        available = 0

    print("[" + site["name"] + "] 全" + str(total) + "件 / 成立済" + str(sold)
          + "件 → 購入可能 " + str(available) + "件")

    prev = state.get(site["id"])
    if prev is None:
        print("[" + site["name"] + "] 初回記録")
    else:
        old_c = prev.get("count", 0) or 0
        if available > old_c:
            msg = "購入可能なチケットが出ました: " + str(old_c) + "件 → " + str(available) + "件"
            print("[" + site["name"] + "] 変更検知! " + msg)
            notify("【" + site["name"] + "】チケットあり", msg, site["url"])
        elif available < old_c:
            print("[" + site["name"] + "] 減少（通知なし）")

    state[site["id"]] = {"hash": str(available),
                         "summary": "購入可能 " + str(available) + " 件",
                         "count": available}


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
        first_run = False
    else:
        state = {}
        first_run = True

    before = json.dumps(state, ensure_ascii=False, sort_keys=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(user_agent=UA, viewport={"width": 412, "height": 915})

        for site in JBA_SITES:
            check_jba(page, site, state)

        check_softbank(page, state)
        browser.close()

    after = json.dumps(state, ensure_ascii=False, sort_keys=True)
    if before != after:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("state.json を更新しました")

    if first_run:
        notify("監視を開始しました",
               "JBAリセール3件＋ソフトバンクiPad Air(M3)の監視を開始しました。",
               "https://github.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
