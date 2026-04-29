from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from domain.valuation.models.ddm import DDMParameters
from domain.valuation.policies import FactorSeverity
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

def _factor_names(result):
    return {factor.name for factor in result.factors}

def test_reverse_dcf_passes_with_positive_normalized_fcf() -> None:
    from application.valuations.reverse_dcf.validator import ReverseDCFChecker

    result = ReverseDCFChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is True
    assert "Negative Raw FCF — Using Normalised Seed" in _factor_names(result)

def test_reverse_dcf_blocks_non_positive_fcf_without_normalized_fcf() -> None:
    from application.valuations.reverse_dcf.validator import ReverseDCFChecker

    result = ReverseDCFChecker(make_ai_metrics()).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Negative FCF — Back-Solve Impossible" in _factor_names(result)

def test_reverse_dcf_blocks_invalid_price() -> None:
    from application.valuations.reverse_dcf.validator import ReverseDCFChecker

    metrics = make_orcl_metrics()
    metrics.market_data = replace(metrics.market_data, current_price=0.0)

    result = ReverseDCFChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score >= 99
    assert "Invalid Market Price" in _factor_names(result)

def test_reverse_dcf_warns_for_high_implied_growth(monkeypatch) -> None:
    from application.valuations.reverse_dcf import valuation as reverse_valuation
    from application.valuations.reverse_dcf.validator import ReverseDCFChecker

    monkeypatch.setattr(
        reverse_valuation,
        "solve_reverse_dcf",
        lambda metrics: SimpleNamespace(
            result=SimpleNamespace(implied_growth_rate=0.45),
        ),
    )
    metrics = make_orcl_metrics()
    metrics.cash_flow = replace(metrics.cash_flow, fcf_ttm=10_000_000_000.0)
    metrics.valuation = replace(
        metrics.valuation,
        normalized_fcf=None,
        capex_spike_detected=False,
    )

    result = ReverseDCFChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert "Very High Implied Growth" in _factor_names(result)

def test_reverse_dcf_warns_for_negative_implied_growth(monkeypatch) -> None:
    from application.valuations.reverse_dcf import valuation as reverse_valuation
    from application.valuations.reverse_dcf.validator import ReverseDCFChecker

    monkeypatch.setattr(
        reverse_valuation,
        "solve_reverse_dcf",
        lambda metrics: SimpleNamespace(
            result=SimpleNamespace(implied_growth_rate=-0.02),
        ),
    )
    metrics = make_orcl_metrics()
    metrics.cash_flow = replace(metrics.cash_flow, fcf_ttm=10_000_000_000.0)
    metrics.valuation = replace(
        metrics.valuation,
        normalized_fcf=None,
        capex_spike_detected=False,
    )

    result = ReverseDCFChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert "Negative Implied Growth" in _factor_names(result)

def test_reverse_dcf_blocks_when_solver_fails_after_prechecks(monkeypatch) -> None:
    from application.valuations.reverse_dcf import valuation as reverse_valuation
    from application.valuations.reverse_dcf.validator import ReverseDCFChecker

    def fail(metrics):
        raise RuntimeError("boom")

    monkeypatch.setattr(reverse_valuation, "solve_reverse_dcf", fail)
    metrics = make_orcl_metrics()
    metrics.cash_flow = replace(metrics.cash_flow, fcf_ttm=10_000_000_000.0)
    metrics.valuation = replace(
        metrics.valuation,
        normalized_fcf=None,
        capex_spike_detected=False,
    )

    result = ReverseDCFChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Reverse DCF Solver Failed" in _factor_names(result)
