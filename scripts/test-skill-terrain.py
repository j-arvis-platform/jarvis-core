"""Test skill elexity-terrain-pv — Jarvis V2 J3.2.

Valide sur 3 prompts metier :
1. TVA 6 kWc DMEGC sans EMS       -> doit repondre 20 % + 3 conditions
2. Procedure raccordement 9 kWc   -> doit lister DP / Enedis / Consuel / EDF OA
3. Gain client 6 kWc autoconso    -> doit citer prime autoconso + surplus
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
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

TENANT_ENV = ROOT.parent / "tenant-configs" / "tenant-elexity34" / ".env"
load_dotenv(TENANT_ENV)

from agent.core.skills import (  # noqa: E402
    discover_skills, match_skills, inject_into_system_prompt,
)
from agent.handlers.main import JarvisAgent  # noqa: E402


MODULES_ROOT = ROOT.parent / "modules"

CASES = [
    {
        "name": "TVA 6kWc DMEGC sans EMS",
        "prompt": "Quel est le taux TVA pour 6 kWc DMEGC sans EMS ?",
        "must_match_skill": "elexity-terrain-pv",
        "must_contain_patterns": [
            (r"20\s*%", "mention TVA 20 %"),
            (r"3\s*conditions|trois\s*conditions", "mention des 3 conditions"),
            (r"Certisolis|PPE2-V2", "mention Certisolis"),
        ],
    },
    {
        "name": "Procedure raccordement 9 kWc",
        "prompt": "Procedure complete pour raccorder une installation 9 kWc a Gignac ?",
        "must_match_skill": "elexity-terrain-pv",
        "must_contain_patterns": [
            (r"DP\s*mairie|d[ée]claration\s*pr[ée]alable", "etape DP mairie"),
            (r"Enedis", "etape Enedis"),
            (r"Consuel", "etape Consuel"),
            (r"EDF\s*OA", "etape EDF OA"),
        ],
    },
    {
        "name": "Gain client 6 kWc autoconso",
        "prompt": "Combien gagne un client avec une installation 6 kWc autoconso partielle ?",
        "must_match_skill": "elexity-terrain-pv",
        "must_contain_patterns": [
            (r"prime\s*autoconsommation|80\s*(EUR|€)/kWc", "prime autoconso"),
            (r"0[,.]04\s*(EUR|€)", "tarif EDF OA 0,04 EUR/kWh"),
            (r"autoconso|autoconsommation", "mention autoconso"),
        ],
    },
]


def run_case(case: dict, skills: list, jarvis: JarvisAgent) -> tuple[bool, str]:
    prompt = case["prompt"]
    print(f"\n=== {case['name']} ===")
    print(f"Prompt : {prompt!r}")

    matched = match_skills(prompt, skills)
    matched_names = [s.name for s in matched]
    print(f"Skills matches : {matched_names}")
    if case["must_match_skill"] not in matched_names:
        return False, f"skill {case['must_match_skill']} non matche"

    # reinjecte system prompt + reset conv pour isoler chaque test
    jarvis.reset_conversation()
    jarvis.system_prompt = inject_into_system_prompt(
        JarvisAgent(jarvis.tenant_id).system_prompt, matched
    )
    reply = jarvis.respond(prompt)
    print("--- reponse ---")
    print(reply[:1500])
    print("--- fin ---")

    missing = []
    for pat, label in case["must_contain_patterns"]:
        if not re.search(pat, reply, flags=re.I):
            missing.append(label)
    if missing:
        return False, f"manquant : {missing}"
    return True, "OK"


def main() -> int:
    skills = discover_skills(MODULES_ROOT)
    print(f"Skills decouverts : {[s.name for s in skills]}\n")
    tenant_id = os.environ.get("JARVIS_TENANT_ID", "elexity34")
    jarvis = JarvisAgent(tenant_id=tenant_id)

    results = []
    for case in CASES:
        ok, detail = run_case(case, skills, jarvis)
        results.append((case["name"], ok, detail))

    print("\n============ BILAN ============")
    ok_count = 0
    for name, ok, detail in results:
        status = "OK " if ok else "KO"
        print(f"  [{status}] {name} - {detail}")
        if ok:
            ok_count += 1
    print(f"\n{ok_count}/{len(CASES)} cas passes.")
    return 0 if ok_count == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
