# Usage Examples

## Basic Usage

```bash
# From report directory
cd report

# Analyze a single diagnostic archive
python scripts/analyze_diagnostic.py /path/to/elasticsearch-diagnostics-20260119.zip

# Output: health_report.md and health_report.json in current directory
```

## Advanced Usage

### Custom Output Directory

```bash
# Analyze with custom output directory
python scripts/analyze_diagnostic.py \
    /path/to/archive.zip \
    --output /path/to/reports \
    --format json,markdown
```

### Custom Thresholds

```bash
# Create custom thresholds file
cat > my_thresholds.yml << EOF
cluster:
  active_shards_percent:
    warning: 95
    critical: 80
  pending_tasks:
    warning: 200
node:
  heap_used_percent:
    warning: 80
    critical: 90
index:
  large_index_gb:
    warning: 50
EOF

# Use custom thresholds
python scripts/analyze_diagnostic.py \
    archive.zip \
    --config my_thresholds.yml
```

### Batch Processing

```bash
# Analyze multiple archives in a directory
python scripts/analyze_diagnostic.py \
    --batch /path/to/archives/ \
    --output /path/to/reports/

# Note: Not implemented yet - single archive mode only
```

### Verbose Output

```bash
# Run with verbose logging
python scripts/analyze_diagnostic.py \
    archive.zip \
    --verbose
```

### Different Report Formats

```bash
# Generate JSON report only
python scripts/analyze_diagnostic.py archive.zip --format json

# Generate Markdown report only
python scripts/analyze_diagnostic.py archive.zip --format markdown

# Generate both reports
python scripts/analyze_diagnostic.py archive.zip --format json,markdown
python scripts/analyze_diagnostic.py archive.zip --format all
```

## Output Files

### Health Report (health_report.md)

The Markdown report contains:
- Executive summary with cluster status, issue counts, and score
- Critical issues with recommendations
- Warnings with recommendations
- Cluster health overview
- Node health table
- Index health overview

### Health Report (health_report.json)

The JSON report contains:
- Cluster name and timestamp
- Summary with score and issue counts
- All issues with full details
- Node, index, and configuration details

## Interpreting Results

### Score Interpretation

- **90-100**: Healthy cluster, minor issues
- **70-89**: Some concerns, needs attention
- **50-69**: Significant issues, urgent action needed
- **0-49**: Critical state, immediate action required

### Severity Levels

- **Critical**: Immediate action required, cluster at risk
- **Warning**: Issue detected, monitor and plan remediation
- **Info**: Informational, optimization opportunities

## Common Issues and Solutions

### High Heap Usage

**Symptoms**: Slow performance, frequent GC pauses, circuit breaker errors

**Solutions**:
- Increase heap size: `-Xmx` parameter
- Check for memory leaks: use heap dump analysis
- Reduce concurrent operations: lower indexing/search rate
- Review field data cache: reduce aggressive caching

### Unassigned Shards

**Symptoms**: Red cluster status, reduced redundancy

**Solutions**:
- Check allocation explain API: `_cluster/allocation/explain`
- Verify disk space: ensure sufficient storage
- Check node health: all nodes should be running
- Review shard allocation settings

### Thread Pool Rejections

**Symptoms**: Errors in logs, reduced throughput

**Solutions**:
- Increase thread pool size: `thread_pool.write.queue_size`
- Reduce concurrent load: limit indexing/search rate
- Check for resource saturation: CPU, memory, disk I/O
- Review JVM heap settings: ensure adequate heap

### Red/Yellow Indices

**Symptoms**: Cluster status not green, data loss risk

**Solutions**:
- Investigate shard allocation: `cat/shards` command
- Check node availability: verify all data nodes are running
- Review replica settings: ensure proper replication
- Check disk space: ensure sufficient for all shards

### Slow Queries

**Symptoms**: High search latency, timeouts

**Solutions**:
- Add indices for common query fields
- Optimize query: use filters, avoid wildcards
- Review field mappings: enable `doc_values` for sorting
- Check for missing indices: ensure query targets exist
- Use query profiling: `profile` API or Kibana

### High CPU Usage

**Symptoms**: Slow operations, timeouts, high load

**Solutions**:
- Review heavy queries: check for expensive aggregations
- Check indexing rate: adjust bulk size and rate
- Verify thread pool settings: optimize concurrency
- Check for background tasks: snapshots, recovery, merges
- Scale hardware: add more nodes or upgrade

### High Disk Usage

**Symptoms**: Write failures, I/O errors

**Solutions**:
- Delete old indices: use index lifecycle management
- Reduce shard count: consolidate indices
- Implement ILM: index lifecycle management
- Add storage: add more disk capacity
- Review data retention: purge old time-series data

## Troubleshooting

### Archive Parsing Errors

**Error**: "Archive not found"
- Verify file path is correct
- Check archive file extension (.zip)
- Ensure file is readable

**Error**: "No cluster data found"
- Check if archive contains `cat/` directory
- Verify `cat_health.txt` exists
- Check archive format: ensure it's a valid diagnostic

**Error**: "Parse failed"
- Check file encoding: ensure UTF-8 compatible
- Verify archive integrity: try manual extraction
- Check file permissions: ensure read access

### Memory Issues

**Error**: "Out of memory during analysis"
- Increase Python heap: `-Xmx` parameter
- Process archives sequentially: instead of multiple at once
- Use 64-bit Python: for larger memory space

### Report Generation

**Issue**: Reports not created
- Check output directory permissions
- Verify output path exists or can be created
- Check disk space: ensure space for reports
- Review error messages: check console output

## Tips

1. **Start with default thresholds**: Run analysis first with defaults, then customize based on results

2. **Review critical issues first**: Address critical items before warnings

3. **Use verbose mode**: For debugging or detailed analysis

4. **Compare multiple archives**: Track health over time to identify trends

5. **Document custom thresholds**: Keep track of threshold changes for consistency

6. **Regular health checks**: Schedule periodic analysis for ongoing monitoring

7. **Integrate with monitoring**: Export monitoring data for trend analysis

8. **Archive reports**: Keep historical health reports for audit trail

## Integration with Support

When working with Elastic Support:

1. Include health report with diagnostic archive
2. Note score and severity of issues
3. Reference specific issues and recommendations from report
4. Provide cluster name and version information
5. Include timestamp for correlation
