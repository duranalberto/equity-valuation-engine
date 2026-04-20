from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, dataclass_transform

from calculations import metrics_formulas as mf
from calculations import safe_div

from ..core.enums import Sectors
from .history import BalanceSheetHistory, CashFlowHistory, FinancialsHistory


def _bind_fields(cls):
    """
    Bind each dataclass field as a class-level attribute so mapper code can
    reference fields via e.g. ``CompanyProfile.ticker`` instead of the string
    ``"ticker"``.

    Called explicitly after ``@dataclass`` or ``@dataclass(frozen=True)`` so
    that Pylance always sees the native ``@dataclass`` decorator and can infer
    the full ``__init__`` signature without ambiguity.
    """
    for f in cls.__dataclass_fields__.values():
        setattr(cls, f.name, f)
    return cls


@dataclass_transform()
def bindable_dataclass(cls=None, /):
    """
    Convenience decorator for **mutable** domain classes.

    Equivalent to applying ``@dataclass`` and then ``_bind_fields``.  Only
    used for classes that do not need ``frozen=True``; frozen classes
    (``Valuation``, ``Ratios``) use ``@dataclass(frozen=True)`` directly so
    that Pylance can resolve their ``__init__`` signatures without ambiguity.
    """
    def wrapper(cls):
        cls = dataclass(cls)
        return _bind_fields(cls)

    return wrapper if cls is None else wrapper(cls)


@bindable_dataclass
class CompanyProfile:
    ticker:             str
    company_name:       Optional[str]     = None
    sector:             Optional[Sectors] = None
    industry:           Optional[str]     = None
    country:            Optional[str]     = None
    financial_currency: Optional[str]     = None
    trading_currency:   Optional[str]     = None
    exchange:           Optional[str]     = None
    quote_type:         Optional[str]     = None
    website:            Optional[str]     = None


@bindable_dataclass
class Financials:
    """
    Income-statement scalars plus an optional historical companion.

    All numeric fields default to ``0.0``.  A zero value means either "the
    company genuinely had zero" or "data was unavailable" — the
    ``MissingValueRegistry`` disambiguates via the reason tag recorded at
    load time.
    """

    revenue_ttm:          float = 0.0
    ebit_ttm:             float = 0.0
    ebt_ttm:              float = 0.0
    tax_expense_ttm:      float = 0.0
    interest_expense_ttm: float = 0.0
    gross_profit_ttm:     float = 0.0
    operating_income_ttm: float = 0.0
    net_income_ttm:       float = 0.0
    revenue_ttm_prev:     float = 0.0
    net_income_ttm_prev:  float = 0.0
    da_ttm:               float = 0.0

    revenue_growth_rate: float = 0.0
    net_income_growth:   float = 0.0
    gross_margin:        float = 0.0
    operating_margin:    float = 0.0
    net_margin:          float = 0.0
    ebitda_ttm:          float = 0.0

    history: Optional[FinancialsHistory] = None

    def __post_init__(self) -> None:
        self.revenue_growth_rate = (
            mf.calculate_growth(self.revenue_ttm, self.revenue_ttm_prev) or 0.0
        )
        self.net_income_growth = (
            mf.calculate_growth(self.net_income_ttm, self.net_income_ttm_prev) or 0.0
        )
        self.gross_margin     = safe_div(self.gross_profit_ttm,     self.revenue_ttm) or 0.0
        self.operating_margin = safe_div(self.operating_income_ttm, self.revenue_ttm) or 0.0
        self.net_margin       = safe_div(self.net_income_ttm,       self.revenue_ttm) or 0.0
        self.ebitda_ttm       = mf.safe_sum(self.ebit_ttm, self.da_ttm)


@bindable_dataclass
class CashFlow:
    """
    Cash-flow scalars plus an optional historical companion.

    Capex fields are normalised to negative outflows in ``__post_init__``.
    """

    operating_cf_ttm:     float = 0.0
    capex_ttm:            float = 0.0
    oper_cf_last_year:    float = 0.0
    latest_annual_capex:  float = 0.0
    oper_cf_last_quarter: float = 0.0
    latest_quarter_capex: float = 0.0
    dividends_paid_ttm:   float = 0.0
    share_buybacks_ttm:   float = 0.0

    fcf_ttm:          float = 0.0
    last_year_fcf:    float = 0.0
    last_quarter_fcf: float = 0.0

    history: Optional[CashFlowHistory] = None

    def __post_init__(self) -> None:
        self.capex_ttm            = -abs(float(self.capex_ttm))
        self.latest_annual_capex  = -abs(float(self.latest_annual_capex))
        self.latest_quarter_capex = -abs(float(self.latest_quarter_capex))

        self.fcf_ttm          = mf.safe_sum(self.operating_cf_ttm,     self.capex_ttm)
        self.last_year_fcf    = mf.safe_sum(self.oper_cf_last_year,    self.latest_annual_capex)
        self.last_quarter_fcf = mf.safe_sum(self.oper_cf_last_quarter, self.latest_quarter_capex)


