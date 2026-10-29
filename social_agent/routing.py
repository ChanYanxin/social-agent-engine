"""Transparent baseline router; not a trained intent classifier."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    tier: str
    reason: str


def choose_route(message: str) -> Route:
    text = message.strip().lower()
    if text.startswith(("@calc ", "@time")):
        return Route("tool", "explicit tool command")
    if len(text) > 220 or any(
        word in text
        for word in ("analyze", "compare", "explain why", "推理", "分析", "比较", "规划", "复杂")
    ):
        return Route("large", "complexity heuristic")
    return Route("small", "simple interaction heuristic")
