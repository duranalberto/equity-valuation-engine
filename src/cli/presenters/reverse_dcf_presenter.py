from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.reverse_dcf import ReverseDCFReport

from .utils import fmt_num, fmt_pct


def cli_print_valuation(metrics: StockMetrics, report: ReverseDCFReport) -> None:
    ticker = metrics.profile.ticker
    result = getattr(report, "result", None)
    if result is None:
        print(f"ERROR: ReverseDCFReport for {ticker} contains no result.")
        return

    print(f"====================== Reverse DCF Diagnostics for {ticker} ======================\n")
    print(tabulate(
        [
            ["Current Stock Price", fmt_num(report.current_price)],
            ["Forward Growth Rate", fmt_pct(metrics.valuation.forward_growth_rate)],
            ["Implied Growth Rate", fmt_pct(result.implied_growth_rate)],
            ["Delta vs Forward Growth", fmt_pct(result.implied_vs_forward_delta)],
            ["WACC", fmt_pct(result.wacc)],
            ["Terminal Growth Rate", fmt_pct(result.terminal_growth_rate)],
            ["FCF Seed", fmt_num(result.fcf_seed)],
            ["FCF Seed Source", result.fcf_seed_source],
            ["Verification IV", fmt_num(result.verification_iv)],
            ["Verification Error", fmt_pct(result.verification_error_pct)],
        ],
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
    ))
    print()
    print(f"Interpretation: {result.interpretation}")
    print()
