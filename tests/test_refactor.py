"""
tests/test_refactor.py

Covers:
  Plan B — YfinanceFetcher / YfinanceParser split
    * YfinanceParser works from fixture RawTickerData (no network)
    * get_ttm_from_quarters sums correctly
    * get_latest_numeric respects period
    * EPS history paths (direct, from-statement, approximation, missing)
    * EPS path 3 no longer applies FX rate (bug fix)
    * price history builds PriceHistory from raw DataFrame

  Plan A — immutable Valuation and Ratios
    * Valuation.build() derives cost_of_debt and corporate_tax_rate
    * Valuation is frozen — mutation raises FrozenInstanceError
    * Ratios.build() computes all ratio fields correctly
    * Ratios is frozen — mutation raises FrozenInstanceError
    * StockMetrics.__post_init__ wires build() calls correctly
    * Ratios.build() with missing inputs logs a warning, returns all-None

  Infrastructure
    * FinancialRepository is @runtime_checkable
    * MetricsLoader raises TypeError for non-conforming loader_cls
    * currency_service no longer calls print()
"""
from __future__ import annotations

import dataclasses
import io
import logging
import sys
import unittest
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── path setup ─────────────────────────────────────────────────────────── #
sys.path.insert(0, "src")

from infrastructure.repositories.yfinance.raw_ticker_data import (
    RawTickerData, empty_raw,
)
from infrastructure.repositories.yfinance.yfinance_parser import YfinanceParser
from infrastructure.repositories.financial_repository import (
    FinancialRepository, Statement, Period, Action,
)
from infrastructure.repositories.yfinance.mappers.yfinance_fields import (
    YfFinancialField, CurrencyType,
)
from infrastructure.repositories.yfinance.value_objects import DataQuality
from domain.metrics.stock import (
    Valuation, Ratios, Financials, CashFlow, BalanceSheet, MarketData,
    HistoricalData, StockMetrics, CompanyProfile,
)
from domain.core.enums import Sectors


# =========================================================================== #
# Helpers / fixtures
# =========================================================================== #

def _make_quarterly_income(
    rows: dict[str, list[float]],
    dates: list[str] | None = None,
) -> pd.DataFrame:
    """Build a quarterly income statement DataFrame in yfinance column-per-date format."""
    if dates is None:
        dates = ["2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"]
    df = pd.DataFrame(rows, index=dates).T
    df.columns = pd.to_datetime(df.columns)
    return df


def _make_raw(
    quarterly_income: pd.DataFrame | None = None,
    quarterly_cashflow: pd.DataFrame | None = None,
    quarterly_balance: pd.DataFrame | None = None,
    annual_income: pd.DataFrame | None = None,
    earnings_history: pd.DataFrame | None = None,
    price_history: pd.DataFrame | None = None,
    info: dict | None = None,
) -> RawTickerData:
    empty = pd.DataFrame()
    return RawTickerData(
        ticker_symbol="TEST",
        info=info or {},
        annual_income=annual_income if annual_income is not None else empty,
        annual_cashflow=empty,
        annual_balance_sheet=empty,
        quarterly_income=quarterly_income if quarterly_income is not None else empty,
        quarterly_cashflow=quarterly_cashflow if quarterly_cashflow is not None else empty,
        quarterly_balance_sheet=quarterly_balance if quarterly_balance is not None else empty,
        earnings_history_raw=earnings_history,
        price_history_raw=price_history,
    )


def _revenue_field() -> YfFinancialField:
    return YfFinancialField(
        label=["Total Revenue", "Revenue"],
        currency_type=CurrencyType.FINANCIAL,
        statement=Statement.INCOME,
        action=Action.GET_TTM_VALUE,
    )


def _revenue_latest_field(period: Period = Period.QUARTERLY) -> YfFinancialField:
    return YfFinancialField(
        label=["Total Revenue", "Revenue"],
        currency_type=CurrencyType.FINANCIAL,
        statement=Statement.INCOME,
        action=Action.GET_LATEST_VALUE,
        period=period,
    )


