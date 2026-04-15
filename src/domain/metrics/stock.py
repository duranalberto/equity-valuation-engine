from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, dataclass_transform

from calculations import metrics_formulas as mf
from calculations import safe_div

from ..core.enums import Sectors
from .history import BalanceSheetHistory, CashFlowHistory, FinancialsHistory


@dataclass_transform()
def bindable_dataclass(cls=None, /, **dataclass_kwargs):
    """
    Wrapper around @dataclass that also binds dataclass fields as class-level
    attributes, enabling mapper key access via e.g. CompanyProfile.ticker.

    NOTE: This shadows the class attribute with a ``dataclasses.Field`` object.
    IDEs and type-checkers will see the annotated type (e.g. ``str``) rather
    than ``Field``.  When adding new mapper-key usage, verify with a runtime
    test rather than relying solely on static analysis.

    ``frozen`` dataclasses are fully supported — ``bindable_dataclass`` passes
    all keyword arguments through to ``@dataclass``.
    """
    def wrapper(cls):
        cls = dataclass(cls, **dataclass_kwargs)
        for f in cls.__dataclass_fields__.values():
            setattr(cls, f.name, f)
        return cls

    return wrapper if cls is None else wrapper(cls)


def bind_dataclass_fields(cls):
    for f in cls.__dataclass_fields__.values():
        setattr(cls, f.name, f)
    return cls


