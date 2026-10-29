"""Reproducible, *synthetic* long-range preference recall evaluation.

No real user data, LLM-as-a-Judge, cost benchmark or invented performance numbers.
"""

import argparse
import asyncio
import json
import statistics
import tempfile
from pathlib import Path

from social_agent.config import Settings
from social_agent.engine import AgentEngine
from social_agent.schemas import ChatRequest
from social_agent.storage import SQLiteStore


async def evaluate(mode: str, count: int = 10, filler_turns: int = 12) -> dict:
    with tempfile.TemporaryDirectory() as temp:
        settings = Settings(database_path=str(Path(temp) / "eval.sqlite3"), window_messages=8)
        store = SQLiteStore(settings.database_path)
        engine = AgentEngine(settings, store)
        success = 0
        latencies = []
        for i in range(count):
            user, thread = f"eval{i}", f"session{i}"
            store.set_consent(user, True)
            await engine.chat(ChatRequest(user_id=user, thread_id=thread, message="我喜欢猫", memory_mode=mode))
            for j in range(filler_turns):
                await engine.chat(ChatRequest(user_id=user, thread_id=thread, message=f"闲聊 {j}", memory_mode=mode))
            response = await engine.chat(
                ChatRequest(user_id=user, thread_id=thread, message="我喜欢什么宠物？", memory_mode=mode)
            )
            success += int("猫" in response.reply)
            latencies.append(response.metrics.latency_ms)
        return {
            "mode": mode,
            "scenarios": count,
            "filler_turns": filler_turns,
            "accuracy": round(success / count, 4),
            "mean_latency_ms": round(statistics.mean(latencies), 2),
            "disclaimer": "Synthetic demo-model evaluation only; not LLM or production performance",
        }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["off", "window", "dual", "all"], default="all")
    parser.add_argument("--cases", type=int, default=10)
    parser.add_argument("--filler", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.cases <= 1000 or not 0 <= args.filler <= 100:
        parser.error("cases must be 1..1000 and filler must be 0..100")
    modes = ["off", "window", "dual"] if args.mode == "all" else [args.mode]
    results = [await evaluate(mode, args.cases, args.filler) for mode in modes]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
