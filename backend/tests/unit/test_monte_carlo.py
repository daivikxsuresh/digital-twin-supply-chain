"""Monte Carlo simulation tests — validated against the sim.js spec behavior."""

import pytest

from app.twin.simulation.monte_carlo import (
    OTIF_FLOOR,
    histogram,
    run_monte_carlo,
)

BASE_OTIF = 94.2


def test_reproducible_with_seed():
    a = run_monte_carlo(BASE_OTIF, severity=0.6, duration_days=7, trials=500, seed=42)
    b = run_monte_carlo(BASE_OTIF, severity=0.6, duration_days=7, trials=500, seed=42)
    assert a.otif_samples == b.otif_samples
    assert a.cost_samples == b.cost_samples


def test_otif_bounded():
    result = run_monte_carlo(BASE_OTIF, severity=0.9, duration_days=30, trials=2000, seed=1)
    assert all(OTIF_FLOOR <= v <= BASE_OTIF for v in result.otif_samples)


def test_percentiles_ordered():
    result = run_monte_carlo(BASE_OTIF, severity=0.5, duration_days=10, trials=1000, seed=7)
    assert result.otif.p5 <= result.otif.p50 <= result.otif.p95
    assert result.cost.p5 <= result.cost.p50 <= result.cost.p95
    assert result.cost.p5 >= 0


def test_higher_severity_hurts_more():
    mild = run_monte_carlo(BASE_OTIF, severity=0.2, duration_days=7, trials=2000, seed=3)
    severe = run_monte_carlo(BASE_OTIF, severity=0.9, duration_days=7, trials=2000, seed=3)
    assert severe.mean_otif < mild.mean_otif
    assert severe.cost.p50 > mild.cost.p50


def test_longer_duration_costs_more():
    short = run_monte_carlo(BASE_OTIF, severity=0.5, duration_days=3, trials=2000, seed=9)
    long = run_monte_carlo(BASE_OTIF, severity=0.5, duration_days=45, trials=2000, seed=9)
    assert long.cost.p50 > short.cost.p50


def test_graph_exposure_overrides_fallback():
    tiny = run_monte_carlo(
        BASE_OTIF, severity=0.7, duration_days=7, trials=2000, seed=5, node_exposure=0.02
    )
    huge = run_monte_carlo(
        BASE_OTIF, severity=0.7, duration_days=7, trials=2000, seed=5, node_exposure=0.90
    )
    assert tiny.mean_otif > huge.mean_otif


def test_node_daily_value_drives_cost():
    cheap = run_monte_carlo(
        BASE_OTIF, severity=0.5, duration_days=7, trials=2000, seed=11, node_daily_value=1_000
    )
    pricey = run_monte_carlo(
        BASE_OTIF, severity=0.5, duration_days=7, trials=2000, seed=11, node_daily_value=500_000
    )
    assert pricey.cost.p50 > cheap.cost.p50


@pytest.mark.parametrize(
    ("severity", "duration", "trials"),
    [(-0.1, 7, 100), (1.1, 7, 100), (0.5, 0, 100), (0.5, 7, 0)],
)
def test_invalid_inputs_rejected(severity, duration, trials):
    with pytest.raises(ValueError):
        run_monte_carlo(BASE_OTIF, severity=severity, duration_days=duration, trials=trials)


def test_histogram_counts_all_values():
    result = run_monte_carlo(BASE_OTIF, severity=0.5, duration_days=7, trials=1000, seed=2)
    hist = histogram(result.otif_samples, bins=30)
    assert sum(hist["counts"]) == 1000
    assert len(hist["counts"]) == 30
    assert hist["min"] <= hist["max"]
