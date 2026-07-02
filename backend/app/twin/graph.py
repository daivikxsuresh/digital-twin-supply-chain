"""
Twin graph — the in-memory network model of the supply chain.

Nodes: suppliers, facilities, and demand regions.
Edges: observed flows (shipments joined to orders for $ value) plus a
supplier→facility country-match heuristic until PO/BOM data arrives (Phase 7).

Node ids are namespaced strings ("supplier:S-001", "facility:F-001",
"region:East") so the three entity types can share one DiGraph.
"""

from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import structlog

logger = structlog.get_logger(__name__)

NODE_SUPPLIER = "supplier"
NODE_FACILITY = "facility"
NODE_REGION = "region"


def supplier_node(external_id: str) -> str:
    return f"{NODE_SUPPLIER}:{external_id}"


def facility_node(external_id: str) -> str:
    return f"{NODE_FACILITY}:{external_id}"


def region_node(name: str) -> str:
    return f"{NODE_REGION}:{name}"


@dataclass
class NodeExposure:
    """How much of total network flow touches this node."""

    node_id: str
    throughput_value: float
    exposure_share: float  # 0..1 share of total edge value
    daily_value: float  # avg $ flow per day through this node


@dataclass
class TwinGraph:
    """Wraps a NetworkX DiGraph with supply-chain-specific queries."""

    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    flow_window_days: int = 30  # window the edge values were observed over

    # ------------------------------------------------------------------ build

    def add_supplier(self, external_id: str, **attrs: Any) -> str:
        node_id = supplier_node(external_id)
        self.graph.add_node(node_id, node_type=NODE_SUPPLIER, external_id=external_id, **attrs)
        return node_id

    def add_facility(self, external_id: str, **attrs: Any) -> str:
        node_id = facility_node(external_id)
        self.graph.add_node(node_id, node_type=NODE_FACILITY, external_id=external_id, **attrs)
        return node_id

    def add_region(self, name: str, **attrs: Any) -> str:
        node_id = region_node(name)
        self.graph.add_node(node_id, node_type=NODE_REGION, name=name, **attrs)
        return node_id

    def add_flow(self, src: str, dst: str, value: float = 0.0, shipments: int = 1) -> None:
        """Accumulate an observed flow onto the src→dst edge."""
        if self.graph.has_edge(src, dst):
            edge = self.graph.edges[src, dst]
            edge["value"] += value
            edge["shipments"] += shipments
        else:
            self.graph.add_edge(src, dst, value=value, shipments=shipments)

    # ---------------------------------------------------------------- queries

    @property
    def total_edge_value(self) -> float:
        return sum(d["value"] for _, _, d in self.graph.edges(data=True))

    def node_throughput(self, node_id: str) -> float:
        """Total $ value flowing in + out of a node."""
        in_value = sum(d["value"] for _, _, d in self.graph.in_edges(node_id, data=True))
        out_value = sum(d["value"] for _, _, d in self.graph.out_edges(node_id, data=True))
        return in_value + out_value

    def exposure(self, node_id: str) -> NodeExposure:
        """
        Share of network flow that passes through a node — this replaces the
        demo's random triangular(0.15, 0.35, 0.6) exposure draw with the
        node's real observed share.

        Each unit of edge value is counted once at its origin and once at its
        destination, so throughput is divided by 2× total edge value to keep
        exposure_share in [0, 1].
        """
        if node_id not in self.graph:
            raise KeyError(f"Node not in twin graph: {node_id}")
        total = self.total_edge_value
        throughput = self.node_throughput(node_id)
        share = min(1.0, throughput / (2 * total)) if total > 0 else 0.0
        daily = throughput / self.flow_window_days if self.flow_window_days else 0.0
        return NodeExposure(
            node_id=node_id,
            throughput_value=throughput,
            exposure_share=share,
            daily_value=daily,
        )

    def critical_nodes(self, top_n: int = 5) -> list[NodeExposure]:
        """Nodes ranked by exposure — the ones a disruption hurts most."""
        exposures = [self.exposure(n) for n in self.graph.nodes]
        exposures.sort(key=lambda e: e.exposure_share, reverse=True)
        return exposures[:top_n]

    def single_points_of_failure(self) -> list[str]:
        """Facilities whose removal disconnects a region from all supply."""
        spofs: list[str] = []
        regions = [n for n, d in self.graph.nodes(data=True) if d["node_type"] == NODE_REGION]
        facilities = [n for n, d in self.graph.nodes(data=True) if d["node_type"] == NODE_FACILITY]
        for fac in facilities:
            pruned = nx.restricted_view(self.graph, [fac], [])
            for reg in regions:
                if self.graph.in_degree(reg) > 0 and pruned.in_degree(reg) == 0:
                    spofs.append(fac)
                    break
        return spofs

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            counts[data["node_type"]] = counts.get(data["node_type"], 0) + 1
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_counts": counts,
            "total_flow_value": round(self.total_edge_value, 2),
        }


def build_twin_graph(
    suppliers: list[dict],
    facilities: list[dict],
    shipments: list[dict],
    orders: list[dict],
    flow_window_days: int = 30,
) -> TwinGraph:
    """
    Assemble the twin graph from plain dict rows (as returned by the DB layer).

    Expected keys:
      suppliers:  external_id, name, country
      facilities: external_id, name, facility_type, country, region
      shipments:  external_id, order_id, origin_facility_id, destination_country
      orders:     external_id, region, total_amount
    """
    twin = TwinGraph(flow_window_days=flow_window_days)

    for s in suppliers:
        twin.add_supplier(s["external_id"], name=s.get("name"), country=s.get("country"))
    for f in facilities:
        twin.add_facility(
            f["external_id"],
            name=f.get("name"),
            facility_type=f.get("facility_type"),
            country=f.get("country"),
            region=f.get("region"),
        )

    # Demand-side edges: facility → destination region, valued by order amount
    order_value = {o["external_id"]: o.get("total_amount") or 0.0 for o in orders}
    order_region = {o["external_id"]: o.get("region") for o in orders}
    for sh in shipments:
        origin = sh.get("origin_facility_id")
        if not origin:
            continue
        src = facility_node(origin)
        if src not in twin.graph:
            src = twin.add_facility(origin, name=None, facility_type=None)
        region = order_region.get(sh.get("order_id")) or sh.get("destination_country") or "UNKNOWN"
        dst = region_node(str(region))
        if dst not in twin.graph:
            twin.add_region(str(region))
        twin.add_flow(src, dst, value=order_value.get(sh.get("order_id"), 0.0))

    # Supply-side edges: country-match heuristic until real PO data (Phase 7).
    # A supplier is assumed to feed facilities in its own country, splitting
    # the facility's outbound value evenly across its in-country suppliers.
    fac_out = {
        n: sum(d["value"] for _, _, d in twin.graph.out_edges(n, data=True))
        for n, data in twin.graph.nodes(data=True)
        if data["node_type"] == NODE_FACILITY
    }
    suppliers_by_country: dict[str, list[str]] = {}
    for s in suppliers:
        if s.get("country"):
            suppliers_by_country.setdefault(s["country"], []).append(supplier_node(s["external_id"]))
    for f in facilities:
        matched = suppliers_by_country.get(f.get("country") or "", [])
        if not matched:
            continue
        fac = facility_node(f["external_id"])
        share = fac_out.get(fac, 0.0) / len(matched)
        for sup in matched:
            twin.add_flow(sup, fac, value=share)

    logger.info("twin_graph.built", **twin.summary())
    return twin
