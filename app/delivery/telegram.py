from __future__ import annotations

import os
from pathlib import Path

import requests


def _token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nao configurado no .env")
    return token


def _chat_id() -> str:
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID nao configurado no .env")
    return chat_id


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{_token()}/sendMessage"
    response = requests.post(url, data={"chat_id": _chat_id(), "text": text}, timeout=30)
    if not response.ok:
        raise RuntimeError(f"Falha Telegram sendMessage: HTTP {response.status_code} - {response.text}")


def send_telegram_document(file_path: str, caption: str) -> None:
    url = f"https://api.telegram.org/bot{_token()}/sendDocument"
    path = Path(file_path)
    with path.open("rb") as file:
        response = requests.post(
            url,
            data={"chat_id": _chat_id(), "caption": caption},
            files={"document": (path.name, file, "application/pdf")},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"Falha Telegram sendDocument: HTTP {response.status_code} - {response.text}")


def test_telegram_connection() -> None:
    send_telegram_message("Teste do Flow Map Brasil: integração com Telegram funcionando.")
