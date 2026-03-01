# Finance Project Overview

This project provides a modular toolkit for extracting financial data, computing derived financial metrics, and generating several forms of equity valuation. Its core objective is to obtain raw financial information from external providers, transform it into standardized financial metrics, and apply valuation methodologies such as DCF, ROE-driven intrinsic value, and PE-based fair price estimations.

Each valuation relies on a shared data access interface and a common set of calculated metrics, ensuring consistency and enabling multiple valuation models to coexist and evolve.

## Financial Data Extraction

The project retrieves financial data through a repository abstraction that returns primitive financial values such as revenue figures, EPS history, cash flow values, and price history. Each repository implementation adheres to a common protocol, allowing the rest of the system to operate independently of the external data source.

### How Metrics Extraction Works

Metrics extraction follows a consistent pattern:

1. The repository delivers raw financial primitives.
2. Metric loaders access these values and assemble higher-level representations such as:

   * Trailing twelve months results (TTM)
   * Annual values for revenue, EPS, cash flows, and margins
   * Historical price sequences
   * Dividend information
3. These extracted fields are then processed by calculators to generate derived metrics used by valuation engines.

This approach ensures a clean separation between raw data retrieval and the financial logic applied to it.

## Computed Data and Derived Metrics

The project includes a set of financial calculation modules responsible for producing metrics required by valuation models. These calculations operate only on primitives returned by the repository and include:

* Growth rate calculations for revenue, EPS, or cash flows
* Discounting operations for DCF valuation
* Profitability metrics such as margins and return on equity
* Cost of capital and WACC computations
* Dividend-related ratios

The calculated metrics become the foundation for all valuations, ensuring that each valuation engine receives consistent, domain-relevant inputs.

## Valuation Models

The project currently supports several valuation approaches, each with its own parameterization, calculation workflow, and interpretation of the extracted metrics.

### Discounted Cash Flow (DCF)

The DCF valuation estimates intrinsic value by forecasting future free cash flows, discounting them by the appropriate cost of capital, and computing a terminal value. The process includes:

* Extracting and computing cash flow history and growth
* Estimating future cash flows based on provided assumptions
* Discounting projected flows
* Summing discounted flows and terminal value

### Return on Equity (ROE) Based Valuation

The ROE valuation builds on profitability metrics to project future earnings and potential reinvestment outcomes. It evaluates a stock's intrinsic price based on:

* Historical and computed ROE values
* Growth expectations derived from reinvestment and profitability
* Discounted future earnings trajectories

### Price-Earnings (PE) Valuation

The PE-based model estimates a fair price by comparing the stock's EPS and growth projections to expected valuation multiples. It relies on:

* Recent EPS and EPS history
* Calculated forward-looking EPS estimates based on growth
* A target PE ratio for the valuation horizon

## yfinance-Based Repository Implementation

One repository implementation uses the `yfinance` library to extract financial statements, cash flow data, price history, and other quantitative indicators directly from Yahoo Finance. The implementation transforms `yfinance` response objects and DataFrames into the primitives defined by the repository protocol.

The project intentionally isolates this implementation within its own module so that:

* The core codebase does not depend on `yfinance` specifics
* Additional data providers can be added later without modifying valuation or calculation logic

## CLI Usage and Input Data

The command-line interface provides a simple mechanism for running valuations and extracting metrics for a single stock. The CLI accepts inputs such as:

* A stock ticker symbol
* Valuation-specific parameter overrides
* Output format preferences (e.g., JSON or formatted output)

Typical CLI flow:

1. User specifies ticker and valuation method.
2. The CLI initializes the appropriate repository.
3. The CLI constructs the selected valuation engine and its parameters.
4. Valuation results or metric summaries are displayed.

The CLI is built to enable straightforward interaction while maintaining flexibility for future expansions, including batch stock valuation or comparative analysis.
