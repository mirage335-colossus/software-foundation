#!/usr/bin/env python3
"""Verify the complete SDK inventory before CMake initializes the compiler."""
import argparse
import os
from pathlib import Path
from sdk_manifest import verify_sdk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--release', action='store_true')
    args = parser.parse_args()
    for name in ('CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'PKG_CONFIG_PATH'):
        if os.environ.get(name): raise ValueError('unset host search override for SDK builds: ' + name)
    print(verify_sdk(args.root, args.release))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError) as error: raise SystemExit(str(error))
