"""
Legifrance + JudiLibre via PISTE — wrapper async pour J-ARVIS V2.

Source des donnees : API publiques DILA (Direction de l'information legale
et administrative) via le portail PISTE (piste.gouv.fr).

Deux APIs differentes exposees sur la meme base OAuth PISTE :
- /dila/legifrance/lf-engine-app : textes juridiques (codes, lois,
  decrets, arretes, JORF, conventions collectives, CNIL, Conseil
  d'Etat...)
- /cassation/judilibre/v1.0 : jurisprudence judiciaire (Cour de
  cassation, cours d'appel, tribunaux judiciaires, tribunaux de
  commerce).

Cas d'usage prioritaires pour ELEXITY 34 :
- TVA 5,5 % photovoltaique : article 279-0 bis du CGI
  (conditions cumulatives : <= 9 kWc + panneaux Certisolis PPE2-V2 + EMS).
- Decennale batiment : articles 1792 et suivants du Code civil.
- RGE QualiPV : arretes du 1er decembre 2015 (qualifications
  installateurs).
- CGV / CGU : verification conformite clauses (droit conso, droit
  de retractation...).
- Loi Hamon : droit de retractation consommateur (14 jours,
  article L221-18 du Code de la consommation).

OAuth 2.0 Client Credentials :
- Grant type : client_credentials
- Scope : "openid"
- Token duree : ~60 min (auto-refresh ici)
- application/x-www-form-urlencoded pour le token endpoint
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20.0

ENVIRONMENTS: dict[str, dict[str, str]] = {
    "sandbox": {
        "oauth": "https://sandbox-oauth.piste.gouv.fr/api/oauth/token",
        "base": "https://sandbox-api.piste.gouv.fr",
    },
    "prod": {
        "oauth": "https://oauth.piste.gouv.fr/api/oauth/token",
        "base": "https://api.piste.gouv.fr",
    },
}


@dataclass
class LegifranceClient:
    client_id: str
    client_secret: str
    environment: str = "sandbox"
    timeout: float = DEFAULT_TIMEOUT

    _access_token: str | None = field(default=None, init=False, repr=False)
    _token_expires_at: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.environment not in ENVIRONMENTS:
            raise ValueError(
                f"environment={self.environment!r} invalide — "
                f"attendu : {list(ENVIRONMENTS)}"
            )

    @property
    def _token_url(self) -> str:
        return ENVIRONMENTS[self.environment]["oauth"]

    @property
    def _base_url(self) -> str:
        return ENVIRONMENTS[self.environment]["base"]

    @property
    def _lf_api(self) -> str:
        return f"{self._base_url}/dila/legifrance/lf-engine-app"

    @property
    def _jl_api(self) -> str:
        return f"{self._base_url}/cassation/judilibre/v1.0"

    async def authenticate(self, force: bool = False) -> str:
        """Obtient (ou recupere en cache) le token OAuth2.

        Token cache en memoire, auto-refresh 60s avant expiration.
        force=True pour regenerer immediatement (utile apres un 401).
        """
        now = time.time()
        if (not force) and self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "openid",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        logger.info("piste_oauth env=%s", self.environment)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self._token_url, headers=headers, data=data)
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            logger.error("piste_oauth_error status=%d body=%r",
                         resp.status_code, str(body)[:200])
            raise LegifranceError(
                f"OAuth PISTE HTTP {resp.status_code}", body
            )
        payload = resp.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._token_expires_at = now + expires_in
        logger.info("piste_oauth_ok expires_in=%d", expires_in)
        return self._access_token

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.authenticate()
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _post_lf(self, path: str, payload: dict) -> dict:
        url = f"{self._lf_api}{path}"
        headers = await self._auth_headers()
        headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
        return self._handle(resp, path)

    async def _get(self, url: str, params: dict | None = None) -> dict:
        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers, params=params or {})
        return self._handle(resp, url)

    def _handle(self, resp: httpx.Response, ctx: str) -> dict:
        if resp.status_code == 401:
            # token expire entre-temps — invalide le cache, laisse le caller re-essayer
            self._access_token = None
            self._token_expires_at = 0
            raise LegifranceError(f"Token expire/refuse ({ctx})", {"status": 401})
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            logger.error("piste_api_error ctx=%s status=%d body=%r",
                         ctx, resp.status_code, str(body)[:200])
            raise LegifranceError(
                f"PISTE HTTP {resp.status_code} ({ctx})", body,
            )
        return resp.json()

    async def ping(self) -> str:
        """Teste la connectivite basique Legifrance (/search/ping).

        Cet endpoint repond text/plain ; on bypasse le _handle JSON.
        """
        token = await self.authenticate()
        url = f"{self._lf_api}/search/ping"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code >= 400:
            raise LegifranceError(
                f"PISTE ping HTTP {resp.status_code}",
                {"body": resp.text[:200]},
            )
        return resp.text.strip() or "ok"

    async def search_code(self, code_name: str, query: str,
                          limit: int = 10) -> dict:
        """Recherche dans un code juridique specifique.

        code_name : ex. 'Code general des impots', 'Code civil',
                    'Code de la consommation'.
        query : termes de recherche (ex. 'article 279-0 bis').
        """
        payload = {
            "recherche": {
                "champs": [{
                    "typeChamp": "ALL",
                    "criteres": [{
                        "typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                        "valeur": query,
                        "operateur": "ET",
                    }],
                    "operateur": "ET",
                }],
                "filtres": [{
                    "facette": "NOM_CODE",
                    "valeurs": [code_name],
                }],
                "pageNumber": 1,
                "pageSize": limit,
                "operateur": "ET",
                "sort": "PERTINENCE",
                "typePagination": "DEFAUT",
            },
            "fond": "CODE_DATE",
        }
        return await self._post_lf("/search", payload)

    async def search_legifrance(self, query: str, fond: str = "ALL",
                                limit: int = 10) -> dict:
        """Recherche generique dans Legifrance.

        fond : ALL | JORF | LODA_DATE | CIRC | KALI | CODE_DATE ...
        """
        payload = {
            "recherche": {
                "champs": [{
                    "typeChamp": "ALL",
                    "criteres": [{
                        "typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                        "valeur": query,
                        "operateur": "ET",
                    }],
                    "operateur": "ET",
                }],
                "pageNumber": 1,
                "pageSize": limit,
                "operateur": "ET",
                "sort": "PERTINENCE",
                "typePagination": "DEFAUT",
            },
            "fond": fond,
        }
        return await self._post_lf("/search", payload)

    async def get_article(self, article_id: str) -> dict:
        """Recupere un article par son id Legifrance (ex. 'LEGIARTI000006309361')."""
        return await self._post_lf("/consult/getArticle", {"id": article_id})

    async def get_code_section(self, legi_part_id: str) -> dict:
        """Consulte un pan de code (ex. 'LEGITEXT000006069577' pour le CGI)."""
        return await self._post_lf("/consult/legiPart", {"textId": legi_part_id})

    # ----- JudiLibre (jurisprudence) -----

    async def search_jurisprudence(self, query: str,
                                   jurisdiction: list[str] | None = None,
                                   limit: int = 10) -> dict:
        """Recherche jurisprudence via JudiLibre.

        jurisdiction : liste parmi ['cc','ca','tj','tcom'] (defaut : toutes).
        """
        params: dict[str, Any] = {
            "query": query,
            "page_size": limit,
            "page": 0,
            "resolve_references": "true",
            "sort": "scorepub",
            "order": "desc",
        }
        for j in jurisdiction or ["cc", "ca", "tj", "tcom"]:
            params.setdefault("jurisdiction", []).append(j)
        url = f"{self._jl_api}/search"
        return await self._get(url, params=params)

    async def get_decision(self, decision_id: str) -> dict:
        """Recupere une decision jurisprudentielle par id JudiLibre."""
        url = f"{self._jl_api}/decision"
        return await self._get(url, params={"id": decision_id})


class LegifranceError(RuntimeError):
    def __init__(self, message: str, payload: Any = None):
        super().__init__(message)
        self.payload = payload


def build_from_env(env: dict[str, str] | None = None) -> LegifranceClient:
    import os
    env = env or os.environ
    return LegifranceClient(
        client_id=env["PISTE_CLIENT_ID"],
        client_secret=env["PISTE_CLIENT_SECRET"],
        environment=env.get("PISTE_ENVIRONMENT", "sandbox"),
    )
