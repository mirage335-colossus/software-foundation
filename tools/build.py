#!/usr/bin/env python3
"""One incremental build entry point; never installs or downloads dependencies."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

import windows_compiler

ROOT = Path(__file__).resolve().parents[1]


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("jobs must be positive")
    return value


def default_jobs():
    from build_capacity import default_jobs as capacity
    return capacity()


def job_limits(args):
    build = args.build_jobs or args.jobs or positive(os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL") or str(default_jobs()))
    tests = args.test_jobs or args.jobs or positive(os.environ.get("CTEST_PARALLEL_LEVEL") or "2")
    return build, tests


def contained(root, relative):
    root = Path(root).resolve(strict=True)
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("SDK paths must be nonempty relative paths")
    resolved = (root / path).resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise ValueError("SDK path escapes its root")
    return resolved


def sdk_identity(root):
    # Share one SDK contract with direct CMake and release consumers.
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from sdk_manifest import verify_sdk
    return verify_sdk(root)


def host_programs(root=None):
    """Select retained build tools where the SDK declares them."""
    programs = {name: name for name in ("cmake", "ctest", "cpack", "ninja")}
    if root:
        metadata = json.loads((root / "sdk.json").read_text(encoding="utf-8"))
        for name, relative in metadata.get("host_tools", {}).items():
            if name in programs or name == "python":
                programs[name] = str(contained(root, relative))
    return programs


def verify_windows_linker(minimum):
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from sdk_windows import linker_version
    from windows_toolchain import inspect_selected_linker
    actual = inspect_selected_linker()['version']
    if linker_version(actual) < linker_version(minimum):
        raise ValueError("actual consuming linker is older than the dependency producer")


def cache_identity(build):
    selected = {}
    cache_version = {}
    for line in (build / "CMakeCache.txt").read_text(encoding="utf-8").splitlines():
        if "=" not in line or ":" not in line or line.startswith(("#", "//")):
            continue
        name_type, value = line.split("=", 1)
        name = name_type.split(":", 1)[0]
        if name in ("CMAKE_CACHE_MAJOR_VERSION", "CMAKE_CACHE_MINOR_VERSION", "CMAKE_CACHE_PATCH_VERSION"):
            cache_version[name] = value
        # Every cached input can affect generated rules, package discovery or
        # runtime behavior. A prefix allowlist misses linker/launcher/toolkit
        # overrides and lets an externally edited cache bypass the build stamp.
        selected[name] = value
    if "CMAKE_CXX_COMPILER" not in selected:
        version = ".".join(cache_version["CMAKE_CACHE_" + part + "_VERSION"] for part in ("MAJOR", "MINOR", "PATCH"))
        record = build / "CMakeFiles" / version / "CMakeCXXCompiler.cmake"
        match = re.search(r'^set\(CMAKE_CXX_COMPILER "([^"\n]+)"\)$', record.read_text(encoding="utf-8"), re.M)
        if not match:
            raise ValueError("configured compiler identity is absent")
        selected["CMAKE_CXX_COMPILER"] = match[1]
    compiler = Path(selected["CMAKE_CXX_COMPILER"]).resolve(strict=True)
    selected["compiler_file_sha256"] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    selected["compiler_resolved_path"] = str(compiler)
    return selected


def run(command, **kwargs):
    print("+ " + subprocess.list2cmdline([str(x) for x in command]), flush=True)
    windows_compiler.run(command, cwd=ROOT, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("build", "test", "package"), default="build")
    parser.add_argument("preset", nargs="?", choices=("dev", "release", "asan"), default=None)
    parser.add_argument("--jobs", type=positive)
    parser.add_argument("--build-jobs", type=positive, help="independent compilation concurrency")
    parser.add_argument("--test-jobs", type=positive, help="independent test concurrency")
    parser.add_argument("--dependency-prefix", type=Path, help="verified native development prefix")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--label", choices=("fast", "core", "tools", "integration", "gui"))
    selection.add_argument("--full", action="store_true", help="run all enabled tests (default)")
    parser.add_argument("--sdk", type=Path)
    parser.add_argument("--windows-dependencies", type=Path, help="verified restored Windows dependency export")
    parser.add_argument("--dependency-group", type=Path, action="append", default=[],
                        help="verified retained group; first group is primary for host-supplied toolchains")
    gui_input = parser.add_mutually_exclusive_group()
    gui_input.add_argument("--gui-source", type=Path)
    gui_input.add_argument("--gui-input-group", type=Path, help="verified offline GUI source group")
    parser.add_argument("--gui-backends", default="terminal,framebuffer,hosted-web",
                        help="comma-separated backends; requires a GUI source or input group")
    parser.add_argument("--host-tests", action="store_true")
    parser.add_argument("--portable", action="store_true", help="generic CPU and private static C++ runtime")
    parser.add_argument("--build-dir", type=Path, help="owned per-session output tree")
    parser.add_argument("--distribution-tests", action="store_true")
    parser.add_argument("--junit", type=Path, help="machine-readable outcomes for this test invocation")
    args = parser.parse_args(argv)
    preset = args.preset or ("release" if args.action == "package" else "dev")
    if (args.label or args.full or args.junit) and args.action != "test":
        parser.error("test selection applies only to test")
    if args.action == "package" and preset != "release":
        parser.error("package requires release configuration")
    backends = args.gui_backends.split(",")
    allowed = {"terminal", "framebuffer", "fltk", "rev", "sdl", "hosted-web", "wasm"}
    if len(set(backends)) != len(backends) or not set(backends) <= allowed:
        parser.error("unknown or duplicate GUI backend")
    has_gui = bool(args.gui_source or args.gui_input_group)
    if args.host_tests and not has_gui:
        parser.error("host checks require GUI inputs")
    if "wasm" in backends and (backends != ["wasm"] or not args.sdk or args.host_tests):
        parser.error("Wasm requires one backend and a prepared SDK; native host tests are separate")
    jobs, test_jobs = job_limits(args)
    suffix = ("-sdk" if args.sdk else "") + ("-gui" if has_gui else "")
    build = args.build_dir.resolve() if args.build_dir else ROOT / "build" / (preset + suffix + ("-portable" if args.portable else ""))
    gui_group_identity = None
    if args.gui_input_group:
        gui_group = args.gui_input_group.resolve(strict=True)
        helper = ROOT / "gui/source_group.py"
        restored = json.loads(subprocess.check_output(
            [sys.executable, "-B", str(helper), "restore", str(gui_group), "--output", str(build / "inputs/gui")],
            text=True, encoding="utf-8"))
        args.gui_source = Path(restored["source"]).resolve(strict=True)
        gui_group_identity = {"root": str(gui_group), "sha256": restored["group_sha256"]}
    configure = ["cmake", "--preset", preset, "-B", str(build),
                 "-DFOUNDATION_BUILD_GUI=" + ("ON" if args.gui_source else "OFF"),
                 "-DFOUNDATION_SANITIZERS=" + ("ON" if preset == "asan" else "OFF"),
                 "-DFOUNDATION_PORTABLE=" + ("ON" if args.portable else "OFF"),
                 "-DFOUNDATION_DISTRIBUTION_TESTS=" + ("ON" if args.distribution_tests else "OFF")]
    for name in ("fltk", "rev", "sdl"):
        configure.append("-DFOUNDATION_GUI_" + name.upper() + "=" + ("ON" if args.gui_source and name in backends else "OFF"))
    configure += ["-DFOUNDATION_GUI_WEB=" + ("ON" if "hosted-web" in backends else "OFF"),
                  "-DFOUNDATION_GUI_HOST_TESTS=" + ("ON" if args.host_tests else "OFF")]
    identity = {"preset": preset, "sdk": None, "gui": None,
                "backends": sorted(backends) if args.gui_source else [], "host_tests": args.host_tests,
                "portable": args.portable, "distribution_tests": args.distribution_tests, "dependencies": [],
                "windows_dependencies": None,
                "environment": {key: os.environ.get(key) for key in
                 ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "CMAKE_GENERATOR")}}
    if gui_group_identity:
        identity["gui_input_group"] = gui_group_identity
    if args.dependency_prefix:
        if args.sdk or args.windows_dependencies:
            parser.error("native development prefix cannot be combined with a prepared SDK")
        from prepare_dependencies import verify
        prefix_root = args.dependency_prefix.resolve(strict=True)
        identity["dependency_prefix"] = {"root": str(prefix_root), **verify(prefix_root)}
        configure += ["-DFOUNDATION_DEPENDENCY_PREFIX=" + str(prefix_root)]
    programs = host_programs()
    child_environment = os.environ.copy()
    if args.sdk:
        sdk = args.sdk.resolve(strict=True)
        for key in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "PKG_CONFIG_PATH"):
            if os.environ.get(key):
                parser.error("unset host search override for SDK builds: " + key)
        identity["sdk"] = {"root": str(sdk), "sha256": sdk_identity(sdk)}
        is_browser = json.loads((sdk / "sdk.json").read_text(encoding="utf-8"))["target"]["system"] == "Emscripten"
        if is_browser != (backends == ["wasm"]):
            raise ValueError("prepared SDK target and selected GUI backend disagree")
        if is_browser:
            from sdk_wasm import environment
            child_environment = environment(sdk)
            configure += ["-DFOUNDATION_NODE_EXECUTABLE=" + str(contained(sdk, "node/bin/node"))]
        programs = host_programs(sdk)
        configure[0] = programs["cmake"]
        child_environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if programs["ninja"] != "ninja":
            configure += ["-DCMAKE_MAKE_PROGRAM=" + programs["ninja"]]
        if "python" in programs:
            configure += ["-DPython3_EXECUTABLE=" + programs["python"]]
        if args.action == "package":
            from sdk_manifest import verify_sdk
            verify_sdk(sdk, release=True)
        configure += ["-DCMAKE_TOOLCHAIN_FILE=" + str(ROOT / "cmake/toolchains/sdk.cmake"),
                      "-DFOUNDATION_SDK_ROOT=" + str(sdk)]
    dependency_ids = []
    if args.sdk:
        dependency_ids.append(json.loads((args.sdk.resolve() / "sdk.json").read_text(encoding="utf-8"))["recipe_id"])
    if args.dependency_group:
        tools = str(Path(__file__).resolve().parent)
        if tools not in sys.path:
            sys.path.insert(0, tools)
        from dependency_store import verify_group
        for group_arg in args.dependency_group:
            group = group_arg.resolve(strict=True)
            checksums = list(group.glob("sdk-*-SHA256SUMS"))
            if len(checksums) != 1:
                raise ValueError("retained group needs exactly one recipe checksum inventory")
            match = re.fullmatch(r"sdk-([0-9a-f]{64})-SHA256SUMS", checksums[0].name)
            if not match:
                raise ValueError("invalid retained group identity")
            recipe = match[1]
            hashes = verify_group(group, recipe)
            if recipe in dependency_ids:
                raise ValueError("duplicate prepared group")
            dependency_ids.append(recipe)
            identity["dependencies"].append({"root": str(group), "recipe": recipe, "files": hashes})
    if args.windows_dependencies:
        if os.name != "nt" or args.sdk or not args.portable:
            raise ValueError("Windows dependency exports require a native portable Windows build")
        from dependency_archive import read_json, verify_inventory, inspect_manifest_archive
        from dependency_store import names
        from sdk_manifest import verify_sdk
        dependencies = args.windows_dependencies.resolve(strict=True)
        metadata = read_json(dependencies / "sdk.json")
        if metadata.get("kind") != "windows-dependencies" or metadata.get("recipe_id") not in dependency_ids:
            raise ValueError("Windows dependency export needs its complete matching retained group")
        verify_sdk(dependencies, release=True)
        retained = next(item for item in identity["dependencies"] if item["recipe"] == metadata["recipe_id"])
        archived, _ = inspect_manifest_archive(Path(retained["root"]) / names(metadata["recipe_id"])[0], "sdk.json")
        if archived != metadata:
            raise ValueError("restored Windows metadata differs from retained producer metadata")
        provenance = metadata.get("provenance", {})
        if (metadata["target"]["system"] != "Windows" or metadata["target"]["processor"] != "x86_64" or
                provenance.get("toolset") != "v143" or provenance.get("crt_linkage") != "static" or
                provenance.get("library_linkage") != "static" or provenance.get("lto") is not False):
            raise ValueError("incompatible Windows dependency ABI contract")
        verify_windows_linker(metadata["external_toolchain"]["minimum_linker"])
        verify_inventory(dependencies, metadata["files"], exclude=("sdk.json",))
        identity["windows_dependencies"] = {"root": str(dependencies), "sha256": hashlib.sha256((dependencies / "sdk.json").read_bytes()).hexdigest()}
        installed = dependencies / "prefix/installed/x64-windows-static"
        prefix = installed if installed.is_dir() else dependencies / "prefix"
        configure += ["-DCMAKE_PREFIX_PATH=" + str(prefix), "-DFOUNDATION_WINDOWS_DEPENDENCIES=" + str(dependencies)]
        vcpkg = dependencies / "prefix/scripts/buildsystems/vcpkg.cmake"
        if vcpkg.is_file():
            configure += ["-DCMAKE_TOOLCHAIN_FILE=" + str(vcpkg), "-DVCPKG_TARGET_TRIPLET=x64-windows-static",
                          "-DVCPKG_MANIFEST_MODE=OFF", "-DVCPKG_FEATURE_FLAGS=-manifests"]
    configure += ["-DFOUNDATION_DEPENDENCY_RECIPE=" + (dependency_ids[0] if dependency_ids else "native-unprepared"),
                  "-DFOUNDATION_DEPENDENCY_RECIPES=" + ";".join(sorted(dependency_ids))]
    if args.gui_source:
        gui = args.gui_source.resolve(strict=True)
        identity["gui"] = str(gui)
        configure += ["-DFOUNDATION_BUILD_GUI=ON", "-DFOUNDATION_GUI_SOURCE=" + str(gui)]
    build.mkdir(parents=True, exist_ok=True)
    stamp = build / "wrapper-identity.json"
    if (build / "CMakeCache.txt").exists() and not stamp.exists():
        raise ValueError("refusing to adopt a populated unstamped build tree; move it aside or use CMake directly")
    if stamp.exists() and json.loads(stamp.read_text(encoding="utf-8")) != identity:
        raise ValueError("toolchain/configuration changed; use a fresh build tree or move the old one aside")
    cache_stamp = build / "configured-identity.json"
    if cache_stamp.exists() and json.loads(cache_stamp.read_text(encoding="utf-8")) != cache_identity(build):
        raise ValueError("configured compiler/options changed outside this wrapper; use a fresh tree or CMake directly")
    # Failed configuration must not leave a tree silently reusable with another SDK.
    stamp.write_text(json.dumps(identity, indent=2) + "\n")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from source_identity import source_tree
    source_before = source_tree(ROOT, args.gui_source)
    run(configure, env=child_environment)
    cache_stamp.write_text(json.dumps(cache_identity(build), indent=2) + "\n")
    target = "all"
    if args.action == "test":
        target = "foundation-tests" + ("-" + args.label if args.label else "")
    run([programs["cmake"], "--build", str(build), "--parallel", str(jobs), "--target", target], env=child_environment)
    if source_tree(ROOT, args.gui_source) != source_before:
        raise ValueError("source changed during compilation; rebuild a stable candidate")
    if args.action == "test":
        command = [programs["ctest"], "--test-dir", str(build), "--output-on-failure",
                   "--no-tests=error", "--parallel", str(test_jobs)]
        if args.junit:
            junit = args.junit.resolve()
            junit.parent.mkdir(parents=True, exist_ok=True)
            junit.unlink(missing_ok=True)
            command += ["--output-junit", str(junit)]
        if args.label:
            command += ["-L", "^" + args.label + "$"]
        run(command, env=child_environment)
        if source_tree(ROOT, args.gui_source) != source_before:
            raise ValueError("source changed during validation; results are not qualification")
    elif args.action == "package":
        run([programs["cpack"], "--config", str(build / "CPackConfig.cmake"), "-C", "Release"], env=child_environment)
    if source_tree(ROOT, args.gui_source) != source_before:
        raise ValueError("source changed during the operation; outputs are not qualification")
    if gui_group_identity:
        verified = json.loads(subprocess.check_output(
            [sys.executable, "-B", str(helper), "verify", str(gui_group)], text=True, encoding="utf-8"))
        if verified["group_sha256"] != gui_group_identity["sha256"]:
            raise ValueError("GUI input group changed during execution; evidence is invalid")
    if args.sdk and sdk_identity(args.sdk.resolve()) != identity["sdk"]["sha256"]:
        raise ValueError("prepared SDK changed during execution; evidence is invalid")
    if args.windows_dependencies:
        verify_inventory(dependencies, metadata["files"], exclude=("sdk.json",))
        if hashlib.sha256((dependencies / "sdk.json").read_bytes()).hexdigest() != identity["windows_dependencies"]["sha256"]:
            raise ValueError("Windows dependency identity changed during execution")
    if args.dependency_prefix and verify(prefix_root) != {key: value for key, value in identity["dependency_prefix"].items() if key != "root"}:
        raise ValueError("native development prefix changed during execution")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("build: " + str(error), file=sys.stderr)
        sys.exit(1)
