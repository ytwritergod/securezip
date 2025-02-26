import time
os.environ['TZ'] = 'UTC'  # Set timezone to UTC 
time.tzset()  # Apply timezone
import os
import re
import math
import shutil
import zipfile
import time  # New
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, AUTHORIZED_FILE, MAX_TOTAL_SIZE

# Fix Time Sync Issue
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

def split_large_file(file_path, chunk_size=2*1024*1024*1024):
    part_num = 1
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            part_name = f"{file_            with open(part_name, 'wb') as chunk_file:
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

# ==================== AUTHORIZATION FILTER ====================
async def auth_filter(_, __, message: Message):
    return message.from_user.id in load_authorized_users()

authorized = filters.create(auth_filter)

# ==================== COMMAND HANDLERS ====================
@app.on_message(filters.command("authorise") & filters.user(OWNER_ID))
async def authorize_user(_, message: Message):
    try:
        user_id = int(message.command[1])
        if user_id in load_authorized_users():
            await message.reply("✅ User already authorized!")
            return
        save_authorized_user(user_id)
        await message.reply(f"🔓 Authorized user: {user_id}")
    except (IndexError, ValueError):
        await message.reply("❌ Use: /authorise <user_id>")

@app.on_message(filters.command("start") & authorized)
async def start(_, message: Message):
    await message.reply(
        "📁 **ZIP Archiver Bot**\n"
        "Send /zip to start\n"
        "Made with ❤️ by **God Father**"
    )

@app.on_message(filters.command("zip") & authorized)
async def start_zip_session(_, message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {
        "files": [],
        "total_size": 0,
        "process_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "zip_name": "archive.zip",
        "password": None
    }
    await message.reply("🔄 Send files (Max 20GB total)")

# ==================== FILE HANDLING ====================
@app.on_message(authorized & (filters.document | filters.video | filters.photo))
async def handle_files(_, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        return

    try:
        # File handling logic
        file_size = message.document.file_size if message.document else \
                   message.video.file_size if message.video else \
                   message.photo.file_size

        # Check total size
        new_total = user_data[user_id]["total_size"] + file_size
        if new_total > MAX_TOTAL_SIZE:
            await message.reply("⚠️ Total size exceeds 20GB limit!")
            return

        # Download file
        file_name = message.document.file_name if message.document else \
                   message.video.file_name if message.video else \
                   f"photo_{message.id}.jpg"

        temp_dir = f"temp_{user_id}_{user_data[user_id]['process_id']}"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = await message.download(file_name=os.path.join(temp_dir, file_name))

        # Update data
        user_data[user_id]["files"].append(file_path)
        user_data[user_id]["total_size"] = new_total

        await message.reply(f"✅ Saved: {file_name}\n📏 Total: {format_size(new_total)}")

    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ==================== ZIP CREATION WITH PASSWORD ====================
@app.on_message(filters.command("createzip") & authorized)
async def create_zip_command(_, message: Message):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Set Name", callback_data="set_name"),
         InlineKeyboardButton("🔑 Set Password", callback_data="set_password")],
        [InlineKeyboardButton("🚀 Create ZIP", callback_data="create_zip")]
    ])
    await message.reply("⚙️ Configure ZIP:", reply_markup=buttons)

@app.on_callback_query()
async def handle_callbacks(_, query):
    user_id = query.from_user.id
    if user_id not in user_data:
        await query.answer("Session expired! Start with /zip")
        return

    if query.data == "set_name":
        await query.message.edit("📝 Reply with ZIP name (e.g., data.zip)")
        user_data[user_id]["awaiting"] = "zip_name"
    
    elif query.data == "set_password":
        await query.message.edit("🔒 Reply with password (or /skip)")
        user_data[user_id]["awaiting"] = "password"
    
    elif query.data == "create_zip":
        await create_zip(_, query.message)

@app.on_message(filters.text & ~filters.command & authorized)
async def handle_text(_, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data or "awaiting" not in user_data[user_id]:
        return

    text = message.text.strip()
    input_type = user_data[user_id]["awaiting"]

    if input_type == "zip_name":
        if not re.match(r"^[\w\-]+\.zip$", text):
            await message.reply("❌ Invalid name! Use: example.zip")
            return
        user_data[user_id]["zip_name"] = text
        await message.reply(f"📁 Name set: {text}")
    
    elif input_type == "password":
        user_data[user_id]["password"] = text if text != "/skip" else None
        reply = "🔒 Password removed!" if text == "/skip" else f"🔐 Password set: {'•'*len(text)}"
        await message.reply(reply)

    del user_data[user_id]["awaiting"]

async def create_zip(_, message: Message):
    user_id = message.from_user.id
    try:
        data = user_data.get(user_id)
        if not data or not data["files"]:
            await message.reply("⚠️ No files to archive!")
            return

        # Create ZIP with password
        zip_path = data["zip_name"]
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if data["password"]:
                zipf.setpassword(data["password"].encode('utf-8'))
            for file in data["files"]:
                zipf.write(file, os.path.basename(file))

        # Split and send
        zip_size = os.path.getsize(zip_path)
        caption = f"🔒 Password: {data['password']}" if data["password"] else ""
        
        if zip_size > 2 * 1024 * 1024 * 1024:
            await message.reply("⚡ Splitting into 2GB parts...")
            for part in split_large_file(zip_path):
                await message.reply_document(document=part, caption=caption)
                os.remove(part)
        else:
            await message.reply_document(document=zip_path, caption=caption)

        # Cleanup
        shutil.rmtree(f"temp_{user_id}_{data['process_id']}", ignore_errors=True)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        del user_data[user_id]

    except Exception as e:
        await message.reply(f"❌ Failed: {str(e)}")

if __name__ == "__main__":
    print("🤖 Bot Started!")
    app.run()
