"""Startup budget: print the numbers, fail only on a gross regression.

Little Shell's selling point is that it opens fast. This guards it: the cold
import of the window module and a full `--version` process launch are timed,
printed, and checked against generous ceilings (tolerant of slow CI runners).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def time_import() -> float:
    code = ("import time; t=time.perf_counter(); "
            "import littleshell.window.main; print(time.perf_counter()-t)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, timeout=60, check=True)
    return float(out.stdout.strip().splitlines()[-1])


def time_cli(args: list[str]) -> float:
    start = time.perf_counter()
    subprocess.run([sys.executable, "little_shell.py", *args], cwd=ROOT,
                   capture_output=True, timeout=60, check=True)
    return time.perf_counter() - start


def main() -> int:
    imp = time_import()
    ver = time_cli(["--version"])
    print(f"import littleshell.window.main : {imp:.3f}s")
    print(f"little_shell.py --version      : {ver:.3f}s")
    assert imp < 4.0, f"window import regressed: {imp:.2f}s (ceiling 4.0s)"
    assert ver < 8.0, f"--version startup regressed: {ver:.2f}s (ceiling 8.0s)"
    print("startup budget OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
