from __future__ import annotations

# Import every ORM-defining module so constructing any single discovery
# repository (e.g. just InventoryDeviceRepository in a test) still registers
# the whole discovery schema on Base.metadata before init_db()'s
# create_all() runs — mirrors the same defensive re-export device_repository
# already does for the diagnostics/executions tables.
from discovery.repositories import (  # noqa: F401
    address_repository,
    identifier_repository,
    interface_repository,
    inventory_device_repository,
    observation_repository,
    topology_link_repository,
)
