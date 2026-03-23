#!/usr/bin/env python3
"""
check_gc.py – Garbage Collection Health Check
Analyses JVM GC metrics from the elastic/support-diagnostics bundle.
"""

import sys
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


# Thresholds
GC_OLD_WARN_MS_PER_MIN  = 2_000    # 2 s of old-gen GC per minute
GC_OLD_FAIL_MS_PER_MIN  = 10_000   # 10 s of old-gen GC per minute
GC_YOUNG_WARN_COUNT_PER_MIN = 40
HEAP_WARN_PCT           = 75
HEAP_FAIL_PCT           = 90


def _safe_get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d != {} else default


def bytes_to_mb(b: int) -> float:
    return b / (1024 * 1024)


def check_gc(b: DiagnosticBundle) -> int:
    issues = 0
    section("GARBAGE COLLECTION")

    nodes_stats = b.read_json("nodes_stats.json")
    if nodes_stats is None:
        fail("nodes_stats.json not found in bundle")
        return 1

    nodes = nodes_stats.get("nodes", {})
    if not nodes:
        fail("No node stats found")
        return 1

    for node_id, ns in nodes.items():
        node_name = ns.get("name", node_id)
        jvm       = ns.get("jvm", {})
        uptime_ms = jvm.get("uptime_in_millis", 1)
        uptime_min = max(uptime_ms / 60_000, 1)

        print(f"\n  {BOLD}Node: {node_name}{RESET}")

        # ── Heap ────────────────────────────────────────────────────────
        heap_used  = _safe_get(jvm, "mem", "heap_used_in_bytes", default=0)
        heap_max   = _safe_get(jvm, "mem", "heap_max_in_bytes",  default=1)
        heap_pct   = (heap_used / heap_max * 100) if heap_max else 0
        heap_level = "ok" if heap_pct < HEAP_WARN_PCT else ("warn" if heap_pct < HEAP_FAIL_PCT else "fail")
        row(f"  Heap usage",
            f"{bytes_to_mb(heap_used):.0f} MB / {bytes_to_mb(heap_max):.0f} MB  ({heap_pct:.1f}%)",
            heap_level)
        if heap_pct >= HEAP_FAIL_PCT:
            issues += 1

        # ── GC collectors ────────────────────────────────────────────────
        collectors = _safe_get(jvm, "gc", "collectors", default={})
        if not collectors:
            info("  No GC collector data available")
            continue

        for collector_name, stats in collectors.items():
            count      = stats.get("collection_count", 0)
            time_ms    = stats.get("collection_time_in_millis", 0)
            count_rate = count / uptime_min
            time_rate  = time_ms / uptime_min   # ms per minute

            is_old = any(s in collector_name.lower() for s in ("old", "cms", "g1 old", "zgc", "shenandoah"))

            if is_old:
                level = ("ok"   if time_rate < GC_OLD_WARN_MS_PER_MIN  else
                         "warn" if time_rate < GC_OLD_FAIL_MS_PER_MIN  else "fail")
                if time_rate >= GC_OLD_FAIL_MS_PER_MIN:
                    issues += 1
            else:
                level = "ok" if count_rate < GC_YOUNG_WARN_COUNT_PER_MIN else "warn"

            row(f"  [{collector_name}] count",
                f"{count:,}  ({count_rate:.2f}/min)", level)
            row(f"  [{collector_name}] time",
                f"{time_ms:,} ms  ({time_rate:.1f} ms/min)", level)

            if level == "warn":
                warn(f"  High GC activity on '{collector_name}' – check heap sizing and memory pressure")
            elif level == "fail":
                fail(f"  Critical GC activity on '{collector_name}' – node likely under severe memory pressure")

    return issues


def check_jvm_versions(b: DiagnosticBundle) -> int:
    issues = 0
    section("JVM VERSIONS")

    nodes_info = b.read_json("nodes_info.json")
    if nodes_info is None:
        info("nodes_info.json not found – skipping JVM version check")
        return 0

    seen_versions: dict[str, list[str]] = {}
    for node_id, ni in nodes_info.get("nodes", {}).items():
        node_name = ni.get("name", node_id)
        jvm_ver   = _safe_get(ni, "jvm", "version", default="unknown")
        seen_versions.setdefault(jvm_ver, []).append(node_name)

    for ver, names in seen_versions.items():
        row(f"JVM {ver}", f"{len(names)} node(s): {', '.join(names)}", "info")

    if len(seen_versions) > 1:
        warn("Multiple JVM versions detected across nodes – mixed JVM environments can cause instability")
        issues += 1
    else:
        ok("All nodes running the same JVM version")

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total = 0
    total += check_gc(b)
    total += check_jvm_versions(b)

    section("GC SUMMARY")
    if total == 0:
        ok("No GC issues detected")
    else:
        fail(f"{total} GC issue(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
