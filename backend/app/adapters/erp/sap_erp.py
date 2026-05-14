"""
SAP ERP Adapter — Stub
======================
Blueprint for the SAP S/4HANA OData v4 integration.
Implement this when onboarding a SAP client.

SAP OData v4 endpoints to implement
-------------------------------------
Orders:
  GET /sap/opu/odata4/sap/api_salesorder_srv/srvd_a2x/sap/salesorder/0001/SalesOrder
  Filter: $filter=CreationDate ge <date> and SalesOrderType eq 'OR'
  Key fields: SalesOrder, SoldToParty, TotalNetAmount, OverallDeliveryStatus

Order Items:
  GET /sap/opu/odata4/.../SalesOrderItem?$filter=SalesOrder eq '<id>'
  Key fields: SalesOrderItem, Material, RequestedQuantity, NetAmount

Deliveries / Shipments:
  GET /sap/opu/odata4/sap/api_outbound_delivery_srv/...
  Key fields: DeliveryDocument, ShippingPoint, PlannedGoodsIssueDate, ActualGoodsMovementDate

Inventory:
  GET /sap/opu/odata4/sap/api_material_stock_srv/...
  Key fields: Material, Plant, StorageLocation, MatlStkQtyInMatlBaseUnit

Authentication: OAuth 2.0 client credentials via SAP BTP
Base URL pattern: https://<tenant>.s4hana.ondemand.com
"""

from collections.abc import AsyncIterator

from app.adapters.base import BaseERPAdapter
from app.adapters.canonical_models import (
    CanonicalFacility,
    CanonicalInventorySnapshot,
    CanonicalOrder,
    CanonicalRecommendation,
    CanonicalShipment,
    CanonicalSupplier,
    WritebackResult,
)


class SAPERPAdapter(BaseERPAdapter):
    source_system = "SAP_ERP"

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret

    async def fetch_orders(self) -> AsyncIterator[CanonicalOrder]:
        raise NotImplementedError(
            "SAP order fetch not yet implemented. "
            "See module docstring for OData v4 endpoint details."
        )
        yield  # makes this an async generator

    async def fetch_inventory_snapshots(self) -> AsyncIterator[CanonicalInventorySnapshot]:
        raise NotImplementedError(
            "SAP inventory fetch not yet implemented. "
            "See module docstring for OData v4 endpoint details."
        )
        yield

    async def fetch_suppliers(self) -> AsyncIterator[CanonicalSupplier]:
        raise NotImplementedError("SAP supplier fetch not yet implemented.")
        yield

    async def fetch_facilities(self) -> AsyncIterator[CanonicalFacility]:
        raise NotImplementedError("SAP facility fetch not yet implemented.")
        yield

    async def push_recommendation(
        self, recommendation: CanonicalRecommendation
    ) -> WritebackResult:
        raise NotImplementedError(
            "SAP writeback not yet implemented. "
            "Target: POST to SAP Purchase Order API or Production Order change endpoint."
        )