def _make_financials(**overrides) -> Financials:
    defaults = dict(
        revenue_ttm=1_000.0,
        ebit_ttm=200.0,
        ebt_ttm=180.0,
        tax_expense_ttm=36.0,
        interest_expense_ttm=-20.0,
        gross_profit_ttm=500.0,
        operating_income_ttm=200.0,
        net_income_ttm=144.0,
        revenue_ttm_prev=900.0,
        net_income_ttm_prev=120.0,
        da_ttm=50.0,
    )
    defaults.update(overrides)
    return Financials(**defaults)


def _make_balance_sheet(**overrides) -> BalanceSheet:
    defaults = dict(
        total_debt=400.0,
        total_equity=600.0,
        cash_and_equivalents=100.0,
        total_assets=1_200.0,
        total_liabilities=600.0,
        current_assets=300.0,
        current_liabilities=150.0,
        inventory=50.0,
    )
    defaults.update(overrides)
    return BalanceSheet(**defaults)


def _make_cash_flow(**overrides) -> CashFlow:
    defaults = dict(
        operating_cf_ttm=200.0,
        capex_ttm=-50.0,
        oper_cf_last_year=180.0,
        latest_annual_capex=-40.0,
        oper_cf_last_quarter=55.0,
        latest_quarter_capex=-12.0,
        dividends_paid_ttm=-30.0,
        share_buybacks_ttm=-20.0,
    )
    defaults.update(overrides)
    return CashFlow(**defaults)


def _make_market_data(**overrides) -> MarketData:
    defaults = dict(
        current_price=50.0,
        shares_outstanding=100,
        market_cap=5_000.0,
        beta=1.2,
        eps_ttm=1.44,
        pe_ttm=34.7,
        last_quarter_eps=0.38,
        last_year_eps=1.30,
        low_52_week=35.0,
        high_52_week=60.0,
        fifty_day_avg=48.0,
        two_hundred_day_avg=46.0,
        volume=1_000_000,
        avg_volume=900_000,
    )
    defaults.update(overrides)
    return MarketData(**defaults)


# =========================================================================== #
# Plan B — YfinanceParser (no network)
# =========================================================================== #

class TestYfinanceParserConstruction:
    def test_requires_raw_ticker_data(self):
        with pytest.raises(TypeError, match="RawTickerData"):
            YfinanceParser("not a raw object")  # type: ignore

    def test_accepts_empty_raw(self):
        parser = YfinanceParser(empty_raw("AAPL"))
        assert parser is not None

    def test_mapper_is_set(self):
        parser = YfinanceParser(empty_raw())
        assert parser.mapper is not None


class TestYfinanceParserTTM:
    def test_ttm_sums_four_quarters(self):
        """get_ttm_from_quarters sums the four most recent quarterly values."""
        df = _make_quarterly_income({"Total Revenue": [100.0, 90.0, 80.0, 70.0]})
        raw = _make_raw(quarterly_income=df)
        parser = YfinanceParser(raw)
        result = parser.get_ttm_from_quarters(_revenue_field(), year_offset=0)
        assert result == pytest.approx(340.0)

    def test_ttm_year_offset_1(self):
        """year_offset=1 uses the four quarters starting from index 4."""
        dates = [
            "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31",
            "2023-09-30", "2023-06-30", "2023-03-31", "2022-12-31",
        ]
        df = _make_quarterly_income(
            {"Total Revenue": [100.0, 90.0, 80.0, 70.0, 60.0, 55.0, 50.0, 45.0]},
            dates=dates,
        )
        raw = _make_raw(quarterly_income=df)
        parser = YfinanceParser(raw)
        result = parser.get_ttm_from_quarters(_revenue_field(), year_offset=1)
        # sum of indices 4-7: 60+55+50+45 = 210
        assert result == pytest.approx(210.0)

    def test_ttm_returns_none_when_field_absent(self):
        raw = _make_raw()  # empty DataFrames
        parser = YfinanceParser(raw)
        result = parser.get_ttm_from_quarters(_revenue_field())
        assert result is None

    def test_ttm_applies_fx_rate(self):
        """Financial-currency fields are multiplied by the FX rate."""
        df = _make_quarterly_income({"Total Revenue": [100.0, 100.0, 100.0, 100.0]})
        raw = _make_raw(quarterly_income=df, info={"financialCurrency": "GBP"})
        with patch(
            "infrastructure.repositories.yfinance.yfinance_parser.get_rate_to_usd",
            side_effect=lambda c: 1.25 if c == "GBP" else 1.0,
        ):
            parser = YfinanceParser(raw)
            result = parser.get_ttm_from_quarters(_revenue_field())
        # 400 * 1.25 = 500
        assert result == pytest.approx(500.0)

    def test_negative_year_offset_raises(self):
        parser = YfinanceParser(empty_raw())
        with pytest.raises(ValueError, match="year_offset"):
            parser.get_ttm_from_quarters(_revenue_field(), year_offset=-1)


