import os
import re
import yt_dlp
import time
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

app = Client(
    "ytbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def convert_to_watch(url):
    match = re.search(r"(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url

async def progress_bar(current, total, message: Message, start, status):
    now = time.time()
    speed = current / (now - start)
    eta = (total - current) / speed if speed else 0
    percent = current * 100 / total

    msg = (
        f"**{status}…**\n"
        f"📊 **{percent:.1f}%**\n"
        f"⚡ Speed: `{speed/1024/1024:.2f} MB/s`\n"
        f"⏳ ETA: `{eta:.1f}s`"
    )
    try:
        await message.edit(msg)
    except:
        pass

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "👋 Namaste!\n\n"
        "📌 YouTube link bhejo (Watch / Embed / Short sab chalega)\n"
        "🎥 Main 360p video download karke Telegram me upload karunga.\n"
        "⚡ Speed + ETA bhi dikhega!\n"
    )

@app.on_message(filters.text & ~filters.command("start"))
async def process(client, message):
    url = message.text.strip()
    url = convert_to_watch(url)

    if "youtu" not in url:
        return await message.reply("❌ Valid YouTube link bhejo!")

    status = await message.reply("🔍 Checking video...")

    try:
        start_time = time.time()
        ydl_opts = {
            "format": "18",
            "outtmpl": DOWNLOAD_PATH + "%(title)s.%(ext)s",
            "quiet": True,
            "merge_output_format": "mp4",
            "progress_hooks": [
                lambda d: client.loop.create_task(
                    progress_bar(
                        d.get("downloaded_bytes", 0),
                        d.get("total_bytes", 1),
                        status,
                        start_time,
                        "📥 Downloading"
                    )
                ) if d["status"] == "downloading" else None
            ],
            "cookies": "cookies.txt"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        await status.edit("📤 Uploading…")

        await client.send_video(
            message.chat.id,
            filename,
            caption=info.get("title", "Video"),
            progress=progress_bar,
            progress_args=(status, time.time(), "📡 Uploading")
        )

        os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit(f"❌ Error: `{str(e)}`")


if __name__ == "__main__":
    print("BOT STARTING…")
    app.run()
