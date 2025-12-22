import os
import sys
from unittest.mock import MagicMock

# Force pynput to use dummy backend on CI
os.environ["PYNPUT_BACKEND"] = "dummy"

# Mock pyautogui and mouseinfo  headless CI
if "pyautogui" not in sys.modules:
    m_pyautogui = MagicMock()
    # Set default attributes accessed by app.py
    m_pyautogui.FAILSAFE = False
    m_pyautogui.PAUSE = 0.1
    sys.modules["pyautogui"] = m_pyautogui

if "mouseinfo" not in sys.modules:
    sys.modules["mouseinfo"] = MagicMock()
