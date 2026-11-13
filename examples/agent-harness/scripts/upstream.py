#!/usr/bin/env python3
"""Run the shared upstream maintenance tool from this harness example."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[3] / "tools/upstream.py"), run_name="__main__")
