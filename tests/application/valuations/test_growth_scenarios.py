"""
Tests for growth clamp diagnostics and negative-income growth filtering fixes in application/valuations/utils.py.

growth clamp diagnostics: _derive_base_growth() must emit logger.warning (and in
       generate_growth_scenarios() scenarios that hit the ceiling/floor)
       when growth rates are clamped.

negative-income growth filtering: _derive_base_growth() must disqualify net_income_growth when
       net_income_ttm is negative, even if the ratio of two negatives
       produces a large-looking positive number (+55% for C3.ai).
"""
import logging
import pytest
import dataclasses

from domain.core.missing import MissingReason
from domain.metrics.stock import (
    BalanceSheet,
    CashFlow,
    Financials,
    HistoricalData,
    MarketData,
    Valuation,
)
from domain.metrics.history import CashFlowHistory
from tests.unit.fixtures import make_ai_metrics, make_orcl_metrics, make_adbe_metrics


def _derive(metrics, **kwargs):
    from application.valuations.utils import _derive_base_growth
    return _derive_base_growth(metrics, **kwargs)


def _generate_scenarios(metrics, years=10, margin=0.25, **kwargs):
    from application.valuations.utils import generate_growth_scenarios
    return generate_growth_scenarios(metrics, years, margin, **kwargs)


# ── negative-income growth filtering Tests ───────────────────────────────────────────────────────────────


def _build_minimal_valuation(financials):
    return Valuation.build(
        financials=financials,
        balance_sheet=BalanceSheet(
            total_debt=0.0,
            total_equity=100.0,
            cash_and_equivalents=10.0,
            total_assets=200.0,
            total_liabilities=100.0,
            current_assets=50.0,
            current_liabilities=25.0,
            inventory=0.0,
        ),
        market_data=MarketData(
            current_price=10.0,
            shares_outstanding=10,
            market_cap=100.0,
        ),
        cash_flow=CashFlow(
            operating_cf_ttm=10.0,
            capex_ttm=-2.0,
            oper_cf_last_year=9.0,
            latest_annual_capex=-2.0,
            oper_cf_last_quarter=3.0,
            latest_quarter_capex=-1.0,
            dividends_paid_ttm=0.0,
            share_buybacks_ttm=0.0,
        ),
        historical_data=HistoricalData(eps_history=None),
    )


def test_source_valuation_build_skips_ttm_ni_growth_when_income_is_negative():
    financials = Financials(
        revenue_ttm=90.0,
        ebit_ttm=-10.0,
        ebt_ttm=-10.0,
        tax_expense_ttm=0.0,
        interest_expense_ttm=0.0,
        gross_profit_ttm=30.0,
        operating_income_ttm=-12.0,
        net_income_ttm=-150.0,
        revenue_ttm_prev=100.0,
        net_income_ttm_prev=-100.0,
        da_ttm=1.0,
    )

    valuation, diagnostics = _build_minimal_valuation(financials)

    assert financials.net_income_growth == pytest.approx(0.5)
    assert valuation.forward_growth_rate == 0.0
    assert any(
        diag.model == "Valuation"
        and diag.field == "forward_growth_rate"
        and diag.reason is MissingReason.DERIVED_FAILED
        and "net_income_ttm is negative" in diag.detail
        for diag in diagnostics
    )


def test_source_valuation_build_allows_ttm_ni_growth_when_income_is_positive():
    financials = Financials(
        revenue_ttm=120.0,
        ebit_ttm=20.0,
        ebt_ttm=20.0,
        tax_expense_ttm=4.0,
        interest_expense_ttm=0.0,
        gross_profit_ttm=60.0,
        operating_income_ttm=22.0,
        net_income_ttm=130.0,
        revenue_ttm_prev=100.0,
        net_income_ttm_prev=100.0,
        da_ttm=2.0,
    )

    valuation, diagnostics = _build_minimal_valuation(financials)

    assert financials.net_income_growth == pytest.approx(0.3)
    assert valuation.forward_growth_rate == pytest.approx(0.3)
    assert not any(
        diag.field == "forward_growth_rate"
        and diag.detail
        and "net_income_ttm is negative" in diag.detail
        for diag in diagnostics
    )


