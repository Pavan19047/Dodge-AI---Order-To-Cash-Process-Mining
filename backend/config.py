import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "dodge.duckdb"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# LLM config
# gemini-2.0-flash: confirmed available via list_models() for this key
GEMINI_MODEL = "gemini-2.0-flash"

# Query limits
MAX_GRAPH_NODES = 250
MAX_QUERY_ROWS = 50
QUERY_TIMEOUT_SECONDS = 15

# CORS origins (update for production)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://*.vercel.app",
    "*",
]
