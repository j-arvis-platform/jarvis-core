"""
WhatsApp Business Cloud API wrapper pour J-ARVIS V2.

Un seul numero Business par tenant (ex. Elexity 34 : +33 7 83 90 90 63
phone_number_id 289084227628955). Ce numero sert a TOUTES les marques
du tenant (ELEXITY PV, Solarstis domo, bornes, clim, elec...).

Regles WhatsApp Business (Meta) — a respecter scrupuleusement :

1. Fenetre 24h conversationnelle :
   - Apres qu'un client a envoye un message au Business, le Business
     peut repondre en message texte LIBRE pendant 24h.
   - Au-dela des 24h : seul l'envoi de message TEMPLATE pre-approuve
     par Meta est autorise.

2. Templates :
   - Crees et approuves dans Meta Business Suite (pas via cette API).
   - Categories : MARKETING (promo), UTILITY (transactionnel),
     AUTHENTICATION (OTP). Les regles de tarification different.
   - Variables {{1}}, {{2}}... dans le texte du template remplies
     via le champ `components` a l'envoi.

3. Anti-spam strict :
   - Regle interne (portee de V1) : 1 message PROACTIF max par
     client par 24h. A cabler via Supabase `rate_limit_whatsapp`
     post go-live.
   - Sanctions Meta en cas d'abus : quality rating baisse
     (GREEN -> YELLOW -> RED), puis palier de messaging limit
     abaisse, puis suspension.

4. Reception webhook :
   - Desactivee en V2 tant que V1 ecoute les messages entrants
     (cf. docs/TELEGRAM-V1-V2-STRATEGY.md — meme logique Meta).
   - V2 expose uniquement l'envoi pour l'instant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com"
DEFAULT_TIMEOUT = 15.0
DEFAULT_API_VERSION = "v21.0"


@dataclass
class WhatsAppClient:
    access_token: str
    phone_number_id: str
    api_version: str = DEFAULT_API_VERSION
    timeout: float = DEFAULT_TIMEOUT

    @property
    def _base_url(self) -> str:
        return f"{GRAPH_API_BASE}/{self.api_version}/{self.phone_number_id}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers, json=payload)
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            err = body.get("error", {})
            logger.error(
                "whatsapp_api_error status=%d code=%s type=%s message=%r",
                resp.status_code, err.get("code"), err.get("type"),
                (err.get("message") or "")[:200],
            )
            raise WhatsAppError(err.get("message", f"HTTP {resp.status_code}"), body)
        return resp.json()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _normalize_number(n: str) -> str:
        """Format Meta : chiffres uniquement, avec indicatif pays (pas de '+')."""
        cleaned = n.strip().replace(" ", "").replace("-", "")
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        if cleaned.startswith("00"):
            cleaned = cleaned[2:]
        if not cleaned.isdigit():
            raise ValueError(f"Numero invalide : {n!r}")
        return cleaned

    async def send_text_message(self, to_number: str, body: str,
                                preview_url: bool = False) -> dict[str, Any]:
        """Envoie un message texte libre.

        ATTENTION : requiert fenetre 24h conversationnelle ouverte.
        Hors fenetre : utiliser send_template_message.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._normalize_number(to_number),
            "type": "text",
            "text": {"preview_url": preview_url, "body": body},
        }
        logger.info(
            "whatsapp_send type=text from=%s to=%s len=%d",
            self.phone_number_id, to_number, len(body),
        )
        return await self._post("/messages", payload)

    async def send_template_message(self, to_number: str, template_name: str,
                                    language_code: str = "fr",
                                    components: list[dict] | None = None,
                                    ) -> dict[str, Any]:
        """Envoie un message template pre-approuve par Meta.

        Utiliser hors fenetre 24h ou pour notifications proactives.
        Template doit etre CREE et APPROUVE dans Meta Business Suite.
        """
        template: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "to": self._normalize_number(to_number),
            "type": "template",
            "template": template,
        }
        logger.info(
            "whatsapp_send type=template name=%s lang=%s to=%s",
            template_name, language_code, to_number,
        )
        return await self._post("/messages", payload)

    async def send_media_message(self, to_number: str, media_type: str,
                                 media_url_or_id: str, caption: str | None = None,
                                 filename: str | None = None) -> dict[str, Any]:
        """Envoie image/document/video/audio.

        media_type : 'image' | 'document' | 'video' | 'audio'
        media_url_or_id : URL publique ou media_id prealablement uploade.
        """
        if media_type not in {"image", "document", "video", "audio"}:
            raise ValueError(f"media_type invalide : {media_type!r}")

        media_obj: dict[str, Any] = {}
        if media_url_or_id.startswith("http"):
            media_obj["link"] = media_url_or_id
        else:
            media_obj["id"] = media_url_or_id
        if caption and media_type in {"image", "document", "video"}:
            media_obj["caption"] = caption
        if filename and media_type == "document":
            media_obj["filename"] = filename

        payload = {
            "messaging_product": "whatsapp",
            "to": self._normalize_number(to_number),
            "type": media_type,
            media_type: media_obj,
        }
        logger.info(
            "whatsapp_send type=%s to=%s", media_type, to_number,
        )
        return await self._post("/messages", payload)

    async def get_phone_info(self) -> dict[str, Any]:
        """Metadonnees du numero Business (display, quality, tier...)."""
        return await self._get("", params={
            "fields": "verified_name,display_phone_number,quality_rating,"
                      "code_verification_status,messaging_limit_tier",
        })


class WhatsAppError(RuntimeError):
    def __init__(self, message: str, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {}


def build_from_env(env: dict[str, str] | None = None) -> WhatsAppClient:
    import os
    env = env or os.environ
    return WhatsAppClient(
        access_token=env["WHATSAPP_ACCESS_TOKEN"],
        phone_number_id=env["WHATSAPP_PHONE_NUMBER_ID"],
        api_version=env.get("WHATSAPP_API_VERSION", DEFAULT_API_VERSION),
    )
