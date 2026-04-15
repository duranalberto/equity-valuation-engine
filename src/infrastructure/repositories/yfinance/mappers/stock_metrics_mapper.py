from domain.core.enums import Sectors
from domain.metrics.history import (
    BalanceSheetHistory,
    CashFlowHistory,
    FinancialsHistory,
)
from domain.metrics.stock import (
    BalanceSheet,
    CashFlow,
    CompanyProfile,
    Financials,
    MarketData,
    StockMetrics,
)
from infrastructure.mappers.base_mapper import GenericMapper
from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper
from infrastructure.repositories.financial_repository import (
    Action,
    EnumField,
    Period,
    Statement,
)

from .common_constants import (
    FINANCIAL_CURRENCY_LABEL,
    SECTOR_LABEL,
    TRADING_CURRENCY_LABEL,
)
from .yfinance_fields import (
    CurrencyType,
    YfFinancialField,
    YfLabelField,
    YfPerShareFinancialField,
    YfSeriesField,
)

EPS_LABELS = [
    "eps", "earnings per share", "diluted earnings per share",
    "basic earnings per share", "basic eps", "diluted eps",
    "earnings per share basic", "earnings per share diluted",
]

REVENUE_LABELS = [
    "revenue", "net sales", "total revenue", "sales",
    "total sales", "top line revenue", "net revenue",
    "operating revenue", "total operating revenue",
]

NET_INCOME_LABELS = [
    "net income", "net earnings",
    "netincome", "netearnings",
    "net_income", "net_earnings",
    "net income applicable to common shareholders",
    "net income common stockholders",
    "net income to common stockholders",
    "net income available to common shareholders",
    "net income applicable to common stock",
    "netincomeapplicabletocommonshareholders",
    "consolidated net income",
    "profit attributable to owners",
]

_OPERATING_LABELS = [
    "operating cash flow", "operatingcashflow",
    "operating_cash_flow", "cashflowfromoperations",
    "total cash from operating activities",
    "totalcashfromoperatingactivities",
    "cash provided by operating activities",
    "cashprovidedbyoperatingactivities",
    "cash flow from operations",
    "net cash provided by operating activities",
    "netcashprovidedbyoperatingactivities",
]

_CAPEX_LABELS = [
    "capital expenditures", "capital expenditure",
    "capitalexpenditures", "capital_expenditures",
    "purchase of fixed assets", "capex",
    "purchases of property plant and equipment",
    "investments in property plant and equipment",
    "additions to property plant and equipment",
]

_DA_LABELS = [
    "depreciation and amortization", "depreciation",
    "amortization", "depreciationamortization",
    "depreciation and amortisation", "depreciation_and_amortization",
]

_EBIT_LABELS = [
    "ebit",
    "earnings before interest and taxes",
    "income before interest and taxes",
    "profit before interest and taxes",
    "operating profit before interest",
]

_GROSS_PROFIT_LABELS = [
    "gross profit", "total gross profit",
    "grossprofit", "totalgrossprofit",
    "gross_profit", "total_gross_profit",
]

_OPERATING_INCOME_LABELS = [
    "operating income", "operating profit",
    "operatingincome", "operatingprofit",
    "operating_income", "operating_profit",
    "income from operations",
    "income_from_operations",
    "income from operation",
]

_EBT_LABELS = [
    "income before tax", "earnings before tax",
    "income before income taxes",
    "pretax income", "profit before tax",
    "pre tax income", "pre-tax profit",
    "income before provision for income taxes",
    "income before taxes", "earnings before taxes",
    "income before tax expense", "income before income tax",
    "profit before income taxes",
    "earnings before income taxes",
]

_TAX_LABELS = [
    "income tax expense", "taxes",
    "provision for income taxes",
    "tax provision", "tax expense",
    "income taxes", "income tax",
    "provision for taxes", "income tax payable",
    "income tax benefit", "state income taxes",
    "taxes and licenses", "federal income taxes",
]

_INTEREST_LABELS = [
    "interest expense", "cost of debt",
    "financing expense", "interest charges",
    "finance costs", "interest paid",
    "interest and debt expense",
    "interest expense net",
    "interest expense (income)",
    "interest income (expense)",
    "interest expense, net",
    "net interest expense",
    "interest and financing charges",
]

