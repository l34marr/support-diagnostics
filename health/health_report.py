#!/usr/bin/env python3
"""
health_report.py – Elasticsearch Full Health Check Report
Orchestrates all individual health check modules and produces a
consolidated report from an elastic/support-diagnostics bundle.

Usage:
    python health_report.py <path-to-diagnostics.zip>

Example:
    python health_report.py local-diagnostics-20260311-054110.zip
"""

import importlib
import sys
import time
from datetime import datetime, timezone
from utils import (
    DiagnosticBundle, section, row, ok, warn, fail, info,
    GREEN, YELLOW, RED, CYAN, BOLD, RESET,
    STATUS_OK, STATUS_WARN, STATUS_FAIL,
)

CHECKS = [
    ("check_cluster",  "Cluster"),
    ("check_gc",       "Garbage Collection"),
    ("check_indices",  "Indices"),
    ("check_logs",     "Logs"),
    ("check_nodes",    "Nodes"),
    ("check_threads",  "Threads"),
    ("check_tls",      "TLS / Security"),
]


def banner(zip_path: str) -> None:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════╗
║         ELASTICSEARCH DIAGNOSTIC HEALTH REPORT                       ║
║         Generated : {now:<48}║
║         Bundle    : {zip_path:<48}║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
""")


def run_checks(zip_path: str) -> dict[str, int]:
    results: dict[str, int] = {}

    for module_name, label in CHECKS:
        print(f"\n{BOLD}{CYAN}{'═' * 72}{RESET}")
        print(f"{BOLD}{CYAN}  SECTION: {label.upper()}{RESET}")
        print(f"{BOLD}{CYAN}{'═' * 72}{RESET}")

        try:
            mod = importlib.import_module(module_name)
            mod.main(zip_path)
            # Capture the return value via re-running each internal check
            # We call main() which prints but doesn't return; use 0 as placeholder
            results[label] = 0   # individual checks print their own issues
        except SystemExit:
            pass
        except Exception as exc:
            fail(f"Error running {label} check: {exc}")
            results[label] = 1

    return results


def print_final_summary(zip_path: str) -> None:
    section("FINAL HEALTH REPORT SUMMARY")

    b = DiagnosticBundle(zip_path)

    # Pull high-level cluster health for the summary card
    ch = b.read_json("cluster_health.json") or {}
    status   = ch.get("status", "unknown").upper()
    cluster  = ch.get("cluster_name", "unknown")
    nodes_n  = ch.get("number_of_nodes", "?")
    shards   = ch.get("active_shards", "?")
    unassign = ch.get("unassigned_shards", 0)
    pending  = ch.get("number_of_pending_tasks", 0)

    color = {"GREEN": GREEN, "YELLOW": YELLOW, "RED": RED}.get(status, CYAN)

    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │  Cluster    : {BOLD}{cluster:<38}{RESET}│
  │  Status     : {color}{BOLD}{status:<38}{RESET}│
  │  Nodes      : {str(nodes_n):<38}│
  │  Shards     : {str(shards):<38}│
  │  Unassigned : {str(unassign):<38}│
  │  Pending    : {str(pending):<38}│
  └─────────────────────────────────────────────────────┘""")

    print(f"""
  {BOLD}Checks run:{RESET}""")
    for _, label in CHECKS:
        print(f"    {STATUS_OK}  {label}")

    print(f"""
  {BOLD}Next Steps:{RESET}
    • Address any {RED}✘ FAIL{RESET} items immediately
    • Review and plan remediation for {YELLOW}⚠  WARN{RESET} items
    • Re-run diagnostics after applying fixes to validate improvement
    • For persistent issues, consult Elastic Support with this bundle
""")


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)

    zip_path = sys.argv[1]
    banner(zip_path)

    t0 = time.time()
    run_checks(zip_path)
    elapsed = time.time() - t0

    print_final_summary(zip_path)
    print(f"  Report completed in {elapsed:.1f}s\n")


if __name__ == "__main__":
    main()
