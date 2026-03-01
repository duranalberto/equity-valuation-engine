from typing import Optional, List
from dataclasses import dataclass
from calculations import safe_div, metrics_formulas as mf
from ..core.enums import Sectors

def bindable_dataclass(cls=None, /, **dataclass_kwargs):
    """
    Wrapper around @dataclass that:
      1. Applies @dataclass normally
      2. Automatically binds dataclass fields as class-level attributes.
    """

    def wrapper(cls):
        cls = dataclass(cls, **dataclass_kwargs)

        for field in cls.__dataclass_fields__.values():
            setattr(cls, field.name, field)

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
    revenue_ttm: float
    ebit_ttm: float
    ebt_ttm: float
    tax_expense_ttm: float
    interest_expense_ttm: float
    gross_profit_ttm: float
    operating_income_ttm: float
    net_income_ttm: float
    revenue_ttm_prev: float
    net_income_ttm_prev: float
    da_ttm: float
    revenue_growth_rate: Optional[float] = None
    net_income_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    ebitda_ttm: Optional[float] = None
    
    def __post_init__(self) -> None:
        self.revenue_growth_rate = mf.calculate_growth(self.revenue_ttm, self.revenue_ttm_prev)
        self.net_income_growth = mf.calculate_growth(self.net_income_ttm, self.net_income_ttm_prev)
        self.gross_margin = safe_div(self.gross_profit_ttm, self.revenue_ttm)
        self.operating_margin = safe_div(self.operating_income_ttm, self.revenue_ttm)
        self.net_margin = safe_div(self.net_income_ttm, self.revenue_ttm)
        self.ebitda_ttm = mf.safe_sum(self.ebit_ttm, self.da_ttm)


@bindable_dataclass
class CashFlow:
    operating_cf_ttm: float
    capex_ttm: float
    oper_cf_last_year: float
    latest_annual_capex: float
    oper_cf_last_quarter: float
    latest_quarter_capex: float
    dividends_paid_ttm: float
    share_buybacks_ttm: float
    fcf_ttm: Optional[float] = None
    last_year_fcf: Optional[float] = None
    last_quarter_fcf: Optional[float] = None
    
    def __post_init__(self) -> None:
        self.fcf_ttm = mf.safe_sum(self.operating_cf_ttm, self.capex_ttm)
        self.last_year_fcf = mf.safe_sum(self.oper_cf_last_year, self.latest_annual_capex)
        self.last_quarter_fcf = mf.safe_sum(self.oper_cf_last_quarter, self.latest_quarter_capex)


@bindable_dataclass
class BalanceSheet:
    total_debt: float
    total_equity: float
    cash_and_equivalents: float
    total_assets: float
    total_liabilities: float
    current_assets: float
    current_liabilities: float
    inventory: float
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    
    def __post_init__(self) -> None:
        self.current_ratio = safe_div(self.current_assets, self.current_liabilities)
        self.quick_ratio = mf.quick_ratio(self.current_assets, self.inventory, self.current_liabilities)


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
        financials: Financials, 
        balance_sheet: BalanceSheet, 
        market_data: MarketData,
        cash_flow: CashFlow,
        historical_data: Optional[HistoricalData] = None
    ):
        self.enterprise_value = mf.enterprise_value(
            market_data.market_cap, balance_sheet.total_debt, balance_sheet.cash_and_equivalents
        )
        
        if market_data and financials:
            self.price_to_sales = safe_div(
                market_data.market_cap,
                financials.revenue_ttm
            )
            self.price_to_book = mf.price_to_book(
                price=market_data.current_price,
                total_equity=balance_sheet.total_equity if balance_sheet else None,
                shares_outstanding=market_data.shares_outstanding
            )
        
        eps_series = historical_data.eps_history if historical_data else None
        if eps_series and len(eps_series) > 1:
            self.forward_growth_rate = mf.cagr_from_series(eps_series) or 0.0
        else:
            self.forward_growth_rate = financials.net_income_growth or 0.0
        if historical_data and historical_data.price_history:
            self.median_historical_pe = mf.median_pe_ratio(
                prices=historical_data.price_history,
                eps_values=historical_data.eps_history,
            )
        
        fcf_now = cash_flow.fcf_ttm
        fcf_prev = cash_flow.last_year_fcf

        if fcf_now and fcf_prev and fcf_prev > 0:
            self.fcf_cagr = (fcf_now / fcf_prev) - 1


