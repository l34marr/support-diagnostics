# ELK Diagnostic Data Analysis & Health Check Report

## Overview

This document outlines the plan for creating scripts that analyze ELK (Elasticsearch, Logstash, Kibana) diagnostic data collected by the Elastic Support Diagnostics Utility and generate comprehensive health check reports.

## Background

The Elastic Support Diagnostics Utility collects extensive diagnostic data from running ELK clusters:

- **REST API Data**: Cluster state, node stats, indices stats, shards, allocation, settings, etc.
- **System Calls**: OS metrics (CPU, memory, disk I/O, network), process information, JVM thread dumps
- **Log Files**: Application logs, GC logs, slow logs
- **Monitoring Data**: Time-series metrics (optional export up to 12 hours)

Data is packaged as ZIP archives in the format: `<type>-diagnostics-<timestamp>.zip`

## Purpose

The analysis scripts will:

1. **Parse** diagnostic archive contents
2. **Evaluate** cluster health based on configuration and performance metrics
3. **Identify** common issues and anomalies
4. **Generate** actionable health check reports with recommendations

## Diagnostic Data Structure

### Archive Contents

```
<type>-diagnostics-<timestamp>.zip
├── diagnostics.log              # Execution log with errors/warnings
├── manifest.json               # Inventory of collected items
├── cat/                       # Cat API outputs (text format)
│   ├── cat_health.txt
│   ├── cat_nodes.txt
│   ├── cat_indices.txt
│   ├── cat_shards.txt
│   ├── cat_allocation.txt
│   └── ...
├── syscalls/                  # OS command outputs
│   ├── top.txt
│   ├── netstat.txt
│   ├── iostat.txt
│   ├── process-list.txt
│   └── ...
├── logs/                      # Log files (if collected)
│   ├── elasticsearch.log
│   ├── gc.log
│   └── ...
└── [API endpoints].json        # REST API responses
    ├── nodes.json
    ├── cluster_state.json
    ├── indices_stats.json
    ├── shards.json
    └── ...
```

### Key Data Sources

#### 1. Cluster Health (`cat_health.txt`)
- Cluster status (green/yellow/red)
- Number of nodes
- Shards (active, relocating, initializing, unassigned)
- Documents count
- Store size
- Pending tasks

#### 2. Node Information (`cat_nodes.txt`, `nodes.json`)
- Node names, roles (master, data, ingest, coordinating)
- CPU usage, load averages
- JVM heap used/available
- Disk usage, disk I/O
- Network I/O
- Thread pools queue/rejected counts

#### 3. Index/Shard Information (`cat_indices.txt`, `cat_shards.txt`, `shards.json`)
- Index health status
- Shard distribution across nodes
- Relocating/initializing shards
- Unassigned shards with reasons
- Index sizes and document counts

#### 4. System Metrics (`syscalls/`)
- **top.txt**: Process CPU, memory usage
- **netstat.txt**: Network connections, listening ports
- **iostat.txt**: Disk I/O statistics
- **process-list.txt**: Running processes

#### 5. Log Analysis (`logs/`)
- Error and warning patterns
- GC behavior
- Slow query patterns
- Configuration errors

## Health Check Categories

### 1. Cluster Health Checks

| Check | Data Source | Threshold | Severity |
|-------|-------------|-----------|----------|
| Cluster Status | `cat_health.txt` | Yellow/Red | Critical |
| Active Shards | `cat_shards.txt` | < 90% of total | Warning |
| Unassigned Shards | `cat_shards.txt` | Any | Critical |
| Relocating Shards | `cat_shards.txt` | Any | Warning |
| Shard Balance | `cat_shards.txt` | Imbalance > 20% | Warning |
| Pending Tasks | `cat_pending_tasks.txt` | Count > 100 | Warning |

### 2. Node Health Checks

