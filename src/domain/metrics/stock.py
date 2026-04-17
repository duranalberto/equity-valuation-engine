from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, dataclass_transform

from calculations import metrics_formulas as mf
from calculations import safe_div
from domain.core.missing import Missing, MissingReason

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
    company_name:       str | None = None
    sector:             Sectors | None = None
    industry:           str | None = None
    country:            str | None = None
    financial_currency: str | None = None
    trading_currency:   str | None = None
    exchange:           str | None = None
    quote_type:         str | None = None
    website:            str | None = None


@bindable_dataclass
class Financials:
    """
    Income-statement scalars (unchanged) plus an optional historical companion.
    """

    revenue_ttm:           float | Missing | None
    ebit_ttm:              float | Missing | None
    ebt_ttm:               float | Missing | None
    tax_expense_ttm:       float | Missing | None
    interest_expense_ttm:  float | Missing | None
    gross_profit_ttm:      float | Missing | None
    operating_income_ttm:  float | Missing | None
    net_income_ttm:        float | Missing | None
    revenue_ttm_prev:      float | Missing | None
    net_income_ttm_prev:   float | Missing | None
    da_ttm:                float | Missing | None

    revenue_growth_rate:  float | Missing | None = field(default=None, init=False)
    net_income_growth:    float | Missing | None = field(default=None, init=False)
    gross_margin:         float | Missing | None = field(default=None, init=False)
    operating_margin:     float | Missing | None = field(default=None, init=False)
    net_margin:           float | Missing | None = field(default=None, init=False)
    ebitda_ttm:           float | Missing | None = field(default=None, init=False)

    history: FinancialsHistory | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.history = None
        self.revenue_growth_rate = mf.calculate_growth(
            self.revenue_ttm, self.revenue_ttm_prev
        )
        self.net_income_growth = mf.calculate_growth(
            self.net_income_ttm, self.net_income_ttm_prev
        )
        self.gross_margin = self._derived_ratio(
            safe_div(self.gross_profit_ttm, self.revenue_ttm, "gross_margin"),
            "gross_margin",
        )
        self.operating_margin = self._derived_ratio(
            safe_div(self.operating_income_ttm, self.revenue_ttm),
            "operating_margin",
        )
        self.net_margin = self._derived_ratio(
            safe_div(self.net_income_ttm, self.revenue_ttm),
            "net_margin",
        )
        if self.ebit_ttm is not None and self.da_ttm is not None:
            self.ebitda_ttm = mf.safe_sum(self.ebit_ttm, self.da_ttm)
        else:
            self.ebitda_ttm = Missing(
                MissingReason.INSUFFICIENT_DATA,
                "ebitda_ttm",
                "EBIT or D&A was not available to derive EBITDA.",
            )

    @staticmethod
    def _derived_ratio(value: float | Missing | None, field: str) -> float | Missing:
        if value is None:
            return Missing(
                MissingReason.INSUFFICIENT_DATA,
                field,
                f"{field} could not be computed because one or more inputs were unavailable.",
            )
        return value


