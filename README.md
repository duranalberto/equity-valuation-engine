# Equity Valuation Engine

A Python equity valuation engine that fetches market and financial statement
data, builds normalized stock metrics, runs valuation suitability checks, and
produces intrinsic valuation reports.

## Supported Models

- DCF
- P/E
- ROE
- EV/EBITDA
- P/S
- DDM
- NAV
- Reverse DCF diagnostics

Reverse DCF is opt-in and diagnostic; it is included in JSON output when
requested but excluded from the composite intrinsic value.

## Installation

To install for development:

```bash
python -m pip install -e .
```

To install test tooling:

```bash
python -m pip install -e ".[test]"
```

### Import as a package from GitHub

You can install this engine directly into other projects without publishing it to PyPI. Use:

```bash
pip install git+https://github.com/duranalberto/equity-valuation-engine.git
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

- `--json` emits one parseable JSON object.
- `--cli` emits human-readable tables.
- `--all` emits CLI tables followed by one final JSON document.

## Project Shape

The engine is organized around:

- yfinance-backed data loading
- `StockMetrics` domain models
- missing-data diagnostics
- valuation managers and validators
- CLI presenters and JSON serialization
- sector and scenario assumptions in `src/config/valuations/`

See [docs/README.md](docs/README.md) for architecture notes, model summaries,
configuration guidance, and limitations.

## Testing

```bash
pytest -q
```

Valuation outputs are analytical estimates based on available data and
configuration assumptions. They are not investment advice.
