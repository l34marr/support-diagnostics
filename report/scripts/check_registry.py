"""
Health check registry.
Central registry for all health checks.
"""

from typing import List, Optional, Dict, Any
from data_models import DiagnosticData, HealthCheck, Severity
from health_checks.base import BaseHealthCheck
from health_checks.cluster_health import get_all_cluster_checks
from health_checks.node_health import get_all_node_checks
from health_checks.index_health import get_all_index_checks
from health_checks.configuration import get_all_configuration_checks
from health_checks.performance import get_all_performance_checks
from utils.recommendations import get_recommendations


class HealthCheckRegistry:
    """Registry for managing and running health checks."""

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None):
        self.thresholds = thresholds or {}
        self.all_checks: List[BaseHealthCheck] = []

    def register_all_checks(self):
        """Register all health checks."""
        self.all_checks = []
        self.all_checks.extend(get_all_cluster_checks(self.thresholds))
        self.all_checks.extend(get_all_node_checks(self.thresholds))
        self.all_checks.extend(get_all_index_checks(self.thresholds))
        self.all_checks.extend(get_all_configuration_checks(self.thresholds))
        self.all_checks.extend(get_all_performance_checks(self.thresholds))

    def run_checks(self, data: DiagnosticData) -> List[HealthCheck]:
        """Run all registered health checks and return issues."""
        issues = []

        for check in self.all_checks:
            result = check.check(data)
            if result:
                recs = get_recommendations(check.name)
                result.recommendation = '\n'.join(recs.get('recommendations', []))
                if not result.recommendation:
                    result.recommendation = recs.get('message', 'Review issue')
                issues.append(result)

        return issues

    def get_issues_by_severity(self, issues: List[HealthCheck], severity: Severity) -> List[HealthCheck]:
        """Get issues filtered by severity."""
        return [issue for issue in issues if issue.severity == severity]

    def get_issues_by_category(self, issues: List[HealthCheck], category: str) -> List[HealthCheck]:
        """Get issues filtered by category."""
        return [issue for issue in issues if issue.category == category]


def run_health_checks(data: DiagnosticData, thresholds: dict = None) -> List[HealthCheck]:
    """Run all health checks with given thresholds."""
    registry = HealthCheckRegistry(thresholds)
    registry.register_all_checks()
    return registry.run_checks(data)
