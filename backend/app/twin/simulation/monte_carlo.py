"""
Monte Carlo disruption simulation — Python port of the TwinFlow demo's
sim.js, which is the agreed spec for this engine.

Differences from the demo:
  * exposure and daily $ value come from the real twin graph when supplied
    (the demo drew both from fixed triangular distributions);
  * seedable RNG for reproducible runs and testable output;
  * pure stdlib (random.triangular / random.gauss) — no numpy dependency.
"""

from dataclasses import dataclass, field

import structlog

from random import Random

logger = structlog.get_logger(__name__)

# Demo fallbacks (sim.js constants) used when graph data is missing/thin.
# Order matches random.triangular(low, high, mode).
FALLBACK_EXPOSURE = (0.15, 0.60, 0.35)
FALLBACK_DAILY_EXPOSURE = (18_000.0, 95_000.0, 42_000.0)
OTIF_FLOOR = 20.0


@dataclass
class Percentiles:
    p5: float
    p50: float
    p95: float


@dataclass
class SimulationResult:
    trials: int
    otif: Percentiles
    cost: Percentiles
    mean_otif: float
    otif_samples: list[float] = field(repr=False, default_factory=list)
    cost_samples: list[float] = field(repr=False, default_factory=list)


def _percentile(sorted_values: list[float], p: float) -> float:
    # Matches sim.js: arr[min(len-1, floor(p * len))]
    idx = min(len(sorted_values) - 1, int(p * len(sorted_values)))
    return sorted_values[idx]


def run_monte_carlo(
    base_otif: float,
    severity: float,
    duration_days: float,
    trials: int = 1000,
    *,
    node_exposure: float | None = None,
    node_daily_value: float | None = None,
    seed: int | None = None,
) -> SimulationResult:
    """
    Run N trials of a disruption scenario and return the distribution of
    OTIF impact and dollar exposure.

    base_otif        baseline on-time-in-full %, e.g. 94.2
    severity         disruption severity 0..1
    duration_days    stated duration of the disruption
    node_exposure    real flow share (0..1) of the disrupted node from the
                     twin graph; falls back to the demo's triangular draw
    node_daily_value real avg $ flow/day through the node; same fallback
    seed             fix for reproducible results
    """
    if not 0.0 <= severity <= 1.0:
        raise ValueError(f"severity must be in [0, 1], got {severity}")
    if duration_days <= 0:
        raise ValueError(f"duration_days must be positive, got {duration_days}")
    if trials < 1:
        raise ValueError(f"trials must be >= 1, got {trials}")

    rng = Random(seed)
    otif_results: list[float] = []
    cost_results: list[float] = []

    for _ in range(trials):
        # Disruption depth: triangular around severity, capped
        depth_draw = rng.triangular(severity * 0.5, min(1.0, severity * 1.5), severity)
        depth = min(0.95, max(0.02, depth_draw))

        # Recovery time varies around stated duration
        recovery = max(1.0, rng.gauss(duration_days, duration_days * 0.35))

        # Network absorption: buffers absorb part of the hit (more for short events)
        absorption = max(0.0, rng.gauss(0.30, 0.12)) * (1.25 if duration_days <= 7 else 0.85)
        eff_depth = depth * (1 - min(0.7, absorption))

        # Exposure: real graph share when known, else demo triangular.
        # Real exposure still gets ±20% relative jitter — measured share is
        # a point estimate over a window, not a certainty.
        if node_exposure is not None:
            exposure = min(1.0, max(0.0, rng.gauss(node_exposure, node_exposure * 0.2)))
        else:
            exposure = rng.triangular(*FALLBACK_EXPOSURE)

        otif_hit = base_otif * eff_depth * exposure
        otif_results.append(max(OTIF_FLOOR, base_otif - otif_hit))

        if node_daily_value is not None:
            daily = max(0.0, rng.gauss(node_daily_value, node_daily_value * 0.25))
        else:
            daily = rng.triangular(*FALLBACK_DAILY_EXPOSURE)
        cost_results.append(eff_depth * exposure * daily * recovery)

    otif_results.sort()
    cost_results.sort()

    result = SimulationResult(
        trials=trials,
        otif=Percentiles(
            p5=_percentile(otif_results, 0.05),
            p50=_percentile(otif_results, 0.50),
            p95=_percentile(otif_results, 0.95),
        ),
        cost=Percentiles(
            p5=_percentile(cost_results, 0.05),
            p50=_percentile(cost_results, 0.50),
            p95=_percentile(cost_results, 0.95),
        ),
        mean_otif=sum(otif_results) / trials,
        otif_samples=otif_results,
        cost_samples=cost_results,
    )
    logger.info(
        "monte_carlo.complete",
        trials=trials,
        severity=severity,
        otif_p50=round(result.otif.p50, 2),
        cost_p50=round(result.cost.p50, 0),
    )
    return result


def histogram(sorted_values: list[float], bins: int = 30) -> dict:
    """Histogram bins for frontend chart drawing (port of sim.js histogram)."""
    lo, hi = sorted_values[0], sorted_values[-1]
    width = (hi - lo) / bins or 1.0
    counts = [0] * bins
    for v in sorted_values:
        i = int((v - lo) / width)
        counts[min(bins - 1, max(0, i))] += 1
    return {"counts": counts, "min": lo, "max": hi, "bin_width": width}
