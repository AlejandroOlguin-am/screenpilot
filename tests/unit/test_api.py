import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TEAM_TOKEN", "t0k")
    monkeypatch.setenv("FAKE_TASK_S", "0.3")
    with TestClient(main.app) as c:
        yield c


AUTH = {"Authorization": "Bearer t0k"}
BODY = {"tarea": "x", "escritorio": {"url": "wss://d/websockify", "password": "p"}}


def test_health_sin_token(client):
    assert client.get("/health").json() == {"ok": True}


def test_post_sin_token_es_401(client):
    assert client.post("/tasks", json=BODY).status_code == 401
    assert client.post("/tasks", json=BODY, headers={"Authorization": "Bearer otro"}).status_code == 401


def test_flujo_en_curso_luego_final(client):
    t0 = time.monotonic()
    r = client.post("/tasks", json=BODY, headers=AUTH)
    assert time.monotonic() - t0 < 2
    tid = r.json()["task_id"]
    assert client.get(f"/tasks/{tid}", headers=AUTH).json()["estado"] == "en_curso"
    deadline = time.monotonic() + 5
    while client.get(f"/tasks/{tid}", headers=AUTH).json()["estado"] == "en_curso":
        assert time.monotonic() < deadline
        time.sleep(0.1)
    assert client.get(f"/tasks/{tid}", headers=AUTH).json()["estado"] in {"terminada", "fallida"}


def test_id_desconocido_es_404(client):
    assert client.get("/tasks/nope", headers=AUTH).status_code == 404
