from domain.core.enums import Sectors
from infrastructure.mappers.base_mapper import GenericMapper
from typing import Dict

class YahooSectorMapper(GenericMapper):

    @property
    def target_type(self) -> type[Sectors]:
        return Sectors

    @property
    def mapping(self) -> Dict[Sectors, str]:
        return {
            Sectors.BASIC_MATERIALS: "basic-materials",
            Sectors.COMMUNICATION_SERVICES: "communication-services",
            Sectors.CONSUMER_CYCLICAL: "consumer-cyclical",
            Sectors.CONSUMER_DEFENSIVE: "consumer-defensive",
            Sectors.ENERGY: "energy",
            Sectors.FINANCIAL_SERVICES: "financial-services",
            Sectors.HEALTHCARE: "healthcare",
            Sectors.INDUSTRIALS: "industrials",
            Sectors.REAL_ESTATE: "real-estate",
            Sectors.TECHNOLOGY: "technology",
            Sectors.UTILITIES: "utilities",
        }

