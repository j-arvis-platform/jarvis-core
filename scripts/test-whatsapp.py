"""Test d'envoi WhatsApp Business — Jarvis V2 J2.1.

Usage :
  python scripts/test-whatsapp.py <numero_e164> [text|template] [template_name]

Exemples :
  python scripts/test-whatsapp.py +33679242770 text
  python scripts/test-whatsapp.py +33679242770 template hello_world
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.integrations.whatsapp import build_from_env  # noqa: E402


async def main(to_number: str, mode: str, template_name: str) -> None:
    client = build_from_env()

    print("=== Phone info ===")
    info = await client.get_phone_info()
    print(f"  display={info.get('display_phone_number')}")
    print(f"  verified_name={info.get('verified_name')}")
    print(f"  quality_rating={info.get('quality_rating')}")
    print(f"  messaging_limit_tier={info.get('messaging_limit_tier')}")

    print(f"\n=== Send ({mode}) ===")
    print(f"  to={to_number}")

    if mode == "text":
        body = (
            "[J-ARVIS V2] Test WhatsApp Business OK. "
            "Envoi depuis ELEXITY 34. Ne pas repondre."
        )
        print(f"  body='{body}' ({len(body)} chars)")
        result = await client.send_text_message(to_number=to_number, body=body)
    elif mode == "template":
        # 'hello_world' est le template fourni par Meta par defaut (langue en_US).
        lang = "en_US" if template_name == "hello_world" else "fr"
        print(f"  template={template_name} lang={lang}")
        result = await client.send_template_message(
            to_number=to_number,
            template_name=template_name,
            language_code=lang,
        )
    else:
        print(f"mode inconnu : {mode!r}", file=sys.stderr)
        sys.exit(2)

    msgs = result.get("messages") or []
    if msgs:
        print(f"\n  message_id={msgs[0].get('id')}")
        print(f"  status={msgs[0].get('message_status')}")
    else:
        print(f"  raw response: {result}")

    print("\nOK — delivery asynchrone cote Meta (quelques secondes).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    to_number = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "text"
    template_name = sys.argv[3] if len(sys.argv) > 3 else "hello_world"
    asyncio.run(main(to_number, mode, template_name))
