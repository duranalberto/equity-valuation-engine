"""
cli/presenters/summary_presenter.py

DESIGN-D: Prints the consolidated ValuationSummaryReport as a compact table.

Output format:
  ╒═══════╤═══════════╤══════════╤══════════╤══════════╤════════════╤══════════╕
  │ Model │ Bear IV   │ Base IV  │ Bull IV  │ Status   │ Upside     │ Source   │
  ╞═══════╪═══════════╪══════════╪══════════╪════════════════════════╪══════════╡
  │ DCF   │ $101.08   │ $223.03  │ $551.10  │ base→...  │ +34.4%    │ normalised│
  │ P/E   │ $178.30   │ $366.91  │ $893.29  │ underval  │ +121.1%   │          │
  │ ROE   │  $74.62   │ $152.84  │ $384.75  │ reasonable│  -7.9%    │ capped   │
  ╘═══════╧═══════════╧══════════╧══════════╧════════════╧═══════════╧══════════╛
  Composite (Base):  $247.59  |  Model Agreement: 0.38 (moderate)
  Confidence Band:   $131.93 – $363.26  |  Implied Upside: +49.2%
"""
from __future__ import annotations

from typing import Optional

from domain.valuation.models.summary import ValuationSummaryReport

try:
    from tabulate import tabulate
    _HAS_TABULATE = True
except ImportError:
    _HAS_TABULATE = False


def _fmt_iv(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"${v:>8,.2f}"


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1%}"


def _status_label(status: str) -> str:
    """Abbreviate valuation_status for compact display."""
    if "undervalued" in status:
        return "undervalued"
    if "overvalued" in status:
        return "overvalued"
    return "reasonable"


def cli_print_summary(report: ValuationSummaryReport, current_price: float) -> None:
    """
    Print the consolidated valuation summary table to stdout.

    This is called by cli/main.py after all managers complete, using the
    same current_price already available in StockMetrics.market_data.
    """
    print(f"\n{'='*70}")
    print(f"  VALUATION SUMMARY — {report.ticker}   (current price: ${current_price:,.2f})")
    print(f"{'='*70}")

    # Build per-model rows: collect Bear / Base / Bull for each model
    model_names = list(dict.fromkeys(r.model_name for r in report.rows))  # preserve order

    table_rows = []
    for model in model_names:
        model_rows = {r.scenario: r for r in report.rows if r.model_name == model}
        bear_iv    = model_rows.get("Bear")
        base_iv    = model_rows.get("Base")
        bull_iv    = model_rows.get("Bull")

        base_status = _status_label(base_iv.valuation_status) if base_iv else "—"
        base_upside = _fmt_pct(base_iv.implied_upside)        if base_iv else "—"

        table_rows.append([
            model,
            _fmt_iv(bear_iv.intrinsic_value if bear_iv else None),
            _fmt_iv(base_iv.intrinsic_value if base_iv else None),
            _fmt_iv(bull_iv.intrinsic_value if bull_iv else None),
            base_status,
            base_upside,
        ])

    headers = ["Model", "Bear IV", "Base IV", "Bull IV", "Status (Base)", "Upside (Base)"]

    if _HAS_TABULATE:
        print(tabulate(table_rows, headers=headers, tablefmt="fancy_grid",
                       colalign=("left", "right", "right", "right", "left", "right")))
    else:
        # Fallback plain formatting
        col_w = [14, 12, 12, 12, 14, 13]
        hdr = "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
        sep = "  ".join("-" * w for w in col_w)
        print(hdr)
        print(sep)
        for row in table_rows:
            print("  ".join(str(c).ljust(w) for c, w in zip(row, col_w)))

    # Composite metrics line
    print()
    if report.composite_intrinsic is not None:
        comp_str   = f"${report.composite_intrinsic:,.2f}"
        upside_str = _fmt_pct(report.implied_upside)
        print(f"  Composite Base IV:  {comp_str}   |   Implied Upside: {upside_str}")
    else:
        print("  Composite Base IV:  N/A")

    if report.model_agreement_score is not None:
        score = report.model_agreement_score
        label = "high" if score > 0.40 else "moderate" if score > 0.20 else "strong"
        print(f"  Model Agreement:    {score:.2f} ({label})", end="")
        if report.confidence_band:
            lo, hi = report.confidence_band
            print(f"   |   Band: ${lo:,.2f} – ${hi:,.2f}", end="")
        print()

    if report.models_skipped:
        print(f"  Skipped models:     {', '.join(report.models_skipped)}")

    print(f"\n  {report.note}")
    print(f"{'='*70}\n")