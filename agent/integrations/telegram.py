"""
Telegram Bot wrapper pour J-ARVIS V2.

Un seul bot actif par tenant (ex. @Jarvis_hamid_bot pour ELEXITY 34).
Les personas narratives (Lea, Hugo, Claire...) signent les messages, mais
tous passent par le meme bot physique.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10.0


@dataclass
class TelegramBot:
    """Wrapper async autour de l'API Bot Telegram."""

    token: str
    admin_chat_id: str
    timeout: float = DEFAULT_TIMEOUT

    @property
    def _base_url(self) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self.token}"

    async def _post(self, method: str, data: dict[str, Any] | None = None,
                    files: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}/{method}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, data=data, files=files)
            payload = resp.json()
        if not payload.get("ok"):
            logger.error("telegram_api_error method=%s payload=%s", method, payload)
            raise TelegramError(payload.get("description", "unknown error"), payload)
        return payload["result"]

    async def get_me(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self._base_url}/getMe")
        payload = resp.json()
        if not payload.get("ok"):
            raise TelegramError(payload.get("description", "getMe failed"), payload)
        return payload["result"]

    async def send_message(self, text: str, chat_id: str | None = None,
                           parse_mode: str | None = "HTML") -> dict[str, Any]:
        data: dict[str, Any] = {
            "chat_id": chat_id or self.admin_chat_id,
            "text": text,
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        return await self._post("sendMessage", data=data)

    async def send_photo(self, photo_path: str | Path, caption: str = "",
                         chat_id: str | None = None) -> dict[str, Any]:
        path = Path(photo_path)
        if not path.is_file():
            raise FileNotFoundError(f"photo introuvable : {path}")
        data = {
            "chat_id": chat_id or self.admin_chat_id,
            "caption": caption,
        }
        with path.open("rb") as f:
            files = {"photo": (path.name, f, "application/octet-stream")}
            return await self._post("sendPhoto", data=data, files=files)

    async def get_updates(self, offset: int | None = None,
                          limit: int = 100, timeout: int = 0) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        async with httpx.AsyncClient(timeout=self.timeout + timeout) as client:
            resp = await client.get(f"{self._base_url}/getUpdates", params=params)
        payload = resp.json()
        if not payload.get("ok"):
            raise TelegramError(payload.get("description", "getUpdates failed"), payload)
        return payload["result"]


class TelegramError(RuntimeError):
    def __init__(self, message: str, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {}


def build_from_env(env: dict[str, str] | None = None) -> TelegramBot:
    """Construit un TelegramBot a partir des env vars du tenant."""
    import os
    env = env or os.environ
    token = env["TELEGRAM_BOT_TOKEN_JARVIS"]
    admin = env["TELEGRAM_CHAT_ID_ADMIN"]
    return TelegramBot(token=token, admin_chat_id=admin)
