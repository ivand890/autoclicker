"""Update project versions from VERSION env.

This script updates:
- pyproject.toml [project].version (via tomlkit)
- src/autoclicker/__init__.py __version__
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def main() -> None:
    version = os.environ.get("VERSION")
    if not version:
        raise SystemExit("VERSION env var is required")

    pyproject_path = Path("pyproject.toml")
    init_path = Path("src/autoclicker/__init__.py")

    # Update pyproject.toml
    try:
        import tomlkit  # type: ignore
    except Exception as e:
        raise SystemExit(f"tomlkit is required in CI to update pyproject.toml: {e}")

    text = pyproject_path.read_text(encoding="utf-8")
    doc = tomlkit.parse(text)
    proj = doc.get("project")
    if not isinstance(proj, dict):
        raise SystemExit("[project] table not found in pyproject.toml")
    proj["version"] = version
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    # Update __version__ in package __init__
    init_text = init_path.read_text(encoding="utf-8") if init_path.exists() else ""
    pattern = re.compile(r"^(?P<prefix>\s*__version__\s*=\s*['\"])\S*(?P<quote>['\"])", re.MULTILINE)
    if pattern.search(init_text):
        new_text = pattern.sub(fr"\g<prefix>{version}\g<quote>", init_text)
    else:
        new_text = init_text.rstrip() + f"\n__version__ = \"{version}\"\n"
    init_path.write_text(new_text, encoding="utf-8")

    print("Updated versions:")
    print(" - pyproject.toml [project].version =", version)
    print(" - src/autoclicker/__init__.py __version__ =", version)


if __name__ == "__main__":
    main()
