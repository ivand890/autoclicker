import os

# Force pynput to use dummy backend on CI
os.environ["PYNPUT_BACKEND"] = "dummy"
