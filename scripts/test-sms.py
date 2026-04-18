"""Test d'envoi SMS Twilio — Jarvis V2 J2.3.

Usage : python scripts/test-sms.py <numero_e164>
Exemple : python scripts/test-sms.py +33612345678
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.integrations.sms import build_from_env  # noqa: E402


async def main(to_number: str) -> None:
    client = build_from_env()

    print("=== Account ===")
    acct = await client.get_account_info()
    print(f"  name={acct.get('friendly_name')} status={acct.get('status')}")

    print("\n=== Balance ===")
    bal = await client.get_balance()
    print(f"  balance={bal.get('balance')} {bal.get('currency')}")

    body = (
        "[J-ARVIS V2] Test SMS Twilio OK. "
        "Envoi depuis ELEXITY 34. Ne pas repondre."
    )

    print("\n=== Send ===")
    print(f"  from={client.from_number} to={to_number}")
    print(f"  body='{body}' ({len(body)} chars)")
    result = await client.send_sms(to_number=to_number, body=body)
    print(f"\n  sid={result.get('sid')}")
    print(f"  status={result.get('status')}")
    print(f"  num_segments={result.get('num_segments')}")
    print(f"  price={result.get('price')} {result.get('price_unit')}")

    print("\nOK — la delivery finale arrive en async, recheck dans 1-2 min :")
    print(f"  client.get_message_status('{result.get('sid')}')")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test-sms.py <numero_e164>", file=sys.stderr)
        print("Example: python scripts/test-sms.py +33612345678", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
