"""Tests for OS-aware installer, preflight checker, and JIT model installer."""

from os1_orchestrator.installer import Os1Installer


def test_installer_preflight_report():
    installer = Os1Installer(required_disk_gb=4.5)
    report = installer.get_preflight_report()

    assert report.os_platform in ["macOS", "Windows", "Linux", "Android"]
    assert report.total_disk_gb > 0
    assert report.free_disk_gb > 0
    assert report.fallback_offline_ready is True
    assert len(report.installed_models) >= 4
    assert len(report.solution_label) > 0


def test_os_specific_model_filtering():
    installer = Os1Installer()
    report = installer.get_preflight_report()

    # If on macOS, Windows UI Automation should NOT be active
    if report.os_platform == "macOS":
        win_mod = next((m for m in report.available_jit_modules if m.key == "windows_ui_automation"), None)
        assert win_mod is None or win_mod.is_active is False

    # If on Android, desktop automation should NOT be active
    if report.os_platform == "Android":
        mac_mod = next((m for m in report.available_jit_modules if m.key == "macos_accessibility"), None)
        assert mac_mod is None or mac_mod.is_active is False


def test_jit_model_activation_on_teamviewer_intent():
    installer = Os1Installer()

    # Normal prompt does not trigger JIT
    assert installer.check_and_trigger_jit("What is the weather today?") is None

    # TeamViewer / Remote PC prompt triggers JIT
    triggered = installer.check_and_trigger_jit("Can you control my PC over TeamViewer please?")
    assert triggered == "uitars_remote_pc"
    assert "uitars_remote_pc" in installer.installed_jit


def test_installer_cleanup_execution():
    installer = Os1Installer()
    res = installer.clean_system_space()

    assert res["status"] == "success"
    assert "free_disk_gb" in res
    assert res["os_platform"] in ["macOS", "Windows", "Linux", "Android"]
