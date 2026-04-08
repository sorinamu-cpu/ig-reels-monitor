import os
import time
import requests
from datetime import datetime, timedelta, timezone

ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
IG_USER_ID = os.environ["META_IG_USER_ID"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

COMMENT_THRESHOLD = 300
DAYS_WINDOW = 3
SLEEP_SEC = 18
GRAPH_VERSION = "v21.0"

def fetch_business_discovery(username):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}"
    fields = (
        f"business_discovery.username({username})"
        "{id,username,media.limit(10){"
        "id,media_product_type,comments_count,like_count,"
        "permalink,timestamp,caption}}"
    )
    params = {"fields": fields, "access_token": ACCESS_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"[WARN] {username} → HTTP {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"[ERROR] {username} → {e}")
        return None

def filter_hot_reels(data):
    if not data or "business_discovery" not in data:
        return []
    bd = data["business_discovery"]
    username = bd.get("username", "unknown")
    media_list = bd.get("media", {}).get("data", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_WINDOW)
    hits = []
    for m in media_list:
        if m.get("media_product_type") != "REELS":
            continue
        ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
        if ts < cutoff:
            continue
        if m.get("comments_count", 0) < COMMENT_THRESHOLD:
            continue
        hits.append({
            "username": username,
            "permalink": m["permalink"],
            "comments": m["comments_count"],
            "likes": m.get("like_count", 0),
            "timestamp": ts.isoformat(),
        })
    return hits

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TG_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }, timeout=30)

def main():
    with open("usernames.txt") as f:
        usernames = [line.strip() for line in f if line.strip()]

    print(f"Total targets: {len(usernames)}")
    all_hits = []
    for i, u in enumerate(usernames, 1):
        print(f"[{i}/{len(usernames)}] {u}")
        data = fetch_business_discovery(u)
        hits = filter_hot_reels(data)
        all_hits.extend(hits)
        time.sleep(SLEEP_SEC)

    if not all_hits:
        send_telegram(f"📊 오늘 조건({COMMENT_THRESHOLD}+ 댓글, 최근 {DAYS_WINDOW}일) 충족 릴스 없음")
        return

    all_hits.sort(key=lambda x: x["comments"], reverse=True)

    header = f"🔥 떡상 릴스 {len(all_hits)}건 (댓글 {COMMENT_THRESHOLD}+, 최근 {DAYS_WINDOW}일)\n\n"
    lines = []
    for h in all_hits:
        lines.append(
            f"@{h['username']} | 💬{h['comments']} ❤️{h['likes']}\n{h['permalink']}\n"
        )
    msg = header
    for line in lines:
        if len(msg) + len(line) > 3800:
            send_telegram(msg)
            msg = ""
        msg += line + "\n"
    if msg:
        send_telegram(msg)

if __name__ == "__main__":
    main()
