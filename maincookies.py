import os
import re
import time
import math
import asyncio
import functools
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified
import yt_dlp

# ===== Configuration =====
API_ID = int(os.getenv("API_ID", ""))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)
COOKIE_FILE = "cookies.txt"

app = Client("ytbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

download_active = {}
last_update_time = 0

# ===== Helper Functions =====

def clean_filename(name):
    """
    Filename mein se invalid characters (/:*?"<>|) hatata hai
    taaki 'No such file' ya 'float' error na aaye.
    """
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def format_time(seconds):
    if not seconds or seconds < 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)} {["B", "KB", "MB", "GB", "TB"][index]}'
    except IndexError:
        return "File too large"

async def progress_bar(current, total, status_msg, action_text, start_time, eta=None):
    global last_update_time
    now = time.time()
    
    if (now - last_update_time) < 4 and current != total:
        return
        
    last_update_time = now
    percentage = current * 100 / total
    
    if eta is not None:
        eta_str = format_time(eta)
        diff = now - start_time
        speed = current / diff if diff > 0 else 0
    else:
        diff = now - start_time
        speed = current / diff if diff > 0 else 0
        eta_seconds = (total - current) / speed if speed > 0 else 0
        eta_str = format_time(eta_seconds)

    speed_str = f"{get_readable_file_size(speed)}/s"
    
    bars = 10
    filled = math.floor(percentage / 10)
    progress_str = "▰" * filled + "▱" * (bars - filled)

    text = (
        f"{action_text}\n"
        f"{progress_str} | {round(percentage, 1)}%\n"
        f"💾 Size: {get_readable_file_size(current)} / {get_readable_file_size(total)}\n"
        f"🚀 Speed: {speed_str}\n"
        f"⏳ ETA: {eta_str}"
    )

    try:
        await status_msg.edit(text)
    except MessageNotModified:
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value)

# ===== Download Logic =====

def download_video_sync(url, custom_name, height, chat_id, status_msg, loop):
    """
    Ab ye 'custom_name' accept karega aur usi naam se save karega.
    """
    # Filename sanitize karein
    safe_name = clean_filename(custom_name) if custom_name else "%(title)s"
    
    if not download_active.get(chat_id, True):
        raise Exception("CANCELLED")

    def hook(d):
        if d['status'] == 'downloading':
            if not download_active.get(chat_id, True):
                raise Exception("CANCELLED")
            
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes')
            start_time = d.get('start_time', time.time())
            eta = d.get('eta')

            if total and downloaded:
                 asyncio.run_coroutine_threadsafe(
                    progress_bar(downloaded, total, status_msg, "📥 **Downloading...**", start_time, eta),
                    loop
                )

    # Output template mein aapka custom naam set kar diya
    # %(ext)s automatically mp4/mkv laga dega
    final_filename_tmpl = f"{DOWNLOAD_PATH}{safe_name}.%(ext)s"

    ydl_opts = {
        "outtmpl": final_filename_tmpl,
        "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
        "merge_output_format": "mp4",
        "writethumbnail": True,
        "quiet": True,
        "noprogress": True,
        "progress_hooks": [hook],
        "cookiefile": COOKIE_FILE if os.path.exists(COOKIE_FILE) else None
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # yt-dlp kabhi kabhi merge karke ext badal deta hai, check karein
        if not os.path.exists(filename):
            pre, ext = os.path.splitext(filename)
            filename = pre + ".mp4"
            
    return info, filename

# ===== Bot Handlers =====

@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "👋 **Hi! Send me a link.**\n\n"
        "**Supported Formats:**\n"
        "1. Direct Link: `https://youtube.com/...`\n"
        "2. Custom Name:\n"
        "`Name =>> My Video Title`\n"
        "`Url =>> https://youtube.com/...`"
    )

