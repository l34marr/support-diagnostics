"""
Integration tests for health checks.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from data_models import DiagnosticData, ClusterInfo, NodeInfo, IndexInfo, ShardInfo, Severity
from health_checks.cluster_health import ClusterStatusCheck, UnassignedShardsCheck
from health_checks.node_health import HeapUsageCheck, CPUUsageCheck, ThreadPoolRejectionsCheck
from health_checks.index_health import RedIndicesCheck, YellowIndicesCheck


@pytest.fixture
def sample_data():
    """Create sample diagnostic data for testing."""
    return DiagnosticData(
        cluster=ClusterInfo(
            name='test-cluster',
            status='green',
            number_of_nodes=3,
            active_primary_shards=10,
            active_shards=10,
            relocating_shards=0,
            initializing_shards=0,
            unassigned_shards=0,
            active_shards_percent=100.0,
            documents_count=10000,
            store_size='10gb',
            pending_tasks=5,
            version='8.10.0',
        ),
        nodes=[
            NodeInfo(
                name='node-1',
                roles=['master', 'data'],
                cpu_percent=45.2,
                heap_used_percent=85.5,
                heap_used='4gb',
                heap_max='5gb',
                disk_used_percent=65.3,
                disk_total='500gb',
                disk_used='327gb',
                load_1m=5.2,
                load_5m=4.8,
                load_15m=4.5,
                thread_pool_rejections={'write': 5},
                version='8.10.0',
            ),
            NodeInfo(
                name='node-2',
                roles=['data'],
                cpu_percent=30.1,
                heap_used_percent=45.0,
                heap_used='2gb',
                heap_max='5gb',
                disk_used_percent=40.0,
                disk_total='500gb',
                disk_used='200gb',
                load_1m=3.1,
                load_5m=3.0,
                load_15m=2.8,
                thread_pool_rejections={},
                version='8.10.0',
            ),
        ],
        indices=[
            IndexInfo(
                name='test-index-1',
                health='green',
                status='open',
                pri=3,
                rep=1,
                docs_count=5000,
                store_size='2gb',
                pri_store_size='1gb',
                creation_date='2024-01-19',
                field_count=100,
                nesting_depth=3,
            ),
            IndexInfo(
                name='test-index-2',
                health='red',
                status='open',
                pri=2,
                rep=1,
                docs_count=1000,
                store_size='1gb',
                pri_store_size='500mb',
                creation_date='2024-01-20',
                field_count=500,
                nesting_depth=10,
            ),
            IndexInfo(
                name='test-index-3',
                health='yellow',
                status='open',
                pri=5,
                rep=1,
                docs_count=200,
                store_size='500mb',
                pri_store_size='250mb',
                creation_date='2024-01-21',
                field_count=2000,
                nesting_depth=15,
            ),
        ],
        shards=[
            ShardInfo(
                index='test-index-1',
                shard=0,
                prirep='p',
                state='STARTED',
                docs=500,
                store='500mb',
                node='node-1',
            ),
            ShardInfo(
                index='test-index-1',
                shard=1,
                prirep='r',
                state='STARTED',
                docs=500,
                store='500mb',
                node='node-2',
            ),
            ShardInfo(
                index='test-index-2',
                shard=0,
                prirep='p',
                state='UNASSIGNED',
                docs=0,
                store='0b',
                node=None,
                unassigned_reason='ALLOCATION_FAILED',
            ),
        ],
        raw_data={
            'logs': {
                'elasticsearch.log': [
                    {'line': 'ERROR [node-1] Circuit breaker tripped', 'level': 'error'},
                ]
            },
            'gc_log': {
                'long_gc_pauses': [
                    {'duration': 35.0, 'line': '[GC pause 35.0s]'},
                    {'duration': 12.0, 'line': '[GC pause 12.0s]'},
                ]
            }
        }
    )


def test_cluster_status_green():
    """Test cluster status check with healthy cluster."""
    check = ClusterStatusCheck()
    data = sample_data()
    data.cluster.status = 'green'

    result = check.check(data)
    assert result is None


def test_cluster_status_yellow():
    """Test cluster status check with yellow cluster."""
    check = ClusterStatusCheck()
    data = sample_data()
    data.cluster.status = 'yellow'

    result = check.check(data)
    assert result is not None
    assert result.name == 'cluster_status'
    assert result.severity == Severity.CRITICAL


def test_cluster_status_red():
    """Test cluster status check with red cluster."""
    check = ClusterStatusCheck()
    data = sample_data()
    data.cluster.status = 'red'

    result = check.check(data)
    assert result is not None
    assert result.name == 'cluster_status'
    assert result.description == 'Cluster status is RED'


def test_unassigned_shards():
    """Test unassigned shards check."""
    check = UnassignedShardsCheck()
    data = sample_data()
    data.cluster.unassigned_shards = 1

    result = check.check(data)
    assert result is not None
    assert result.name == 'unassigned_shards'
    assert result.severity == Severity.CRITICAL
    assert '1' in str(result.evidence)


def test_no_unassigned_shards():
    """Test unassigned shards check with no unassigned shards."""
    check = UnassignedShardsCheck()
    data = sample_data()
    data.cluster.unassigned_shards = 0

    result = check.check(data)
    assert result is None


def test_heap_usage_critical():
    """Test heap usage check with critical value."""
    check = HeapUsageCheck(critical_threshold=85.0, warning_threshold=75.0)
    data = sample_data()
    data.nodes[0].heap_used_percent = 95.0

    result = check.check(data)
    assert result is not None
    assert result.severity == Severity.CRITICAL


def test_heap_usage_warning():
    """Test heap usage check with warning value."""
    check = HeapUsageCheck(critical_threshold=85.0, warning_threshold=75.0)
    data = sample_data()
    data.nodes[0].heap_used_percent = 80.0

    result = check.check(data)
    assert result is not None
    assert result.severity == Severity.WARNING


def test_heap_usage_healthy():
    """Test heap usage check with healthy value."""
    check = HeapUsageCheck(critical_threshold=85.0, warning_threshold=75.0)
    data = sample_data()
    data.nodes[0].heap_used_percent = 50.0

    result = check.check(data)
    assert result is None


def test_cpu_usage_warning():
    """Test CPU usage check with warning value."""
    check = CPUUsageCheck(warning_threshold=80.0, critical_threshold=90.0)
    data = sample_data()
    data.nodes[0].cpu_percent = 85.0

    result = check.check(data)
    assert result is not None
    assert result.severity == Severity.WARNING


def test_thread_pool_rejections():
    """Test thread pool rejections check."""
    check = ThreadPoolRejectionsCheck()
    data = sample_data()

    result = check.check(data)
    assert result is not None
    assert result.name == 'thread_pool_rejections'
    assert result.severity == Severity.CRITICAL


def test_no_thread_pool_rejections():
    """Test thread pool rejections check with no rejections."""
    check = ThreadPoolRejectionsCheck()
    data = sample_data()
    data.nodes[0].thread_pool_rejections = {}

    result = check.check(data)
    assert result is None


def test_red_indices():
    """Test red indices check."""
    check = RedIndicesCheck()
    data = sample_data()

    result = check.check(data)
    assert result is not None
    assert result.name == 'red_indices'
    assert result.severity == Severity.CRITICAL


def test_no_red_indices():
    """Test red indices check with no red indices."""
    check = RedIndicesCheck()
    data = sample_data()
    data.indices = [idx for idx in data.indices if idx.health != 'red']

    result = check.check(data)
    assert result is None


def test_yellow_indices():
    """Test yellow indices check."""
    check = YellowIndicesCheck()
    data = sample_data()

    result = check.check(data)
    assert result is not None
    assert result.name == 'yellow_indices'
    assert result.severity == Severity.WARNING


def test_long_gc_pauses():
    """Test long GC pauses check."""
    check = health_checks.performance.GCDurationCheck(warning_threshold=10.0, critical_threshold=30.0)
    data = sample_data()

    result = check.check(data)
    assert result is not None
    assert result.severity == Severity.CRITICAL
