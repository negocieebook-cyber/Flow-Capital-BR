from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "flow_map_brasil.db"


def ensure_directories() -> None:
    for path in (DATA_DIR, REPORTS_DIR, CHARTS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    ensure_directories()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    log_path = LOGS_DIR / "weekly_report.log"
    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


def load_environment() -> None:
    load_dotenv(BASE_DIR / ".env")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _validate_settings(settings: dict[str, Any]) -> None:
    required = [
        ("market", "benchmark"),
        ("report", "lookback_weeks"),
        ("report", "volume_baseline_weeks"),
        ("report", "unusual_volume_threshold"),
        ("report", "leader_score_threshold"),
    ]
    missing = [f"{s}.{k}" for s, k in required if not settings.get(s, {}).get(k)]
    if missing:
        raise ValueError(f"Configurações obrigatórias ausentes em user_settings.yml: {', '.join(missing)}")


def load_user_settings() -> dict[str, Any]:
    settings = load_yaml(CONFIG_DIR / "user_settings.yml")
    _validate_settings(settings)
    return settings


def load_sectors() -> dict[str, list[str]]:
    raw = load_yaml(CONFIG_DIR / "sectors_brazil.yml")
    return {sector: list(tickers or []) for sector, tickers in raw.items()}


def get_database_path() -> Path:
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("sqlite:///"):
        value = database_url.replace("sqlite:///", "", 1)
        path = Path(value)
        return path if path.is_absolute() else BASE_DIR / path
    return DB_PATH


def get_telegram_chat_id(settings: dict[str, Any]) -> str | None:
    return os.getenv("TELEGRAM_CHAT_ID") or settings.get("telegram", {}).get("chat_id")