@bindable_dataclass
class BalanceSheet:
    """Balance-sheet scalars plus an optional historical companion."""

    total_debt:           float = 0.0
    total_equity:         float = 0.0
    cash_and_equivalents: float = 0.0
    total_assets:         float = 0.0
    total_liabilities:    float = 0.0
    current_assets:       float = 0.0
    current_liabilities:  float = 0.0
    inventory:            float = 0.0

    current_ratio: float = 0.0
    quick_ratio:   float = 0.0

    history: Optional[BalanceSheetHistory] = None

    def __post_init__(self) -> None:
        self.current_ratio = safe_div(self.current_assets, self.current_liabilities) or 0.0
        self.quick_ratio   = mf.quick_ratio(
            self.current_assets, self.inventory, self.current_liabilities
        ) or 0.0


@bindable_dataclass
class MarketData:
    """
    Market and per-share data.

    ``beta`` defaults to ``1.0`` (market beta), not ``0.0``.  A beta of 0
    implies zero market risk which breaks CAPM; 1.0 is the correct neutral
    assumption when the value is unavailable.
    """

    current_price:       float
    shares_outstanding:  int
    market_cap:          float
    beta:                float = 1.0
    eps_ttm:             float = 0.0
    pe_ttm:              float = 0.0
    last_quarter_eps:    float = 0.0
    last_year_eps:       float = 0.0
    low_52_week:         float = 0.0
    high_52_week:        float = 0.0
    fifty_day_avg:       float = 0.0
    two_hundred_day_avg: float = 0.0
    volume:              int   = 0
    avg_volume:          int   = 0

    def __post_init__(self) -> None:
        if self.shares_outstanding is None or self.shares_outstanding <= 0:
            raise ValueError("shares_outstanding must be a positive integer.")


@bindable_dataclass
class HistoricalData:
    price_history: Optional[List[float]] = None
    eps_history:   Optional[List[float]] = None


