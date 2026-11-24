"""Tests for Real Mac and Mobile (Android + iOS) Automation Engines."""

import importlib
import pytest
from fastapi.testclient import TestClient

from os1_orchestrator.mac_automation import mac_automation
from os1_orchestrator.mobile_automation import mobile_automation


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS1_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("OS1_CLIENT_TOKEN", "test-token")
    import os1_orchestrator.app as app_module
    importlib.reload(app_module)
    return TestClient(app_module.app, headers={"Authorization": "Bearer test-token"})


def test_mac_automation_queries():
    """Verify real Mac automation queries running apps & frontmost process."""
    front = mac_automation.get_frontmost_app()
    assert isinstance(front, dict)
    assert "app" in front

    apps = mac_automation.list_running_apps()
    assert isinstance(apps, list)

    res = mac_automation.execute_tool("status", {})
    assert "app" in res


def test_mobile_automation_android_discovery():
    """Verify real Android device discovery and ADB communication."""
    devices = mobile_automation.list_android_devices()
    assert isinstance(devices, list)

    ios_devices = mobile_automation.list_ios_devices()
    assert isinstance(ios_devices, list)

    # Dispatcher test
    dev_res = mobile_automation.execute_mobile_tool("devices", {})
    assert dev_res["ok"] is True
    assert "android" in dev_res
    assert "ios" in dev_res


def test_mobile_api_endpoints(client):
    """Verify /os1/mobile/status and /os1/mac endpoints."""
    resp = client.get("/os1/mobile/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "android_devices" in data
    assert "ios_devices" in data
    assert "available_avds" in data

    # Mac info
    mac_resp = client.get("/os1/mac/info")
    assert mac_resp.status_code == 200
    mac_data = mac_resp.json()
    assert mac_data["ok"] is True
    assert "model" in mac_data
    assert "os_version" in mac_data

    # Mac screenshot
    shot_resp = client.get("/os1/mac/screenshot")
    assert shot_resp.status_code == 200
    assert shot_resp.headers["content-type"] == "image/jpeg"
    assert len(shot_resp.content) > 1000
