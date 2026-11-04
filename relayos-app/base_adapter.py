"""Base ERP Adapter for RelayOS enterprise tenants."""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseERPAdapter(ABC):
    def __init__(self, tenant_slug: str, rate_limit_rpm: int):
        self.tenant_slug = tenant_slug
        self.rate_limit_rpm = rate_limit_rpm

    @abstractmethod
    def sync_records(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronize enterprise ERP records."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check adapter connectivity and status."""
        pass
