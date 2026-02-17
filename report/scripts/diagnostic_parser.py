"""
Diagnostic archive parser for ELK diagnostic data.
Extracts and parses diagnostic ZIP archives.
"""

import json
import zipfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

from data_models import (
    DiagnosticData, ClusterInfo, NodeInfo, IndexInfo, ShardInfo
)


def extract_archive(archive_path: str, extract_to: str) -> Dict[str, Path]:
    """
    Extract diagnostic ZIP archive and return file mapping.

    Returns:
        {
            'cat_health': Path('cat/cat_health.txt'),
            'nodes': Path('nodes.json'),
            ...
        }
    """
    archive_file = Path(archive_path)
    extract_dir = Path(extract_to)

    if not archive_file.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_file, 'r') as zf:
        zf.extractall(extract_dir)

    file_map = {}

    for file_path in extract_dir.rglob('*'):
        if file_path.is_file():
            rel_path = file_path.relative_to(extract_dir)

            key = None
            if str(rel_path).startswith('cat/'):
                key = rel_path.stem.replace('cat_', '')
            elif str(rel_path).startswith('syscalls/'):
                key = f"syscall_{rel_path.stem}"
            elif str(rel_path).startswith('logs/'):
                key = f"log_{rel_path.stem}"
            elif file_path.suffix == '.json':
                key = rel_path.stem

            if key:
                file_map[key] = file_path

    file_map['root'] = extract_dir
    return file_map


def parse_cat_text_file(file_path: Optional[Path]) -> List[Dict[str, str]]:
    """
    Parse cat API text files with space-separated columns.

    Returns list of dictionaries mapping column names to values.
    """
    if not file_path or not file_path.exists():
        return []

    data = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    columns = None

    for i, line in enumerate(lines):
        line = line.strip()

        if not line or line.startswith('['):
            continue

        if i == 0:
            columns = re.split(r'\s{2,}', line)
            continue

        if columns is None:
            continue

        values = re.split(r'\s{2,}', line)

        if len(values) == len(columns):
            row = dict(zip(columns, values))
            data.append(row)

    return data


def parse_json_file(file_path: Optional[Path]) -> Optional[Any]:
    """Parse JSON file and return data."""
    if not file_path or not file_path.exists():
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def parse_cluster_health(cat_health_data: List[Dict[str, str]]) -> Optional[ClusterInfo]:
    """Parse cluster health from cat_health.txt data."""
    if not cat_health_data:
        return None

    row = cat_health_data[0]

    status = row.get('status', 'unknown')
    name = row.get('cluster_name', 'unknown')

    cluster = ClusterInfo(
        name=name,
        status=status,
        number_of_nodes=int(row.get('node.total', 0) or 0),
        active_primary_shards=int(row.get('shards.primary', 0) or 0),
        active_shards=int(row.get('shards.active', 0) or 0),
        relocating_shards=int(row.get('shards.relocating', 0) or 0),
        initializing_shards=int(row.get('shards.initializing', 0) or 0),
        unassigned_shards=int(row.get('shards.unassigned', 0) or 0),
        active_shards_percent=float(row.get('shards.active %', '100').replace('%', '')),
        documents_count=_parse_int(row.get('docs.count')) or 0,
        store_size=row.get('store.size', '0b'),
        pending_tasks=int(row.get('pending_tasks', 0) or 0),
    )

    return cluster


