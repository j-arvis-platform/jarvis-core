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
            "A utiliser pour alertes operationnelles critiques uniquement."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "send_sms_twilio",
        "description": (
            "Envoie un SMS via Twilio a un numero E.164 (+33XXXXXXXXX). "
            "Canal PREMIUM (cout ~0,075 EUR/SMS). Anti-spam : 1 SMS max "
            "par numero par 24h sauf 'urgence'=true. Body max 160 chars "
            "(au-dela, split automatique facture en plusieurs SMS)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_number": {"type": "string"},
                "body": {"type": "string"},
                "urgence": {"type": "boolean", "default": False},
            },
            "required": ["to_number", "body"],
        },
    },
    {
        "name": "send_email_gmail",
        "description": (
            "Envoie un email transactionnel via Gmail Workspace SMTP. "
            "Expediteur : contact@elexity34.fr automatiquement. "
            "Anti-spam : 1 email max par destinataire par 24h. "
            "Toujours fournir un body_html ; body_text est un fallback "
            "pour clients mail sans HTML."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body_html": {"type": "string"},
                "body_text": {"type": "string"},
                "cc": {"type": "string"},
            },
            "required": ["to", "subject", "body_html"],
        },
    },
    {
        "name": "send_whatsapp_message",
        "description": (
            "Envoie un message WhatsApp texte libre a un client. REQUIERT "
            "une fenetre 24h conversationnelle ouverte (le client doit "
            "avoir ecrit dans les 24 dernieres heures). Hors fenetre : "
            "utiliser send_whatsapp_template a la place. Si l'API renvoie "
            "une erreur fenetre 24h, signale-le honnetement a l'utilisateur."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_number": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to_number", "body"],
        },
    },
    {
        "name": "send_whatsapp_template",
        "description": (
            "Envoie un message WhatsApp via un template pre-approuve par "
            "Meta. A utiliser hors fenetre 24h ou pour notifications "
            "proactives. Le template doit exister dans Meta Business Suite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_number": {"type": "string"},
                "template_name": {"type": "string"},
                "language": {"type": "string", "default": "fr"},
            },
            "required": ["to_number", "template_name"],
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

    # ---- Canaux (sync pur — pas d'asyncio.run pour eviter conflit
    #      avec l'event loop FastAPI quand respond() est appele depuis
    #      un handler async). Les wrappers async dans agent/integrations/
    #      restent utilisables ailleurs.

    def _tool_notify_admin_telegram(self, data: dict) -> dict:
        token = self.env["TELEGRAM_BOT_TOKEN_JARVIS"]
        chat_id = self.env["TELEGRAM_CHAT_ID_ADMIN"]
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": data["text"],
                  "parse_mode": "HTML"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok"):
            return {"error": payload.get("description", "telegram_failed")}
        return {"message_id": payload["result"]["message_id"]}

    def _tool_send_sms_twilio(self, data: dict) -> dict:
        sid = self.env["TWILIO_ACCOUNT_SID"]
        token = self.env["TWILIO_AUTH_TOKEN"]
        from_number = self.env["TWILIO_FROM_NUMBER"]
        body = data["body"]
        if len(body) > 160:
            logger.warning("sms body=%d chars (>160, will split)", len(body))
        resp = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": data["to_number"], "From": from_number, "Body": body},
            auth=(sid, token),
            timeout=20,
        )
        if resp.status_code >= 400:
            err = resp.json() if resp.content else {}
            return {"error": f"HTTP {resp.status_code}",
                    "detail": err.get("message")}
        body_resp = resp.json()
        return {"sid": body_resp.get("sid"),
                "status": body_resp.get("status"),
                "num_segments": body_resp.get("num_segments")}

    def _tool_send_email_gmail(self, data: dict) -> dict:
        import smtplib
        import ssl
        from email.message import EmailMessage
        from email.utils import formataddr, make_msgid

        host = self.env.get("SMTP_HOST", "smtp.gmail.com")
        port = int(self.env.get("SMTP_PORT", "587"))
        user = self.env["SMTP_USER"]
        password = self.env["SMTP_PASSWORD"]
        from_name = self.env.get("SMTP_FROM_NAME", "ELEXITY 34")
        from_email = self.env.get("SMTP_FROM_EMAIL", user)

        msg = EmailMessage()
        msg["From"] = formataddr((from_name, from_email))
        msg["To"] = data["to"]
        msg["Subject"] = data["subject"]
        msg["Message-ID"] = make_msgid(domain=from_email.split("@", 1)[-1])
        if data.get("cc"):
            msg["Cc"] = data["cc"]
        body_text = data.get("body_text") or "Votre client mail ne supporte pas le HTML."
        msg.set_content(body_text)
        msg.add_alternative(data["body_html"], subtype="html")

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(msg)

        return {"message_id": msg["Message-ID"], "to": data["to"]}

    def _tool_send_whatsapp_message(self, data: dict) -> dict:
        token = self.env["WHATSAPP_ACCESS_TOKEN"]
        phone_id = self.env["WHATSAPP_PHONE_NUMBER_ID"]
        version = self.env.get("WHATSAPP_API_VERSION", "v21.0")

        normalized = data["to_number"].lstrip("+").replace(" ", "").replace("-", "")
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized,
            "type": "text",
            "text": {"preview_url": False, "body": data["body"]},
        }
        resp = httpx.post(
            f"https://graph.facebook.com/{version}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json=payload, timeout=20,
        )
        if resp.status_code >= 400:
            body_err = resp.json() if resp.content else {}
            err = body_err.get("error", {})
            return {"error": err.get("message", f"HTTP {resp.status_code}"),
                    "code": err.get("code"),
                    "hint": ("Fenetre 24h fermee : utiliser un template "
                             "(send_whatsapp_template)") if err.get("code") in (131047, 131051) else None}
        msgs = resp.json().get("messages") or []
        return {"wamid": msgs[0]["id"] if msgs else None}

    def _tool_send_whatsapp_template(self, data: dict) -> dict:
        token = self.env["WHATSAPP_ACCESS_TOKEN"]
        phone_id = self.env["WHATSAPP_PHONE_NUMBER_ID"]
        version = self.env.get("WHATSAPP_API_VERSION", "v21.0")

        normalized = data["to_number"].lstrip("+").replace(" ", "").replace("-", "")
        payload = {
            "messaging_product": "whatsapp",
            "to": normalized,
            "type": "template",
            "template": {
                "name": data["template_name"],
                "language": {"code": data.get("language", "fr")},
            },
        }
        resp = httpx.post(
            f"https://graph.facebook.com/{version}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json=payload, timeout=20,
        )
        if resp.status_code >= 400:
            body_err = resp.json() if resp.content else {}
            err = body_err.get("error", {})
            return {"error": err.get("message", f"HTTP {resp.status_code}"),
                    "code": err.get("code")}
        msgs = resp.json().get("messages") or []
        return {"wamid": msgs[0]["id"] if msgs else None}
