#!/usr/bin/env python3
"""Fail when Go imports point out of the go-clean-api layer map.

Scans non-test .go files under a module root. Exit 0 when the arrow holds,
exit 1 when a layer imports a package it must not see. Exit 2 on usage errors.

    python3 check_layers.py <module-root>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# (path fragment that identifies the layer, import substrings that break the arrow)
RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "/internal/domain/",
        (
            "/internal/application/",
            "/internal/infrastructure/",
            "/internal/delivery/",
            "/config",
            "github.com/go-chi/",
            "github.com/jackc/pgx",
            "database/sql",
            "net/http",
        ),
    ),
    (
        "/internal/application/",
        (
            "/internal/infrastructure/",
            "/internal/delivery/",
            "/config",
            "github.com/go-chi/",
            "github.com/jackc/pgx",
            "database/sql",
            "net/http",
        ),
    ),
    (
        "/internal/infrastructure/",
        (
            "/internal/application/",
            "/internal/delivery/",
        ),
    ),
    (
        "/internal/delivery/",
        (
            # Persistence must stay behind a port. Security and observability
            # are edge packages delivery is allowed to import; cmd still wires them.
            "/internal/infrastructure/database",
            "github.com/jackc/pgx",
            "database/sql",
        ),
    ),
    (
        "/config/",
        (
            "/internal/",
        ),
    ),
)

IMPORT_BLOCK = re.compile(r"^import\s+\((.*?)\)", re.M | re.S)
IMPORT_LINE = re.compile(r'^import\s+(?:\w+\s+)?"([^"]+)"', re.M)
QUOTED = re.compile(r'"([^"]+)"')


def imports_of(text: str) -> list[str]:
    found: list[str] = []
    for block in IMPORT_BLOCK.findall(text):
        found.extend(QUOTED.findall(block))
    found.extend(IMPORT_LINE.findall(text))
    return found


def layer_key(rel: str) -> str:
    """Normalize so the fragment matches whether or not the path has a leading slash."""
    return "/" + rel.lstrip("/")


def violations(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rel = layer_key(str(path.relative_to(root)))
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            hits.append(f"{path}:0: cannot read ({exc})")
            continue
        for fragment, banned in RULES:
            if fragment not in rel:
                continue
            for imp in imports_of(text):
                if any(b in imp for b in banned):
                    hits.append(f"{path.relative_to(root)}: imports {imp}")
            break
    return hits


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_layers.py <module-root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    hits = violations(root)
    if not hits:
        print(f"ok {root}")
        return 0
    print(f"{len(hits)} layer violation(s) in {root}")
    for hit in hits:
        print(hit)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