_DIVIDENDS_LABELS = [
    "dividends paid", "cash dividends paid",
    "common dividends paid", "payments of dividends",
    "preferred dividends paid",
]

_BUYBACKS_LABELS = [
    "repurchaseofstock", "stock buybacks",
    "repurchase of capital stock",
    "repurchase of stock",
    "repurchase of common stock",
    "repurchaseofcommonstock",
    "repurchase of shares",
    "common stock repurchased",
    "commonstockrepurchased",
    "purchase of treasury stock",
    "purchaseoftreasurystock",
]

_TOTAL_DEBT_LABELS = [
    "total debt", "long term debt", "current debt",
    "short term debt", "long term borrowings",
    "short term borrowings", "total borrowings",
    "interest bearing debt", "gross debt", "funded debt",
    "notes payable", "bank loans", "debt obligations",
]

_TOTAL_EQUITY_LABELS = [
    "stockholders equity", "common stock equity",
    "total equity gross minority interest",
    "total shareholders equity",
    "total stockholder equity",
    "shareholders equity", "owners equity",
    "total equity",
    "equity attributable to shareholders",
    "total partners capital",
    "stockholders' equity", "equity capital",
]

_CASH_LABELS = [
    "cash and cash equivalents",
    "cash and equivalents", "cash",
    "cash & short term investments",
    "short term investments",
    "cash and short term investments",
    "cash & equivalents", "cash equivalents",
    "cash and marketable securities",
    "marketable securities", "cash on hand",
    "liquid assets", "cash and bank balances",
]

_TOTAL_ASSETS_LABELS = [
    "total assets", "totalassets",
    "total_assets", "assets",
    "total consolidated assets",
]

_TOTAL_LIABILITIES_LABELS = [
    "total liabilities", "total liab",
    "totalliabilities", "total_liabilities",
    "liabilities",
    "total liabilities net minority interest",
    "total_liabilities_net_minority_interest",
    "totalliabilitiesnetminorityinterest",
    "total liabilities (net minority interest)",
    "total-liabilities-net-minority-interest",
    "totalliabilities_netminorityinterest",
]

_CURRENT_ASSETS_LABELS = [
    "total current assets", "current assets",
    "totalcurrentassets", "currentassets",
    "total_current_assets", "current assets total",
]

_CURRENT_LIABILITIES_LABELS = [
    "total current liabilities", "current liabilities",
    "totalcurrentliabilities", "currentliabilities",
    "total_current_liabilities", "current liabilities total",
]

_INVENTORY_LABELS = [
    "inventory", "inventory, net",
    "merchandise inventory", "raw materials",
    "inventory_net", "finished goods", "inventories",
    "work in progress",
]

_FIN_INC_TTM = {
    "currency_type": CurrencyType.FINANCIAL,
    "statement":     Statement.INCOME,
    "action":        Action.GET_TTM_VALUE,
}

_FIN_CF = {
    "currency_type": CurrencyType.FINANCIAL,
    "statement":     Statement.CASHFLOW,
}

_FIN_BS_LATEST = {
    "currency_type": CurrencyType.FINANCIAL,
    "statement":     Statement.BALANCE_SHEET,
    "period":        Period.QUARTERLY,
    "action":        Action.GET_LATEST_VALUE,
}


class CompanyProfileMapper(GenericMapper):

    @property
    def target_type(self):
        return CompanyProfile

    @property
    def mapping(self):
        return {
            CompanyProfile.ticker:             YfLabelField(label="symbol"),
            CompanyProfile.company_name:       YfLabelField(label="longName"),
            CompanyProfile.sector:             EnumField(label=SECTOR_LABEL, enum=Sectors),
            CompanyProfile.industry:           YfLabelField(label="industry"),
            CompanyProfile.country:            YfLabelField(label="country"),
            CompanyProfile.financial_currency: YfLabelField(label=FINANCIAL_CURRENCY_LABEL),
            CompanyProfile.trading_currency:   YfLabelField(label=TRADING_CURRENCY_LABEL),
            CompanyProfile.exchange:           YfLabelField(label="exchange"),
            CompanyProfile.quote_type:         YfLabelField(label="quoteType"),
            CompanyProfile.website:            YfLabelField(label="website"),
        }


