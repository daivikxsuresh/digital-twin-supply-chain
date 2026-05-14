from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.adapters.canonical_models import (
    CanonicalFacility,
    CanonicalInventorySnapshot,
    CanonicalOrder,
    CanonicalShipment,
    CanonicalSupplier,
    WritebackResult,
    CanonicalRecommendation,
)


class BaseERPAdapter(ABC):
    """
    Abstract contract for all ERP integrations.

    To add a new ERP (SAP, NetSuite, Oracle, etc.) implement all methods below
    and register the adapter in adapters/__init__.py ADAPTER_REGISTRY.
    Each method must yield canonical models — the rest of the system never
    touches raw ERP data.
    """

    source_system: str  # override in subclass, e.g. "SAP_PROD"

    @abstractmethod
    def fetch_orders(self) -> AsyncIterator[CanonicalOrder]:
        """Yield all orders from the ERP, newest first."""
        ...

    @abstractmethod
    def fetch_inventory_snapshots(self) -> AsyncIterator[CanonicalInventorySnapshot]:
        """Yield current inventory snapshots across all facilities and SKUs."""
        ...

    @abstractmethod
    def fetch_suppliers(self) -> AsyncIterator[CanonicalSupplier]:
        """Yield all active suppliers."""
        ...

    @abstractmethod
    def fetch_facilities(self) -> AsyncIterator[CanonicalFacility]:
        """Yield all facilities (factories, DCs, stores, ports)."""
        ...

    @abstractmethod
    async def push_recommendation(
        self, recommendation: CanonicalRecommendation
    ) -> WritebackResult:
        """
        Push a twin recommendation back into the ERP.
        Must be idempotent — safe to call twice with the same recommendation_id.
        """
        ...


class BaseTMSAdapter(ABC):
    """
    Abstract contract for all TMS (Transportation Management System) integrations.

    Follow the same pattern as BaseERPAdapter — implement, register, done.
    """

    source_system: str  # override in subclass, e.g. "ORACLE_TMS"

    @abstractmethod
    def fetch_shipments(self) -> AsyncIterator[CanonicalShipment]:
        """Yield all active and recent shipments."""
        ...

    @abstractmethod
    async def fetch_shipment_location(self, shipment_external_id: str) -> dict:
        """
        Return current GPS/location data for a single shipment.
        Expected keys: latitude, longitude, timestamp, status_description.
        """
        ...

    @abstractmethod
    async def push_shipment_instruction(
        self, shipment_external_id: str, instruction: dict
    ) -> WritebackResult:
        """
        Push a routing or reroute instruction to the TMS.
        Must be idempotent on shipment_external_id + instruction hash.
        """
        ...
