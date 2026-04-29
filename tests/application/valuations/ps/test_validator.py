from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from domain.valuation.models.ddm import DDMParameters
from domain.valuation.policies import FactorSeverity
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

def _factor_names(result):
    return {factor.name for factor in result.factors}

def test_ps_passes_for_positive_revenue_company() -> None:
    from application.valuations.ps.validator import PSChecker

    result = PSChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is True

def test_ps_blocks_zero_revenue() -> None:
    from application.valuations.ps.validator import PSChecker

    metrics = make_orcl_metrics()
    metrics.financials = replace(metrics.financials, revenue_ttm=0.0)

    result = PSChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Zero/Negative Revenue" in _factor_names(result)

def test_ps_blocks_declining_revenue() -> None:
    from application.valuations.ps.validator import PSChecker

    metrics = make_orcl_metrics()
    metrics.financials = replace(metrics.financials, revenue_growth_rate=-0.01)

    result = PSChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Declining Revenue" in _factor_names(result)

def test_ps_blocks_low_gross_margin() -> None:
    from application.valuations.ps.validator import PSChecker

    metrics = make_orcl_metrics()
    metrics.financials = replace(metrics.financials, gross_margin=0.15)

    result = PSChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Low Gross Margin" in _factor_names(result)

def test_ps_warns_for_high_current_multiple() -> None:
    from application.valuations.ps.validator import PSChecker

    metrics = make_orcl_metrics()
    metrics.valuation = replace(metrics.valuation, price_to_sales=20.0)

    result = PSChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert "Very High Current P/S" in _factor_names(result)
    assert all(f.severity == FactorSeverity.WARNING for f in result.factors)

def test_ps_blocks_missing_sector_multiple() -> None:
    from application.valuations.ps.validator import PSChecker

    metrics = make_orcl_metrics()
    metrics.profile = replace(metrics.profile, sector=None)

    result = PSChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Missing Sector P/S Multiple" in _factor_names(result)
