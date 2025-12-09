import os
import re
import yt_dlp
import time
from pyrogram import Client, filters
from pyrogram.types import Message

# ======= Render Secure Cookies Load =======
COOKIES_ENV = os.getenv("YOUTUBE_COOKIES")
if COOKIES_ENV:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(COOKIES_ENV)

# ======= Telegram API =======
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


def convert_to_watch(url: str):
    match = re.search(r"(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return f"https://www.youtube.com/watch?v={match.group(1)}" if match else url


async def progress_bar(current, total, message: Message, start, status):
    now = time.time()
    speed = current / (now - start)
    eta = (total - current) / speed if speed else 0
    percent = current * 100 / total

    try:
        await message.edit(
            f"**{status}…**\n"
            f"📊 **{percent:.1f}%**\n"
            f"⚡ Speed: `{speed / 1024 / 1024:.2f} MB/s`\n"
            f"⏳ ETA: `{eta:.1f}s`"
        )
    except:
        pass


async def download(video_url, status):
    start = time.time()

    ydl_opts = {
        "format": "18",  # 360p mp4
        "outtmpl": DOWNLOAD_PATH + "%(title)s.%(ext)s",
        "merge_output_format": "mp4",

        # 🛡️ Anti Robot Fix (Android Client)
        "extractor_args": {
            "youtube": {"player_client": ["android"]}
        },

        # Login cookies for certain videos
        "cookies": "cookies.txt",

        "quiet": True,
        "retries": 10,
        "fragment_retries": 10,
        "nocheckcertificate": True,

        "progress_hooks": [
            lambda d: app.loop.create_task(
                progress_bar(
                    d.get("downloaded_bytes", 0),
                    d.get("total_bytes", 1),
                    status,
                    start,
                    "📥 Downloading"
                )
            ) if d.get("status") == "downloading" else None
        ]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filename = ydl.prepare_filename(info)

    return info, filename


@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "👋 Namaste!\n\n"
        "🎥 YouTube link bhejo, main 360p me download karke bhej dunga.\n"
        "📡 Anti-Robot Enabled\n"
        "🔑 Agar video private/age-restricted ho to `cookies.txt` jaruri hai!"
    )


@app.on_message(filters.text & ~filters.command("start"))
async def process(_, message):
    url = convert_to_watch(message.text.strip())

    if "youtu" not in url:
        return await message.reply(
            "❌ Valid YouTube link bhejo!\nExample: https://youtu.be/xyz"
        )

    status = await message.reply("🔍 Checking URL…")

    try:
        info, filename = await download(url, status)

        await status.edit("📤 Uploading…")
        await message.reply_video(
            filename,
            caption=info.get("title", "Video"),
            progress=progress_bar,
            progress_args=(status, time.time(), "📡 Uploading")
        )

        os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit(f"❌ Error:\n`{str(e)}`")


if __name__ == "__main__":
    print("BOT STARTED ON RENDER…")
    app.run()
