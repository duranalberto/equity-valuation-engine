from __future__ import annotations

import domain.metrics.stock as sm
from domain.metrics.history import (
    BalanceSheetHistory,
    CashFlowHistory,
    FinancialsHistory,
)
from infrastructure.mappers.base_mapper import GenericMapper
from infrastructure.mappers.stock_metrics_mapper import StockMetricsMapper
from infrastructure.repositories.financial_repository import (
    Action,
    EnumField,
    Period,
)

from .common_constants import (
    BALANCE_SHEET_LABELS,
    CASH_FLOW_LABELS,
    INCOME_STMT_LABELS,
    INFO_LABELS,
)
from .yfinance_fields import Statement, YfFinancialField, YfLabelField, YfSeriesField


def _make_company_profile_mapper() -> GenericMapper:
    return GenericMapper(
        target_type=sm.CompanyProfile,
        fields={
            "ticker":             YfLabelField(INFO_LABELS["ticker"]),
            "company_name":       YfLabelField(INFO_LABELS["company_name"]),
            "sector":             EnumField(INFO_LABELS["sector"]),
            "industry":           YfLabelField(INFO_LABELS["industry"]),
            "country":            YfLabelField(INFO_LABELS["country"]),
            "financial_currency": YfLabelField(INFO_LABELS["financial_currency"]),
            "trading_currency":   YfLabelField(INFO_LABELS["trading_currency"]),
            "exchange":           YfLabelField(INFO_LABELS["exchange"]),
            "quote_type":         YfLabelField(INFO_LABELS["quote_type"]),
            "website":            YfLabelField(INFO_LABELS["website"]),
        },
    )


