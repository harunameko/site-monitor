# -*- coding: utf-8 -*-
"""
サイト更新監視スクリプト
- JBAリセールページ: 出品チケットの件数と商品リンクを抽出して比較
- ソフトバンクページ: 本文テキストのハッシュを比較
変更があれば ntfy.sh 経由でスマホにプッシュ通知
"""

import hashlib
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

STATE_FILE = "state.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.8",
}

SITES = [
    {
        "id": "jba1",
        "name": "JBAリセール(1)",
        "url": "https://resale.jba-ticket.jp/collections/resale/event_id:252a938a-c9be-4e67-9c70-49aad739fc1d",
        "type": "jba",
    },
    {
        "id": "jba2",
        "name": "JBAリセール(2)",
        "url": "https://resale.jba-ticket.jp/collections/resale/event_id:42684d5a-6709-4953-b31a-99b2bd0e3197",
        "type": "jba",
    },
    {
        "id": "jba3",
        "name": "JBAリセール(3)",
        "url": "https://resale.jba-ticket.jp/collections/resale/event_id:0647c25d-cb81-4cf1-8914-3a6b3393987c",
        "type": "jba",
    },
    {
        "id": "softbank_ipad",
        "name": "ソフトバンク iPad",
        "url": "https://www.softbank.jp/online-shop/special/products/lineup/ipad/?agncyId=sbm",
        "type": "text",
    },
]


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_jba(html: str) -> dict:
    """JBAリセール(Shopify)ページから出品件数と商品リンクを抽出"""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    m = re.search(r"(\d+)\s*件", text)
    count = int(m.group(1)) if m else -1

    products = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/products/" in href:
            products.add(href.split("?")[0])

    fingerprint = json.dumps(
        {"count": count, "products": sorted(products)},
        ensure_ascii=False, sort_keys=True,
    )
    return {
        "hash": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        "summary": f"出品 {count} 件" if count >= 0 else f"商品リンク {len(products)} 件",
        "count": count,
    }


def extract_text(html: str) -> dict:
    """一般ページ: 本文テキストを正規化してハッシュ化"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    body = soup.find("main") or soup.body or soup
    text = body.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return {
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "summary": "ページ内容",
        "count": None,
    }


def notify(title: str, message: str, url: str) -> None:
    if not NTFY_TOPIC:
        print("NTFY_TOPIC 未設定のため通知をスキップ")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Click": url,
                "Priority": "urgent",
                "Tags": "loudspeaker",
            },
            timeout=15,
        )
        print(f"通知送信: {title}")
    except Exception as e:
        print(f"通知送信失敗: {e}")


def main() -> int:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        first_run = False
    else:
        state = {}
        first_run = True

    changed_any = False

    for site in SITES:
        sid, name, url = site["id"], site["name"], site["url"]
        try:
            html = fetch(url)
        except Exception as e:
            print(f"[{name}] 取得失敗: {e}")
            continue

        result = extract_jba(html) if site["type"] == "jba" else extract_text(html)
        prev = state.get(sid)

        if prev is None:
            print(f"[{name}] 初回記録 ({result['summary']})")
        elif prev["hash"] != result["hash"]:
            print(f"[{name}] 変更検知! {prev.get('summary')} → {result['summary']}")
            if site["type"] == "jba":
                old_c = prev.get("count", -1)
                new_c = result["count"]
                if new_c is not None and new_c > (old_c or 0):
                    msg = f"出品が増えました: {old_c}件 → {new_c}件"
                else:
                    msg = f"{prev.get('summary')} → {result['summary']}"
            else:
                msg = "ページ内容が更新されました"
            notify(f"【{name}】更新あり", msg, url)
        else:
            print(f"[{name}] 変更なし ({result['summary']})")

        if prev is None or prev["hash"] != result["hash"]:
            changed_any = True

        state[sid] = result

    if changed_any:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("state.json を更新しました")

    if first_run:
        notify("監視を開始しました", "4サイトの監視をスタートしました。この通知が届けば設定成功です。",
               "https://github.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
