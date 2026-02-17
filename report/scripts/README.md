# ELK Diagnostic Analysis Scripts

This directory contains Python scripts for analyzing ELK (Elasticsearch, Logstash, Kibana) diagnostic archives.

## Directory Structure

```
scripts/
├── analyze_diagnostic.py          # Main CLI entry point
├── diagnostic_parser.py           # Archive and data parsing
├── data_models.py                # Data model classes
├── check_registry.py             # Health check registry
├── health_checks/                 # Health check implementations
│   ├── base.py                  # Base health check class
│   ├── cluster_health.py         # Cluster-level checks
│   ├── node_health.py            # Node-level checks
│   ├── index_health.py           # Index-level checks
│   ├── configuration.py          # Configuration checks
│   └── performance.py            # Performance checks
├── report_generators/            # Report generation
│   ├── markdown.py               # Markdown report generator
│   └── json_report.py            # JSON report generator
└── utils/                        # Utility modules
    ├── thresholds.py             # Threshold configuration loader
    └── recommendations.py         # Recommendation library loader

tests/                              # Unit and integration tests
config/                             # Configuration files
    ├── thresholds.yml            # Default thresholds
    └── recommendations.yml         # Default recommendations
```

## Usage

```bash
# Analyze a diagnostic archive
python scripts/analyze_diagnostic.py /path/to/elasticsearch-diagnostics-20260119.zip

# With custom output directory
python scripts/analyze_diagnostic.py archive.zip --output /path/to/reports

# With custom thresholds
python scripts/analyze_diagnostic.py archive.zip --config thresholds.yml

# JSON report only
python scripts/analyze_diagnostic.py archive.zip --format json

# Both reports
python scripts/analyze_diagnostic.py archive.zip --format json,markdown --verbose
```

## Health Checks

The tool implements the following health check categories:

### Cluster Health (5 checks)
- Cluster Status (green/yellow/red)
- Active Shards Percentage
- Unassigned Shards
- Relocating Shards
- Pending Tasks

### Node Health (8 checks)
- Heap Usage
- CPU Usage
- Load Average
- Disk Usage
- Thread Pool Rejections
- Circuit Breakers
- GC Duration
- Long GC Pauses

### Index Health (7 checks)
- Red Indices
- Yellow Indices
- Large Indices
- Many Small Indices
- Too Many Fields
- Deep Nesting
- Replication Delays

### Configuration Checks (3 checks)
- Master-eligible Nodes
- Swap Disabled
- File Descriptors

### Performance Checks (5 checks)
- Slow Queries
- High Rejection Rate
- Thread Pool Contention
- Search Latency
- Indexing Latency

## Configuration Files

### thresholds.yml

Defines threshold values for health checks. Format:

```yaml
cluster:
  active_shards_percent:
    warning: 90
    critical: 70
  pending_tasks:
    warning: 100

node:
  heap_used_percent:
    warning: 75
    critical: 85
  cpu_percent:
    warning: 70
    critical: 90

index:
  large_index_gb:
    warning: 100
  field_count:
    warning: 1000
```

### recommendations.yml

Defines recommendations for health issues. Format:

```yaml
high_heap_usage:
  message: JVM heap usage exceeds threshold
  recommendations:
    - Increase heap size: -Xmx parameter
    - Check for memory leaks
    - Reduce concurrent load
```

## Requirements

- Python 3.8+
- pyyaml>=6.0

Install dependencies:

```bash
pip install -r requirements.txt
```

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_parser.py

# Run with verbose output
python -m pytest tests/ -v
```

### Adding New Health Checks

1. Create new check class in appropriate `health_checks/` module
2. Inherit from `BaseHealthCheck`
3. Implement `check()` method
4. Add check to appropriate factory function
5. Add thresholds to `config/thresholds.yml`
6. Add recommendations to `config/recommendations.yml`
7. Add tests in `tests/` directory

See `EXAMPLES.md` for usage details.
