"""
Tools Anthropic exposes a Jarvis V2.

Contient :
- TOOLS_SCHEMA : liste des tool definitions JSON (format Anthropic API)
- ToolExecutor : execute un tool call en appelant les APIs concernees

Pattern derive du test J1.6 (scripts/test-integration-e2e.py), packe
pour etre reutilise dans JarvisAgent.respond() et server.py.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


TOOLS_SCHEMA: list[dict[str, Any]] = [
    # ---------- Supabase ----------
    {
        "name": "supabase_create_contact",
        "description": (
            "Cree un contact (prospect / client / fournisseur) dans la BDD "
            "Supabase du tenant. Retourne le contact cree avec son UUID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string",
                         "enum": ["client", "prospect", "fournisseur",
                                  "partenaire", "sous_traitant"]},
                "nom": {"type": "string"},
                "prenom": {"type": "string"},
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
        "description": (
            "Cree un projet (chantier PV, install domotique, etc.) lie a un "
            "contact. Reference auto ELX-2026-xxxx cote BDD."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string"},
                "titre": {"type": "string"},
                "marque": {"type": "string",
                           "enum": ["solarstis", "domotique", "bornes_ve",
                                    "climatisation", "electricite_generale", "admin"]},
                "type": {"type": "string"},
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
        "description": (
            "Cree une tache (assignee humaine ou Jarvis). Peut etre liee a "
            "un projet et/ou contact. Echeance au format ISO 8601."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "projet_id": {"type": "string"},
                "contact_id": {"type": "string"},
                "titre": {"type": "string"},
                "description": {"type": "string"},
                "assignee": {"type": "string", "default": "jarvis"},
                "persona": {"type": "string",
                            "enum": ["lea", "claire", "hugo", "sofia",
                                     "adam", "yasmine", "noah", "elias"]},
                "priorite": {"type": "string",
                             "enum": ["critique", "urgent", "normale", "basse"]},
                "echeance": {"type": "string"},
            },
            "required": ["titre"],
        },
    },
    {
        "name": "supabase_query_table",
        "description": (
            "Recupere des lignes d'une table Supabase avec filtres "
            "clef=valeur simples. Table autorisee : contacts, projets, "
            "taches, file_humaine, audit_logs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string",
                          "enum": ["contacts", "projets", "taches",
                                   "file_humaine", "audit_logs"]},
                "filters": {"type": "object",
                            "description": "Couples clef=valeur (egalite stricte)"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["table"],
        },
    },
    # ---------- Invoice Ninja ----------
    {
        "name": "ninja_search_client",
        "description": "Cherche un client Invoice Ninja par email.",
        "input_schema": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    },
    {
        "name": "ninja_create_client",
        "description": "Cree un nouveau client Invoice Ninja pour facturation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
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
        "description": (
            "Cree un brouillon de devis Invoice Ninja pour un client. "
            "TVA par defaut 20 %. line_items = [{notes, quantity, cost}]."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "notes": {"type": "string"},
                            "quantity": {"type": "number"},
                            "cost": {"type": "number"},
                        },
                    },
                },
                "taux_tva": {"type": "number", "default": 20.0},
            },
            "required": ["client_id", "line_items"],
        },
    },
    # ---------- Communication canaux ----------
    {
        "name": "notify_admin_telegram",
        "description": (
            "Envoie un message Telegram a l'admin (Hamid). HTML supporte. "
            "Utiliser pour alertes operationnelles critiques."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


class ToolExecutor:
    """Execute les tools definis dans TOOLS_SCHEMA."""

    def __init__(self, env: dict | None = None):
        self.env = env or os.environ
        self.supabase_url = self.env["SUPABASE_URL"]
        self.supabase_key = self.env["SUPABASE_SERVICE_KEY"]
        self.ninja_url = self.env.get("INVOICE_NINJA_URL", "")
        self.ninja_token = self.env.get("INVOICE_NINJA_API_KEY", "")
        self.sb_headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.ninja_headers = {
            "X-Api-Token": self.ninja_token,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }

    def execute(self, name: str, input_data: dict) -> Any:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return handler(dict(input_data))
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = e.response.text[:400]
            except Exception:
                pass
            logger.error("tool_http_error name=%s status=%s body=%s",
                         name, e.response.status_code, body[:200])
            return {"error": f"HTTP {e.response.status_code}",
                    "detail": body}
        except Exception as e:
            logger.error("tool_error name=%s err=%s", name, e)
            return {"error": f"{type(e).__name__}: {e}"}

    # ---- Supabase tools ----

    def _tool_supabase_create_contact(self, data: dict) -> dict:
        adresse = {}
        for k_src, k_dst in (
            ("adresse_rue", "rue"),
            ("adresse_cp", "cp"),
            ("adresse_ville", "ville"),
        ):
            if data.get(k_src):
                adresse[k_dst] = data.pop(k_src)
        if adresse:
            data["adresse"] = adresse  # Supabase JSONB accepte dict direct
        resp = httpx.post(f"{self.supabase_url}/rest/v1/contacts",
                          headers=self.sb_headers, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()[0]

    def _tool_supabase_create_projet(self, data: dict) -> dict:
        resp = httpx.post(f"{self.supabase_url}/rest/v1/projets",
                          headers=self.sb_headers, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()[0]

    def _tool_supabase_create_tache(self, data: dict) -> dict:
        resp = httpx.post(f"{self.supabase_url}/rest/v1/taches",
                          headers=self.sb_headers, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()[0]

    def _tool_supabase_query_table(self, data: dict) -> list:
        table = data["table"]
        params = []
        for k, v in (data.get("filters") or {}).items():
            params.append((k, f"eq.{v}"))
        params.append(("limit", str(data.get("limit", 20))))
        resp = httpx.get(f"{self.supabase_url}/rest/v1/{table}",
                         headers=self.sb_headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ---- Invoice Ninja tools ----

    def _tool_ninja_search_client(self, data: dict) -> list:
        email = data["email"]
        resp = httpx.get(
            f"{self.ninja_url}/api/v1/clients?email={email}&per_page=5",
            headers=self.ninja_headers, timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    def _tool_ninja_create_client(self, data: dict) -> dict:
        resp = httpx.post(f"{self.ninja_url}/api/v1/clients",
                          headers=self.ninja_headers, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", resp.json())

    def _tool_ninja_create_quote(self, data: dict) -> dict:
        taux = data.pop("taux_tva", 20.0)
        quote = {
            "client_id": data["client_id"],
            "line_items": data["line_items"],
            "tax_name1": "TVA",
            "tax_rate1": taux,
        }
        resp = httpx.post(f"{self.ninja_url}/api/v1/quotes",
                          headers=self.ninja_headers, json=quote, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", resp.json())

    # ---- Canaux ----

    def _tool_notify_admin_telegram(self, data: dict) -> dict:
        # Import local pour eviter dependance au demarrage si non utilise
        import asyncio

        from agent.integrations.telegram import build_from_env
        try:
            bot = build_from_env(self.env)
            return asyncio.run(bot.send_message(data["text"]))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
