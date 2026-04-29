from types import SimpleNamespace

import pytest

from application.valuations.dcf.valuation import dcf_valuation
from domain.valuation.models.dcf import DCFInputData, DCFParameters
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

def _make_stock_metrics(
    *,
    fcf_ttm: float,
    last_year_fcf: float,
    capex_spike_detected: bool = False,
    normalized_fcf: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        profile=SimpleNamespace(ticker="TEST", sector=None),
        cash_flow=SimpleNamespace(
            fcf_ttm=fcf_ttm,
            last_year_fcf=last_year_fcf,
            last_quarter_fcf=1.0,
            operating_cf_ttm=20.0,
        ),
        financials=SimpleNamespace(
            net_income_ttm=100.0,
            revenue_growth_rate=0.1,
        ),
        valuation=SimpleNamespace(
            capex_spike_detected=capex_spike_detected,
            normalized_fcf=normalized_fcf,
            cost_of_debt=0.05,
            corporate_tax_rate=0.2,
        ),
        balance_sheet=SimpleNamespace(
            total_debt=10.0,
            cash_and_equivalents=5.0,
            total_equity=20.0,
        ),
        market_data=SimpleNamespace(
            market_cap=100.0,
            beta=1.0,
            shares_outstanding=10.0,
            current_price=1.0,
            eps_ttm=1.0,
            pe_ttm=10.0,
        ),
    )

def test_dcf_valuation_returns_result_without_extra_constructor_field() -> None:
    stock_metrics = _make_stock_metrics(fcf_ttm=10.0, last_year_fcf=8.0)
    input_data = DCFInputData(
        stock_metrics=stock_metrics,
        growth_rates=[0.1, 0.1, 0.1],
        wacc=SimpleNamespace(wacc=0.1),
        params=DCFParameters(projection_years=3, margin_of_safety=0.25),
    )

    result = dcf_valuation(input_data)

    assert result.fcf_projections == pytest.approx([11.0, 12.1, 13.31])
    assert result.fcf_seed_source == "raw"
    assert result.intrinsic_value_per_share > 0

def test_dcf_valuation_marks_normalized_seed_when_capex_spike_exists() -> None:
    stock_metrics = _make_stock_metrics(
        fcf_ttm=-10.0,
        last_year_fcf=8.0,
        capex_spike_detected=True,
        normalized_fcf=25.0,
    )
    input_data = DCFInputData(
        stock_metrics=stock_metrics,
        growth_rates=[0.1, 0.1, 0.1],
        wacc=SimpleNamespace(wacc=0.1),
        params=DCFParameters(projection_years=3, margin_of_safety=0.25),
    )

    result = dcf_valuation(input_data)

    assert result.fcf_seed_source == "normalized"


