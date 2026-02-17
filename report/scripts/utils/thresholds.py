"""
Threshold configuration loader.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_THRESHOLDS = {
    'cluster': {
        'active_shards_percent': {'warning': 90.0, 'critical': 70.0},
        'unassigned_shards': {'critical': 0},
        'relocating_shards': {'warning': 0, 'critical': 50},
        'pending_tasks': {'warning': 100},
    },
    'node': {
        'heap_used_percent': {'warning': 75.0, 'critical': 85.0},
        'cpu_percent': {'warning': 70.0, 'critical': 90.0},
        'disk_used_percent': {'warning': 80.0, 'critical': 90.0},
        'gc_duration': {'warning': 10.0, 'critical': 30.0},
        'long_gc_pause': {'critical': 30.0},
    },
    'index': {
        'large_index_gb': {'warning': 100.0},
        'many_small_indices': {'count': 1000, 'avg_size_gb': 1.0},
        'field_count': {'warning': 1000},
        'nesting_depth': {'warning': 20},
    },
}


def load_thresholds(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load threshold configuration from YAML file or use defaults.

    Returns threshold configuration dictionary.
    """
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or DEFAULT_THRESHOLDS

    return DEFAULT_THRESHOLDS
