"""
Tests for buyback distribution handling:
  execute_roe_scenarios() must substitute share_buybacks_ttm as the
  distribution component when dividends_paid_ttm = 0 and buybacks > 0.

  Previously the validator promised this behaviour but execute_roe_scenarios()
  always used dividends — leaving dividend_rate_per_share = $0 for ADBE and
  making npv_dividends = 0 for all scenarios, artificially compressing the
  Bear intrinsic value.
"""
import pytest

from tests.unit.fixtures import make_adbe_metrics, make_orcl_metrics


def _execute_roe(metrics, params=None):
    from application.valuations.roe.valuation import execute_roe_scenarios
    return execute_roe_scenarios(metrics, params)


# Buyback distribution seed

class TestROEBuybackDistributionSeed:
    """ADBE profile: zero dividends, large buybacks → buyback seed used."""

    def test_buyback_substituted_flag_is_true(self):
        """ROEValuationResult.buyback_substituted must be True for ADBE."""
        report = _execute_roe(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.buyback_substituted is True, (
                f"Expected buyback_substituted=True in {scenario_name} scenario "
                f"for ADBE (dividends=0, buybacks>0)."
            )

    def test_npv_dividends_is_positive(self):
        """
        With buyback substitution, NPV of distributions must be > 0.
        Previously this was always 0 — the core symptom of buyback distribution handling.
        """
        report = _execute_roe(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.npv_dividends > 0, (
                f"Expected npv_dividends > 0 in {scenario_name} scenario after "
                f"buyback substitution.  Got {result.npv_dividends}."
            )

    def test_dividend_progression_is_nonzero(self):
        """dividend_progression list must contain positive values (not all zeros)."""
        report = _execute_roe(make_adbe_metrics())
        for scenario_name, result in report.scenarios.items():
            assert any(v > 0 for v in result.dividend_progression), (
                f"{scenario_name}: dividend_progression is all zeros — "
                f"buyback substitution did not propagate through roe_valuation()."
            )

    def test_intrinsic_value_increases_vs_zero_distribution(self):
        """
        Bear intrinsic value with buyback substitution must exceed the
        no-distribution value of ~$119.55 (npv_required_value alone).
        The buyback yield of 10.59% on a $28.29 book value adds material NPV.
        """
        report = _execute_roe(make_adbe_metrics())
        bear = report.scenarios["Bear"]
        # Old broken Bear = $119.55 (npv_required_value only, zero dividends)
        # With ADBE buybacks ~$10.5B / 404.2M shares = ~$25.97/share seed,
        # NPV of distributions should push the total meaningfully above $119.55.
        assert bear.intrinsic_value > 119.55, (
            f"Bear intrinsic value {bear.intrinsic_value:.2f} should exceed the "
            f"no-distribution value of $119.55 after buyback substitution."
        )

    def test_distribution_seed_equals_buybacks_per_share(self):
        """
        The per-share distribution seed must equal buybacks / shares.
        ADBE: buybacks = 10_509_000_000, shares = 404_200_000
        Expected seed ≈ 25.9797/share
        """
        adbe = make_adbe_metrics()
        expected_seed = abs(adbe.cash_flow.share_buybacks_ttm) / adbe.market_data.shares_outstanding
        report = _execute_roe(adbe)
        # The seed is applied to year-1, which then grows.  Back-calculate year-0
        # from year-1 of the Base scenario: dividend[0] = seed * (1 + g_year1).
        base = report.scenarios["Base"]
        g1   = base.growth_rates[0]
        implied_seed = base.dividend_progression[0] / (1 + g1)
        assert abs(implied_seed - expected_seed) < 0.01, (
            f"Distribution seed {implied_seed:.4f} doesn't match expected "
            f"{expected_seed:.4f} (buybacks/shares)."
        )


# Dividend distribution seed

class TestROEDividendDistributionSeed:
    """ORCL profile: positive dividends → buyback_substituted=False."""

    def test_buyback_substituted_flag_is_false(self):
        """ORCL pays dividends — buyback_substituted must be False."""
        report = _execute_roe(make_orcl_metrics())
        for scenario_name, result in report.scenarios.items():
            assert result.buyback_substituted is False, (
                f"Expected buyback_substituted=False for ORCL (pays dividends) "
                f"in {scenario_name} scenario."
            )

    def test_distribution_seed_equals_dividends_per_share(self):
        """
        Distribution seed for ORCL must equal abs(dividends_paid_ttm) / shares.
        ORCL: dividends = 5_688_000_000, shares = 2_876_046_000
        Expected seed ≈ 1.9777/share
        """
        orcl = make_orcl_metrics()
        expected_seed = abs(orcl.cash_flow.dividends_paid_ttm) / orcl.market_data.shares_outstanding
        report = _execute_roe(orcl)
        base = report.scenarios["Base"]
        g1   = base.growth_rates[0]
        implied_seed = base.dividend_progression[0] / (1 + g1)
        assert abs(implied_seed - expected_seed) < 0.01, (
            f"Dividend seed {implied_seed:.4f} doesn't match expected "
            f"{expected_seed:.4f} for ORCL."
        )


# Distribution seed edge cases

class TestROEDistributionSeedEdgeCases:

    def _adbe_with_overrides(self, **cf_overrides):
        import dataclasses
        m = make_adbe_metrics()
        m.cash_flow = dataclasses.replace(m.cash_flow, **cf_overrides)
        return m

    def test_zero_dividends_zero_buybacks_seed_is_zero(self):
        """
        When both dividends and buybacks are zero, distribution seed = 0.
        NPV of distributions = 0.  buyback_substituted remains False.
        """
        m = self._adbe_with_overrides(
            dividends_paid_ttm=0.0,
            share_buybacks_ttm=0.0,
        )
        report = _execute_roe(m)
        for scenario_name, result in report.scenarios.items():
            assert result.buyback_substituted is False
            assert result.npv_dividends == 0.0, (
                f"{scenario_name}: npv_dividends={result.npv_dividends}, expected 0."
            )

    def test_positive_dividends_and_buybacks_uses_dividends(self):
        """
        When both are non-zero, dividends take priority (existing behaviour).
        buyback_substituted=False.
        """
        m = self._adbe_with_overrides(
            dividends_paid_ttm=-1_000_000_000.0,   # $1B dividends
            share_buybacks_ttm=-10_509_000_000.0,  # $10.5B buybacks
        )
        report = _execute_roe(m)
        for scenario_name, result in report.scenarios.items():
            assert result.buyback_substituted is False, (
                f"When dividends are non-zero, buyback_substituted should be False."
            )
        # Seed ≈ 1B / 404.2M ≈ 2.47/share — lower than buyback seed
        base = report.scenarios["Base"]
        g1   = base.growth_rates[0]
        implied_seed = base.dividend_progression[0] / (1 + g1)
        expected_div_seed = 1_000_000_000 / make_adbe_metrics().market_data.shares_outstanding
        assert abs(implied_seed - expected_div_seed) < 0.01


"""
Tests for ROE cap handling:
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


# ROE cap applied

class TestROEReturnCapApplied:
    """ORCL: ROE 42.11% > 35% cap → capping must fire."""

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

# ROE cap not applied

class TestROEReturnCapNotApplied:
    """ADBE: ROE 63.05% but cap is still technology=35% → ADBE also capped."""

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

# ROE cap formula

class TestROEReturnCapFormula:
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


from types import SimpleNamespace

import pytest

from application.valuations.roe.valuation import roe_valuation
from domain.valuation.models.roe import ROEParameters, ROEValuationInput


def test_roe_valuation_equity_per_share_progression_starts_per_share() -> None:
    stock_metrics = SimpleNamespace(
        balance_sheet=SimpleNamespace(total_equity=1000.0),
        market_data=SimpleNamespace(shares_outstanding=100.0, current_price=10.0),
        ratios=SimpleNamespace(return_on_equity=0.2),
    )
    params = ROEParameters(projection_years=3, margin_of_safety=0.25, discount_rate=0.1)
    roe_input = ROEValuationInput(
        stock_metrics=stock_metrics,
        dividend_rate_per_share=1.0,
        growth_rates=[0.1, 0.1, 0.1],
        params=params,
    )

    result = roe_valuation(roe_input)

    assert result.shareholders_equity_progression == pytest.approx([11.0, 12.1, 13.31])


def test_roe_valuation_discounts_first_year_cash_flow() -> None:
    stock_metrics = SimpleNamespace(
        balance_sheet=SimpleNamespace(total_equity=1000.0),
        market_data=SimpleNamespace(shares_outstanding=100.0, current_price=10.0),
        ratios=SimpleNamespace(return_on_equity=0.2),
    )
    params = ROEParameters(projection_years=1, margin_of_safety=0.25, discount_rate=0.1)
    roe_input = ROEValuationInput(
        stock_metrics=stock_metrics,
        dividend_rate_per_share=1.0,
        growth_rates=[0.1],
        params=params,
    )

    result = roe_valuation(roe_input)

    assert result.dividend_progression == pytest.approx([1.1])
    assert result.npv_dividend_progression == pytest.approx([1.0])
