#!/usr/bin/env python3
"""Build an external consumer after relocating the installed prefix."""
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import sys
import json

parser = argparse.ArgumentParser()
parser.add_argument("--build", type=Path, required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--sdk", type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source / "tools"))
from build import host_programs, sdk_identity
programs = host_programs(args.sdk)
sdk_before = sdk_identity(args.sdk) if args.sdk else None
environment = os.environ.copy()
browser_sdk = bool(args.sdk and json.loads((args.sdk / "sdk.json").read_text())["target"]["system"] == "Emscripten")
if args.sdk:
    environment["PYTHONDONTWRITEBYTECODE"] = "1"


def run(command, **kwargs):
    if command[0] == "cmake":
        command[0] = programs["cmake"]
    subprocess.run([str(part) for part in command], check=True, env=kwargs.pop("env", environment), **kwargs)


with tempfile.TemporaryDirectory(prefix="foundation install ") as directory:
    root = Path(directory)
    original = root / "original prefix"
    moved = root / "relocated prefix"
    run(["cmake", "--install", args.build, "--config", args.config, "--prefix", original])
    original.rename(moved)
    for section, name in (("man1", "foundation-cli.1"), ("man7", "software-foundation.7")):
        copies = list(moved.rglob(section + "/" + name))
        if len(copies) != 1 or copies[0].read_bytes() != (args.source / "docs/man" / name).read_bytes():
            raise RuntimeError("installed manual missing, duplicated or changed: " + name)
    # Build only against the install, without access to its original location.
    consumer = root / "consumer source"
    shutil.copytree(args.source / "examples/consumer", consumer)
    configs = list(moved.rglob("FoundationConfig.cmake"))
    if len(configs) != 1:
        raise RuntimeError("installed package configuration missing or ambiguous")
    extra = []
    if args.sdk:
        extra = ["-DCMAKE_TOOLCHAIN_FILE=" + str(args.source / "cmake/toolchains/sdk.cmake"),
                 "-DFOUNDATION_SDK_ROOT=" + str(args.sdk.resolve())]
        if programs["ninja"] != "ninja":
            extra += ["-DCMAKE_MAKE_PROGRAM=" + programs["ninja"]]
    run(["cmake", "-S", consumer, "-B", root / "consumer build", "-G", "Ninja",
         "-DCMAKE_BUILD_TYPE=" + args.config, "-DFoundation_DIR=" + str(configs[0].parent),
         "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF", "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF", *extra])
    run(["cmake", "--build", root / "consumer build", "--parallel", "2"])
    suffix = ".js" if browser_sdk else (".exe" if __import__("os").name == "nt" else "")
    executor = [args.sdk / "node/bin/node"] if browser_sdk else []
    run([*executor, root / "consumer build" / ("consumer" + suffix)])
    clean = {key: value for key, value in os.environ.items() if key not in
             ("LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES")}
    run([*executor, moved / "bin" / ("foundation-cli" + suffix), "--self-check"], cwd=moved, env=clean)
    if args.sdk and sdk_identity(args.sdk) != sdk_before:
        raise ValueError("SDK changed while checking its installed consumer")