class TestGrowthSignalSelection:
    """
    C3.ai: net_income_ttm < 0 must disqualify net_income_growth signal.

    C3.ai data:
      net_income_ttm      = -434_502_000   (NEGATIVE)
      net_income_growth   = +55.35%        (ratio of two negatives — meaningless)
      revenue_growth_rate = -1.03%         (slightly negative)
      forward_growth_rate = 14.55%         (suspect — from NI CAGR of negatives)

    After negative-income growth filtering fix:
      net_income_growth MUST be skipped.
      forward_growth_rate should be the primary signal (if non-zero and finite).
    """

    def test_net_income_growth_not_used_when_income_negative(self):
        """
        _derive_base_growth() must NOT return net_income_growth (55.35%) for C3.ai.
        Even though it is the largest positive signal, it is derived from two
        negative numbers and is not economically meaningful.
        """
        m = make_ai_metrics()
        # Temporarily zero out forward_growth_rate and fcf_cagr so the test
        # can verify the NI growth signal specifically gets skipped.
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        result = _derive(m)
        # Should NOT be the raw 55.35% net_income_growth value
        assert abs(result - m.financials.net_income_growth) > 0.01, (
            f"_derive_base_growth() returned {result:.4f} which matches "
            f"net_income_growth ({m.financials.net_income_growth:.4f}).  "
            f"This signal should have been disqualified (net_income_ttm < 0)."
        )

    def test_fallback_to_revenue_growth_when_ni_negative(self):
        """
        With forward_growth_rate=0 and fcf_cagr=0 and NI disqualified,
        the engine should fall through to revenue_growth_rate.

        C3.ai revenue_growth_rate = -1.03% (negative but valid as a signal).
        """
        m = make_ai_metrics()
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        result = _derive(m)
        # Should be clamped revenue_growth_rate = -0.0103
        expected = m.financials.revenue_growth_rate
        assert abs(result - expected) < 1e-6, (
            f"Expected fallback to revenue_growth_rate ({expected:.4f}), "
            f"got {result:.4f}."
        )

    def test_fallback_to_constant_when_all_signals_invalid(self):
        """
        When all signals are zero/disqualified, must fall back to
        _FALLBACK_BASE_GROWTH (0.04).
        """
        m = make_ai_metrics()
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        m.financials = dataclasses.replace(
            m.financials,
            revenue_growth_rate=0.0,
            net_income_growth=0.5535,   # still present but should be disqualified
        )
        result = _derive(m)
        from application.valuations.utils import _FALLBACK_BASE_GROWTH
        assert abs(result - _FALLBACK_BASE_GROWTH) < 1e-6, (
            f"Expected fallback growth {_FALLBACK_BASE_GROWTH}, got {result:.4f}."
        )

    def test_positive_net_income_allows_ni_growth_signal(self):
        """
        When net_income_ttm > 0, net_income_growth IS a valid signal and
        should be used (with all higher-priority signals zeroed).
        This verifies negative-income growth filtering does not over-block.
        """
        m = make_ai_metrics()
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        m.financials = dataclasses.replace(
            m.financials,
            net_income_ttm=100_000_000.0,       # positive — signal now valid
            net_income_growth=0.30,
        )
        result = _derive(m)
        assert abs(result - 0.30) < 1e-6, (
            f"Expected net_income_growth (0.30) to be used when "
            f"net_income_ttm > 0.  Got {result:.4f}."
        )

    def test_profitable_company_unaffected(self):
        """
        ORCL net_income_ttm = +$16.2B — net_income_growth signal should
        remain fully available (existing behaviour for profitable companies).
        """
        m = make_orcl_metrics()
        # Zero higher-priority signals to isolate NI growth
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        result = _derive(m)
        # Should fall to net_income_growth = 54.87%  → clamped to 50%
        from application.valuations.utils import _GROWTH_CEILING
        expected = min(m.financials.net_income_growth, _GROWTH_CEILING)
        assert abs(result - expected) < 1e-6, (
            f"ORCL (profitable): expected clamped NI growth {expected:.4f}, "
            f"got {result:.4f}."
        )


# ── growth clamp diagnostics Tests ───────────────────────────────────────────────────────────────

