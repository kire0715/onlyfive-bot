import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

# --- 設定 ---
URL = "https://only-five.jp/creators/4635"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

# クラウド上で常時稼働させるためのWebサーバー枠組み (Flask)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL が未設定です", flush=True)
        return
    payload = {"content": message}
    for attempt in range(3):
        try:
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            print(f"Discord送信結果: status={res.status_code}, body={res.text[:120]}", flush=True)
            if res.status_code in (200, 204):
                return
            if res.status_code == 429:
                retry_after = float(res.headers.get("Retry-After", 15))
                wait_sec = min(max(retry_after, 15.0), 60.0)
                print(f"429 レート制限のため {wait_sec} 秒待機します", flush=True)
                time.sleep(wait_sec)
                continue
            return
        except Exception as e:
            print(f"Discord送信エラー: {e}", flush=True)
            return

def send_ntfy_notification(message):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC が未設定です", flush=True)
        return
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {"Title": "ONLY FIVE 更新通知"}
    try:
        res = requests.post(
            url,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        print(f"ntfy送信結果: status={res.status_code}, body={res.text[:120]}", flush=True)
    except Exception as e:
        print(f"ntfy送信エラー: {e}", flush=True)

def get_stats():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        total_posts = None
        consecutive_days = None

        # class="title" を持つ h3 タグを全検索
        for h3 in soup.find_all("h3", class_="title"):
            text = h3.text.strip()
            if text == "総投稿数":
                # 直後にある h1.count を取得
                next_h1 = h3.find_next("h1", class_="count")
                if next_h1:
                    total_posts = next_h1.text.strip()
            elif text == "連続投稿日数":
                # 直後にある h1.count を取得
                next_h1 = h3.find_next("h1", class_="count")
                if next_h1:
                    consecutive_days = next_h1.text.strip()

        if total_posts and consecutive_days:
            return total_posts, consecutive_days

    except Exception as e:
        print(f"データ取得エラー: {e}")
        
    return None, None
def monitor():
    last_total, last_consecutive = get_stats()
    print(f"監視開始 - 総投稿数: {last_total}, 連続投稿日数: {last_consecutive}", flush=True)
    while True:
        time.sleep(180)  # 3分ごと
        try:
            current_total, current_consecutive = get_stats()
            if current_total is None:
                print("取得スキップ: current_total is None", flush=True)
                continue
            print(f"監視チェック - total={current_total}, consecutive={current_consecutive}", flush=True)
            if current_total != last_total or current_consecutive != last_consecutive:
                msg = (
                    f"【ONLY FIVE 更新通知】\n"
                    f"石浜もも さんの投稿データに変化がありました！\n\n"
                    f"■ 総投稿数: {last_total} → {current_total}\n"
                    f"■ 連続投稿日数: {last_consecutive} → {current_consecutive}\n"
                    f"URL: {URL}"
                )
                print(msg, flush=True)
                send_discord_notification(msg)
                last_total = current_total
                last_consecutive = current_consecutive
        except Exception as e:
            print(f"エラー発生: {e}", flush=True)

# バックグラウンドで監視処理を起動
threading.Thread(target=monitor, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)




