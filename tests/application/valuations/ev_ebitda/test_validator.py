from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from domain.valuation.models.ddm import DDMParameters
from domain.valuation.policies import FactorSeverity
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

def _factor_names(result):
    return {factor.name for factor in result.factors}

def test_ev_ebitda_passes_for_positive_ebitda_company() -> None:
    from application.valuations.ev_ebitda.validator import EVEBITDAChecker

    result = EVEBITDAChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is True

def test_ev_ebitda_blocks_non_positive_ebitda() -> None:
    from application.valuations.ev_ebitda.validator import EVEBITDAChecker

    metrics = make_orcl_metrics()
    metrics.financials = replace(metrics.financials, ebitda_ttm=0.0)

    result = EVEBITDAChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Negative/Zero EBITDA" in _factor_names(result)

def test_ev_ebitda_warns_for_high_multiple_and_debt_to_assets() -> None:
    from application.valuations.ev_ebitda.validator import EVEBITDAChecker

    metrics = make_orcl_metrics()
    metrics.valuation = replace(
        metrics.valuation,
        enterprise_value=metrics.financials.ebitda_ttm * 50.0,
    )

    result = EVEBITDAChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert {"Very High Current EV/EBITDA", "High Debt-to-Assets"} <= _factor_names(result)

def test_ev_ebitda_blocks_missing_sector_multiple() -> None:
    from application.valuations.ev_ebitda.validator import EVEBITDAChecker

    metrics = make_orcl_metrics()
    metrics.profile = replace(metrics.profile, sector=None)

    result = EVEBITDAChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Missing Sector EV/EBITDA Multiple" in _factor_names(result)
