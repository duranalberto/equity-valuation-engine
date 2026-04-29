"""
tests/test_phase2.py

Unit tests for Phase 2 items:
  BUG-E — fcf_tv_seed exposed in DCFValuationResult
  BUG-F — PEG ratio uses forward_growth_rate denominator
  DESIGN-C — sensitivity spread derived from beta / sector
  DESIGN-D — ValuationSummaryReport composite + agreement score
"""
from __future__ import annotations

import math
import os
import sys

# Path bootstrap — allow import without editable install
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_HERE, "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from types import SimpleNamespace

import pytest
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

# ─────────────────────────────────────────────────────────────────────────────
# BUG-E: fcf_tv_seed
# ─────────────────────────────────────────────────────────────────────────────

class TestBugE_FcfTvSeed:
    """
    BUG-E — _terminal_value_gordon() now returns (tv, fcf_tv_seed).
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
                f"{scenario_name}: fcf_tv_seed should not be None after BUG-E fix."
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


# ─────────────────────────────────────────────────────────────────────────────
# BUG-F: PEG ratio denominator
# ─────────────────────────────────────────────────────────────────────────────

class TestBugF_PegRatio:
    """
    BUG-F — Ratios.build() now uses forward_growth_rate as the primary PEG
    denominator instead of TTM net_income_growth.

    This fixes artificially high PEG values: ORCL 54x, ADBE 48x — artefacts
    of volatile TTM NI growth being used instead of the forward CAGR.
    """

    def _build_ratios(self, metrics):
        """Import and run Ratios.build() on the given metrics stub."""
        from domain.metrics.stock import Ratios
        ratios, _ = Ratios.build(
            financials=metrics.financials,
            cash_flow=metrics.cash_flow,
            balance_sheet=metrics.balance_sheet,
            market_data=metrics.market_data,
            valuation=metrics.valuation,
        )
        return ratios

    def test_peg_source_is_forward_ni_cagr_when_available(self):
        """
        When forward_growth_rate is non-zero, peg_growth_source must be
        'forward_ni_cagr' — not 'ttm_ni_growth'.
        """
        ratios = self._build_ratios(make_adbe_metrics())
        assert ratios.peg_growth_source == "forward_ni_cagr", (
            f"ADBE: expected peg_growth_source='forward_ni_cagr', "
            f"got '{ratios.peg_growth_source}'."
        )

    def test_peg_uses_forward_growth_rate_denominator(self):
        """
        PEG = pe_ttm / forward_growth_rate (not net_income_growth).
        ADBE: pe_ttm=14.1642, forward_growth_rate=0.1445
        Expected PEG ≈ 14.1642 / 0.1445 ≈ 98.0 (not the old 47.79).
        """
        adbe = make_adbe_metrics()
        ratios = self._build_ratios(adbe)
        expected = adbe.market_data.pe_ttm / adbe.valuation.forward_growth_rate
        assert abs(ratios.peg_ratio - expected) < 0.01, (
            f"ADBE PEG ratio={ratios.peg_ratio:.4f}, expected {expected:.4f} "
            f"(pe_ttm / forward_growth_rate)."
        )

    def test_peg_old_value_not_used(self):
        """
        Old PEG used net_income_growth as denominator.  For ADBE that gives
        47.79.  The new value using forward_growth_rate should differ from
        this old value by more than 1.0.
        """
        old_peg = 47.7871  # from terminal JSON output
        ratios  = self._build_ratios(make_adbe_metrics())
        assert abs(ratios.peg_ratio - old_peg) > 1.0, (
            f"PEG ratio {ratios.peg_ratio:.4f} is suspiciously close to the old "
            f"TTM-based value {old_peg:.4f}.  Check BUG-F fix is applied."
        )

    def test_peg_falls_back_to_ttm_growth_when_forward_rate_zero(self):
        """
        When forward_growth_rate=0.0, must fall back to net_income_growth
        and set peg_growth_source='ttm_ni_growth'.
        """
        adbe = make_adbe_metrics()
        # Zero out forward_growth_rate to force fallback
        adbe.valuation = SimpleNamespace(
            **{**vars(adbe.valuation), "forward_growth_rate": 0.0}
        )
        ratios = self._build_ratios(adbe)
        assert ratios.peg_growth_source == "ttm_ni_growth", (
            f"Expected fallback to 'ttm_ni_growth' when forward_growth_rate=0.  "
            f"Got '{ratios.peg_growth_source}'."
        )
        expected = adbe.market_data.pe_ttm / adbe.financials.net_income_growth
        assert abs(ratios.peg_ratio - expected) < 0.01

    def test_peg_is_zero_when_no_pe_available(self):
        """When pe_ttm is None (negative EPS company), PEG must remain 0."""
        ratios = self._build_ratios(make_ai_metrics())
        assert ratios.peg_ratio == 0.0, (
            f"AI has no P/E (negative EPS), PEG should be 0.  Got {ratios.peg_ratio}."
        )

    def test_orcl_peg_uses_forward_growth_rate(self):
        """ORCL: pe_ttm=29.80, forward_growth_rate=0.2281 → PEG ≈ 130.6"""
        orcl   = make_orcl_metrics()
        ratios = self._build_ratios(orcl)
        expected = orcl.market_data.pe_ttm / orcl.valuation.forward_growth_rate
        assert abs(ratios.peg_ratio - expected) < 0.01, (
            f"ORCL PEG={ratios.peg_ratio:.4f}, expected {expected:.4f}."
        )
        # New PEG should be meaningfully different from old TTM-based 54.30
        assert abs(ratios.peg_ratio - 54.30) > 5.0, (
            "ORCL PEG looks like it's still using TTM NI growth denominator."
        )


# ─────────────────────────────────────────────────────────────────────────────
# DESIGN-C: Dynamic sensitivity spread
# ─────────────────────────────────────────────────────────────────────────────

class TestDesignC_DynamicSensitivitySpread:
    """
    DESIGN-C — build_sensitivity_report() derives WACC and TGR spreads
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


