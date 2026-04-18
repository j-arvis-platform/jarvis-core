"""Test MCP OpenSolar — Jarvis V2 J3.4.

Valide :
1. Instantiation client depuis env
2. Authentification (email/password -> JWT token)
3. list_projects : retourne les derniers projets ELEXITY
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = (ROOT.parent / "modules" / "module-photovoltaique"
           / "mcps" / "opensolar")
sys.path.insert(0, str(MCP_DIR))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from opensolar_client import OpenSolarError, build_from_env  # noqa: E402


async def main() -> int:
    print("=== 1) Instantiation ===")
    client = build_from_env()
    print(f"  email={client.email}")
    print(f"  org_id={client.org_id}")

    print("\n=== 2) Authentification ===")
    try:
        token = await client.authenticate()
    except OpenSolarError as e:
        print(f"  KO : {e}")
        return 1
    print(f"  OK : token_len={len(token)}")

    print("\n=== 3) list_projects (5 derniers) ===")
    try:
        data = await client.list_projects(limit=5)
    except OpenSolarError as e:
        print(f"  KO : {e}")
        return 2

    if isinstance(data, list):
        results = data
    elif isinstance(data, dict):
        results = data.get("results", [])
    else:
        results = []
    print(f"  count={len(results)}")

    for p in results[:5]:
        print(f"  - id={p.get('id')} "
              f"address={(p.get('address') or '')[:60]!r} "
              f"created={p.get('created_date') or p.get('created')}")

    print("\nBilan : OpenSolar MCP operationnel.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
