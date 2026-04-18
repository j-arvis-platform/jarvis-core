"""Test d'envoi Telegram — Jarvis V2 J2.5."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENANT_ENV = Path(__file__).resolve().parents[2] / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.integrations.telegram import build_from_env  # noqa: E402


async def main() -> None:
    bot = build_from_env()

    print("=== getMe ===")
    me = await bot.get_me()
    print(f"  bot id={me['id']} username=@{me['username']} name={me['first_name']}")

    print("\n=== sendMessage ===")
    text = (
        "\U0001F680 <b>J-ARVIS V2 connecte</b>\n\n"
        "Bonjour Hamid, c'est Jarvis.\n"
        "Pret pour J2 (canaux de communication).\n\n"
        "<i>Etape 2.5 Telegram : OK.</i>"
    )
    result = await bot.send_message(text)
    print(f"  message_id={result['message_id']} chat_id={result['chat']['id']}")

    print("\nOK.")


if __name__ == "__main__":
    asyncio.run(main())