@bindable_dataclass
class Ratios:
    fcf_margin: float = 0.0
    price_to_fcf: float = 0.0
    roic: float = 0.0
    fcf_yield: float = 0.0
    debt_to_equity: float = 0.0
    ebit_margin: float = 0.0
    peg_ratio: float = 0.0
    return_on_equity: float = 0.0
    return_on_assets: float = 0.0
    price_to_sales: float = 0.0
    price_to_book: float = 0.0
    dividend_yield: float = 0.0
    payout_ratio: float = 0.0
    ev_ebit: float = 0.0
    ev_ebitda: float = 0.0
    book_value_per_share: float = 0.0
    interest_coverage: float = 0.0
    
    def calculate_metrics(
        self,
        financials: Optional[Financials],
        cash_flow: Optional[CashFlow],
        balance_sheet: Optional[BalanceSheet],
        market_data: Optional[MarketData] = None,
        valuation: Optional[Valuation] = None,
    ) -> None:

        if not all([financials, cash_flow, balance_sheet, valuation]):
            return

        _f, _cf, _b, _v = financials, cash_flow, balance_sheet, valuation

        market_cap = market_data.market_cap if market_data else None
        pe_ttm = market_data.pe_ttm if market_data else None
        shares_outstanding = market_data.shares_outstanding if market_data else None
        current_price = market_data.current_price if market_data else None
        corporate_tax_rate = valuation.corporate_tax_rate if valuation else None

        self.fcf_margin = safe_div(_cf.fcf_ttm, _f.revenue_ttm)
        self.roic = mf.roic(_f.ebit_ttm, corporate_tax_rate, _b.total_debt, _b.total_equity, _b.cash_and_equivalents)
        self.interest_coverage = mf.interest_coverage(_f.ebit_ttm, _f.interest_expense_ttm)
        self.ebit_margin = safe_div(_f.ebit_ttm, _f.revenue_ttm)
        self.price_to_fcf = safe_div(market_cap, _cf.fcf_ttm)
        self.fcf_yield = safe_div(_cf.fcf_ttm, market_cap)
        self.peg_ratio = safe_div(pe_ttm, _f.net_income_growth)
        self.price_to_sales = safe_div(market_cap, _f.revenue_ttm)
        self.price_to_book = mf.price_to_book(current_price, _b.total_equity, shares_outstanding)
        if _v.enterprise_value is not None:
            self.ev_ebit = safe_div(_v.enterprise_value, _f.ebit_ttm)
            self.ev_ebitda = safe_div(_v.enterprise_value, _f.ebitda_ttm)

        self.return_on_equity = safe_div(_f.net_income_ttm, _b.total_equity)
        self.return_on_assets = safe_div(_f.net_income_ttm, _b.total_assets)
        self.dividend_yield = mf.dividend_yield(_cf.dividends_paid_ttm, shares_outstanding, current_price)
        self.payout_ratio = mf.payout_ratio(_cf.dividends_paid_ttm, _f.net_income_ttm)
        self.debt_to_equity = safe_div(_b.total_debt, _b.total_equity)
        self.debt_to_equity = safe_div(_b.total_debt, _b.total_equity)
        
        self.book_value_per_share = safe_div(
            _b.total_equity, 
            float(shares_outstanding) if shares_outstanding is not None else None
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
            self.valuation.corporate_tax_rate = safe_div(_f.tax_expense_ttm, _f.ebt_ttm)
        if self.market_data:
            self.valuation.cost_of_debt = safe_div(abs(_f.interest_expense_ttm or 0.0), _b.total_debt)

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