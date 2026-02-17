"""
Data models for the ELK diagnostic analysis tool.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class Severity(Enum):
    """Severity levels for health checks."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class HealthCheck:
    """Represents a single health check result."""
    name: str
    severity: Severity
    category: str
    description: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    failed: bool = False
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert health check to dictionary."""
        return {
            "check": self.name,
            "severity": self.severity.value,
            "category": self.category,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "failed": self.failed,
            "details": self.details,
        }


@dataclass
class NodeInfo:
    """Information about a single node in the cluster."""
    name: str
    roles: List[str] = field(default_factory=list)
    cpu_percent: Optional[float] = None
    heap_used_percent: Optional[float] = None
    heap_used: Optional[str] = None
    heap_max: Optional[str] = None
    disk_used_percent: Optional[float] = None
    disk_total: Optional[str] = None
    disk_used: Optional[str] = None
    load_1m: Optional[float] = None
    load_5m: Optional[float] = None
    load_15m: Optional[float] = None
    thread_pool_rejections: Dict[str, int] = field(default_factory=dict)
    circuit_breakers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    gc_old_collection_time: Optional[float] = None
    gc_young_collection_time: Optional[float] = None
    uptime: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert node info to dictionary."""
        return {
            "name": self.name,
            "roles": self.roles,
            "cpu_percent": self.cpu_percent,
            "heap_used_percent": self.heap_used_percent,
            "heap_used": self.heap_used,
            "heap_max": self.heap_max,
            "disk_used_percent": self.disk_used_percent,
            "disk_total": self.disk_total,
            "disk_used": self.disk_used,
            "load_1m": self.load_1m,
            "load_5m": self.load_5m,
            "load_15m": self.load_15m,
            "thread_pool_rejections": self.thread_pool_rejections,
            "circuit_breakers": self.circuit_breakers,
            "gc_old_collection_time": self.gc_old_collection_time,
            "gc_young_collection_time": self.gc_young_collection_time,
            "uptime": self.uptime,
            "version": self.version,
        }


@dataclass
class IndexInfo:
    """Information about a single index."""
    name: str
    status: Optional[str] = None
    health: Optional[str] = None
    pri: Optional[int] = None
    rep: Optional[int] = None
    docs_count: Optional[int] = None
    store_size: Optional[str] = None
    pri_store_size: Optional[str] = None
    creation_date: Optional[str] = None
    field_count: Optional[int] = None
    nesting_depth: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert index info to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "health": self.health,
            "pri": self.pri,
            "rep": self.rep,
            "docs_count": self.docs_count,
            "store_size": self.store_size,
            "pri_store_size": self.pri_store_size,
            "creation_date": self.creation_date,
            "field_count": self.field_count,
            "nesting_depth": self.nesting_depth,
        }


@dataclass
class ShardInfo:
    """Information about a shard."""
    index: str
    shard: int
    prirep: str
    state: str
    docs: Optional[int] = None
    store: Optional[str] = None
    node: Optional[str] = None
    unassigned_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert shard info to dictionary."""
        return {
            "index": self.index,
            "shard": self.shard,
            "prirep": self.prirep,
            "state": self.state,
            "docs": self.docs,
            "store": self.store,
            "node": self.node,
            "unassigned_reason": self.unassigned_reason,
        }


@dataclass
class ClusterInfo:
    """Information about the cluster."""
    name: str
    status: str
    number_of_nodes: int
    active_primary_shards: int
    active_shards: int
    relocating_shards: int
    initializing_shards: int
    unassigned_shards: int
    active_shards_percent: float
    documents_count: int
    store_size: str
    pending_tasks: int
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert cluster info to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "number_of_nodes": self.number_of_nodes,
            "active_primary_shards": self.active_primary_shards,
            "active_shards": self.active_shards,
            "relocating_shards": self.relocating_shards,
            "initializing_shards": self.initializing_shards,
            "unassigned_shards": self.unassigned_shards,
            "active_shards_percent": self.active_shards_percent,
            "documents_count": self.documents_count,
            "store_size": self.store_size,
            "pending_tasks": self.pending_tasks,
            "version": self.version,
        }


@dataclass
class DiagnosticData:
    """Container for all parsed diagnostic data."""
    cluster: Optional[ClusterInfo] = None
    nodes: List[NodeInfo] = field(default_factory=list)
    indices: List[IndexInfo] = field(default_factory=list)
    shards: List[ShardInfo] = field(default_factory=list)
    manifest: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert diagnostic data to dictionary."""
        return {
            "cluster": self.cluster.to_dict() if self.cluster else None,
            "nodes": [n.to_dict() for n in self.nodes],
            "indices": [i.to_dict() for i in self.indices],
            "shards": [s.to_dict() for s in self.shards],
            "manifest": self.manifest,
        }


@dataclass
class HealthSummary:
    """Summary of health check results."""
    score: int
    critical_count: int
    warning_count: int
    info_count: int
    total_checks: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "score": self.score,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "total_checks": self.total_checks,
        }


@dataclass
class HealthReport:
    """Complete health check report."""
    timestamp: str
    cluster_name: str
    summary: HealthSummary
    issues: List[HealthCheck] = field(default_factory=list)
    data: Optional[DiagnosticData] = None

    def get_issues_by_severity(self, severity: Severity) -> List[HealthCheck]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]

    def get_issues_by_category(self, category: str) -> List[HealthCheck]:
        """Get all issues in a specific category."""
        return [issue for issue in self.issues if issue.category == category]

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "cluster_name": self.cluster_name,
            "timestamp": self.timestamp,
            "summary": self.summary.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
            "details": self.data.to_dict() if self.data else None,
        }
