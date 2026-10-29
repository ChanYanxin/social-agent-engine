"""Inspectable agent state transitions: route -> retrieve -> tool/model -> persist.

The v0.1 baseline uses this explicit orchestrator (NOT LangGraph). The boundaries
are intentionally small so a LangGraph implementation can be added and compared.
"""

import json
import time
from dataclasses import dataclass
from typing import AsyncIterator

from social_agent.config import Settings
from social_agent.memory import extract_fact, retrieve
from social_agent.models import ChatContext, model_factory, to_messages
from social_agent.routing import Route, choose_route
from social_agent.schemas import ChatMetrics, ChatRequest, ChatResponse
from social_agent.storage import SQLiteStore
from social_agent.tools import invoke_tool


def approx_tokens(text: str) -> int:
    # One coarse universal *estimate*, not accurate for Chinese or model billing.
    return max(1, (len(text) + 3) // 4)


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass
class Prepared:
    route: Route
    context: ChatContext
    started: float


class AgentEngine:
    def __init__(self, settings: Settings, store: SQLiteStore):
        self.settings = settings
        self.store = store
        self.model = model_factory(settings)

    def prepare(self, request: ChatRequest) -> Prepared:
        started = time.perf_counter()
        self.store.ensure_user(request.user_id)
        route = choose_route(request.message)
        history = (
            self.store.recent_messages(request.user_id, request.thread_id, self.settings.window_messages)
            if request.memory_mode in {"window", "dual"} else []
        )
        # Long-term memory is opt-in, and isolated from window-only and off baselines.
        if request.memory_mode == "dual" and self.store.consent(request.user_id):
            fact = extract_fact(request.message)
            if fact:
                self.store.write_memory(request.user_id, *fact)
            memories = retrieve(self.store, request.user_id, request.message, self.settings.memory_top_k)
            # Queries about preferences are also answered from the structured memory.
        else:
            memories = []
        return Prepared(route, ChatContext(request.message, history, memories), started)

    def metrics(self, prepared: Prepared, reply: str, tool_used: str | None = None) -> ChatMetrics:
        tier = prepared.route.tier
        prompt = json.dumps(to_messages(prepared.context), ensure_ascii=False)
        return ChatMetrics(
            route=tier,
            model="built-in tool" if tier == "tool" else self.model.name(tier),
            latency_ms=round((time.perf_counter() - prepared.started) * 1000, 2),
            approx_input_tokens=approx_tokens(prompt),
            approx_output_tokens=approx_tokens(reply),
            memory_items=len(prepared.context.memories),
            tool_used=tool_used,
        )

    def save_exchange(self, request: ChatRequest, reply: str) -> None:
        self.store.save_message(request.user_id, request.thread_id, "user", request.message)
        self.store.save_message(request.user_id, request.thread_id, "assistant", reply)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        prepared = self.prepare(request)
        tool_used = None
        if prepared.route.tier == "tool":
            tool_used, reply = await invoke_tool(request.message)
        else:
            reply = await self.model.complete(prepared.context, prepared.route.tier)
        self.save_exchange(request, reply)
        return ChatResponse(reply=reply, metrics=self.metrics(prepared, reply, tool_used))

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        prepared = self.prepare(request)
        yield sse("meta", {"route": prepared.route.tier, "memory_items": len(prepared.context.memories)})
        chunks: list[str] = []
        tool_used = None
        try:
            if prepared.route.tier == "tool":
                tool_used, result = await invoke_tool(request.message)
                chunks.append(result)
                yield sse("delta", {"text": result})
            else:
                async for chunk in self.model.stream(prepared.context, prepared.route.tier):
                    chunks.append(chunk)
                    yield sse("delta", {"text": chunk})
            reply = "".join(chunks)
            self.save_exchange(request, reply)
            yield sse("done", {"metrics": self.metrics(prepared, reply, tool_used).model_dump()})
        except Exception:
            # Never stream raw provider errors, which may contain credentials/PII.
            yield sse("error", {"message": "Generation failed; response was not stored."})
