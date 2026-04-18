"""Test skill elexity-commercial — Jarvis V2 J3.1.

Valide :
1. Le loader trouve bien le skill et parse le frontmatter.
2. Les triggers matchent un prompt prospect realiste.
3. Jarvis injecte le skill dans son system prompt et repond
   conformement aux regles metier (presentation Lea, validation
   zone, aucun prix, proposition VT).
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

# Windows cp1252 console kills emojis -> force UTF-8 avec replace sur stdout
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.core.skills import (  # noqa: E402
    discover_skills, match_skills, inject_into_system_prompt,
)
from agent.handlers.main import JarvisAgent  # noqa: E402


MODULES_ROOT = ROOT.parent / "modules"

CHECKS = [
    ("presentation Lea",    r"L[ée]a"),
    ("mention ELEXITY",     r"ELEXITY\s*34"),
    ("zone intervention",   r"150\s*km|Gignac|zone"),
    ("proposition VT",      r"visite\s+technique|VT\b|sur\s*place"),
    ("pas de prix ferme",   r"^(?!.*\b(\d{3,}\s*(EUR|€|euros)|\d+\s*€/kWc)).*$"),
]


def main() -> int:
    print("=== 1) Decouverte des skills ===")
    skills = discover_skills(MODULES_ROOT)
    for s in skills:
        print(f"  - {s.name} triggers={s.triggers} body={len(s.body)} chars")
    if not skills:
        print("ERREUR : aucun skill trouve.", file=sys.stderr)
        return 1

    prompt = "M. Dupont demande un devis 6 kWc photovoltaique a Montpellier"
    print(f"\n=== 2) Matching triggers pour prompt : {prompt!r} ===")
    matched = match_skills(prompt, skills)
    for s in matched:
        print(f"  matche : {s.name}")
    if not any(s.name == "elexity-commercial" for s in matched):
        print("ERREUR : elexity-commercial ne matche pas le prompt.", file=sys.stderr)
        return 1

    print("\n=== 3) Jarvis repond avec skill injecte ===")
    tenant_id = os.environ.get("JARVIS_TENANT_ID", "elexity34")
    jarvis = JarvisAgent(tenant_id=tenant_id)
    jarvis.system_prompt = inject_into_system_prompt(
        jarvis.system_prompt, matched
    )
    reply = jarvis.respond(prompt)

    print("\n--- Reponse Jarvis ---")
    print(reply)
    print("--- fin reponse ---\n")

    print("=== 4) Verification des regles metier ===")
    passed = 0
    failed: list[str] = []
    for label, pattern in CHECKS:
        if label == "pas de prix ferme":
            # verifie que la reponse n'inclut PAS un prix ferme
            bad = re.search(r"\b(\d{3,}\s*(EUR|€|euros))", reply, flags=re.I)
            if bad:
                failed.append(f"{label} : trouve {bad.group(0)!r}")
            else:
                passed += 1
                print(f"  OK  - {label}")
        elif re.search(pattern, reply, flags=re.I):
            passed += 1
            print(f"  OK  - {label}")
        else:
            failed.append(label)
            print(f"  KO  - {label}")

    print(f"\nRESULTAT : {passed}/{len(CHECKS)} verifications passees.")
    if failed:
        print("Echecs :", failed, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
