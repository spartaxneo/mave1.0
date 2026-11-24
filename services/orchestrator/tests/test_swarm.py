import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS1_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "devsecret-devsecret-devsecret-devsecret")
    monkeypatch.setenv("OS1_CLIENT_TOKEN", "test-token")
    monkeypatch.setenv("JEV_TRANSPORT", "mock")
    import os1_orchestrator.app as app_module

    return TestClient(app_module.app), app_module


def test_swarm_list_and_details(authed_client):
    client, app_module = authed_client
    headers = {"Authorization": "Bearer test-token"}

    # 1. List runs
    res = client.get("/os1/runs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert len(data["runs"]) >= 3
    run_ids = [r["id"] for r in data["runs"]]
    assert "run_101" in run_ids
    assert "run_102" in run_ids
    assert "run_103" in run_ids

    # 2. Get specific run details
    res_detail = client.get("/os1/runs/run_101", headers=headers)
    assert res_detail.status_code == 200
    d = res_detail.json()
    assert d["ok"] is True
    assert d["run"]["label"] == "Clean up inbox newsletters"
    assert len(d["run"]["logs"]) > 0
    assert "spoken_status" in d


def test_swarm_start_and_stop_run(authed_client):
    client, app_module = authed_client
    headers = {"Authorization": "Bearer test-token"}

    # 1. Start a new run
    res_start = client.post(
        "/os1/runs",
        headers=headers,
        json={"label": "Research ferry timetables to Larkspur", "duration_seconds": 10.0},
    )
    assert res_start.status_code == 200
    run = res_start.json()["run"]
    assert run["status"] == "running"
    run_id = run["id"]

    # 2. Stop the run
    res_stop = client.post(f"/os1/runs/{run_id}/stop", headers=headers)
    assert res_stop.status_code == 200
    stopped = res_stop.json()["run"]
    assert stopped["status"] == "cancelled"
    assert "Stopped by user" in stopped["stage"]

    # Verify state reflects cancellation
    res_check = client.get(f"/os1/runs/{run_id}", headers=headers)
    assert res_check.json()["run"]["status"] == "cancelled"


def test_swarm_chat_voice_interactions(authed_client):
    client, app_module = authed_client
    headers = {"Authorization": "Bearer test-token"}

    # 1. Spoken status query: "How is Clean up inbox newsletters going?"
    res_status = client.post(
        "/os1/chat",
        headers=headers,
        json={"phrase": "How is Clean up inbox newsletters going?"},
    )
    assert res_status.status_code == 200
    d = res_status.json()
    assert d["target"] == "swarm"
    assert d["action"] == "status"
    assert "Clean up inbox newsletters" in d["reply"]

    # 2. Spoken stop command: "Stop Clean up inbox newsletters"
    res_stop = client.post(
        "/os1/chat",
        headers=headers,
        json={"phrase": "Stop Clean up inbox newsletters"},
    )
    assert res_stop.status_code == 200
    d_stop = res_stop.json()
    assert d_stop["target"] == "swarm"
    assert d_stop["action"] == "stop"
    assert "stopped" in d_stop["reply"].lower()

    # 3. Spoken delegation: "Can you research Sausalito hotel rates in the background?"
    res_delegate = client.post(
        "/os1/chat",
        headers=headers,
        json={"phrase": "Can you research Sausalito hotel rates in the background?"},
    )
    assert res_delegate.status_code == 200
    d_del = res_delegate.json()
    assert d_del["target"] == "swarm"
    assert d_del["action"] == "start"
    assert "Sausalito hotel rates" in d_del["reply"]
    assert d_del["surface"] == "swarm"


def test_swarm_clear_done(authed_client):
    client, app_module = authed_client
    headers = {"Authorization": "Bearer test-token"}

    # run_103 is done by default
    res = client.post("/os1/runs/clear-done", headers=headers)
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # run_103 should no longer be in active runs
    runs = client.get("/os1/runs", headers=headers).json()["runs"]
    active_ids = [r["id"] for r in runs]
    assert "run_103" not in active_ids
