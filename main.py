import instaloader
import os
import time
import requests
import base64
import tempfile
import pathlib
from datetime import datetime, timezone, timedelta

COMMENT_THRESHOLD = 300
DAYS_WINDOW = 3
SLEEP_SEC = 20

IG_USERNAME = os.environ["IG_USERNAME"]
IG_SESSION = os.environ["IG_SESSION"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def days_ago(dt):
    diff = (datetime.now(timezone.utc) - dt).days
    if diff == 0:
        return "오늘"
    return f"{diff}일 전"

def main():
    L = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False
    )

    session_data = base64.b64decode(IG_SESSION)
    session_path = pathlib.Path(tempfile.gettempdir()) / f"session-{IG_USERNAME}"
    session_path.write_bytes(session_data)
    L.load_session_from_file(IG_USERNAME, str(session_path))
    print("세션 로드 완료")

    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_WINDOW)

    with open("usernames.txt") as f:
        usernames = [u.strip() for u in f if u.strip()]

    print(f"총 {len(usernames)}개 계정 모니터링 시작")

    for i, username in enumerate(usernames, 1):
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            for post in profile.get_posts():
                if post.date_utc < cutoff:
                    break
                if post.is_video and post.comments >= COMMENT_THRESHOLD:
                    upload_date = post.date_utc.strftime("%Y-%m-%d")
                    ago = days_ago(post.date_utc)
                    duration = int(post.video_duration) if post.video_duration else 0
                    views = f"{post.video_view_count:,}" if post.video_view_count else "?"
                    caption_first = post.caption.split('\n')[0][:50] if post.caption else ""
                    shortcode = post.shortcode

                    msg = (
                        f"🔥 릴스 발견!\n"
                        f"계정명: @{username}\n"
                        f"업로드: {upload_date} ({ago})\n"
                        f"댓글: {post.comments:,}개 | 조회수: {views}회\n"
                        f"링크: https://www.instagram.com/reel/{shortcode}/\n"
                        f"영상길이: {duration}초\n"
                        f"캡션: {caption_first}"
                    )
                    send_telegram(msg)
                    print(f"[알림 전송] @{username} - 댓글 {post.comments}개")

        except Exception as e:
            print(f"[오류] {username}: {e}")

        time.sleep(SLEEP_SEC)
        if i % 50 == 0:
            print(f"진행: {i}/{len(usernames)}")

if __name__ == "__main__":
    main()
