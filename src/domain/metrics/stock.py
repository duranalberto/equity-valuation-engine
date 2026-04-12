from typing import Optional, List
from dataclasses import dataclass, field
from calculations import safe_div, metrics_formulas as mf
from ..core.enums import Sectors


def bindable_dataclass(cls=None, /, **dataclass_kwargs):
    """
    Wrapper around @dataclass that also binds dataclass fields as class-level
    attributes, enabling mapper key access via e.g. CompanyProfile.ticker.

    NOTE: This shadows the class attribute with a ``dataclasses.Field`` object.
    IDEs and type-checkers will see the annotated type (e.g. ``str``) rather
    than ``Field``.  When adding new mapper-key usage, verify with a runtime
    test rather than relying solely on static analysis.
    """
    def wrapper(cls):
        cls = dataclass(cls, **dataclass_kwargs)
        for f in cls.__dataclass_fields__.values():
            setattr(cls, f.name, f)
        return cls

    return wrapper if cls is None else wrapper(cls)


@bindable_dataclass
class CompanyProfile:
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[Sectors] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    financial_currency: Optional[str] = None
    trading_currency: Optional[str] = None
    exchange: Optional[str] = None
    quote_type: Optional[str] = None
    website: Optional[str] = None


@bindable_dataclass
class Financials:
    revenue_ttm: Optional[float]
    ebit_ttm: Optional[float]
    ebt_ttm: Optional[float]
    tax_expense_ttm: Optional[float]
    interest_expense_ttm: Optional[float]
    gross_profit_ttm: Optional[float]
    operating_income_ttm: Optional[float]
    net_income_ttm: Optional[float]
    revenue_ttm_prev: Optional[float]
    net_income_ttm_prev: Optional[float]
    da_ttm: Optional[float]
    # Computed in __post_init__ — all Optional so null-checks are meaningful.
    revenue_growth_rate: Optional[float] = None
    net_income_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    ebitda_ttm: Optional[float] = None

    def __post_init__(self) -> None:
        # calculate_growth and safe_div now return Optional[float]; the
        # results are stored as-is so downstream null-checks are reliable.
        self.revenue_growth_rate = mf.calculate_growth(
            self.revenue_ttm, self.revenue_ttm_prev
        )
        self.net_income_growth = mf.calculate_growth(
            self.net_income_ttm, self.net_income_ttm_prev
        )
        self.gross_margin = safe_div(self.gross_profit_ttm, self.revenue_ttm)
        self.operating_margin = safe_div(self.operating_income_ttm, self.revenue_ttm)
        self.net_margin = safe_div(self.net_income_ttm, self.revenue_ttm)
        # ebitda only when both components are present
        if self.ebit_ttm is not None and self.da_ttm is not None:
            self.ebitda_ttm = mf.safe_sum(self.ebit_ttm, self.da_ttm)
        else:
            self.ebitda_ttm = None


@bindable_dataclass
class CashFlow:
    operating_cf_ttm: Optional[float]
    capex_ttm: Optional[float]
    oper_cf_last_year: Optional[float]
    latest_annual_capex: Optional[float]
    oper_cf_last_quarter: Optional[float]
    latest_quarter_capex: Optional[float]
    dividends_paid_ttm: Optional[float]
    share_buybacks_ttm: Optional[float]
    fcf_ttm: Optional[float] = None
    last_year_fcf: Optional[float] = None
    last_quarter_fcf: Optional[float] = None

    def __post_init__(self) -> None:
        if self.operating_cf_ttm is not None and self.capex_ttm is not None:
            self.fcf_ttm = mf.safe_sum(self.operating_cf_ttm, self.capex_ttm)
        if self.oper_cf_last_year is not None and self.latest_annual_capex is not None:
            self.last_year_fcf = mf.safe_sum(self.oper_cf_last_year, self.latest_annual_capex)
        if self.oper_cf_last_quarter is not None and self.latest_quarter_capex is not None:
            self.last_quarter_fcf = mf.safe_sum(
                self.oper_cf_last_quarter, self.latest_quarter_capex
            )


