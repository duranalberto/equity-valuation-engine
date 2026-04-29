from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from domain.valuation.models.ddm import DDMParameters
from domain.valuation.policies import FactorSeverity
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

def _factor_names(result):
    return {factor.name for factor in result.factors}

def test_nav_passes_for_positive_assets() -> None:
    from application.valuations.nav.validator import NAVChecker

    result = NAVChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is True

def test_nav_blocks_zero_assets() -> None:
    from application.valuations.nav.validator import NAVChecker

    metrics = make_orcl_metrics()
    metrics.balance_sheet = replace(metrics.balance_sheet, total_assets=0.0)

    result = NAVChecker(metrics).evaluate()

    assert result.is_suitable is False
    assert result.total_severity_score == 99
    assert "Zero/Missing Total Assets" in _factor_names(result)

def test_nav_warns_for_negative_book_equity_and_nav_without_blocking() -> None:
    from application.valuations.nav.validator import NAVChecker

    metrics = make_orcl_metrics()
    metrics.balance_sheet = replace(
        metrics.balance_sheet,
        total_assets=100.0,
        total_liabilities=120.0,
        total_equity=-20.0,
    )

    result = NAVChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert {"Negative Book Equity", "Negative/Zero NAV"} <= _factor_names(result)

def test_nav_warns_for_high_goodwill_and_intangibles() -> None:
    from application.valuations.nav.validator import NAVChecker

    metrics = make_orcl_metrics()
    metrics.balance_sheet = replace(
        metrics.balance_sheet,
        total_assets=100.0,
        goodwill_and_intangibles=60.0,
    )

    result = NAVChecker(metrics).evaluate()

    assert result.is_suitable is True
    assert "High Goodwill/Intangibles" in _factor_names(result)