class FinancialsMapper(GenericMapper):

    @property
    def target_type(self):
        return Financials

    @property
    def mapping(self):
        return {
            Financials.revenue_ttm: YfFinancialField(
                label=REVENUE_LABELS, **_FIN_INC_TTM
            ),
            Financials.gross_profit_ttm: YfFinancialField(
                label=_GROSS_PROFIT_LABELS, **_FIN_INC_TTM
            ),
            Financials.operating_income_ttm: YfFinancialField(
                label=_OPERATING_INCOME_LABELS, **_FIN_INC_TTM
            ),
            Financials.net_income_ttm: YfFinancialField(
                label=NET_INCOME_LABELS, **_FIN_INC_TTM
            ),
            Financials.ebit_ttm: YfFinancialField(
                label=_EBIT_LABELS, **_FIN_INC_TTM
            ),
            Financials.ebt_ttm: YfFinancialField(
                label=_EBT_LABELS, **_FIN_INC_TTM
            ),
            Financials.tax_expense_ttm: YfFinancialField(
                label=_TAX_LABELS, **_FIN_INC_TTM
            ),
            Financials.interest_expense_ttm: YfFinancialField(
                label=_INTEREST_LABELS, **_FIN_INC_TTM
            ),
            Financials.revenue_ttm_prev: YfFinancialField(
                label=REVENUE_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.INCOME,
                action=Action.GET_TTM_PREV_VALUE,
            ),
            Financials.net_income_ttm_prev: YfFinancialField(
                label=NET_INCOME_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.INCOME,
                action=Action.GET_TTM_PREV_VALUE,
            ),
            Financials.da_ttm: YfFinancialField(
                label=_DA_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.CASHFLOW,
                action=Action.GET_TTM_VALUE,
            ),
        }


class CashFlowMapper(GenericMapper):

    @property
    def target_type(self):
        return CashFlow

    @property
    def mapping(self):
        return {
            CashFlow.operating_cf_ttm: YfFinancialField(
                label=_OPERATING_LABELS, **_FIN_CF,
                action=Action.GET_TTM_VALUE,
            ),
            CashFlow.capex_ttm: YfFinancialField(
                label=_CAPEX_LABELS, **_FIN_CF,
                period=Period.QUARTERLY, action=Action.GET_TTM_VALUE,
            ),
            CashFlow.oper_cf_last_year: YfFinancialField(
                label=_OPERATING_LABELS, **_FIN_CF,
                period=Period.ANNUAL, action=Action.GET_LATEST_VALUE,
            ),
            CashFlow.latest_annual_capex: YfFinancialField(
                label=_CAPEX_LABELS, **_FIN_CF,
                period=Period.ANNUAL, action=Action.GET_LATEST_VALUE,
            ),
            CashFlow.oper_cf_last_quarter: YfFinancialField(
                label=_OPERATING_LABELS, **_FIN_CF,
                period=Period.QUARTERLY, action=Action.GET_LATEST_VALUE,
            ),
            CashFlow.latest_quarter_capex: YfFinancialField(
                label=_CAPEX_LABELS, **_FIN_CF,
                period=Period.QUARTERLY, action=Action.GET_LATEST_VALUE,
            ),
            CashFlow.dividends_paid_ttm: YfFinancialField(
                label=_DIVIDENDS_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.CASHFLOW,
                action=Action.GET_TTM_VALUE,
            ),
            CashFlow.share_buybacks_ttm: YfFinancialField(
                label=_BUYBACKS_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.CASHFLOW,
                action=Action.GET_TTM_VALUE,
            ),
        }


