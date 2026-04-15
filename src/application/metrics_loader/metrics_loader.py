from __future__ import annotations

import logging
from enum import Enum
from typing import List, Optional, Type, TypeVar, Union, cast, get_args, get_origin, get_type_hints

import domain.metrics.stock as sm
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
ModelT = TypeVar("ModelT")
HistoryT = TypeVar("HistoryT")
def _is_optional(annotation) -> bool:
    """Return True when *annotation* is Optional[X] (i.e. Union[X, None])."""
    return get_origin(annotation) is Union and type(None) in get_args(annotation)


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
    ) -> None:
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
        """
        Return the full ordered historical series for a statement row.

        ``period`` overrides the period declared on the field descriptor.
        When both are ``None`` the loader defaults to QUARTERLY.
        """
        if field is None:
            return None
        return self.loader.get_series(field, period)

    def get_from_field(
        self, field: BaseField
    ) -> Optional[Union[float, str, Enum, List[float]]]:
        """
        Dispatch to the correct loader method based on field type and action.
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

    def _build_valuation(self) -> sm.Valuation:
        """
        Construct a seed ``Valuation`` for the loader-specific fields.

        Only ``highest_price`` is passed here.  ``cost_of_debt`` and
        ``corporate_tax_rate`` are derived inside ``Valuation.build``.

        Note: ValuationMapper fields (costOfDebt, corporateTaxRate) in
        StockMetricsMapper are intentionally unused because Valuation is
        always built via Valuation.build() — the mapper would duplicate
        derivation logic already expressed there.  The seed carries only
        ``highest_price``, which has no formula equivalent.
        """
        return sm.Valuation(
            highest_price=self.loader.get_highest_price(),
            cost_of_debt=None,
            corporate_tax_rate=None,
            price_to_sales=None,
            price_to_book=None,
            median_historical_pe=None,
            fcf_cagr=None,
            forward_growth_rate=None,
            enterprise_value=None,
        )

    def _build_historical_data(self) -> sm.HistoricalData:
        return sm.HistoricalData(
            price_history=self.loader.get_price_history(),
            eps_history=self.loader.get_eps_history(),
        )

    def build_model(self, model_cls: type[ModelT]) -> ModelT:
        """
        Build a domain model instance from its registered mapper.

        For every field in the mapper:
        - If the descriptor is a ``BaseField``, dispatch to ``get_from_field``.
        - Otherwise default to ``None``.

        A ``ValueError`` is raised when a resolved ``None`` would be assigned
        to a field whose type annotation is not ``Optional``.  This surfaces
        data-quality problems at construction time rather than allowing silent
        incorrect calculations downstream.
        """
        mapper = self.mapper[model_cls]
        try:
            hints = get_type_hints(mapper.target_type)
        except Exception:
            hints = getattr(mapper.target_type, "__annotations__", {})

        kwargs = {}
        for field_name, field_def in mapper.items():
            if isinstance(field_def, BaseField):
                value = self.get_from_field(field_def)
            else:
                value = None

            if value is None and field_name in hints and not _is_optional(hints[field_name]):
                raise ValueError(
                    f"Required field '{field_name}' on {mapper.target_type.__name__} "
                    f"resolved to None. Check that the data source contains this field "
                    f"or mark the domain field as Optional."
                )

            kwargs[field_name] = value

        return cast(ModelT, mapper.target_type(**kwargs))

    def _build_history_model(self, mapper: GenericMapper) -> HistoryT:
        """
        Generic history model builder.

        Iterates the mapper and calls ``get_series_value()`` for every
        ``YfSeriesField`` it encounters.  Non-series fields (e.g. derived
        fields with ``init=False``) are skipped — they are never present in
        the mapper by design.
        """
        kwargs = {}
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
        2. Construct ``StockMetrics`` — ``__post_init__`` runs
           ``Valuation.build`` and ``Ratios.build`` using scalar data only.
        3. Build history companions and attach them to their sub-models.
        4. Call ``stock._rebuild_derived()`` so ``Valuation`` and ``Ratios``
           are re-computed with the richer history data.
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

        stock.financials.history    = self._build_financials_history()
        stock.cash_flow.history     = self._build_cashflow_history()
        stock.balance_sheet.history = self._build_balance_sheet_history()

        stock._rebuild_derived()

        return stock
