#!/usr/bin/env python3
"""Checked CI scheduling and package operations shared with local development."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STANDARD = {"linux-x86_64": "ubuntu-24.04", "linux-aarch64": "ubuntu-24.04-arm",
            "windows-x86_64": "windows-2022"}


def plan(devfast=False, include_arm=True, pool="standard", configured=""):
    if pool not in ("standard", "faster"):
        raise ValueError("unknown runner pool")
    if pool == "faster" and not re.fullmatch(r"foundation-linux-[a-z0-9-]+", configured):
        raise ValueError("explicit authorized larger-runner label required")
    targets = [x for x in STANDARD if include_arm or x != "linux-aarch64"]
    packages, checks = [], []
    for target in targets:
        runner = configured if target == "linux-x86_64" and pool == "faster" else STANDARD[target]
        packages.append({"target": target, "runner": runner})
        for scope in (["core"] if devfast else ["core", "tools", "integration"]):
            checks.append({"target": target, "runner": runner, "scope": scope})
    return {"checks": {"include": checks}, "packages": {"include": packages}}


def assert_host(target):
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    system = platform.system().lower()
    if target != system + "-" + machine:
        raise ValueError("actual host differs from selected execution target")
    return {"target": target, "system": system, "machine": machine, "release": platform.release(),
            "python": platform.python_version()}


def run(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def archives(directory):
    values = sorted(list(directory.rglob("*.tar.gz")) + list(directory.rglob("*.zip")))
    if not values:
        raise ValueError("no application archives found")
    names = [x.name for x in values]
    if len(names) != len(set(names)):
        raise ValueError("duplicate application archive names")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--devfast", action="store_true")
    p.add_argument("--no-arm", action="store_true")
    p.add_argument("--pool", choices=("standard", "faster"), default="standard")
    p.add_argument("--configured", default="")
    p.add_argument("--github-output", type=Path)
    p = sub.add_parser("host")
    p.add_argument("target", choices=tuple(STANDARD))
    p = sub.add_parser("package")
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=2)
    p = sub.add_parser("check-archives")
    p.add_argument("directory", type=Path)
    p.add_argument("--runtime-only", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(args.devfast, not args.no_arm, args.pool, args.configured)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as out:
                for key, value in result.items():
                    out.write(key + "=" + json.dumps(value, separators=(",", ":")) + "\n")
        print(json.dumps(result, indent=2))
    elif args.command == "host":
        print(json.dumps(assert_host(args.target)))
    elif args.command == "package":
        if args.jobs < 1:
            raise ValueError("positive compile concurrency required")
        run([sys.executable, "tools/build.py", "package", "release", "--portable", "--build-dir", args.build,
             "--jobs", str(args.jobs)])
        for archive in archives(args.build / "packages"):
            manifest = archive.with_name(archive.name + ".json")
            for operation in ("create", "verify"):
                run([sys.executable, "tools/artifact.py", operation, archive, "--manifest", manifest])
    else:
        for archive in archives(args.directory):
            run([sys.executable, "tools/artifact.py", "verify", archive,
                 "--manifest", archive.with_name(archive.name + ".json"),
                 *(["--runtime-only"] if args.runtime_only else [])])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("CI: " + str(error), file=sys.stderr)
        sys.exit(1)
