import pytest

from social_agent.config import Settings
from social_agent.evaluation import evaluate
from social_agent.routing import choose_route
from social_agent.tools import safe_calculate


def test_route_rules():
    assert choose_route("你好").tier == "small"
    assert choose_route("分析两种解决方案").tier == "large"
    assert choose_route("@time").tier == "tool"


def test_safe_math():
    assert safe_calculate("1+2*3") == "7"
    assert safe_calculate("-(4-9)/5") == "1"
    with pytest.raises(ValueError):
        safe_calculate("2**1000")
    with pytest.raises(ValueError):
        safe_calculate("10*999999999999999")


@pytest.mark.asyncio
async def test_synthetic_recall_eval():
    off = await evaluate("off", count=2, filler_turns=6)
    window = await evaluate("window", count=2, filler_turns=6)
    dual = await evaluate("dual", count=2, filler_turns=6)
    assert off["accuracy"] == 0.0
    assert window["accuracy"] == 0.0
    assert dual["accuracy"] == 1.0


def test_config_validation(tmp_path):
    Settings(database_path=str(tmp_path / "x.sqlite3"), model_backend="demo").validate()
    with pytest.raises(ValueError):
        Settings(database_path=str(tmp_path / "x.sqlite3"), model_backend="openai").validate()
