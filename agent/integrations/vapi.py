"""
Vapi voice API wrapper pour J-ARVIS V2.

Vapi orchestre :
- LLM (Claude Haiku 4.5 pour Axel, via provider anthropic)
- Voice synthese (Cartesia pour Axel)
- Transport telephonie (Twilio / Telnyx / WebRTC Vapi natif)

Repere assistant ELEXITY 34 :
- Axel : qualification leads solaire, prise RDV, SAV premier niveau
- Zone intervention : 150 km autour Gignac 34150
- Jamais de prix, toujours proposer etude gratuite
- Hors zone : refuser poliment, pas de callback promise
- SAV : creer ticket + callback humain (pas de RDV auto)

Cout appel :
- Vapi + Twilio FR : env. 0,08-0,12 EUR/min (LLM + TTS + STT + telephonie)
- Latence objectif : < 1 sec (sinon la conversation casse)
- Timeout silence client : 30 sec par defaut

Cohabitation V1/V2 :
- V2 = API client (CRUD assistants, appels sortants) autorise
- V2 webhook inbound = DESACTIVE tant que V1 ecoute les appels
  entrants sur +33939245020 / +33412120708 (cf docs/TELEGRAM-V1-V2-STRATEGY.md)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VAPI_API_BASE = "https://api.vapi.ai"
DEFAULT_TIMEOUT = 20.0


@dataclass
class VapiClient:
    api_key: str
    timeout: float = DEFAULT_TIMEOUT

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{VAPI_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{VAPI_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers, json=payload)
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            logger.error(
                "vapi_api_error status=%d body=%r",
                resp.status_code, str(body)[:300],
            )
            raise VapiError(
                f"HTTP {resp.status_code} — {str(body)[:200]}", body,
            )
        return resp.json()

    async def _patch(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{VAPI_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(url, headers=self._headers, json=payload)
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            logger.error(
                "vapi_api_error status=%d body=%r",
                resp.status_code, str(body)[:300],
            )
            raise VapiError(
                f"HTTP {resp.status_code} — {str(body)[:200]}", body,
            )
        return resp.json()

    async def list_assistants(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self._get("/assistant", params={"limit": limit})

    async def get_assistant(self, assistant_id: str) -> dict[str, Any]:
        return await self._get(f"/assistant/{assistant_id}")

    async def update_assistant(self, assistant_id: str,
                               updates: dict[str, Any]) -> dict[str, Any]:
        """Met a jour un assistant (prompt, voice, model, firstMessage...)."""
        logger.info("vapi_update_assistant id=%s keys=%s",
                    assistant_id, list(updates.keys()))
        return await self._patch(f"/assistant/{assistant_id}", updates)

    async def list_phone_numbers(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self._get("/phone-number", params={"limit": limit})

    async def create_outbound_call(self, assistant_id: str,
                                   customer_number: str,
                                   phone_number_id: str | None = None,
                                   metadata: dict[str, Any] | None = None,
                                   ) -> dict[str, Any]:
        """Initie un appel sortant : l'assistant Vapi appelle un numero.

        customer_number : format E.164 (+33612345678).
        phone_number_id : id du numero emetteur cote Vapi (Twilio/Telnyx).
          Si None, Vapi choisit le premier numero lie a l'assistant.
        """
        if not customer_number.startswith("+"):
            raise ValueError(f"customer_number non E.164 : {customer_number!r}")

        payload: dict[str, Any] = {
            "assistantId": assistant_id,
            "customer": {"number": customer_number},
        }
        if phone_number_id:
            payload["phoneNumberId"] = phone_number_id
        if metadata:
            payload.setdefault("assistantOverrides", {})["metadata"] = metadata

        logger.info(
            "vapi_outbound_call assistant=%s to=%s phone_number_id=%s",
            assistant_id, customer_number, phone_number_id,
        )
        return await self._post("/call", payload)

    async def get_call(self, call_id: str) -> dict[str, Any]:
        return await self._get(f"/call/{call_id}")

    async def list_calls(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._get("/call", params={"limit": limit})

    async def get_call_transcript(self, call_id: str) -> str | None:
        """Recupere le transcript complet d'un appel termine."""
        call = await self.get_call(call_id)
        return call.get("transcript") or call.get("artifact", {}).get("transcript")


class VapiError(RuntimeError):
    def __init__(self, message: str, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {}


def build_from_env(env: dict[str, str] | None = None) -> VapiClient:
    import os
    env = env or os.environ
    return VapiClient(api_key=env["VAPI_API_KEY"])