class TestGrowthClampDiagnostics:
    """
    Clipping at _GROWTH_CEILING must emit logger.warning.
    """

    def test_ceiling_clip_emits_warning_in_derive(self, caplog):
        """
        When raw growth exceeds 50%, _clamp_and_warn must log a WARNING.
        """
        m = make_orcl_metrics()
        # Set NI growth to 80% (above ceiling) and zero higher-priority signals
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        m.financials = dataclasses.replace(
            m.financials,
            net_income_ttm=100_000_000.0,   # positive so signal is valid
            net_income_growth=0.80,          # above 50% ceiling
        )
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _derive(m)

        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("clamped" in t.lower() or "ceiling" in t.lower() for t in warning_texts), (
            f"Expected a WARNING about growth ceiling clip.  "
            f"Got warnings: {warning_texts}"
        )

    def test_clamp_diagnostic_is_persisted_in_growth_assumption(self):
        from application.valuations.utils import generate_growth_scenarios_with_assumption

        m = make_orcl_metrics()
        m.valuation = dataclasses.replace(m.valuation, forward_growth_rate=0.80)

        scenario_set = generate_growth_scenarios_with_assumption(
            m,
            projection_years=10,
            margin_of_safety=0.25,
        )

        assert any(
            "clamped" in diagnostic.lower()
            for diagnostic in scenario_set.assumption.diagnostics
        )

    def test_ceiling_clip_in_scenario_generator_emits_warning(self, caplog):
        """
        generate_growth_scenarios() must log a WARNING when the Bull scenario
        ceiling binds on at least one year.
        """
        m = make_orcl_metrics()
        # Force base_growth to 50% — Bull multiplier (1.25×) = 62.5% > ceiling
        m.valuation = dataclasses.replace(m.valuation, forward_growth_rate=0.50)
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _generate_scenarios(m)

        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("ceiling" in t.lower() or "capped" in t.lower() for t in warning_texts), (
            f"Expected WARNING about scenario ceiling clip.  "
            f"Got warnings: {warning_texts}"
        )

    def test_scenario_clip_diagnostic_is_persisted_in_growth_assumption(self):
        from application.valuations.utils import generate_growth_scenarios_with_assumption

        m = make_orcl_metrics()
        m.valuation = dataclasses.replace(m.valuation, forward_growth_rate=0.50)

        scenario_set = generate_growth_scenarios_with_assumption(
            m,
            projection_years=10,
            margin_of_safety=0.25,
        )

        assert any(
            "growth ceiling" in diagnostic.lower()
            for diagnostic in scenario_set.assumption.diagnostics
        )

    def test_no_clip_no_warning(self, caplog):
        """
        ADBE base growth ~14.45% — well below the 50% ceiling for all
        scenarios.  No clipping warning should be emitted.
        """
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _generate_scenarios(make_adbe_metrics())

        clip_warnings = [
            r.message for r in caplog.records
            if r.levelno == logging.WARNING and
            ("clamped" in r.message.lower() or "ceiling" in r.message.lower() or
             "floor" in r.message.lower())
        ]
        assert not clip_warnings, (
            f"Unexpected clipping warnings for ADBE: {clip_warnings}"
        )

    def test_floor_clip_emits_warning(self, caplog):
        """
        When growth goes below -20% floor, a WARNING must be emitted for
        the Bear scenario.
        """
        m = make_adbe_metrics()
        # Set forward_growth_rate to -0.30 so Bear scenario clips the floor
        m.valuation = dataclasses.replace(m.valuation, forward_growth_rate=-0.30)
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _generate_scenarios(m)

        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("floor" in t.lower() or "clamped" in t.lower() for t in warning_texts), (
            f"Expected WARNING about floor clip.  Got warnings: {warning_texts}"
        )

    def test_source_fcf_cagr_near_zero_history_records_build_diagnostic(self):
        cash_flow = CashFlow(
            operating_cf_ttm=0.0,
            capex_ttm=0.0,
            oper_cf_last_year=0.0,
            latest_annual_capex=0.0,
            history=CashFlowHistory(
                operating_cf_annual=[1_500_000.0, 3_000_000.0],
                capex_annual=[-1_000_000.0, -1_000_000.0],
            ),
        )

        valuation, diagnostics = Valuation.build(
            financials=Financials(net_income_ttm=10.0),
            balance_sheet=BalanceSheet(total_equity=100.0, total_assets=100.0),
            market_data=MarketData(current_price=10.0, shares_outstanding=10, market_cap=100.0),
            cash_flow=cash_flow,
            historical_data=HistoricalData(),
        )

        assert valuation.fcf_cagr == 0.0
        assert any(
            diag.model == "Valuation"
            and diag.field == "fcf_cagr"
            and "below $1,000,000" in diag.detail
            for diag in diagnostics
        )

    def test_source_ttm_fcf_fallback_rejects_near_zero_base(self):
        cash_flow = CashFlow(
            operating_cf_ttm=900_000.0,
            capex_ttm=-100_000.0,
            oper_cf_last_year=700_000.0,
            latest_annual_capex=-100_000.0,
        )

        valuation, diagnostics = Valuation.build(
            financials=Financials(net_income_ttm=10.0),
            balance_sheet=BalanceSheet(total_equity=100.0, total_assets=100.0),
            market_data=MarketData(current_price=10.0, shares_outstanding=10, market_cap=100.0),
            cash_flow=cash_flow,
            historical_data=HistoricalData(),
        )

        assert valuation.fcf_cagr == 0.0
        assert any(
            diag.model == "Valuation"
            and diag.field == "fcf_cagr"
            and "TTM/prior-year" in diag.detail
            and "below $1,000,000" in diag.detail
            for diag in diagnostics
        )

    def test_source_fcf_cagr_out_of_bounds_records_build_diagnostic(self):
        cash_flow = CashFlow(
            operating_cf_ttm=0.0,
            capex_ttm=0.0,
            oper_cf_last_year=0.0,
            latest_annual_capex=0.0,
            history=CashFlowHistory(
                operating_cf_annual=[2_000_000.0, 11_000_000.0],
                capex_annual=[-1_000_000.0, -1_000_000.0],
            ),
        )

        valuation, diagnostics = Valuation.build(
            financials=Financials(net_income_ttm=10.0),
            balance_sheet=BalanceSheet(total_equity=100.0, total_assets=100.0),
            market_data=MarketData(current_price=10.0, shares_outstanding=10, market_cap=100.0),
            cash_flow=cash_flow,
            historical_data=HistoricalData(),
        )

        assert valuation.fcf_cagr > 0.50
        assert any(
            diag.model == "Valuation"
            and diag.field == "fcf_cagr"
            and "outside growth bounds" in diag.detail
            for diag in diagnostics
        )