@_bind_fields
@dataclass(frozen=True)
class Valuation:
    """
    Derived valuation inputs and multiples.

    All numeric fields default to ``0.0`` **except** ``median_historical_pe``
    which stays ``Optional[float]``.  It is used directly as a multiplier in
    the P/E model (``eps × median_pe``); a ``0.0`` multiplier would silently
    produce a zero intrinsic value for every scenario.  ``PEChecker`` treats
    ``None`` here as a CRITICAL blocker before execution reaches that formula.

    Immutability contract: ``frozen=True`` — set once via ``Valuation.build``.
    """

    highest_price:        float           = 0.0
    cost_of_debt:         float           = 0.0
    corporate_tax_rate:   float           = 0.0
    price_to_sales:       float           = 0.0
    price_to_book:        float           = 0.0
    median_historical_pe: Optional[float] = None   # stays Optional — see docstring
    fcf_cagr:             float           = 0.0
    forward_growth_rate:  float           = 0.0
    enterprise_value:     float           = 0.0

    @classmethod
    def build(
        cls,
        *,
        financials:         "Financials",
        balance_sheet:      "BalanceSheet",
        market_data:        "MarketData",
        cash_flow:          "CashFlow",
        historical_data:    Optional["HistoricalData"] = None,
        highest_price:      float = 0.0,
        cost_of_debt:       float = 0.0,
        corporate_tax_rate: float = 0.0,
    ) -> "Valuation":
        """
        Compute and return a fully-populated, immutable ``Valuation``.

        All ``safe_div`` calls are unwrapped to ``float`` with ``or 0.0``
        so the resulting instance has no ``Optional`` numeric fields.
        ``median_historical_pe`` is the sole exception — see class docstring.
        """
        if corporate_tax_rate == 0.0:
            corporate_tax_rate = (
                safe_div(financials.tax_expense_ttm, financials.ebt_ttm) or 0.0
            )

        if cost_of_debt == 0.0 and balance_sheet.total_debt != 0.0:
            cost_of_debt = (
                safe_div(
                    abs(financials.interest_expense_ttm or 0.0),
                    balance_sheet.total_debt,
                ) or 0.0
            )

        ev = mf.enterprise_value(
            market_data.market_cap,
            balance_sheet.total_debt,
            balance_sheet.cash_and_equivalents,
        ) or 0.0

        price_to_sales = safe_div(market_data.market_cap, financials.revenue_ttm) or 0.0
        price_to_book  = mf.price_to_book(
            price=market_data.current_price,
            total_equity=balance_sheet.total_equity,
            shares_outstanding=market_data.shares_outstanding,
        ) or 0.0

        # --- forward_growth_rate: prefer annual net-income CAGR, then EPS CAGR, then TTM growth ---
        forward_growth_rate: float = 0.0
        if (
            financials.history is not None
            and financials.history.net_income_annual is not None
            and len(financials.history.net_income_annual) >= 2
        ):
            forward_growth_rate = mf.cagr_from_series(
                financials.history.net_income_annual
            ) or 0.0

        if forward_growth_rate == 0.0:
            eps_series = historical_data.eps_history if historical_data else None
            if eps_series and len(eps_series) > 1:
                forward_growth_rate = mf.cagr_from_series(eps_series) or 0.0

        if forward_growth_rate == 0.0:
            forward_growth_rate = financials.net_income_growth

        # --- median historical P/E (stays Optional) ---
        median_pe: Optional[float] = None
        if historical_data and historical_data.price_history:
            eps_history = historical_data.eps_history
            if eps_history:
                median_pe = mf.median_pe_ratio(
                    prices=historical_data.price_history,
                    eps_values=eps_history,
                )

        # --- FCF CAGR: prefer annual series, fall back to YoY scalar ---
        fcf_cagr: float = 0.0
        if (
            cash_flow.history is not None
            and cash_flow.history.fcf_annual is not None
            and len(cash_flow.history.fcf_annual) >= 2
        ):
            fcf_cagr = mf.cagr_from_series(cash_flow.history.fcf_annual) or 0.0

        if fcf_cagr == 0.0:
            fcf_now  = cash_flow.fcf_ttm
            fcf_prev = cash_flow.last_year_fcf
            if fcf_now != 0.0 and fcf_prev > 0.0:
                fcf_cagr = (fcf_now / fcf_prev) - 1.0

        return cls(
            highest_price=highest_price,
            cost_of_debt=cost_of_debt,
            corporate_tax_rate=corporate_tax_rate,
            price_to_sales=price_to_sales,
            price_to_book=price_to_book,
            median_historical_pe=median_pe,
            fcf_cagr=fcf_cagr,
            forward_growth_rate=forward_growth_rate,
            enterprise_value=ev,
        )


