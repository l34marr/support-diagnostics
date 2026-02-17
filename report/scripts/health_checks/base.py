"""
Base class for health checks.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from data_models import HealthCheck as HealthCheckModel, Severity


class BaseHealthCheck(ABC):
    """
    Abstract base class for all health checks.

    All health checks must implement the check() method.
    """

    def __init__(self, name: str, category: str, severity: Severity):
        self.name = name
        self.category = category
        self.severity = severity

    @abstractmethod
    def check(self, data: Any) -> Optional[HealthCheckModel]:
        """
        Execute health check on diagnostic data.

        Returns HealthCheckModel if issue found, None otherwise.
        """

    def create_issue(
        self,
        description: str,
        evidence: Dict[str, Any],
        recommendation: str,
        details: str = ""
    ) -> HealthCheckModel:
        """Create a HealthCheckModel issue."""
        return HealthCheckModel(
            name=self.name,
            severity=self.severity,
            category=self.category,
            description=description,
            evidence=evidence,
            recommendation=recommendation,
            failed=True,
            details=details,
        )
