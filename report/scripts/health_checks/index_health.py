"""
Index health checks.
"""

from typing import Any, Optional

from data_models import DiagnosticData, Severity
from health_checks.base import BaseHealthCheck


class RedIndicesCheck(BaseHealthCheck):
    """Check for red indices."""

    def __init__(self):
        super().__init__("red_indices", "index", Severity.CRITICAL)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        red_indices = [idx for idx in data.indices if idx.health == 'red']

        if red_indices:
            return self.create_issue(
                description=f"Found {len(red_indices)} red index(es)",
                evidence={
                    "count": len(red_indices),
                    "indices": [idx.name for idx in red_indices],
                },
                recommendation="Investigate and fix red indices immediately. Check shard allocation and node health.",
                details=f"Indices: {', '.join([idx.name for idx in red_indices[:10]])}",
            )

        return None


class YellowIndicesCheck(BaseHealthCheck):
    """Check for yellow indices."""

    def __init__(self):
        super().__init__("yellow_indices", "index", Severity.WARNING)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        yellow_indices = [idx for idx in data.indices if idx.health == 'yellow']

        if yellow_indices:
            return self.create_issue(
                description=f"Found {len(yellow_indices)} yellow index(es)",
                evidence={
                    "count": len(yellow_indices),
                    "indices": [idx.name for idx in yellow_indices],
                },
                recommendation="Check for replica shard allocation issues.",
                details=f"Indices: {', '.join([idx.name for idx in yellow_indices[:10]])}",
            )

        return None


class LargeIndicesCheck(BaseHealthCheck):
    """Check for large indices (>100GB)."""

    def __init__(self, threshold_gb: float = 100.0):
        super().__init__("large_indices", "index", Severity.WARNING)
        self.threshold_gb = threshold_gb

    def check(self, data: DiagnosticData) -> Optional[Any]:
        large_indices = []

        for idx in data.indices:
            if idx.store_size:
                size_gb = _parse_size_to_gb(idx.store_size)
                if size_gb and size_gb > self.threshold_gb:
                    large_indices.append({
                        "index": idx.name,
                        "size": idx.store_size,
                        "size_gb": size_gb,
                    })

        if large_indices:
            return self.create_issue(
                description=f"Found {len(large_indices)} large index(es) > {self.threshold_gb}GB",
                evidence={"indices": large_indices},
                recommendation="Consider index lifecycle management, rollover, or sharding strategies.",
            )

        return None


class ManySmallIndicesCheck(BaseHealthCheck):
    """Check for many small indices."""

    def __init__(self, count_threshold: int = 1000, avg_size_threshold_gb: float = 1.0):
        super().__init__("many_small_indices", "index", Severity.WARNING)
        self.count_threshold = count_threshold
        self.avg_size_threshold_gb = avg_size_threshold_gb

    def check(self, data: DiagnosticData) -> Optional[Any]:
        if len(data.indices) < self.count_threshold:
            return None

        total_size_gb = 0
        valid_indices = []

        for idx in data.indices:
            if idx.store_size:
                size_gb = _parse_size_to_gb(idx.store_size)
                if size_gb is not None:
                    total_size_gb += size_gb
                    valid_indices.append(idx)

        if valid_indices:
            avg_size_gb = total_size_gb / len(valid_indices)

            if avg_size_gb < self.avg_size_threshold_gb:
                return self.create_issue(
                    description=f"Found {len(valid_indices)} indices with avg size {avg_size_gb:.2f}GB",
                    evidence={
                        "count": len(valid_indices),
                        "avg_size_gb": avg_size_gb,
                    },
                    recommendation="Use index lifecycle management (ILM), rollover, or consolidate small indices.",
                )

        return None


class TooManyFieldsCheck(BaseHealthCheck):
    """Check for indices with too many fields."""

    def __init__(self, threshold: int = 1000):
        super().__init__("too_many_fields", "index", Severity.WARNING)
        self.threshold = threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        problematic_indices = []

        for idx in data.indices:
            if idx.field_count and idx.field_count > self.threshold:
                problematic_indices.append({
                    "index": idx.name,
                    "field_count": idx.field_count,
                })

        if problematic_indices:
            return self.create_issue(
                description=f"Found {len(problematic_indices)} index(es) with > {self.threshold} fields",
                evidence={"indices": problematic_indices},
                recommendation="Review field mapping strategy. Use nested documents or separate indices.",
            )

        return None


