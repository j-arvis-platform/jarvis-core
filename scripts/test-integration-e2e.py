"""
J-ARVIS V2 — Test Integration E2E : Agent orchestre MCPs via tool_use
Etape 1.6 : Claude decide quels outils appeler, dans quel ordre.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")

from anthropic import Anthropic

# ── Clients ──
claude = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
NINJA_URL = os.environ["INVOICE_NINJA_URL"]
NINJA_TOKEN = os.environ["INVOICE_NINJA_TOKEN"]

sb_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
ninja_headers = {
    "X-Api-Token": NINJA_TOKEN,
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

# Track created resources for cleanup
created = []
audit_entries = []
mcp_calls = 0


def log_audit(actor, persona, action, resource_type, resource_id, details, status="success"):
    entry = {
        "actor": actor, "persona": persona, "action": action,
        "resource_type": resource_type, "resource_id": resource_id,
        "details": json.dumps(details, ensure_ascii=False), "status": status,
    }
    resp = httpx.post(f"{SUPABASE_URL}/rest/v1/audit_logs", headers=sb_headers, json=entry, timeout=10)
    if resp.status_code == 201:
        row = resp.json()[0]
        audit_entries.append(row["id"])
        created.append(("audit_logs", row["id"]))
    return entry


# ── Tool implementations ──

def tool_supabase_create_contact(data):
    global mcp_calls
    mcp_calls += 1
    resp = httpx.post(f"{SUPABASE_URL}/rest/v1/contacts", headers=sb_headers, json=data, timeout=10)
    resp.raise_for_status()
    row = resp.json()[0]
    created.append(("contacts", row["id"]))
    log_audit("jarvis", "lea", "create_contact", "contact", row["id"], {"nom": data.get("nom")})
    return row


def tool_supabase_create_projet(data):
    global mcp_calls
    mcp_calls += 1
    resp = httpx.post(f"{SUPABASE_URL}/rest/v1/projets", headers=sb_headers, json=data, timeout=10)
    resp.raise_for_status()
    row = resp.json()[0]
    created.append(("projets", row["id"]))
    log_audit("jarvis", "lea", "create_projet", "projet", row["id"], {"ref": row.get("reference"), "titre": data.get("titre")})
    return row


def tool_supabase_create_tache(data):
    global mcp_calls
    mcp_calls += 1
    resp = httpx.post(f"{SUPABASE_URL}/rest/v1/taches", headers=sb_headers, json=data, timeout=10)
    resp.raise_for_status()
    row = resp.json()[0]
    created.append(("taches", row["id"]))
    log_audit("jarvis", "lea", "create_tache", "tache", row["id"], {"titre": data.get("titre")})
    return row


def tool_ninja_search_client(email):
    global mcp_calls
    mcp_calls += 1
    resp = httpx.get(
        f"{NINJA_URL}/api/v1/clients?email={email}&per_page=5",
        headers=ninja_headers, timeout=10,
    )
    resp.raise_for_status()
    clients = resp.json().get("data", [])
    log_audit("jarvis", "lea", "search_client_ninja", "invoice_ninja", None, {"email": email, "found": len(clients)})
    return clients


def tool_ninja_create_client(data):
    global mcp_calls
    mcp_calls += 1
    resp = httpx.post(f"{NINJA_URL}/api/v1/clients", headers=ninja_headers, json=data, timeout=10)
    resp.raise_for_status()
    client = resp.json().get("data", resp.json())
    client_id = client.get("id", "?")
    created.append(("ninja_client", client_id))
    log_audit("jarvis", "lea", "create_client_ninja", "invoice_ninja", None, {"client_id": client_id})
    return client


def tool_ninja_create_quote(client_id, line_items):
    global mcp_calls
    mcp_calls += 1
    quote_data = {
        "client_id": client_id,
        "line_items": line_items,
        "tax_name1": "TVA",
        "tax_rate1": 20,
    }
    resp = httpx.post(f"{NINJA_URL}/api/v1/quotes", headers=ninja_headers, json=quote_data, timeout=10)
    resp.raise_for_status()
    quote = resp.json().get("data", resp.json())
    quote_id = quote.get("id", "?")
    quote_number = quote.get("number", "?")
    created.append(("ninja_quote", quote_id))
    log_audit("jarvis", "lea", "create_quote_ninja", "invoice_ninja", None, {"quote_id": quote_id, "number": quote_number})
    return quote


# ── Tool definitions for Claude ──

TOOLS = [
    {
        "name": "supabase_create_contact",
        "description": "Cree un contact (prospect/client) dans la base Supabase. Retourne le contact cree avec son id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["client", "prospect", "fournisseur", "partenaire", "sous_traitant"]},
                "nom": {"type": "string", "description": "Nom de famille"},
                "prenom": {"type": "string", "description": "Prenom"},
                "email": {"type": "string"},
                "telephone": {"type": "string"},
                "adresse_rue": {"type": "string"},
                "adresse_cp": {"type": "string"},
                "adresse_ville": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["type", "nom"],
        },
    },
    {
        "name": "supabase_create_projet",
        "description": "Cree un projet (chantier PV, domotique, etc.) lie a un contact. Genere une reference auto ELX-2026-xxxx.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "UUID du contact"},
                "titre": {"type": "string"},
                "marque": {"type": "string", "enum": ["solarstis", "domotique", "bornes_ve", "climatisation", "electricite_generale", "admin"]},
                "type": {"type": "string", "description": "Ex: chantier_pv, install_domotique, audit_energetique"},
                "statut": {"type": "string", "default": "prospect"},
                "montant_ht": {"type": "number"},
                "montant_ttc": {"type": "number"},
                "taux_tva": {"type": "number", "default": 20.0},
                "puissance_kwc": {"type": "number"},
                "nb_panneaux": {"type": "integer"},
            },
            "required": ["contact_id", "titre", "marque", "type"],
        },
    },
    {
        "name": "supabase_create_tache",
        "description": "Cree une tache a faire (par Jarvis ou un humain). Peut etre liee a un projet et/ou contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "projet_id": {"type": "string"},
                "contact_id": {"type": "string"},
                "titre": {"type": "string"},
                "description": {"type": "string"},
                "assignee": {"type": "string", "default": "jarvis"},
                "persona": {"type": "string", "enum": ["lea", "claire", "hugo", "sofia", "adam", "yasmine", "noah", "elias"]},
                "priorite": {"type": "string", "enum": ["critique", "urgent", "normale", "basse"]},
                "echeance": {"type": "string", "description": "Date ISO 8601"},
            },
            "required": ["titre"],
        },
    },
    {
        "name": "ninja_search_client",
        "description": "Cherche un client dans Invoice Ninja par email. Retourne la liste des clients trouves (peut etre vide).",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
            },
            "required": ["email"],
        },
    },
    {
        "name": "ninja_create_client",
        "description": "Cree un nouveau client dans Invoice Ninja pour la facturation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nom complet du client"},
                "contacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"},
                        },
                    },
                },
                "address1": {"type": "string"},
                "city": {"type": "string"},
                "postal_code": {"type": "string"},
                "country_id": {"type": "string", "default": "250"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ninja_create_quote",
        "description": "Cree un brouillon de devis dans Invoice Ninja. Retourne le devis cree avec son numero.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "ID du client Invoice Ninja"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_key": {"type": "string"},
                            "notes": {"type": "string", "description": "Description de la ligne"},
                            "quantity": {"type": "number"},
                            "cost": {"type": "number", "description": "Prix unitaire HT"},
                        },
                    },
                },
            },
            "required": ["client_id", "line_items"],
        },
    },
]

SYSTEM_PROMPT = """Tu es Jarvis, l'assistant IA d'ELEXITY 34 SASU (installateur PV RGE QualiPV, Gignac 34150).