def _make_financials_mapper() -> GenericMapper:
    return GenericMapper(
        target_type=sm.Financials,
        fields={
            "revenue_ttm":          YfFinancialField(INCOME_STMT_LABELS["revenue"],          Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "ebit_ttm":             YfFinancialField(INCOME_STMT_LABELS["ebit"],             Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "ebt_ttm":              YfFinancialField(INCOME_STMT_LABELS["ebt"],              Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "tax_expense_ttm":      YfFinancialField(INCOME_STMT_LABELS["tax_expense"],      Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "interest_expense_ttm": YfFinancialField(INCOME_STMT_LABELS["interest_expense"], Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "gross_profit_ttm":     YfFinancialField(INCOME_STMT_LABELS["gross_profit"],     Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "operating_income_ttm": YfFinancialField(INCOME_STMT_LABELS["operating_income"], Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "net_income_ttm":       YfFinancialField(INCOME_STMT_LABELS["net_income"],       Action.GET_TTM_VALUE,      statement=Statement.INCOME),
            "revenue_ttm_prev":     YfFinancialField(INCOME_STMT_LABELS["revenue"],          Action.GET_TTM_PREV_VALUE, statement=Statement.INCOME),
            "net_income_ttm_prev":  YfFinancialField(INCOME_STMT_LABELS["net_income"],       Action.GET_TTM_PREV_VALUE, statement=Statement.INCOME),
            "da_ttm":               YfFinancialField(INCOME_STMT_LABELS["da"],               Action.GET_TTM_VALUE,      statement=Statement.INCOME),
        },
    )


def _make_cash_flow_mapper() -> GenericMapper:
    return GenericMapper(
        target_type=sm.CashFlow,
        fields={
            "operating_cf_ttm":     YfFinancialField(CASH_FLOW_LABELS["operating_cf"], Action.GET_TTM_VALUE,    statement=Statement.CASH_FLOW),
            "capex_ttm":            YfFinancialField(CASH_FLOW_LABELS["capex"],        Action.GET_TTM_VALUE,    statement=Statement.CASH_FLOW),
            "oper_cf_last_year":    YfFinancialField(CASH_FLOW_LABELS["operating_cf"], Action.GET_LATEST_VALUE, Period.ANNUAL,    statement=Statement.CASH_FLOW),
            "latest_annual_capex":  YfFinancialField(CASH_FLOW_LABELS["capex"],        Action.GET_LATEST_VALUE, Period.ANNUAL,    statement=Statement.CASH_FLOW),
            "oper_cf_last_quarter": YfFinancialField(CASH_FLOW_LABELS["operating_cf"], Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.CASH_FLOW),
            "latest_quarter_capex": YfFinancialField(CASH_FLOW_LABELS["capex"],        Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.CASH_FLOW),
            "dividends_paid_ttm":   YfFinancialField(CASH_FLOW_LABELS["dividends_paid"],  Action.GET_TTM_VALUE, statement=Statement.CASH_FLOW),
            "share_buybacks_ttm":   YfFinancialField(CASH_FLOW_LABELS["share_buybacks"],  Action.GET_TTM_VALUE, statement=Statement.CASH_FLOW),
        },
    )


def _make_balance_sheet_mapper() -> GenericMapper:
    return GenericMapper(
        target_type=sm.BalanceSheet,
        fields={
            "total_debt":           YfFinancialField(BALANCE_SHEET_LABELS["total_debt"],           Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_equity":         YfFinancialField(BALANCE_SHEET_LABELS["total_equity"],         Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "cash_and_equivalents": YfFinancialField(BALANCE_SHEET_LABELS["cash_and_equivalents"], Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_assets":         YfFinancialField(BALANCE_SHEET_LABELS["total_assets"],         Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_liabilities":    YfFinancialField(BALANCE_SHEET_LABELS["total_liabilities"],    Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "current_assets":       YfFinancialField(BALANCE_SHEET_LABELS["current_assets"],       Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "current_liabilities":  YfFinancialField(BALANCE_SHEET_LABELS["current_liabilities"],  Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "inventory":            YfFinancialField(BALANCE_SHEET_LABELS["inventory"],            Action.GET_LATEST_VALUE, Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
        },
    )


def _make_market_data_mapper() -> GenericMapper:
    return GenericMapper(
        target_type=sm.MarketData,
        fields={
            "current_price":       YfLabelField(INFO_LABELS["current_price"]),
            "shares_outstanding":  YfLabelField(INFO_LABELS["shares_outstanding"]),
            "market_cap":          YfLabelField(INFO_LABELS["market_cap"]),
            "beta":                YfLabelField(INFO_LABELS["beta"]),
            "eps_ttm":             YfLabelField(INFO_LABELS["eps_ttm"]),
            "pe_ttm":              YfLabelField(INFO_LABELS["pe_ttm"]),
            # last_quarter_eps and last_year_eps use sentinel keys that route
            # through YfinanceParser.last_quarter_eps() / last_year_eps()
            # rather than reading the same trailingEps value from ticker.info.
            "last_quarter_eps":    YfLabelField(INFO_LABELS["last_quarter_eps"]),
            "last_year_eps":       YfLabelField(INFO_LABELS["last_year_eps"]),
            "low_52_week":         YfLabelField(INFO_LABELS["low_52_week"]),
            "high_52_week":        YfLabelField(INFO_LABELS["high_52_week"]),
            "fifty_day_avg":       YfLabelField(INFO_LABELS["fifty_day_avg"]),
            "two_hundred_day_avg": YfLabelField(INFO_LABELS["two_hundred_day_avg"]),
            "volume":              YfLabelField(INFO_LABELS["volume"]),
            "avg_volume":          YfLabelField(INFO_LABELS["avg_volume"]),
        },
    )


def build_stock_metrics_mapper() -> StockMetricsMapper:
    mapper = StockMetricsMapper()
    mapper.register(sm.CompanyProfile, _make_company_profile_mapper())
    mapper.register(sm.Financials,     _make_financials_mapper())
    mapper.register(sm.CashFlow,       _make_cash_flow_mapper())
    mapper.register(sm.BalanceSheet,   _make_balance_sheet_mapper())
    mapper.register(sm.MarketData,     _make_market_data_mapper())
    return mapper


def FinancialsHistoryMapper() -> GenericMapper:
    return GenericMapper(
        target_type=FinancialsHistory,
        fields={
            "revenue_quarterly":          YfSeriesField(INCOME_STMT_LABELS["revenue"],          Period.QUARTERLY, statement=Statement.INCOME),
            "gross_profit_quarterly":     YfSeriesField(INCOME_STMT_LABELS["gross_profit"],     Period.QUARTERLY, statement=Statement.INCOME),
            "operating_income_quarterly": YfSeriesField(INCOME_STMT_LABELS["operating_income"], Period.QUARTERLY, statement=Statement.INCOME),
            "net_income_quarterly":       YfSeriesField(INCOME_STMT_LABELS["net_income"],       Period.QUARTERLY, statement=Statement.INCOME),
            "ebit_quarterly":             YfSeriesField(INCOME_STMT_LABELS["ebit"],             Period.QUARTERLY, statement=Statement.INCOME),
            "ebt_quarterly":              YfSeriesField(INCOME_STMT_LABELS["ebt"],              Period.QUARTERLY, statement=Statement.INCOME),
            "tax_expense_quarterly":      YfSeriesField(INCOME_STMT_LABELS["tax_expense"],      Period.QUARTERLY, statement=Statement.INCOME),
            "interest_expense_quarterly": YfSeriesField(INCOME_STMT_LABELS["interest_expense"], Period.QUARTERLY, statement=Statement.INCOME),
            "da_quarterly":               YfSeriesField(INCOME_STMT_LABELS["da"],               Period.QUARTERLY, statement=Statement.INCOME),
            "revenue_annual":             YfSeriesField(INCOME_STMT_LABELS["revenue"],          Period.ANNUAL,    statement=Statement.INCOME),
            "gross_profit_annual":        YfSeriesField(INCOME_STMT_LABELS["gross_profit"],     Period.ANNUAL,    statement=Statement.INCOME),
            "operating_income_annual":    YfSeriesField(INCOME_STMT_LABELS["operating_income"], Period.ANNUAL,    statement=Statement.INCOME),
            "net_income_annual":          YfSeriesField(INCOME_STMT_LABELS["net_income"],       Period.ANNUAL,    statement=Statement.INCOME),
            "ebit_annual":                YfSeriesField(INCOME_STMT_LABELS["ebit"],             Period.ANNUAL,    statement=Statement.INCOME),
            "ebt_annual":                 YfSeriesField(INCOME_STMT_LABELS["ebt"],              Period.ANNUAL,    statement=Statement.INCOME),
            "tax_expense_annual":         YfSeriesField(INCOME_STMT_LABELS["tax_expense"],      Period.ANNUAL,    statement=Statement.INCOME),
            "interest_expense_annual":    YfSeriesField(INCOME_STMT_LABELS["interest_expense"], Period.ANNUAL,    statement=Statement.INCOME),
        },
    )


def CashFlowHistoryMapper() -> GenericMapper:
    return GenericMapper(
        target_type=CashFlowHistory,
        fields={
            "operating_cf_quarterly":   YfSeriesField(CASH_FLOW_LABELS["operating_cf"],   Period.QUARTERLY, statement=Statement.CASH_FLOW),
            "capex_quarterly":          YfSeriesField(CASH_FLOW_LABELS["capex"],           Period.QUARTERLY, statement=Statement.CASH_FLOW),
            "dividends_paid_quarterly": YfSeriesField(CASH_FLOW_LABELS["dividends_paid"],  Period.QUARTERLY, statement=Statement.CASH_FLOW),
            "share_buybacks_quarterly": YfSeriesField(CASH_FLOW_LABELS["share_buybacks"],  Period.QUARTERLY, statement=Statement.CASH_FLOW),
            "operating_cf_annual":      YfSeriesField(CASH_FLOW_LABELS["operating_cf"],   Period.ANNUAL,    statement=Statement.CASH_FLOW),
            "capex_annual":             YfSeriesField(CASH_FLOW_LABELS["capex"],           Period.ANNUAL,    statement=Statement.CASH_FLOW),
            "dividends_paid_annual":    YfSeriesField(CASH_FLOW_LABELS["dividends_paid"],  Period.ANNUAL,    statement=Statement.CASH_FLOW),
            "share_buybacks_annual":    YfSeriesField(CASH_FLOW_LABELS["share_buybacks"],  Period.ANNUAL,    statement=Statement.CASH_FLOW),
        },
    )


def BalanceSheetHistoryMapper() -> GenericMapper:
    return GenericMapper(
        target_type=BalanceSheetHistory,
        fields={
            "total_debt_quarterly":          YfSeriesField(BALANCE_SHEET_LABELS["total_debt"],           Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_equity_quarterly":        YfSeriesField(BALANCE_SHEET_LABELS["total_equity"],         Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "cash_quarterly":                YfSeriesField(BALANCE_SHEET_LABELS["cash_and_equivalents"], Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_assets_quarterly":        YfSeriesField(BALANCE_SHEET_LABELS["total_assets"],         Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_liabilities_quarterly":   YfSeriesField(BALANCE_SHEET_LABELS["total_liabilities"],    Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "current_assets_quarterly":      YfSeriesField(BALANCE_SHEET_LABELS["current_assets"],       Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "current_liabilities_quarterly": YfSeriesField(BALANCE_SHEET_LABELS["current_liabilities"],  Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "inventory_quarterly":           YfSeriesField(BALANCE_SHEET_LABELS["inventory"],            Period.QUARTERLY, statement=Statement.BALANCE_SHEET),
            "total_debt_annual":             YfSeriesField(BALANCE_SHEET_LABELS["total_debt"],           Period.ANNUAL,    statement=Statement.BALANCE_SHEET),
            "total_equity_annual":           YfSeriesField(BALANCE_SHEET_LABELS["total_equity"],         Period.ANNUAL,    statement=Statement.BALANCE_SHEET),
            "cash_annual":                   YfSeriesField(BALANCE_SHEET_LABELS["cash_and_equivalents"], Period.ANNUAL,    statement=Statement.BALANCE_SHEET),
            "total_assets_annual":           YfSeriesField(BALANCE_SHEET_LABELS["total_assets"],         Period.ANNUAL,    statement=Statement.BALANCE_SHEET),
        },
    )