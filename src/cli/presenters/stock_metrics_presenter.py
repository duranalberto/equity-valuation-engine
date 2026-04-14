from tabulate import tabulate
from domain.metrics.stock import StockMetrics
from .utils import fmt_num, fmt_pct


def print_tabulated_metrics(stock: StockMetrics):
    print("\n====================== Company Overview ======================\n")

    md = stock.market_data
    profile = stock.profile
    fin = stock.financials
    cf = stock.cash_flow
    bs = stock.balance_sheet
    val = stock.valuation
    ratios = stock.ratios

    if not ratios:
        print("ERROR: Ratios object is missing. Cannot print detailed metrics.")
        return

    print(tabulate([
        ["Ticker", profile.ticker],
        ["Company Name", profile.company_name or "-"],
        ["Sector", profile.sector or "-"],
        ["Industry", profile.industry or "-"],
        ["Country", profile.country or "-"],
        ["Exchange", profile.exchange or "-"],
        ["Current Price", fmt_num(md.current_price)],
        ["Shares Outstanding", fmt_num(md.shares_outstanding)],
        ["Market Cap", fmt_num(md.market_cap)],
        ["Beta (5Y Monthly)", fmt_num(md.beta)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))

    print("\n-- Earnings & Price Multiples --")
    print(tabulate([
        ["EPS (TTM)", fmt_num(md.eps_ttm)],
        ["P/E Ratio (TTM)", fmt_num(md.pe_ttm)],
        ["EPS (Last Quarter)", fmt_num(md.last_quarter_eps)],
        ["EPS (Last Fiscal Year)", fmt_num(md.last_year_eps)],
        ["Price-to-Sales", fmt_num(val.price_to_sales)],
        ["Price-to-Book", fmt_num(val.price_to_book)],
        ["Median Historical P/E", fmt_num(val.median_historical_pe)],
        ["Forward Growth Rate", fmt_pct(val.forward_growth_rate)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))

    print("\n-- Enterprise Value Multiples --")
    print(tabulate([
        ["EV / Revenue (TTM)", fmt_num(val.enterprise_value / fin.revenue_ttm)],
        ["EV / EBIT", fmt_num(ratios.ev_ebit)],
        ["EV / EBITDA", fmt_num(ratios.ev_ebitda)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))

    print("\n-- Free Cash Flow & Shareholders --")
    print(tabulate([
        ["FCF (TTM)", fmt_num(cf.fcf_ttm)],
        ["FCF (Last Fiscal Year)", fmt_num(cf.last_year_fcf)],
        ["FCF (Last Quarter)", fmt_num(cf.last_quarter_fcf)],
        ["Price / FCF", fmt_num(ratios.price_to_fcf)],
        ["FCF Yield", fmt_pct(ratios.fcf_yield)],
        ["Dividends Paid (TTM)", fmt_num(cf.dividends_paid_ttm)],
        ["Share Buybacks (TTM)", fmt_num(cf.share_buybacks_ttm)],
        ["Dividend Yield", fmt_pct(ratios.dividend_yield)],
        ["Payout Ratio", fmt_pct(ratios.payout_ratio)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))

    print("\n-- Debt, Cash & Tax --")
    print(tabulate([
        ["Total Debt", fmt_num(bs.total_debt)],
        ["Cash & Equivalents", fmt_num(bs.cash_and_equivalents)],
        ["Net Debt", fmt_num((bs.total_debt or 0) - (bs.cash_and_equivalents or 0))],
        ["Enterprise Value (EV)", fmt_num(val.enterprise_value)],
        ["Interest Coverage", fmt_num(ratios.interest_coverage)],
        ["Debt to Equity", fmt_num(ratios.debt_to_equity)],
        ["Corporate Tax Rate", fmt_pct(val.corporate_tax_rate)],
        ["Cost of Debt (Rd)", fmt_pct(val.cost_of_debt)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))

    print("\n-- Revenue & Profitability --")
    print(tabulate([
        ["Revenue (TTM)", fmt_num(fin.revenue_ttm)],
        ["Revenue Growth (TTM)", fmt_pct(fin.revenue_growth_rate)],
        ["Net Income Growth (TTM)", fmt_pct(fin.net_income_growth)],
        ["Gross Margin", fmt_pct(fin.gross_margin)],
        ["Operating Margin", fmt_pct(fin.operating_margin)],
        ["Net Margin", fmt_pct(fin.net_margin)],
        ["EBIT Margin", fmt_pct(ratios.ebit_margin)],
        ["FCF Margin", fmt_pct(ratios.fcf_margin)],
        ["PEG Ratio", fmt_num(ratios.peg_ratio)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))

    print("\n-- Return Ratios --")
    print(tabulate([
        ["ROIC", fmt_pct(ratios.roic)],
        ["ROE", fmt_pct(ratios.return_on_equity)],
        ["ROA", fmt_pct(ratios.return_on_assets)],
    ], headers=["Metric", "Value"], tablefmt="fancy_grid"))