# ─────────────────────────────────────────────────────────────────────────────
# DESIGN-D: ValuationSummaryReport
# ─────────────────────────────────────────────────────────────────────────────

class TestDesignD_ValuationSummaryReport:
    """
    DESIGN-D — ValuationSummaryReport.build() computes composite intrinsic,
    model_agreement_score, confidence_band, and implied_upside from
    per-model Base scenario rows.
    """

    def _make_row(self, model, scenario, iv, status="undervalued", price=100.0):
        from domain.valuation.models.summary import ModelScenarioRow
        return ModelScenarioRow(
            model_name=model,
            scenario=scenario,
            intrinsic_value=iv,
            valuation_status=status,
            implied_upside=(iv / price - 1.0),
        )

    def test_composite_is_equal_weight_average_of_base_ivs(self):
        """composite_intrinsic = mean of all Base scenario intrinsic values."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [
            self._make_row("DCF", "Base", 200.0),
            self._make_row("PE",  "Base", 300.0),
            self._make_row("ROE", "Base", 100.0),
            # Bear / Bull should NOT enter composite
            self._make_row("DCF", "Bear", 50.0),
            self._make_row("DCF", "Bull", 400.0),
        ]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["DCF", "PE", "ROE"], models_skipped=[],
        )
        assert report.composite_intrinsic == pytest.approx(200.0)

    def test_model_agreement_score_is_normalised_std_dev(self):
        """agreement_score = std_dev(base_IVs) / current_price."""
        from domain.valuation.models.summary import ValuationSummaryReport
        ivs = [200.0, 300.0, 100.0]
        rows = [self._make_row("M1", "Base", ivs[0]),
                self._make_row("M2", "Base", ivs[1]),
                self._make_row("M3", "Base", ivs[2])]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["M1","M2","M3"], models_skipped=[],
        )
        mean  = sum(ivs) / 3
        sigma = math.sqrt(sum((x - mean) ** 2 for x in ivs) / 3)
        expected_score = sigma / 150.0
        assert report.model_agreement_score == pytest.approx(expected_score, rel=1e-6)

    def test_confidence_band_is_composite_plus_minus_sigma(self):
        """confidence_band = (composite − σ, composite + σ)."""
        from domain.valuation.models.summary import ValuationSummaryReport
        ivs = [200.0, 300.0]
        rows = [self._make_row("M1", "Base", ivs[0]),
                self._make_row("M2", "Base", ivs[1])]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["M1","M2"], models_skipped=[],
        )
        mean  = 250.0
        sigma = math.sqrt(((200 - 250)**2 + (300 - 250)**2) / 2)
        assert report.confidence_band == pytest.approx((mean - sigma, mean + sigma), rel=1e-6)

    def test_implied_upside_sign(self):
        """Positive implied_upside when composite > current_price."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [self._make_row("DCF", "Base", 200.0, price=100.0)]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=100.0,
            rows=rows, models_run=["DCF"], models_skipped=[],
        )
        assert report.implied_upside == pytest.approx(1.0)  # 100% upside

    def test_no_models_ran_note_contains_guidance(self):
        """When all models are blocked, note must explain and suggest P/S."""
        from domain.valuation.models.summary import ValuationSummaryReport
        report = ValuationSummaryReport.build(
            ticker="AI", current_price=8.97,
            rows=[], models_run=[], models_skipped=["DCF", "PE", "ROE"],
        )
        assert report.composite_intrinsic is None
        assert "P/S" in report.note or "revenue" in report.note.lower(), (
            f"Note should mention P/S model.  Got: {report.note}"
        )
        assert "AI" in report.note

    def test_single_model_agreement_is_zero(self):
        """Single model → perfect agreement score = 0.0."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [self._make_row("DCF", "Base", 300.0)]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["DCF"], models_skipped=[],
        )
        assert report.model_agreement_score == 0.0

    def test_models_run_and_skipped_recorded(self):
        """models_run and models_skipped must be stored exactly as passed."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [self._make_row("DCF", "Base", 200.0)]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows,
            models_run=["DCF"],
            models_skipped=["PE", "ROE"],
        )
        assert report.models_run    == ["DCF"]
        assert report.models_skipped == ["PE", "ROE"]

    def test_bear_bull_rows_excluded_from_composite(self):
        """Bear and Bull rows must not contribute to composite_intrinsic."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [
            self._make_row("DCF", "Bear", 50.0),
            self._make_row("DCF", "Base", 200.0),
            self._make_row("DCF", "Bull", 400.0),
        ]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["DCF"], models_skipped=[],
        )
        assert report.composite_intrinsic == pytest.approx(200.0)

    def test_note_mentions_high_dispersion_when_agreement_low(self):
        """When agreement > 0.40, note should warn about low model agreement."""
        from domain.valuation.models.summary import ValuationSummaryReport
        # Widely spread Base IVs → high agreement score
        rows = [
            self._make_row("M1", "Base", 50.0,   price=100.0),
            self._make_row("M2", "Base", 500.0,  price=100.0),
        ]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=100.0,
            rows=rows, models_run=["M1","M2"], models_skipped=[],
        )
        assert report.model_agreement_score > 0.40
        assert "LOW" in report.note or "low" in report.note.lower() or "agreement" in report.note.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Integration regression: Phase 1 results unaffected by Phase 2 changes
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase2Regression:
    """
    Verify Phase 2 changes don't regress Phase 1 outcomes.
    """

    def test_orcl_dcf_still_suitable_after_phase2(self):
        """ORCL DCF suitability (BUG-A) must still pass after Phase 2."""
        from application.valuations.dcf.validator import DCFChecker
        result = DCFChecker(make_orcl_metrics()).evaluate()
        assert result.is_suitable is True
        assert result.total_severity_score < 99

    def test_adbe_roe_buyback_substituted_after_phase2(self):
        """ADBE ROE buyback substitution (BUG-B) must persist after Phase 2."""
        from application.valuations.roe.valuation import execute_roe_scenarios
        report = execute_roe_scenarios(make_adbe_metrics())
        for _, result in report.scenarios.items():
            assert result.buyback_substituted is True
            assert result.npv_dividends > 0

    def test_orcl_roe_capped_after_phase2(self):
        """ORCL ROE cap (BUG-C) must persist after Phase 2."""
        from application.valuations.roe.valuation import execute_roe_scenarios
        report = execute_roe_scenarios(make_orcl_metrics())
        for _, result in report.scenarios.items():
            assert result.roe_was_capped is True
            assert abs(result.roe_applied - 0.35) < 1e-6

    def test_ai_dcf_still_blocked_after_phase2(self):
        """AI DCF must remain blocked (dual negative, no normalised FCF)."""
        from application.valuations.dcf.validator import DCFChecker
        result = DCFChecker(make_ai_metrics()).evaluate()
        assert result.is_suitable is False
        assert result.total_severity_score == 99