@app.on_message(filters.text & ~filters.command("start") & filters.private)
async def process(_, message: Message):
    text = message.text.strip()
    
    # Defaults
    custom_name = None
    url = None

    # Check for Custom Format: "Name =>> ... Url =>> ..."
    if "Name =>>" in text and "Url =>>" in text:
        try:
            # Regex se Name aur URL nikalna (Multiline support ke sath)
            name_match = re.search(r"Name =>>(.*?)(?:Url =>>|$|\n)", text, re.IGNORECASE | re.DOTALL)
            url_match = re.search(r"Url =>>(.*)", text, re.IGNORECASE | re.DOTALL)
            
            if name_match and url_match:
                custom_name = name_match.group(1).strip()
                url = url_match.group(1).strip()
        except Exception as e:
            return await message.reply(f"❌ Parsing Error: {e}")
    else:
        # Normal Link
        url = text

    # Validate URL
    if not url or "http" not in url:
        return await message.reply("❌ **Invalid Link found.**")

    # Extract ID for Callback Data (Shortness ke liye)
    vid_id_match = re.search(r"(?:v=|\/|youtu\.be\/|watch\?v=)([0-9A-Za-z_-]{11})", url)
    vid_id = vid_id_match.group(1) if vid_id_match else "unknown"

    # Store Custom Name in a temporary dictionary or encode in callback?
    # Callback data limit is small (64 bytes). 
    # Solution: URL/Name ko memory mein save karein ID ke sath.
    temp_id = f"{message.chat.id}_{int(time.time())}"
    download_active[temp_id] = {"url": url, "name": custom_name}

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("360p", callback_data=f"360|{temp_id}"),
            InlineKeyboardButton("480p", callback_data=f"480|{temp_id}"),
            InlineKeyboardButton("720p", callback_data=f"720|{temp_id}")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{temp_id}")]
    ])

    display_name = custom_name if custom_name else "YouTube Video"
    
    await message.reply(
        f"🎞 **Ready to Download:**\n📝 Name: `{display_name}`\n\nSelect quality:", 
        reply_markup=buttons
    )

@app.on_callback_query()
async def callback_query(client, cb: CallbackQuery):
    chat_id = cb.message.chat.id
    data = cb.data.split("|")
    action = data[0]
    temp_id = data[1]

    if action == "cancel":
        if temp_id in download_active:
            del download_active[temp_id]
        await cb.answer("Canceled ❌")
        await cb.message.edit("🚫 Download canceled.")
        return

    # Retrieve data
    task_data = download_active.get(temp_id)
    if not task_data:
        await cb.answer("Session expired. Send link again.")
        return

    url = task_data["url"]
    custom_name = task_data["name"]
    height = action
    
    # Mark as active for cancellation check
    # Note: We use chat_id for global cancellation check in hooks
    download_active[chat_id] = True 
    
    status_msg = await cb.message.edit(f"⏳ **Initializing download for {height}p...**")
    loop = asyncio.get_running_loop()

    filename = None
    thumbnail_path = None
    
    try:
        # 1. Download
        info, filename = await loop.run_in_executor(
            None, 
            functools.partial(download_video_sync, url, custom_name, height, chat_id, status_msg, loop)
        )

        # 2. Find Thumbnail
        base_name = os.path.splitext(filename)[0]
        for ext in [".jpg", ".webp", ".png"]:
            if os.path.exists(base_name + ext):
                thumbnail_path = base_name + ext
                break

        # 3. Upload
        if not download_active.get(chat_id, True):
            raise Exception("CANCELLED")
            
        await status_msg.edit("📤 **Uploading to Telegram...**")
        start_time_upload = time.time()
        
        # Caption Logic
        caption = f"🎥 **{custom_name if custom_name else info.get('title')}**\nResolution: {height}p"
        
        await cb.message.reply_video(
            video=filename,
            caption=caption,
            thumb=thumbnail_path,
            duration=int(info.get('duration', 0)),
            width=int(info.get('width', 0)),
            height=int(info.get('height', 0)),
            progress=progress_bar,
            progress_args=(status_msg, "📤 **Uploading...**", start_time_upload)
        )
        
        await status_msg.delete()

    except Exception as e:
        err_text = str(e)
        if "CANCELLED" in err_text:
            await status_msg.edit("🚫 Task Canceled.")
        elif "Sign in" in err_text:
             await status_msg.edit("⚠️ **Error:** Cookies required for this video.")
        else:
            await status_msg.edit(f"⚠️ **Error:** `{err_text}`")
            print(f"Error Details: {e}")

    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        # Cleanup dictionary
        if temp_id in download_active:
            del download_active[temp_id]
        download_active[chat_id] = False

if __name__ == "__main__":
    if not os.path.exists(COOKIE_FILE):
        print(f"⚠️ WARNING: '{COOKIE_FILE}' missing.")
    print("BOT STARTED")
    app.run()
    