class BalanceSheetMapper(GenericMapper):

    @property
    def target_type(self):
        return BalanceSheet

    @property
    def mapping(self):
        return {
            BalanceSheet.current_assets:       YfFinancialField(label=_CURRENT_ASSETS_LABELS,      **_FIN_BS_LATEST),
            BalanceSheet.current_liabilities:  YfFinancialField(label=_CURRENT_LIABILITIES_LABELS, **_FIN_BS_LATEST),
            BalanceSheet.inventory:            YfFinancialField(label=_INVENTORY_LABELS,            **_FIN_BS_LATEST),
            BalanceSheet.total_debt:           YfFinancialField(label=_TOTAL_DEBT_LABELS,           **_FIN_BS_LATEST),
            BalanceSheet.total_equity:         YfFinancialField(label=_TOTAL_EQUITY_LABELS,         **_FIN_BS_LATEST),
            BalanceSheet.cash_and_equivalents: YfFinancialField(label=_CASH_LABELS,                 **_FIN_BS_LATEST),
            BalanceSheet.total_assets:         YfFinancialField(label=_TOTAL_ASSETS_LABELS,         **_FIN_BS_LATEST),
            BalanceSheet.total_liabilities:    YfFinancialField(label=_TOTAL_LIABILITIES_LABELS,    **_FIN_BS_LATEST),
        }


class MarketDataMapper(GenericMapper):

    @property
    def target_type(self):
        return MarketData

    @property
    def mapping(self):
        return {
            MarketData.current_price:       YfLabelField(label="currentPrice",         currency_type=CurrencyType.TRADING),
            MarketData.shares_outstanding:  YfLabelField(label="sharesOutstanding"),
            MarketData.market_cap:          YfLabelField(label="marketCap",             currency_type=CurrencyType.TRADING),
            MarketData.beta:                YfLabelField(label="beta"),
            MarketData.pe_ttm:              YfLabelField(label="trailingPE"),
            MarketData.low_52_week:         YfLabelField(label="fiftyTwoWeekLow",       currency_type=CurrencyType.TRADING),
            MarketData.high_52_week:        YfLabelField(label="fiftyTwoWeekHigh",      currency_type=CurrencyType.TRADING),
            MarketData.fifty_day_avg:       YfLabelField(label="fiftyDayAverage",       currency_type=CurrencyType.TRADING),
            MarketData.two_hundred_day_avg: YfLabelField(label="twoHundredDayAverage",  currency_type=CurrencyType.TRADING),
            MarketData.volume:              YfLabelField(label="volume",                currency_type=CurrencyType.TRADING),
            MarketData.avg_volume:          YfLabelField(
                label=["averageVolume", "averageDailyVolume10Day"],
                currency_type=CurrencyType.TRADING,
            ),
            MarketData.eps_ttm: YfPerShareFinancialField(
                label=EPS_LABELS,
                currency_type=CurrencyType.NONE,
                statement=Statement.INCOME,
                action=Action.GET_TTM_VALUE,
            ),
            MarketData.last_quarter_eps: YfPerShareFinancialField(
                label=EPS_LABELS,
                currency_type=CurrencyType.NONE,
                statement=Statement.INCOME,
                period=Period.QUARTERLY,
                action=Action.GET_LATEST_VALUE,
            ),
            MarketData.last_year_eps: YfPerShareFinancialField(
                label=EPS_LABELS,
                currency_type=CurrencyType.NONE,
                statement=Statement.INCOME,
                period=Period.ANNUAL,
                action=Action.GET_LATEST_VALUE,
            ),
        }


