from __future__ import annotations

from pathlib import Path

APP_NAME = "OpenWrt Router Diagnostic App"
APP_INTERNAL_NAME = "openwrt-router-app"
APP_VERSION = "0.2.0"

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
COMMANDS_FILE = CONFIG_DIR / "commands.yaml"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
DIAGNOSTIC_THRESHOLDS_FILE = CONFIG_DIR / "diagnostic_thresholds.yaml"

EVIDENCE_DIR = BASE_DIR / "evidence"
EXECUTIONS_EVIDENCE_DIR = EVIDENCE_DIR / "executions"
DIAGNOSTICS_EVIDENCE_DIR = EVIDENCE_DIR / "diagnostics"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_PATH = BASE_DIR / "history.db"

CONNECTION_TEST_COMMAND = "echo IDAF_ROUTER_CONNECTION_OK"
CONNECTION_TEST_MARKER = "IDAF_ROUTER_CONNECTION_OK"

# Streamlit session_state keys shared across app.py and pages/*.py
SESSION_CONNECTED_DEVICES = "connected_devices"  # dict[str, ConnectedDevice]
SESSION_ACTIVE_DEVICE_KEY = "active_device_key"  # currently active device in Comandos
SESSION_ADHOC_DEVICE_KEY = "adhoc"  # fixed key for the quick/unsaved connection
SESSION_DIAGNOSTIC_RESULTS = "diagnostic_results"  # dict[str, dict] latest diagnostic JSON per device
SESSION_LAST_RESULT = "last_result"
SESSION_LAST_DIAGNOSTIC = "last_diagnostic"
SESSION_PASSWORD_WIDGET_KEY = "password_input"