class TestDCFTerminalValueSeed:
    """
    DCF terminal value seed reporting — _terminal_value_gordon() now returns (tv, fcf_tv_seed).
    The seed is a 3-year average of the last FCFs and is propagated to
    DCFValuationResult.fcf_tv_seed for transparency.
    """

    def _run_dcf(self, metrics):
        from application.valuations.dcf.valuation import execute_dcf_scenarios
        return execute_dcf_scenarios(metrics)

    def test_fcf_tv_seed_is_not_none(self):
        """Every DCF scenario result must carry a non-None fcf_tv_seed."""
        report = self._run_dcf(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.fcf_tv_seed is not None, (
                f"{scenario_name}: fcf_tv_seed should not be None after DCF terminal value seed reporting fix."
            )

    def test_fcf_tv_seed_is_positive_for_profitable_company(self):
        """ADBE has positive FCF — tv_seed should be positive."""
        report = self._run_dcf(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.fcf_tv_seed > 0, (
                f"{scenario_name}: ADBE fcf_tv_seed={result.fcf_tv_seed:.0f} "
                f"should be positive."
            )

    def test_fcf_tv_seed_equals_last_3yr_avg(self):
        """
        fcf_tv_seed must equal the average of the last 3 FCF projections.
        This verifies the 3-year averaging window is correctly applied.
        """
        report = self._run_dcf(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            projs = result.fcf_projections
            expected_seed = sum(projs[-3:]) / 3.0
            assert abs(result.fcf_tv_seed - expected_seed) < 1.0, (
                f"{scenario_name}: fcf_tv_seed={result.fcf_tv_seed:.2f} "
                f"does not match 3yr avg of projections={expected_seed:.2f}."
            )

    def test_fcf_tv_seed_uses_normalised_fcf_for_orcl(self):
        """
        ORCL has capex spike + normalised FCF.  tv_seed should be based
        on the normalised projection chain, not raw FCF projections.
        The seed must be positive (since normalised_fcf=16.6B is positive).
        """
        report = self._run_dcf(make_orcl_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.fcf_tv_seed is not None
            assert result.fcf_tv_seed > 0, (
                f"ORCL {scenario_name}: tv_seed should be positive "
                f"(normalised FCF used as seed).  Got {result.fcf_tv_seed:.0f}."
            )

    def test_compute_dcf_returns_tuple(self):
        """
        compute_discounted_cash_flow must return (DiscountedCashFlow, float).
        This tests the function signature change directly.
        """
        from calculations.dfc_formulas import compute_discounted_cash_flow
        projections = [100.0, 110.0, 121.0, 133.1, 146.41]
        result = compute_discounted_cash_flow(projections, 0.10, 0.02)
        assert isinstance(result, tuple), (
            "compute_discounted_cash_flow should return a tuple (dcf, tv_seed)."
        )
        dcf_output, tv_seed = result
        assert tv_seed is not None
        # tv_seed = avg of last 3 projections: (121 + 133.1 + 146.41) / 3
        expected = (121.0 + 133.1 + 146.41) / 3.0
        assert abs(tv_seed - expected) < 1e-6, (
            f"tv_seed={tv_seed:.4f}, expected {expected:.4f}."
        )

    def test_terminal_value_gordon_returns_tuple(self):
        """_terminal_value_gordon must return (tv, fcf_tv_seed) tuple."""
        from calculations.dfc_formulas import _terminal_value_gordon
        fcfs = [100.0, 110.0, 120.0]
        tv, seed = _terminal_value_gordon(fcfs, 0.10, 0.02)
        assert seed == pytest.approx((100.0 + 110.0 + 120.0) / 3.0)
        # TV = avg * (1+g) / (r - g) = 110 * 1.02 / 0.08 = 1402.5
        assert tv == pytest.approx(110.0 * 1.02 / 0.08, rel=1e-6)

class TestDCFSensitivitySpread:
    """
    dynamic sensitivity spread behavior — build_sensitivity_report() derives WACC and TGR spreads
    dynamically from beta and sector, replacing hardcoded values.

    wacc_spread = max(0.02, min(0.08, beta * 0.025))
    tgr_spread  = loaded from dcf.yaml tgr_spread[sector]
    """

    def _get_spreads(self, metrics):
        from application.valuations.dcf.valuation import _derive_sensitivity_spreads
        return _derive_sensitivity_spreads(metrics, base_wacc=0.10, base_terminal_growth=0.02)

    def test_high_beta_gives_wider_wacc_spread(self):
        """ORCL beta=1.597 → wacc_spread = 1.597*0.025 = 0.0399, ≥ 0.02."""
        wacc_spread, _ = self._get_spreads(make_orcl_metrics())
        expected = max(0.02, min(0.08, 1.597 * 0.025))
        assert abs(wacc_spread - expected) < 1e-6, (
            f"ORCL wacc_spread={wacc_spread:.4f}, expected {expected:.4f}."
        )

    def test_adbe_beta_wacc_spread(self):
        """ADBE beta=1.518 → wacc_spread ≈ 0.03795."""
        wacc_spread, _ = self._get_spreads(make_adbe_metrics())
        expected = max(0.02, min(0.08, 1.518 * 0.025))
        assert abs(wacc_spread - expected) < 1e-6

    def test_ai_high_beta_spread_capped_at_08(self):
        """AI beta=2.07 → 2.07*0.025=0.05175 (below cap of 0.08), not capped."""
        wacc_spread, _ = self._get_spreads(make_ai_metrics())
        expected = max(0.02, min(0.08, 2.07 * 0.025))
        assert abs(wacc_spread - expected) < 1e-6
        # Verify it's larger than ADBE's spread (higher beta → wider)
        adbe_spread, _ = self._get_spreads(make_adbe_metrics())
        assert wacc_spread > adbe_spread, (
            f"AI spread ({wacc_spread:.4f}) should exceed ADBE spread ({adbe_spread:.4f})."
        )

    def test_very_low_beta_gives_minimum_spread(self):
        """beta=0.5 → 0.5*0.025=0.0125, clamped to minimum 0.02."""
        m = make_adbe_metrics()
        m.market_data = SimpleNamespace(**{**vars(m.market_data), "beta": 0.5})
        wacc_spread, _ = self._get_spreads(m)
        assert wacc_spread == pytest.approx(0.02), (
            f"Low-beta company should get minimum spread 0.02, got {wacc_spread:.4f}."
        )

    def test_sensitivity_report_stores_derived_spreads(self):
        """DCFSensitivityReport.derived_wacc_spread and derived_tgr_spread must be set."""
        from application.valuations.dcf.valuation import build_sensitivity_report
        adbe = make_adbe_metrics()
        # Minimal FCF projections for testing
        projections = [10_000_000_000.0 * (1.14 ** i) for i in range(1, 11)]
        report = build_sensitivity_report(
            stock_metrics=adbe,
            base_fcf_projections=projections,
            base_wacc=0.1248,
            base_terminal_growth=0.022,
        )
        assert report.derived_wacc_spread is not None, (
            "derived_wacc_spread should be set on DCFSensitivityReport."
        )
        assert report.derived_tgr_spread is not None, (
            "derived_tgr_spread should be set on DCFSensitivityReport."
        )

    def test_sensitivity_table_range_reflects_beta(self):
        """
        Higher beta → wider WACC axis range in sensitivity table.
        AI (beta=2.07) should have a wider WACC range than ADBE (beta=1.518).
        """
        from application.valuations.dcf.valuation import build_sensitivity_report
        projections = [1e10 * (1.1 ** i) for i in range(1, 11)]

        adbe_report = build_sensitivity_report(
            stock_metrics=make_adbe_metrics(),
            base_fcf_projections=projections,
            base_wacc=0.12,
            base_terminal_growth=0.022,
        )
        ai_report = build_sensitivity_report(
            stock_metrics=make_ai_metrics(),
            base_fcf_projections=projections,
            base_wacc=0.16,
            base_terminal_growth=0.022,
        )

        adbe_range = max(adbe_report.wacc_values) - min(adbe_report.wacc_values)
        ai_range   = max(ai_report.wacc_values)   - min(ai_report.wacc_values)
        assert ai_range >= adbe_range, (
            f"AI WACC range ({ai_range:.4f}) should be ≥ ADBE range ({adbe_range:.4f})."
        )

    def test_explicit_override_respected(self):
        """Explicit wacc_spread/tgr_spread kwargs must override derived values."""
        from application.valuations.dcf.valuation import build_sensitivity_report
        projections = [1e10 * (1.1 ** i) for i in range(1, 11)]
        report = build_sensitivity_report(
            stock_metrics=make_adbe_metrics(),
            base_fcf_projections=projections,
            base_wacc=0.12,
            base_terminal_growth=0.022,
            wacc_spread=0.06,   # explicit override
            tgr_spread=0.04,    # explicit override
        )
        actual_range = round(max(report.wacc_values) - min(report.wacc_values), 6)
        assert abs(actual_range - 0.06) < 1e-4, (
            f"Explicit wacc_spread=0.06 override not respected.  Range={actual_range:.4f}."
        )