@bindable_dataclass
class BalanceSheet:
    total_debt: Optional[float]
    total_equity: Optional[float]
    cash_and_equivalents: Optional[float]
    total_assets: Optional[float]
    total_liabilities: Optional[float]
    current_assets: Optional[float]
    current_liabilities: Optional[float]
    inventory: Optional[float]
    # Computed in __post_init__ — Optional so null-checks work correctly.
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    def __post_init__(self) -> None:
        # safe_div now returns None when current_liabilities is None/0 —
        # previously this silently produced 0.0, making null checks useless.
        self.current_ratio = safe_div(self.current_assets, self.current_liabilities)
        self.quick_ratio = mf.quick_ratio(
            self.current_assets, self.inventory, self.current_liabilities
        )


@bindable_dataclass
class MarketData:
    current_price: float
    shares_outstanding: int
    market_cap: float
    beta: float
    eps_ttm: float
    pe_ttm: float
    last_quarter_eps: float
    last_year_eps: float
    low_52_week: float
    high_52_week: float
    fifty_day_avg: float
    two_hundred_day_avg: float
    volume: int
    avg_volume: int


@bindable_dataclass
class HistoricalData:
    price_history: Optional[List[float]] = None
    eps_history: Optional[List[float]] = None


@bindable_dataclass
class Valuation:
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    cost_of_debt: Optional[float] = None
    corporate_tax_rate: Optional[float] = None
    highest_price: Optional[float] = None
    median_historical_pe: Optional[float] = None
    fcf_cagr: Optional[float] = None
    forward_growth_rate: Optional[float] = None
    enterprise_value: Optional[float] = None

    def calculate_metrics(
        self,
        financials: "Financials",
        balance_sheet: "BalanceSheet",
        market_data: "MarketData",
        cash_flow: "CashFlow",
        historical_data: Optional["HistoricalData"] = None,
    ) -> None:
        if market_data and balance_sheet:
            self.enterprise_value = mf.enterprise_value(
                market_data.market_cap,
                balance_sheet.total_debt,
                balance_sheet.cash_and_equivalents,
            )

        if market_data and financials:
            self.price_to_sales = safe_div(market_data.market_cap, financials.revenue_ttm)
            self.price_to_book = mf.price_to_book(
                price=market_data.current_price,
                total_equity=balance_sheet.total_equity if balance_sheet else None,
                shares_outstanding=market_data.shares_outstanding,
            )

        eps_series = historical_data.eps_history if historical_data else None
        if eps_series and len(eps_series) > 1:
            self.forward_growth_rate = mf.cagr_from_series(eps_series)
        elif financials:
            self.forward_growth_rate = financials.net_income_growth

        if historical_data and historical_data.price_history:
            self.median_historical_pe = mf.median_pe_ratio(
                prices=historical_data.price_history,
                eps_values=historical_data.eps_history,
            )

        if cash_flow:
            fcf_now = cash_flow.fcf_ttm
            fcf_prev = cash_flow.last_year_fcf
            if fcf_now is not None and fcf_prev is not None and fcf_prev > 0:
                self.fcf_cagr = (fcf_now / fcf_prev) - 1


