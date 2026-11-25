import os
import re
import threading
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

URL = "https://only-five.jp/creators/4635"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")


def send_ntfy_notification(message: str) -> None:
    if not NTFY_TOPIC:
        print("NTFY_TOPIC が未設定です", flush=True)
        return

    endpoint = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {
        "Title": "ONLY FIVE Alert",
        "Click": URL,
    }
    try:
        res = requests.post(
            endpoint,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        print(f"ntfy送信結果: status={res.status_code}, body={res.text[:120]}", flush=True)
    except Exception as e:
        print(f"ntfy送信エラー: {e}", flush=True)


def extract_number(text: str):
    if not text:
        return None
    m = re.search(r"(\d[\d,]*)", text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def get_stats():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        res = requests.get(URL, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        total_posts = None
        consecutive_days = None

        for box in soup.select(".rank-contents"):
            title_el = box.select_one(".title")
            count_el = box.select_one(".count")
            if not title_el or not count_el:
                continue

            title_text = title_el.get_text(strip=True)
            num = extract_number(count_el.get_text(strip=True))

            if "総投稿数" in title_text and num is not None:
                total_posts = num
            elif "連続投稿日数" in title_text and num is not None:
                consecutive_days = num

        return total_posts, consecutive_days
    except Exception as e:
        print(f"データ取得エラー: {e}", flush=True)
        return None, None


def monitor():
    last_total, last_consecutive = get_stats()
    print(f"監視開始 - 総投稿数: {last_total}, 連続投稿日数: {last_consecutive}", flush=True)

    while True:
        time.sleep(180)  # 3分ごと
        try:
            current_total, current_consecutive = get_stats()
            if current_total is None or current_consecutive is None:
                print(
                    f"取得スキップ: current_total={current_total}, current_consecutive={current_consecutive}",
                    flush=True,
                )
                continue

            print(f"監視チェック - total={current_total}, consecutive={current_consecutive}", flush=True)

            if current_total != last_total or current_consecutive != last_consecutive:
                msg = (
                    f"石浜もも さんの投稿データに変化がありました！\n\n"
                    f"■ 総投稿数: {last_total} → {current_total}\n"
                    f"■ 連続投稿日数: {last_consecutive} → {current_consecutive}\n"
                    f"URL: {URL}"
                )
                print(msg, flush=True)
                send_ntfy_notification(msg)
                last_total = current_total
                last_consecutive = current_consecutive
        except Exception as e:
            print(f"エラー発生: {e}", flush=True)


@app.route("/", methods=["GET", "HEAD"])
def index():
    return "OK", 200


if not getattr(app, "_monitor_started", False):
    app._monitor_started = True
    threading.Thread(target=monitor, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