@bindable_dataclass
class CashFlow:
    """
    Cash-flow scalars (unchanged) plus an optional historical companion.
    """

    operating_cf_ttm:       float | Missing | None
    capex_ttm:              float | Missing | None
    oper_cf_last_year:      float | Missing | None
    latest_annual_capex:    float | Missing | None
    oper_cf_last_quarter:   float | Missing | None
    latest_quarter_capex:   float | Missing | None
    dividends_paid_ttm:     float | Missing | None
    share_buybacks_ttm:     float | Missing | None

    fcf_ttm:          float | Missing | None = field(default=None, init=False)
    last_year_fcf:    float | Missing | None = field(default=None, init=False)
    last_quarter_fcf: float | Missing | None = field(default=None, init=False)

    history: CashFlowHistory | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.history = None
        if self.capex_ttm is not None:
            self.capex_ttm = -abs(float(self.capex_ttm))
        if self.latest_annual_capex is not None:
            self.latest_annual_capex = -abs(float(self.latest_annual_capex))
        if self.latest_quarter_capex is not None:
            self.latest_quarter_capex = -abs(float(self.latest_quarter_capex))

        if self.operating_cf_ttm is not None and self.capex_ttm is not None:
            self.fcf_ttm = mf.safe_sum(self.operating_cf_ttm, self.capex_ttm)
        elif self.operating_cf_ttm is None or self.capex_ttm is None:
            self.fcf_ttm = Missing(
                MissingReason.INSUFFICIENT_DATA,
                "fcf_ttm",
                "Operating cash flow or capex was not available to derive FCF.",
            )
        if self.oper_cf_last_year is not None and self.latest_annual_capex is not None:
            self.last_year_fcf = mf.safe_sum(
                self.oper_cf_last_year, self.latest_annual_capex
            )
        elif self.oper_cf_last_year is None or self.latest_annual_capex is None:
            self.last_year_fcf = Missing(
                MissingReason.INSUFFICIENT_DATA,
                "last_year_fcf",
                "Operating cash flow or capex was not available to derive last year FCF.",
            )
        if self.oper_cf_last_quarter is not None and self.latest_quarter_capex is not None:
            self.last_quarter_fcf = mf.safe_sum(
                self.oper_cf_last_quarter, self.latest_quarter_capex
            )
        elif self.oper_cf_last_quarter is None or self.latest_quarter_capex is None:
            self.last_quarter_fcf = Missing(
                MissingReason.INSUFFICIENT_DATA,
                "last_quarter_fcf",
                "Operating cash flow or capex was not available to derive last quarter FCF.",
            )


@bindable_dataclass
class BalanceSheet:
    """
    Balance-sheet scalars (unchanged) plus an optional historical companion.
    """

    total_debt:           float | Missing | None
    total_equity:         float | Missing | None
    cash_and_equivalents: float | Missing | None
    total_assets:         float | Missing | None
    total_liabilities:    float | Missing | None
    current_assets:       float | Missing | None
    current_liabilities:  float | Missing | None
    inventory:            float | Missing | None

    current_ratio: float | Missing | None = field(default=None, init=False)
    quick_ratio:   float | Missing | None = field(default=None, init=False)

    history: BalanceSheetHistory | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.history = None
        self.current_ratio = self._derived_ratio(
            safe_div(self.current_assets, self.current_liabilities),
            "current_ratio",
        )
        self.quick_ratio = self._derived_ratio(
            mf.quick_ratio(
                self.current_assets, self.inventory, self.current_liabilities
            ),
            "quick_ratio",
        )

    @staticmethod
    def _derived_ratio(value: float | Missing | None, field: str) -> float | Missing:
        if value is None:
            return Missing(
                MissingReason.INSUFFICIENT_DATA,
                field,
                f"{field} could not be computed because one or more inputs were unavailable.",
            )
        return value



@bindable_dataclass
class MarketData:
    current_price:       float
    shares_outstanding:  int
    market_cap:          float
    beta:                float | Missing | None
    eps_ttm:             float | Missing | None
    pe_ttm:              float | Missing | None
    last_quarter_eps:    float | Missing | None
    last_year_eps:       float | Missing | None
    low_52_week:         float | Missing | None
    high_52_week:        float | Missing | None
    fifty_day_avg:       float | Missing | None
    two_hundred_day_avg: float | Missing | None
    volume:              int | Missing | None
    avg_volume:          int | Missing | None

    def __post_init__(self) -> None:
        if self.shares_outstanding is None or self.shares_outstanding <= 0:
            raise ValueError(
                "shares_outstanding must be a positive integer."
            )



@bindable_dataclass
class HistoricalData:
    price_history: List[float] | None = None
    eps_history:   List[float] | None = None



