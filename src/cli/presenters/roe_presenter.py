from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.roe import ROEValuationReport, ROEValuationResult

from .utils import colors, fmt_num, fmt_pct


def build_summary_metrics_table(metrics: StockMetrics):
    current_price  = metrics.market_data.current_price
    bvs            = getattr(getattr(metrics, "ratios", None), "book_value_per_share", None)
    roe            = getattr(getattr(metrics, "ratios", None), "return_on_equity", None)
    dividend_yield = getattr(getattr(metrics, "ratios", None), "dividend_yield", None)
    buyback_yield  = getattr(getattr(metrics, "ratios", None), "buyback_yield", None)
    return [
        ["Current Stock Price",          fmt_num(current_price)],
        ["Book Value per Share (BVS)",    fmt_num(bvs)            if bvs            is not None else "-"],
        ["Return on Equity (ROE) (TTM)",  fmt_pct(roe)            if roe            is not None else "-"],
        ["Current Dividend Yield",        fmt_pct(dividend_yield) if dividend_yield is not None else "-"],
        ["Current Buyback Yield",         fmt_pct(buyback_yield)  if buyback_yield  is not None else "-"],
    ]


def build_scenario_summary_table(report: ROEValuationReport):
    summary_table = []
    for scenario_name, r in report.scenarios.items():
        status = r.valuation_status
        if "undervalued" in status:
            status_colored = f"{colors.GREEN.value}{status}{colors.RESET.value}"
        elif "overvalued" in status:
            status_colored = f"{colors.RED.value}{status}{colors.RESET.value}"
        else:
            status_colored = status

        # BUG-B / BUG-C: annotate intrinsic value with flags where applicable.
        iv_str = fmt_num(r.intrinsic_value)
        if r.buyback_substituted:
            iv_str += " [B]"   # buyback yield used as distribution
        if r.roe_was_capped:
            roe_str = fmt_pct(r.roe_applied) + " (capped)"
        else:
            roe_str = fmt_pct(r.roe_applied) if r.roe_applied is not None else "-"

        summary_table.append([
            scenario_name,
            iv_str,
            fmt_num(r.npv_dividends),
            fmt_num(r.npv_required_value),
            roe_str,
            status_colored,
        ])
    return summary_table


def cli_print_valuation(metrics: StockMetrics, report: ROEValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: ROEValuationReport for {ticker} contains no scenarios.")
        return

    first_result: ROEValuationResult = next(iter(report.scenarios.values()))
    if not first_result.dividend_progression:
        print(f"ERROR: ROEValuationResult for {ticker} contains no dividend progressions.")
        return

    proj_len     = len(first_result.dividend_progression)
    year_headers = [f"Year {i + 1}" for i in range(proj_len)]

    # Determine annotation notes to print after the tables.
    notes = []
    if first_result.buyback_substituted:
        notes.append(
            "[B] Intrinsic value uses share buyback yield as the distribution component "
            "because dividends_paid_ttm = $0.  This aligns with total shareholder return."
        )
    if first_result.roe_was_capped:
        notes.append(
            f"ROE capped at {fmt_pct(report.params.roe_cap)} (sector ceiling) to prevent "
            f"leverage-inflated ROE from compounding unconstrained over the projection window.  "
            f"Raw ROE = {fmt_pct(metrics.ratios.return_on_equity if metrics.ratios else None)}."
        )

    print(f"======================== ROE Valuation Comparison for {ticker} ========================\n")
    print(tabulate(
        build_summary_metrics_table(metrics),
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
        colalign=("left", "left"),
    ))

    if notes:
        print()
        for note in notes:
            print(f"  NOTE: {note}")

    print()
    print("\n-- Scenario Valuation Summary --")
    print(tabulate(
        build_scenario_summary_table(report),
        headers=["Scenario", "Intrinsic Value", "Total NPV Distributions", "NPV Terminal Value", "ROE Applied", "Status"],
        tablefmt="fancy_grid",
        colalign=("left", "decimal", "decimal", "decimal", "left", "left"),
    ))
    print()
    print("\n-- 1. Shareholders' Equity Progression (Per Share) --")
    print(tabulate(
        [[sn] + [fmt_num(v) for v in r.shareholders_equity_progression]
         for sn, r in report.scenarios.items()],
        headers=["Scenario"] + year_headers,
        tablefmt="fancy_grid",
    ))
    print()
    print("\n-- 2. Distribution Progression (Per Share) --")
    dist_label = "Buyback-Substituted Distribution" if first_result.buyback_substituted else "Dividend"
    print(f"   ({dist_label})")
    print(tabulate(
        [[sn] + [fmt_num(v) for v in r.dividend_progression]
         for sn, r in report.scenarios.items()],
        headers=["Scenario"] + year_headers,
        tablefmt="fancy_grid",
    ))
    print()
    print("\n-- 3. NPV Distribution Progression (Per Share) --")
    print(tabulate(
        [[sn] + [fmt_num(v) for v in r.npv_dividend_progression]
         for sn, r in report.scenarios.items()],
        headers=["Scenario"] + year_headers,
        tablefmt="fancy_grid",
    ))
    print()