"""Test d'envoi email SMTP — Jarvis V2 J2.2."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.integrations.email import build_from_env  # noqa: E402


async def main() -> None:
    import os
    client = build_from_env()

    # FROM contact@elexity34.fr -> TO admin@j-arvis.ai
    # Valide : (a) envoi Workspace via SMTP Gmail, (b) reception boite OVH J-ARVIS
    to = os.environ.get("TEST_EMAIL_TO", "admin@j-arvis.ai")

    print("=== Config ===")
    print(f"  host={client.host} port={client.port}")
    print(f"  from={client.from_header}")
    print(f"  to={to}")

    variables = {
        "destinataire": to,
        "smtp_host": client.host,
        "smtp_port": client.port,
        "from_email": client.from_email,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    print("\n=== Send ===")
    result = await client.send_email_with_template(
        to=to,
        template_name="test",
        variables=variables,
        subject="[J-ARVIS V2] Test SMTP Gmail (J2.2)",
    )
    print(f"  message_id={result['message_id']}")
    print(f"  recipients={result['recipients']}")
    print("\nOK.")


if __name__ == "__main__":
    asyncio.run(main())
