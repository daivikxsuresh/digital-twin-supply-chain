"""Twin engine tests — DB-free by injecting a prebuilt graph."""

import pytest

from app.twin.engine import TwinEngine
from app.twin.graph import build_twin_graph, facility_node
from app.twin.state import STATE_DISRUPTED, STATE_NORMAL

SUPPLIERS = [{"external_id": "S-1", "name": "Acme", "country": "US"}]
FACILITIES = [
    {"external_id": "F-1", "name": "Newark DC", "facility_type": "DISTRIBUTION_CENTER",
     "country": "US", "region": "East"},
]
ORDERS = [{"external_id": "O-1", "region": "East", "total_amount": 5000.0}]
SHIPMENTS = [
    {"external_id": "SH-1", "order_id": "O-1", "origin_facility_id": "F-1",
     "destination_country": "US"},
]


@pytest.fixture()
def engine() -> TwinEngine:
    eng = TwinEngine()
    eng.twin = build_twin_graph(SUPPLIERS, FACILITIES, SHIPMENTS, ORDERS)
    eng._dirty = False
    return eng


async def test_run_scenario_marks_node_disrupted(engine):
    node = facility_node("F-1")
    result = await engine.run_scenario(node, severity=0.6, duration_days=7, trials=200, seed=1)
    assert result.trials == 200
    assert engine.states.get(node).state == STATE_DISRUPTED
    assert engine.states.impacted_nodes() == [node]


async def test_run_scenario_unknown_node_raises(engine):
    with pytest.raises(KeyError):
        await engine.run_scenario("facility:NOPE", severity=0.5, duration_days=7)


async def test_run_scenario_reproducible(engine):
    node = facility_node("F-1")
    a = await engine.run_scenario(node, severity=0.5, duration_days=7, trials=300, seed=42)
    b = await engine.run_scenario(node, severity=0.5, duration_days=7, trials=300, seed=42)
    assert a.otif_samples == b.otif_samples


async def test_resolve_scenario_recovers_node(engine):
    node = facility_node("F-1")
    await engine.run_scenario(node, severity=0.5, duration_days=7, trials=100, seed=1)
    await engine.resolve_scenario(node)
    assert engine.states.get(node).state == STATE_NORMAL
    assert engine.states.impacted_nodes() == []


async def test_handle_event_marks_dirty(engine):
    assert engine._dirty is False
    await engine.handle_event({"event_type": "order.created"})
    assert engine._dirty is True


async def test_handle_event_ignores_unrelated(engine):
    await engine.handle_event({"event_type": "heartbeat"})
    assert engine._dirty is False


async def test_status_reports_graph_and_states(engine):
    node = facility_node("F-1")
    await engine.run_scenario(node, severity=0.5, duration_days=7, trials=100, seed=1)
    status = await engine.status()
    assert status["graph"]["nodes"] == 3  # supplier, facility, region
    assert status["impacted_nodes"] == [node]
    assert len(status["critical_nodes"]) > 0
