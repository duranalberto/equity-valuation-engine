from .yfinance_fields import(
    CurrencyType, YfLabelField, YfFinancialField
)
from infrastructure.repositories.financial_repository import (
    EnumField, Statement, Period, Action
)
from infrastructure.mappers.base_mapper import GenericMapper
from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper
from domain.core.enums import Sectors
from domain.metrics.stock import (
    StockMetrics, CompanyProfile, Valuation, Financials, 
    MarketData, CashFlow, BalanceSheet
)
from .common_constants import (
    SECTOR_LABEL, FINANCIAL_CURRENCY_LABEL, TRADING_CURRENCY_LABEL
)


class CompanyProfileMapper(GenericMapper):

    @property
    def target_type(self):
        return CompanyProfile

    @property
    def mapping(self):
        return {
            CompanyProfile.ticker: YfLabelField(label='symbol'),
            CompanyProfile.company_name: YfLabelField(label='longName'),
            CompanyProfile.sector: EnumField(label=SECTOR_LABEL, enum=Sectors),
            CompanyProfile.industry: YfLabelField(label='industry'),
            CompanyProfile.country: YfLabelField(label='country'),
            CompanyProfile.financial_currency: YfLabelField(label=FINANCIAL_CURRENCY_LABEL),
            CompanyProfile.trading_currency: YfLabelField(label=TRADING_CURRENCY_LABEL),
            CompanyProfile.exchange: YfLabelField(label='exchange'),
            CompanyProfile.quote_type: YfLabelField(label='quoteType'),
            CompanyProfile.website: YfLabelField(label='website'),
        }


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

