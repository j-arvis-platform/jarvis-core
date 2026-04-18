"""FastAPI serveur pour J-ARVIS V2.

Expose l'agent Jarvis derriere une API HTTP simple consommee par :
- la PWA (Pulse / Actions / Chat)
- les tests manuels curl
- plus tard d'autres integrations internes

Lance via :
  uvicorn agent.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.core.skills import (
    discover_skills, inject_into_system_prompt, match_skills,
)
from agent.core.supabase_client import get_supabase, query_table
from agent.handlers.main import JarvisAgent

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("jarvis-server")

TENANT_ID = os.environ.get("JARVIS_TENANT_ID", "elexity34")
MODULES_ROOT = os.environ.get(
    "JARVIS_MODULES_ROOT",
    str((os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) + "/../modules"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.jarvis = JarvisAgent(tenant_id=TENANT_ID)
    app.state.skills = discover_skills(_resolve_modules_path())
    logger.info("Jarvis pret : tenant=%s skills=%s",
                TENANT_ID, [s.name for s in app.state.skills])
    yield


def _resolve_modules_path() -> "os.PathLike":
    from pathlib import Path
    candidates = [
        Path(MODULES_ROOT).resolve(),
        Path(__file__).resolve().parents[2] / "modules",
        Path("/home/jarvis/jarvis-platform/modules"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


app = FastAPI(title="J-ARVIS Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ALLOW_ORIGINS", "*"
    ).split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    context: dict[str, Any] | None = None


class DecideRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected|reported)$")
    note: str | None = None


@app.get("/api/health")
async def health() -> dict[str, Any]:
    services: dict[str, Any] = {}

    # Supabase
    try:
        sb = get_supabase(TENANT_ID)
        sb.table("contacts").select("id").limit(1).execute()
        services["supabase"] = "ok"
    except Exception as e:
        services["supabase"] = f"ko: {e}"

    # Jarvis / Anthropic (on teste seulement que l'agent est chargé)
    try:
        _ = app.state.jarvis.system_prompt
        services["jarvis"] = "ok"
    except Exception as e:
        services["jarvis"] = f"ko: {e}"

    services["skills"] = [s.name for s in app.state.skills]
    status = "ok" if all(
        v == "ok" for k, v in services.items() if k != "skills"
    ) else "degraded"
    return {"status": status, "tenant": TENANT_ID, "services": services,
            "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/kpis")
async def kpis() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since_7j = (now - timedelta(days=7)).isoformat()
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0,
                                   microsecond=0).isoformat()

    k: dict[str, Any] = {}
    alerts: list[dict[str, Any]] = []

    try:
        sb = get_supabase(TENANT_ID)
        k["prospects_7j"] = _safe_count(
            sb.table("contacts").select("id", count="exact")
            .eq("type", "prospect")
            .gte("created_at", since_7j).execute()
        )
        k["devis_en_attente"] = _safe_count(
            sb.table("projets").select("id", count="exact")
            .eq("statut", "devis_envoye").execute()
        )
        k["taches_ouvertes"] = _safe_count(
            sb.table("taches").select("id", count="exact")
            .in_("statut", ["todo", "in_progress"]).execute()
        )
        # CA mois : placeholder tant que Invoice Ninja MCP pas cable
        k["ca_mois"] = "—"

        alerts_resp = (
            sb.table("file_humaine").select("*")
            .eq("decision", "pending")
            .order("created_at", desc=True)
            .limit(3).execute()
        )
        alerts = alerts_resp.data or []
    except Exception as e:
        logger.warning("kpis: supabase KO %s", e)

    return {"kpis": k, "alerts": alerts,
            "generated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/file-humaine")
async def list_file_humaine() -> dict[str, Any]:
    try:
        sb = get_supabase(TENANT_ID)
        resp = (
            sb.table("file_humaine").select("*")
            .eq("decision", "pending")
            .order("created_at", desc=False).execute()
        )
        return {"items": resp.data or []}
    except Exception as e:
        logger.error("file_humaine KO %s", e)
        raise HTTPException(502, detail=str(e))


@app.post("/api/file-humaine/{item_id}/decide")
async def decide_item(item_id: str, body: DecideRequest) -> dict[str, Any]:
    try:
        sb = get_supabase(TENANT_ID)
        patch = {
            "decision": body.decision,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        if body.note:
            patch["decision_meta"] = {"note": body.note}
        resp = sb.table("file_humaine").update(patch).eq("id", item_id).execute()
        return {"ok": True, "row": (resp.data or [None])[0]}
    except Exception as e:
        raise HTTPException(502, detail=str(e))


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    jarvis: JarvisAgent = app.state.jarvis
    skills = app.state.skills

    matched = match_skills(req.message, skills)
    base = JarvisAgent(TENANT_ID).system_prompt
    jarvis.system_prompt = inject_into_system_prompt(base, matched)

    try:
        reply = jarvis.respond(req.message)
    except Exception as e:
        logger.error("chat KO %s", e)
        raise HTTPException(500, detail=str(e))

    return {
        "response": reply,
        "skills_matched": [s.name for s in matched],
        "time": datetime.now(timezone.utc).isoformat(),
    }


def _safe_count(resp) -> int:
    try:
        return int(resp.count or 0)
    except Exception:
        return 0
