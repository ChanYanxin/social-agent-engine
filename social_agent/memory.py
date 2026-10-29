"""Opt-in structured long-term facts and deterministic memory retrieval.

This first version intentionally does NOT claim to implement embeddings or a knowledge graph.
"""

import re

from social_agent.storage import SQLiteStore

EXPLICIT = re.compile(
    r"^(?:remember\s*:|记住[：:])\s*([a-zA-Z0-9_-]{1,40})\s*=\s*(.{1,200})$",
    re.IGNORECASE,
)
PET_ZH = re.compile(r"我(?:现在)?(?:更)?喜欢(猫|狗)(?![\w])")
PET_EN = re.compile(r"\bI\s+(?:now\s+)?(?:prefer|like|love)\s+(cats|dogs)\b", re.IGNORECASE)
PET_KEYS = ("宠物", "猫", "狗", "pet", "cat", "dog", "animal")


def extract_fact(message: str) -> tuple[str, str] | None:
    """Only explicit key/value facts and a narrow, low-sensitivity pet example."""
    text = message.strip()
    if match := EXPLICIT.fullmatch(text):
        return match.group(1).lower(), match.group(2).strip()
    if match := PET_ZH.search(text):
        return "pet", match.group(1)
    if match := PET_EN.search(text):
        return "pet", match.group(1).lower()
    return None


def retrieve(store: SQLiteStore, user_id: str, query: str, limit: int = 5) -> list[dict]:
    """Small deterministic relevance ranking; per-user scope is enforced in the store."""
    if limit <= 0:
        return []
    facts = store.memories(user_id)
    q = query.casefold()

    def score(fact: dict) -> int:
        key, value = fact["key"].casefold(), fact["value"].casefold()
        relevant_pet = key == "pet" and any(k in q for k in PET_KEYS)
        # Direct query-key overlap outranks weaker value overlap.
        return 10 * int(key in q or relevant_pet) + 2 * int(value in q)

    ranked = sorted(facts, key=score, reverse=True)
    return [fact for fact in ranked if score(fact) > 0][:limit]
