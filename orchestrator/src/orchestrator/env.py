"""Load repo-root `.env` (Groq + registry settings) for the orchestrator."""

from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV)
