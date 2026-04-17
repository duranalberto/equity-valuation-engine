from domain.core.missing_registry import MissingRegistry
from domain.metrics.stock import StockMetrics


def evaluate_nulls(stock: StockMetrics) -> str:
    registry = MissingRegistry().scan(stock)
    return registry.report()

