import os
import re
import yt_dlp
from pyrogram import Client, filters

# ⬇ env se values uthayenge (Render me env vars set karoge)
API_ID = int(os.getenv("API_ID", "27881923"))
API_HASH = os.getenv("79abda5e46a51fc0dce1313f2548ce19")
BOT_TOKEN = os.getenv("7834877953:AAFxCNHmyuoCT2y6IMm0zsxuGxQo8vsY0QM")

DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

app = Client(
    "yt360_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def convert_to_watch(url: str) -> str:
    match = re.search(r"(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if match:
        vid = match.group(1)
        return f"https://www.youtube.com/watch?v={vid}"
    return url

def download_360p(url: str):
    ydl_opts = {
        "format": "18",  # 360p (video+audio)
        "outtmpl": DOWNLOAD_PATH + "%(title)s.%(ext)s",
        "quiet": True,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return info, filename

@app.on_message(filters.text & filters.private)
def process(client, message):
    raw_url = message.text.strip()
    url = convert_to_watch(raw_url)

    if "youtu" not in url:
        return message.reply("❌ Sirf YouTube link bhejo (watch/embed/youtu.be).")

    status = message.reply("📥 360p Downloading...")

    try:
        info, filename = download_360p(url)
        title = info.get("title", "Video")
        thumb = info.get("thumbnail")

        status.edit("📤 Uploading Telegram...")
        client.send_video(
            message.chat.id,
            filename,
            caption=title,
            thumb=thumb
        )

        os.remove(filename)
        status.delete()

    except Exception as e:
        status.edit(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Starting bot…")
    app.run()