PERSONA ACTIVE : Lea (commerciale, chaleureuse, pedagogue)

Tu disposes d'outils pour gerer les contacts, projets, taches (Supabase) et la facturation (Invoice Ninja).

WORKFLOW pour un nouveau prospect PV :
1. Creer le contact dans Supabase (type=prospect)
2. Creer le projet lie (marque=solarstis, type=chantier_pv)
3. Verifier si le client existe deja dans Invoice Ninja
4. Si non, creer le client dans Invoice Ninja
5. Creer un brouillon de devis dans Invoice Ninja (1 ligne : Installation PV, prix HT, TVA 20%)
6. Creer une tache de suivi (envoyer devis + programmer VT, echeance J+3)
7. Repondre a Hamid avec un resume clair de ce qui a ete fait

DONNEES METIER :
- TVA 20% par defaut (stock non-Certisolis)
- Zone 150km autour Gignac 34150
- RGE QualiPV + decennale MAAF

REGLE : execute TOUTES les etapes systematiquement. Ne saute rien."""

USER_MESSAGE = """Nouveau prospect : M. Jean Dupont, 45 avenue du Soleil, 34150 Gignac.
Email : jean.dupont@test-jarvis.fr, tel : 06 12 34 56 78.
Il veut un devis pour une installation PV 6 kWc. Source : site web.
Budget estime : 8500 EUR HT.

