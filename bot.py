import os
import re
import math
import shutil
import zipfile
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, AUTHORIZED_FILE, MAX_TOTAL_SIZE

# Fix Time Sync
os.environ['TZ'] = 'UTC'
time.tzset()

# Initialize Client
app = Client(
    "secure_zip_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_data = {}

# ==================== HELPER FUNCTIONS ====================
def format_size(size_bytes):
    units = ("B", "KB", "MB", "GB")
    if size_bytes == 0:
        return "0B"
    i = int(math.floor(math.log(size_bytes, 1024)))
    return f"{round(size_bytes / (1024 ** i), 2)} {units[i]}"

def split_large_file(file_path, chunk_size=2*1024*1024*1024):  # Fixed 2GB chunk size
    part_num = 1
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            part_name = f"{file_path}.part{part_num}"
            with open(part_name, 'wb') as chunk_file:
                chunk_file.write(chunk)
            yield part_name
            part_num += 1
    os.remove(file_path)

def load_authorized_users():
    if not os.path.exists(AUTHORIZED_FILE):
        return [OWNER_ID]
    with open(AUTHORIZED_FILE, 'r') as f:
        return [int(line.strip()) for line in f if line.strip()]

def save_authorized_user(user_id: int):
    with open(AUTHORIZED_FILE, 'a') as f:
        f.write(f"{user_id}\n")

# ==================== COMMAND HANDLERS ====================
@app.on_message(filters.command("start") & filters.create(lambda _, __, m: m.from_user.id in load_authorized_users()))
async def start(_, message: Message):
    await message.reply("📁 Send /zip to start")

@app.on_message(filters.command("zip") & filters.create(lambda _, __, m: m.from_user.id in load_authorized_users()))
async def start_zip(_, message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {
        "files": [],
        "total_size": 0,
        "process_id": datetime.now().strftime("%Y%m%d%H%M%S")
    }
    await message.reply("🔄 Send files (Max 20GB)")

# ==================== FILE HANDLING ====================
@app.on_message((filters.document | filters.video | filters.photo) & filters.create(lambda _, __, m: m.from_user.id in load_authorized_users()))
async def handle_files(_, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        return

    try:
        file_size = message.document.file_size if message.document else message.video.file_size if message.video else message.photo.file_size
        new_total = user_data[user_id]["total_size"] + file_size

        if new_total > MAX_TOTAL_SIZE:
            await message.reply("⚠️ Size exceeded 20GB!")
            return

        file_name = message.document.file_name if message.document else message.video.file_name if message.video else f"photo_{message.id}.jpg"
        temp_dir = f"temp_{user_id}_{user_data[user_id]['process_id']}"
        
        os.makedirs(temp_dir, exist_ok=True)
        file_path = await message.download(file_name=os.path.join(temp_dir, file_name))
        
        user_data[user_id]["files"].append(file_path)
        user_data[user_id]["total_size"] = new_total

        await message.reply(f"✅ Saved: {file_name}\n📏 Total: {format_size(new_total)}")

    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ==================== ZIP CREATION ====================
@app.on_message(filters.command("createzip") & filters.create(lambda _, __, m: m.from_user.id in load_authorized_users()))
async def create_zip(_, message: Message):
    user_id = message.from_user.id
    if not user_data.get(user_id):
        await message.reply("⚠️ Send /zip first!")
        return

    try:
        data = user_data[user_id]
        zip_path = f"archive_{data['process_id']}.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in data["files"]:
                zipf.write(file, os.path.basename(file))

        # Split if >2GB
        zip_size = os.path.getsize(zip_path)
        if zip_size > 2*1024*1024*1024:
            await message.reply("⚡ Splitting into parts...")
            for part in split_large_file(zip_path):
                await message.reply_document(document=part)
                os.remove(part)
        else:
            await message.reply_document(document=zip_path)

        # Cleanup
        shutil.rmtree(f"temp_{user_id}_{data['process_id']}", ignore_errors=True)
        os.remove(zip_path)
        del user_data[user_id]

    except Exception as e:
        await message.reply(f"❌ Failed: {str(e)}")

if __name__ == "__main__":
    print("🤖 Bot Started!")
    app.run()
