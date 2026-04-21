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
                "get_price_history, get_eps_history."
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

    def build_stock_metrics(self) -> sm.StockMetrics:
        """
        Build the full ``StockMetrics`` aggregate.

        Construction order
        ------------------
        1. Build all primary scalar sub-models (profile, financials, …).
        2. Construct ``StockMetrics`` — ``__post_init__`` performs validation
           only; it does **not** call ``_rebuild_derived()``.
        3. Build history companions and attach them to their sub-models.
        4. Call ``_rebuild_derived()`` exactly once — full history is now
           available.  Builders emit ``BuildDiagnostic`` entries which are
           stored on ``stock._diagnostics``.
        5. Feed ``_diagnostics`` into the registry to record formula-level
           misses.
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

        # Attach history companions before the single rebuild pass.
        stock.financials.history    = self._build_financials_history()
        stock.cash_flow.history     = self._build_cashflow_history()
        stock.balance_sheet.history = self._build_balance_sheet_history()

        # Single-pass derive: full history is available.
        stock._rebuild_derived()

        # Feed builder-emitted diagnostics into the registry.
        if self._registry is not None:
            for diag in stock._diagnostics:
                self._registry.record_derived(
                    diag.model,
                    diag.field,
                    diag.reason,
                    diag.detail,
                )

        return stock