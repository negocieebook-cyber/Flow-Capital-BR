from __future__ import annotations

import os
from pathlib import Path

import requests


def _token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nao configurado no .env")
    return token


def _chat_ids() -> list[str]:
    raw_chat_ids = os.getenv("TELEGRAM_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID")
    if not raw_chat_ids:
        raise RuntimeError("TELEGRAM_CHAT_ID ou TELEGRAM_CHAT_IDS nao configurado no .env")
    chat_ids = [chat_id.strip() for chat_id in raw_chat_ids.split(",") if chat_id.strip()]
    if not chat_ids:
        raise RuntimeError("Nenhum chat_id valido configurado no .env")
    return chat_ids


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{_token()}/sendMessage"
    failures = []
    for chat_id in _chat_ids():
        response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
        if not response.ok:
            failures.append(f"{chat_id}: HTTP {response.status_code} - {response.text}")
    if failures:
        raise RuntimeError(f"Falha Telegram sendMessage: {'; '.join(failures)}")


def send_telegram_document(file_path: str, caption: str) -> None:
    url = f"https://api.telegram.org/bot{_token()}/sendDocument"
    path = Path(file_path)
    failures = []
    for chat_id in _chat_ids():
        with path.open("rb") as file:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"document": (path.name, file, "application/pdf")},
                timeout=60,
            )
        if not response.ok:
            failures.append(f"{chat_id}: HTTP {response.status_code} - {response.text}")
    if failures:
        raise RuntimeError(f"Falha Telegram sendDocument: {'; '.join(failures)}")


def test_telegram_connection() -> None:
    send_telegram_message("Teste do Flow Map Brasil: integração com Telegram funcionando.")