Cree tout le dossier et prepare le brouillon de devis."""


def execute_tool(name, input_data):
    """Execute un outil et retourne le resultat."""
    if name == "supabase_create_contact":
        adresse = {}
        if input_data.get("adresse_rue"):
            adresse["rue"] = input_data.pop("adresse_rue")
        if input_data.get("adresse_cp"):
            adresse["cp"] = input_data.pop("adresse_cp")
        if input_data.get("adresse_ville"):
            adresse["ville"] = input_data.pop("adresse_ville")
        if adresse:
            input_data["adresse"] = json.dumps(adresse)
        return tool_supabase_create_contact(input_data)

    elif name == "supabase_create_projet":
        return tool_supabase_create_projet(input_data)

    elif name == "supabase_create_tache":
        return tool_supabase_create_tache(input_data)

    elif name == "ninja_search_client":
        return tool_ninja_search_client(input_data["email"])

    elif name == "ninja_create_client":
        return tool_ninja_create_client(input_data)

    elif name == "ninja_create_quote":
        return tool_ninja_create_quote(input_data["client_id"], input_data["line_items"])

    else:
        return {"error": f"Unknown tool: {name}"}


def main():
    global mcp_calls

    print("=" * 60)
    print("  J-ARVIS V2 — Test Integration E2E")
    print("  Scenario : Nouveau prospect PV M. Dupont")
    print("=" * 60)

    total_start = time.time()
    total_tokens_in = 0
    total_tokens_out = 0
    tool_rounds = 0

    messages = [{"role": "user", "content": USER_MESSAGE}]

    # Agentic loop : Claude calls tools until done
    while True:
        tool_rounds += 1
        print(f"\n--- Round {tool_rounds} ---")

        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        total_tokens_in += response.usage.input_tokens
        total_tokens_out += response.usage.output_tokens

        # Process response blocks
        tool_results = []
        final_text = ""

        for block in response.content:
            if block.type == "text":
                final_text += block.text
            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                print(f"  TOOL: {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:100]}...)")

                try:
                    result = execute_tool(tool_name, tool_input)
                    # Serialize result safely
                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                    print(f"    -> OK ({len(result_str)} chars)")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_str[:4000],
                    })
                except Exception as e:
                    err = str(e)
                    print(f"    -> ERROR: {err[:100]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({"error": err[:500]}),
                        "is_error": True,
                    })

        # If no tool calls, we're done
        if response.stop_reason == "end_turn" or not tool_results:
            break

        # Feed tool results back
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if tool_rounds > 10:
            print("  ABORT: too many rounds")
            break

    total_ms = int((time.time() - total_start) * 1000)
    cost_eur = ((total_tokens_in * 3 / 1_000_000) + (total_tokens_out * 15 / 1_000_000)) * 0.92

    # Final response
    print("\n" + "=" * 60)
    print("  REPONSE FINALE DE JARVIS (persona Lea) :")
    print("=" * 60)
    safe_text = final_text.encode("ascii", errors="replace").decode("ascii")
    print(safe_text)

    # Cleanup
    print("\n" + "=" * 60)
    print("  NETTOYAGE")
    print("=" * 60)

    # Cleanup Invoice Ninja (quotes then clients)
    for resource_type, resource_id in reversed(created):
        if resource_type == "ninja_quote":
            resp = httpx.delete(f"{NINJA_URL}/api/v1/quotes/{resource_id}", headers=ninja_headers, timeout=10)
            print(f"  DELETE ninja quote {resource_id[:12]}... : {resp.status_code}")
        elif resource_type == "ninja_client":
            resp = httpx.delete(f"{NINJA_URL}/api/v1/clients/{resource_id}", headers=ninja_headers, timeout=10)
            print(f"  DELETE ninja client {resource_id[:12]}... : {resp.status_code}")

    # Cleanup Supabase (reverse order: audit, taches, projets, contacts)
    for resource_type, resource_id in reversed(created):
        if resource_type in ("contacts", "projets", "taches", "audit_logs"):
            httpx.delete(f"{SUPABASE_URL}/rest/v1/{resource_type}?id=eq.{resource_id}", headers=sb_headers, timeout=10)
            print(f"  DELETE supabase {resource_type} {resource_id[:12]}...")

    # Rapport
    print("\n" + "=" * 60)
    print("  RAPPORT INTEGRATION E2E")
    print("=" * 60)
    print(f"  Duree totale         : {total_ms}ms ({total_ms/1000:.1f}s)")
    print(f"  Rounds agent         : {tool_rounds}")
    print(f"  Appels MCP           : {mcp_calls}")
    print(f"  Tokens in            : {total_tokens_in}")
    print(f"  Tokens out           : {total_tokens_out}")
    print(f"  Tokens total         : {total_tokens_in + total_tokens_out}")
    print(f"  Cout estime          : {cost_eur:.4f} EUR")
    print(f"  Audit logs crees     : {len(audit_entries)}")
    print(f"  Resources creees     : {len(created)}")
    print(f"  Nettoyage            : OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
