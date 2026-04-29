"""
Tests for BUG-B fix:
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


# ── Test UT-B1 ────────────────────────────────────────────────────────────────

class TestBugB_BuybackSubstitution:
    """UT-B1 — ADBE profile: zero dividends, large buybacks → buyback seed used."""

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
        Previously this was always 0 — the core symptom of BUG-B.
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
        Bear intrinsic value with buyback substitution must exceed the old
        (broken) value of ~$119.55 (npv_required_value alone, no distributions).
        The buyback yield of 10.59% on a $28.29 book value adds material NPV.
        """
        report = _execute_roe(make_adbe_metrics())
        bear = report.scenarios["Bear"]
        # Old broken Bear = $119.55 (npv_required_value only, zero dividends)
        # With ADBE buybacks ~$10.5B / 404.2M shares = ~$25.97/share seed,
        # NPV of distributions should push the total meaningfully above $119.55.
        assert bear.intrinsic_value > 119.55, (
            f"Bear intrinsic value {bear.intrinsic_value:.2f} should exceed the "
            f"pre-fix value of $119.55 after buyback substitution."
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


# ── Test UT-B2 ────────────────────────────────────────────────────────────────

class TestBugB_NoRegressionWithDividends:
    """UT-B2 — ORCL profile: positive dividends → buyback_substituted=False."""

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


# ── Test UT-B3: edge cases ────────────────────────────────────────────────────

class TestBugB_EdgeCases:

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
