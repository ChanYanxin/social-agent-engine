"""Environment-based settings with safe local demo defaults."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: str = "social_agent.sqlite3"
    model_backend: str = "demo"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    provider_api_key: str = ""
    small_model: str = "gpt-4o-mini"
    large_model: str = "gpt-4o"
    window_messages: int = 12
    memory_top_k: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("DATABASE_PATH", "social_agent.sqlite3"),
            model_backend=os.getenv("MODEL_BACKEND", "demo").lower(),
            api_key=os.getenv("SOCIAL_AGENT_API_KEY", ""),
            base_url=os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1"),
            provider_api_key=os.getenv("OPENAI_COMPAT_API_KEY", ""),
            small_model=os.getenv("SMALL_MODEL", "gpt-4o-mini"),
            large_model=os.getenv("LARGE_MODEL", "gpt-4o"),
        )

    def validate(self) -> None:
        if self.model_backend not in {"demo", "openai"}:
            raise ValueError("MODEL_BACKEND must be demo or openai")
        if self.model_backend == "openai" and not self.provider_api_key:
            raise ValueError("OPENAI_COMPAT_API_KEY is required in openai mode")
        if self.window_messages < 0 or self.memory_top_k < 0:
            raise ValueError("Memory limits must not be negative")
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