# ── Combined regression tests ─────────────────────────────────────────────────

class TestGrowthScenarioBehavior:
    """Ensure growth scenario behavior works for normal profitable-company paths."""

    def test_orcl_base_growth_uses_forward_rate(self):
        """ORCL forward_growth_rate = 22.81% should be the primary signal."""
        result = _derive(make_orcl_metrics())
        assert abs(result - 0.2281) < 1e-4, (
            f"ORCL base growth should equal forward_growth_rate (0.2281), got {result:.4f}."
        )

    def test_adbe_base_growth_uses_forward_rate(self):
        """ADBE forward_growth_rate = 14.45% should be the primary signal."""
        result = _derive(make_adbe_metrics())
        assert abs(result - 0.1445) < 1e-4, (
            f"ADBE base growth should equal forward_growth_rate (0.1445), got {result:.4f}."
        )

    def test_orcl_weighted_blend_is_opt_in(self):
        """ORCL weighted blend is available only when explicitly requested."""
        result = _derive(make_orcl_metrics(), growth_model="weighted_blend")
        assert result == pytest.approx(0.2758818181818182)

    def test_adbe_weighted_blend_is_opt_in(self):
        """ADBE weighted blend is available only when explicitly requested."""
        result = _derive(make_adbe_metrics(), growth_model="weighted_blend")
        assert result == pytest.approx(0.1492125)

    def test_scenarios_generate_three_lists(self):
        """generate_growth_scenarios always returns Bear, Base, Bull keys."""
        for m in (make_orcl_metrics(), make_adbe_metrics()):
            scenarios = _generate_scenarios(m)
            assert set(scenarios.keys()) == {"Bear", "Base", "Bull"}

    def test_scenarios_have_correct_length(self):
        """Each scenario list must have exactly projection_years entries."""
        for years in (5, 10, 15):
            scenarios = _generate_scenarios(make_adbe_metrics(), years=years)
            for name, rates in scenarios.items():
                assert len(rates) == years, (
                    f"{name}: expected {years} rates, got {len(rates)}."
                )

    def test_bear_growth_lower_than_bull(self):
        """Bear mean growth should be lower than Bull mean growth."""
        for m in (make_orcl_metrics(), make_adbe_metrics()):
            scenarios = _generate_scenarios(m)
            bear_mean = sum(scenarios["Bear"]) / len(scenarios["Bear"])
            bull_mean = sum(scenarios["Bull"]) / len(scenarios["Bull"])
            assert bear_mean < bull_mean, (
                f"Bear mean ({bear_mean:.4f}) should be < Bull mean ({bull_mean:.4f})."
            )

    def test_reversion_off_is_flat_when_not_stochastic(self):
        """Default deterministic scenarios are flat within each scenario."""
        scenarios = _generate_scenarios(
            make_adbe_metrics(),
            years=5,
            margin=0.0,
            stochastic=False,
            reversion_enabled=False,
        )
        for rates in scenarios.values():
            assert rates == pytest.approx([rates[0]] * len(rates))

    def test_reversion_on_tapers_toward_sector_long_run_growth(self):
        """Opt-in reversion moves technology growth toward its long-run 8% rate."""
        scenarios = _generate_scenarios(
            make_adbe_metrics(),
            years=5,
            margin=0.0,
            stochastic=False,
            reversion_enabled=True,
        )
        base = scenarios["Base"]
        long_run = 0.08
        assert base[-1] == pytest.approx(long_run)
        assert abs(base[-1] - long_run) < abs(base[0] - long_run)



