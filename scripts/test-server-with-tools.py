"""Valide que /api/chat (ou JarvisAgent.respond directement) peut
reellement APPELER les outils MCP (Supabase, Invoice Ninja...) via
le parametre tools= de l'API Claude.

Usage :
  python scripts/test-server-with-tools.py               # test local via respond()
  python scripts/test-server-with-tools.py --prod        # test via https://elexity34.j-arvis.ai/api/chat
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

PROMPT = (
    "Crée un contact test dans Supabase : Mme Testouille (prenom: Alice), "
    "email alice.testouille@test-jarvis.fr, telephone 0600000000, "
    "adresse 1 rue du Test 34150 Gignac, type prospect, source 'test-j3-tools'. "
    "Puis dis-moi l'UUID créé et rappelle-moi les valeurs saisies."
)

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def run_local() -> tuple[bool, str | None]:
    from agent.handlers.main import JarvisAgent
    j = JarvisAgent("elexity34")
    # Injecter les skills actifs pour etre au plus proche du flow serveur
    from agent.core.skills import discover_skills, match_skills, inject_into_system_prompt
    skills = discover_skills(ROOT.parent / "modules")
    matched = match_skills(PROMPT, skills)
    if matched:
        j.system_prompt = inject_into_system_prompt(j.system_prompt, matched)

    reply = j.respond(PROMPT)
    print("--- reponse locale ---")
    print(reply[:1500])
    m = UUID_RE.search(reply)
    return (m is not None, m.group(0) if m else None)


def run_prod() -> tuple[bool, str | None]:
    import httpx
    resp = httpx.post(
        "https://elexity34.j-arvis.ai/api/chat",
        json={"message": PROMPT},
        timeout=90,
    )
    print(f"status={resp.status_code}")
    data = resp.json() if resp.content else {}
    reply = data.get("response", "")
    print("--- reponse prod ---")
    print(reply[:1500])
    m = UUID_RE.search(reply)
    return (m is not None, m.group(0) if m else None)


def cleanup(uuid: str) -> None:
    import httpx
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    resp = httpx.delete(f"{url}/rest/v1/contacts?id=eq.{uuid}",
                        headers=headers, timeout=15)
    print(f"cleanup contact {uuid[:8]}... -> HTTP {resp.status_code}")


def main() -> int:
    mode = "prod" if "--prod" in sys.argv else "local"
    print(f"=== Test respond() avec tools (mode={mode}) ===")
    print(f"Prompt : {PROMPT[:140]}...")

    if mode == "prod":
        ok, uuid = run_prod()
    else:
        ok, uuid = run_local()

    if ok:
        print(f"\nOK : UUID detecte dans la reponse -> {uuid}")
        try:
            cleanup(uuid)
        except Exception as e:
            print(f"cleanup KO : {e}")
        return 0
    else:
        print("\nKO : aucun UUID dans la reponse (tools non utilises)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
