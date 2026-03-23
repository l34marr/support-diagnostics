#!/usr/bin/env python3
"""
check_threads.py – Thread Pool Health Check
Analyses thread pool metrics from the elastic/support-diagnostics bundle.
"""

import sys
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


# Thread pools that are most critical to monitor
CRITICAL_POOLS = {
    "write",
    "search",
    "get",
    "bulk",
    "index",
    "force_merge",
    "flush",
    "refresh",
    "warmer",
    "generic",
    "management",
    "fetch_shard_store",
    "fetch_shard_started",
    "snapshot",
    "ml_utility",
    "ml_datafeed",
}

# Thresholds
QUEUE_WARN       = 50
QUEUE_FAIL       = 200
REJECTED_WARN    = 1      # any rejection is a warning
REJECTED_FAIL    = 100
ACTIVE_WARN_PCT  = 80     # % of pool size


def check_thread_pools(b: DiagnosticBundle) -> int:
    issues = 0
    section("THREAD POOLS")

    nodes_stats = b.read_json("nodes_stats.json")
    if nodes_stats is None:
        fail("nodes_stats.json not found")
        return 1

    nodes = nodes_stats.get("nodes", {})
    if not nodes:
        fail("No node stats available")
        return 1

    # Aggregated rejections across all nodes
    global_rejected: dict[str, int] = {}
    global_queue:    dict[str, int] = {}

    for nid, ns in nodes.items():
        name = ns.get("name", nid)
        thread_pools = ns.get("thread_pool", {})
        if not thread_pools:
            continue

        print(f"\n  {BOLD}── {name} ──{RESET}")

        queued_pools    = []
        rejected_pools  = []
        saturated_pools = []

        for pool_name, stats in sorted(thread_pools.items()):
            queue    = stats.get("queue",     0)
            rejected = stats.get("rejected",  0)
            active   = stats.get("active",    0)
            threads  = stats.get("threads",   1) or 1
            largest  = stats.get("largest",   0)

            # Accumulate for cross-node summary
            global_rejected[pool_name] = global_rejected.get(pool_name, 0) + rejected
            global_queue[pool_name]    = global_queue.get(pool_name, 0)    + queue

            active_pct = (active / threads * 100) if threads else 0

            if rejected >= REJECTED_FAIL:
                rejected_pools.append((pool_name, rejected, queue, active_pct))
                issues += 1
            elif rejected >= REJECTED_WARN:
                rejected_pools.append((pool_name, rejected, queue, active_pct))

            if queue >= QUEUE_FAIL:
                queued_pools.append((pool_name, queue, rejected))
                issues += 1
            elif queue >= QUEUE_WARN:
                queued_pools.append((pool_name, queue, rejected))

            if active_pct >= ACTIVE_WARN_PCT and pool_name in CRITICAL_POOLS:
                saturated_pools.append((pool_name, active, threads, active_pct))

        if not (queued_pools or rejected_pools or saturated_pools):
            ok("  All thread pools healthy")
            continue

        if rejected_pools:
            fail(f"  Thread pool REJECTIONS detected on {name}:")
            for pool, rej, q, act_pct in rejected_pools:
                level = "fail" if rej >= REJECTED_FAIL else "warn"
                row(f"    [{pool}]",
                    f"rejected={rej:,}  queue={q}  active={act_pct:.0f}%",
                    level)

        if queued_pools:
            warn(f"  Thread pool QUEUES elevated on {name}:")
            for pool, q, rej in queued_pools:
                level = "fail" if q >= QUEUE_FAIL else "warn"
                row(f"    [{pool}]", f"queue={q}  rejected={rej:,}", level)

        if saturated_pools:
            warn(f"  Near-saturated thread pools on {name}:")
            for pool, active, threads, pct in saturated_pools:
                row(f"    [{pool}]", f"active={active}/{threads}  ({pct:.0f}%)", "warn")

    # ── Cross-node summary ────────────────────────────────────────────────────
    section("CROSS-NODE THREAD POOL SUMMARY")

    critical_rejected = {k: v for k, v in global_rejected.items() if v >= REJECTED_WARN}
    critical_queue    = {k: v for k, v in global_queue.items()    if v >= QUEUE_WARN}

    if not critical_rejected and not critical_queue:
        ok("No cross-node thread pool rejections or queue buildup")
    else:
        if critical_rejected:
            row("Pools with rejections (total across nodes)", "", "info")
            for pool, cnt in sorted(critical_rejected.items(), key=lambda x: -x[1]):
                level = "fail" if cnt >= REJECTED_FAIL else "warn"
                row(f"  {pool}", f"{cnt:,} rejections", level)
                if level == "fail" and pool not in [p for p, *_ in []]:
                    issues += 1

        if critical_queue:
            row("Pools with queued tasks (total across nodes)", "", "info")
            for pool, cnt in sorted(critical_queue.items(), key=lambda x: -x[1]):
                level = "fail" if cnt >= QUEUE_FAIL else "warn"
                row(f"  {pool}", f"queue depth {cnt}", level)

    return issues


def check_hot_threads(b: DiagnosticBundle) -> int:
    issues = 0
    section("HOT THREADS")

    ht = b.read_text("nodes_hot_threads.txt")
    if ht is None:
        ht = b.read_text("hot_threads.txt")

    if ht is None:
        info("Hot threads file not found in bundle")
        return 0

    lines = ht.splitlines()

    # Count occurrences of different thread types
    busy_count = sum(1 for l in lines if "% cpu" in l.lower() or "% in" in l.lower())
    row("Hot thread snapshots", str(busy_count), "info")

    # Flag CPU-heavy patterns
    cpu_heavy = [l for l in lines if "100.0%" in l or "99." in l]
    if cpu_heavy:
        warn(f"{len(cpu_heavy)} thread(s) running at very high CPU:")
        for l in cpu_heavy[:5]:
            print(f"       {l.strip()[:160]}")
        issues += 1

    # Look for stuck threads / blocked
    blocked = [l for l in lines if "BLOCKED" in l or "WAITING" in l]
    if blocked:
        warn(f"{len(blocked)} BLOCKED/WAITING thread(s) found:")
        for l in blocked[:5]:
            print(f"       {l.strip()[:160]}")

    info("Review nodes_hot_threads.txt manually for detailed stack traces")
    return issues


def check_pending_tasks(b: DiagnosticBundle) -> int:
    issues = 0
    section("PENDING CLUSTER TASKS")

    pending = b.read_json("pending_tasks.json")
    if pending is None:
        info("pending_tasks.json not found")
        return 0

    tasks = pending.get("tasks", [])
    row("Pending cluster tasks", str(len(tasks)),
        "ok" if len(tasks) == 0 else ("warn" if len(tasks) < 20 else "fail"))

    if tasks:
        warn(f"{len(tasks)} pending task(s) – may indicate cluster manager overload:")
        for t in tasks[:10]:
            print(f"       priority={t.get('priority','?')}  "
                  f"source={t.get('source','?')}  "
                  f"time_in_queue={t.get('time_in_queue','?')}")
        if len(tasks) >= 20:
            issues += 1

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total = 0
    total += check_thread_pools(b)
    total += check_hot_threads(b)
    total += check_pending_tasks(b)

    section("THREADS SUMMARY")
    if total == 0:
        ok("No thread pool issues detected")
    else:
        fail(f"{total} thread pool issue(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