@bindable_dataclass
class CompanyProfile:
    ticker:             str
    company_name:       Optional[str]     = None
    sector:             Optional[Sectors]  = None
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
    Income-statement scalars (unchanged) plus an optional historical companion.
    """

    revenue_ttm:           Optional[float]
    ebit_ttm:              Optional[float]
    ebt_ttm:               Optional[float]
    tax_expense_ttm:       Optional[float]
    interest_expense_ttm:  Optional[float]
    gross_profit_ttm:      Optional[float]
    operating_income_ttm:  Optional[float]
    net_income_ttm:        Optional[float]
    revenue_ttm_prev:      Optional[float]
    net_income_ttm_prev:   Optional[float]
    da_ttm:                Optional[float]

    revenue_growth_rate:  Optional[float] = None
    net_income_growth:    Optional[float] = None
    gross_margin:         Optional[float] = None
    operating_margin:     Optional[float] = None
    net_margin:           Optional[float] = None
    ebitda_ttm:           Optional[float] = None

    history: Optional[FinancialsHistory] = None

    def __post_init__(self) -> None:
        self.revenue_growth_rate = mf.calculate_growth(
            self.revenue_ttm, self.revenue_ttm_prev
        )
        self.net_income_growth = mf.calculate_growth(
            self.net_income_ttm, self.net_income_ttm_prev
        )
        self.gross_margin    = safe_div(self.gross_profit_ttm, self.revenue_ttm)
        self.operating_margin = safe_div(self.operating_income_ttm, self.revenue_ttm)
        self.net_margin       = safe_div(self.net_income_ttm, self.revenue_ttm)
        if self.ebit_ttm is not None and self.da_ttm is not None:
            self.ebitda_ttm = mf.safe_sum(self.ebit_ttm, self.da_ttm)
        else:
            self.ebitda_ttm = None


@bindable_dataclass
class CashFlow:
    """
    Cash-flow scalars (unchanged) plus an optional historical companion.
    """

    operating_cf_ttm:       Optional[float]
    capex_ttm:              Optional[float]
    oper_cf_last_year:      Optional[float]
    latest_annual_capex:    Optional[float]
    oper_cf_last_quarter:   Optional[float]
    latest_quarter_capex:   Optional[float]
    dividends_paid_ttm:     Optional[float]
    share_buybacks_ttm:     Optional[float]

    fcf_ttm:          Optional[float] = None
    last_year_fcf:    Optional[float] = None
    last_quarter_fcf: Optional[float] = None

    history: Optional[CashFlowHistory] = None

    def __post_init__(self) -> None:
        if self.capex_ttm is not None:
            self.capex_ttm = -abs(float(self.capex_ttm))
        if self.latest_annual_capex is not None:
            self.latest_annual_capex = -abs(float(self.latest_annual_capex))
        if self.latest_quarter_capex is not None:
            self.latest_quarter_capex = -abs(float(self.latest_quarter_capex))

        if self.operating_cf_ttm is not None and self.capex_ttm is not None:
            self.fcf_ttm = mf.safe_sum(self.operating_cf_ttm, self.capex_ttm)
        if self.oper_cf_last_year is not None and self.latest_annual_capex is not None:
            self.last_year_fcf = mf.safe_sum(
                self.oper_cf_last_year, self.latest_annual_capex
            )
        if self.oper_cf_last_quarter is not None and self.latest_quarter_capex is not None:
            self.last_quarter_fcf = mf.safe_sum(
                self.oper_cf_last_quarter, self.latest_quarter_capex
            )


@bindable_dataclass
class BalanceSheet:
    """
    Balance-sheet scalars (unchanged) plus an optional historical companion.
    """

    total_debt:           Optional[float]
    total_equity:         Optional[float]
    cash_and_equivalents: Optional[float]
    total_assets:         Optional[float]
    total_liabilities:    Optional[float]
    current_assets:       Optional[float]
    current_liabilities:  Optional[float]
    inventory:            Optional[float]

    current_ratio: Optional[float] = None
    quick_ratio:   Optional[float] = None

    history: Optional[BalanceSheetHistory] = None

    def __post_init__(self) -> None:
        self.current_ratio = safe_div(self.current_assets, self.current_liabilities)
        self.quick_ratio   = mf.quick_ratio(
            self.current_assets, self.inventory, self.current_liabilities
        )



@bindable_dataclass
class MarketData:
    current_price:       float
    shares_outstanding:  int
    market_cap:          float
    beta:                Optional[float]
    eps_ttm:             Optional[float]
    pe_ttm:              Optional[float]
    last_quarter_eps:    Optional[float]
    last_year_eps:       Optional[float]
    low_52_week:         Optional[float]
    high_52_week:        Optional[float]
    fifty_day_avg:       Optional[float]
    two_hundred_day_avg: Optional[float]
    volume:              Optional[int]
    avg_volume:          Optional[int]

    def __post_init__(self) -> None:
        if self.shares_outstanding is None or self.shares_outstanding <= 0:
            raise ValueError(
                "shares_outstanding must be a positive integer."
            )



@bindable_dataclass
class HistoricalData:
    price_history: Optional[List[float]] = None
    eps_history:   Optional[List[float]] = None



@dataclass(frozen=True)
class Valuation:
    """
    Derived valuation inputs and multiples.

    Immutability contract
    ---------------------
    ``frozen=True`` means any attempt to set an attribute after construction
    raises ``dataclasses.FrozenInstanceError`` immediately.
    """

    highest_price:       Optional[float]
    cost_of_debt:        Optional[float]
    corporate_tax_rate:  Optional[float]
    price_to_sales:      Optional[float]
    price_to_book:       Optional[float]
    median_historical_pe: Optional[float]
    fcf_cagr:            Optional[float]
    forward_growth_rate: Optional[float]
    enterprise_value:    Optional[float]

    @classmethod
    def build(
        cls,
        *,
        financials:      "Financials",
        balance_sheet:   "BalanceSheet",
        market_data:     "MarketData",
        cash_flow:       "CashFlow",
        historical_data: Optional["HistoricalData"] = None,
        highest_price:   Optional[float] = None,
        cost_of_debt:    Optional[float] = None,
        corporate_tax_rate: Optional[float] = None,
    ) -> "Valuation":
        """
        Compute and return a fully populated, immutable ``Valuation``.

        cost_of_debt and corporate_tax_rate
        ------------------------------------
        Derived from statement data when not supplied:

            corporate_tax_rate = tax_expense_ttm / ebt_ttm
            cost_of_debt       = |interest_expense_ttm| / total_debt
        """
        if corporate_tax_rate is None:
            corporate_tax_rate = safe_div(
                financials.tax_expense_ttm, financials.ebt_ttm
            )

        if cost_of_debt is None and balance_sheet.total_debt:
            cost_of_debt = safe_div(
                abs(financials.interest_expense_ttm or 0.0),
                balance_sheet.total_debt,
            )

        ev = mf.enterprise_value(
            market_data.market_cap,
            balance_sheet.total_debt,
            balance_sheet.cash_and_equivalents,
        )

        price_to_sales = safe_div(market_data.market_cap, financials.revenue_ttm)
        price_to_book  = mf.price_to_book(
            price=market_data.current_price,
            total_equity=balance_sheet.total_equity,
            shares_outstanding=market_data.shares_outstanding,
        )

        eps_series = historical_data.eps_history if historical_data else None
        forward_growth_rate: Optional[float] = None

        if (
            financials.history is not None
            and financials.history.net_income_annual is not None
            and len(financials.history.net_income_annual) >= 2
        ):
            forward_growth_rate = mf.cagr_from_series(
                financials.history.net_income_annual
            )

        if forward_growth_rate is None and eps_series and len(eps_series) > 1:
            forward_growth_rate = mf.cagr_from_series(eps_series)

        if forward_growth_rate is None:
            forward_growth_rate = financials.net_income_growth

        median_pe = None
        if historical_data and historical_data.price_history:
            eps_history = historical_data.eps_history
            if eps_history:
                median_pe = mf.median_pe_ratio(
                    prices=historical_data.price_history,
                    eps_values=eps_history,
                )

        fcf_cagr: Optional[float] = None

        if (
            cash_flow.history is not None
            and cash_flow.history.fcf_annual is not None
            and len(cash_flow.history.fcf_annual) >= 2
        ):
            fcf_cagr = mf.cagr_from_series(cash_flow.history.fcf_annual)

        if fcf_cagr is None:
            fcf_now  = cash_flow.fcf_ttm
            fcf_prev = cash_flow.last_year_fcf
            if fcf_now is not None and fcf_prev is not None and fcf_prev > 0:
                fcf_cagr = (fcf_now / fcf_prev) - 1

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


@dataclass(frozen=True)
class Ratios:
    """
    Computed financial ratios.

    All fields default to ``None`` — a ``None`` ratio means "could not be
    calculated" (missing input), distinguishable from ``0.0`` (computed zero).

    Use ``Ratios.build(...)`` to construct.
    """

    fcf_margin:        Optional[float] = None
    price_to_fcf:      Optional[float] = None
    roic:              Optional[float] = None
    fcf_yield:         Optional[float] = None
    debt_to_equity:    Optional[float] = None
    ebit_margin:       Optional[float] = None
    peg_ratio:         Optional[float] = None
    return_on_equity:  Optional[float] = None
    return_on_assets:  Optional[float] = None
    price_to_sales:    Optional[float] = None
    price_to_book:     Optional[float] = None
    dividend_yield:    Optional[float] = None
    payout_ratio:      Optional[float] = None
    ev_ebit:           Optional[float] = None
    ev_ebitda:         Optional[float] = None
    book_value_per_share: Optional[float] = None
    interest_coverage: Optional[float] = None

    @classmethod
    def build(
        cls,
        *,
        financials:   "Financials",
        cash_flow:    "CashFlow",
        balance_sheet: "BalanceSheet",
        market_data:  Optional["MarketData"] = None,
        valuation:    Optional["Valuation"]  = None,
    ) -> "Ratios":
        """
        Compute and return a fully populated, immutable ``Ratios``.

        Returns an all-None ``Ratios`` instance (rather than raising) when
        required inputs are absent, and logs a warning so the missing data
        is visible in logs.
        """
        if not all([financials, cash_flow, balance_sheet]):
            import logging
            logging.getLogger(__name__).warning(
                "Ratios.build: one or more required inputs (financials, "
                "cash_flow, balance_sheet) is None — returning empty Ratios."
            )
            return cls()

        market_cap         = market_data.market_cap         if market_data else None
        pe_ttm             = market_data.pe_ttm              if market_data else None
        shares_outstanding = market_data.shares_outstanding  if market_data else None
        current_price      = market_data.current_price       if market_data else None
        corporate_tax_rate = valuation.corporate_tax_rate    if valuation   else None
        ev                 = valuation.enterprise_value      if valuation   else None

        fcf_margin = (
            safe_div(cash_flow.fcf_ttm, financials.revenue_ttm)
            if cash_flow.fcf_ttm is not None
            else None
        )
        roic = mf.roic(
            financials.ebit_ttm,
            corporate_tax_rate,
            balance_sheet.total_debt,
            balance_sheet.total_equity,
            balance_sheet.cash_and_equivalents,
        )
        interest_coverage = (
            mf.interest_coverage(financials.ebit_ttm, financials.interest_expense_ttm)
            if financials.ebit_ttm is not None
            else None
        )
        ebit_margin = (
            safe_div(financials.ebit_ttm, financials.revenue_ttm)
            if financials.ebit_ttm is not None
            else None
        )
        price_to_fcf = (
            safe_div(market_cap, cash_flow.fcf_ttm) if cash_flow.fcf_ttm else None
        )
        fcf_yield = (
            safe_div(cash_flow.fcf_ttm, market_cap)
            if cash_flow.fcf_ttm is not None
            else None
        )
        peg_ratio = (
            safe_div(pe_ttm, financials.net_income_growth)
            if pe_ttm is not None and financials.net_income_growth
            else None
        )
        price_to_sales = (
            safe_div(market_cap, financials.revenue_ttm)
            if financials.revenue_ttm
            else None
        )
        price_to_book = mf.price_to_book(
            current_price, balance_sheet.total_equity, shares_outstanding
        )
        ev_ebit = (
            safe_div(ev, financials.ebit_ttm)
            if ev is not None and financials.ebit_ttm
            else None
        )
        ev_ebitda = (
            safe_div(ev, financials.ebitda_ttm)
            if ev is not None and financials.ebitda_ttm
            else None
        )
        return_on_equity = (
            safe_div(financials.net_income_ttm, balance_sheet.total_equity)
            if balance_sheet.total_equity
            else None
        )
        return_on_assets = (
            safe_div(financials.net_income_ttm, balance_sheet.total_assets)
            if balance_sheet.total_assets
            else None
        )
        dividend_yield = mf.dividend_yield(
            cash_flow.dividends_paid_ttm, shares_outstanding, current_price
        )
        payout_ratio = mf.payout_ratio(
            cash_flow.dividends_paid_ttm, financials.net_income_ttm
        )
        debt_to_equity = (
            safe_div(balance_sheet.total_debt, balance_sheet.total_equity)
            if balance_sheet.total_equity
            else None
        )
        book_value_per_share = safe_div(
            balance_sheet.total_equity,
            float(shares_outstanding) if shares_outstanding is not None else None,
        )

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


bind_dataclass_fields(Valuation)
bind_dataclass_fields(Ratios)


@bindable_dataclass
class StockMetrics:
    """
    The central aggregate for a single ticker.

    ``__post_init__`` delegates all computation to the two immutable
    factory methods.

    Note on history companions
    --------------------------
    The ``.history`` fields on ``Financials``, ``CashFlow``, and
    ``BalanceSheet`` are populated by ``MetricsLoader._build_*_history()``
    **after** ``StockMetrics`` is constructed, by mutating the sub-objects
    in place.  This is safe because those three dataclasses are mutable
    (not frozen).  ``Valuation`` and ``Ratios`` are re-built once history
    is attached.
    """

    profile:        CompanyProfile
    financials:     Financials
    cash_flow:      CashFlow
    balance_sheet:  BalanceSheet
    market_data:    MarketData
    valuation:      Valuation
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
