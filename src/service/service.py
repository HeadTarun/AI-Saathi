from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents import DEFAULT_AGENT, get_all_agent_info
from api.study_routes import router as study_router
from db import get_supabase


def _cors_origins() -> list[str]:
    configured = os.environ.get("BACKEND_CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]

    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "").strip().rstrip("/")
    if frontend_origin:
        origins.append(frontend_origin)

    vercel_url = os.environ.get("VERCEL_URL", "").strip().rstrip("/")
    if vercel_url:
        origins.append(vercel_url if vercel_url.startswith(("http://", "https://")) else f"https://{vercel_url}")

    origins.extend(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    return sorted(set(origins))


app = FastAPI(
    title="AI Study Companion",
    description="Local MVP for adaptive study planning, teaching, quizzes, and progress.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    health: dict[str, Any] = {"status": "ok", "supabase": {"connected": False}}
    try:
        rows = (
            get_supabase()
            .table("exams")
            .select("id")
            .eq("is_active", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        health["supabase"] = {
            "connected": True,
            "active_exam_available": bool(rows),
            "source": "public.exams",
        }
    except Exception as exc:
        health["status"] = "degraded"
        health["supabase"] = {
            "connected": False,
            "error": str(exc),
        }
    return health


@app.get("/info")
async def info() -> dict[str, Any]:
    return {
        "agents": [agent.model_dump() for agent in get_all_agent_info()],
        "models": ["local-deterministic"],
        "default_agent": DEFAULT_AGENT,
        "default_model": "local-deterministic",
    }


app.include_router(study_router)
