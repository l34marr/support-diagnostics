"""
Node health checks.
"""

from typing import Any, Optional

from data_models import DiagnosticData, Severity
from health_checks.base import BaseHealthCheck


class HeapUsageCheck(BaseHealthCheck):
    """Check JVM heap usage per node."""

    def __init__(self, critical_threshold: float = 85.0, warning_threshold: float = 75.0):
        super().__init__("heap_usage", "node", Severity.CRITICAL)
        self.critical_threshold = critical_threshold
        self.warning_threshold = warning_threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        issues = []

        for node in data.nodes:
            if node.heap_used_percent is None:
                continue

            if node.heap_used_percent >= self.critical_threshold:
                issues.append({
                    "node": node.name,
                    "value": node.heap_used_percent,
                    "threshold": self.critical_threshold,
                    "heap_used": node.heap_used,
                    "heap_max": node.heap_max,
                })
            elif node.heap_used_percent >= self.warning_threshold:
                self.severity = Severity.WARNING
                issues.append({
                    "node": node.name,
                    "value": node.heap_used_percent,
                    "threshold": self.warning_threshold,
                    "heap_used": node.heap_used,
                    "heap_max": node.heap_max,
                })

        if issues:
            self.severity = Severity.CRITICAL
            return self.create_issue(
                description=f"High heap usage detected on {len(issues)} node(s)",
                evidence={"nodes": issues},
                recommendation="Increase heap size or reduce load. Check for memory leaks via heap dump analysis.",
                details=f"Nodes: {', '.join([i['node'] for i in issues])}",
            )

        return None


class CPUUsageCheck(BaseHealthCheck):
    """Check CPU usage per node."""

    def __init__(self, warning_threshold: float = 80.0, critical_threshold: float = 90.0):
        super().__init__("cpu_usage", "node", Severity.WARNING)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        issues = []

        for node in data.nodes:
            if node.cpu_percent is None:
                continue

            if node.cpu_percent >= self.critical_threshold:
                self.severity = Severity.CRITICAL
                issues.append({
                    "node": node.name,
                    "value": node.cpu_percent,
                    "threshold": self.critical_threshold,
                })
            elif node.cpu_percent >= self.warning_threshold:
                issues.append({
                    "node": node.name,
                    "value": node.cpu_percent,
                    "threshold": self.warning_threshold,
                })

        if issues:
            avg_cpu = sum(i['value'] for i in issues if i['value']) / len(issues) if issues else 0

            return self.create_issue(
                description=f"High CPU usage detected on {len(issues)} node(s) (avg: {avg_cpu:.1f}%)",
                evidence={"nodes": issues},
                recommendation="Check for long-running queries, high indexing rates, or resource contention.",
                details=f"Average CPU: {avg_cpu:.1f}%",
            )

        return None


class LoadAverageCheck(BaseHealthCheck):
    """Check load average vs CPU cores."""

    def __init__(self):
        super().__init__("load_average", "node", Severity.WARNING)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        issues = []

        for node in data.nodes:
            if node.load_1m is None:
                continue

            if node.load_1m > 10:
                issues.append({
                    "node": node.name,
                    "load_1m": node.load_1m,
                    "load_5m": node.load_5m,
                    "load_15m": node.load_15m,
                })

        if issues:
            return self.create_issue(
                description=f"High load average detected on {len(issues)} node(s)",
                evidence={"nodes": issues},
                recommendation="Check for resource-intensive operations. Verify CPU scaling.",
            )

        return None


class DiskUsageCheck(BaseHealthCheck):
    """Check disk usage per node."""

    def __init__(self, warning_threshold: float = 80.0, critical_threshold: float = 90.0):
        super().__init__("disk_usage", "node", Severity.WARNING)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        issues = []

        for node in data.nodes:
            if node.disk_used_percent is None:
                continue

            if node.disk_used_percent >= self.critical_threshold:
                self.severity = Severity.CRITICAL
                issues.append({
                    "node": node.name,
                    "value": node.disk_used_percent,
                    "threshold": self.critical_threshold,
                    "disk_used": node.disk_used,
                    "disk_total": node.disk_total,
                })
            elif node.disk_used_percent >= self.warning_threshold:
                issues.append({
                    "node": node.name,
                    "value": node.disk_used_percent,
                    "threshold": self.warning_threshold,
                    "disk_used": node.disk_used,
                    "disk_total": node.disk_total,
                })

        if issues:
            return self.create_issue(
                description=f"High disk usage detected on {len(issues)} node(s)",
                evidence={"nodes": issues},
                recommendation="Free up disk space or add storage. Consider index lifecycle management.",
            )

        return None


