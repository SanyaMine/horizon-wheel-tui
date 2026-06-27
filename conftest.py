import os
import sys

# Ensure the project root (this file's dir) is importable so `hwt` and `tests` resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
