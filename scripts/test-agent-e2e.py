"""
J-ARVIS V2 — Test E2E : Agent + Supabase + Claude API
Etape 1.4 du build plan
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import httpx
from anthropic import Anthropic

# Config
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

supabase_headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

claude = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Tu es Jarvis, l'assistant IA d'ELEXITY 34 SASU, installateur photovoltaique RGE QualiPV a Gignac (34150).

PERSONA ACTIVE : Lea (commerciale)
Style : chaleureuse, pedagogue, rassurante. Tu tutoies jamais le client. Vous de rigueur.

DONNEES ENTREPRISE :
- ELEXITY 34 SASU, SIRET 94006873700011
- RGE QualiPV + decennale MAAF
- Zone : 150km autour de Gignac 34150
- Panneaux : DMEGC 405W/500W, DualSun 500W, Trina Solar 500W
- Onduleurs : Huawei, APsystems, Enphase, Hoymiles, SolarEdge
- EDF OA 2026 : 0.04 EUR/kWh surplus, prime autoconso ~80 EUR/kWc sur 5 ans
- TVA 20% par defaut (stock non-Certisolis), 5.5% si 3 conditions

REGLES :
1. Tu ES Jarvis, pas Lea. Lea est ton style commercial.
2. Ne fabrique jamais de chiffres. Utilise les donnees ci-dessus.
3. Propose toujours un RDV visite technique.
4. Sois concis mais complet.
"""

def supabase_post(table, data):
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers,
        json=data,
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()[0]

def supabase_delete(table, row_id):
    httpx.delete(
        f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
        headers=supabase_headers,
        timeout=10.0,
    )

def main():
    print("=" * 60)
    print("  J-ARVIS V2 - Test E2E Agent")
    print("=" * 60)

    created_ids = {}
    total_start = time.time()

    # 1. Connexion Supabase
    print("\n[1/7] Test connexion Supabase...")
    try:
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/contacts?select=id&limit=0",
            headers=supabase_headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        print("  -> Supabase : OK")
    except Exception as e:
        print(f"  -> Supabase : ERREUR - {e}")
        sys.exit(1)

    # 2. Creer contact test
    print("\n[2/7] Creation contact test...")
    contact = supabase_post("contacts", {
        "type": "prospect",
        "nom": "Dupont",
        "prenom": "Jean",
        "email": "jean.dupont@test.fr",
        "telephone": "0612345678",
        "adresse": json.dumps({
            "rue": "45 avenue du Soleil",
            "cp": "34150",
            "ville": "Gignac",
        }),
        "source": "site_web",
        "score_prospect": 60,
    })
    created_ids["contacts"] = contact["id"]
    print(f"  -> Contact cree : {contact['nom']} {contact['prenom']} (id={contact['id'][:8]}...)")

    # 3. Creer projet lie
    print("\n[3/7] Creation projet PV...")
    projet = supabase_post("projets", {
        "contact_id": contact["id"],
        "titre": "Installation PV 6kWc - Dupont Gignac",
        "marque": "solarstis",
        "type": "chantier_pv",
        "statut": "prospect",
        "montant_ht": 8500.00,
        "montant_ttc": 10200.00,
        "taux_tva": 20.00,
        "puissance_kwc": 6.0,
        "nb_panneaux": 12,
    })
    created_ids["projets"] = projet["id"]
    print(f"  -> Projet cree : ref={projet['reference']}, 6kWc, 8500 EUR HT")

    # 4. Appel Claude API avec persona Lea
    print("\n[4/7] Appel Claude API (persona Lea)...")
    user_message = (
        "M. Jean Dupont de Gignac demande un devis pour une installation "
        "photovoltaique 6 kWc sur sa maison. Il a vu notre site web. "
        "Prepare une reponse courte et chaleureuse, propose un RDV visite technique."
    )

    api_start = time.time()
    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    api_duration_ms = int((time.time() - api_start) * 1000)

    reply = response.content[0].text
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens

    # Cost estimate (Sonnet 4.6 pricing: $3/Mtok in, $15/Mtok out)
    cost_eur = ((tokens_in * 3 / 1_000_000) + (tokens_out * 15 / 1_000_000)) * 0.92

    print(f"  -> Modele : claude-sonnet-4-6")
    print(f"  -> Tokens : {tokens_in} in / {tokens_out} out")
    print(f"  -> Latence API : {api_duration_ms}ms")
    print(f"  -> Cout estime : {cost_eur:.4f} EUR")

    # 5. Sauver dans audit_logs
    print("\n[5/7] Sauvegarde audit_log...")
    audit = supabase_post("audit_logs", {
        "actor": "jarvis",
        "persona": "lea",
        "action": "generate_response",
        "resource_type": "projet",
        "resource_id": projet["id"],
        "details": json.dumps({
            "model": "claude-sonnet-4-6",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": api_duration_ms,
            "cost_eur": round(cost_eur, 4),
            "prompt_preview": user_message[:100],
        }),
        "status": "success",
    })
    created_ids["audit_logs"] = audit["id"]
    print(f"  -> Audit log cree (id={audit['id'][:8]}...)")

    # 6. Afficher la reponse de Lea
    print("\n[6/7] Reponse generee par Jarvis (persona Lea) :")
    print("-" * 60)
    print(reply.encode("ascii", errors="replace").decode("ascii"))
    print("-" * 60)

    # 7. Nettoyage
    print("\n[7/7] Nettoyage donnees test...")
    for table in ["audit_logs", "projets", "contacts"]:
        if table in created_ids:
            supabase_delete(table, created_ids[table])
            print(f"  -> {table} supprime")

    total_ms = int((time.time() - total_start) * 1000)

    # Rapport final
    print("\n" + "=" * 60)
    print("  RAPPORT TEST E2E")
    print("=" * 60)
    print(f"  Connexion Supabase     : OK")
    print(f"  Contact cree           : OK (Dupont Jean)")
    print(f"  Projet cree            : OK (ref={projet['reference']})")
    print(f"  Claude API persona Lea : OK")
    print(f"  Audit log              : OK")
    print(f"  Nettoyage              : OK")
    print(f"  ---")
    print(f"  Modele                 : claude-sonnet-4-6")
    print(f"  Tokens                 : {tokens_in} in / {tokens_out} out")
    print(f"  Latence API Claude     : {api_duration_ms}ms")
    print(f"  Latence totale E2E     : {total_ms}ms")
    print(f"  Cout estime            : {cost_eur:.4f} EUR")
    print("=" * 60)


if __name__ == "__main__":
    main()
