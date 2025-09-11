"""Validate VERSION env against SemVer using the semver library.

Exits non-zero with an error message if invalid.
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    version = os.environ.get("VERSION")
    if not version:
        print("VERSION env var is required", file=sys.stderr)
        raise SystemExit(1)

    try:
        import semver  # type: ignore
    except ImportError as e:
        print(f"Missing 'semver' dependency: {e}", file=sys.stderr)
        raise SystemExit(1)

    try:
        semver.Version.parse(version)
    except ValueError as e:
        print(f"Invalid SemVer '{version}': {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Valid SemVer: {version}")


if __name__ == "__main__":
    main()