| Check | Data Source | Threshold | Severity |
|-------|-------------|-----------|----------|
| Heap Usage | `nodes.json` | > 85% | Critical |
| CPU Usage | `nodes.json` | > 80% avg | Warning |
| Load Average | `cat_nodes.txt` | > CPU cores | Warning |
| Disk Usage | `nodes.json` | > 80% | Warning |
| Thread Pool Rejections | `nodes.json` | Any | Critical |
| Circuit Breakers | `nodes.json` | Any | Critical |
| JVM GC Duration | `gc.log` | > 10s | Warning |
| Long GC Pauses | `gc.log` | > 30s | Critical |

### 3. Index Health Checks

| Check | Data Source | Threshold | Severity |
|-------|-------------|-----------|----------|
| Red Indices | `cat_indices.txt` | Any | Critical |
| Yellow Indices | `cat_indices.txt` | Any | Warning |
| Large Indices | `cat_indices.txt` | > 100GB | Warning |
| Many Small Indices | `cat_indices.txt` | > 1000 indices, avg < 1GB | Warning |
| Too Many Fields | `indices_stats.json` | > 1000 fields | Warning |
| Deep Nesting | `indices_stats.json` | > 20 levels | Warning |
| Replication Delays | `cat_indices.txt` | pri - rep > 0 | Warning |

### 4. Configuration Best Practices

| Check | Data Source | Recommendation | Severity |
|-------|-------------|----------------|----------|
| Master-eligible Nodes | `nodes.json` | 3 or 5 (odd numbers) | Warning |
| Minimum Master Nodes | `cluster_state.json` | Set correctly | Warning |
| Memory Locking | `syscalls/` | mlockall enabled | Info |
| Swap Disabled | `syscalls/` | swapoff | Warning |
| File Descriptors | `process-list.txt` | ulimit > 65535 | Warning |
| Refresh Interval | `indices_stats.json` | Default 1s | Info |
| Shard Count | `indices_stats.json` | 10-50 per GB | Warning |

### 5. Performance Issues

| Check | Data Source | Pattern | Severity |
|-------|-------------|---------|----------|
| Slow Queries | `logs/` | Duration > 5s | Warning |
| High Rejection Rate | `nodes.json` | > 1% | Critical |
| Contention | `nodes.json` | Bulk/Queue > 1000 | Warning |
| Search Latency | `nodes.json` | P95 > 5s | Warning |
| Indexing Latency | `nodes.json` | P95 > 30s | Warning |

## Analysis Script Requirements

### Primary Script: `analyze_diagnostic.py`

**Language**: Python 3.8+

**Dependencies**:
```python
# Standard library
import json
import zipfile
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Third-party
import pandas as pd  # For data analysis and tabular reports
import yaml          # For parsing configuration files
```

### Core Features

#### 1. Archive Extraction

```python
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
```

#### 2. Data Parsing

**Text Files** (`cat/*.txt`):
- Parse space-separated columns with headers
- Handle multi-line records
- Extract metrics by column name

**JSON Files**:
- Parse JSON responses
- Extract nested metrics (nodes, indices, etc.)
- Normalize time-series data if present

**Log Files**:
- Parse structured logs (JSON format)
- Extract timestamp, level, message
- Pattern matching for errors/warnings

#### 3. Health Check Engine

```python
class HealthCheck:
    def __init__(self, name: str, severity: str):
        self.name = name
        self.severity = severity  # 'critical', 'warning', 'info'
        self.description = ""
        self.evidence = {}
        self.recommendation = ""

    def failed(self) -> bool:
        """Return True if health check failed."""
```

#### 4. Analysis Pipeline

```python
def analyze_diagnostic(archive_path: str) -> HealthReport:
    """
    Main analysis pipeline:

    1. Extract archive
    2. Parse all data sources
    3. Run health checks by category
    4. Aggregate results
    5. Generate report
    """
```

## Report Generation

### Output Formats

#### 1. Markdown Report (`health_report.md`)

```markdown
# Cluster Health Check Report

## Executive Summary
- **Cluster Status**: ⚠️ Yellow
- **Critical Issues**: 3
- **Warnings**: 12
- **Info**: 5
- **Overall Score**: 65/100

## Critical Issues
### 1. High Heap Usage (95%)
- **Node**: node-1
- **Evidence**: heap_used_percent = 95
- **Recommendation**: Increase heap or reduce load

...

## Warnings
...

## Node Health
...

## Index Health
...
```

