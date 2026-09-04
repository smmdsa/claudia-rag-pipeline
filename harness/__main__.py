"""Entry point for `python3 -m harness`."""
import sys

from harness.cli import main

sys.exit(main(sys.argv[1:]))
