"""
Recommendations library loader.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

DEFAULT_RECOMMENDATIONS = {
    'high_heap_usage': {
        'message': 'JVM heap usage exceeds threshold',
        'recommendations': [
            'Increase heap size: -Xmx parameter',
            'Check for memory leaks via heap dump analysis',
            'Reduce concurrent queries or indexing load',
            'Review field data cache size',
            'Check circuit breaker rejections',
        ],
    },
    'cluster_status': {
        'message': 'Cluster is not healthy',
        'recommendations': [
            'Check unassigned shards and node failures',
            'Ensure all nodes are healthy and running',
            'Review cluster state',
        ],
    },
    'unassigned_shards': {
        'message': 'Unassigned shards detected',
        'recommendations': [
            'Use allocation explain API to determine cause',
            'Check disk space on all nodes',
            'Verify node capacity and health',
            'Review shard allocation settings',
        ],
    },
    'thread_pool_rejections': {
        'message': 'Thread pool rejections detected',
        'recommendations': [
            'Increase thread pool sizes',
            'Reduce concurrent operations',
            'Check for resource saturation',
            'Review JVM heap settings',
        ],
    },
    'circuit_breakers': {
        'message': 'Circuit breakers tripped',
        'recommendations': [
            'Reduce request size',
            'Increase circuit breaker limits',
            'Check for memory leaks',
            'Review field data and caching',
        ],
    },
    'red_indices': {
        'message': 'Red indices detected',
        'recommendations': [
            'Investigate shard allocation issues',
            'Check node health and disk space',
            'Review index configuration',
            'Check for failed shard recovery',
        ],
    },
}


def load_recommendations(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load recommendations from YAML file or use defaults.

    Returns recommendations dictionary.
    """
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or DEFAULT_RECOMMENDATIONS

    return DEFAULT_RECOMMENDATIONS


def get_recommendations(check_name: str, recommendations: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get recommendations for a specific health check.

    Returns recommendation dictionary with message and list of recommendations.
    """
    if not recommendations:
        recommendations = load_recommendations()

    return recommendations.get(check_name, {
        'message': 'Issue detected',
        'recommendations': ['Review the issue and investigate further'],
    })
