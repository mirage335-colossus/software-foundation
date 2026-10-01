#!/usr/bin/env python3
"""Build an external consumer after relocating the installed prefix."""
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--build", type=Path, required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--config", required=True)
args = parser.parse_args()


def run(command, **kwargs):
    subprocess.run([str(part) for part in command], check=True, **kwargs)


with tempfile.TemporaryDirectory(prefix="foundation install ") as directory:
    root = Path(directory)
    original = root / "original prefix"
    moved = root / "relocated prefix"
    run(["cmake", "--install", args.build, "--config", args.config, "--prefix", original])
    original.rename(moved)
    # Build only against the install, without access to its original location.
    consumer = root / "consumer source"
    shutil.copytree(args.source / "examples/consumer", consumer)
    configs = list(moved.rglob("FoundationConfig.cmake"))
    if len(configs) != 1:
        raise RuntimeError("installed package configuration missing or ambiguous")
    run(["cmake", "-S", consumer, "-B", root / "consumer build", "-G", "Ninja",
         "-DCMAKE_BUILD_TYPE=" + args.config, "-DFoundation_DIR=" + str(configs[0].parent),
         "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF", "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF"])
    run(["cmake", "--build", root / "consumer build", "--parallel", "2"])
    suffix = ".exe" if __import__("os").name == "nt" else ""
    run([root / "consumer build" / ("consumer" + suffix)])
    clean = {key: value for key, value in os.environ.items() if key not in
             ("LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES")}
    run([moved / "bin" / ("foundation-cli" + suffix), "--self-check"], cwd=moved, env=clean)
