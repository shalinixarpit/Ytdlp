import os
import re
import yt_dlp
from pyrogram import Client, filters

BOT_TOKEN = "7567559210:AAH8ZHbf_DCLr0dPe1gN8NvS-_EifLj7VIA"  # <-- Token yahan daalo
DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

app = Client("yt360_bot", bot_token=BOT_TOKEN)

def convert_to_watch(url):
    match = re.search(r"(?:embed/|v=|youtu.be/)([A-Za-z0-9_-]{11})", url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

def download_360p(url):
    ydl_opts = {
        "format": "18",           # 360p + audio
        "outtmpl": DOWNLOAD_PATH + "%(title)s.%(ext)s",
        "quiet": True,
        "merge_output_format": "mp4"
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
        return message.reply("❌ Sirf YouTube link bhejo!")

    status = message.reply("📥 360p Downloading...")

    try:
        info, filename = download_360p(url)
        title = info.get("title", "Video")
        thumbnail = info.get("thumbnail")

        status.edit("📤 Uploading Telegram...")
        client.send_video(message.chat.id, filename, caption=title, thumb=thumbnail)

        os.remove(filename)
        status.delete()

    except Exception as e:
        status.edit(f"❌ Error: {e}")

app.run()