class TestYfinanceParserGetLatestNumeric:
    def test_quarterly_latest_returns_most_recent(self):
        df = _make_quarterly_income({"Total Revenue": [100.0, 90.0, 80.0, 70.0]})
        raw = _make_raw(quarterly_income=df)
        parser = YfinanceParser(raw)
        field = _revenue_latest_field(Period.QUARTERLY)
        result = parser.get_latest_numeric(field)
        assert result == pytest.approx(100.0)

    def test_annual_latest_respects_period(self):
        """When period=ANNUAL the parser looks in the annual DataFrame."""
        dates = ["2023-12-31", "2022-12-31", "2021-12-31"]
        df = pd.DataFrame(
            {"Total Revenue": [500.0, 450.0, 400.0]},
            index=dates,
        ).T
        df.columns = pd.to_datetime(df.columns)
        raw = _make_raw(annual_income=df)
        parser = YfinanceParser(raw)
        field = _revenue_latest_field(Period.ANNUAL)
        result = parser.get_latest_numeric(field)
        assert result == pytest.approx(500.0)

    def test_returns_none_when_absent(self):
        parser = YfinanceParser(empty_raw())
        assert parser.get_latest_numeric(_revenue_latest_field()) is None


class TestYfinanceParserEPSHistory:
    def test_path1_direct_earnings_history(self):
        """EPS comes from earnings_history_raw.epsActual when available."""
        eh = pd.DataFrame({"epsActual": [1.0, 1.1, 1.2, 1.3]})
        raw = _make_raw(earnings_history=eh)
        parser = YfinanceParser(raw)
        assert parser.get_eps_data_quality() == DataQuality.DIRECT
        assert parser.get_eps_history() == pytest.approx([1.0, 1.1, 1.2, 1.3])

    def test_path1_no_fx_applied(self):
        """EPS from path 1 must NOT be FX-multiplied."""
        eh = pd.DataFrame({"epsActual": [2.0, 2.5]})
        raw = _make_raw(earnings_history=eh, info={"financialCurrency": "GBP"})
        with patch(
            "infrastructure.repositories.yfinance.yfinance_parser.get_rate_to_usd",
            side_effect=lambda c: 1.25 if c == "GBP" else 1.0,
        ):
            parser = YfinanceParser(raw)
        # Must remain 2.0, 2.5 — not 2.5, 3.125
        assert parser.get_eps_history() == pytest.approx([2.0, 2.5])

    def test_path2_from_quarterly_statement(self):
        """Falls back to quarterly income EPS row when earnings_history absent."""
        df = _make_quarterly_income({"diluted eps": [0.5, 0.6, 0.7, 0.8]})
        raw = _make_raw(quarterly_income=df)
        parser = YfinanceParser(raw)
        assert parser.get_eps_data_quality() == DataQuality.DERIVED_FROM_STATEMENT

    def test_path2_no_fx_applied(self):
        df = _make_quarterly_income({"diluted eps": [1.0, 1.0, 1.0, 1.0]})
        raw = _make_raw(quarterly_income=df, info={"financialCurrency": "EUR"})
        with patch(
            "infrastructure.repositories.yfinance.yfinance_parser.get_rate_to_usd",
            side_effect=lambda c: 1.08 if c == "EUR" else 1.0,
        ):
            parser = YfinanceParser(raw)
        eps = parser.get_eps_history()
        # All values should be 1.0 — NOT 1.08
        assert all(abs(v - 1.0) < 0.01 for v in eps)

    def test_path3_net_income_over_shares_no_fx(self):
        """
        Path 3: EPS = Net Income / Shares.
        The FX rate must NOT be applied — this was the bug in the original loader.
        Net income is in financial currency; dividing by shares gives per-share
        in that currency.  No conversion needed.
        """
        df = _make_quarterly_income({"Net Income": [400.0, 400.0, 400.0, 400.0]})
        info = {
            "sharesOutstanding": 100,
            "financialCurrency": "GBP",
        }
        raw = _make_raw(quarterly_income=df, info=info)
        with patch(
            "infrastructure.repositories.yfinance.yfinance_parser.get_rate_to_usd",
            side_effect=lambda c: 1.25 if c == "GBP" else 1.0,
        ):
            parser = YfinanceParser(raw)
        assert parser.get_eps_data_quality() == DataQuality.DERIVED_FROM_NET_INCOME
        # Expected: 400 / 100 = 4.0 per value, NOT 400 * 1.25 / 100 = 5.0
        eps = parser.get_eps_history()
        assert eps is not None
        for v in eps:
            assert abs(v - 4.0) < 0.01, f"EPS {v} looks FX-converted (expected ~4.0)"

    def test_path4_missing_returns_none(self):
        raw = _make_raw()
        parser = YfinanceParser(raw)
        assert parser.get_eps_data_quality() == DataQuality.MISSING
        assert parser.get_eps_history() is None


