from dataclasses import replace

from application.valuations.roe.validator import ROEChecker
from domain.valuation.models.roe import ROEParameters
from domain.valuation.policies import FactorSeverity
from tests.unit.fixtures import make_adbe_metrics, make_orcl_metrics


def _cap_factors(result):
    return [factor for factor in result.factors if "Cap" in factor.name or "cap" in factor.name.lower()]


def test_roe_validator_discloses_cap_as_zero_weight_warning() -> None:
    result = ROEChecker(make_orcl_metrics()).evaluate()
    factors = _cap_factors(result)

    assert factors
    assert all(factor.weight == 0 for factor in factors)
    assert all(factor.severity == FactorSeverity.WARNING for factor in factors)


def test_roe_validator_discloses_cap_for_other_technology_company() -> None:
    result = ROEChecker(make_adbe_metrics()).evaluate()

    assert _cap_factors(result)
    assert all(factor.weight == 0 for factor in _cap_factors(result))


def test_roe_validator_cap_warning_does_not_block_suitable_company() -> None:
    result = ROEChecker(make_orcl_metrics()).evaluate()

    assert result.is_suitable is True
    assert result.total_severity_score <= 5


def test_roe_validator_omits_cap_warning_below_cap() -> None:
    metrics = make_orcl_metrics()
    metrics.ratios = replace(metrics.ratios, return_on_equity=0.20)
    params = ROEParameters(
        projection_years=10,
        margin_of_safety=0.30,
        discount_rate=0.11,
        roe_cap=0.35,
    )

    result = ROEChecker(metrics, params=params).evaluate()

    assert _cap_factors(result) == []


def test_roe_validator_omits_cap_warning_when_cap_disabled() -> None:
    params = ROEParameters(
        projection_years=10,
        margin_of_safety=0.30,
        discount_rate=0.11,
        roe_cap=None,
    )

    result = ROEChecker(make_orcl_metrics(), params=params).evaluate()

    assert _cap_factors(result) == []
