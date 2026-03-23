# Elasticsearch Diagnostic Health Check Scripts

A collection of Python scripts that analyse an
[elastic/support-diagnostics](https://github.com/elastic/support-diagnostics)
bundle and produce a human-readable health report.

## Requirements

* Python 3.10+  (uses `match`-free syntax, works on 3.10+)
* No third-party packages required – stdlib only

## File Layout

```
health/
├── README.md              ← this file
├── utils.py               ← shared helpers (bundle reader, colour output)
├── health_report.py       ← main runner (runs all checks)
├── check_cluster.py       ← Cluster health, state & settings
├── check_gc.py            ← JVM / Garbage Collection metrics
├── check_indices.py       ← Index health, shard sizes, deleted docs
├── check_logs.py          ← Log pattern analysis & deprecation log
├── check_nodes.py         ← Per-node CPU / disk / heap / FD / roles
├── check_threads.py       ← Thread pool queues, rejections, hot threads
└── check_tls.py           ← TLS certificates, protocols, ciphers
```

## Usage

### Run the full report (recommended)

```bash
cd health
python health_report.py ../local-diagnostics-20260311-054110.zip
```

### Run a single check

```bash
python check_cluster.py  ../local-diagnostics-20260311-054110.zip
python check_gc.py       ../local-diagnostics-20260311-054110.zip
python check_indices.py  ../local-diagnostics-20260311-054110.zip
python check_logs.py     ../local-diagnostics-20260311-054110.zip
python check_nodes.py    ../local-diagnostics-20260311-054110.zip
python check_threads.py  ../local-diagnostics-20260311-054110.zip
python check_tls.py      ../local-diagnostics-20260311-054110.zip
```

The bundle can be either the raw `.zip` file or an extracted directory.

## What Each Check Covers

| Script | Key Files Read | What It Checks |
|---|---|---|
| `check_cluster.py` | `cluster_health.json`, `cluster_state.json`, `cluster_settings.json` | Status, shard assignment, pending tasks, read-only blocks, transient settings |
| `check_gc.py` | `nodes_stats.json`, `nodes_info.json` | Heap %, old-gen GC rate, young-gen GC rate, mixed JVM versions |
| `check_indices.py` | `cat_indices.json`, `cat_shards.json`, `indices_stats.json`, `index_settings.json` | Red/yellow indices, oversized shards, deleted-doc bloat, read-only blocks, zero-replica indices |
| `check_logs.py` | `logs/*.log`, `*deprecation*.log` | OOM errors, circuit-breaker trips, disk watermarks, shard failures, deprecation warnings |
| `check_nodes.py` | `nodes_info.json`, `nodes_stats.json` | CPU / load, heap, disk, open FDs, mixed ES versions, master node count |
| `check_threads.py` | `nodes_stats.json`, `nodes_hot_threads.txt`, `pending_tasks.json` | Thread pool queue depth, rejections, near-saturated pools, hot threads |
| `check_tls.py` | `ssl_certs.json`, `nodes_info.json`, `cluster_settings.json` | Certificate expiry, self-signed certs, security disabled, weak ciphers, deprecated TLS versions |

## Output Legend

| Symbol | Meaning |
|---|---|
| ✔ OK | Within acceptable thresholds |
| ⚠ WARN | Elevated – should be investigated |
| ✘ FAIL | Critical – immediate action recommended |
| ℹ INFO | Informational only |

## Diagnostic Bundle Structure

The elastic/support-diagnostics tool produces a ZIP containing files such as:

```
local-diagnostics-YYYYMMDD-HHmmss/
├── cluster_health.json
├── cluster_state.json
├── cluster_settings.json
├── nodes_info.json
├── nodes_stats.json
├── cat_indices.json
├── cat_shards.json
├── indices_stats.json
├── index_settings.json
├── ssl_certs.json
├── pending_tasks.json
├── nodes_hot_threads.txt
└── logs/
    ├── elasticsearch.log
    └── elasticsearch_deprecation.log
```

Scripts gracefully skip any files that are absent.
