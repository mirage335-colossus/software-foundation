#!/usr/bin/env python3
"""One incremental build entry point; never installs or downloads dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("jobs must be positive")
    return value


def default_jobs():
    """Conservative cap; explicit --jobs wins for measured workloads."""
    try:
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        cores = os.cpu_count() or 1
    return max(1, min(cores, 4))


def contained(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("SDK paths must be nonempty relative paths")
    resolved = (root / path).resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise ValueError("SDK path escapes its root")
    return resolved


def sdk_identity(root):
    raw = (root / "sdk.json").read_bytes()
    data = json.loads(raw)
    if data["schema_version"] != 1 or not data["recipe_id"]:
        raise ValueError("unsupported or incomplete SDK manifest")
    target = data["target"]
    for key in ("system", "processor", "triple"):
        if not isinstance(target[key], str) or not target[key]:
            raise ValueError("SDK target fields must be nonempty strings")
    if target["system"] != "Linux":
        raise ValueError("the example sysroot toolchain supports Linux targets")
    for key in ("sysroot", "cxx_compiler"):
        contained(root, target[key])
    hashes = data["files"]
    if not hashes or target["cxx_compiler"] not in hashes:
        raise ValueError("SDK inventory must include its compiler")
    # Complete supplier inventories include all compiler support and sysroot files.
    paths = list(root.rglob("*"))
    for path in paths:
        if path.is_symlink():
            contained(root, path.relative_to(root))
        if not path.is_dir() and not path.is_file():
            raise ValueError("SDK contains an unsupported file type")
    actual = {p.relative_to(root).as_posix() for p in paths
              if p.is_file() and p != root / "sdk.json"}
    if actual != set(hashes):
        raise ValueError("SDK file inventory is incomplete or contains extra entries")
    for relative, expected in hashes.items():
        path = contained(root, relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("SDK file checksum mismatch: " + relative)
    return hashlib.sha256(raw).hexdigest()


def cache_identity(build):
    selected = {}
    for line in (build / "CMakeCache.txt").read_text().splitlines():
        if "=" not in line or ":" not in line or line.startswith(("#", "//")):
            continue
        name_type, value = line.split("=", 1)
        name = name_type.split(":", 1)[0]
        if name.startswith(("CMAKE_CXX_", "CMAKE_GENERATOR", "CMAKE_TOOLCHAIN_FILE", "CMAKE_SYSROOT", "FOUNDATION_")) or name in ("CMAKE_BUILD_TYPE", "CMAKE_MAKE_PROGRAM", "BUILD_TESTING"):
            selected[name] = value
    compiler = Path(selected["CMAKE_CXX_COMPILER"]).resolve(strict=True)
    selected["compiler_file_sha256"] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    selected["compiler_resolved_path"] = str(compiler)
    return selected


def run(command, **kwargs):
    print("+ " + subprocess.list2cmdline([str(x) for x in command]), flush=True)
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("build", "test", "package"), default="build")
    parser.add_argument("preset", nargs="?", choices=("dev", "release", "asan"), default=None)
    parser.add_argument("--jobs", type=positive)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--label", choices=("fast", "core", "tools", "integration", "gui"))
    selection.add_argument("--full", action="store_true", help="run all enabled tests (default)")
    parser.add_argument("--sdk", type=Path)
    parser.add_argument("--gui-source", type=Path)
    args = parser.parse_args(argv)
    preset = args.preset or ("release" if args.action == "package" else "dev")
    if (args.label or args.full) and args.action != "test":
        parser.error("test selection applies only to test")
    if args.action == "package" and (preset != "release" or args.gui_source):
        parser.error("package requires release core configuration")
    jobs = args.jobs or positive(os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL") or str(default_jobs()))
    test_jobs = args.jobs or positive(os.environ.get("CTEST_PARALLEL_LEVEL") or str(jobs))
    suffix = ("-sdk" if args.sdk else "") + ("-gui" if args.gui_source else "")
    build = ROOT / "build" / (preset + suffix)
    configure = ["cmake", "--preset", preset, "-B", str(build),
                 "-DFOUNDATION_BUILD_GUI=" + ("ON" if args.gui_source else "OFF"),
                 "-DFOUNDATION_SANITIZERS=" + ("ON" if preset == "asan" else "OFF")]
    identity = {"preset": preset, "sdk": None, "gui": None,
                "environment": {key: os.environ.get(key) for key in
                 ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "CMAKE_GENERATOR")}}
    if args.sdk:
        sdk = args.sdk.resolve(strict=True)
        for key in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "PKG_CONFIG_PATH"):
            if os.environ.get(key):
                parser.error("unset host search override for SDK builds: " + key)
        identity["sdk"] = {"root": str(sdk), "sha256": sdk_identity(sdk)}
        configure += ["-DCMAKE_TOOLCHAIN_FILE=" + str(ROOT / "cmake/toolchains/sdk.cmake"),
                      "-DFOUNDATION_SDK_ROOT=" + str(sdk)]
    if args.gui_source:
        gui = args.gui_source.resolve(strict=True)
        identity["gui"] = str(gui)
        configure += ["-DFOUNDATION_BUILD_GUI=ON", "-DFOUNDATION_GUI_SOURCE=" + str(gui)]
    build.mkdir(parents=True, exist_ok=True)
    stamp = build / "wrapper-identity.json"
    if (build / "CMakeCache.txt").exists() and not stamp.exists():
        raise ValueError("refusing to adopt a populated unstamped build tree; move it aside or use CMake directly")
    if stamp.exists() and json.loads(stamp.read_text()) != identity:
        raise ValueError("toolchain/configuration changed; use a fresh build tree or move the old one aside")
    cache_stamp = build / "configured-identity.json"
    if cache_stamp.exists() and json.loads(cache_stamp.read_text()) != cache_identity(build):
        raise ValueError("configured compiler/options changed outside this wrapper; use a fresh tree or CMake directly")
    # Failed configuration must not leave a tree silently reusable with another SDK.
    stamp.write_text(json.dumps(identity, indent=2) + "\n")
    run(configure)
    cache_stamp.write_text(json.dumps(cache_identity(build), indent=2) + "\n")
    target = "all"
    if args.action == "test":
        target = "foundation-tests" + ("-" + args.label if args.label else "")
    run(["cmake", "--build", str(build), "--parallel", str(jobs), "--target", target])
    if args.action == "test":
        command = ["ctest", "--test-dir", str(build), "--output-on-failure",
                   "--no-tests=error", "--parallel", str(test_jobs)]
        if args.label:
            command += ["-L", "^" + args.label + "$"]
        run(command)
    elif args.action == "package":
        run(["cpack", "--config", str(build / "CPackConfig.cmake"), "-C", "Release"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("build: " + str(error), file=sys.stderr)
        sys.exit(1)