@bindable_dataclass
class Ratios:
    fcf_margin: Optional[float] = None
    price_to_fcf: Optional[float] = None
    roic: Optional[float] = None
    fcf_yield: Optional[float] = None
    debt_to_equity: Optional[float] = None
    ebit_margin: Optional[float] = None
    peg_ratio: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    dividend_yield: Optional[float] = None
    payout_ratio: Optional[float] = None
    ev_ebit: Optional[float] = None
    ev_ebitda: Optional[float] = None
    book_value_per_share: Optional[float] = None
    interest_coverage: Optional[float] = None

    def calculate_metrics(
        self,
        financials: Optional["Financials"],
        cash_flow: Optional["CashFlow"],
        balance_sheet: Optional["BalanceSheet"],
        market_data: Optional["MarketData"] = None,
        valuation: Optional["Valuation"] = None,
    ) -> None:
        if not all([financials, cash_flow, balance_sheet, valuation]):
            return

        _f, _cf, _b, _v = financials, cash_flow, balance_sheet, valuation

        market_cap = market_data.market_cap if market_data else None
        pe_ttm = market_data.pe_ttm if market_data else None
        shares_outstanding = market_data.shares_outstanding if market_data else None
        current_price = market_data.current_price if market_data else None
        corporate_tax_rate = valuation.corporate_tax_rate if valuation else None

        # All safe_div calls now return Optional[float] — None propagates
        # correctly instead of silently collapsing to 0.0.
        self.fcf_margin = (
            safe_div(_cf.fcf_ttm, _f.revenue_ttm) if _cf.fcf_ttm is not None else None
        )
        self.roic = mf.roic(
            _f.ebit_ttm,
            corporate_tax_rate,
            _b.total_debt,
            _b.total_equity,
            _b.cash_and_equivalents,
        )
        self.interest_coverage = (
            mf.interest_coverage(_f.ebit_ttm, _f.interest_expense_ttm)
            if _f.ebit_ttm is not None
            else None
        )
        self.ebit_margin = (
            safe_div(_f.ebit_ttm, _f.revenue_ttm) if _f.ebit_ttm is not None else None
        )
        self.price_to_fcf = safe_div(market_cap, _cf.fcf_ttm) if _cf.fcf_ttm else None
        self.fcf_yield = (
            safe_div(_cf.fcf_ttm, market_cap) if _cf.fcf_ttm is not None else None
        )
        self.peg_ratio = (
            safe_div(pe_ttm, _f.net_income_growth)
            if pe_ttm is not None and _f.net_income_growth
            else None
        )
        self.price_to_sales = safe_div(market_cap, _f.revenue_ttm) if _f.revenue_ttm else None
        self.price_to_book = mf.price_to_book(current_price, _b.total_equity, shares_outstanding)

        if _v.enterprise_value is not None:
            self.ev_ebit = safe_div(_v.enterprise_value, _f.ebit_ttm) if _f.ebit_ttm else None
            self.ev_ebitda = (
                safe_div(_v.enterprise_value, _f.ebitda_ttm) if _f.ebitda_ttm else None
            )

        self.return_on_equity = (
            safe_div(_f.net_income_ttm, _b.total_equity) if _b.total_equity else None
        )
        self.return_on_assets = (
            safe_div(_f.net_income_ttm, _b.total_assets) if _b.total_assets else None
        )
        self.dividend_yield = mf.dividend_yield(
            _cf.dividends_paid_ttm, shares_outstanding, current_price
        )
        self.payout_ratio = mf.payout_ratio(_cf.dividends_paid_ttm, _f.net_income_ttm)
        self.debt_to_equity = (
            safe_div(_b.total_debt, _b.total_equity) if _b.total_equity else None
        )
        self.book_value_per_share = safe_div(
            _b.total_equity,
            float(shares_outstanding) if shares_outstanding is not None else None,
        )


@bindable_dataclass
class StockMetrics:
    profile: CompanyProfile
    financials: Financials
    cash_flow: CashFlow
    balance_sheet: BalanceSheet
    market_data: MarketData
    valuation: Valuation
    historical_data: Optional[HistoricalData] = None
    ratios: Optional[Ratios] = None

    def __post_init__(self) -> None:
        # Phase order is load-bearing:
        # 1. derive valuation inputs (cost_of_debt, corporate_tax_rate)
        # 2. populate Valuation derived fields (enterprise_value, price_to_*)
        # 3. populate Ratios (depends on valuation.enterprise_value)
        self._compute_derived_valuation_inputs()
        self.valuation.calculate_metrics(
            financials=self.financials,
            balance_sheet=self.balance_sheet,
            market_data=self.market_data,
            historical_data=self.historical_data,
            cash_flow=self.cash_flow,
        )
        self._compute_ratios()

    def _compute_derived_valuation_inputs(self) -> None:
        _f, _b = self.financials, self.balance_sheet
        if self.valuation:
            # safe_div returns None when ebt_ttm is None/zero — previously
            # this silently set corporate_tax_rate to 0.0.
            self.valuation.corporate_tax_rate = safe_div(
                _f.tax_expense_ttm, _f.ebt_ttm
            )
        if self.market_data and _b.total_debt:
            self.valuation.cost_of_debt = safe_div(
                abs(_f.interest_expense_ttm or 0.0), _b.total_debt
            )

    def _compute_ratios(self) -> None:
        ratios = Ratios()
        ratios.calculate_metrics(
            financials=self.financials,
            cash_flow=self.cash_flow,
            balance_sheet=self.balance_sheet,
            market_data=self.market_data,
            valuation=self.valuation,
        )
        self.ratios = ratios