@dataclass(frozen=True)
class Valuation:
    """
    Derived valuation inputs and multiples.

    Immutability contract
    ---------------------
    ``frozen=True`` means any attempt to set an attribute after construction
    raises ``dataclasses.FrozenInstanceError`` immediately.
    """

    highest_price:       float | Missing | None
    cost_of_debt:        float | Missing | None
    corporate_tax_rate:  float | Missing | None
    price_to_sales:      float | Missing | None
    price_to_book:       float | Missing | None
    median_historical_pe: float | Missing | None
    fcf_cagr:            float | Missing | None
    forward_growth_rate: float | Missing | None
    enterprise_value:    float | Missing | None

    @classmethod
    def build(
        cls,
        *,
        financials:      "Financials",
        balance_sheet:   "BalanceSheet",
        market_data:     "MarketData",
        cash_flow:       "CashFlow",
        historical_data: HistoricalData | None = None,
        highest_price:   float | None = None,
        cost_of_debt:    float | None = None,
        corporate_tax_rate: float | None = None,
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

        price_to_sales = safe_div(market_data.market_cap, financials.revenue_ttm, "price_to_sales")
        price_to_book  = mf.price_to_book(
            price=market_data.current_price,
            total_equity=balance_sheet.total_equity,
            shares_outstanding=market_data.shares_outstanding,
        )

        eps_series = historical_data.eps_history if historical_data else None
        forward_growth_rate: float | None = None

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

        fcf_cagr: float | None = None

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

    fcf_margin:        float | Missing | None = None
    price_to_fcf:      float | Missing | None = None
    roic:              float | Missing | None = None
    fcf_yield:         float | Missing | None = None
    debt_to_equity:    float | Missing | None = None
    ebit_margin:       float | Missing | None = None
    peg_ratio:         float | Missing | None = None
    return_on_equity:  float | Missing | None = None
    return_on_assets:  float | Missing | None = None
    price_to_sales:    float | Missing | None = None
    price_to_book:     float | Missing | None = None
    dividend_yield:    float | Missing | None = None
    payout_ratio:      float | Missing | None = None
    ev_ebit:           float | Missing | None = None
    ev_ebitda:         float | Missing | None = None
    book_value_per_share: float | Missing | None = None
    interest_coverage: float | Missing | None = None

    @classmethod
    def build(
        cls,
        *,
        financials:   "Financials",
        cash_flow:    "CashFlow",
        balance_sheet: "BalanceSheet",
        market_data:  MarketData | None = None,
        valuation:    Valuation | None = None,
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

        fcf_margin = safe_div(cash_flow.fcf_ttm, financials.revenue_ttm, "fcf_margin")
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
        price_to_fcf = safe_div(market_cap, cash_flow.fcf_ttm, "price_to_fcf")
        fcf_yield = safe_div(cash_flow.fcf_ttm, market_cap, "fcf_yield")
        peg_ratio = safe_div(pe_ttm, financials.net_income_growth, "peg_ratio")
        price_to_sales = safe_div(market_cap, financials.revenue_ttm, "price_to_sales")
        price_to_book = mf.price_to_book(
            current_price, balance_sheet.total_equity, shares_outstanding
        )
        ev_ebit = safe_div(ev, financials.ebit_ttm, "ev_ebit")
        ev_ebitda = safe_div(ev, financials.ebitda_ttm, "ev_ebitda")
        return_on_equity = safe_div(financials.net_income_ttm, balance_sheet.total_equity, "return_on_equity")
        return_on_assets = safe_div(financials.net_income_ttm, balance_sheet.total_assets, "return_on_assets")
        dividend_yield = mf.dividend_yield(
            cash_flow.dividends_paid_ttm, shares_outstanding, current_price
        )
        payout_ratio = mf.payout_ratio(
            cash_flow.dividends_paid_ttm, financials.net_income_ttm
        )
        debt_to_equity = safe_div(balance_sheet.total_debt, balance_sheet.total_equity, "debt_to_equity")
        book_value_per_share = safe_div(
            balance_sheet.total_equity,
            float(shares_outstanding) if shares_outstanding is not None else None,
            "book_value_per_share",
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
    historical_data: HistoricalData | None = None
    ratios:          Ratios | None = None

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
