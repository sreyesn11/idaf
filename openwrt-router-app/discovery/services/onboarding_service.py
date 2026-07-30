from __future__ import annotations

import logging
from datetime import datetime

from core.exceptions import InventoryDeviceNotFoundError
from discovery.correlation.merge_planner import MergePlanner
from discovery.enums import DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType
from discovery.models import MergePreview
from discovery.repositories.inventory_device_repository import InventoryDeviceRecord, InventoryDeviceRepository

logger = logging.getLogger(__name__)


class OnboardingService:
    """Implements the discover -> approve pipeline actions from spec section 12:
    approve, edit-then-approve, ignore, restore, and merge. Never creates SSH
    credentials — approving a device only changes its inventory status."""

    def __init__(
        self,
        inventory_device_repository: InventoryDeviceRepository,
        merge_planner: MergePlanner,
    ) -> None:
        self._devices = inventory_device_repository
        self._merge_planner = merge_planner

    def approve(self, device_id: int) -> InventoryDeviceRecord:
        now = datetime.now().astimezone()
        record = self._devices.update_status(
            device_id, discovery_status=DeviceDiscoveryStatus.APPROVED, approved_at=now
        )
        logger.info("Dispositivo aprobado device_id=%s alias=%s", device_id, record.alias)
        return record

    def edit_and_approve(
        self,
        device_id: int,
        *,
        name: str,
        alias: str,
        device_type: DeviceType,
    ) -> InventoryDeviceRecord:
        self._devices.update_fields(device_id, name=name, alias=alias, device_type=device_type)
        return self.approve(device_id)

    def ignore(self, device_id: int) -> InventoryDeviceRecord:
        now = datetime.now().astimezone()
        record = self._devices.update_status(
            device_id, discovery_status=DeviceDiscoveryStatus.IGNORED, ignored_at=now
        )
        logger.info("Dispositivo ignorado device_id=%s alias=%s", device_id, record.alias)
        return record

    def restore(self, device_id: int) -> InventoryDeviceRecord:
        """Bring an ignored device back to the pending-approval queue."""
        record = self._devices.get_by_id(device_id)
        if record is None:
            raise InventoryDeviceNotFoundError(f"device_id={device_id}")
        target_status = (
            DeviceDiscoveryStatus.APPROVED
            if record.management_status == DeviceManagementStatus.MANAGED.value
            else DeviceDiscoveryStatus.PENDING_APPROVAL
        )
        record = self._devices.update_status(device_id, discovery_status=target_status)
        logger.info("Dispositivo restaurado device_id=%s alias=%s estado=%s", device_id, record.alias, target_status)
        return record

    def preview_merge(self, source_device_id: int, target_device_id: int) -> MergePreview:
        return self._merge_planner.preview(source_device_id, target_device_id)

    def merge(self, source_device_id: int, target_device_id: int, *, confirmed: bool) -> None:
        self._merge_planner.merge(source_device_id, target_device_id, confirmed=confirmed)
        logger.info(
            "Dispositivos fusionados source_device_id=%s target_device_id=%s", source_device_id, target_device_id
        )
