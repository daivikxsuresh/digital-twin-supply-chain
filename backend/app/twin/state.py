"""
Node state machine — lifecycle of a supply chain node in the twin.

    NORMAL ──flag_risk──▶ AT_RISK ──disrupt──▶ DISRUPTED
      ▲                      │                     │
      │◀──────stand_down─────┘              begin_recovery
      │                                            ▼
      └────────────recover──────────────────── RECOVERING

NORMAL can also jump straight to DISRUPTED (sudden events: fire, strike,
port closure). Every transition is timestamped and appended to a history
log so KPIs (Phase 3) can compute time-in-state and MTTR.
"""

from datetime import datetime, timezone

import structlog
from transitions import Machine

logger = structlog.get_logger(__name__)

STATE_NORMAL = "normal"
STATE_AT_RISK = "at_risk"
STATE_DISRUPTED = "disrupted"
STATE_RECOVERING = "recovering"

STATES = [STATE_NORMAL, STATE_AT_RISK, STATE_DISRUPTED, STATE_RECOVERING]

TRANSITIONS = [
    {"trigger": "flag_risk", "source": STATE_NORMAL, "dest": STATE_AT_RISK},
    {"trigger": "stand_down", "source": STATE_AT_RISK, "dest": STATE_NORMAL},
    {"trigger": "disrupt", "source": [STATE_NORMAL, STATE_AT_RISK], "dest": STATE_DISRUPTED},
    {"trigger": "begin_recovery", "source": STATE_DISRUPTED, "dest": STATE_RECOVERING},
    {"trigger": "recover", "source": STATE_RECOVERING, "dest": STATE_NORMAL},
    # Relapse while recovering
    {"trigger": "disrupt", "source": STATE_RECOVERING, "dest": STATE_DISRUPTED},
]


class NodeState:
    """State machine + transition history for one twin graph node."""

    def __init__(self, node_id: str, initial: str = STATE_NORMAL) -> None:
        self.node_id = node_id
        self.history: list[dict] = []
        self.machine = Machine(
            model=self,
            states=STATES,
            transitions=TRANSITIONS,
            initial=initial,
            after_state_change="_record",
            ignore_invalid_triggers=False,
        )

    def _record(self) -> None:
        entry = {"state": self.state, "at": datetime.now(timezone.utc)}
        self.history.append(entry)
        logger.info("twin_node.state_change", node_id=self.node_id, state=self.state)

    @property
    def is_impacted(self) -> bool:
        return self.state in (STATE_DISRUPTED, STATE_RECOVERING)


class StateRegistry:
    """Holds a NodeState per twin graph node, created lazily."""

    def __init__(self) -> None:
        self._states: dict[str, NodeState] = {}

    def get(self, node_id: str) -> NodeState:
        if node_id not in self._states:
            self._states[node_id] = NodeState(node_id)
        return self._states[node_id]

    def impacted_nodes(self) -> list[str]:
        return [n for n, s in self._states.items() if s.is_impacted]

    def snapshot(self) -> dict[str, str]:
        return {n: s.state for n, s in self._states.items()}

    def reset(self) -> None:
        self._states.clear()
