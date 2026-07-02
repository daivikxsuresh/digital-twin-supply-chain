"""Node state machine lifecycle tests."""

import pytest
from transitions import MachineError

from app.twin.state import (
    STATE_AT_RISK,
    STATE_DISRUPTED,
    STATE_NORMAL,
    STATE_RECOVERING,
    NodeState,
    StateRegistry,
)


def test_full_lifecycle():
    node = NodeState("facility:F-1")
    assert node.state == STATE_NORMAL

    node.flag_risk()
    assert node.state == STATE_AT_RISK

    node.disrupt()
    assert node.state == STATE_DISRUPTED
    assert node.is_impacted

    node.begin_recovery()
    assert node.state == STATE_RECOVERING
    assert node.is_impacted

    node.recover()
    assert node.state == STATE_NORMAL
    assert not node.is_impacted


def test_sudden_disruption_from_normal():
    node = NodeState("facility:F-1")
    node.disrupt()
    assert node.state == STATE_DISRUPTED


def test_at_risk_can_stand_down():
    node = NodeState("facility:F-1")
    node.flag_risk()
    node.stand_down()
    assert node.state == STATE_NORMAL


def test_relapse_during_recovery():
    node = NodeState("facility:F-1")
    node.disrupt()
    node.begin_recovery()
    node.disrupt()
    assert node.state == STATE_DISRUPTED


def test_invalid_transition_rejected():
    node = NodeState("facility:F-1")
    with pytest.raises(MachineError):
        node.begin_recovery()  # can't recover what isn't disrupted


def test_history_recorded():
    node = NodeState("facility:F-1")
    node.disrupt()
    node.begin_recovery()
    node.recover()
    states = [h["state"] for h in node.history]
    assert states == [STATE_DISRUPTED, STATE_RECOVERING, STATE_NORMAL]
    assert all("at" in h for h in node.history)


def test_registry_tracks_impacted():
    registry = StateRegistry()
    registry.get("facility:F-1").disrupt()
    registry.get("facility:F-2").flag_risk()

    assert registry.impacted_nodes() == ["facility:F-1"]
    assert registry.snapshot() == {
        "facility:F-1": STATE_DISRUPTED,
        "facility:F-2": STATE_AT_RISK,
    }

    registry.reset()
    assert registry.snapshot() == {}


def test_registry_returns_same_instance():
    registry = StateRegistry()
    assert registry.get("x") is registry.get("x")