NET_INCOMES_LABELS = [
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

_FINANCIAL_INCOME_TTM = {
    'currency_type':CurrencyType.FINANCIAL,
    'statement':Statement.INCOME,
    'action':Action.GET_TTM_VALUE
}

class FinancialsMapper(GenericMapper):

    @property
    def target_type(self):
        return Financials

    @property
    def mapping(self):
        return {
            Financials.revenue_ttm: YfFinancialField(
                label=REVENUE_LABELS,
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.gross_profit_ttm: YfFinancialField(
                label=[
                    "gross profit", "total gross profit",
                    "grossprofit", "totalgrossprofit",
                    "gross_profit", "total_gross_profit",
                ],
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.operating_income_ttm: YfFinancialField(
                label=[
                    "operating income", "operating profit",
                    "operatingincome", "operatingprofit",
                    "operating_income", "operating_profit",
                    "income from operations",
                    "income_from_operations",
                    "income from operation",
                ],
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.net_income_ttm: YfFinancialField(
                label=NET_INCOMES_LABELS,
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.ebit_ttm: YfFinancialField(
                label=[
                    "ebit",
                    "earnings before interest and taxes",
                    "income before interest and taxes",
                    "profit before interest and taxes",
                    "operating profit before interest",
                ],
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.ebt_ttm: YfFinancialField(
                label=[
                    "income before tax", "earnings before tax",
                    "income before income taxes",
                    "pretax income", "profit before tax",
                    "pre tax income", "pre-tax profit",
                    "income before provision for income taxes",
                    "income before taxes", "earnings before taxes",
                    "income before tax expense", "income before income tax",
                    "profit before income taxes",
                    "earnings before income taxes",
                    
                ],
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.tax_expense_ttm: YfFinancialField(
                label=[
                    "income tax expense", "taxes",
                    "provision for income taxes",
                    "tax provision", "tax expense",
                    "income taxes", "income tax",
                    "provision for taxes", "income tax payable",
                    "income tax benefit", "state income taxes",
                    "taxes and licenses", "federal income taxes",
                ],
                **_FINANCIAL_INCOME_TTM
            ),
             Financials.interest_expense_ttm: YfFinancialField(
                label=[
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
                ],
                **_FINANCIAL_INCOME_TTM
            ),
            Financials.revenue_ttm_prev: YfFinancialField(
                label=REVENUE_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.INCOME,
                action=Action.GET_TTM_PREV_VALUE
            ),
            Financials.net_income_ttm_prev: YfFinancialField(
                label=NET_INCOMES_LABELS,
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.INCOME,
                action=Action.GET_TTM_PREV_VALUE
            ),
            Financials.da_ttm: YfFinancialField(
                label=[
                    "depreciation and amortization", "depreciation", 
                    "amortization", "depreciationamortization",
                    "depreciation and amortisation", "depreciation_and_amortization"
                ],
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.CASHFLOW,
                action=Action.GET_TTM_VALUE
            )
        }


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

_FINANCIAL_CASHFLOW = {
    'currency_type':CurrencyType.FINANCIAL,
    'statement':Statement.CASHFLOW,
}

class CashFlowMapper(GenericMapper):

    @property
    def target_type(self):
        return CashFlow

    @property
    def mapping(self):
        return {
            CashFlow.operating_cf_ttm: YfFinancialField(
                label=_OPERATING_LABELS,
                **_FINANCIAL_CASHFLOW,
                action=Action.GET_TTM_VALUE
            ),
            CashFlow.capex_ttm: YfFinancialField(
                label=_CAPEX_LABELS,
                **_FINANCIAL_CASHFLOW,
                period=Period.QUARTERLY,
                action=Action.GET_TTM_VALUE
            ),
            CashFlow.oper_cf_last_year: YfFinancialField(
                label=_OPERATING_LABELS,
                **_FINANCIAL_CASHFLOW,
                period=Period.ANNUAL,
                action=Action.GET_LATEST_VALUE
            ),
            CashFlow.latest_annual_capex: YfFinancialField(
                label=_CAPEX_LABELS,
                **_FINANCIAL_CASHFLOW,
                period=Period.ANNUAL,
                action=Action.GET_LATEST_VALUE
            ),
            CashFlow.oper_cf_last_quarter: YfFinancialField(
                label=_OPERATING_LABELS,
                **_FINANCIAL_CASHFLOW,
                period=Period.QUARTERLY,
                action=Action.GET_LATEST_VALUE
            ),
            CashFlow.latest_quarter_capex: YfFinancialField(
                label=_CAPEX_LABELS,
                **_FINANCIAL_CASHFLOW,
                period=Period.QUARTERLY,
                action=Action.GET_LATEST_VALUE
            ),
            CashFlow.dividends_paid_ttm: YfFinancialField(
                label=[
                    "dividends paid", "cash dividends paid",
                    "common dividends paid", "payments of dividends",
                    "preferred dividends paid",
                ],
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.CASHFLOW,
                action=Action.GET_TTM_VALUE
            ),
            CashFlow.share_buybacks_ttm: YfFinancialField(
                label=[
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
                ],
                currency_type=CurrencyType.FINANCIAL,
                statement=Statement.CASHFLOW,
                action=Action.GET_TTM_VALUE
            ),
        }


_FINANCIAL_BALANCE_SHEET_LAST_VALUE = {
    'currency_type':CurrencyType.FINANCIAL,
    'statement':Statement.BALANCE_SHEET,
    'period':Period.QUARTERLY,
    'action':Action.GET_LATEST_VALUE
}

class BalanceSheetMapper(GenericMapper):

    @property
    def target_type(self):
        return BalanceSheet

    @property
    def mapping(self):
        return  {
            BalanceSheet.current_assets: YfFinancialField(
                label=[
                    "total current assets",
                    "current assets",
                    "totalcurrentassets",
                    "currentassets",
                    "total_current_assets",
                    "current assets total",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.current_liabilities: YfFinancialField(
                label=[
                    "total current liabilities",
                    "current liabilities",
                    "totalcurrentliabilities",
                    "currentliabilities",
                    "total_current_liabilities",
                    "current liabilities total",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.inventory: YfFinancialField(
                label=[
                    "inventory", "inventory, net",
                    "merchandise inventory",
                    "raw materials", "inventory_net",
                    "finished goods", "inventories",
                    "work in progress",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.total_debt: YfFinancialField(
                label=[
                    "total debt",
                    "long term debt",
                    "current debt",
                    "short term debt",
                    "long term borrowings",
                    "short term borrowings",
                    "total borrowings",
                    "interest bearing debt",
                    "gross debt",
                    "funded debt",
                    "notes payable",
                    "bank loans",
                    "debt obligations",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.total_equity: YfFinancialField(
                label=[
                    "stockholders equity",
                    "common stock equity",
                    "total equity gross minority interest",
                    "total shareholders equity",
                    "total stockholder equity",
                    "shareholders equity",
                    "owners equity",
                    "total equity",
                    "equity attributable to shareholders",
                    "total partners capital",
                    "stockholders' equity",
                    "equity capital",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.cash_and_equivalents: YfFinancialField(
                label=[
                    "cash and cash equivalents",
                    "cash and equivalents",
                    "cash",
                    "cash & short term investments",
                    "short term investments",
                    "cash and short term investments",
                    "cash & equivalents",
                    "cash equivalents",
                    "cash and marketable securities",
                    "marketable securities",
                    "cash on hand",
                    "liquid assets",
                    "cash and bank balances",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.total_assets: YfFinancialField(
                label=[
                    "total assets",
                    "totalassets",
                    "total_assets",
                    "assets",
                    "total consolidated assets",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            ),
            BalanceSheet.total_liabilities: YfFinancialField(
                label = [
                    "total liabilities",
                    "total liab",
                    "totalliabilities",
                    "total_liabilities",
                    "liabilities",
                    "total liabilities net minority interest",
                    "total_liabilities_net_minority_interest",
                    "totalliabilitiesnetminorityinterest",
                    "total liabilities (net minority interest)",
                    "total-liabilities-net-minority-interest",
                    "totalliabilities_netminorityinterest",
                ],
                **_FINANCIAL_BALANCE_SHEET_LAST_VALUE
            )
        }


class MarketDataMapper(GenericMapper):

    @property
    def target_type(self):
        return MarketData

    @property
    def mapping(self):
        return {
            MarketData.current_price: YfLabelField(label='currentPrice', currency_type=CurrencyType.TRADING),
            MarketData.shares_outstanding: YfLabelField(label='sharesOutstanding'), 
            MarketData.market_cap: YfLabelField(label='marketCap', currency_type=CurrencyType.TRADING),
            MarketData.beta: YfLabelField(label='beta'),
            MarketData.pe_ttm: YfLabelField(label='trailingPE'),
            MarketData.low_52_week: YfLabelField(label='fiftyTwoWeekLow', currency_type=CurrencyType.TRADING),
            MarketData.high_52_week: YfLabelField(label='fiftyTwoWeekHigh', currency_type=CurrencyType.TRADING),
            MarketData.fifty_day_avg: YfLabelField(label='fiftyDayAverage', currency_type=CurrencyType.TRADING),
            MarketData.two_hundred_day_avg: YfLabelField(label='twoHundredDayAverage', currency_type=CurrencyType.TRADING),
            MarketData.volume: YfLabelField(label='volume', currency_type=CurrencyType.TRADING),
            MarketData.avg_volume: YfLabelField(label='averageVolume,averageDailyVolume10Day', currency_type=CurrencyType.TRADING),
            MarketData.eps_ttm: YfFinancialField(
                label=EPS_LABELS,
                currency_type=CurrencyType.NONE,
                statement=Statement.INCOME,
                action=Action.GET_TTM_VALUE
            ),
            MarketData.last_quarter_eps: YfFinancialField(
                label=EPS_LABELS,
                currency_type=CurrencyType.NONE,
                statement=Statement.INCOME,
                period=Period.QUARTERLY,
                action=Action.GET_LATEST_VALUE
            ),
            MarketData.last_year_eps: YfFinancialField(
                label=EPS_LABELS,
                currency_type=CurrencyType.NONE,
                statement=Statement.INCOME,
                period=Period.ANNUAL,
                action=Action.GET_LATEST_VALUE
            )
        }


class ValuationMapper(GenericMapper):

    @property
    def target_type(self):
        return Valuation

    @property
    def mapping(self):
            return {
                Valuation.cost_of_debt: YfLabelField(label='costOfDebt'),
                Valuation.corporate_tax_rate: YfLabelField(label='corporateTaxRate'),
            }


class StockMetricsMapper(BaseStockMetricsMapper):

    @property
    def target_type(self):
        return StockMetrics

    @property
    def mapping(self):
        return {
            StockMetrics.profile: CompanyProfileMapper(),
            StockMetrics.financials: FinancialsMapper(),
            StockMetrics.cash_flow: CashFlowMapper(),
            StockMetrics.balance_sheet: BalanceSheetMapper(),
            StockMetrics.market_data: MarketDataMapper(),
            StockMetrics.valuation: ValuationMapper(),
        }

