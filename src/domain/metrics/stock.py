from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, dataclass_transform

from calculations import metrics_formulas as mf
from calculations import safe_div

from ..core.build_diagnostic import BuildDiagnostic
from ..core.enums import Sectors
from ..core.missing import MissingReason
from .history import BalanceSheetHistory, CashFlowHistory, FinancialsHistory

_COD_CEILING_BY_SECTOR: dict[str, float] = {
    "basic-materials":        0.25,
    "communication-services": 0.25,
    "consumer-cyclical":      0.25,
    "consumer-defensive":     0.20,
    "energy":                 0.25,
    "financial-services":     0.25,
    "healthcare":             0.20,
    "industrials":            0.25,
    "real-estate":            0.25,
    "technology":             0.25,
    "utilities":              0.20,
}
_COD_CEILING_DEFAULT = 0.30


def _cod_ceiling(sector: Optional[Sectors]) -> float:
    if sector is None:
        return _COD_CEILING_DEFAULT
    return _COD_CEILING_BY_SECTOR.get(sector.value, _COD_CEILING_DEFAULT)


def _bind_fields(cls):
    for f in cls.__dataclass_fields__.values():
        setattr(cls, f.name, f)
    return cls


@dataclass_transform()
def bindable_dataclass(cls=None, /):
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
    revenue_growth_rate:  float = 0.0
    net_income_growth:    float = 0.0
    gross_margin:         float = 0.0
    operating_margin:     float = 0.0
    net_margin:           float = 0.0
    ebitda_ttm:           float = 0.0
    history: Optional[FinancialsHistory] = None

    def __post_init__(self) -> None:
        self.revenue_growth_rate = (mf.calculate_growth(self.revenue_ttm, self.revenue_ttm_prev) or 0.0)
        self.net_income_growth   = (mf.calculate_growth(self.net_income_ttm, self.net_income_ttm_prev) or 0.0)
        self.gross_margin     = safe_div(self.gross_profit_ttm,     self.revenue_ttm) or 0.0
        self.operating_margin = safe_div(self.operating_income_ttm, self.revenue_ttm) or 0.0
        self.net_margin       = safe_div(self.net_income_ttm,       self.revenue_ttm) or 0.0
        self.ebitda_ttm       = mf.safe_sum(self.ebit_ttm, self.da_ttm)


@bindable_dataclass
class CashFlow:
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
        self.quick_ratio   = mf.quick_ratio(self.current_assets, self.inventory, self.current_liabilities) or 0.0


