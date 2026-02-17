"""
Cluster health checks.
"""

from typing import Any, Optional

from data_models import DiagnosticData, Severity
from health_checks.base import BaseHealthCheck


class ClusterStatusCheck(BaseHealthCheck):
    """Check cluster status (green/yellow/red)."""

    def __init__(self):
        super().__init__("cluster_status", "cluster", Severity.CRITICAL)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        if not data.cluster:
            return None

        if data.cluster.status == 'red':
            return self.create_issue(
                description="Cluster status is RED",
                evidence={"status": data.cluster.status},
                recommendation="Check unassigned shards and node failures. Ensure all nodes are healthy.",
            )

        if data.cluster.status == 'yellow':
            return self.create_issue(
                description="Cluster status is YELLOW",
                evidence={"status": data.cluster.status},
                recommendation="Check for unassigned shards or replica shard issues.",
            )

        return None


class ActiveShardsCheck(BaseHealthCheck):
    """Check if active shards percentage is below threshold."""

    def __init__(self, threshold: float = 90.0):
        super().__init__("active_shards_percent", "cluster", Severity.WARNING)
        self.threshold = threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        if not data.cluster:
            return None

        if data.cluster.active_shards_percent < self.threshold:
            return self.create_issue(
                description=f"Active shards percentage ({data.cluster.active_shards_percent}%) is below threshold ({self.threshold}%)",
                evidence={
                    "active_shards_percent": data.cluster.active_shards_percent,
                    "active_shards": data.cluster.active_shards,
                    "total_shards": data.cluster.active_shards + data.cluster.unassigned_shards,
                },
                recommendation="Check for shard allocation issues or node failures.",
            )

        return None


class UnassignedShardsCheck(BaseHealthCheck):
    """Check for unassigned shards."""

    def __init__(self):
        super().__init__("unassigned_shards", "cluster", Severity.CRITICAL)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        if not data.cluster:
            return None

        if data.cluster.unassigned_shards > 0:
            unassigned_details = []

            for shard in data.shards:
                if shard.state == 'UNASSIGNED':
                    unassigned_details.append({
                        "index": shard.index,
                        "shard": shard.shard,
                        "prirep": shard.prirep,
                        "reason": shard.unassigned_reason or "unknown",
                    })

            return self.create_issue(
                description=f"Found {data.cluster.unassigned_shards} unassigned shard(s)",
                evidence={
                    "count": data.cluster.unassigned_shards,
                    "shards": unassigned_details[:20],
                },
                recommendation="Use allocation explain API to determine why shards are unassigned. Check disk space and node capacity.",
            )

        return None


class RelocatingShardsCheck(BaseHealthCheck):
    """Check for relocating shards."""

    def __init__(self):
        super().__init__("relocating_shards", "cluster", Severity.WARNING)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        if not data.cluster:
            return None

        if data.cluster.relocating_shards > 0:
            return self.create_issue(
                description=f"Found {data.cluster.relocating_shards} relocating shard(s)",
                evidence={"count": data.cluster.relocating_shards},
                recommendation="Shard relocation may impact performance. Monitor progress and check for rebalancing issues.",
            )

        return None


class PendingTasksCheck(BaseHealthCheck):
    """Check for pending tasks."""

    def __init__(self, threshold: int = 100):
        super().__init__("pending_tasks", "cluster", Severity.WARNING)
        self.threshold = threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        if not data.cluster:
            return None

        if data.cluster.pending_tasks > self.threshold:
            return self.create_issue(
                description=f"Pending tasks count ({data.cluster.pending_tasks}) exceeds threshold ({self.threshold})",
                evidence={"count": data.cluster.pending_tasks, "threshold": self.threshold},
                recommendation="High pending tasks may indicate cluster overload or master node issues. Check cluster state and thread pools.",
            )

        return None


def get_all_cluster_checks(thresholds: dict) -> list:
    """Get all cluster health checks with configured thresholds."""
    cluster_thresholds = thresholds.get('cluster', {})

    return [
        ClusterStatusCheck(),
        ActiveShardsCheck(threshold=cluster_thresholds.get('active_shards_percent', {}).get('warning', 90.0)),
        UnassignedShardsCheck(),
        RelocatingShardsCheck(),
        PendingTasksCheck(threshold=cluster_thresholds.get('pending_tasks', {}).get('warning', 100)),
    ]
