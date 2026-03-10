import os
from dotenv import load_dotenv

load_dotenv()

def load_config():
    return {
        "server_ws_url": os.getenv("SERVER_WS_URL", "ws://127.0.0.1:1984/ws/events"),
        "retry_delay": int(os.getenv("RETRY_DELAY", 30))
    }