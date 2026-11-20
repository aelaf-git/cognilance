"""Copy and restore coordinator.db and checkpoints.db."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

FILES = ("coordinator.db", "checkpoints.db")


def copy_databases(source: Path, dest: Path) -> None:
    """Copy the two coordinator SQLite files from source into dest."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = source / name
        if not src.is_file():
            raise FileNotFoundError(f"Missing {src}")
        shutil.copy2(src, dest / name)


def restore_databases(source: Path, dest: Path) -> None:
    """Write the copied SQLite files back into dest."""
    copy_databases(source, dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("copy", "restore"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args(argv)
    action = copy_databases if args.command == "copy" else restore_databases
    try:
        action(args.source, args.dest)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
