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

# ⚡ MULTIPLE SOCKS5 PROXIES (Auto Rotation)
PROXIES = [
    "socks5://13.232.2.142:46866",
    "socks5://40.192.14.136:10019",
    "socks5://40.192.16.115:9267",
    "socks5://40.192.100.189:9981",
    "socks5://18.60.222.217:812",
    "socks5://43.205.124.165:448",
    "socks5://40.192.16.115:15769",
    "socks5://13.232.2.142:421",
    "socks5://165.231.253.66:9443",
    "socks5://40.192.16.115:38915",
    "socks5://18.60.222.217:9252",
    "socks5://40.192.3.100:8714",
    "socks5://40.192.14.136:48293",
    "socks5://43.205.124.165:27287",
    "socks5://40.192.100.189:9092"
]

def get_next_proxy():
    proxy = PROXIES.pop(0)
    PROXIES.append(proxy)
    return proxy


app = Client(
    "ytbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


def convert_to_watch(url):
    match = re.search(r"(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return f"https://www.youtube.com/watch?v={match.group(1)}" if match else url


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
async def start(_, message):
    await message.reply(
        "👋 Namaste!\n\n"
        "🎥 YouTube link bhejo, main 360p me download karke Telegram me bhej dunga.\n"
        "🌐 Automatic Proxy Rotation Enabled 🔥\n\n"
        "👉 Private / Age restricted videos bhi support!"
    )


async def download(video_url, status):
    retries = len(PROXIES)

    for attempt in range(retries):
        proxy = get_next_proxy()
        await status.edit(f"🌐 Using Proxy {attempt+1}/{retries}\n`{proxy}`")

        try:
            start = time.time()
            ydl_opts = {
                "format": "18",
                "outtmpl": DOWNLOAD_PATH + "%(title)s.%(ext)s",
                "merge_output_format": "mp4",
                "cookies": "cookies.txt",
                "proxy": proxy,
                "quiet": True,
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

        except Exception as e:
            await status.edit(f"⚠️ Proxy failed:\n`{proxy}`\n🔁 Retrying…")

    raise Exception("❌ All proxies failed! Try later.")


@app.on_message(filters.text & ~filters.command("start"))
async def process(_, message):
    url = convert_to_watch(message.text.strip())

    if "youtu" not in url:
        return await message.reply("❌ Valid YouTube link bhejo!")

    status = await message.reply("🔍 Validating URL…")

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
    print("BOT STARTING…")
    app.run()
    except Exception as e:
        await status.edit(f"❌ Error: `{str(e)}`")


if __name__ == "__main__":
    print("BOT STARTING…")
    app.run()
