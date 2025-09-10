"""CLI entrypoint for autoclicker.

Usage:
    autoclicker [--help] [--version]

Without flags, starts the interactive autoclicker. See README for hotkeys
and macOS permission requirements.
"""

from __future__ import annotations


def main() -> None:
    # Parse minimal flags without importing heavy modules.
    import sys

    argv = sys.argv[1:]
    if any(a in ("-h", "--help") for a in argv):
        print(
            """
autoclicker — macOS-friendly Python autoclicker

Usage:
  autoclicker [--help] [--version]

Notes:
  - Grant Accessibility and Input Monitoring permissions to your terminal app
    in macOS settings, then restart the terminal.
  - Hotkeys:
      s start/pause • +/− speed • ]/[ hold • m method • c test
      j jitter • d debug • Ctrl+Alt+K lock
            """.strip()
        )
        return

    if any(a in ("-V", "--version") for a in argv):
        from . import __version__

        print(__version__)
        return

    # Start the application only when not handling flags.
    from . import app

    app.main()
