# Clickmate

Clickmate is a macOS-friendly Python autoclicker. It prefers native Quartz CoreGraphics events on macOS (when available) and falls back to `pynput` or `pyautogui`. It features randomized delays, adjustable hold time (“pressure”), and a clean single-line status UI.

## Features

- Start/Pause with `s`
- Randomized delay per click (0.5×–1.5× of base)
- Adjust speed with `+` (faster) / `-` (slower)
- Adjust hold time with `]` (increase) / `[` (decrease)
- Toggle click engine with `m` (`pynput` → `quartz` → `pyautogui`)
- Single test click with `c`
- Optional jitter movement `j` and debug logs `d`
- Global hotkey to lock/unlock local keys: `Ctrl+Alt+K`

Defaults: delay `0.50s`, hold `0.10s`, method `quartz` (if available), jitter off.

## Install and run (uv)

Requires Python `>=3.11` and `uv`.

- Quick, no install:
   ```bash
   uvx clickmate --help
   uvx clickmate --version
   uvx clickmate
   ```

- Install as a tool:
   ```bash
   uv tool install clickmate
   # then
   clickmate
   ```

- From a local checkout:
   ```bash
   # run with a fresh, isolated env and pick up local changes
   uv tool run --from . --refresh clickmate
   # or install locally as a tool
   uv tool install .
   ```

Development:
```bash
uv sync
uv run clickmate --help
uv run clickmate
# or run the module entrypoint
uv run -m autoclicker --help
```

Tip: If `uv tool run --from . clickmate` doesn’t reflect local changes, add `--refresh` (above). Alternatively, bump the version in `pyproject.toml` or uninstall/reinstall the tool:
```bash
uv tool uninstall clickmate
uv tool install .
```

## Usage

1) Run the program (see above). 2) Move the mouse to your target. 3) Press `s` to start; press `s` again to pause. Use `+`/`-` to change speed and `]`/`[` to change hold time. Use `m` to switch engines when needed. Press `Ctrl+Alt+K` anytime to lock/unlock local hotkeys (safety). Exit with `Ctrl+C`.

### Hotkeys

- `s` — start/pause
- `+` / `-` — faster / slower
- `]` / `[` — increase / decrease hold time
- `m` — toggle engine (`pynput` → `quartz` → `pyautogui`)
- `c` — single test click
- `j` — toggle jitter
- `d` — toggle debug logs
- `Ctrl+Alt+K` — global lock/unlock local keys

## Status line

The app renders one continuously updated status line with fixed-width fields and a spinner while clicking.

Example:
```
▶ | delay: 0.50s | rng: 0.25–0.75 | hold: 0.10s | meth: QTZ | jitter: - | debug: - | lock: no | clicks: 000042 | last: 0.18s | next: 0.43s | cps: 3.5 | fb:1 | method quartz
```

Key fields:
- `delay` base delay; actual delays are randomized within `rng` (0.5×–1.5×)
- `hold` button press duration (“pressure”)
- `meth` engine: `QTZ` (Quartz), `PNP` (pynput), `PGA` (pyautogui)
- `lock` `yes` when local keys are locked (only `Ctrl+Alt+K` works)
- `fb:N` fallback count when switching engines was required

Notes: colors when TTY; ephemeral messages fade after ~2.5s; no extra newlines.

## macOS permissions

Grant permissions to your terminal app (Terminal/iTerm/VS Code):
1. System Settings → Privacy & Security → Accessibility → add your terminal
2. System Settings → Privacy & Security → Input Monitoring → add your terminal
3. Restart the terminal

Quartz clicks need the `Quartz` module (PyObjC). If unavailable, Clickmate automatically uses `pynput`.

## Troubleshooting

- Keys don’t work or clicks are blocked: re-check Accessibility and Input Monitoring permissions.
- App ignores clicks: press `m` to switch engines (prefer `quartz` on macOS), enable jitter `j`, or increase hold time `]` to ~0.02–0.05s.
- Output looks noisy: run in a normal terminal to get the single-line status.

## CI/CD and releases

- CI (`.github/workflows/ci.yml`): `uv sync`, `ruff`, and `pytest` on Python 3.11–3.13.
- Release (`.github/workflows/release.yml`): pushing a tag like `v1.2.3` triggers a build (`uv build --no-sources`) and publish via PyPI Trusted Publishing (OIDC). The package version is derived from the tag and injected during the build. TestPyPI publishing is not used.

## Contributing and community

- See `CONTRIBUTING.md` for development and PR guidelines.
- See `CODE_OF_CONDUCT.md` for community expectations.
- Security: see `SECURITY.md`.

## License

MIT — see `LICENSE`.

## Dependencies

- `pyautogui` — automation
- `pynput` — input handling and alternative click path
- Optional: `pyobjc` (provides `Quartz`) — enables Quartz engine on macOS