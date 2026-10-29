import pytest
from fastapi.testclient import TestClient

from social_agent.api import create_app
from social_agent.config import Settings


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database_path=str(tmp_path / "test.sqlite3")))


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def chat(client, user="alice", thread="a", message="hi", mode="dual"):
    return client.post(
        "/v1/chat",
        json={"user_id": user, "thread_id": thread, "message": message, "memory_mode": mode},
    )
