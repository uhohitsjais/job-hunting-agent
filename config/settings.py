import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "jobs.db"))
GENERATED_DIR = BASE_DIR / "data" / "generated"
LOGS_DIR = BASE_DIR / "data" / "logs"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "")

FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
