from conftest import chat

from social_agent.api import create_app
from social_agent.config import Settings
from fastapi.testclient import TestClient


def test_health_and_ui(client):
    assert client.get("/healthz").json() == {"ok": True, "backend": "demo"}
    response = client.get("/")
    assert response.status_code == 200
    assert "Social Agent Engine" in response.text


def test_chat_validation_and_response(client):
    assert chat(client, user="a/../../", message="hi").status_code == 422
    assert chat(client, message="").status_code == 422
    assert chat(client, message="hello").json()["metrics"]["model"] == "demo-rule-model"
    assert chat(client, message="分析这个问题").json()["metrics"]["route"] == "large"


def test_sse_endpoint(client):
    response = client.post(
        "/v1/chat/stream",
        json={"user_id": "alice", "thread_id": "a", "message": "hello"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: meta" in response.text
    assert "event: delta" in response.text
    assert "event: done" in response.text


def test_api_key_required_if_configured(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "auth.sqlite3"), api_key="my-secret"))
    with TestClient(app) as client:
        request = {"user_id": "alice", "thread_id": "t", "message": "hi"}
        assert client.post("/v1/chat", json=request).status_code == 401
        assert client.post("/v1/chat", json=request, headers={"X-API-Key": "my-secret"}).status_code == 200
        assert client.get("/v1/users/alice/memories").status_code == 401


def test_window_baseline_does_not_use_long_term(client):
    client.put("/v1/users/alice/consent", json={"enabled": True})
    chat(client, message="我喜欢猫", mode="dual")
    assert "不知道" in chat(client, thread="other", message="我喜欢什么宠物？", mode="window").json()["reply"]
    assert "不知道" in chat(client, thread="yet_another", message="我喜欢什么宠物？", mode="off").json()["reply"]


def test_tool_explicit_command(client):
    response = chat(client, message="@calc (6+4)*2").json()
    assert response["reply"] == "20"
    assert response["metrics"]["route"] == "tool"
    assert response["metrics"]["tool_used"] == "calculator"
    assert "Tool error" in chat(client, message="@calc __import__('os').system('whoami')").json()["reply"]
    assert "Tool error" in chat(client, message="@calc 1/0").json()["reply"]


def test_consent_persisted_per_user(client):
    assert client.put("/v1/users/alice/consent", json={"enabled": True}).json()["enabled"]
    assert client.put("/v1/users/alice/consent", json={"enabled": False}).json()["enabled"] is False
