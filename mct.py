# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line entry point: `python mct.py ...` from source, or mct.exe when installed."""
import sys

from colorassist.cli import main

if __name__ == "__main__":
    sys.exit(main())
