"""
Tests for BUG-C fix:
  roe_valuation() must apply params.roe_cap to return_on_equity before
  computing terminal income when the live ROE exceeds the sector ceiling.

  ORCL ROE = 42.11%  >  technology cap = 35%.
  Expected: roe_was_capped=True, roe_applied=0.35, year_n_income computed
            with 0.35 rather than 0.4211.
"""
import pytest

from tests.unit.fixtures import make_orcl_metrics, make_adbe_metrics


_TECH_ROE_CAP = 0.35   # from roe.yaml technology key


def _execute_roe(metrics, params=None):
    from application.valuations.roe.valuation import execute_roe_scenarios
    return execute_roe_scenarios(metrics, params)


def _get_params(metrics):
    from application.valuations.roe.defaults import get_params
    return get_params(metrics)


# ── Test UT-C1 ────────────────────────────────────────────────────────────────

class TestBugC_RoeCap_Applied:
    """UT-C1 — ORCL: ROE 42.11% > 35% cap → capping must fire."""

    def test_roe_was_capped_is_true(self):
        """roe_was_capped flag must be True for all ORCL scenarios."""
        report = _execute_roe(make_orcl_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.roe_was_capped is True, (
                f"{scenario_name}: Expected roe_was_capped=True for ORCL "
                f"(ROE=42.11% > cap=35%)."
            )

    def test_roe_applied_equals_cap(self):
        """roe_applied must equal the config cap (0.35) not the raw ROE (0.4211)."""
        report = _execute_roe(make_orcl_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.roe_applied is not None
            assert abs(result.roe_applied - _TECH_ROE_CAP) < 1e-6, (
                f"{scenario_name}: roe_applied={result.roe_applied:.4f}, "
                f"expected {_TECH_ROE_CAP}."
            )

    def test_year_n_income_uses_capped_roe(self):
        """
        year_n_income = roe_applied * final_equity_per_share.
        Verify it matches the capped ROE, not the raw ROE.
        """
        report = _execute_roe(make_orcl_metrics())
        for scenario_name, result in report.scenarios.items():
            final_equity = result.shareholders_equity_progression[-1]
            expected_income_capped = _TECH_ROE_CAP * final_equity
            expected_income_raw    = 0.4211       * final_equity   # would be wrong
            assert abs(result.year_n_income - expected_income_capped) < 0.01, (
                f"{scenario_name}: year_n_income={result.year_n_income:.4f}, "
                f"expected {expected_income_capped:.4f} (capped), "
                f"NOT {expected_income_raw:.4f} (raw)."
            )

    def test_intrinsic_value_lower_than_uncapped(self):
        """
        Capping ROE at 35% instead of 42.11% must produce a lower intrinsic
        value (less rosy terminal income → smaller required_value).
        Compare against an explicitly uncapped run (roe_cap=None).
        """
        from domain.valuation.models.roe import ROEParameters
        orcl   = make_orcl_metrics()
        params_capped   = _get_params(orcl)                  # cap=0.35 from config
        params_uncapped = ROEParameters(                      # no cap
            projection_years=params_capped.projection_years,
            margin_of_safety=params_capped.margin_of_safety,
            discount_rate=params_capped.discount_rate,
            roe_cap=None,
        )
        report_capped   = _execute_roe(orcl, params_capped)
        report_uncapped = _execute_roe(orcl, params_uncapped)

        for scenario in ("Bear", "Base", "Bull"):
            iv_capped   = report_capped.scenarios[scenario].intrinsic_value
            iv_uncapped = report_uncapped.scenarios[scenario].intrinsic_value
            assert iv_capped < iv_uncapped, (
                f"{scenario}: capped IV ({iv_capped:.2f}) should be less than "
                f"uncapped IV ({iv_uncapped:.2f})."
            )

    def test_validator_emits_roe_cap_warning_factor(self):
        """ROEChecker must emit a zero-weight WARNING factor about the cap."""
        from application.valuations.roe.validator import ROEChecker
        from domain.valuation.policies import FactorSeverity
        checker = ROEChecker(make_orcl_metrics())
        result  = checker.evaluate()
        cap_factors = [f for f in result.factors if "Cap" in f.name or "cap" in f.name.lower()]
        assert cap_factors, (
            f"Expected an ROE Cap factor in validator output.  "
            f"Got factors: {[f.name for f in result.factors]}"
        )
        # Must be zero weight — informational only, must not affect suitability
        for f in cap_factors:
            assert f.weight == 0, (
                f"ROE Cap factor '{f.name}' has weight={f.weight}, expected 0."
            )

    def test_validator_still_suitable_despite_cap_warning(self):
        """
        Emitting the ROE-cap INFO factor must NOT push the suitability score
        above the block threshold.  ORCL has high D/E → WARNING score=1,
        plus the cap factor (weight=0) → total should still be ≤ 5 (suitable).
        """
        from application.valuations.roe.validator import ROEChecker
        checker = ROEChecker(make_orcl_metrics())
        result  = checker.evaluate()
        assert result.is_suitable is True, (
            f"ORCL ROE should still be suitable (D/E warning only).  "
            f"Score={result.total_severity_score}, "
            f"interpretation='{result.interpretation}'"
        )


# ── Test UT-C2 ────────────────────────────────────────────────────────────────

class TestBugC_RoeCap_NotApplied:
    """UT-C2 — ADBE: ROE 63.05% but cap is still technology=35% → ADBE also capped."""

    def test_adbe_is_also_capped(self):
        """
        ADBE ROE = 63.05% also exceeds the 35% technology cap.
        Verify cap fires — this is a broader test of the mechanism.
        """
        report = _execute_roe(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.roe_was_capped is True, (
                f"{scenario_name}: ADBE ROE=63.05% > cap=35% should be capped."
            )

    def test_below_cap_no_capping(self):
        """
        When a company's ROE is below the cap, roe_was_capped must be False
        and roe_applied must equal the raw ROE.
        """
        import dataclasses
        from domain.valuation.models.roe import ROEParameters
        m = make_orcl_metrics()
        # Artificially lower ROE to below the 35% cap
        m.ratios = dataclasses.replace(m.ratios, return_on_equity=0.20)
        params = ROEParameters(
            projection_years=10,
            margin_of_safety=0.30,
            discount_rate=0.11,
            roe_cap=_TECH_ROE_CAP,
        )
        report = _execute_roe(m, params)
        for scenario_name, result in report.scenarios.items():
            assert result.roe_was_capped is False, (
                f"{scenario_name}: ROE=20% < cap=35% should NOT be capped."
            )
            assert abs(result.roe_applied - 0.20) < 1e-6, (
                f"{scenario_name}: roe_applied should equal raw ROE (0.20), "
                f"got {result.roe_applied}."
            )

    def test_roe_cap_none_disables_capping(self):
        """When roe_cap=None the raw ROE is always used regardless of magnitude."""
        import dataclasses
        from domain.valuation.models.roe import ROEParameters
        orcl = make_orcl_metrics()
        params = ROEParameters(
            projection_years=10,
            margin_of_safety=0.30,
            discount_rate=0.11,
            roe_cap=None,
        )
        report = _execute_roe(orcl, params)
        for scenario_name, result in report.scenarios.items():
            assert result.roe_was_capped is False
            assert abs(result.roe_applied - 0.4211) < 1e-4, (
                f"{scenario_name}: roe_applied={result.roe_applied} should be "
                f"raw ROE=0.4211 when roe_cap=None."
            )


# ── Test UT-C3: mathematical correctness ─────────────────────────────────────

class TestBugC_MathematicalCorrectness:
    """Verify the terminal income formula uses the capped ROE exactly."""

    def test_required_value_formula(self):
        """
        required_value = year_n_income / discount_rate
        With cap=0.35, discount_rate=0.11, and known final equity we can
        derive the exact expected required_value for each scenario.
        """
        report = _execute_roe(make_orcl_metrics())
        params = report.params
        for scenario_name, result in report.scenarios.items():
            final_equity = result.shareholders_equity_progression[-1]
            expected_yn_income    = _TECH_ROE_CAP * final_equity
            expected_req_value    = expected_yn_income / params.discount_rate
            expected_npv_req      = expected_req_value / ((1 + params.discount_rate) ** params.projection_years)

            assert abs(result.year_n_income    - expected_yn_income) < 0.01, (
                f"{scenario_name} year_n_income mismatch: "
                f"{result.year_n_income:.4f} vs {expected_yn_income:.4f}"
            )
            assert abs(result.required_value   - expected_req_value) < 0.01, (
                f"{scenario_name} required_value mismatch: "
                f"{result.required_value:.4f} vs {expected_req_value:.4f}"
            )
            assert abs(result.npv_required_value - expected_npv_req) < 0.01, (
                f"{scenario_name} npv_required_value mismatch: "
                f"{result.npv_required_value:.4f} vs {expected_npv_req:.4f}"
            )
