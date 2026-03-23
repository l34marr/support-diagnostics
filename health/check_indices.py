#!/usr/bin/env python3
"""
check_indices.py – Indices Health Check
Analyses index-level health from the elastic/support-diagnostics bundle.
"""

import sys
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


# Thresholds
SHARD_SIZE_WARN_GB      = 40
SHARD_SIZE_FAIL_GB      = 60
DOC_COUNT_WARN          = 1_000_000_000    # 1 billion docs per shard
INDEX_COUNT_WARN        = 1_000
INDEX_COUNT_FAIL        = 5_000
DELETED_RATIO_WARN      = 0.20             # 20 % deleted docs
RED_INDICES_FAIL        = 1


def bytes_to_gb(b: int) -> float:
    return b / (1024 ** 3)


def check_indices_health(b: DiagnosticBundle) -> int:
    issues = 0
    section("INDICES HEALTH")

    cat_indices = b.read_json("cat_indices.json")
    if cat_indices is None:
        # Try text form
        txt = b.read_text("cat_indices.txt")
        if txt:
            info("cat_indices available as text only – detailed analysis skipped")
            print(txt[:2000])
        else:
            fail("cat_indices.json / cat_indices.txt not found in bundle")
            issues += 1
        return issues

    total   = len(cat_indices)
    red     = [i for i in cat_indices if i.get("health") == "red"]
    yellow  = [i for i in cat_indices if i.get("health") == "yellow"]
    green   = [i for i in cat_indices if i.get("health") == "green"]

    row("Total indices",   str(total),      "ok" if total < INDEX_COUNT_WARN else "warn")
    row("Green  indices",  str(len(green)), "ok")
    row("Yellow indices",  str(len(yellow)), "ok" if not yellow else "warn")
    row("Red    indices",  str(len(red)),   "ok" if not red    else "fail")

    if total >= INDEX_COUNT_FAIL:
        fail(f"Very high index count ({total}) – consider ILM / index consolidation")
        issues += 1
    elif total >= INDEX_COUNT_WARN:
        warn(f"High index count ({total}) – monitor cluster state size")

    if red:
        issues += len(red)
        fail(f"{len(red)} RED index/indices detected:")
        for idx in red[:10]:
            print(f"       {BOLD}{idx.get('index', '?')}{RESET}  "
                  f"pri={idx.get('pri','?')}  rep={idx.get('rep','?')}  "
                  f"unassigned={idx.get('pri.store.size','?')}")

    if yellow:
        warn(f"{len(yellow)} YELLOW index/indices (replica unassigned):")
        for idx in yellow[:10]:
            print(f"       {idx.get('index','?')}")

    return issues


def check_shard_sizes(b: DiagnosticBundle) -> int:
    issues = 0
    section("SHARD SIZES")

    cat_shards = b.read_json("cat_shards.json")
    if cat_shards is None:
        info("cat_shards.json not found – skipping shard size analysis")
        return 0

    large_shards = []
    unassigned   = []

    for s in cat_shards:
        state = s.get("state", "").upper()
        if state == "UNASSIGNED":
            unassigned.append(s)
            continue

        size_str = s.get("store", "") or "0b"
        # Parse size  e.g. "45.3gb", "512mb", "1.2tb"
        size_gb = _parse_size_gb(size_str)
        if size_gb >= SHARD_SIZE_FAIL_GB:
            large_shards.append((s.get("index","?"), s.get("shard","?"), s.get("prirep","?"), size_gb, "fail"))
        elif size_gb >= SHARD_SIZE_WARN_GB:
            large_shards.append((s.get("index","?"), s.get("shard","?"), s.get("prirep","?"), size_gb, "warn"))

    row("Unassigned shards", str(len(unassigned)),
        "ok" if not unassigned else "fail")
    if unassigned:
        issues += 1
        fail(f"{len(unassigned)} unassigned shard(s):")
        for s in unassigned[:10]:
            reason = s.get("unassigned.reason", "unknown")
            print(f"       {s.get('index','?')} shard={s.get('shard','?')} reason={reason}")

    row("Oversized shards (>40 GB)", str(len(large_shards)),
        "ok" if not large_shards else "warn")
    for idx, shard, prirep, size_gb, lvl in large_shards[:10]:
        row(f"  {idx}[{shard}][{prirep}]", f"{size_gb:.1f} GB", lvl)
        if lvl == "fail":
            issues += 1

    return issues


def check_deleted_docs(b: DiagnosticBundle) -> int:
    issues = 0
    section("DELETED DOCUMENTS (SEGMENT BLOAT)")

    stats = b.read_json("indices_stats.json")
    if stats is None:
        info("indices_stats.json not found – skipping deleted docs check")
        return 0

    indices = stats.get("indices", {})
    bloated = []

    for name, idata in indices.items():
        total_docs   = (idata.get("total", {}).get("docs", {}).get("count", 0) or 0)
        deleted_docs = (idata.get("total", {}).get("docs", {}).get("deleted", 0) or 0)
        if total_docs + deleted_docs == 0:
            continue
        ratio = deleted_docs / (total_docs + deleted_docs)
        if ratio >= DELETED_RATIO_WARN:
            bloated.append((name, total_docs, deleted_docs, ratio))

    row("Indices with >20% deleted docs", str(len(bloated)),
        "ok" if not bloated else "warn")

    for name, total, deleted, ratio in sorted(bloated, key=lambda x: -x[3])[:15]:
        row(f"  {name}", f"deleted={deleted:,}  ratio={ratio:.1%}", "warn")
        warn(f"  Consider force-merge or ILM rollover on '{name}' to reclaim space")

    if bloated:
        issues += len(bloated)

    return issues


def _parse_size_gb(s: str) -> float:
    s = s.strip().lower()
    if not s or s in ("-", ""):
        return 0.0
    multipliers = {"tb": 1024, "gb": 1, "mb": 1/1024, "kb": 1/1024**2, "b": 1/1024**3}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                return float(s[:-len(suffix)]) * mult
            except ValueError:
                return 0.0
    return 0.0


def check_index_settings(b: DiagnosticBundle) -> int:
    issues = 0
    section("INDEX SETTINGS REVIEW")

    settings = b.read_json("index_settings.json")
    if settings is None:
        info("index_settings.json not found – skipping")
        return 0

    no_replicas = []
    read_only   = []

    for idx_name, cfg in settings.items():
        idx_cfg = cfg.get("settings", {}).get("index", {})

        reps = idx_cfg.get("number_of_replicas", "1")
        if str(reps) == "0":
            no_replicas.append(idx_name)

        ro = idx_cfg.get("blocks", {}).get("read_only_allow_delete") or \
             idx_cfg.get("blocks", {}).get("read_only")
        if str(ro).lower() == "true":
            read_only.append(idx_name)

    row("Indices with 0 replicas", str(len(no_replicas)),
        "ok" if not no_replicas else "warn")
    if no_replicas:
        warn("Indices with no replicas have no redundancy:")
        for n in no_replicas[:10]:
            print(f"       {n}")

    row("Read-only blocked indices", str(len(read_only)),
        "ok" if not read_only else "fail")
    if read_only:
        fail("Read-only block active (likely caused by disk watermark breach):")
        for n in read_only[:10]:
            print(f"       {n}")
        issues += len(read_only)

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total = 0
    total += check_indices_health(b)
    total += check_shard_sizes(b)
    total += check_deleted_docs(b)
    total += check_index_settings(b)

    section("INDICES SUMMARY")
    if total == 0:
        ok("No index-level issues detected")
    else:
        fail(f"{total} index issue(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
