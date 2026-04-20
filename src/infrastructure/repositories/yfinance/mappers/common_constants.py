from __future__ import annotations

INFO_LABELS = {
    "ticker":             "symbol",
    "company_name":       "longName",
    "sector":             "sector",
    "industry":           "industry",
    "country":            "country",
    "financial_currency": "financialCurrency",
    "trading_currency":   "currency",
    "exchange":           "exchange",
    "quote_type":         "quoteType",
    "website":            "website",
    "current_price":      "currentPrice",
    "shares_outstanding": "sharesOutstanding",
    "market_cap":         "marketCap",
    "beta":               "beta",
    "eps_ttm":            "trailingEps",
    "pe_ttm":             "trailingPE",
    "low_52_week":        "fiftyTwoWeekLow",
    "high_52_week":       "fiftyTwoWeekHigh",
    "fifty_day_avg":      "fiftyDayAverage",
    "two_hundred_day_avg":"twoHundredDayAverage",
    "volume":             "volume",
    "avg_volume":         "averageVolume",
}


INCOME_STMT_LABELS = {
    "revenue": [
        "Total Revenue", "Revenue", "Net Revenue",
        "Sales", "Net Sales", "Operating Revenue",
    ],
    "gross_profit": [
        "Gross Profit",
    ],
    "operating_income": [
        "Operating Income", "Operating Profit",
        "EBIT",
        "Income From Operations",
    ],
    "net_income": [
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income Applicable To Common Shares",
    ],
    "ebit": [
        "EBIT",
        "Operating Income",
        "Operating Profit",
    ],
    "ebt": [
        "Pretax Income",
        "Income Before Tax",
        "Earnings Before Tax",
    ],
    "tax_expense": [
        "Tax Provision",
        "Income Tax Expense",
        "Provision For Income Taxes",
    ],
    "interest_expense": [
        "Interest Expense",
        "Interest Expense Non Operating",
        "Net Interest Income",
    ],
    "da": [
        "Reconciled Depreciation",
        "Depreciation And Amortization",
        "Depreciation",
        "Amortization",
    ],
}


BALANCE_SHEET_LABELS = {
    "total_debt": [
        "Total Debt",
        "Long Term Debt And Capital Lease Obligation",
        "Long Term Debt",
        "Current Debt And Capital Lease Obligation",
    ],
    "total_equity": [
        "Stockholders Equity",
        "Common Stock Equity",
        "Total Equity Gross Minority Interest",
    ],
    "cash_and_equivalents": [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash And Short Term Investments",
    ],
    "total_assets": [
        "Total Assets",
    ],
    "total_liabilities": [
        "Total Liabilities Net Minority Interest",
        "Total Liabilities",
    ],
    "current_assets": [
        "Current Assets",
        "Total Current Assets",
    ],
    "current_liabilities": [
        "Current Liabilities",
        "Total Current Liabilities Net Minority Interest",
        "Total Current Liabilities",
    ],
    "inventory": [
        "Inventory",
        "Inventories",
    ],
}


CASH_FLOW_LABELS = {
    "operating_cf": [
        "Operating Cash Flow",
        "Cash From Operations",
        "Net Cash Provided By Operating Activities",
        "Cash Flows From Used In Operating Activities",
    ],
    "capex": [
        "Capital Expenditure",
        "Capital Expenditures",
        "Purchase Of Property Plant And Equipment",
        "Purchases Of Property Plant And Equipment",
    ],
    "dividends_paid": [
        "Common Stock Dividend Paid",
        "Cash Dividends Paid",
        "Payment Of Dividends",
        "Dividends Paid",
    ],
    "share_buybacks": [
        "Repurchase Of Capital Stock",
        "Common Stock Repurchase",
        "Repurchase Of Common Stock",
        "Purchase Of Treasury Shares",
    ],
}
