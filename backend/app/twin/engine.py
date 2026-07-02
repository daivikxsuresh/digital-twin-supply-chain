"""
Twin engine — the orchestrator that owns the in-memory twin graph, per-node
state machines, and scenario simulation.

Lifecycle:
  * rebuild()       — full reload of the graph from PostgreSQL
  * handle_event()  — called by Kafka processors on ingest; marks the graph
                      dirty so the next read triggers a rebuild (cheap and
                      correct; incremental updates come later if needed)
  * run_scenario()  — disrupt a node, run Monte Carlo, return the impact

Exposed as the module-level singleton `twin_engine`, mirroring how the
ingest processors are wired in main.py.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.twin.graph import TwinGraph, build_twin_graph
from app.twin.simulation.monte_carlo import SimulationResult, run_monte_carlo
from app.twin.state import StateRegistry

logger = structlog.get_logger(__name__)

# Baseline OTIF % used until Phase 3 computes it from delivered shipments
DEFAULT_BASE_OTIF = 94.2

# Events that change network structure/flows and require a graph rebuild
_GRAPH_EVENT_TYPES = {"order", "shipment"}


class TwinEngine:
    def __init__(self, flow_window_days: int = 30) -> None:
        self.flow_window_days = flow_window_days
        self.twin: TwinGraph | None = None
        self.states = StateRegistry()
        self._dirty = True
        self.last_built_at: datetime | None = None

    # ----------------------------------------------------------------- build

    async def rebuild(self) -> TwinGraph:
        """Reload the full twin graph from the database."""
        from app.db.session import AsyncSessionLocal
        from app.models.facility import Facility
        from app.models.order import Order
        from app.models.shipment import Shipment
        from app.models.supplier import Supplier

        async with AsyncSessionLocal() as session:
            suppliers = (await session.execute(select(Supplier))).scalars().all()
            facilities = (await session.execute(select(Facility))).scalars().all()
            shipments = (await session.execute(select(Shipment))).scalars().all()
            orders = (await session.execute(select(Order))).scalars().all()

        self.twin = build_twin_graph(
            suppliers=[
                {"external_id": s.external_id, "name": s.name, "country": s.country}
                for s in suppliers
            ],
            facilities=[
                {
                    "external_id": f.external_id,
                    "name": f.name,
                    "facility_type": f.facility_type,
                    "country": f.country,
                    "region": f.region,
                }
                for f in facilities
            ],
            shipments=[
                {
                    "external_id": sh.external_id,
                    "order_id": sh.order_id,
                    "origin_facility_id": sh.origin_facility_id,
                    "destination_country": sh.destination_country,
                }
                for sh in shipments
            ],
            orders=[
                {"external_id": o.external_id, "region": o.region, "total_amount": o.total_amount}
                for o in orders
            ],
            flow_window_days=self.flow_window_days,
        )
        self._dirty = False
        self.last_built_at = datetime.now(timezone.utc)
        logger.info("twin_engine.rebuilt", **self.twin.summary())
        return self.twin

    async def get_twin(self) -> TwinGraph:
        """Return the current graph, rebuilding if ingest marked it dirty."""
        if self.twin is None or self._dirty:
            await self.rebuild()
        assert self.twin is not None
        return self.twin

    async def handle_event(self, event: dict) -> None:
        """Ingest hook — called by Kafka processors after each upsert."""
        event_type = str(event.get("event_type", "")).lower()
        if any(t in event_type for t in _GRAPH_EVENT_TYPES):
            self._dirty = True

    # ------------------------------------------------------------- simulation

    async def run_scenario(
        self,
        node_id: str,
        severity: float,
        duration_days: float,
        trials: int = 1000,
        base_otif: float = DEFAULT_BASE_OTIF,
        seed: int | None = None,
    ) -> SimulationResult:
        """
        Disrupt one node and simulate the network impact.

        Marks the node DISRUPTED in its state machine, feeds its real
        exposure and daily $ value from the graph into the Monte Carlo run.
        """
        twin = await self.get_twin()
        exposure = twin.exposure(node_id)  # raises KeyError for unknown nodes

        node_state = self.states.get(node_id)
        if node_state.state != "disrupted":
            node_state.disrupt()

        # A node with no observed flow gives the sim nothing to work with —
        # fall back to the demo distributions rather than simulating zero impact.
        has_flow = exposure.throughput_value > 0
        result = run_monte_carlo(
            base_otif=base_otif,
            severity=severity,
            duration_days=duration_days,
            trials=trials,
            node_exposure=exposure.exposure_share if has_flow else None,
            node_daily_value=exposure.daily_value if has_flow else None,
            seed=seed,
        )
        logger.info(
            "twin_engine.scenario_complete",
            node_id=node_id,
            severity=severity,
            duration_days=duration_days,
            used_graph_exposure=has_flow,
        )
        return result

    async def resolve_scenario(self, node_id: str) -> None:
        """Walk a disrupted node back to normal (recovery complete)."""
        node_state = self.states.get(node_id)
        if node_state.state == "disrupted":
            node_state.begin_recovery()
        if node_state.state == "recovering":
            node_state.recover()

    # ---------------------------------------------------------------- status

    async def status(self) -> dict:
        twin = await self.get_twin()
        return {
            "graph": twin.summary(),
            "last_built_at": self.last_built_at.isoformat() if self.last_built_at else None,
            "impacted_nodes": self.states.impacted_nodes(),
            "critical_nodes": [
                {
                    "node_id": e.node_id,
                    "exposure_share": round(e.exposure_share, 4),
                    "daily_value": round(e.daily_value, 2),
                }
                for e in twin.critical_nodes()
            ],
        }


# Module-level singleton, mirroring the ingest processor wiring
twin_engine = TwinEngine()
