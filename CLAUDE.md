# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository currently contains only a specification document — [Prompt_Claude_Mini_App_OpenWrt.md](Prompt_Claude_Mini_App_OpenWrt.md) — and no implementation yet. That document is the full functional/technical spec for a project called **OpenWrt Router Diagnostic App** (internal name `openwrt-router-app`), which is the first module of a master's thesis on observability/diagnostics architecture for IoT networks. The thesis scope is intentionally limited in this phase to the OpenWrt router only; ESP32 nodes, Thread/OpenThread, MQTT, Prometheus, Grafana and ThingsBoard are explicitly out of scope for now and must not be implemented — the architecture should just leave room for them later.

When asked to build this project, treat `Prompt_Claude_Mini_App_OpenWrt.md` as the source of truth and follow it closely rather than improvising a different structure. Below is a condensed map of the decisions that matter most; consult the full document for exact YAML/JSON shapes and wording of user-facing messages (many are specified in Spanish and should stay in Spanish).

## Intended stack and commands

- Python 3.11+, Streamlit (UI), Paramiko (SSH), Pydantic (models/validation), SQLAlchemy + SQLite (history), PyYAML (config), stdlib `logging`, pytest (tests).
- Explicitly excluded for this phase: React, Node.js, Django, Flask, Redis, Celery, Kafka, Docker, PostgreSQL, any external DB or cloud service.

Once the app exists, the expected commands are:

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
streamlit run app.py         # run the app
pytest -v                    # run all tests
```

There is no single-test command specified in the spec; use standard pytest node-id selection (`pytest tests/test_parsers.py::test_name -v`) once tests exist.

## Architecture (to be built)

```text
openwrt-router-app/
├── app.py                      # Streamlit entrypoint
├── pages/                      # Streamlit multipage UI: Conexion, Comandos, Historial, Acerca_de
├── core/                       # ssh_client, command_service, execution_service, exceptions, constants
├── models/                     # Pydantic models: connection, command, execution
├── parsers/                    # base + one parser per output format (json/text/lines/uptime/free/df)
├── repositories/                # database.py + execution_repository.py (SQLite persistence)
├── config/                     # commands.yaml (allow-listed commands), settings.yaml
├── evidence/                   # JSON evidence files, partitioned evidence/YYYY/MM/DD/<execution_id>.json
├── logs/                       # rotating app.log
└── tests/
```

Data flow for the primary use case (this is the one path that must work end-to-end first): Streamlit UI → SSH connect (`ssh_client.py`) → execute allow-listed command (`command_service.py` + `execution_service.py`) → parse output (`parsers/`) → persist to SQLite (`repositories/`) → write JSON evidence file → render result in UI. The layering is deliberate — connection, execution, parsing, storage, and presentation are separate concerns and should stay in their respective modules rather than collapsing into `app.py`.

### Commands are data, not code

There is no free-text command field anywhere in the UI. Every executable command is declared in `config/commands.yaml` with `id`, `name`, `description`, `command`, `parser`, `category`, `timeout`, `enabled`. `command_service.py` loads and validates this file, filters to `enabled: true`, and is the only path by which a command reaches the SSH client — never build a command string from user input.

### Parsers share one interface

Every parser implements `BaseParser.parse(raw_output: str) -> dict` (see `parsers/base.py`). If a parser fails, the raw stdout must still be preserved on the result and the execution status should degrade to `COMPLETED_WITH_WARNINGS` rather than losing data or raising to the user.

### Execution status model

Executions move through: `CREATED → CONNECTING → RUNNING → COMPLETED | COMPLETED_WITH_WARNINGS | FAILED | TIMEOUT`. `COMPLETED` requires exit code 0 and no relevant stderr; nonzero exit code or connection error → `FAILED`; exceeded timeout → `TIMEOUT`.

### Errors

Custom exception hierarchy rooted at `RouterAppError` (see spec §15: `SSHConnectionError`, `SSHAuthenticationError`, `SSHTimeoutError`, `CommandNotAllowedError`, `CommandExecutionError`, `ParserError`). The UI shows friendly Spanish messages (e.g. "No fue posible contactar el router...") and never surfaces full stack traces to the end user.

## Security constraints (non-negotiable, per spec §3/§10)

- No free-form/arbitrary command execution — allow-list only, no `shell=True`, no concatenating user input into commands.
- The app never modifies router configuration and never runs destructive commands.
- The SSH password lives only in Streamlit session memory for the duration of the session: never persisted to SQLite, JSON evidence, YAML, logs, or any other durable store. Logs must never contain passwords, private keys, tokens, or other credentials, and evidence JSON must never include them either.
- Host key policy is configurable (`ssh.host_key_policy: auto|reject` in `config/settings.yaml`). `AutoAddPolicy` is acceptable for the MVP lab setting but must be encapsulated with a comment noting it's lab-only, with a strict/reject mode available.
- Don't assume every OpenWrt command/tool is available on every target device/version — handle missing commands gracefully.

## Testing approach

Tests must not open real SSH connections — mock Paramiko/the SSH client. Per spec §16, coverage should include: YAML command loading, command validation and `enabled` filtering, lookup by id, each parser (json/uptime/free/df), Pydantic model validation, SQLite persistence, evidence-file generation, and error handling paths.
