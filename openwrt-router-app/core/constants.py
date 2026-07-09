from __future__ import annotations

from pathlib import Path

APP_NAME = "OpenWrt Router Diagnostic App"
APP_INTERNAL_NAME = "openwrt-router-app"
APP_VERSION = "0.1.0"

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
COMMANDS_FILE = CONFIG_DIR / "commands.yaml"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"

EVIDENCE_DIR = BASE_DIR / "evidence"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_PATH = BASE_DIR / "history.db"

CONNECTION_TEST_COMMAND = "echo IDAF_ROUTER_CONNECTION_OK"
CONNECTION_TEST_MARKER = "IDAF_ROUTER_CONNECTION_OK"

# Streamlit session_state keys shared across app.py and pages/*.py
SESSION_CONNECTION_CONFIG = "connection_config"
SESSION_CONNECTION_STATUS = "connection_status"
SESSION_LAST_RESULT = "last_result"
