from __future__ import annotations

import logging
from enum import Enum
from typing import List, Optional, Type, TypeVar, Union, cast

import domain.metrics.stock as sm
from domain.core.missing import MissingReason
from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.history import (
    BalanceSheetHistory,
    CashFlowHistory,
    FinancialsHistory,
)
from infrastructure.mappers.base_mapper import GenericMapper
from infrastructure.repositories import YfinanceDataLoader
from infrastructure.repositories.financial_repository import (
    Action,
    BaseField,
    EnumField,
    FinancialField,
    FinancialRepository,
    LabelField,
    Period,
)
from infrastructure.repositories.yfinance.mappers import (
    BalanceSheetHistoryMapper,
    CashFlowHistoryMapper,
    FinancialsHistoryMapper,
    YfSeriesField,
)

logger = logging.getLogger(__name__)
ModelT   = TypeVar("ModelT")
HistoryT = TypeVar("HistoryT")


class MetricsLoader:
    HISTORY_MAPPERS: dict = {
        FinancialsHistory:   FinancialsHistoryMapper,
        CashFlowHistory:     CashFlowHistoryMapper,
        BalanceSheetHistory: BalanceSheetHistoryMapper,
    }

    def __init__(
        self,
        ticker_symbol: str,
        loader_cls: Type = YfinanceDataLoader,
        registry: Optional[MissingValueRegistry] = None,
    ) -> None:
        """
        Parameters
        ----------
        ticker_symbol : str
            The ticker to load data for.
        loader_cls : Type
            Data-loader class that implements ``FinancialRepository``.
        registry : MissingValueRegistry, optional
            When provided, all source-level and derived-level misses are
            recorded here during ``build_stock_metrics()``.  Callers that do
            not need diagnostics can omit this parameter.
        """
        loader_instance = loader_cls(ticker_symbol)
        if not isinstance(loader_instance, FinancialRepository):
            raise TypeError(
                f"{loader_cls.__name__} does not implement the "
                "FinancialRepository protocol.  Ensure it defines: "
                "get_label, get_ttm_from_quarters, get_annual_value, "
                "get_latest_numeric, get_series, get_highest_price, "
                "get_price_history, get_eps_history, get_eps_data_quality."
            )

        self.loader: FinancialRepository = loader_instance
        self.mapper = self.loader.mapper
        self._registry = registry

    def get_latest_value(self, field: FinancialField) -> Optional[float]:
        if field is None:
            return None
        return self.loader.get_latest_numeric(field)

    def get_ttm_value(self, field: FinancialField) -> Optional[float]:
        if field is None:
            return None
        return self.loader.get_ttm_from_quarters(field, year_offset=0)

    def get_ttm_prev_value(self, field: FinancialField) -> Optional[float]:
        if field is None:
            return None
        prev_ttm = self.loader.get_ttm_from_quarters(field, year_offset=1)
        if prev_ttm is not None:
            return prev_ttm
        return self.loader.get_annual_value(field, year_offset=1)

    def get_series_value(
        self,
        field: FinancialField,
        period: Optional[Period] = None,
    ) -> Optional[List[float]]:
        if field is None:
            return None
        return self.loader.get_series(field, period)

    def get_from_field(
        self, field: BaseField
    ) -> Optional[Union[float, str, Enum, List[float]]]:
        """
        Dispatch to the correct loader method based on field type and action.

        Returns the raw loader result — ``None`` when data is unavailable.
        Callers should use ``_get_field_value`` (which wraps this method) to
        get a non-None default and simultaneously record the miss.
        """
        if isinstance(field, FinancialField):
            match field.action:
                case Action.GET_LATEST_VALUE:
                    return self.get_latest_value(field)
                case Action.GET_TTM_VALUE:
                    return self.get_ttm_value(field)
                case Action.GET_TTM_PREV_VALUE:
                    return self.get_ttm_prev_value(field)
                case Action.GET_SERIES:
                    return self.get_series_value(field)

        if isinstance(field, (LabelField, EnumField)):
            return self.loader.get_label(field)

        return None


    def _get_field_value(
        self,
        model_name: str,
        field_name: str,
        field_def: BaseField,
    ) -> Union[float, str, Enum, List[float], None]:
        """
        Dispatch + record miss.

        For numeric ``FinancialField`` descriptors, returns ``0.0`` (never
        ``None``) when the loader has no data, and records the miss in the
        registry.  For label/enum fields, returns ``None`` on miss (the domain
        model fields are ``Optional[str]``/``Optional[Enum]`` by design).
        """
        raw = self.get_from_field(field_def)
        if raw is not None:
            return raw

        if isinstance(field_def, FinancialField) and self._registry is not None:
            self._registry.record(
                model_name,
                field_name,
                MissingReason.NOT_IN_SOURCE,
                detail=f"No data returned for label(s): {getattr(field_def, 'label', '?')}",
            )

        # Numeric fields default to 0.0; label/enum fields return None.
        if isinstance(field_def, FinancialField):
            return 0.0
        return None

    def _build_valuation(self) -> sm.Valuation:
        """
        Construct a seed ``Valuation`` carrying only ``highest_price``.

        The full ``Valuation`` is computed by ``Valuation.build()`` inside
        ``StockMetrics._rebuild_derived()``.  ``cost_of_debt`` and
        ``corporate_tax_rate`` are derived from statement data there; the
        seed passes ``0.0`` so the factory knows to compute them.
        """
        return sm.Valuation(
            highest_price=self.loader.get_highest_price() or 0.0,
            cost_of_debt=0.0,
            corporate_tax_rate=0.0,
            price_to_sales=0.0,
            price_to_book=0.0,
            median_historical_pe=None,
            fcf_cagr=0.0,
            forward_growth_rate=0.0,
            enterprise_value=0.0,
        )

    def _build_historical_data(self) -> sm.HistoricalData:
        return sm.HistoricalData(
            price_history=self.loader.get_price_history(),
            eps_history=self.loader.get_eps_history(),
        )

    def build_model(self, model_cls: type[ModelT]) -> ModelT:
        """
        Build a domain sub-model from its registered mapper.

        For every field in the mapper:
        - ``FinancialField`` descriptors → ``_get_field_value()`` (records miss
          in registry, returns ``0.0`` on None).
        - Other ``BaseField`` descriptors (LabelField, EnumField) → raw loader
          result (``None`` allowed; those fields are Optional in domain).
        - Non-field mapper entries → ``None``.
        """
        mapper     = self.mapper[model_cls]
        model_name = model_cls.__name__
        kwargs: dict = {}

        for field_name, field_def in mapper.items():
            if isinstance(field_def, BaseField):
                kwargs[field_name] = self._get_field_value(
                    model_name, field_name, field_def
                )
            else:
                kwargs[field_name] = None

        return cast(ModelT, mapper.target_type(**kwargs))

    def _build_history_model(self, mapper: GenericMapper) -> HistoryT:
        """
        Generic history-model builder.

        Calls ``get_series_value()`` for every ``YfSeriesField`` and
        ``get_from_field()`` for other ``BaseField`` descriptors.  History
        fields that return ``None`` are left as ``None`` — series have no
        meaningful scalar default, and the registry does not record series
        misses (history is optional by design).
        """
        kwargs: dict = {}
        for field_name, field_def in mapper.items():
            if isinstance(field_def, YfSeriesField):
                kwargs[field_name] = self.get_series_value(field_def)
            elif isinstance(field_def, BaseField):
                kwargs[field_name] = self.get_from_field(field_def)
            else:
                kwargs[field_name] = None
        return cast(HistoryT, mapper.target_type(**kwargs))

    def _build_financials_history(self) -> FinancialsHistory:
        return cast(FinancialsHistory, self._build_history_model(FinancialsHistoryMapper()))

    def _build_cashflow_history(self) -> CashFlowHistory:
        return cast(CashFlowHistory, self._build_history_model(CashFlowHistoryMapper()))

    def _build_balance_sheet_history(self) -> BalanceSheetHistory:
        return cast(BalanceSheetHistory, self._build_history_model(BalanceSheetHistoryMapper()))

    def _post_build_audit(self, stock: sm.StockMetrics) -> None:
        """
        Record formula-level misses after the full build is complete.

        This runs after the second ``_rebuild_derived()`` call so it reflects
        the final state of ``Valuation`` and ``Ratios``.  Each check decides
        between ``DERIVED_FAILED``, ``ZERO_DENOMINATOR``, or
        ``NOT_APPLICABLE`` based on why the formula produced ``0.0``.
        """
        if self._registry is None:
            return

        val = stock.valuation
        fin = stock.financials
        bs  = stock.balance_sheet
        cf  = stock.cash_flow
        r   = stock.ratios

        _D = MissingReason.DERIVED_FAILED
        _Z = MissingReason.ZERO_DENOMINATOR
        _N = MissingReason.NOT_APPLICABLE
        _I = MissingReason.INSUFFICIENT_DATA

        # --- Valuation ---
        if val.corporate_tax_rate == 0.0:
            if fin.ebt_ttm == 0.0 and fin.tax_expense_ttm == 0.0:
                self._registry.record_derived(
                    "Valuation", "corporate_tax_rate", _D,
                    "both ebt_ttm and tax_expense_ttm are zero or missing",
                )
            elif fin.ebt_ttm == 0.0:
                self._registry.record_derived(
                    "Valuation", "corporate_tax_rate", _Z,
                    "ebt_ttm is zero — tax rate is mathematically undefined",
                )

        if val.cost_of_debt == 0.0:
            if bs.total_debt == 0.0:
                self._registry.record_derived(
                    "Valuation", "cost_of_debt", _N,
                    "no debt on balance sheet",
                )
            elif fin.interest_expense_ttm == 0.0:
                self._registry.record_derived(
                    "Valuation", "cost_of_debt", _D,
                    "interest_expense_ttm is zero or missing",
                )

        if val.enterprise_value == 0.0 and stock.market_data.market_cap == 0.0:
            self._registry.record_derived(
                "Valuation", "enterprise_value", _D,
                "market_cap is zero",
            )

        if val.median_historical_pe is None:
            self._registry.record_derived(
                "Valuation", "median_historical_pe", _I,
                "fewer than 3 valid (price, EPS) pairs in historical data",
            )

        if val.fcf_cagr == 0.0:
            if cf.history is None or cf.history.fcf_annual is None:
                self._registry.record_derived(
                    "Valuation", "fcf_cagr", _I,
                    "no annual FCF history available",
                )
            elif len(cf.history.fcf_annual) < 2:
                self._registry.record_derived(
                    "Valuation", "fcf_cagr", _I,
                    "fewer than 2 annual FCF data points",
                )

        if val.forward_growth_rate == 0.0:
            self._registry.record_derived(
                "Valuation", "forward_growth_rate", _D,
                "all growth signals (NI CAGR, EPS CAGR, TTM growth) resolved to zero",
            )

        if val.price_to_sales == 0.0 and fin.revenue_ttm == 0.0:
            self._registry.record_derived(
                "Valuation", "price_to_sales", _Z,
                "revenue_ttm is zero",
            )

        # --- Ratios ---
        if r is None:
            return

        if r.roic == 0.0 and fin.ebit_ttm == 0.0:
            self._registry.record_derived(
                "Ratios", "roic", _D,
                "ebit_ttm is zero or missing",
            )

        if r.peg_ratio == 0.0 and fin.net_income_growth == 0.0:
            self._registry.record_derived(
                "Ratios", "peg_ratio", _Z,
                "net_income_growth is zero — PEG is undefined",
            )

        if r.interest_coverage == 0.0 and fin.interest_expense_ttm == 0.0:
            self._registry.record_derived(
                "Ratios", "interest_coverage", _N,
                "interest_expense_ttm is zero — company likely has no debt",
            )

        if r.ev_ebit == 0.0 and fin.ebit_ttm == 0.0:
            self._registry.record_derived("Ratios", "ev_ebit", _Z, "ebit_ttm is zero")

        if r.ev_ebitda == 0.0 and fin.ebitda_ttm == 0.0:
            self._registry.record_derived("Ratios", "ev_ebitda", _Z, "ebitda_ttm is zero")

        if r.price_to_fcf == 0.0 and cf.fcf_ttm == 0.0:
            self._registry.record_derived(
                "Ratios", "price_to_fcf", _Z,
                "fcf_ttm is zero",
            )

        if r.fcf_yield == 0.0 and cf.fcf_ttm == 0.0:
            self._registry.record_derived(
                "Ratios", "fcf_yield", _Z,
                "fcf_ttm is zero",
            )

        if r.dividend_yield == 0.0 and cf.dividends_paid_ttm == 0.0:
            self._registry.record_derived(
                "Ratios", "dividend_yield", _N,
                "dividends_paid_ttm is zero — company may not pay dividends",
            )

        if r.payout_ratio == 0.0 and cf.dividends_paid_ttm == 0.0:
            self._registry.record_derived(
                "Ratios", "payout_ratio", _N,
                "dividends_paid_ttm is zero",
            )

        if r.debt_to_equity == 0.0 and bs.total_debt == 0.0:
            self._registry.record_derived(
                "Ratios", "debt_to_equity", _N,
                "total_debt is zero — company is debt-free",
            )

    def build_stock_metrics(self) -> sm.StockMetrics:
        """
        Build the full ``StockMetrics`` aggregate.

        Construction order
        ------------------
        1. Build all primary scalar sub-models (profile, financials, …).
        2. Construct ``StockMetrics`` — ``__post_init__`` runs the *first*
           ``_rebuild_derived()`` pass using scalar data only (no history).
        3. Clear derived registry entries from the first pass (they may be
           stale now that history is about to be attached).
        4. Build history companions and attach them to their sub-models.
        5. Run the second ``_rebuild_derived()`` with full history.
        6. Run ``_post_build_audit()`` to record formula-level misses from
           the final state.
        """
        stock = sm.StockMetrics(
            self.build_model(sm.CompanyProfile),
            self.build_model(sm.Financials),
            self.build_model(sm.CashFlow),
            self.build_model(sm.BalanceSheet),
            self.build_model(sm.MarketData),
            self._build_valuation(),
            self._build_historical_data(),
        )

        # Clear any derived misses from the first _rebuild_derived() pass
        # (ran inside __post_init__ without history) before attaching history.
        if self._registry is not None:
            self._registry.clear_derived()

        stock.financials.history    = self._build_financials_history()
        stock.cash_flow.history     = self._build_cashflow_history()
        stock.balance_sheet.history = self._build_balance_sheet_history()

        stock._rebuild_derived()        # second pass — full history available
        self._post_build_audit(stock)   # record formula-level misses from final state

        return stock
