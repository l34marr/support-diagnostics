#!/usr/bin/env python3
"""
check_nodes.py – Node-level Health Check
Analyses node info and stats from the elastic/support-diagnostics bundle.
"""

import sys
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


# Thresholds
DISK_WARN_PCT        = 75
DISK_FAIL_PCT        = 90
CPU_WARN_PCT         = 70
CPU_FAIL_PCT         = 90
LOAD_WARN_FACTOR     = 2.0   # load_1m / cpu_count
LOAD_FAIL_FACTOR     = 4.0
OPEN_FILES_WARN_PCT  = 80    # % of limit
HEAP_WARN_PCT        = 75
HEAP_FAIL_PCT        = 90
ES_VERSION_MISMATCH  = True  # fail on mixed ES versions


def _safe(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d != {} else default


def bytes_to_gb(b: int) -> float:
    return b / 1024 ** 3


def check_nodes_info(b: DiagnosticBundle) -> int:
    issues = 0
    section("NODES INFO")

    nodes_info = b.read_json("nodes_info.json")
    if nodes_info is None:
        fail("nodes_info.json not found")
        return 1

    nodes = nodes_info.get("nodes", {})
    row("Total nodes discovered", str(len(nodes)), "ok" if nodes else "fail")
    if not nodes:
        return 1

    # ES version consistency
    versions: dict[str, list] = {}
    roles_summary: dict[str, int] = {}

    for nid, ni in nodes.items():
        ver = ni.get("version", "unknown")
        versions.setdefault(ver, []).append(ni.get("name", nid))
        for role in ni.get("roles", []):
            roles_summary[role] = roles_summary.get(role, 0) + 1

    for ver, names in versions.items():
        row(f"ES version {ver}", f"{len(names)} node(s)", "info")
    if len(versions) > 1:
        warn("Mixed Elasticsearch versions detected – complete rolling upgrade as soon as possible")
        issues += 1
    else:
        ok("All nodes on the same Elasticsearch version")

    section("NODE ROLES")
    for role, count in sorted(roles_summary.items()):
        row(f"  {role}", str(count), "info")

    # Check for dedicated master nodes
    master_nodes = [ni for ni in nodes.values() if "master" in ni.get("roles", [])]
    data_master  = [ni for ni in master_nodes    if "data"   in ni.get("roles", [])]
    if len(master_nodes) < 3:
        warn(f"Only {len(master_nodes)} master-eligible node(s) – recommend at least 3 for quorum stability")
        issues += 1
    if data_master and len(nodes) > 3:
        warn("Master nodes also hold data roles – consider dedicated master nodes in larger clusters")
        issues += 1

    row("Master-eligible nodes", str(len(master_nodes)),
        "ok" if len(master_nodes) >= 3 else "warn")

    return issues


def check_nodes_stats(b: DiagnosticBundle) -> int:
    issues = 0
    section("NODES STATS")

    nodes_stats = b.read_json("nodes_stats.json")
    if nodes_stats is None:
        fail("nodes_stats.json not found")
        return 1

    nodes = nodes_stats.get("nodes", {})
    if not nodes:
        fail("No node stats available")
        return 1

    for nid, ns in nodes.items():
        name = ns.get("name", nid)
        print(f"\n  {BOLD}── {name} ──{RESET}")

        # ── CPU / Load ────────────────────────────────────────────────────
        cpu_pct   = _safe(ns, "os", "cpu", "percent", default=0) or 0
        load_avg  = _safe(ns, "os", "cpu", "load_average", "1m", default=0.0) or 0.0
        cpu_count = _safe(ns, "os", "available_processors", default=1) or 1

        cpu_level  = "ok" if cpu_pct < CPU_WARN_PCT else ("warn" if cpu_pct < CPU_FAIL_PCT else "fail")
        load_ratio = load_avg / cpu_count if cpu_count else 0
        load_level = "ok" if load_ratio < LOAD_WARN_FACTOR else ("warn" if load_ratio < LOAD_FAIL_FACTOR else "fail")

        row("  CPU usage",      f"{cpu_pct}%",                                     cpu_level)
        row("  Load avg (1m)",  f"{load_avg:.2f}  (ratio={load_ratio:.2f})",        load_level)
        if cpu_level == "fail":   issues += 1
        if load_level == "fail":  issues += 1

        # ── Heap ──────────────────────────────────────────────────────────
        heap_used = _safe(ns, "jvm", "mem", "heap_used_in_bytes", default=0) or 0
        heap_max  = _safe(ns, "jvm", "mem", "heap_max_in_bytes",  default=1) or 1
        heap_pct  = heap_used / heap_max * 100
        heap_level = "ok" if heap_pct < HEAP_WARN_PCT else ("warn" if heap_pct < HEAP_FAIL_PCT else "fail")
        row("  Heap",
            f"{bytes_to_gb(heap_used):.1f} / {bytes_to_gb(heap_max):.1f} GB  ({heap_pct:.1f}%)",
            heap_level)
        if heap_level == "fail":
            issues += 1

        # ── Disk ──────────────────────────────────────────────────────────
        fs_total = _safe(ns, "fs", "total", default={}) or {}
        disk_total_bytes = fs_total.get("total_in_bytes", 0) or 0
        disk_free_bytes  = fs_total.get("available_in_bytes", 0) or 0
        if disk_total_bytes > 0:
            used_pct = (1 - disk_free_bytes / disk_total_bytes) * 100
            disk_level = "ok" if used_pct < DISK_WARN_PCT else ("warn" if used_pct < DISK_FAIL_PCT else "fail")
            row("  Disk usage",
                f"{bytes_to_gb(disk_total_bytes - disk_free_bytes):.1f} / "
                f"{bytes_to_gb(disk_total_bytes):.1f} GB  ({used_pct:.1f}%)",
                disk_level)
            if disk_level == "fail":
                fail(f"  Node {name} disk critically full – risk of read-only blocks")
                issues += 1
            elif disk_level == "warn":
                warn(f"  Node {name} disk usage elevated – monitor closely")

        # ── Open file descriptors ─────────────────────────────────────────
        fd_cur = _safe(ns, "process", "open_file_descriptors",     default=0) or 0
        fd_max = _safe(ns, "process", "max_file_descriptors",      default=0) or 0
        if fd_max > 0:
            fd_pct = fd_cur / fd_max * 100
            fd_level = "ok" if fd_pct < OPEN_FILES_WARN_PCT else "warn"
            row("  Open file descriptors",
                f"{fd_cur:,} / {fd_max:,}  ({fd_pct:.1f}%)", fd_level)
        elif fd_cur > 0:
            row("  Open file descriptors", f"{fd_cur:,}", "info")

        # ── Network ───────────────────────────────────────────────────────
        transport = _safe(ns, "transport", default={}) or {}
        rx_bytes  = transport.get("rx_size_in_bytes", 0)
        tx_bytes  = transport.get("tx_size_in_bytes", 0)
        row("  Transport RX / TX",
            f"{bytes_to_gb(rx_bytes):.2f} GB / {bytes_to_gb(tx_bytes):.2f} GB", "info")

    return issues


def check_master_stability(b: DiagnosticBundle) -> int:
    issues = 0
    section("MASTER STABILITY")

    # Check master history via cluster_state or master_history file
    master_history = b.read_json("master_history.json")
    if master_history is None:
        info("master_history.json not found – checking cluster_state instead")
        cs = b.read_json("cluster_state.json")
        if cs:
            master = cs.get("master_node", "n/a")
            row("Current master node ID", master, "ok" if master != "n/a" else "fail")
            if master == "n/a":
                issues += 1
        return issues

    changes = master_history.get("master_history", []) if isinstance(master_history, dict) else master_history
    row("Master node change events", str(len(changes)),
        "ok" if len(changes) <= 1 else ("warn" if len(changes) <= 5 else "fail"))
    if len(changes) > 1:
        warn("Multiple master changes detected – investigate network stability or master node health")
        issues += 1

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total = 0
    total += check_nodes_info(b)
    total += check_nodes_stats(b)
    total += check_master_stability(b)

    section("NODES SUMMARY")
    if total == 0:
        ok("No node-level issues detected")
    else:
        fail(f"{total} node issue(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