def parse_nodes(cat_nodes_data: List[Dict[str, str]],
               nodes_json: Optional[Dict[str, Any]]) -> List[NodeInfo]:
    """Parse node information from cat_nodes.txt and nodes.json."""
    nodes = []

    node_dict = {}

    if cat_nodes_data:
        for row in cat_nodes_data:
            name = row.get('name', 'unknown')

            node_dict[name] = NodeInfo(
                name=name,
                cpu_percent=_parse_percent(row.get('cpu')),
                heap_used_percent=_parse_percent(row.get('heap.percent')),
                heap_used=row.get('heap.ram'),
                heap_max=row.get('heap.max'),
                disk_used_percent=_parse_percent(row.get('disk.used_percent')),
                disk_total=row.get('disk.total'),
                disk_used=row.get('disk.used'),
                load_1m=_parse_float(row.get('load_1m')),
                load_5m=_parse_float(row.get('load_5m')),
                load_15m=_parse_float(row.get('load_15m')),
                roles=row.get('node.role', '').split('&') if row.get('node.role') else [],
                version=row.get('version'),
            )

    if nodes_json:
        for node_name, node_data in nodes_json.get('nodes', {}).items():
            if node_name in node_dict:
                info = node_dict[node_name]

                jvm = node_data.get('jvm', {})
                mem = jvm.get('mem', {})
                gc = jvm.get('gc', {}).get('collectors', {})

                if not info.heap_used_percent:
                    heap_used = mem.get('heap_used_in_bytes', 0)
                    heap_max = mem.get('heap_max_in_bytes', 1)
                    info.heap_used_percent = (heap_used / heap_max * 100) if heap_max > 0 else 0

                info.heap_used = _format_bytes(mem.get('heap_used_in_bytes'))
                info.heap_max = _format_bytes(mem.get('heap_max_in_bytes'))

                old_gc = gc.get('old', {})
                young_gc = gc.get('young', {})
                info.gc_old_collection_time = old_gc.get('collection_time_in_millis')
                info.gc_young_collection_time = young_gc.get('collection_time_in_millis')

                thread_pool = node_data.get('thread_pool', {})
                rejections = {}
                for pool_name, pool_data in thread_pool.items():
                    rejected = pool_data.get('rejected', 0)
                    if rejected > 0:
                        rejections[pool_name] = rejected
                info.thread_pool_rejections = rejections

                circuit_breakers = node_data.get('breakers', {})
                cb_data = {}
                for cb_name, cb_info in circuit_breakers.items():
                    if cb_info.get('tripped'):
                        cb_data[cb_name] = {
                            'limit': _format_bytes(cb_info.get('limit_size_in_bytes')),
                            'estimated': _format_bytes(cb_info.get('estimated_size_in_bytes')),
                        }
                info.circuit_breakers = cb_data

            else:
                roles = node_data.get('roles', [])
                jvm = node_data.get('jvm', {})
                os = node_data.get('os', {})

                info = NodeInfo(
                    name=node_name.split('/')[-1],
                    roles=roles,
                    heap_used_percent=_parse_percent(jvm.get('mem', {}).get('heap_used_percent')),
                    heap_used=_format_bytes(jvm.get('mem', {}).get('heap_used_in_bytes')),
                    heap_max=_format_bytes(jvm.get('mem', {}).get('heap_max_in_bytes')),
                    cpu_percent=os.get('cpu', {}).get('percent'),
                    load_1m=os.get('cpu', {}).get('load_average', {}).get('1m'),
                    load_5m=os.get('cpu', {}).get('load_average', {}).get('5m'),
                    load_15m=os.get('cpu', {}).get('load_average', {}).get('15m'),
                    version=node_data.get('version'),
                )
                node_dict[info.name] = info

    nodes.extend(node_dict.values())
    return nodes


def parse_indices(cat_indices_data: List[Dict[str, str]],
                 indices_stats: Optional[Dict[str, Any]]) -> List[IndexInfo]:
    """Parse index information from cat_indices.txt and indices_stats.json."""
    indices = {}

    if cat_indices_data:
        for row in cat_indices_data:
            name = row.get('index', 'unknown')

            indices[name] = IndexInfo(
                name=name,
                health=row.get('health'),
                status=row.get('status'),
                pri=_parse_int(row.get('pri')),
                rep=_parse_int(row.get('rep')),
                docs_count=_parse_int(row.get('docs.count')),
                store_size=row.get('store.size'),
                pri_store_size=row.get('pri.store.size'),
                creation_date=row.get('creation.date'),
            )

    if indices_stats:
        for index_name, index_data in indices_stats.get('indices', {}).items():
            if index_name in indices:
                info = indices[index_name]

                mappings = index_data.get('mappings', {})
                field_count = len(mappings.get('properties', {}))
                info.field_count = field_count

                max_depth = _calculate_nesting_depth(mappings.get('properties', {}))
                info.nesting_depth = max_depth

    return list(indices.values())