class TestYfinanceParserPriceHistory:
    def test_builds_price_history_from_raw(self):
        df = pd.DataFrame({"Close": [10.0, 12.0, 15.0, 11.0]})
        raw = _make_raw(price_history=df)
        parser = YfinanceParser(raw)
        assert parser.get_price_history() == pytest.approx([10.0, 12.0, 15.0, 11.0])

    def test_highest_price(self):
        df = pd.DataFrame({"Close": [10.0, 12.0, 15.0, 11.0]})
        raw = _make_raw(price_history=df)
        parser = YfinanceParser(raw)
        assert parser.get_highest_price() == pytest.approx(15.0)

    def test_adj_close_preferred_over_close(self):
        df = pd.DataFrame({"Adj Close": [9.0, 11.0, 14.0], "Close": [10.0, 12.0, 15.0]})
        raw = _make_raw(price_history=df)
        parser = YfinanceParser(raw)
        assert parser.get_price_history() == pytest.approx([9.0, 11.0, 14.0])

    def test_empty_price_history_returns_none(self):
        raw = _make_raw(price_history=pd.DataFrame())
        parser = YfinanceParser(raw)
        assert parser.get_price_history() is None
        assert parser.get_highest_price() is None


# =========================================================================== #
# Plan A — immutable Valuation
# =========================================================================== #

