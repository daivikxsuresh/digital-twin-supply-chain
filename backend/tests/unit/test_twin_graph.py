"""Twin graph construction and exposure query tests."""

import pytest

from app.twin.graph import build_twin_graph, facility_node, region_node, supplier_node

SUPPLIERS = [
    {"external_id": "S-1", "name": "Acme Metals", "country": "US"},
    {"external_id": "S-2", "name": "Shenzhen Parts", "country": "CN"},
]
FACILITIES = [
    {"external_id": "F-1", "name": "Newark DC", "facility_type": "DISTRIBUTION_CENTER",
     "country": "US", "region": "East"},
    {"external_id": "F-2", "name": "Dallas DC", "facility_type": "DISTRIBUTION_CENTER",
     "country": "US", "region": "South"},
]
ORDERS = [
    {"external_id": "O-1", "region": "East", "total_amount": 1000.0},
    {"external_id": "O-2", "region": "East", "total_amount": 3000.0},
    {"external_id": "O-3", "region": "South", "total_amount": 1000.0},
]
SHIPMENTS = [
    {"external_id": "SH-1", "order_id": "O-1", "origin_facility_id": "F-1",
     "destination_country": "US"},
    {"external_id": "SH-2", "order_id": "O-2", "origin_facility_id": "F-1",
     "destination_country": "US"},
    {"external_id": "SH-3", "order_id": "O-3", "origin_facility_id": "F-2",
     "destination_country": "US"},
]


@pytest.fixture()
def twin():
    return build_twin_graph(SUPPLIERS, FACILITIES, SHIPMENTS, ORDERS, flow_window_days=30)


def test_nodes_created(twin):
    assert supplier_node("S-1") in twin.graph
    assert facility_node("F-1") in twin.graph
    assert region_node("East") in twin.graph
    assert twin.summary()["node_counts"] == {"supplier": 2, "facility": 2, "region": 2}


def test_demand_edges_accumulate_order_value(twin):
    edge = twin.graph.edges[facility_node("F-1"), region_node("East")]
    assert edge["value"] == 4000.0  # O-1 + O-2
    assert edge["shipments"] == 2


def test_supplier_heuristic_matches_country(twin):
    # S-1 (US) feeds both US facilities; S-2 (CN) feeds none
    assert twin.graph.has_edge(supplier_node("S-1"), facility_node("F-1"))
    assert twin.graph.has_edge(supplier_node("S-1"), facility_node("F-2"))
    assert twin.graph.out_degree(supplier_node("S-2")) == 0


def test_exposure_reflects_flow_share(twin):
    big = twin.exposure(facility_node("F-1"))   # $4000 out + $4000 in from supplier
    small = twin.exposure(facility_node("F-2"))  # $1000 out + $1000 in
    assert big.exposure_share > small.exposure_share
    assert 0.0 <= small.exposure_share <= big.exposure_share <= 1.0
    assert big.daily_value == pytest.approx(big.throughput_value / 30)


def test_exposure_unknown_node_raises(twin):
    with pytest.raises(KeyError):
        twin.exposure("facility:NOPE")


def test_critical_nodes_ranked(twin):
    ranked = twin.critical_nodes(top_n=3)
    shares = [e.exposure_share for e in ranked]
    assert shares == sorted(shares, reverse=True)


def test_single_point_of_failure_detected(twin):
    # F-1 is the only supply into East; F-2 the only supply into South
    spofs = twin.single_points_of_failure()
    assert facility_node("F-1") in spofs
    assert facility_node("F-2") in spofs


def test_shipment_with_unknown_facility_creates_node():
    shipments = SHIPMENTS + [
        {"external_id": "SH-4", "order_id": "O-1", "origin_facility_id": "F-9",
         "destination_country": "US"},
    ]
    twin = build_twin_graph(SUPPLIERS, FACILITIES, shipments, ORDERS)
    assert facility_node("F-9") in twin.graph


def test_empty_network():
    twin = build_twin_graph([], [], [], [])
    assert twin.summary()["nodes"] == 0
    assert twin.total_edge_value == 0.0
