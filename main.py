import os
import re
import yt_dlp
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait

# ===== Telegram API =====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH"))
BOT_TOKEN = os.getenv("BOT_TOKEN"))

DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

app = Client(
    "ytbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# =============== Helpers ==================
download_active = {}

def convert_to_watch(url: str):
    live = re.search(r"youtube\.com/live/([A-Za-z0-9_-]{11})", url)
    if live:
        return f"https://www.youtube.com/watch?v={live.group(1)}"

    match = re.search(r"(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return f"https://www.youtube.com/watch?v={match.group(1)}" if match else url


async def progress_bar(current, total, message: Message, start, status):
    if not download_active.get(message.chat.id, True):
        return

    now = time.time()
    percent = current * 100 / total
    if int(percent) % 3 != 0:
        return

    speed = current / (now - start)
    eta = (total - current) / speed if speed else 0

    try:
        await message.edit(
            f"**{status}…**\n"
            f"📊 {percent:.1f}%\n"
            f"⚡ {speed/1024/1024:.2f} MB/s\n"
            f"⏳ {eta:.1f}s"
        )
    except:
        pass


async def download_custom(url, fmt, status, chat_id):
    start = time.time()

    ydl_opts = {
        "format": fmt,
        "outtmpl": DOWNLOAD_PATH + "%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "retries": 3,
        "fragment_retries": 3,
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

    if not download_active[chat_id]:
        raise Exception("Canceled")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except:
        raise Exception("⚠️ Public video required — login/cookie not allowed")

    return info, filename

# =============== Bot Commands ===============
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "👋 Hi! Send **public YouTube link** (even multiple links)\n"
        "🎥 Choose quality → I’ll send video here\n\n"
        "❌ Login-required videos not supported\n"
        "🔄 You can **Cancel** download anytime!"
    )


@app.on_message(filters.text & ~filters.command("start"))
async def process(_, message):
    urls = re.findall(r"(https?://\S+)", message.text)
    if not urls:
        return await message.reply("Please send valid video links")

    for url in urls:
        url = convert_to_watch(url)

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("360p", callback_data=f"18|{url}"),
                InlineKeyboardButton("480p", callback_data=f"135|{url}"),
                InlineKeyboardButton("720p", callback_data=f"22|{url}")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{url}")]
        ])

        await message.reply(f"🎞 Select quality:\n{url}", reply_markup=buttons)


@app.on_callback_query()
async def callback_query(client, cb):
    chat_id = cb.message.chat.id
    action, url = cb.data.split("|")

    if action == "cancel":
        download_active[chat_id] = False
        await cb.answer("Canceled ❌")
        return await cb.message.edit("🚫 Download canceled by user.")

    fmt = action
    download_active[chat_id] = True

    status = await cb.message.reply("⏳ Starting…")

    try:
        info, filename = await download_custom(url, fmt, status, chat_id)
        await status.edit("📤 Uploading…")

        while True:
            try:
                await cb.message.reply_video(filename, caption=info.get("title"))
                break
            except FloodWait as e:
                await asyncio.sleep(e.value)

        os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit(str(e))

    await cb.answer()


if __name__ == "__main__":
    print("BOT STARTED")
    app.run()
