from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from repositories.database import get_engine, init_db


def _create_legacy_executions_table_without_device_id(engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id VARCHAR UNIQUE,
                    host VARCHAR
                )
                """
            )
        )
        conn.execute(text("INSERT INTO executions (execution_id, host) VALUES ('exec-1', '192.168.1.1')"))
        conn.commit()


def test_init_db_adds_device_id_column_to_legacy_table(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "legacy.db")
    _create_legacy_executions_table_without_device_id(engine)

    init_db(engine)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(executions)"))}
        assert "device_id" in columns

        row = conn.execute(text("SELECT execution_id, host, device_id FROM executions")).first()
        assert row.execution_id == "exec-1"
        assert row.host == "192.168.1.1"
        assert row.device_id is None


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "history.db")
    init_db(engine)
    init_db(engine)  # must not raise on a second call

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(executions)"))}
        assert "device_id" in columns
