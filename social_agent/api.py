"""HTTP interface. The optional API key is for a local demo, not user authentication."""

import hmac
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from social_agent.config import Settings
from social_agent.engine import AgentEngine
from social_agent.schemas import (
    ChatRequest,
    ChatResponse,
    ConsentRequest,
    ConsentResponse,
    MemoryItem,
    MemoryWrite,
)
from social_agent.storage import SQLiteStore

WEB_INDEX = Path(__file__).resolve().parent.parent / "web" / "index.html"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    store = SQLiteStore(settings.database_path)
    engine = AgentEngine(settings, store)
    app = FastAPI(
        title="Social Agent Engine",
        description="Research prototype; demo mode is rule-based, not a real LLM.",
        version="0.1.0",
    )
    app.state.store = store
    app.state.engine = engine

    def verify_key(x_api_key: str | None = Header(default=None)) -> None:
        if settings.api_key and not hmac.compare_digest(x_api_key or "", settings.api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

    def valid_user(user_id: str) -> str:
        from re import fullmatch

        if not fullmatch(r"[a-zA-Z0-9_-]{1,64}", user_id):
            raise HTTPException(status_code=422, detail="Invalid user_id")
        return user_id

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "backend": settings.model_backend}

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(WEB_INDEX)

    @app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(verify_key)])
    async def chat(request: ChatRequest):
        try:
            return await engine.chat(request)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Model generation failed") from exc

    @app.post("/v1/chat/stream", dependencies=[Depends(verify_key)])
    async def chat_stream(request: ChatRequest):
        return StreamingResponse(
            engine.stream(request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.put("/v1/users/{user_id}/consent", response_model=ConsentResponse, dependencies=[Depends(verify_key)])
    def set_consent(user_id: str, request: ConsentRequest):
        valid_user(user_id)
        store.set_consent(user_id, request.enabled)
        return ConsentResponse(user_id=user_id, enabled=request.enabled)

    @app.get("/v1/users/{user_id}/memories", response_model=list[MemoryItem], dependencies=[Depends(verify_key)])
    def list_memories(user_id: str):
        valid_user(user_id)
        return store.memories(user_id)

    @app.put("/v1/users/{user_id}/memories", dependencies=[Depends(verify_key)])
    def put_memory(user_id: str, request: MemoryWrite):
        valid_user(user_id)
        if not store.write_memory(user_id, request.key, request.value):
            raise HTTPException(status_code=403, detail="Memory consent is disabled")
        return {"stored": True}

    @app.delete("/v1/users/{user_id}/memories/{key}", dependencies=[Depends(verify_key)])
    def delete_memory(user_id: str, key: str):
        valid_user(user_id)
        store.delete_memory(user_id, key)
        return {"deleted": True}

    @app.delete("/v1/users/{user_id}", dependencies=[Depends(verify_key)])
    def delete_user(user_id: str):
        valid_user(user_id)
        store.delete_user(user_id)
        return {"deleted": True}

    return app


app = create_app()
