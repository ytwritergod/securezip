import os

# Configuration
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
OWNER_ID = int(os.environ.get("OWNER_ID", 123456789))  # Your User ID
AUTHORIZED_FILE = "authorized.txt"  # Authorized users storage
MAX_TOTAL_SIZE = 20 * 1024 * 1024 * 1024  # 20GB
