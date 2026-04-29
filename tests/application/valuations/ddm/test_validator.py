from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from domain.valuation.models.ddm import DDMParameters
from domain.valuation.policies import FactorSeverity
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

def _factor_names(result):
    return {factor.name for factor in result.factors}

def test_ddm_passes_for_dividend_payer() -> None:
    from application.valuations.ddm.validator import DDMChecker

    result = DDMChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is True

def test_ddm_blocks_no_dividends() -> None:
    from application.valuations.ddm.validator import DDMChecker

    result = DDMChecker(make_adbe_metrics()).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "No Dividends Paid" in _factor_names(result)

def test_ddm_blocks_unsustainable_payout_ratio() -> None:
    from application.valuations.ddm.validator import DDMChecker

    metrics = make_orcl_metrics()
    metrics.ratios = replace(metrics.ratios, payout_ratio=1.2)

    result = DDMChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Unsustainable Payout Ratio" in _factor_names(result)

def test_ddm_blocks_when_growth_exceeds_required_return(monkeypatch) -> None:
    from application.valuations.ddm import defaults as ddm_defaults
    from application.valuations.ddm.validator import DDMChecker

    monkeypatch.setattr(
        ddm_defaults,
        "get_params",
        lambda metrics: DDMParameters(
            projection_years=10,
            margin_of_safety=0.20,
            terminal_growth_rate=0.20,
            risk_free_rate=0.01,
            market_risk_premium=0.01,
        ),
    )

    result = DDMChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Gordon Growth Undefined" in _factor_names(result)

def test_ddm_warns_when_dividend_growth_exceeds_revenue_growth() -> None:
    from application.valuations.ddm.validator import DDMChecker

    metrics = make_orcl_metrics()
    metrics.financials = replace(metrics.financials, revenue_growth_rate=0.01)

    result = DDMChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert "Dividend Growth Exceeds Revenue Growth" in _factor_names(result)

def test_ddm_warns_for_low_interest_coverage_when_company_has_debt() -> None:
    from application.valuations.ddm.validator import DDMChecker

    metrics = make_orcl_metrics()
    metrics.ratios = replace(metrics.ratios, interest_coverage=1.5)

    result = DDMChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert "Low Interest Coverage" in _factor_names(result)
