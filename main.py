import os
import re
import yt_dlp
import time
import asyncio
import functools
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified

# ===== Configuration =====
# Ensure these are set in your environment variables
API_ID = int(os.getenv("API_ID", "")) 
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

app = Client("ytbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global dictionary to manage cancellation states
# Format: {chat_id: boolean}
download_active = {}

# =============== Helpers ==================

def extract_video_id(url: str):
    """Extracts the 11-character Video ID to keep callback data short."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

def get_readable_time(seconds):
    return time.strftime("%M:%S", time.gmtime(seconds))

def get_progress_hook(chat_id, message: Message, start_time):
    """Creates a progress hook for yt_dlp."""
    def hook(d):
        if d['status'] == 'downloading':
            if not download_active.get(chat_id, True):
                raise Exception("CANCELLED")
            
            # Update progress every 5 seconds to avoid FloodWait
            now = time.time()
            if (now - start_time) > 5 and int(now) % 3 == 0:
                percent = d.get('_percent_str', '0%')
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                
                try:
                    # We use app.loop.create_task to run async func from sync hook
                    app.loop.create_task(
                        message.edit(
                            f"📥 **Downloading...**\n"
                            f"📊 Progress: {percent}\n"
                            f"⚡ Speed: {speed}\n"
                            f"⏳ ETA: {eta}"
                        )
                    )
                except Exception:
                    pass
    return hook

async def run_sync_in_thread(func, *args, **kwargs):
    """Runs a synchronous function in a separate thread to avoid blocking."""
    return await asyncio.get_event_loop().run_in_executor(
        None, functools.partial(func, *args, **kwargs)
    )

def download_video_sync(video_id, height, chat_id, message, start_time):
    """The synchronous yt_dlp logic."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Format selection: Best video under specific height + Best Audio, merged to mp4
    fmt_string = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"

    ydl_opts = {
        "format": fmt_string,
        "outtmpl": f"{DOWNLOAD_PATH}%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "progress_hooks": [get_progress_hook(chat_id, message, start_time)],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # yt_dlp might change extension on merge, ensure we get the actual file
        if not os.path.exists(filename):
            filename = filename.rsplit(".", 1)[0] + ".mp4"
            
    return info, filename

# =============== Bot Commands ===============

@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "👋 **Hi! Send me a YouTube link.**\n\n"
        "🎥 I will ask for quality.\n"
        "⚡ Downloads are fast & support audio merging."
    )

@app.on_message(filters.text & ~filters.command("start"))
async def process(_, message: Message):
    url = message.text.strip()
    vid_id = extract_video_id(url)
    
    if not vid_id:
        return await message.reply("❌ **Invalid YouTube Link**")

    # Limit callback data length (Telegram limit is 64 bytes)
    # Data format: "quality|video_id"
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("360p", callback_data=f"360|{vid_id}"),
            InlineKeyboardButton("480p", callback_data=f"480|{vid_id}"),
            InlineKeyboardButton("720p", callback_data=f"720|{vid_id}")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{vid_id}")]
    ])

    await message.reply(
        f"🎞 **Found Video:** `...{vid_id}`\nSelect quality:", 
        reply_markup=buttons
    )

@app.on_callback_query()
async def callback_query(client, cb: CallbackQuery):
    chat_id = cb.message.chat.id
    data = cb.data.split("|")
    action = data[0]
    vid_id = data[1]

    if action == "cancel":
        download_active[chat_id] = False
        await cb.answer("Canceled ❌")
        await cb.message.edit("🚫 Download canceled by user.")
        return

    # Start Download
    download_active[chat_id] = True
    height = action  # e.g., "720"
    
    status_msg = await cb.message.edit(f"⏳ **Initializing download for {height}p...**")
    start_time = time.time()

    filename = None
    try:
        # Run blocking yt_dlp in a thread
        info, filename = await run_sync_in_thread(
            download_video_sync, 
            vid_id, 
            height, 
            chat_id, 
            status_msg, 
            start_time
        )

        # Upload
        await status_msg.edit("📤 **Uploading to Telegram...**")
        
        # Pyrogram's native progress for upload
        async def upload_progress(current, total):
            now = time.time()
            if (now - start_time) > 5 and int(now) % 3 == 0:
                try:
                    await status_msg.edit(
                        f"📤 **Uploading...**\n"
                        f"📊 {current * 100 / total:.1f}%"
                    )
                except:
                    pass

        await cb.message.reply_video(
            video=filename,
            caption=f"🎥 **{info.get('title', 'Video')}**\nResolution: {height}p",
            progress=upload_progress
        )
        
        await status_msg.delete()

    except Exception as e:
        err_text = str(e)
        if "CANCELLED" in err_text:
            await status_msg.edit("🚫 Task Canceled.")
        else:
            await status_msg.edit(f"⚠️ **Error:** {err_text}")
            print(f"Error: {e}")

    finally:
        # Cleanup file
        if filename and os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    print("BOT STARTED")
    app.run()
        