class StockMetricsMapper(BaseStockMetricsMapper):
    _MAPPER_EXCLUDED_FIELDS: frozenset = frozenset({"valuation", "ratios", "historical_data"})

    @property
    def target_type(self):
        return StockMetrics

    @property
    def mapping(self):
        profile       = getattr(StockMetrics, "profile")
        financials    = getattr(StockMetrics, "financials")
        cash_flow     = getattr(StockMetrics, "cash_flow")
        balance_sheet = getattr(StockMetrics, "balance_sheet")
        market_data   = getattr(StockMetrics, "market_data")

        return {
            profile:       CompanyProfileMapper(),
            financials:    FinancialsMapper(),
            cash_flow:     CashFlowMapper(),
            balance_sheet: BalanceSheetMapper(),
            market_data:   MarketDataMapper(),
        }

    def validate(self) -> None:
        """
        Validate the mapper, exempting fields listed in ``_MAPPER_EXCLUDED_FIELDS``.

        ``GenericMapper.validate()`` raises ``ValueError`` for any non-Optional
        field of the target type that is absent from the mapping.  That contract
        is correct for leaf sub-model mappers but must be relaxed here because
        ``valuation``, ``ratios``, and ``historical_data`` on ``StockMetrics``
        are built through dedicated factory paths that deliberately bypass the
        mapper pipeline — they are never passed through ``build_model()``.

        We re-implement only the missing-fields check from the base class,
        filtering out the known exclusions, and then delegate duplicate-value
        checking to the base implementation via ``_validate_unique_values()``.
        """
        domain = self.extract_domain(self.target_type)
        mapping_keys = set(self.normalized_mapping.keys())

        missing_required = {
            key
            for key in set(domain.keys()) - mapping_keys
            if key not in self._MAPPER_EXCLUDED_FIELDS
            and not self.is_optional_type(domain[key])
        }
        if missing_required:
            raise ValueError(
                f"StockMetricsMapper is missing required fields: {missing_required}"
            )

        extra = mapping_keys - set(domain.keys())
        if extra:
            raise ValueError(
                f"StockMetricsMapper has invalid field names: {extra}"
            )

        self._validate_unique_values()


_FIN_QUARTERLY = {"currency_type": CurrencyType.FINANCIAL, "statement": Statement.INCOME,        "period": Period.QUARTERLY}
_CF_QUARTERLY  = {"currency_type": CurrencyType.FINANCIAL, "statement": Statement.CASHFLOW,      "period": Period.QUARTERLY}
_BS_QUARTERLY  = {"currency_type": CurrencyType.FINANCIAL, "statement": Statement.BALANCE_SHEET, "period": Period.QUARTERLY}
_FIN_ANNUAL    = {"currency_type": CurrencyType.FINANCIAL, "statement": Statement.INCOME,        "period": Period.ANNUAL}
_CF_ANNUAL     = {"currency_type": CurrencyType.FINANCIAL, "statement": Statement.CASHFLOW,      "period": Period.ANNUAL}
_BS_ANNUAL     = {"currency_type": CurrencyType.FINANCIAL, "statement": Statement.BALANCE_SHEET, "period": Period.ANNUAL}


class FinancialsHistoryMapper(GenericMapper):
    """
    Maps ``FinancialsHistory`` fields to ``YfSeriesField`` descriptors.

    Uses string keys because ``FinancialsHistory`` is a plain ``@dataclass``
    (not ``bindable_dataclass``), so field descriptors are not bound as class
    attributes — only string keys work with ``GenericMapper._normalize_key``.
    """

    @property
    def target_type(self):
        return FinancialsHistory

    @property
    def mapping(self):
        return {
            "revenue_quarterly":          YfSeriesField(label=REVENUE_LABELS,             **_FIN_QUARTERLY),
            "gross_profit_quarterly":     YfSeriesField(label=_GROSS_PROFIT_LABELS,       **_FIN_QUARTERLY),
            "operating_income_quarterly": YfSeriesField(label=_OPERATING_INCOME_LABELS,   **_FIN_QUARTERLY),
            "net_income_quarterly":       YfSeriesField(label=NET_INCOME_LABELS,          **_FIN_QUARTERLY),
            "ebit_quarterly":             YfSeriesField(label=_EBIT_LABELS,               **_FIN_QUARTERLY),
            "ebt_quarterly":              YfSeriesField(label=_EBT_LABELS,                **_FIN_QUARTERLY),
            "tax_expense_quarterly":      YfSeriesField(label=_TAX_LABELS,                **_FIN_QUARTERLY),
            "interest_expense_quarterly": YfSeriesField(label=_INTEREST_LABELS,           **_FIN_QUARTERLY),
            "da_quarterly":               YfSeriesField(label=_DA_LABELS,
                                                        currency_type=CurrencyType.FINANCIAL,
                                                        statement=Statement.CASHFLOW,
                                                        period=Period.QUARTERLY),
            "revenue_annual":             YfSeriesField(label=REVENUE_LABELS,             **_FIN_ANNUAL),
            "gross_profit_annual":        YfSeriesField(label=_GROSS_PROFIT_LABELS,       **_FIN_ANNUAL),
            "operating_income_annual":    YfSeriesField(label=_OPERATING_INCOME_LABELS,   **_FIN_ANNUAL),
            "net_income_annual":          YfSeriesField(label=NET_INCOME_LABELS,          **_FIN_ANNUAL),
            "ebit_annual":                YfSeriesField(label=_EBIT_LABELS,               **_FIN_ANNUAL),
            "ebt_annual":                 YfSeriesField(label=_EBT_LABELS,                **_FIN_ANNUAL),
            "tax_expense_annual":         YfSeriesField(label=_TAX_LABELS,                **_FIN_ANNUAL),
            "interest_expense_annual":    YfSeriesField(label=_INTEREST_LABELS,           **_FIN_ANNUAL),
        }


