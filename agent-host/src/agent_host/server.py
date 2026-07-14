"""FastAPI server for the Agent Host developer portal."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from agent_host.config import get_settings
from agent_host.env_vars import EnvValidationError, normalize_env, validate_env_key
from agent_host.runner import AgentRunner, RunnerError
from agent_host.store import AgentStore, HostedAgent
from agent_host.ui import developer_portal_html
from agent_host.upload import UploadError, extract_zip

LOGO_PATH = get_settings().repo_root / "cognilance" / "assets" / "logo.png"


class AgentResponse(BaseModel):
    id: str
    name: str
    entry_file: str
    status: str
    port: int | None
    pid: int | None
    error_message: str | None
    registry_online: bool | None
    env_keys: list[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_agent(cls, agent: HostedAgent, *, registry_online: bool | None = None) -> AgentResponse:
        return cls(
            id=agent.id,
            name=agent.name,
            entry_file=agent.entry_file,
            status=agent.status,
            port=agent.port,
            pid=agent.pid,
            error_message=agent.error_message,
            registry_online=registry_online,
            env_keys=agent.env_keys or [],
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


class EnvUpdateRequest(BaseModel):
    set: dict[str, str] = Field(default_factory=dict)
    remove: list[str] = Field(default_factory=list)


def _parse_env_form(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="env must be valid JSON object") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="env must be a JSON object")
    try:
        return normalize_env({str(k): str(v) for k, v in payload.items()})
    except EnvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _registry_online(agent: HostedAgent, settings_port_check: bool = True) -> bool | None:
    if agent.status != "running" or not agent.port:
        return None
    settings = get_settings()
    url = f"{settings.registry_url.rstrip('/')}/v1/agents/discover"
    try:
        resp = httpx.get(url, timeout=3.0)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return False if settings_port_check else None
    if isinstance(payload, dict):
        agents = payload.get("agents", [])
    else:
        agents = payload
    needle = f":{agent.port}"
    for item in agents if isinstance(agents, list) else []:
        if needle in str(item.get("url", "")):
            return True
    return False


def _ensure_agent_mutable(agent: HostedAgent) -> None:
    if agent.status in {"running", "starting"}:
        raise HTTPException(
            status_code=409,
            detail="Stop the agent before changing environment variables",
        )


def create_app() -> FastAPI:
    settings = get_settings()
    store = AgentStore()
    store.init_db()
    runner = AgentRunner(store=store, settings=settings)

    app = FastAPI(title="Cognilance Agent Host", version="0.1.0")

    @app.on_event("startup")
    async def startup() -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/logo.png")
    async def logo() -> FileResponse:
        if not LOGO_PATH.is_file():
            raise HTTPException(status_code=404, detail="Logo not found")
        return FileResponse(LOGO_PATH, media_type="image/png")

    @app.get("/", response_class=HTMLResponse)
    async def portal() -> str:
        return developer_portal_html()

    @app.get("/api/agents")
    async def list_agents() -> JSONResponse:
        agents = store.list_all_with_env_keys()
        payload = [
            AgentResponse.from_agent(a, registry_online=_registry_online(a)).model_dump()
            for a in agents
        ]
        return JSONResponse(content={"agents": payload})

    @app.post("/api/agents/upload")
    async def upload_agent(
        file: UploadFile = File(...),
        env: str = Form(default="{}"),
    ) -> JSONResponse:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Upload must be a .zip file")
        env_vars = _parse_env_form(env)
        data = await file.read()
        agent_id = str(uuid.uuid4())
        extract_dir = settings.data_dir / agent_id
        try:
            result = extract_zip(data, extract_dir, max_bytes=settings.max_zip_bytes)
        except UploadError as exc:
            shutil.rmtree(extract_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        agent = store.create(
            name=result.name,
            entry_file=result.entry_file,
            extract_dir=str(extract_dir),
            agent_id=agent_id,
        )
        if env_vars:
            store.set_env_vars(agent_id, env_vars)
        agent = store.get_with_env_keys(agent_id)
        assert agent is not None
        return JSONResponse(
            content={
                "agent": AgentResponse.from_agent(agent).model_dump(),
                "has_requirements": result.has_requirements,
            },
            status_code=201,
        )

    @app.get("/api/agents/{agent_id}/env")
    async def get_agent_env_keys(agent_id: str) -> JSONResponse:
        agent = store.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return JSONResponse(content={"keys": store.list_env_keys(agent_id)})

    @app.put("/api/agents/{agent_id}/env")
    async def update_agent_env(agent_id: str, body: EnvUpdateRequest) -> JSONResponse:
        agent = store.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        _ensure_agent_mutable(agent)
        try:
            updates = normalize_env(body.set)
            remove_keys = sorted({validate_env_key(key) for key in body.remove if key.strip()})
        except EnvValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        keys = store.merge_env_vars(agent_id, updates, remove_keys=remove_keys)
        return JSONResponse(content={"keys": keys})

    @app.get("/api/earnings")
    async def earnings(wallet: str = "") -> JSONResponse:
        """Mock-USDC earnings for a developer payout wallet (shared payment ledger)."""
        payout = (wallet or "").strip()
        if not payout:
            raise HTTPException(status_code=400, detail="wallet query param required")
        try:
            from cognilance.payments import PaymentService

            svc = PaymentService()
            bal = svc.agent_earnings_base_units(payout)
            ledger = svc.agent_ledger(payout, limit=25)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return JSONResponse(
            content={
                "payout_wallet": payout,
                "balance_base_units": bal,
                "balance_usd": bal // 1_000_000,
                "ledger": ledger,
                "note": (
                    "Funds arrive automatically when managers settle hires; "
                    "set PAYOUT_WALLET + PRICE_USD_CENTS on your agent env."
                ),
            }
        )

    @app.post("/api/agents/{agent_id}/start")
    async def start_agent(agent_id: str) -> JSONResponse:
        try:
            agent = runner.start(agent_id)
        except RunnerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        agent = store.get_with_env_keys(agent_id)
        assert agent is not None
        return JSONResponse(
            content={"agent": AgentResponse.from_agent(agent, registry_online=_registry_online(agent)).model_dump()}
        )

    @app.post("/api/agents/{agent_id}/stop")
    async def stop_agent(agent_id: str) -> JSONResponse:
        try:
            agent = runner.stop(agent_id)
        except RunnerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        agent = store.get_with_env_keys(agent_id) or agent
        return JSONResponse(content={"agent": AgentResponse.from_agent(agent).model_dump()})

    @app.delete("/api/agents/{agent_id}")
    async def delete_agent(agent_id: str) -> JSONResponse:
        agent = store.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        if agent.status == "running":
            try:
                runner.stop(agent_id, force=True)
            except RunnerError:
                pass
        extract_dir = Path(agent.extract_dir)
        if extract_dir.is_dir():
            shutil.rmtree(extract_dir, ignore_errors=True)
        store.delete(agent_id)
        return JSONResponse(content={"deleted": True})

    @app.get("/api/agents/{agent_id}/logs")
    async def agent_logs(agent_id: str, lines: int = 200) -> JSONResponse:
        agent = store.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        lines = max(1, min(lines, 2000))
        return JSONResponse(content={"logs": runner.tail_logs(agent, lines=lines)})

    return app


app = create_app()
