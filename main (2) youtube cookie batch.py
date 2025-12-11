import os
import re
import time
import math
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

# ===== Configuration =====
API_ID = int(os.getenv("API_ID", "")) 
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

DOWNLOAD_PATH = "./downloads/"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# ⚠️ Important: Make sure cookies.txt exists in the same folder
COOKIE_FILE = "cookies.txt" 

app = Client("batch_yt_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {} 
CREDIT_NAME = "𝝙 αηηυ 𝝙"

# ===== Helper Functions =====

def format_time(seconds):
    if not seconds or seconds < 0: return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

def get_readable_size(size_in_bytes) -> str:
    if not size_in_bytes: return '0B'
    units = ["B", "KB", "MB", "GB"]
    index = 0
    while size_in_bytes >= 1024 and index < len(units) - 1:
        size_in_bytes /= 1024
        index += 1
    return f'{round(size_in_bytes, 2)} {units[index]}'

async def progress_bar(current, total, status_msg, action_text, start_time):
    now = time.time()
    if (now - getattr(progress_bar, "last_update", 0)) < 3 and current != total:
        return
    progress_bar.last_update = now
    
    percentage = current * 100 / total
    speed = current / (now - start_time) if (now - start_time) > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    bars = 10
    filled = math.floor(percentage / 10)
    prog = "▰" * filled + "▱" * (bars - filled)
    
    try:
        await status_msg.edit(
            f"{action_text}\n"
            f"{prog} | {round(percentage)}%\n"
            f"💾 Size: {get_readable_size(current)} / {get_readable_size(total)}\n"
            f"🚀 Speed: {get_readable_size(speed)}/s\n"
            f"⏳ ETA: {format_time(eta)}"
        )
    except:
        pass

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

# ===== Bot Handlers =====

@app.on_message(filters.command("start"))
async def start_handler(_, m: Message):
    await m.reply_text("👋 **Hello!**\nUse `/drm` to start.")

@app.on_message(filters.command("drm"))
async def drm_command(_, m: Message):
    user_data[m.chat.id] = {"state": "WAITING_BATCH_NAME"}
    await m.reply_text("🏷 **Enter the Batch Name:**")

@app.on_message(filters.text & filters.private)
async def handle_text(_, m: Message):
    uid = m.chat.id
    state = user_data.get(uid, {}).get("state")

    if state == "WAITING_BATCH_NAME":
        batch_name = m.text.strip()
        user_data[uid]["batch_name"] = batch_name
        user_data[uid]["state"] = "WAITING_TXT"
        await m.reply_text(f"✅ Batch: **{batch_name}**\n📂 **Send the .txt file now.**")

@app.on_message(filters.document & filters.private)
async def process_txt_file(client, m: Message):
    uid = m.chat.id
    current_data = user_data.get(uid, {})
    
    if current_data.get("state") != "WAITING_TXT":
        return await m.reply("⚠️ Please use `/drm` command first.")

    batch_name = current_data.get("batch_name", "Unknown Batch")
    user_data[uid]["state"] = "PROCESSING"
    
    status_msg = await m.reply("📥 **Reading file...**")
    file_path = await m.download(file_name=f"batch_{uid}.txt")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return await status_msg.edit(f"❌ Error: {e}")

    total_links = len(lines)
    await status_msg.edit(f"✅ Found {total_links} lines. Filtering & Downloading...")
    
    # Check Cookies
    use_cookies = os.path.exists(COOKIE_FILE)
    if not use_cookies:
        await m.reply_text("⚠️ **Warning:** `cookies.txt` not found. YouTube might block downloads.")

    # Loop with Enumeration (To get Line Number)
    # start=1 means line 1 will have ID 1
    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line: continue

        try:
            # 1. Parsing
            match = re.match(r"(.*?)(https?://.*)", line)
            if not match: continue
            
            raw_title = match.group(1).strip()
            url = match.group(2).strip()

            if "youtube.com" not in url and "youtu.be" not in url:
                continue

            if raw_title.endswith(":") or raw_title.endswith("|") or raw_title.endswith("-"):
                raw_title = raw_title[:-1].strip()
            
            # Use Line Number as ID
            vid_id = line_num 
            custom_name = clean_filename(raw_title) if raw_title else f"Video_{vid_id}"

        except:
            continue

        # --- Downloading ---
        await status_msg.edit(f"⬇️ **Downloading ({vid_id}/{total_links})**\n`{custom_name}`")
        
        ydl_opts = {
            'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            'outtmpl': f"{DOWNLOAD_PATH}{custom_name}.%(ext)s",
            'merge_output_format': 'mkv',
            'quiet': True,
            'no_warnings': True,
            # COOKIES FIX HERE
            'cookiefile': COOKIE_FILE if use_cookies else None 
        }

        filename = None
        thumb = None

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    if os.path.exists(base + ".mkv"): filename = base + ".mkv"
                    elif os.path.exists(base + ".mp4"): filename = base + ".mp4"

                width = info.get('width', 0)
                height = info.get('height', 0)
                duration = int(info.get('duration', 0))
                res_str = f"[{width}x{height}p]" if height else "[480p]"

            # --- Uploading ---
            await status_msg.edit(f"⬆️ **Uploading ({vid_id})**...")
            start_time = time.time()

            # Updated Caption with Correct VID ID
            caption = (
                f"[🎥]Vid Id : {vid_id}\n"
                f"Video Title : {custom_name} {res_str} .mkv\n"
                f"Batch Name : {batch_name}\n\n"
                f"Extracted by➤{CREDIT_NAME}"
            )

            thumb_path = f"{DOWNLOAD_PATH}{custom_name}.jpg"
            if os.path.exists(thumb_path): thumb = thumb_path

            await client.send_video(
                chat_id=m.chat.id,
                video=filename,
                caption=caption,
                duration=duration,
                width=width,
                height=height,
                thumb=thumb,
                progress=progress_bar,
                progress_args=(status_msg, f"⬆️ **Uploading ({vid_id})...**", start_time)
            )

            if filename and os.path.exists(filename): os.remove(filename)
            if thumb and os.path.exists(thumb): os.remove(thumb)

        except Exception as e:
            err_msg = str(e)
            if "Sign in" in err_msg:
                await m.reply_text(f"🛑 **Critical Error on ID {vid_id}:**\nYouTube requires cookies. Please add `cookies.txt` to the bot folder.\nCommand stopped.")
                break # Stop process to prevent ban
            
            await m.reply_text(f"❌ **Failed ID {vid_id}:** `{custom_name}`\n{err_msg}")
            continue

    await status_msg.edit("✅ **Batch Process Completed!**")
    if os.path.exists(file_path): os.remove(file_path)
    user_data[uid] = {}

if __name__ == "__main__":
    print("🤖 Bot Started...")
    app.run()
                  