class CashFlowHistoryMapper(GenericMapper):
    """
    Maps ``CashFlowHistory`` source fields to ``YfSeriesField`` descriptors.

    ``fcf_quarterly`` and ``fcf_annual`` are derived in ``__post_init__`` with
    ``init=False`` and must NOT appear in the mapper.
    """

    @property
    def target_type(self):
        return CashFlowHistory

    @property
    def mapping(self):
        return {
            "operating_cf_quarterly":   YfSeriesField(label=_OPERATING_LABELS, **_CF_QUARTERLY),
            "capex_quarterly":          YfSeriesField(label=_CAPEX_LABELS,      **_CF_QUARTERLY),
            "dividends_paid_quarterly": YfSeriesField(label=_DIVIDENDS_LABELS,  **_CF_QUARTERLY),
            "share_buybacks_quarterly": YfSeriesField(label=_BUYBACKS_LABELS,   **_CF_QUARTERLY),
            "operating_cf_annual":      YfSeriesField(label=_OPERATING_LABELS,  **_CF_ANNUAL),
            "capex_annual":             YfSeriesField(label=_CAPEX_LABELS,       **_CF_ANNUAL),
            "dividends_paid_annual":    YfSeriesField(label=_DIVIDENDS_LABELS,   **_CF_ANNUAL),
            "share_buybacks_annual":    YfSeriesField(label=_BUYBACKS_LABELS,    **_CF_ANNUAL),
        }


class BalanceSheetHistoryMapper(GenericMapper):
    """Uses string keys (plain ``@dataclass`` — see FinancialsHistoryMapper note)."""

    @property
    def target_type(self):
        return BalanceSheetHistory

    @property
    def mapping(self):
        return {
            "total_debt_quarterly":          YfSeriesField(label=_TOTAL_DEBT_LABELS,          **_BS_QUARTERLY),
            "total_equity_quarterly":        YfSeriesField(label=_TOTAL_EQUITY_LABELS,        **_BS_QUARTERLY),
            "cash_quarterly":                YfSeriesField(label=_CASH_LABELS,                **_BS_QUARTERLY),
            "total_assets_quarterly":        YfSeriesField(label=_TOTAL_ASSETS_LABELS,        **_BS_QUARTERLY),
            "total_liabilities_quarterly":   YfSeriesField(label=_TOTAL_LIABILITIES_LABELS,   **_BS_QUARTERLY),
            "current_assets_quarterly":      YfSeriesField(label=_CURRENT_ASSETS_LABELS,      **_BS_QUARTERLY),
            "current_liabilities_quarterly": YfSeriesField(label=_CURRENT_LIABILITIES_LABELS, **_BS_QUARTERLY),
            "inventory_quarterly":           YfSeriesField(label=_INVENTORY_LABELS,           **_BS_QUARTERLY),
            "total_debt_annual":             YfSeriesField(label=_TOTAL_DEBT_LABELS,          **_BS_ANNUAL),
            "total_equity_annual":           YfSeriesField(label=_TOTAL_EQUITY_LABELS,        **_BS_ANNUAL),
            "cash_annual":                   YfSeriesField(label=_CASH_LABELS,                **_BS_ANNUAL),
            "total_assets_annual":           YfSeriesField(label=_TOTAL_ASSETS_LABELS,        **_BS_ANNUAL),
        }