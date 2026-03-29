import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
REDIS_URL = os.getenv("REDIS_URL")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# ─── Webhook ───
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# ─── MetaApi ───
META_API_TOKEN = os.getenv("META_API_TOKEN")

# ─── Payments / NOWPayments ───
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ─── Telegram ───
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ─── OAuth ───
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# ─── Trading Limits ───
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "0.10"))
ALLOWED_SYMBOLS = [s.strip() for s in os.getenv(
    "ALLOWED_SYMBOLS",
    "XAUUSD,EURUSD,GBPUSD,BTCUSD,ETHUSD,US30,NAS100,BTCUSDT,ETHUSDT"
).split(",")]

# ─── Risk Guard Limits ───
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
MAX_POSITIONS_PER_SYMBOL = int(os.getenv("MAX_POSITIONS_PER_SYMBOL", "1"))
MAX_DAILY_DRAWDOWN = float(os.getenv("MAX_DAILY_DRAWDOWN", "0.05"))
MAX_SIGNALS_PER_MINUTE = int(os.getenv("MAX_SIGNALS_PER_MINUTE", "3"))
