"""
Unit tests for diagnostic parser.
"""

import pytest
import tempfile
import zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from diagnostic_parser import (
    parse_cat_text_file,
    parse_json_file,
    parse_cluster_health,
    parse_nodes,
    parse_indices,
    parse_shards,
    _parse_size_to_gb
)
from data_models import ClusterInfo, NodeInfo, IndexInfo


def test_parse_cat_text_file():
    """Test parsing cat API text files."""
    text = """epoch      timestamp  status       node.total   node.data     shards.active %   shards.relocating
1704289523 2024-01-19T10:00:00Z green                 3             3                 100.0            0
"""

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(text)
        f.flush()
        data = parse_cat_text_file(Path(f.name))

        assert len(data) == 1
        assert data[0]['status'] == 'green'
        assert data[0]['node.total'] == '3'
        assert data[0]['shards.active %'] == '100.0'


def test_parse_cat_text_file_with_comments():
    """Test parsing with comment lines."""
    text = """[2024-01-19T10:00:00Z] Comment line
epoch      timestamp  status       node.total
1704289523 2024-01-19T10:00:00Z green                 3
"""

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(text)
        f.flush()
        data = parse_cat_text_file(Path(f.name))

        assert len(data) == 1
        assert data[0]['status'] == 'green'


def test_parse_json_file():
    """Test JSON file parsing."""
    text = '{"test": "value", "number": 123}'

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write(text)
        f.flush()
        data = parse_json_file(Path(f.name))

        assert data is not None
        assert data['test'] == 'value'
        assert data['number'] == 123


def test_parse_json_file_missing():
    """Test JSON file parsing with missing file."""
    data = parse_json_file(Path('/nonexistent/file.json'))
    assert data is None


def test_parse_cluster_health():
    """Test cluster health parsing."""
    data = [
        {'status': 'yellow', 'node.total': '5', 'shards.active': '10',
         'shards.relocating': '0', 'shards.initializing': '2', 'shards.unassigned': '1',
         'shards.active %': '90.0', 'docs.count': '1000', 'store.size': '10gb',
         'pending_tasks': '5'}
    ]

    cluster = parse_cluster_health(data)

    assert cluster is not None
    assert cluster.status == 'yellow'
    assert cluster.number_of_nodes == 5
    assert cluster.active_shards == 10
    assert cluster.unassigned_shards == 1
    assert cluster.active_shards_percent == 90.0


def test_parse_nodes():
    """Test node parsing."""
    cat_data = [
        {'name': 'node-1', 'heap.percent': '85.5', 'cpu': '45.2',
         'disk.used_percent': '65.3', 'node.role': 'dm', 'version': '8.10.0'},
        {'name': 'node-2', 'heap.percent': '50.0', 'cpu': '30.1',
         'disk.used_percent': '40.0', 'node.role': 'd', 'version': '8.10.0'}
    ]

    nodes_json = {
        'nodes': {
            'node-1': {
                'jvm': {'mem': {'heap_used_in_bytes': 4294967296, 'heap_max_in_bytes': 5368709120}},
                'thread_pool': {'search': {'rejected': 0}, 'write': {'rejected': 5}}
            },
            'node-2': {
                'jvm': {'mem': {'heap_used_in_bytes': 268435456, 'heap_max_in_bytes': 5368709120}},
                'thread_pool': {'search': {'rejected': 0}, 'write': {'rejected': 0}}
            }
        }
    }

    nodes = parse_nodes(cat_data, nodes_json)

    assert len(nodes) == 2
    assert nodes[0].name == 'node-1'
    assert nodes[0].heap_used_percent == pytest.approx(85.5, abs=0.1)
    assert len(nodes[0].thread_pool_rejections) == 1
    assert nodes[0].thread_pool_rejections['write'] == 5


def test_parse_indices():
    """Test index parsing."""
    cat_data = [
        {'index': 'test-1', 'health': 'green', 'status': 'open', 'pri': '3', 'rep': '1',
         'docs.count': '10000', 'store.size': '5gb', 'creation.date': '2024-01-19'},
        {'index': 'test-2', 'health': 'yellow', 'status': 'open', 'pri': '1', 'rep': '0',
         'docs.count': '5000', 'store.size': '500mb', 'creation.date': '2024-01-20'}
    ]

    indices_stats = {
        'indices': {
            'test-1': {
                'mappings': {
                    'properties': {
                        'field1': {'type': 'text'},
                        'nested': {'type': 'object', 'properties': {'inner': {'type': 'text'}}}
                    }
                }
            },
            'test-2': {
                'mappings': {
                    'properties': {'field2': {'type': 'keyword'}}
                }
            }
        }
    }

    indices = parse_indices(cat_data, indices_stats)

    assert len(indices) == 2
    assert indices[0].name == 'test-1'
    assert indices[0].health == 'green'
    assert indices[0].field_count == 2
    assert indices[0].nesting_depth == 2


def test_parse_shards():
    """Test shard parsing."""
    cat_data = [
        {'index': 'test-1', 'shard': '0', 'prirep': 'p', 'state': 'STARTED',
         'docs': '500', 'store': '500mb', 'node': 'node-1'},
        {'index': 'test-1', 'shard': '0', 'prirep': 'r', 'state': 'INITIALIZING',
         'docs': '0', 'store': '0b', 'node': 'node-2'}
    ]

    shards = parse_shards(cat_data, None)

    assert len(shards) == 2
    assert shards[0].index == 'test-1'
    assert shards[0].shard == 0
    assert shards[0].prirep == 'p'
    assert shards[0].state == 'STARTED'


def test_parse_size_to_gb():
    """Test size string parsing."""
    assert _parse_size_to_gb('10gb') == 10.0
    assert _parse_size_to_gb('1024mb') == pytest.approx(1.0, abs=0.1)
    assert _parse_size_to_gb('1tb') == 1024.0
    assert _parse_size_to_gb('500kb') == pytest.approx(0.0005, abs=0.0001)
    assert _parse_size_to_gb('invalid') is None


def test_extract_archive():
    """Test archive extraction."""
    import diagnostic_parser

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / 'test.zip'

        with zipfile.ZipFile(archive_path, 'w') as zf:
            zf.writestr('cat/test.txt', 'test data')
            zf.writestr('nodes.json', '{"nodes": {}}')

        file_map = diagnostic_parser.extract_archive(str(archive_path), tmpdir)

        assert 'cat_test' in file_map or 'cat' in str(file_map.get('root', ''))
        assert 'nodes' in file_map or 'nodes.json' in str(file_map.get('root', ''))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
