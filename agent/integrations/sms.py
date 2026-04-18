"""
Twilio SMS wrapper pour J-ARVIS V2.

Canal premium : utilisation parcimonieuse.
Budget cible : 50 SMS/mois max (~3,75 EUR/mois).

V1 anti-spam rule carried over: max 1 SMS par numero par 24h
(sauf flag urgence). A implementer via table Supabase
`rate_limit_sms` post go-live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"
DEFAULT_TIMEOUT = 15.0
SMS_SEGMENT_GSM7 = 160
SMS_SEGMENT_UCS2 = 70


@dataclass
class TwilioSMSClient:
    """Wrapper async autour de l'API Twilio Messages (REST).

    L'API Twilio est synchrone mais on l'expose en async via httpx.AsyncClient
    pour s'aligner sur telegram/email et preparer un futur passage en webhook.
    """

    account_sid: str
    auth_token: str
    from_number: str
    timeout: float = DEFAULT_TIMEOUT

    @property
    def _auth(self) -> tuple[str, str]:
        return (self.account_sid, self.auth_token)

    @property
    def _account_url(self) -> str:
        return f"{TWILIO_API_BASE}/Accounts/{self.account_sid}"

    async def _get(self, path: str) -> dict[str, Any]:
        url = f"{self._account_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, auth=self._auth)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._account_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, data=data, auth=self._auth)
        if resp.status_code >= 400:
            payload = resp.json() if resp.content else {}
            logger.error(
                "twilio_api_error status=%d code=%s message=%s",
                resp.status_code, payload.get("code"), payload.get("message"),
            )
            raise TwilioSMSError(
                payload.get("message", f"HTTP {resp.status_code}"), payload,
            )
        return resp.json()

    async def send_sms(self, to_number: str, body: str,
                       urgence: bool = False) -> dict[str, Any]:
        """Envoie un SMS.

        to_number : format E.164 (+33612345678).
        body : UTF-8, split automatique par Twilio si > 160 car (GSM-7) ou
               > 70 car (UCS-2 pour accents/emoji).
        urgence : si True, bypasse le flag anti-spam (a cabler post go-live).
        """
        if not to_number.startswith("+"):
            raise ValueError(f"Numero non E.164 : {to_number!r}")

        segments = self._estimate_segments(body)
        logger.info(
            "twilio_send from=%s to=%s segments=%d urgence=%s",
            self.from_number, to_number, segments, urgence,
        )

        data = {"To": to_number, "From": self.from_number, "Body": body}
        result = await self._post("/Messages.json", data)
        logger.info(
            "twilio_sent sid=%s status=%s num_segments=%s",
            result.get("sid"), result.get("status"), result.get("num_segments"),
        )
        return result

    async def get_balance(self) -> dict[str, Any]:
        """Retourne le solde du compte (pour monitoring)."""
        return await self._get("/Balance.json")

    async def get_message_status(self, message_sid: str) -> dict[str, Any]:
        """Status de livraison d'un message precedemment envoye."""
        return await self._get(f"/Messages/{message_sid}.json")

    async def get_account_info(self) -> dict[str, Any]:
        return await self._get(".json")

    @staticmethod
    def _estimate_segments(body: str) -> int:
        try:
            body.encode("ascii")
            limit = SMS_SEGMENT_GSM7
        except UnicodeEncodeError:
            limit = SMS_SEGMENT_UCS2
        if not body:
            return 0
        return (len(body) - 1) // limit + 1


class TwilioSMSError(RuntimeError):
    def __init__(self, message: str, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {}


def build_from_env(env: dict[str, str] | None = None) -> TwilioSMSClient:
    import os
    env = env or os.environ
    return TwilioSMSClient(
        account_sid=env["TWILIO_ACCOUNT_SID"],
        auth_token=env["TWILIO_AUTH_TOKEN"],
        from_number=env["TWILIO_FROM_NUMBER"],
    )
