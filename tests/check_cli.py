#!/usr/bin/env python3
import subprocess
import sys

executable = sys.argv[1]


def check(args, code, stdout=None):
    result = subprocess.run([executable, *args], capture_output=True, text=True)
    if result.returncode != code or (stdout is not None and result.stdout != stdout):
        raise RuntimeError(f"CLI contract failed: {args!r}: {result}")


check(["--version"], 0, "software-foundation 0.1.0\n")
check(["--self-check"], 0, "")
check(["--", "Alpha", "Beta"], 0, "1\tAlpha\n2\tBeta\n")
check(["--", "Valid", "bad\ntext"], 1, "")
check(["--unknown"], 2, "")
check(["--"], 2, "")

# Exercise actual write failure on hosts providing the standard full device.
from pathlib import Path
if Path("/dev/full").exists():
    for args in (["--version"], ["--help"], ["--", "Entry"]):
        with open("/dev/full", "wb") as destination:
            result = subprocess.run([executable, *args], stdout=destination, stderr=subprocess.PIPE)
        if result.returncode != 1:
            raise RuntimeError("CLI reported success after output failure")
