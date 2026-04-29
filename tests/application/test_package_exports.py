from __future__ import annotations


def test_manager_imports_from_model_packages() -> None:
    from application.valuations.dcf import DCFManager
    from application.valuations.ddm import DDMManager
    from application.valuations.ev_ebitda import EVEBITDAManager
    from application.valuations.nav import NAVManager
    from application.valuations.pe import PEManager
    from application.valuations.ps import PSManager
    from application.valuations.reverse_dcf import ReverseDCFManager
    from application.valuations.roe import ROEManager

    assert DCFManager.__name__ == "DCFManager"
    assert PEManager.__name__ == "PEManager"
    assert ROEManager.__name__ == "ROEManager"
    assert EVEBITDAManager.__name__ == "EVEBITDAManager"
    assert PSManager.__name__ == "PSManager"
    assert DDMManager.__name__ == "DDMManager"
    assert NAVManager.__name__ == "NAVManager"
    assert ReverseDCFManager.__name__ == "ReverseDCFManager"


def test_manager_imports_from_aggregate_packages() -> None:
    from application import DCFManager as TopDCFManager
    from application import ReverseDCFManager as TopReverseDCFManager
    from application.valuations import DCFManager, ReverseDCFManager

    assert DCFManager is TopDCFManager
    assert ReverseDCFManager is TopReverseDCFManager


def test_valuation_model_dataclass_imports() -> None:
    from domain.valuation.models import (
        DCFParameters,
        DDMParameters,
        EVEBITDAParameters,
        ModelScenarioRow,
        NAVValuationReport,
        PEValuationReport,
        PSValuationReport,
        ROEValuationResult,
        ReverseDCFReport,
        ValuationSummaryReport,
    )

    exported = [
        DCFParameters,
        PEValuationReport,
        ROEValuationResult,
        EVEBITDAParameters,
        PSValuationReport,
        DDMParameters,
        NAVValuationReport,
        ReverseDCFReport,
        ValuationSummaryReport,
        ModelScenarioRow,
    ]

    assert all(item.__name__ for item in exported)
