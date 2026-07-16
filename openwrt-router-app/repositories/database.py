from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.constants import DATABASE_PATH


class Base(DeclarativeBase):
    pass


def get_engine(database_path: Path = DATABASE_PATH) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path.as_posix()}", future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    # No Alembic in this project: create_all only creates missing tables, it
    # never alters existing ones, so columns added after a table already
    # shipped (e.g. device_id) need this small idempotent ALTER TABLE step.
    _ensure_column(engine, "executions", "device_id", "INTEGER")
    _ensure_column(engine, "diagnostics", "device_id", "INTEGER")
    _ensure_column(engine, "diagnostics", "target_device_id", "TEXT")


def _ensure_column(engine: Engine, table: str, column: str, sql_type: str) -> None:
    with engine.connect() as conn:
        if not conn.dialect.has_table(conn, table):
            return
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
            conn.commit()


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