def parse_shards(cat_shards_data: List[Dict[str, str]],
                shards_json: Optional[Dict[str, Any]]) -> List[ShardInfo]:
    """Parse shard information from cat_shards.txt and shards.json."""
    shards = []

    if cat_shards_data:
        for row in cat_shards_data:
            shard = ShardInfo(
                index=row.get('index', 'unknown'),
                shard=_parse_int(row.get('shard')) or 0,
                prirep=row.get('prirep', 'p'),
                state=row.get('state', 'unknown'),
                docs=_parse_int(row.get('docs')),
                store=row.get('store'),
                node=row.get('node'),
            )
            shards.append(shard)

    return shards


def parse_logs(log_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Parse log files and extract errors, warnings, and patterns."""
    logs = {}

    log_files = list(log_dir.glob('*.log')) if log_dir.exists() else []

    for log_file in log_files:
        log_name = log_file.stem
        entries = []

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    level = None
                    if 'ERROR' in line:
                        level = 'error'
                    elif 'WARN' in line:
                        level = 'warning'

                    if level:
                        entries.append({
                            'line': line,
                            'level': level,
                        })
        except Exception:
            pass

        if entries:
            logs[log_name] = entries

    return logs


def parse_gc_log(log_dir: Path) -> Dict[str, Any]:
    """Parse GC log for long pauses and durations."""
    gc_data = {
        'long_gc_pauses': [],
        'total_gc_time': 0,
    }

    gc_log = log_dir / 'gc.log'
    if not gc_log.exists():
        gc_log = log_dir / 'gc.log.0'

    if not gc_log.exists():
        return gc_data

    try:
        with open(gc_log, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()

                match = re.search(r'\[.*?:(\d+\.?\d*)\]', line)
                if match:
                    duration = float(match.group(1))
                    gc_data['total_gc_time'] += duration

                    if duration > 10:
                        gc_data['long_gc_pauses'].append({
                            'duration': duration,
                            'line': line[:200],
                        })
    except Exception:
        pass

    return gc_data


def parse_diagnostic_archive(archive_path: str) -> DiagnosticData:
    """
    Main parsing pipeline for diagnostic archive.

    Returns DiagnosticData object with all parsed information.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        file_map = extract_archive(archive_path, temp_dir)

        data = DiagnosticData()

        manifest_data = parse_json_file(file_map.get('manifest'))
        data.manifest = manifest_data if manifest_data else {}

        cat_health_data = parse_cat_text_file(file_map.get('cat_health'))
        data.cluster = parse_cluster_health(cat_health_data)

        cat_nodes_data = parse_cat_text_file(file_map.get('cat_nodes'))
        nodes_json = parse_json_file(file_map.get('nodes'))
        data.nodes = parse_nodes(cat_nodes_data, nodes_json)

        cat_indices_data = parse_cat_text_file(file_map.get('cat_indices'))
        indices_stats = parse_json_file(file_map.get('indices_stats'))
        data.indices = parse_indices(cat_indices_data, indices_stats)

        cat_shards_data = parse_cat_text_file(file_map.get('cat_shards'))
        shards_json = parse_json_file(file_map.get('shards'))
        data.shards = parse_shards(cat_shards_data, shards_json)

        logs_dir = file_map['root'] / 'logs'
        data.raw_data['logs'] = parse_logs(logs_dir)
        data.raw_data['gc_log'] = parse_gc_log(logs_dir)

        return data


def _parse_percent(value: Optional[str]) -> Optional[float]:
    """Parse percentage string to float."""
    if not value:
        return None
    try:
        return float(value.replace('%', ''))
    except (ValueError, AttributeError):
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Parse string to float."""
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, AttributeError):
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Parse string to int."""
    if not value:
        return None
    try:
        return int(value.replace(',', ''))
    except (ValueError, AttributeError):
        return None


def _format_bytes(bytes_value: Optional[int]) -> Optional[str]:
    """Format bytes to human-readable string."""
    if not bytes_value or bytes_value == 0:
        return None

    units = ['b', 'kb', 'mb', 'gb', 'tb', 'pb']
    size = float(bytes_value)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f}{units[unit_index]}"


def _calculate_nesting_depth(properties: Dict[str, Any], depth: int = 1) -> int:
    """Calculate maximum nesting depth of fields in mappings."""
    if not properties:
        return 0

    max_depth = depth

    for field_name, field_def in properties.items():
        if 'properties' in field_def:
            nested_depth = _calculate_nesting_depth(field_def['properties'], depth + 1)
            max_depth = max(max_depth, nested_depth)

    return max_depth
