"""Public request/response data contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

USER_ID = r"^[a-zA-Z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(pattern=USER_ID)
    thread_id: str = Field(pattern=USER_ID)
    message: str = Field(min_length=1, max_length=4000)
    memory_mode: Literal["off", "window", "dual"] = "dual"


class ChatMetrics(BaseModel):
    route: Literal["small", "large", "tool"]
    model: str
    latency_ms: float
    approx_input_tokens: int
    approx_output_tokens: int
    memory_items: int
    tool_used: str | None = None
    # Estimated using characters/4, not a tokenizer or provider billing data.


class ChatResponse(BaseModel):
    reply: str
    metrics: ChatMetrics


class ConsentRequest(BaseModel):
    enabled: bool


class MemoryWrite(BaseModel):
    key: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_\-]+$")
    value: str = Field(min_length=1, max_length=200)


class MemoryItem(BaseModel):
    key: str
    value: str
    updated_at: str


class ConsentResponse(BaseModel):
    user_id: str
    enabled: bool
