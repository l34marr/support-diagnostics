"""
Configuration health checks.
"""

from typing import Any, Optional

from data_models import DiagnosticData, Severity
from health_checks.base import BaseHealthCheck


class MasterEligibleNodesCheck(BaseHealthCheck):
    """Check for proper master-eligible node configuration."""

    def __init__(self):
        super().__init__("master_eligible_nodes", "configuration", Severity.WARNING)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        master_nodes = [n for n in data.nodes if 'master' in n.roles]

        if len(master_nodes) not in [3, 5]:
            return self.create_issue(
                description=f"Found {len(master_nodes)} master-eligible node(s) (recommended: 3 or 5)",
                evidence={
                    "count": len(master_nodes),
                    "nodes": [n.name for n in master_nodes],
                },
                recommendation="Configure 3 or 5 master-eligible nodes for split-brain prevention.",
            )

        return None


class SwapDisabledCheck(BaseHealthCheck):
    """Check if swap is disabled."""

    def __init__(self):
        super().__init__("swap_disabled", "configuration", Severity.WARNING)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        log_entries = data.raw_data.get('logs', {}).get('elasticsearch.log', [])
        swap_warnings = [e for e in log_entries if 'swap' in e['line'].lower() and 'enabled' in e['line'].lower()]

        if swap_warnings:
            return self.create_issue(
                description="Swap appears to be enabled on one or more nodes",
                evidence={"warnings": len(swap_warnings)},
                recommendation="Disable swap with `swapoff -a` for all Elasticsearch nodes.",
            )

        return None


class FileDescriptorsCheck(BaseHealthCheck):
    """Check file descriptor limits."""

    def __init__(self, threshold: int = 65535):
        super().__init__("file_descriptors", "configuration", Severity.WARNING)
        self.threshold = threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        log_entries = data.raw_data.get('logs', {}).get('elasticsearch.log', [])
        fd_warnings = [
            e for e in log_entries
            if 'max file descriptors' in e['line'].lower()
            or 'too many open files' in e['line'].lower()
        ]

        if fd_warnings:
            return self.create_issue(
                description=f"File descriptor limit issues detected ({len(fd_warnings)} warnings)",
                evidence={"warnings": len(fd_warnings)},
                recommendation=f"Increase ulimit to at least {self.threshold} for Elasticsearch process.",
            )

        return None


def get_all_configuration_checks(thresholds: dict) -> list:
    """Get all configuration health checks."""
    return [
        MasterEligibleNodesCheck(),
        SwapDisabledCheck(),
        FileDescriptorsCheck(threshold=65535),
    ]
