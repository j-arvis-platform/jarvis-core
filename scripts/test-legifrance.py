"""Test Legifrance + JudiLibre — Jarvis V2 J2.7.

Usage :
  python scripts/test-legifrance.py ping
  python scripts/test-legifrance.py tva      # recherche TVA 5.5% PV (article 279-0 bis CGI)
  python scripts/test-legifrance.py juri     # exemple recherche jurisprudence
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

from agent.integrations.legifrance import build_from_env  # noqa: E402


def _dump_preview(data: dict, max_chars: int = 800) -> None:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "\n... (tronque)"
    print(raw)


async def cmd_ping() -> None:
    client = build_from_env()
    print(f"=== OAuth authenticate (env={client.environment}) ===")
    token = await client.authenticate()
    print(f"  token_len={len(token)} expires_at_ts={client._token_expires_at:.0f}")

    print("\n=== Ping /search/ping ===")
    pong = await client.ping()
    print(f"  {pong[:120]}")


async def cmd_tva() -> None:
    client = build_from_env()
    print("=== Recherche 'taux reduit photovoltaique' (CGI) ===")
    res = await client.search_code(
        code_name="Code general des impots",
        query="taux reduit photovoltaique",
        limit=5,
    )
    total = res.get("totalResultNumber", 0)
    print(f"  total_results={total}")
    _dump_preview(res, max_chars=900)

    print("\n=== Recherche generique '279-0 bis' (fond ALL) ===")
    res2 = await client.search_legifrance(query="279-0 bis", fond="ALL", limit=3)
    total2 = res2.get("totalResultNumber", 0)
    print(f"  total_results={total2}")
    _dump_preview(res2, max_chars=600)


async def cmd_juri() -> None:
    client = build_from_env()
    print("=== Recherche jurisprudence 'decennale photovoltaique' ===")
    res = await client.search_jurisprudence(
        query="decennale photovoltaique",
        jurisdiction=["cc", "ca"],
        limit=3,
    )
    total = res.get("total")
    print(f"  total={total}")
    _dump_preview(res, max_chars=800)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    commands = {"ping": cmd_ping, "tva": cmd_tva, "juri": cmd_juri}
    if cmd not in commands:
        print(f"Commande inconnue : {cmd!r}", file=sys.stderr)
        sys.exit(2)
    asyncio.run(commands[cmd]())
