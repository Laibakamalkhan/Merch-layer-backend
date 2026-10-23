#!/usr/bin/env python3
"""Pre-commit / CI script to ensure no real secrets are committed into git."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Secret patterns to detect
PATTERNS = [
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "Groq API key (gsk_...)"),
    (re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"), "NVIDIA API key (nvapi-...)"),
    (re.compile(r"eyJhbGciOi[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "JWT token (eyJhbGci...)"),
    (re.compile(r"postgres(?:ql)?://(?!(?:USER:PASSWORD|user:password|<[^>]+>))[^:]+:[^@]+@", re.IGNORECASE), "PostgreSQL connection string with credentials"),
]

IGNORED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "dist-ssr",
    "build",
    ".git",
    "__pycache__",
    ".pytest_cache",
}

# Binary / media file extensions to skip
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".7z",
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
}


def get_tracked_files(repo_root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        files = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            path = repo_root / line
            files.append(path)
        return files
    except Exception as exc:
        print(f"Error running git ls-files: {exc}", file=sys.stderr)
        sys.exit(2)


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
    except Exception:
        return True
    return False


def main() -> int:
    # Find repository root (look for .git)
    current = Path(__file__).resolve().parent
    repo_root = current
    while repo_root.parent != repo_root:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    files = get_tracked_files(repo_root)
    violations = []

    for file_path in files:
        if not file_path.is_file():
            continue

        parts = set(file_path.parts)
        if parts & IGNORED_DIRS:
            continue

        if is_binary(file_path):
            continue

        rel_path = file_path.relative_to(repo_root)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, start=1):
                    for pattern, label in PATTERNS:
                        if pattern.search(line):
                            violations.append(f"{rel_path}:{line_num}: {label}")
        except Exception as exc:
            print(f"Could not read {rel_path}: {exc}", file=sys.stderr)

    if violations:
        print(f"FAILED: Found {len(violations)} potential secret(s) in tracked files:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"SUCCESS: Scanned {len(files)} tracked files. No secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())