class TestValuationBuild:
    def setup_method(self):
        self.fin = _make_financials()
        self.bs = _make_balance_sheet()
        self.cf = _make_cash_flow()
        self.md = _make_market_data()

    def test_derives_corporate_tax_rate(self):
        # tax_expense=36, ebt=180 → 36/180 = 0.2
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )
        assert v.corporate_tax_rate == pytest.approx(0.2)

    def test_derives_cost_of_debt(self):
        # |interest_expense|=20, total_debt=400 → 20/400 = 0.05
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )
        assert v.cost_of_debt == pytest.approx(0.05)

    def test_seed_overrides_derived_values(self):
        """Explicit seeds take precedence over derived values."""
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
            cost_of_debt=0.03,
            corporate_tax_rate=0.25,
        )
        assert v.cost_of_debt == pytest.approx(0.03)
        assert v.corporate_tax_rate == pytest.approx(0.25)

    def test_enterprise_value(self):
        # market_cap=5000, total_debt=400, cash=100 → EV=5300
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )
        assert v.enterprise_value == pytest.approx(5_300.0)

    def test_price_to_sales(self):
        # 5000 / 1000 = 5.0
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )
        assert v.price_to_sales == pytest.approx(5.0)

    def test_frozen_raises_on_mutation(self):
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.enterprise_value = 99999  # type: ignore

    def test_highest_price_passthrough(self):
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
            highest_price=75.0,
        )
        assert v.highest_price == pytest.approx(75.0)

    def test_fcf_cagr_computed(self):
        # fcf_ttm = operating(200) + capex(-50) = 150
        # last_year_fcf = 180 + (-40) = 140
        # cagr = (150/140) - 1 ≈ 0.0714
        v = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )
        assert v.fcf_cagr == pytest.approx(150 / 140 - 1, rel=1e-3)

    def test_none_cost_of_debt_when_no_debt(self):
        bs = _make_balance_sheet(total_debt=None)
        v = Valuation.build(
            financials=self.fin, balance_sheet=bs,
            market_data=self.md, cash_flow=self.cf,
        )
        assert v.cost_of_debt is None


# =========================================================================== #
# Plan A — immutable Ratios
# =========================================================================== #

class TestRatiosBuild:
    def setup_method(self):
        self.fin = _make_financials()
        self.bs = _make_balance_sheet()
        self.cf = _make_cash_flow()
        self.md = _make_market_data()
        self.val = Valuation.build(
            financials=self.fin, balance_sheet=self.bs,
            market_data=self.md, cash_flow=self.cf,
        )

    def _build(self) -> Ratios:
        return Ratios.build(
            financials=self.fin,
            cash_flow=self.cf,
            balance_sheet=self.bs,
            market_data=self.md,
            valuation=self.val,
        )

    def test_return_on_equity(self):
        # net_income=144, total_equity=600 → 0.24
        r = self._build()
        assert r.return_on_equity == pytest.approx(0.24)

    def test_return_on_assets(self):
        # net_income=144, total_assets=1200 → 0.12
        r = self._build()
        assert r.return_on_assets == pytest.approx(0.12)

    def test_debt_to_equity(self):
        # 400/600 ≈ 0.6667
        r = self._build()
        assert r.debt_to_equity == pytest.approx(400 / 600)

    def test_fcf_margin(self):
        # fcf_ttm=150, revenue=1000 → 0.15
        r = self._build()
        assert r.fcf_margin == pytest.approx(0.15)

    def test_ev_ebit(self):
        # EV=5300, ebit=200 → 26.5
        r = self._build()
        assert r.ev_ebit == pytest.approx(26.5)

    def test_ev_ebitda(self):
        # EV=5300, ebitda=250 → 21.2
        r = self._build()
        assert r.ev_ebitda == pytest.approx(5_300 / 250)

    def test_frozen_raises_on_mutation(self):
        r = self._build()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.return_on_equity = 0.99  # type: ignore

    def test_missing_inputs_returns_empty_ratios(self, caplog):
        with caplog.at_level(logging.WARNING):
            r = Ratios.build(
                financials=None,  # type: ignore
                cash_flow=self.cf,
                balance_sheet=self.bs,
            )
        assert r.return_on_equity is None
        assert "returning empty Ratios" in caplog.text

    def test_book_value_per_share(self):
        # total_equity=600, shares=100 → 6.0
        r = self._build()
        assert r.book_value_per_share == pytest.approx(6.0)

    def test_interest_coverage(self):
        # ebit=200, interest_expense=-20 → 200/20 = 10
        r = self._build()
        assert r.interest_coverage == pytest.approx(10.0)


# =========================================================================== #
# StockMetrics integration
# =========================================================================== #

