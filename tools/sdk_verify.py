#!/usr/bin/env python3
"""Validate a prepared SDK before CMake enables a target compiler."""
import os
from pathlib import Path
import sys
from build import sdk_identity

try:
    for name in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "CPATH", "C_INCLUDE_PATH",
                 "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "PKG_CONFIG_PATH"):
        if os.environ.get(name):
            raise ValueError("unset host override for SDK build: " + name)
    print(sdk_identity(Path(sys.argv[1]).resolve(strict=True)))
except (OSError, ValueError, KeyError, IndexError) as error:
    print("SDK: " + str(error), file=sys.stderr)
    sys.exit(1)
