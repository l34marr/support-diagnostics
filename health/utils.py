"""
Shared utilities for Elasticsearch Diagnostic Health Check scripts.
Supports the elastic/support-diagnostics ZIP output format.
"""

import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Optional

# ── ANSI colours ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

STATUS_OK   = f"{GREEN}✔  OK{RESET}"
STATUS_WARN = f"{YELLOW}⚠  WARN{RESET}"
STATUS_FAIL = f"{RED}✘  FAIL{RESET}"
STATUS_INFO = f"{CYAN}ℹ  INFO{RESET}"


def status_label(level: str) -> str:
    return {"ok": STATUS_OK, "warn": STATUS_WARN, "fail": STATUS_FAIL}.get(level.lower(), STATUS_INFO)


def section(title: str) -> None:
    bar = "─" * 70
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}")


def row(label: str, value: str, level: str = "info") -> None:
    badge = status_label(level)
    print(f"  {badge}  {BOLD}{label:<40}{RESET}  {value}")


def info(msg: str) -> None:
    print(f"  {STATUS_INFO}  {msg}")


def warn(msg: str) -> None:
    print(f"  {STATUS_WARN}  {YELLOW}{msg}{RESET}")


def fail(msg: str) -> None:
    print(f"  {STATUS_FAIL}  {RED}{msg}{RESET}")


def ok(msg: str) -> None:
    print(f"  {STATUS_OK}  {GREEN}{msg}{RESET}")


# ── ZIP / file helpers ───────────────────────────────────────────────────────

class DiagnosticBundle:
    """Wraps the support-diagnostics ZIP or extracted directory."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._zf: Optional[zipfile.ZipFile] = None
        self._root: Optional[str] = None          # prefix inside zip

        if self.path.suffix == ".zip":
            self._zf = zipfile.ZipFile(self.path)
            names = self._zf.namelist()
            # The zip may have a single top-level folder
            tops = {n.split("/")[0] for n in names if n.strip()}
            self._root = tops.pop() if len(tops) == 1 else ""
        elif self.path.is_dir():
            pass
        else:
            raise FileNotFoundError(f"Cannot open diagnostic bundle: {path}")

    # ── internal ──────────────────────────────────────────────────────────
    def _zip_path(self, relative: str) -> str:
        if self._root:
            return f"{self._root}/{relative}"
        return relative

    def read_text(self, relative: str) -> Optional[str]:
        """Return file content as string, or None if not found."""
        if self._zf:
            zp = self._zip_path(relative)
            try:
                with self._zf.open(zp) as fh:
                    return fh.read().decode("utf-8", errors="replace")
            except KeyError:
                return None
        fp = self.path / relative
        if fp.exists():
            return fp.read_text(errors="replace")
        return None

    def read_json(self, relative: str) -> Optional[Any]:
        txt = self.read_text(relative)
        if txt is None:
            return None
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return None

    def glob(self, pattern: str) -> list[str]:
        """Return relative paths matching a simple glob (* supported)."""
        if self._zf:
            prefix = self._zip_path("").rstrip("/") + "/"
            regex  = re.compile(
                "^" + re.escape(prefix)
                + pattern.replace("*", "[^/]+").replace("**", ".*")
                + "$"
            )
            return [
                n[len(prefix):]
                for n in self._zf.namelist()
                if regex.match(n)
            ]
        base = self.path
        return [str(p.relative_to(base)) for p in base.glob(pattern)]

    def exists(self, relative: str) -> bool:
        if self._zf:
            return self._zip_path(relative) in self._zf.namelist()
        return (self.path / relative).exists()

    def __del__(self):
        if self._zf:
            self._zf.close()


def load_bundle(zip_path: str) -> DiagnosticBundle:
    return DiagnosticBundle(zip_path)
