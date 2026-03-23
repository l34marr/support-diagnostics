#!/usr/bin/env python3
"""
check_cluster.py – Elasticsearch Cluster Health Check
Reads data from an elastic/support-diagnostics bundle.
"""

import sys
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


THRESHOLDS = {
    "disk_watermark_warn_pct": 85,
    "disk_watermark_fail_pct": 95,
    "pending_tasks_warn": 5,
    "pending_tasks_fail": 20,
    "unassigned_shards_fail": 1,
}


def check_cluster_health(b: DiagnosticBundle) -> int:
    """Returns number of failures found."""
    issues = 0
    section("CLUSTER HEALTH")

    data = b.read_json("cluster_health.json")
    if data is None:
        fail("cluster_health.json not found in bundle")
        return 1

    status = data.get("status", "unknown").lower()
    level  = {"green": "ok", "yellow": "warn", "red": "fail"}.get(status, "warn")
    row("Cluster status", status.upper(), level)
    if status != "green":
        issues += 1

    cluster_name = data.get("cluster_name", "n/a")
    row("Cluster name", cluster_name, "info")

    nodes_total = data.get("number_of_nodes", 0)
    nodes_data  = data.get("number_of_data_nodes", 0)
    row("Nodes (total / data)", f"{nodes_total} / {nodes_data}", "ok" if nodes_total > 0 else "fail")

    active_shards = data.get("active_shards", 0)
    pct           = data.get("active_shards_percent_as_number", 0.0)
    row("Active shards", f"{active_shards}  ({pct:.1f}%)",
        "ok" if pct >= 100 else ("warn" if pct >= 90 else "fail"))
    if pct < 100:
        issues += 1

    unassigned = data.get("unassigned_shards", 0)
    row("Unassigned shards", str(unassigned),
        "ok" if unassigned == 0 else "fail")
    if unassigned > 0:
        issues += 1

    relocating = data.get("relocating_shards", 0)
    row("Relocating shards", str(relocating),
        "ok" if relocating == 0 else "warn")

    initializing = data.get("initializing_shards", 0)
    row("Initializing shards", str(initializing),
        "ok" if initializing == 0 else "warn")

    delayed = data.get("delayed_unassigned_shards", 0)
    row("Delayed unassigned shards", str(delayed),
        "ok" if delayed == 0 else "warn")

    pending = data.get("number_of_pending_tasks", 0)
    plevel  = "ok" if pending < THRESHOLDS["pending_tasks_warn"] else \
              ("warn" if pending < THRESHOLDS["pending_tasks_fail"] else "fail")
    row("Pending cluster tasks", str(pending), plevel)
    if pending >= THRESHOLDS["pending_tasks_fail"]:
        issues += 1

    in_flight = data.get("number_of_in_flight_fetch", 0)
    row("In-flight shard fetches", str(in_flight),
        "ok" if in_flight == 0 else "warn")

    timed_out = data.get("timed_out", False)
    row("Health check timed out", str(timed_out),
        "ok" if not timed_out else "fail")
    if timed_out:
        issues += 1

    return issues


def check_cluster_state(b: DiagnosticBundle) -> int:
    issues = 0
    section("CLUSTER STATE SUMMARY")

    state = b.read_json("cluster_state.json")
    if state is None:
        info("cluster_state.json not found – skipping")
        return 0

    master_node = state.get("master_node", "n/a")
    row("Master node ID", master_node, "ok" if master_node != "n/a" else "fail")
    if master_node == "n/a":
        issues += 1

    nodes = state.get("nodes", {})
    row("Nodes in cluster state", str(len(nodes)), "ok" if nodes else "fail")

    routing_table = state.get("routing_table", {}).get("indices", {})
    row("Indices in routing table", str(len(routing_table)), "info")

    return issues


def check_cluster_settings(b: DiagnosticBundle) -> int:
    issues = 0
    section("CLUSTER SETTINGS")

    settings = b.read_json("cluster_settings.json")
    if settings is None:
        info("cluster_settings.json not found – skipping")
        return 0

    persistent = settings.get("persistent", {})
    transient  = settings.get("transient", {})

    # Flat merge of all settings
    all_settings: dict = {}
    for d in (persistent, transient):
        for k, v in d.items():
            all_settings[k] = v

    row("Persistent settings count", str(len(persistent)), "info")
    row("Transient settings count",  str(len(transient)),
        "ok" if not transient else "warn")
    if transient:
        warn("Transient settings present – these are lost on restart; consider making them persistent")
        issues += 1

    # Routing allocation
    alloc = (
        all_settings.get("cluster.routing.allocation.enable")
        or persistent.get("cluster", {}).get("routing", {}).get("allocation", {}).get("enable")
        or "all"
    )
    row("Routing allocation enabled", str(alloc),
        "ok" if str(alloc) == "all" else "warn")
    if str(alloc) != "all":
        warn("Shard allocation is not set to 'all' – cluster may not rebalance correctly")
        issues += 1

    # Read-only
    ro = all_settings.get("cluster.blocks.read_only", "false")
    row("Cluster read-only block", str(ro),
        "ok" if str(ro).lower() == "false" else "fail")
    if str(ro).lower() == "true":
        fail("Cluster is in read-only mode")
        issues += 1

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total_issues = 0
    total_issues += check_cluster_health(b)
    total_issues += check_cluster_state(b)
    total_issues += check_cluster_settings(b)

    section("CLUSTER SUMMARY")
    if total_issues == 0:
        ok("No cluster-level issues detected")
    else:
        fail(f"{total_issues} issue(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