#### 2. JSON Report (`health_report.json`)

```json
{
  "cluster_name": "production-cluster",
  "timestamp": "2026-01-19T23:00:00Z",
  "summary": {
    "score": 65,
    "critical_count": 3,
    "warning_count": 12,
    "info_count": 5
  },
  "issues": [
    {
      "check": "high_heap_usage",
      "severity": "critical",
      "node": "node-1",
      "value": 95,
      "threshold": 85,
      "recommendation": "Increase heap or reduce load"
    }
  ],
  "details": {
    "nodes": [...],
    "indices": [...],
    "configuration": {...}
  }
}
```

#### 3. HTML Report (Optional)

Interactive dashboard with:
- Issue summary cards
- Expandable details
- Severity color-coding
- Visualizations (charts, graphs)

## Implementation Plan

### Phase 1: Core Parsing Engine (Week 1-2)

**Tasks**:
1. Set up project structure
2. Implement archive extraction
3. Create parsers for:
   - Cat API text files
   - JSON API responses
   - Log files
4. Build data model classes
5. Unit tests for parsing

**Deliverables**:
- `diagnostic_parser.py` - Core parsing module
- `data_models.py` - Data structures
- `test_parser.py` - Test suite

### Phase 2: Health Check Engine (Week 3-4)

**Tasks**:
1. Implement `HealthCheck` base class
2. Create health check registry
3. Implement checks for:
   - Cluster health (5 checks)
   - Node health (8 checks)
   - Index health (7 checks)
4. Add threshold configuration
5. Integration tests

**Deliverables**:
- `health_checks/` - Check modules
- `check_registry.py` - Registry
- `test_health_checks.py` - Test suite

### Phase 3: Report Generation (Week 5)

**Tasks**:
1. Implement Markdown report generator
2. Implement JSON report generator
3. Add score calculation algorithm
4. Create issue prioritization
5. Add recommendation engine

**Deliverables**:
- `report_generators/` - Report modules
- `report.md` template
- `report.json` schema

### Phase 4: CLI Tool & Integration (Week 6)

**Tasks**:
1. Create main CLI entry point
2. Add argument parsing
3. Implement batch processing (multiple archives)
4. Add monitoring data analysis (optional)
5. Documentation

**Deliverables**:
- `analyze_diagnostic.py` - Main script
- `README.md` - User guide
- `EXAMPLES.md` - Usage examples

## Script Structure

```
report/
├── README.md                           # This file
├── scripts/
│   ├── analyze_diagnostic.py            # Main CLI script
│   ├── diagnostic_parser.py             # Archive & data parsing
│   ├── data_models.py                  # Data structures
│   ├── health_checks/
│   │   ├── __init__.py
│   │   ├── base.py                     # HealthCheck base class
│   │   ├── cluster_health.py            # Cluster-level checks
│   │   ├── node_health.py               # Node-level checks
│   │   ├── index_health.py              # Index-level checks
│   │   ├── configuration.py             # Configuration checks
│   │   └── performance.py               # Performance checks
│   ├── report_generators/
│   │   ├── __init__.py
│   │   ├── markdown.py                 # Markdown report
│   │   ├── json_report.py               # JSON report
│   │   └── html.py                     # HTML report (optional)
│   └── utils/
│       ├── __init__.py
│       ├── thresholds.py                 # Threshold configuration
│       └── recommendations.py           # Recommendation library
├── tests/
│   ├── test_parser.py
│   ├── test_health_checks.py
│   └── test_report_generation.py
└── config/
    ├── thresholds.yml                   # Default thresholds
    └── recommendations.yml              # Recommendations library
```

## Configuration

### Thresholds (`config/thresholds.yml`)

```yaml
cluster:
  active_shards_percent:
    warning: 90
    critical: 70
  unassigned_shards:
    critical: 0  # Any unassigned is critical
  relocating_shards:
    warning: 0
    critical: 50

node:
  heap_used_percent:
    warning: 75
    critical: 85
  cpu_percent:
    warning: 70
    critical: 90
  disk_used_percent:
    warning: 75
    critical: 90

index:
  red_indices:
    critical: 0  # Any red is critical
  yellow_indices:
    warning: 0
  shard_count_per_gb:
    warning_min: 5
    warning_max: 50
```

