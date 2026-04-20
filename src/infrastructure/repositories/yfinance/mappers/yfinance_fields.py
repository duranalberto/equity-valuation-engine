from __future__ import annotations

from enum import Enum, auto

from infrastructure.repositories.financial_repository import (
    Action,
    FinancialField,
    LabelField,
    Period,
)


class Statement(Enum):
    """
    Identifies which financial statement a ``YfFinancialField`` belongs to.

    Used by ``YfinanceDataLoader._select_df`` to route each field to the
    correct DataFrame without scanning label-constant dictionaries at
    call time.
    """
    INCOME       = auto()
    BALANCE_SHEET = auto()
    CASH_FLOW    = auto()


class YfLabelField(LabelField):
    """Label field backed by the Yahoo Finance info dict."""
    pass


class YfFinancialField(FinancialField):
    """
    Financial field backed by a Yahoo Finance statement DataFrame.

    ``statement`` declares which statement this field belongs to and is used
    by ``YfinanceDataLoader._select_df`` for O(1) DataFrame routing.
    """

    def __init__(
        self,
        label,
        action: Action,
        period: Period | None = None,
        statement: Statement = Statement.INCOME,
    ) -> None:
        super().__init__(label=label, action=action, period=period)
        self.statement = statement

    def __repr__(self) -> str:
        return (
            f"YfFinancialField(label={self.label!r}, action={self.action.name}, "
            f"period={self.period}, statement={self.statement.name})"
        )


class YfSeriesField(FinancialField):
    """
    Historical series field.

    Always uses ``Action.GET_SERIES``.  ``period`` selects quarterly vs annual.
    ``statement`` is required for correct DataFrame routing in
    ``YfinanceDataLoader._select_df``.
    """

    def __init__(
        self,
        label,
        period: Period = Period.QUARTERLY,
        statement: Statement = Statement.INCOME,
    ) -> None:
        super().__init__(label=label, action=Action.GET_SERIES, period=period)
        self.statement = statement

    def __repr__(self) -> str:
        return (
            f"YfSeriesField(label={self.label!r}, period={self.period}, "
            f"statement={self.statement.name})"
        )