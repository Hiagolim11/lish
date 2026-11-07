#!/usr/bin/env python3
"""Executable entry point for Little Shell."""

import sys

from littleshell.launcher import forward


if __name__ == "__main__":
    # A Little Shell already open takes the new window (fast, no GTK load).
    code = forward(sys.argv[1:])
    if code is None:
        from littleshell.cli import main

        code = main()
    raise SystemExit(code)