from dataclasses import dataclass
import json
import math
from types import SimpleNamespace

import pytest
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

class TestGrowthAssumptionReportMetadata:
    """
    Valuation reports expose the selected growth mode, rate, source,
    and signal contributions for JSON consumers.
    """

    def _run_dcf(self, metrics, *, growth_model="waterfall"):
        from application.valuations.dcf.defaults import get_params
        from application.valuations.dcf.valuation import execute_dcf_scenarios
        params = get_params(metrics)
        params.growth_model = growth_model
        return execute_dcf_scenarios(metrics, params)

    def test_dcf_report_includes_growth_assumption(self):
        report = self._run_dcf(make_orcl_metrics())

        assert report.growth_assumption.selected_mode == "waterfall"
        assert report.growth_assumption.selected_source == "forward_growth_rate"
        assert report.growth_assumption.selected_rate == pytest.approx(0.2281)

    def test_growth_assumption_serializes_to_json(self):
        from cli.json_formatter import to_json
        report = self._run_dcf(make_orcl_metrics())

        payload = json.loads(to_json(report, compact=True))

        assert "growth_assumption" in payload
        assert payload["growth_assumption"]["selected_mode"] == "waterfall"
        assert payload["growth_assumption"]["selected_source"] == "forward_growth_rate"
        assert payload["growth_assumption"]["selected_rate"] == pytest.approx(0.2281)

    def test_weighted_blend_report_includes_signal_contributions(self):
        report = self._run_dcf(make_adbe_metrics(), growth_model="weighted_blend")
        assumption = report.growth_assumption

        assert assumption.requested_mode == "weighted_blend"
        assert assumption.selected_mode == "weighted_blend"
        assert assumption.selected_source == "weighted_blend"
        assert assumption.selected_rate == pytest.approx(0.1492125)

        by_source = {signal.source: signal for signal in assumption.signals}
        assert set(by_source) >= {
            "forward_ni_cagr",
            "fcf_cagr",
            "ttm_ni_growth",
            "revenue_growth",
        }
        assert by_source["forward_ni_cagr"].raw_value == pytest.approx(0.1445)
        assert by_source["forward_ni_cagr"].clamped_value == pytest.approx(0.1445)
        assert by_source["forward_ni_cagr"].weight == pytest.approx(0.40)
