from conftest import chat

from social_agent.memory import extract_fact


def test_narrow_automatic_fact_extraction():
    assert extract_fact("我喜欢猫") == ("pet", "猫")
    assert extract_fact("我现在更喜欢狗") == ("pet", "狗")
    assert extract_fact("I prefer cats") == ("pet", "cats")
    assert extract_fact("记住：language=中文") == ("language", "中文")
    assert extract_fact("我的身体情况不舒服") is None
    assert extract_fact("please remember my family members") is None


def test_no_memory_before_opt_in(client):
    assert chat(client, message="我喜欢猫").status_code == 200
    assert client.get("/v1/users/alice/memories").json() == []
    response = chat(client, thread="new", message="我喜欢什么宠物？")
    assert "不知道" in response.json()["reply"]


def test_long_memory_across_threads_and_updates(client):
    client.put("/v1/users/alice/consent", json={"enabled": True})
    chat(client, message="我喜欢猫")
    answer = chat(client, thread="new", message="我喜欢什么宠物？").json()
    assert "猫" in answer["reply"]
    assert answer["metrics"]["memory_items"] == 1
    chat(client, message="我现在更喜欢狗")
    answer = chat(client, thread="new2", message="我喜欢什么宠物？").json()["reply"]
    assert "狗" in answer and "猫" not in answer
    assert len(client.get("/v1/users/alice/memories").json()) == 1


def test_user_isolation(client):
    client.put("/v1/users/alice/consent", json={"enabled": True})
    client.put("/v1/users/bob/consent", json={"enabled": True})
    chat(client, user="alice", message="我喜欢猫")
    chat(client, user="bob", message="我喜欢狗")
    assert "猫" in chat(client, user="alice", thread="new", message="我喜欢什么宠物？").json()["reply"]
    assert "狗" in chat(client, user="bob", thread="new", message="我喜欢什么宠物？").json()["reply"]
    assert "猫" not in chat(client, user="bob", thread="new", message="我喜欢什么宠物？").json()["reply"]


def test_opt_out_erases_memories(client):
    client.put("/v1/users/alice/consent", json={"enabled": True})
    chat(client, message="我喜欢猫")
    client.put("/v1/users/alice/consent", json={"enabled": False})
    assert client.get("/v1/users/alice/memories").json() == []
    assert "不知道" in chat(client, thread="new", message="我喜欢什么宠物？").json()["reply"]


def test_explicit_memory_write_requires_consent(client):
    url = "/v1/users/alice/memories"
    assert client.put(url, json={"key": "city", "value": "Aachen"}).status_code == 403
    client.put("/v1/users/alice/consent", json={"enabled": True})
    assert client.put(url, json={"key": "city", "value": "Aachen"}).json() == {"stored": True}
    assert client.get(url).json()[0]["value"] == "Aachen"
    assert client.delete(url + "/city").status_code == 200
    assert client.get(url).json() == []


def test_delete_user_cascades_messages_and_memories(client, app):
    client.put("/v1/users/alice/consent", json={"enabled": True})
    chat(client, message="我喜欢猫")
    assert app.state.store.message_count("alice", "a") == 2
    assert client.delete("/v1/users/alice").status_code == 200
    assert app.state.store.message_count("alice", "a") == 0
    assert client.get("/v1/users/alice/memories").json() == []