### Recommendations (`config/recommendations.yml`)

```yaml
high_heap_usage:
  severity: critical
  message: "JVM heap usage exceeds threshold"
  recommendations:
    - "Increase heap size: -Xmx parameter"
    - "Check for memory leaks via heap dump analysis"
    - "Reduce concurrent queries or indexing load"
    - "Review field data cache size"
    - "Check circuit breaker rejections"

too_many_shards:
  severity: warning
  message: "Shard count per GB exceeds recommended range (10-50)"
  recommendations:
    - "Consider reducing shard count via shrink API"
    - "Use index lifecycle management (ILM)"
    - "Review hot/warm/cold architecture"
    - "Consider rollover for time-series data"
```

## Usage Examples

### Basic Usage

```bash
# Analyze a single diagnostic archive
python scripts/analyze_diagnostic.py /path/to/elasticsearch-diagnostics-20260119.zip

# Output: health_report.md and health_report.json
```

### Advanced Usage

```bash
# Custom output directory
python scripts/analyze_diagnostic.py \
    /path/to/archive.zip \
    --output /path/to/reports \
    --format json,markdown

# Custom thresholds
python scripts/analyze_diagnostic.py \
    archive.zip \
    --config thresholds_custom.yml

# Batch processing
python scripts/analyze_diagnostic.py \
    --batch /path/to/archives/ \
    --output /path/to/reports/

# Verbose output
python scripts/analyze_diagnostic.py \
    archive.zip \
    --verbose \
    --log-level debug
```

### Integration with Monitoring Data

```bash
# Analyze with time-series monitoring data
python scripts/analyze_diagnostic.py \
    archive.zip \
    --monitoring-export /path/to/monitoring-export.zip \
    --analyze-trends
```

## Monitoring Data Analysis (Optional Enhancement)

For enhanced health checks, integrate with monitoring export data:

- **Trend Analysis**: Identify performance degradation over time
- **Anomaly Detection**: Find unusual patterns in metrics
- **Capacity Planning**: Forecast resource exhaustion
- **Historical Comparison**: Compare current vs. previous state

### Enhanced Checks with Monitoring

| Check | Data | Analysis |
|-------|------|----------|
| CPU Trend | `node_stats` | Linear regression over 12h window |
| Memory Growth | `node_stats` | Identify memory leaks |
| Indexing Rate | `indices_stats` | Detect throughput drops |
| Search Latency | `indices_stats` | P95/P99 trends |
| Shard Movement | `cluster_stats` | Frequent rebalancing |

## Testing Strategy

### Unit Tests

- Parse sample diagnostic files from `src/test/resources/`
- Test each health check individually with mock data
- Verify threshold evaluation logic

### Integration Tests

- End-to-end analysis of real diagnostic archives
- Compare results with known good outputs
- Validate report generation

### Regression Tests

- Maintain test suite with known issues
- Ensure fixes don't introduce regressions
- Performance benchmarks for large archives

## Future Enhancements

### Short-term

1. **Kibana Health Checks**: Extend to Kibana diagnostics
2. **Logstash Health Checks**: Extend to Logstash diagnostics
3. **Historical Comparison**: Compare multiple archives over time
4. **Severity Tuning**: ML-based priority scoring

### Long-term

1. **ML-based Anomaly Detection**: Train on historical diagnostics
2. **Predictive Analysis**: Forecast issues before they occur
3. **Automated Remediation**: Suggest automated fix commands
4. **Interactive Dashboard**: Real-time health monitoring UI

## References

- [Elastic Support Diagnostics Utility README](../README.md)
- [Elasticsearch Cat APIs](https://www.elastic.co/guide/en/elasticsearch/reference/current/cat.html)
- [Cluster Health API](https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-health.html)
- [Nodes Stats API](https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-nodes-stats.html)
- [Best Practices](https://www.elastic.co/guide/en/elasticsearch/reference/current/setup-configuration-memory.html)

## License

Same as parent project: Elastic License v2
