#!/usr/bin/env python3
"""
check_logs.py – Log Analysis Health Check
Scans Elasticsearch log files inside the elastic/support-diagnostics bundle
for ERROR/WARN patterns, GC warnings, circuit-breaker trips, and more.
"""

import re
import sys
from collections import Counter, defaultdict
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


# ── Patterns of interest ─────────────────────────────────────────────────────
PATTERNS = {
    "OutOfMemoryError":         (re.compile(r"OutOfMemoryError",            re.I), "fail"),
    "Circuit Breaker":          (re.compile(r"CircuitBreak|circuit.break",  re.I), "fail"),
    "Disk Watermark":           (re.compile(r"(high|flood.stage).disk.watermark|disk watermark",
                                             re.I), "fail"),
    "Read-only block":          (re.compile(r"read.only.allow.delete|blocked.by..*read.only",
                                             re.I), "fail"),
    "Shard failed":             (re.compile(r"shard.*(failed|failure)",     re.I), "warn"),
    "Cluster state update slow":(re.compile(r"cluster state update took.*(sec|ms)",
                                             re.I), "warn"),
    "Took too long":            (re.compile(r"took.too.long|exceeded.*(timeout|limit)",
                                             re.I), "warn"),
    "Deprecation":              (re.compile(r"\[deprecation\]|\bdeprecated\b",
                                             re.I), "warn"),
    "Exception":                (re.compile(r"\bException\b",               re.I), "warn"),
    "ERROR line":               (re.compile(r"\bERROR\b",                        ), "warn"),
    "WARN line":                (re.compile(r"\bWARN\b",                         ), "info"),
    "GC overhead":              (re.compile(r"GC overhead limit exceeded",  re.I), "fail"),
    "Master not discovered":    (re.compile(r"master not discovered|no master",
                                             re.I), "fail"),
    "Index Throttling":         (re.compile(r"throttl",                     re.I), "warn"),
    "Mapping explosion":        (re.compile(r"Limit of total fields.*exceeded",
                                             re.I), "fail"),
}

MAX_LINES_PER_FILE  = 200_000
MAX_EXAMPLES        = 3
LOG_FILE_GLOBS      = [
    "logs/*.log",
    "logs/**/*.log",
    "*/logs/*.log",
]


def _scan_log_text(text: str, filename: str) -> dict:
    """Scan log text and return counts + examples per pattern."""
    results: dict[str, dict] = {name: {"count": 0, "examples": []} for name in PATTERNS}
    lines = text.splitlines()[:MAX_LINES_PER_FILE]

    for lineno, line in enumerate(lines, 1):
        for name, (regex, _) in PATTERNS.items():
            if regex.search(line):
                results[name]["count"] += 1
                if len(results[name]["examples"]) < MAX_EXAMPLES:
                    results[name]["examples"].append((lineno, line.strip()[:200]))

    return results


def check_logs(b: DiagnosticBundle) -> int:
    issues = 0
    section("LOG ANALYSIS")

    # Discover log files
    log_files: list[str] = []
    for glob in LOG_FILE_GLOBS:
        log_files.extend(b.glob(glob))

    # Deduplicate while preserving order
    seen = set()
    unique_logs = []
    for f in log_files:
        if f not in seen:
            seen.add(f)
            unique_logs.append(f)

    if not unique_logs:
        info("No .log files found in bundle – checking for log directories")
        # Fallback: look for any text file with 'log' in name
        log_files = b.glob("logs/*")
        unique_logs = [f for f in log_files if not f.endswith("/")]

    row("Log files found", str(len(unique_logs)), "info")
    if not unique_logs:
        warn("No log files discovered – manual inspection may be required")
        return 0

    # Aggregate across all log files
    agg: dict[str, dict] = {name: {"count": 0, "examples": [], "files": []} for name in PATTERNS}

    for log_path in unique_logs:
        text = b.read_text(log_path)
        if text is None:
            continue
        file_results = _scan_log_text(text, log_path)
        for name, data in file_results.items():
            if data["count"] > 0:
                agg[name]["count"]   += data["count"]
                agg[name]["files"].append(log_path)
                for ex in data["examples"]:
                    if len(agg[name]["examples"]) < MAX_EXAMPLES:
                        agg[name]["examples"].append((log_path, *ex))

    # Report findings
    section("LOG PATTERN SUMMARY")
    for name, (_, default_level) in PATTERNS.items():
        count = agg[name]["count"]
        if count == 0:
            continue

        level = default_level if count > 0 else "ok"
        # Escalate if very frequent
        if default_level == "warn" and count > 500:
            level = "fail"

        row(f"{name}", f"{count:,} occurrence(s)", level)
        if level in ("fail", "warn"):
            if level == "fail":
                issues += 1
            files_hit = list(set(agg[name]["files"]))[:3]
            for f in files_hit:
                print(f"         in: {f}")
            for ex in agg[name]["examples"][:MAX_EXAMPLES]:
                fpath, lineno, line = ex
                print(f"         {BOLD}line {lineno}{RESET}: {line[:160]}")

    # ── File-level summary ───────────────────────────────────────────────────
    section("LOG FILES SCANNED")
    for f in unique_logs[:20]:
        info(f)
    if len(unique_logs) > 20:
        info(f"… and {len(unique_logs)-20} more")

    return issues


def check_deprecation_log(b: DiagnosticBundle) -> int:
    issues = 0
    section("DEPRECATION LOG")

    dep_files = b.glob("logs/*deprecation*") + b.glob("logs/**/*deprecation*")
    if not dep_files:
        info("No deprecation log file found")
        return 0

    counter: Counter = Counter()
    for dp in dep_files:
        text = b.read_text(dp)
        if not text:
            continue
        for line in text.splitlines():
            # Extract deprecation message (after the level marker)
            m = re.search(r"\[deprecation\]\s*(.*)", line, re.I)
            if m:
                counter[m.group(1)[:120]] += 1

    row("Unique deprecation messages", str(len(counter)),
        "ok" if not counter else "warn")
    if counter:
        warn("Deprecated API / feature usage detected – review before upgrading Elasticsearch:")
        for msg, cnt in counter.most_common(10):
            print(f"       {cnt:>5}x  {msg}")
        issues += 1

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total = 0
    total += check_logs(b)
    total += check_deprecation_log(b)

    section("LOGS SUMMARY")
    if total == 0:
        ok("No critical log patterns detected")
    else:
        fail(f"{total} log concern(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
