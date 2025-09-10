# Clickmate

Clickmate is a Python autoclicker with a macOS-friendly multi-engine click system. It prefers native Quartz CoreGraphics events on macOS (when available) for best compatibility, and falls back to `pynput` or `pyautogui` if needed. Randomized delays, adjustable “pressure” (hold time), and a single-line status display are built in.

## Features

- Start/Pause with `s`
- Random delay per click (0.5×–1.5× of the base delay)
- Adjust click speed on the fly with `+` (faster) and `-` (slower)
- Adjust click “pressure” (hold duration) with `]` (increase) and `[` (decrease)
- Toggle click method with `m` (cycles: `pynput` → `quartz` → `pyautogui`)
- One-off test click with `c`
- Optional debug logs with `d`
- Optional tiny jitter movement before each click (`j`) to improve acceptance in some apps
- Global hotkey to lock/unlock local keys: `Ctrl+Alt+K` (works system-wide)

### Defaults

- Base delay: `0.50s`
- Hold time (pressure): `0.10s`
- Click method: `quartz` if Quartz/PyObjC is available; otherwise `pynput`
- Jitter: disabled by default

## Installation & CLI usage (uv)

Requires Python `>=3.11` and `uv` installed.

- One-off run without installation (preferred for quick use):

   ```bash
   uvx clickmate --help
   uvx clickmate --version
   uvx clickmate
   ```

- Install globally as a persistent tool (adds `autoclicker` to your `PATH`):

   ```bash
   uv tool install clickmate
   # then simply:
   clickmate
   ```

- Run from a local checkout without publishing:

   ```bash
   # ephemeral run from the current workspace
   # NOTE: `uv tool run` uses a cached, isolated env. Add `--refresh` to
   # pick up local source changes if you haven't bumped the version.
   uv tool run --from . --refresh clickmate
   # or install the local project as a tool
   uv tool install .
   ```

Development workflow (recommended):

- Set up the project environment and run the packaged script:

   ```bash
   uv sync
      # see flags
      uv run clickmate --help
      uv run clickmate --version
      # run the console script
      uv run clickmate
   # or run the module directly
      uv run -m autoclicker --help
   ```

Tip: If `uv tool run --from . autoclicker` dont reflect your local changes,
it's likely using a previously cached tool environment. Fix it by either:

- adding `--refresh` (recommended for local dev):

  ```bash
   uv tool run --from . --refresh clickmate --help
   uv tool run --from . --refresh clickmate --version
  ```

- or bumping the package `version` in `pyproject.toml` (forces a new cache key)
- or pruning caches:

  ```bash
  uv cache clean autoclicker
  ```

## Usage

1. Run the program (any of the methods above):

2. Move your mouse to the desired click position.
3. Press `s` to start; press `s` again to pause.
4. Use `+`/`-` to change speed; use `]`/`[` to change hold time.
5. Use `m` to switch engines if your app ignores clicks; `quartz` generally works best on macOS.
6. Use `Ctrl+Alt+K` anytime to lock/unlock local keys (prevents accidental hotkey presses). This does not start/pause clicking; it only enables/disables local hotkeys.
7. Press `Ctrl+C` to exit.

### Hotkeys (summary)

- `s` — start/pause
- `+` / `-` — faster / slower
- `]` / `[` — increase / decrease hold time (pressure)
- `m` — toggle click method (`pynput` → `quartz` → `pyautogui`)
- `c` — single test click
- `j` — toggle jitter movement
- `d` — toggle debug logs
- `Ctrl+Alt+K` — global lock/unlock local keys (works system-wide)

## Status line

When running, the app renders a single, continuously-updated status line. It uses fixed-width fields and stays on one terminal line (no log spam). A small spinner animates while clicking.

Example:

```
▶ | delay: 0.50s | rng: 0.25–0.75 | hold: 0.10s | meth: QTZ | jitter: - | debug: - | lock: no | clicks: 000042 | last: 0.18s | next: 0.43s | cps: 3.5 | fb:1 | method quartz
```

Field notes:

- `delay` — base delay; each actual delay is randomized within `rng` (0.5×–1.5×)
- `hold` — how long the button is held down per click (the “pressure”)
- `meth` — click engine: `QTZ` (Quartz), `PNP` (pynput), `PGA` (pyautogui)
- `jitter` — `J` when enabled, otherwise `-`
- `debug` — `D` when debug logging is on, otherwise `-`
- `lock` — `yes` when local keys are locked (only `Ctrl+Alt+K` works); `no` otherwise
- `clicks` — total clicks since start
- `last` — time since the last click
- `next` — the next randomized delay (shown while waiting)
- `cps` — average clicks per second since start
- `fb:N` — shown when a click had to fall back to another engine
- trailing message — brief, ephemeral messages (e.g., when switching method)

Notes:

- Colors are used when the output is a TTY; `lock:yes` is highlighted.
- Messages are inline and fade after ~2.5s; no extra newlines are printed.

## macOS permissions

For keyboard and mouse automation to work, macOS must trust your terminal:

1. System Settings → Privacy & Security → Accessibility → add your terminal (Terminal, iTerm, or VS Code)
2. System Settings → Privacy & Security → Input Monitoring → add your terminal
3. Restart the terminal and run again

Quartz (CoreGraphics) clicks require the `Quartz` Python module (PyObjC). If it’s not installed, the app will automatically use `pynput`. You don’t need to install PyObjC unless you specifically want Quartz.

## Troubleshooting

- Keys don’t work or clicks are blocked: verify Accessibility and Input Monitoring permissions (see above).
- Clicks ignored by the target app:
  - Press `m` to switch engines; try `quartz` first on macOS
  - Enable jitter with `j` (adds a subtle 1px move before click)
  - Increase hold time with `]` to ~0.02–0.05s
- Terminal output looks noisy: that’s likely not a TTY; run in a normal terminal to see the single-line status, or consider adding flags later to reduce output.

## CI/CD (GitHub Actions + uv)

This repo uses GitHub Actions with `uv` for linting, testing, building, and publishing:

- CI (`.github/workflows/ci.yml`): runs on pushes/PRs, installs with `uv sync`, lints with `ruff`, and runs `pytest` across Python 3.11–3.13.
- Release (`.github/workflows/release.yml`): on tags like `v0.1.0`, builds via `uv build --no-sources` and publishes via `uv publish` using PyPI Trusted Publishing (OIDC).

To publish:

1. Configure a Trusted Publisher for the PyPI project `autoclicker` (and optionally TestPyPI).
2. Push a tag `vX.Y.Z` to trigger the release workflow.
3. Pre-release tags containing `rc` will also publish to TestPyPI.

## Contributing and community

- Please see `CONTRIBUTING.md` for how to set up your environment and submit PRs.
- See `CODE_OF_CONDUCT.md` for expected community behavior.
- Security reports: see `SECURITY.md`.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Dependencies

- `pyautogui` — automation
- `pynput` — input handling and alternative click path
- Optional: `pyobjc` (provides the `Quartz` module) — enables the Quartz click engine on macOS