class ThreadPoolRejectionsCheck(BaseHealthCheck):
    """Check for thread pool rejections."""

    def __init__(self):
        super().__init__("thread_pool_rejections", "node", Severity.CRITICAL)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        issues = []

        for node in data.nodes:
            if node.thread_pool_rejections:
                for pool_name, rejected_count in node.thread_pool_rejections.items():
                    issues.append({
                        "node": node.name,
                        "pool": pool_name,
                        "rejections": rejected_count,
                    })

        if issues:
            return self.create_issue(
                description=f"Thread pool rejections detected on {len(set(i['node'] for i in issues))} node(s)",
                evidence={"rejections": issues},
                recommendation="Increase thread pool sizes or reduce load. Check for resource saturation.",
            )

        return None


class CircuitBreakerCheck(BaseHealthCheck):
    """Check for tripped circuit breakers."""

    def __init__(self):
        super().__init__("circuit_breakers", "node", Severity.CRITICAL)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        issues = []

        for node in data.nodes:
            if node.circuit_breakers:
                for cb_name, cb_data in node.circuit_breakers.items():
                    issues.append({
                        "node": node.name,
                        "breaker": cb_name,
                        "limit": cb_data.get('limit'),
                        "estimated": cb_data.get('estimated'),
                    })

        if issues:
            return self.create_issue(
                description=f"Circuit breakers tripped on {len(set(i['node'] for i in issues))} node(s)",
                evidence={"breakers": issues},
                recommendation="Reduce request size, increase limits, or check for memory leaks.",
            )

        return None


class GCDurationCheck(BaseHealthCheck):
    """Check for long GC pauses."""

    def __init__(self, warning_threshold: float = 10.0, critical_threshold: float = 30.0):
        super().__init__("gc_duration", "node", Severity.WARNING)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        long_pauses = data.raw_data.get('gc_log', {}).get('long_gc_pauses', [])

        if not long_pauses:
            return None

        critical_pauses = [p for p in long_pauses if p['duration'] >= self.critical_threshold]

        if critical_pauses:
            self.severity = Severity.CRITICAL
            return self.create_issue(
                description=f"Found {len(critical_pauses)} long GC pause(s) > {self.critical_threshold}s",
                evidence={"pauses": critical_pauses},
                recommendation="Investigate memory leaks, reduce heap pressure, or optimize queries.",
            )
        elif long_pauses:
            return self.create_issue(
                description=f"Found {len(long_pauses)} GC pause(s) > {self.warning_threshold}s",
                evidence={"pauses": long_pauses},
                recommendation="Monitor GC behavior. Consider heap tuning or query optimization.",
            )

        return None


class LongGCCheck(BaseHealthCheck):
    """Check for excessively long GC pauses."""

    def __init__(self, critical_threshold: float = 30.0):
        super().__init__("long_gc_pause", "node", Severity.CRITICAL)
        self.critical_threshold = critical_threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        long_pauses = data.raw_data.get('gc_log', {}).get('long_gc_pauses', [])

        if not long_pauses:
            return None

        critical_pauses = [p for p in long_pauses if p['duration'] >= self.critical_threshold]

        if critical_pauses:
            return self.create_issue(
                description=f"Found {len(critical_pauses)} GC pause(s) > {self.critical_threshold}s",
                evidence={"pauses": critical_pauses},
                recommendation="Investigate memory leaks immediately. Consider increasing heap or reducing load.",
            )

        return None


def get_all_node_checks(thresholds: dict) -> list:
    """Get all node health checks with configured thresholds."""
    node_thresholds = thresholds.get('node', {})

    return [
        HeapUsageCheck(
            critical_threshold=node_thresholds.get('heap_used_percent', {}).get('critical', 85.0),
            warning_threshold=node_thresholds.get('heap_used_percent', {}).get('warning', 75.0),
        ),
        CPUUsageCheck(
            warning_threshold=node_thresholds.get('cpu_percent', {}).get('warning', 80.0),
            critical_threshold=node_thresholds.get('cpu_percent', {}).get('critical', 90.0),
        ),
        LoadAverageCheck(),
        DiskUsageCheck(
            warning_threshold=node_thresholds.get('disk_used_percent', {}).get('warning', 80.0),
            critical_threshold=node_thresholds.get('disk_used_percent', {}).get('critical', 90.0),
        ),
        ThreadPoolRejectionsCheck(),
        CircuitBreakerCheck(),
        GCDurationCheck(
            warning_threshold=node_thresholds.get('gc_duration', {}).get('warning', 10.0),
            critical_threshold=node_thresholds.get('gc_duration', {}).get('critical', 30.0),
        ),
        LongGCCheck(
            critical_threshold=node_thresholds.get('long_gc_pause', {}).get('critical', 30.0),
        ),
    ]
