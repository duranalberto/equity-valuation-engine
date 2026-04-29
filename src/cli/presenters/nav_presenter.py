from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.nav import NAVValuationReport

from .utils import colors, fmt_num, fmt_pct


def _status_colored(status: str) -> str:
    if "undervalued" in status:
        return f"{colors.GREEN.value}{status}{colors.RESET.value}"
    if "overvalued" in status:
        return f"{colors.RED.value}{status}{colors.RESET.value}"
    return status


def cli_print_valuation(metrics: StockMetrics, report: NAVValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: NAVValuationReport for {ticker} contains no scenarios.")
        return

    print(f"======================== NAV Valuation for {ticker} ========================\n")
    print(tabulate(
        [
            ["Current Stock Price", fmt_num(metrics.market_data.current_price)],
            ["Total Assets", fmt_num(report.total_assets)],
            ["Total Liabilities", fmt_num(report.total_liabilities)],
            ["Total Equity", fmt_num(report.total_equity)],
            ["Goodwill + Intangibles", fmt_num(report.goodwill_and_intangibles)],
            ["Intangible Asset Ratio", fmt_pct(report.intangible_asset_ratio)],
            ["Intangible Warning Cap", fmt_pct(report.intangible_cap)],
        ],
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
    ))
    print()

    rows = []
    for scenario_name, r in report.scenarios.items():
        rows.append([
            scenario_name,
            fmt_pct(r.asset_haircut_used),
            fmt_num(r.adjusted_assets),
            fmt_num(r.nav),
            fmt_num(r.nav_per_share),
            fmt_num(r.price_to_nav),
            fmt_pct(r.intangible_asset_ratio),
            "Yes" if r.intangible_warning else "No",
            _status_colored(r.valuation_status),
        ])

    print(tabulate(
        rows,
        headers=[
            "Scenario",
            "Asset Haircut",
            "Adjusted Assets",
            "NAV",
            "NAV/Share",
            "Price/NAV",
            "Intangible %",
            "Intangible Warning",
            "Status",
        ],
        tablefmt="fancy_grid",
    ))
    print()
