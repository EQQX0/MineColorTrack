"""Command-line entry point: `python mct.py ...` from source, or mct.exe when installed."""
import sys

from colorassist.cli import main

if __name__ == "__main__":
    sys.exit(main())
