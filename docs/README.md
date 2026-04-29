# Equity Valuation Engine Documentation

This project loads equity data, builds normalized financial metrics, runs model
suitability checks, and produces intrinsic valuation reports in human-readable
tables or machine-readable JSON.

## Installation

Runtime install:

```bash
python -m pip install -e .
```

Install with test tooling:

```bash
python -m pip install -e ".[test]"
```

## CLI Usage

Run the CLI as a module:

```bash
python -m cli.main ORCL --json
python -m cli.main ORCL --cli
python -m cli.main ORCL --all
python -m cli.main ORCL --json --reverse-dcf
```

Output modes:

- `--json` prints one compact JSON object on stdout.
- `--cli` prints human-readable valuation tables and the consolidated summary.
- `--all` prints CLI tables first, then a final labeled JSON document.
- `--reverse-dcf` adds Reverse DCF implied-growth diagnostics to the run.

## Architecture

- **Metrics loading** fetches yfinance data and maps it into `StockMetrics`.
- **Missing-data registry** records unavailable source and derived fields.
- **Valuation managers** coordinate suitability checks and scenario execution.
- **Suitability checks** block models with invalid inputs and surface warnings.
- **Presenters** render compact CLI tables for each supported model.
- **JSON formatter** serializes metrics, suitability, valuations, skipped models,
  missing-data records, and the consolidated summary.

## Valuation Models

- **DCF** projects free cash flow, discounts by WACC, and computes terminal value.
- **P/E** projects EPS and applies a historical or target earnings multiple.
- **ROE** projects earnings from return on equity and shareholder distributions.
- **EV/EBITDA** applies sector EV/EBITDA multiples to EBITDA, then bridges to equity.
- **P/S** applies sector price-to-sales multiples to revenue.
- **DDM** discounts projected dividends and a terminal dividend value.
- **NAV** applies scenario haircuts to assets and subtracts liabilities.
- **Reverse DCF** back-solves the growth rate implied by the current market price.

Reverse DCF is diagnostic and opt-in; it does not contribute to the composite
intrinsic value.

## Configuration

Model assumptions live under `src/config/valuations/`:

- Sector multiples: `multiples.yaml`
- NAV asset haircuts and intangible thresholds: `nav.yaml`
- DCF, P/E, and ROE defaults: `dcf.yaml`, `pe.yaml`, `roe.yaml`
- Scenario growth assumptions: `scenarios.yaml`

Review these files periodically when market regimes, sector multiples, or
capital-market assumptions change.

## Known Limitations

- Live runs depend on yfinance availability and data quality.
- Sector multiples and haircuts are static configuration assumptions.
- Suitability warnings help flag weak inputs, but they are not exhaustive risk checks.
- Valuation output is analytical tooling, not investment advice.