class DeepNestingCheck(BaseHealthCheck):
    """Check for deep field nesting."""

    def __init__(self, threshold: int = 20):
        super().__init__("deep_nesting", "index", Severity.WARNING)
        self.threshold = threshold

    def check(self, data: DiagnosticData) -> Optional[Any]:
        problematic_indices = []

        for idx in data.indices:
            if idx.nesting_depth and idx.nesting_depth > self.threshold:
                problematic_indices.append({
                    "index": idx.name,
                    "nesting_depth": idx.nesting_depth,
                })

        if problematic_indices:
            return self.create_issue(
                description=f"Found {len(problematic_indices)} index(es) with nesting depth > {self.threshold}",
                evidence={"indices": problematic_indices},
                recommendation="Flatten document structure or use nested objects instead of deep nesting.",
            )

        return None


class ReplicationDelayCheck(BaseHealthCheck):
    """Check for replication delays (pri - rep > 0)."""

    def __init__(self):
        super().__init__("replication_delay", "index", Severity.WARNING)

    def check(self, data: DiagnosticData) -> Optional[Any]:
        delayed_indices = []

        for idx in data.indices:
            if idx.pri is not None and idx.rep is not None:
                if idx.pri - idx.rep > 0:
                    delayed_indices.append({
                        "index": idx.name,
                        "pri": idx.pri,
                        "rep": idx.rep,
                        "difference": idx.pri - idx.rep,
                    })

        if delayed_indices:
            return self.create_issue(
                description=f"Found {len(delayed_indices)} index(es) with replica shard delays",
                evidence={"indices": delayed_indices},
                recommendation="Check node availability and shard allocation. Verify cluster health.",
            )

        return None


def get_all_index_checks(thresholds: dict) -> list:
    """Get all index health checks with configured thresholds."""
    index_thresholds = thresholds.get('index', {})

    return [
        RedIndicesCheck(),
        YellowIndicesCheck(),
        LargeIndicesCheck(threshold_gb=index_thresholds.get('large_index_gb', {}).get('warning', 100.0)),
        ManySmallIndicesCheck(
            count_threshold=index_thresholds.get('many_small_indices', {}).get('count', 1000),
            avg_size_threshold_gb=index_thresholds.get('many_small_indices', {}).get('avg_size_gb',1.0),
        ),
        TooManyFieldsCheck(threshold=index_thresholds.get('field_count', {}).get('warning', 1000)),
        DeepNestingCheck(threshold=index_thresholds.get('nesting_depth', {}).get('warning', 20)),
        ReplicationDelayCheck(),
    ]


def _parse_size_to_gb(size_str: str) -> Optional[float]:
    """Parse size string (e.g., '10gb', '500mb') to GB."""
    if not size_str:
        return None

    size_str = size_str.lower().replace(' ', '')

    try:
        if size_str.endswith('tb'):
            return float(size_str[:-2]) * 1024
        elif size_str.endswith('gb'):
            return float(size_str[:-2])
        elif size_str.endswith('mb'):
            return float(size_str[:-2]) / 1024
        elif size_str.endswith('kb'):
            return float(size_str[:-2]) / 1024 / 1024
        elif size_str.endswith('b'):
            return float(size_str[:-1]) / 1024 / 1024 / 1024
        else:
            return None
    except ValueError:
        return None

        """Parse size string (e.g., '10gb', '500mb') to GB."""
        if not size_str:
            return None

        size_str = size_str.lower().replace(' ', '')

        try:
            if size_str.endswith('tb'):
                return float(size_str[:-2]) * 1024
            elif size_str.endswith('gb'):
                return float(size_str[:-2])
            elif size_str.endswith('mb'):
                return float(size_str[:-2]) / 1024
            elif size_str.endswith('kb'):
                return float(size_str[:-2]) / 1024 / 1024
            elif size_str.endswith('b'):
                return float(size_str[:-1]) / 1024 / 1024 / 1024
            else:
                return None
        except ValueError:
            return None
