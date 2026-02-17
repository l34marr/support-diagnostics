"""
Performance health checks.
"""

from typing import Any, Optional
import re

from data_models import DiagnosticData, Severity
from health_checks.base import BaseHealthCheck


class SlowQueriesCheck(BaseHealthCheck):
    """Check for slow queries in logs."""

    def __init__(self, duration_threshold_s: float = 5.0):
        super().__init__("slow_queries", "performance", Severity.WARNING)
        self.duration_threshold_s = duration_threshold_s

    def check(self, data: DiagnosticData) -> Optional[Any]:
        slow_queries = []

        for log_name, entries in data.raw_data.get('logs', {}).items():
            for entry in entries:
                line = entry.get('line', '')

                match = re.search(r'took[>(\d+\.?\d*)[<]?\s*m[is]', line.lower())
                if match:
                    duration_s = float(match.group(1))
                    if duration_s > self.duration_threshold_s:
                        slow_queries.append({
                            "log": log_name,
                            "duration_s": duration_s,
                            "line": line[:200],
                        })

        if slow_queries:
            return self.create_issue(
                description=f"Found {len(slow_queries)} slow query/queries (>{self.duration_threshold_s}s)",
                evidence={"queries": slow_queries[:20]},
                recommendation="Optimize queries, add indices, or review field mappings.",
            )

        return None


class HighRejectionRateCheck(BaseHealthCheck):
    """Check for high rejection rates."""

    def __init__(self, threshold_percent: float = 1.0):
        super().__init__("high_rejection_rate", "performance", Severity.CRITICAL)
        self.threshold_percent = threshold_percent

    def check(self, data: DiagnosticData) -> Optional[Any]:
        nodes_with_rejections = []

        for node in data.nodes:
            if node.thread_pool_rejections:
                nodes_with_rejections.append(node.name)

        if not data.nodes:
            return None

        rejection_rate = (len(nodes_with_rejections) / len(data.nodes)) * 100

        if rejection_rate > self.threshold_percent:
            return self.create_issue(
                description=f"High rejection rate ({rejection_rate:.1f}%) across cluster",
                evidence={
                    "rate": rejection_rate,
                    "affected_nodes": nodes_with_rejections,
                },
                recommendation="Check thread pool sizes and load. Increase heap or adjust thread pool settings.",
            )

        return None


class ThreadPoolContentionCheck(BaseHealthCheck):
    """Check for thread pool queue contention."""

    def __init__(self, queue_threshold: int = 1000):
        super().__init__("thread_pool_contention", "performance", Severity.WARNING)
        self.queue_threshold = queue_threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        contentions = []

        for node in data.nodes:
            for pool_name, pool_data in data.raw_data.get('nodes_json', {}).get('nodes', {}).get(node.name, {}).get('thread_pool', {}).items():
                queue = pool_data.get('queue', 0)
                if queue > self.queue_threshold:
                    contentions.append({
                        "node": node.name,
                        "pool": pool_name,
                        "queue": queue,
                    })

        if contentions:
            return self.create_issue(
                description=f"Thread pool queue contention detected on {len(set(c['node'] for c in contentions))} node(s)",
                evidence={"contentions": contentions},
                recommendation="Increase thread pool sizes or reduce concurrent operations.",
            )

        return None


class SearchLatencyCheck(BaseHealthCheck):
    """Check for high search latency."""

    def __init__(self, threshold_s: float = 5.0):
        super().__init__("search_latency", "performance", Severity.WARNING)
        self.threshold_s = threshold_s

    def check(self, data: DiagnosticData) -> Optional[Any]:
        nodes_with_high_latency = []

        for node in data.nodes:
            for pool_name, pool_data in data.raw_data.get('nodes_json', {}).get('nodes', {}).get(node.name, {}).get('thread_pool', {}).items():
                if pool_name.startswith('search'):
                    queue = pool_data.get('queue', 0)
                    if queue > 1000:
                        nodes_with_high_latency.append(node.name)

        if nodes_with_high_latency:
            return self.create_issue(
                description=f"High search latency detected on {len(nodes_with_high_latency)} node(s)",
                evidence={"nodes": nodes_with_high_latency},
                recommendation="Review slow queries, check hardware resources, optimize search requests.",
            )

        return None


class IndexingLatencyCheck(BaseHealthCheck):
    """Check for high indexing latency."""

    def __init__(self, threshold_s: float = 30.0):
        super().__init__("indexing_latency", "performance", Severity.WARNING)
        self.threshold_s = threshold_s

    def check(self, data: DiagnosticData) -> Optional[Any]:
        nodes_with_high_latency = []

        for node in data.nodes:
            for pool_name, pool_data in data.raw_data.get('nodes_json', {}).get('nodes', {}).get(node.name, {}).get('thread_pool', {}).items():
                if pool_name.startswith('write') or pool_name.startswith('index'):
                    queue = pool_data.get('queue', 0)
                    if queue > 1000:
                        nodes_with_high_latency.append(node.name)

        if nodes_with_high_latency:
            return self.create_issue(
                description=f"High indexing latency detected on {len(nodes_with_high_latency)} node(s)",
                evidence={"nodes": nodes_with_high_latency},
                recommendation="Review indexing rate, check hardware, optimize bulk operations.",
            )

        return None


def get_all_performance_checks(thresholds: dict) -> list:
    """Get all performance health checks."""
    return [
        SlowQueriesCheck(duration_threshold_s=5.0),
        HighRejectionRateCheck(threshold_percent=1.0),
        ThreadPoolContentionCheck(queue_threshold=1000),
        SearchLatencyCheck(threshold_s=5.0),
        IndexingLatencyCheck(threshold_s=30.0),
    ]