@bindable_dataclass
class MarketData:
    current_price:       float
    shares_outstanding:  int
    market_cap:          float
    beta:                float = 1.0
    eps_ttm:             float = 0.0
    # BUG-9 fix: pe_ttm explicitly typed as Optional[float] so None from yfinance
    # (negative-EPS companies have no P/E) does not crash PEChecker comparisons.
    pe_ttm:              Optional[float] = None
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

    cost_of_debt is clamped to a sector-specific ceiling inside Valuation.build()
    to prevent data-quality issues (e.g. tiny debt book vs. large interest expense)
    from producing nonsensical WACC values.  When the raw ratio exceeds the ceiling
    a DERIVED_FAILED diagnostic is emitted and cost_of_debt is set to 0.0 so the
    DCF checker's existing High Cost of Debt guard fires correctly.
    """

    highest_price:        float           = 0.0
    cost_of_debt:         float           = 0.0
    corporate_tax_rate:   float           = 0.0
    price_to_sales:       float           = 0.0
    price_to_book:        float           = 0.0
    median_historical_pe: Optional[float] = None
    fcf_cagr:             float           = 0.0
    forward_growth_rate:  float           = 0.0
    enterprise_value:     float           = 0.0
    # BUG-5 fix: expose normalized FCF for display/downstream use
    normalized_fcf:       Optional[float] = None
    capex_spike_detected: bool            = False

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
        sector:             Optional[Sectors] = None,
    ) -> Tuple["Valuation", List[BuildDiagnostic]]:
        diagnostics: List[BuildDiagnostic] = []
        _D = MissingReason.DERIVED_FAILED
        _Z = MissingReason.ZERO_DENOMINATOR
        _N = MissingReason.NOT_APPLICABLE
        _I = MissingReason.INSUFFICIENT_DATA

        # --- corporate_tax_rate ---
        if corporate_tax_rate == 0.0:
            corporate_tax_rate = (safe_div(financials.tax_expense_ttm, financials.ebt_ttm) or 0.0)
            if corporate_tax_rate == 0.0:
                if financials.ebt_ttm == 0.0 and financials.tax_expense_ttm == 0.0:
                    diagnostics.append(BuildDiagnostic("Valuation", "corporate_tax_rate", _D,
                        "both ebt_ttm and tax_expense_ttm are zero or missing"))
                elif financials.ebt_ttm == 0.0:
                    diagnostics.append(BuildDiagnostic("Valuation", "corporate_tax_rate", _Z,
                        "ebt_ttm is zero — tax rate is mathematically undefined"))

        # --- cost_of_debt with ceiling (BUG-6 fix) ---
        if cost_of_debt == 0.0 and balance_sheet.total_debt != 0.0:
            raw_cod = (safe_div(abs(financials.interest_expense_ttm or 0.0), balance_sheet.total_debt) or 0.0)
            ceiling = _cod_ceiling(sector)
            if raw_cod > ceiling:
                diagnostics.append(BuildDiagnostic(
                    "Valuation", "cost_of_debt", _D,
                    f"Computed cost_of_debt {raw_cod:.1%} exceeds sector ceiling {ceiling:.0%}. "
                    f"Likely a data-quality issue (misclassified debt or interest items). "
                    f"Set to 0.0 so the DCF validator can surface this as a blocking factor."
                ))
                cost_of_debt = 0.0
            else:
                cost_of_debt = raw_cod
                if cost_of_debt == 0.0:
                    diagnostics.append(BuildDiagnostic("Valuation", "cost_of_debt", _D,
                        "interest_expense_ttm is zero or missing"))
        elif cost_of_debt == 0.0 and balance_sheet.total_debt == 0.0:
            diagnostics.append(BuildDiagnostic("Valuation", "cost_of_debt", _N, "no debt on balance sheet"))

        # --- enterprise_value ---
        ev = mf.enterprise_value(
            market_data.market_cap, balance_sheet.total_debt, balance_sheet.cash_and_equivalents
        ) or 0.0
        if ev == 0.0 and market_data.market_cap == 0.0:
            diagnostics.append(BuildDiagnostic("Valuation", "enterprise_value", _D, "market_cap is zero"))

        price_to_sales = safe_div(market_data.market_cap, financials.revenue_ttm) or 0.0
        if price_to_sales == 0.0 and financials.revenue_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Valuation", "price_to_sales", _Z, "revenue_ttm is zero"))

        price_to_book = mf.price_to_book(
            price=market_data.current_price,
            total_equity=balance_sheet.total_equity,
            shares_outstanding=market_data.shares_outstanding,
        ) or 0.0

        # --- forward_growth_rate ---
        forward_growth_rate: float = 0.0
        if (financials.history is not None
                and financials.history.net_income_annual is not None
                and len(financials.history.net_income_annual) >= 2):
            forward_growth_rate = mf.cagr_from_series(financials.history.net_income_annual) or 0.0

        if forward_growth_rate == 0.0:
            eps_series = historical_data.eps_history if historical_data else None
            if eps_series and len(eps_series) > 1:
                forward_growth_rate = mf.cagr_from_series(eps_series) or 0.0

        if forward_growth_rate == 0.0:
            forward_growth_rate = financials.net_income_growth

        if forward_growth_rate == 0.0:
            diagnostics.append(BuildDiagnostic("Valuation", "forward_growth_rate", _D,
                "all growth signals (NI CAGR, EPS CAGR, TTM growth) resolved to zero"))

        # --- median historical P/E ---
        median_pe: Optional[float] = None
        if historical_data and historical_data.price_history:
            eps_history = historical_data.eps_history
            if eps_history:
                median_pe = mf.median_pe_ratio(
                    prices=historical_data.price_history, eps_values=eps_history
                )
        if median_pe is None:
            diagnostics.append(BuildDiagnostic("Valuation", "median_historical_pe", _I,
                "fewer than 3 valid (price, EPS) pairs in historical data"))

        # --- FCF CAGR ---
        fcf_cagr: float = 0.0
        if (cash_flow.history is not None
                and cash_flow.history.fcf_annual is not None
                and len(cash_flow.history.fcf_annual) >= 2):
            fcf_cagr = mf.cagr_from_series(cash_flow.history.fcf_annual) or 0.0

        if fcf_cagr == 0.0:
            fcf_now  = cash_flow.fcf_ttm
            fcf_prev = cash_flow.last_year_fcf
            if fcf_now != 0.0 and fcf_prev > 0.0:
                fcf_cagr = (fcf_now / fcf_prev) - 1.0

        if fcf_cagr == 0.0:
            if cash_flow.history is None or cash_flow.history.fcf_annual is None:
                diagnostics.append(BuildDiagnostic("Valuation", "fcf_cagr", _I,
                    "no annual FCF history available"))
            elif len(cash_flow.history.fcf_annual) < 2:
                diagnostics.append(BuildDiagnostic("Valuation", "fcf_cagr", _I,
                    "fewer than 2 annual FCF data points"))

        # --- BUG-5 fix: normalized FCF and capex spike detection ---
        normalized_fcf: Optional[float] = None
        capex_spike_detected: bool = False
        if (cash_flow.history is not None
                and cash_flow.history.capex_annual is not None
                and len(cash_flow.history.capex_annual) >= 3):
            capex_series = cash_flow.history.capex_annual
            # median of all-but-last year as the "normal" capex
            historical_capex = [abs(c) for c in capex_series[:-1] if c is not None]
            if historical_capex:
                sorted_capex = sorted(historical_capex)
                mid = len(sorted_capex) // 2
                median_capex = sorted_capex[mid] if len(sorted_capex) % 2 == 1 else (
                    (sorted_capex[mid - 1] + sorted_capex[mid]) / 2.0
                )
                ttm_capex_abs = abs(cash_flow.capex_ttm)
                if median_capex > 0 and ttm_capex_abs / median_capex > 2.5:
                    capex_spike_detected = True
                    normalized_fcf = cash_flow.operating_cf_ttm - median_capex
                    diagnostics.append(BuildDiagnostic(
                        "Valuation", "normalized_fcf", _D,
                        f"Capex spike detected: TTM capex {ttm_capex_abs/1e9:.1f}B is "
                        f"{ttm_capex_abs/median_capex:.1f}x the historical median "
                        f"{median_capex/1e9:.1f}B. "
                        f"normalized_fcf={normalized_fcf/1e9:.1f}B uses median capex instead."
                    ))

        instance = cls(
            highest_price=highest_price,
            cost_of_debt=cost_of_debt,
            corporate_tax_rate=corporate_tax_rate,
            price_to_sales=price_to_sales,
            price_to_book=price_to_book,
            median_historical_pe=median_pe,
            fcf_cagr=fcf_cagr,
            forward_growth_rate=forward_growth_rate,
            enterprise_value=ev,
            normalized_fcf=normalized_fcf,
            capex_spike_detected=capex_spike_detected,
        )
        return instance, diagnostics


@_bind_fields
@dataclass(frozen=True)
class Ratios:
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
    # BUG-13 fix: expose buyback yield alongside dividend yield
    buyback_yield:        float = 0.0
    total_shareholder_yield: float = 0.0

    @classmethod
    def build(
        cls,
        *,
        financials:    "Financials",
        cash_flow:     "CashFlow",
        balance_sheet: "BalanceSheet",
        market_data:   Optional["MarketData"] = None,
        valuation:     Optional["Valuation"]  = None,
    ) -> Tuple["Ratios", List[BuildDiagnostic]]:
        import logging
        diagnostics: List[BuildDiagnostic] = []
        _D = MissingReason.DERIVED_FAILED
        _Z = MissingReason.ZERO_DENOMINATOR
        _N = MissingReason.NOT_APPLICABLE

        if not all([financials, cash_flow, balance_sheet]):
            logging.getLogger(__name__).warning(
                "Ratios.build: one or more required inputs is None — returning empty Ratios."
            )
            return cls(), diagnostics

        market_cap         = market_data.market_cap         if market_data else 0.0
        pe_ttm             = market_data.pe_ttm              if market_data else None
        shares_outstanding = market_data.shares_outstanding  if market_data else 0
        current_price      = market_data.current_price       if market_data else 0.0
        corporate_tax_rate = valuation.corporate_tax_rate    if valuation   else 0.0
        ev                 = valuation.enterprise_value      if valuation   else 0.0

        fcf_margin = safe_div(cash_flow.fcf_ttm, financials.revenue_ttm) or 0.0

        roic = mf.roic(
            financials.ebit_ttm, corporate_tax_rate,
            balance_sheet.total_debt, balance_sheet.total_equity,
            balance_sheet.cash_and_equivalents,
        ) or 0.0
        if roic == 0.0 and financials.ebit_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "roic", _D, "ebit_ttm is zero or missing"))

        interest_coverage = mf.interest_coverage(financials.ebit_ttm, financials.interest_expense_ttm) or 0.0
        if interest_coverage == 0.0 and financials.interest_expense_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "interest_coverage", _N,
                "interest_expense_ttm is zero — company likely has no debt"))

        ebit_margin  = safe_div(financials.ebit_ttm, financials.revenue_ttm) or 0.0
        price_to_fcf = safe_div(market_cap, cash_flow.fcf_ttm) or 0.0
        fcf_yield    = safe_div(cash_flow.fcf_ttm, market_cap) or 0.0

        if price_to_fcf == 0.0 and cash_flow.fcf_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "price_to_fcf", _Z, "fcf_ttm is zero"))
        if fcf_yield == 0.0 and cash_flow.fcf_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "fcf_yield", _Z, "fcf_ttm is zero"))

        # BUG-9 fix: pe_ttm is Optional[float], guard None before comparison
        peg_ratio = 0.0
        if pe_ttm is not None and pe_ttm != 0.0 and financials.net_income_growth != 0.0:
            peg_ratio = safe_div(pe_ttm, financials.net_income_growth) or 0.0
        if peg_ratio == 0.0 and financials.net_income_growth == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "peg_ratio", _Z,
                "net_income_growth is zero — PEG is undefined"))

        price_to_sales = safe_div(market_cap, financials.revenue_ttm) or 0.0
        price_to_book  = mf.price_to_book(current_price, balance_sheet.total_equity, shares_outstanding) or 0.0
        ev_ebit   = safe_div(ev, financials.ebit_ttm)   or 0.0
        ev_ebitda = safe_div(ev, financials.ebitda_ttm) or 0.0

        if ev_ebit == 0.0 and financials.ebit_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "ev_ebit", _Z, "ebit_ttm is zero"))
        if ev_ebitda == 0.0 and financials.ebitda_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "ev_ebitda", _Z, "ebitda_ttm is zero"))

        return_on_equity = safe_div(financials.net_income_ttm, balance_sheet.total_equity) or 0.0
        return_on_assets = safe_div(financials.net_income_ttm, balance_sheet.total_assets) or 0.0

        dividend_yield = mf.dividend_yield(
            cash_flow.dividends_paid_ttm, shares_outstanding, current_price
        ) or 0.0
        payout_ratio = mf.payout_ratio(cash_flow.dividends_paid_ttm, financials.net_income_ttm) or 0.0

        if dividend_yield == 0.0 and cash_flow.dividends_paid_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "dividend_yield", _N,
                "dividends_paid_ttm is zero — company may not pay dividends"))
        if payout_ratio == 0.0 and cash_flow.dividends_paid_ttm == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "payout_ratio", _N, "dividends_paid_ttm is zero"))

        debt_to_equity = safe_div(balance_sheet.total_debt, balance_sheet.total_equity) or 0.0
        if debt_to_equity == 0.0 and balance_sheet.total_debt == 0.0:
            diagnostics.append(BuildDiagnostic("Ratios", "debt_to_equity", _N,
                "total_debt is zero — company is debt-free"))

        book_value_per_share = safe_div(
            balance_sheet.total_equity,
            float(shares_outstanding) if shares_outstanding else None,
        ) or 0.0

        # BUG-13 fix: buyback yield and total shareholder yield
        buyback_yield = 0.0
        if market_cap > 0 and cash_flow.share_buybacks_ttm != 0.0:
            buyback_yield = safe_div(abs(cash_flow.share_buybacks_ttm), market_cap) or 0.0
        total_shareholder_yield = dividend_yield + buyback_yield

        instance = cls(
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
            buyback_yield=buyback_yield,
            total_shareholder_yield=total_shareholder_yield,
        )
        return instance, diagnostics


@bindable_dataclass
class StockMetrics:
    profile:         CompanyProfile
    financials:      Financials
    cash_flow:       CashFlow
    balance_sheet:   BalanceSheet
    market_data:     MarketData
    valuation:       Valuation
    historical_data: Optional[HistoricalData]      = None
    ratios:          Optional[Ratios]              = None
    _diagnostics: List[BuildDiagnostic] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        pass

    def finalize(self) -> "StockMetrics":
        self._rebuild_derived()
        return self

    def _rebuild_derived(self) -> None:
        valuation, val_diags = Valuation.build(
            financials=self.financials,
            balance_sheet=self.balance_sheet,
            market_data=self.market_data,
            cash_flow=self.cash_flow,
            historical_data=self.historical_data,
            highest_price=self.valuation.highest_price,
            cost_of_debt=self.valuation.cost_of_debt,
            corporate_tax_rate=self.valuation.corporate_tax_rate,
            sector=self.profile.sector,
        )
        self.valuation = valuation

        ratios, ratio_diags = Ratios.build(
            financials=self.financials,
            cash_flow=self.cash_flow,
            balance_sheet=self.balance_sheet,
            market_data=self.market_data,
            valuation=self.valuation,
        )
        self.ratios = ratios
        self._diagnostics = val_diags + ratio_diags