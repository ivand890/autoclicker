# Autoclicker

A Python script that implements an autoclicker using the pyautogui library, with a default click engine powered by pynput on macOS for higher reliability. It also includes a Quartz CoreGraphics engine for apps that require native CGEvents.

## Features

- Start/Pause with `s`
- Random time between clicks (between 0.5x and 1.5x the base delay)
- Adjustable click speed on the fly with `+` (increase speed) and `-` (decrease speed)
- Adjustable click "pressure" (hold duration) with `]` to increase and `[` to decrease
- Toggle click method with `m` (cycles: `pynput` → `quartz` → `pyautogui`)
- One-off test click with `c`
- Optional debug logs with `d`
- Optional tiny jitter movement before each click (improves app acceptance)

## Installation

1. Ensure you have Python 3.11 or higher.
2. Install dependencies using uv:

   ```
   uv sync
   ```

## Usage

1. Run the script:

   ```
   uv run main.py
   ```

2. Move your mouse to the desired click position.
3. Press `s` to start the autoclicker.
4. Press `s` again to pause.
5. Use `+` to increase speed (decrease delay).
6. Use `-` to decrease speed (increase delay).
7. Use `]` / `[` to increase/decrease the hold time (pressure).
8. Press `m` to toggle between click methods (`pynput`/`quartz`/`pyautogui`) if one doesn't work with your app.
9. Press `c` for a single test click where the cursor is.
10. Press `j` to toggle the small pre-click jitter.
11. Press `d` to toggle verbose debug logs.
12. Use `Ctrl+Alt+K` to lock/unlock all local keys (prevents accidental presses).
13. Press Ctrl+C to stop the script.

**Global Hotkey**: `Ctrl+Alt+K` works system-wide to lock/unlock local keys, even when the terminal window is not focused. This prevents accidental key presses from interfering with the autoclicker.

### Hotkeys (summary)

- `s` — start/pause
- `+` / `-` — faster / slower
- `]` / `[` — increase / decrease hold time (pressure)
- `m` — toggle click method (`pynput` → `quartz` → `pyautogui`)
- `c` — single test click
- `j` — toggle jitter movement
- `d` — toggle debug logs
- `Ctrl+Alt+K` — global lock/unlock local keys (works system-wide)

## Troubleshooting

- **Permission Error**: If you see "This process is not trusted! Input event monitoring will not be possible until it is added to accessibility clients."
  - Go to System Settings > Privacy & Security > Accessibility
  - Click the + button and add your terminal application (e.g., Terminal, iTerm, VS Code)
  - Also go to System Settings > Privacy & Security > Input Monitoring
  - Add your terminal application there as well
  - Restart the terminal and try running the script again
- If the script doesn't respond to keys, ensure you have the necessary permissions for keyboard input.
- The autoclicker clicks at the current mouse position, so position your mouse accordingly.
- If clicks don't register in your target application, some apps may block automated input:
   - Try pressing `m` to switch engines. `quartz` often works best on macOS.
   - Enable jitter with `j` (a 1px nudge before click).
   - Increase hold time (pressure) with `]` to ~0.02–0.05s.

## Dependencies

- pyautogui: For mouse and keyboard automation
- pynput: For hotkey detection and macOS-native mouse clicks