from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import DeviceAliasAlreadyExistsError, DeviceNotFoundError
from models.device import DeviceConfig
from repositories.database import get_engine
from repositories.device_repository import DeviceRecord, DeviceRepository


@pytest.fixture()
def repository(tmp_path: Path) -> DeviceRepository:
    engine = get_engine(tmp_path / "history.db")
    return DeviceRepository(engine=engine)


def _make_device(alias: str = "lab-1", host: str = "192.168.1.1") -> DeviceConfig:
    return DeviceConfig(alias=alias, host=host, username="root")


def test_no_password_column_on_device_record() -> None:
    assert "password" not in DeviceRecord.__table__.columns


def test_create_and_list_all(repository: DeviceRepository) -> None:
    repository.create(_make_device())
    devices = repository.list_all()
    assert len(devices) == 1
    assert devices[0].alias == "lab-1"
    assert devices[0].host == "192.168.1.1"


def test_duplicate_alias_raises(repository: DeviceRepository) -> None:
    repository.create(_make_device(alias="lab-1"))
    with pytest.raises(DeviceAliasAlreadyExistsError):
        repository.create(_make_device(alias="lab-1", host="192.168.1.2"))


def test_get_by_id(repository: DeviceRepository) -> None:
    created = repository.create(_make_device())
    fetched = repository.get_by_id(created.id)
    assert fetched is not None
    assert fetched.alias == "lab-1"


def test_get_by_id_missing_returns_none(repository: DeviceRepository) -> None:
    assert repository.get_by_id(999) is None


def test_update(repository: DeviceRepository) -> None:
    created = repository.create(_make_device())
    repository.update(created.id, _make_device(alias="lab-1-renamed", host="192.168.1.99"))
    updated = repository.get_by_id(created.id)
    assert updated.alias == "lab-1-renamed"
    assert updated.host == "192.168.1.99"


def test_update_missing_raises(repository: DeviceRepository) -> None:
    with pytest.raises(DeviceNotFoundError):
        repository.update(999, _make_device())


def test_delete(repository: DeviceRepository) -> None:
    created = repository.create(_make_device())
    repository.delete(created.id)
    assert repository.list_all() == []
