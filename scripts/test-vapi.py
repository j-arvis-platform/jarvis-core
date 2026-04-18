"""Test Vapi — Jarvis V2 J2.4.

Usage :
  python scripts/test-vapi.py inspect
      -> lecture seule : list assistants + phone numbers + details Axel
  python scripts/test-vapi.py call <numero_e164>
      -> APPEL SORTANT REEL (payant !) depuis Axel vers le numero
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.integrations.vapi import build_from_env  # noqa: E402


async def inspect() -> None:
    import os
    client = build_from_env()

    print("=== Assistants ===")
    assistants = await client.list_assistants(limit=20)
    for a in assistants:
        model = a.get("model") or {}
        voice = a.get("voice") or {}
        print(f"  id={a.get('id')}")
        print(f"    name={a.get('name')!r}")
        print(f"    model={model.get('provider')}/{model.get('model')}")
        print(f"    voice={voice.get('provider')}/{voice.get('voiceId')}")
        print(f"    createdAt={a.get('createdAt')}")

    print("\n=== Phone numbers ===")
    numbers = await client.list_phone_numbers(limit=20)
    for p in numbers:
        print(f"  id={p.get('id')}")
        print(f"    number={p.get('number')} provider={p.get('provider')}")
        print(f"    assistantId={p.get('assistantId')}")

    axel_id = os.environ.get("VAPI_ASSISTANT_ID_AXEL")
    if axel_id:
        print(f"\n=== Detail assistant Axel ({axel_id}) ===")
        axel = await client.get_assistant(axel_id)
        first = (axel.get("firstMessage") or "")[:120]
        print(f"  name={axel.get('name')!r}")
        print(f"  firstMessage={first!r}")
        model = axel.get("model") or {}
        voice = axel.get("voice") or {}
        print(f"  model={model.get('provider')}/{model.get('model')}")
        print(f"  voice={voice.get('provider')}/{voice.get('voiceId')}")
        sys_prompt = model.get("messages") or []
        if sys_prompt:
            first_msg = sys_prompt[0] if sys_prompt else {}
            content = (first_msg.get("content") or "")[:200]
            print(f"  system_prompt_start={content!r}")
        print(f"  tools_count={len(axel.get('tools') or [])}")


async def call(to_number: str) -> None:
    import os
    client = build_from_env()
    assistant_id = os.environ["VAPI_ASSISTANT_ID_AXEL"]
    phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID")

    print("=== Outbound call ===")
    print(f"  assistant={assistant_id}")
    print(f"  phone_number_id={phone_number_id}")
    print(f"  to={to_number}")

    result = await client.create_outbound_call(
        assistant_id=assistant_id,
        customer_number=to_number,
        phone_number_id=phone_number_id,
        metadata={"source": "jarvis-v2-test-j2.4"},
    )
    call_id = result.get("id")
    print(f"  call_id={call_id}")
    print(f"  status={result.get('status')}")
    print(f"  createdAt={result.get('createdAt')}")
    print("\nOK. Transcript accessible ~30s apres raccrochage :")
    print(f"  client.get_call_transcript('{call_id}')")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "inspect":
        asyncio.run(inspect())
    elif cmd == "call":
        if len(sys.argv) < 3:
            print("Usage: python scripts/test-vapi.py call <numero_e164>",
                  file=sys.stderr)
            sys.exit(2)
        asyncio.run(call(sys.argv[2]))
    else:
        print(f"Commande inconnue : {cmd!r}", file=sys.stderr)
        sys.exit(2)