class TestStockMetricsPostInit:
    def _make_stock(self, **overrides) -> StockMetrics:
        profile = CompanyProfile(ticker="TEST", sector=Sectors.TECHNOLOGY)
        fin = _make_financials(**overrides.get("financials", {}))
        cf = _make_cash_flow()
        bs = _make_balance_sheet()
        md = _make_market_data()
        # Seed valuation — only highest_price matters here
        seed_val = Valuation(
            highest_price=65.0,
            cost_of_debt=None, corporate_tax_rate=None,
            price_to_sales=None, price_to_book=None,
            median_historical_pe=None, fcf_cagr=None,
            forward_growth_rate=None, enterprise_value=None,
        )
        return StockMetrics(
            profile=profile, financials=fin, cash_flow=cf,
            balance_sheet=bs, market_data=md, valuation=seed_val,
        )

    def test_valuation_is_fully_built(self):
        sm = self._make_stock()
        assert sm.valuation.enterprise_value is not None
        assert sm.valuation.corporate_tax_rate is not None
        assert sm.valuation.cost_of_debt is not None

    def test_ratios_is_fully_built(self):
        sm = self._make_stock()
        assert sm.ratios is not None
        assert sm.ratios.return_on_equity is not None

    def test_valuation_frozen(self):
        sm = self._make_stock()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sm.valuation.enterprise_value = 0  # type: ignore

    def test_ratios_frozen(self):
        sm = self._make_stock()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sm.ratios.return_on_equity = 0  # type: ignore

    def test_phase_order_ratios_use_built_valuation(self):
        """Ratios.ev_ebit must use valuation.enterprise_value from Valuation.build."""
        sm = self._make_stock()
        expected_ev = sm.valuation.enterprise_value
        expected_ev_ebit = expected_ev / sm.financials.ebit_ttm
        assert sm.ratios.ev_ebit == pytest.approx(expected_ev_ebit)


# =========================================================================== #
# Infrastructure — protocol enforcement
# =========================================================================== #

class TestFinancialRepositoryProtocol:
    def test_is_runtime_checkable(self):
        """The protocol must be @runtime_checkable."""
        assert isinstance(None, FinancialRepository) is False

    def test_parser_satisfies_protocol(self):
        parser = YfinanceParser(empty_raw())
        assert isinstance(parser, FinancialRepository)

    def test_non_conforming_class_fails_isinstance(self):
        class BadLoader:
            pass
        assert isinstance(BadLoader(), FinancialRepository) is False


class TestMetricsLoaderProtocolCheck:
    def test_raises_for_non_conforming_loader(self):
        class BadLoader:
            def __init__(self, symbol):
                pass
        from application.metrics_loader.metrics_loader import MetricsLoader
        with pytest.raises(TypeError, match="FinancialRepository"):
            MetricsLoader("AAPL", loader_cls=BadLoader)


# =========================================================================== #
# currency_service — no print()
# =========================================================================== #

class TestCurrencyServiceNoPrint:
    def test_fallback_uses_logger_not_print(self):
        """The fallback path must NOT call print()."""
        from infrastructure.currency.currency_service import get_rate_to_usd, _RATE_CACHE

        # Clear cache so the fallback branch is hit
        _RATE_CACHE.clear()

        captured = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured

        try:
            with patch("requests.Session.get", side_effect=Exception("network down")):
                # ZZZ is not a real currency — will hit the fallback
                get_rate_to_usd("ZZZ")
        finally:
            sys.stdout = original_stdout

        assert captured.getvalue() == "", (
            "currency_service.get_rate_to_usd should not print to stdout; "
            f"got: {captured.getvalue()!r}"
        )


# =========================================================================== #
# empty_raw helper
# =========================================================================== #

class TestEmptyRaw:
    def test_empty_raw_is_valid_raw_ticker_data(self):
        raw = empty_raw("TSLA")
        assert isinstance(raw, RawTickerData)
        assert raw.ticker_symbol == "TSLA"
        assert raw.info == {}
        assert raw.quarterly_income.empty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])