@_bind_fields
@dataclass(frozen=True)
class Ratios:
    """
    Computed financial ratios.  All fields default to ``0.0``.

    Use ``Ratios.build(...)`` to construct.
    """

    fcf_margin:           float = 0.0
    price_to_fcf:         float = 0.0
    roic:                 float = 0.0
    fcf_yield:            float = 0.0
    debt_to_equity:       float = 0.0
    ebit_margin:          float = 0.0
    peg_ratio:            float = 0.0
    return_on_equity:     float = 0.0
    return_on_assets:     float = 0.0
    price_to_sales:       float = 0.0
    price_to_book:        float = 0.0
    dividend_yield:       float = 0.0
    payout_ratio:         float = 0.0
    ev_ebit:              float = 0.0
    ev_ebitda:            float = 0.0
    book_value_per_share: float = 0.0
    interest_coverage:    float = 0.0

    @classmethod
    def build(
        cls,
        *,
        financials:    "Financials",
        cash_flow:     "CashFlow",
        balance_sheet: "BalanceSheet",
        market_data:   Optional["MarketData"] = None,
        valuation:     Optional["Valuation"]  = None,
    ) -> "Ratios":
        """
        Compute and return a fully-populated, immutable ``Ratios``.

        All ``safe_div`` / formula calls are unwrapped to ``float`` with
        ``or 0.0`` so the resulting instance contains no ``Optional`` fields.
        """
        import logging
        if not all([financials, cash_flow, balance_sheet]):
            logging.getLogger(__name__).warning(
                "Ratios.build: one or more required inputs is None — returning empty Ratios."
            )
            return cls()

        market_cap         = market_data.market_cap         if market_data else 0.0
        pe_ttm             = market_data.pe_ttm              if market_data else 0.0
        shares_outstanding = market_data.shares_outstanding  if market_data else 0
        current_price      = market_data.current_price       if market_data else 0.0
        corporate_tax_rate = valuation.corporate_tax_rate    if valuation   else 0.0
        ev                 = valuation.enterprise_value      if valuation   else 0.0

        fcf_margin = safe_div(cash_flow.fcf_ttm, financials.revenue_ttm) or 0.0

        roic = mf.roic(
            financials.ebit_ttm,
            corporate_tax_rate,
            balance_sheet.total_debt,
            balance_sheet.total_equity,
            balance_sheet.cash_and_equivalents,
        ) or 0.0

        interest_coverage = mf.interest_coverage(
            financials.ebit_ttm, financials.interest_expense_ttm
        ) or 0.0

        ebit_margin  = safe_div(financials.ebit_ttm,   financials.revenue_ttm) or 0.0
        price_to_fcf = safe_div(market_cap, cash_flow.fcf_ttm)                or 0.0
        fcf_yield    = safe_div(cash_flow.fcf_ttm, market_cap)                or 0.0

        peg_ratio = (
            safe_div(pe_ttm, financials.net_income_growth) or 0.0
            if pe_ttm != 0.0 and financials.net_income_growth != 0.0
            else 0.0
        )

        price_to_sales = safe_div(market_cap, financials.revenue_ttm) or 0.0
        price_to_book  = mf.price_to_book(current_price, balance_sheet.total_equity,
                                           shares_outstanding) or 0.0
        ev_ebit   = safe_div(ev, financials.ebit_ttm)   or 0.0
        ev_ebitda = safe_div(ev, financials.ebitda_ttm) or 0.0

        return_on_equity = safe_div(financials.net_income_ttm, balance_sheet.total_equity) or 0.0
        return_on_assets = safe_div(financials.net_income_ttm, balance_sheet.total_assets) or 0.0

        dividend_yield = mf.dividend_yield(
            cash_flow.dividends_paid_ttm, shares_outstanding, current_price
        ) or 0.0
        payout_ratio = mf.payout_ratio(
            cash_flow.dividends_paid_ttm, financials.net_income_ttm
        ) or 0.0
        debt_to_equity = safe_div(balance_sheet.total_debt, balance_sheet.total_equity) or 0.0
        book_value_per_share = safe_div(
            balance_sheet.total_equity,
            float(shares_outstanding) if shares_outstanding else None,
        ) or 0.0

        return cls(
            fcf_margin=fcf_margin,
            price_to_fcf=price_to_fcf,
            roic=roic,
            fcf_yield=fcf_yield,
            debt_to_equity=debt_to_equity,
            ebit_margin=ebit_margin,
            peg_ratio=peg_ratio,
            return_on_equity=return_on_equity,
            return_on_assets=return_on_assets,
            price_to_sales=price_to_sales,
            price_to_book=price_to_book,
            dividend_yield=dividend_yield,
            payout_ratio=payout_ratio,
            ev_ebit=ev_ebit,
            ev_ebitda=ev_ebitda,
            book_value_per_share=book_value_per_share,
            interest_coverage=interest_coverage,
        )


@bindable_dataclass
class StockMetrics:
    """
    Central aggregate for a single ticker.

    ``__post_init__`` delegates all computation to ``_rebuild_derived()``.

    Note on history companions
    --------------------------
    The ``.history`` fields on ``Financials``, ``CashFlow``, and
    ``BalanceSheet`` are populated by ``MetricsLoader._build_*_history()``
    **after** construction by mutating the sub-objects in place.  This is safe
    because those three dataclasses are mutable (not frozen).  ``Valuation``
    and ``Ratios`` are re-built once history is attached.
    """

    profile:         CompanyProfile
    financials:      Financials
    cash_flow:       CashFlow
    balance_sheet:   BalanceSheet
    market_data:     MarketData
    valuation:       Valuation
    historical_data: Optional[HistoricalData] = None
    ratios:          Optional[Ratios]         = None

    def __post_init__(self) -> None:
        self._rebuild_derived()

    def _rebuild_derived(self) -> None:
        """
        (Re-)compute ``Valuation`` and ``Ratios`` from current state.

        Called once from ``__post_init__`` and again by ``MetricsLoader``
        after history companions have been attached.
        """
        self.valuation = Valuation.build(
            financials=self.financials,
            balance_sheet=self.balance_sheet,
            market_data=self.market_data,
            cash_flow=self.cash_flow,
            historical_data=self.historical_data,
            highest_price=self.valuation.highest_price,
            cost_of_debt=self.valuation.cost_of_debt,
            corporate_tax_rate=self.valuation.corporate_tax_rate,
        )
        self.ratios = Ratios.build(
            financials=self.financials,
            cash_flow=self.cash_flow,
            balance_sheet=self.balance_sheet,
            market_data=self.market_data,
            valuation=self.valuation,
        )