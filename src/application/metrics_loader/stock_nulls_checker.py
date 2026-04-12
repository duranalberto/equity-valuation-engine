from typing import Optional
from domain.metrics.stock import StockMetrics


def evaluate_nulls(stock: StockMetrics) -> None:
    """
    Logs informative explanations for null or missing values in StockMetrics.

    Now that Ratios fields default to None instead of 0.0 (fix 5.2), these
    checks correctly distinguish "not computed" from "computed as zero".
    """
    f = stock.financials
    cf = stock.cash_flow
    bs = stock.balance_sheet
    md = stock.market_data
    val = stock.valuation
    r = stock.ratios

    print("--- Financials & Growth Checks ---")
    if f.revenue_ttm_prev is None:
        print("Revenue (TTM Prev) is null: Cannot calculate Revenue Growth Rate.")
    if f.net_income_ttm_prev is None:
        print("Net Income (TTM Prev) is null: Cannot calculate Net Income Growth.")
    if f.interest_expense_ttm is None:
        print("Interest Expense (TTM) is null: Cannot calculate Interest Coverage/Cost of Debt.")
    if f.gross_margin is None:
        print("Gross Margin is null: gross profit or revenue missing.")
    if f.operating_margin is None:
        print("Operating Margin is null: operating income or revenue missing.")
    if f.net_margin is None:
        print("Net Margin is null: net income or revenue missing.")
    if f.ebitda_ttm is None:
        print("EBITDA (TTM) is null: EBIT or D&A missing. EV/EBITDA will be null.")

    print("\n--- Cash Flow Checks ---")
    if cf.dividends_paid_ttm is None:
        print("Dividends Paid is null: company may not pay dividends.")
    if cf.fcf_ttm is None:
        print("FCF (TTM) is null: Operating CF or Capex missing.")
    if cf.last_year_fcf is None:
        print("Last Year FCF is null: Cannot calculate FCF CAGR.")

    print("\n--- Balance Sheet Checks ---")
    if bs.inventory is None:
        print("Inventory is null: Quick Ratio may be null.")
    if bs.total_debt is None:
        print("Total Debt is null: Debt-related ratios will be null.")
    if bs.current_ratio is None:
        print("Current Ratio is null: current assets/liabilities missing.")
    if bs.quick_ratio is None:
        print("Quick Ratio is null: inventory or current assets/liabilities missing.")

    print("\n--- Market Data & Valuation Checks ---")
    if md.pe_ttm is None:
        print("P/E TTM is null: EPS negative or data missing.")
    if md.shares_outstanding is None or md.shares_outstanding <= 0:
        print("Shares Outstanding is missing/zero: Cannot calculate ratios per share.")
    if val.cost_of_debt is None:
        print("Cost of debt is null: company may not have interest expense or total debt.")
    if val.corporate_tax_rate is None:
        print("Corporate tax rate is null: EBT or Tax Expense missing.")
    if val.price_to_sales is None:
        print("Price to Sales is null: Market Cap or Revenue missing.")
    if val.enterprise_value is None:
        print("Enterprise Value is null: Market Cap, Total Debt, or Cash missing.")

    print("\n--- Ratios Checks ---")
    if r is None:
        print("Ratios object is null: ratios may not have been calculated yet.")
        return

    if r.peg_ratio is None:
        print("PEG Ratio is null: PE missing or Net Income Growth negative/zero.")
    if r.dividend_yield is None:
        print("Dividend Yield is null: dividends not paid or current price missing.")
    if r.payout_ratio is None:
        print("Payout Ratio is null: dividends not paid or Net Income negative.")
    if r.interest_coverage is None:
        print("Interest Coverage is null: EBIT or Interest Expense missing.")
    if r.roic is None:
        print("ROIC is null: EBIT, Total Debt/Equity, or Tax Rate missing.")
    if r.ev_ebit is None:
        print("EV/EBIT is null: Enterprise Value or EBIT missing/zero.")
    if r.ev_ebitda is None:
        print("EV/EBITDA is null: Enterprise Value or EBITDA missing/zero.")
    if r.price_to_fcf is None:
        print("Price to FCF is null: Market Cap or FCF missing/zero.")
    if r.fcf_yield is None:
        print("FCF Yield is null: FCF or Market Cap missing/zero.")