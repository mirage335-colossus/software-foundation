#!/usr/bin/env python3
"""Freeze test coverage, run disjoint shards, reject incomplete aggregation."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as builder
from dependency_archive import read_json
from dependency_store import verify_group
from source_identity import source_tree


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def gui_source(cache):
    enabled = cache.get("FOUNDATION_BUILD_GUI", "OFF").upper() not in ("OFF", "NO", "FALSE", "0", "")
    value = cache.get("FOUNDATION_GUI_SOURCE")
    if enabled and not value:
        raise ValueError("enabled GUI has no configured source input")
    return Path(value).resolve(strict=True) if enabled else None


def source_id(build=None):
    supplement = gui_source(builder.cache_identity(build)) if build is not None else None
    return source_tree(ROOT, supplement)["tree_sha256"]


def execution_context(build):
    cache = builder.cache_identity(build)
    sdk = Path(cache["FOUNDATION_SDK_ROOT"]).resolve(strict=True) if cache.get("FOUNDATION_SDK_ROOT") else None
    programs = builder.host_programs(sdk)
    if not sdk:
        programs["cmake"] = cache.get("CMAKE_COMMAND", programs["cmake"])
        programs["ctest"] = cache.get("CMAKE_CTEST_COMMAND", programs["ctest"])
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if sdk and read_json(sdk / "sdk.json")["target"]["system"] == "Emscripten":
        from sdk_wasm import environment as sdk_environment
        environment = sdk_environment(sdk)
    return programs, environment


def verify_gui_group(root):
    value = subprocess.check_output([sys.executable, "-B", str(ROOT / "gui/source_group.py"),
                                     "verify", str(root)], text=True, encoding="utf-8")
    return json.loads(value)["group_sha256"]


def build_inputs(build):
    """Recompute bytes, never trust a saved wrapper receipt as verification."""
    cache = builder.cache_identity(build)
    stamp = build / "wrapper-identity.json"
    configured = build / "configured-identity.json"
    wrapper = read_json(stamp) if stamp.exists() else None
    if wrapper is not None:
        if not configured.is_file() or read_json(configured) != cache:
            raise ValueError("configured compiler/options changed outside the build wrapper")
    elif configured.exists():
        raise ValueError("configured build receipt is missing its wrapper identity")
    result = {"cache": cache, "wrapper": wrapper, "sdk": None, "dependencies": [], "windows_dependencies": None,
              "environment": {key: os.environ.get(key) for key in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS",
                  "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "PKG_CONFIG_PATH", "CMAKE_GENERATOR")}}
    sdk_root = cache.get("FOUNDATION_SDK_ROOT")
    recipe_ids = []
    if sdk_root:
        sdk = Path(sdk_root).resolve(strict=True)
        if any(os.environ.get(key) for key in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "CPATH",
                                               "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "PKG_CONFIG_PATH")):
            raise ValueError("unset host search overrides for prepared SDK validation")
        result["sdk"] = {"root": str(sdk), "sha256": builder.sdk_identity(sdk)}
        recipe_ids.append(read_json(sdk / "sdk.json")["recipe_id"])
    if wrapper is not None:
        if wrapper.get("sdk") != result["sdk"]:
            raise ValueError("prepared SDK differs from configured wrapper identity")
        if any(os.environ.get(key) != value for key, value in wrapper.get("environment", {}).items()):
            raise ValueError("build environment differs from configured wrapper identity")
        expected_gui = str(gui_source(cache)) if gui_source(cache) else None
        if wrapper.get("gui") != expected_gui:
            raise ValueError("GUI source differs from configured wrapper identity")
        for item in wrapper.get("dependencies", []):
            actual = {"root": str(Path(item["root"]).resolve(strict=True)), "recipe": item["recipe"],
                      "files": verify_group(item["root"], item["recipe"])}
            if actual != item or item["recipe"] in recipe_ids:
                raise ValueError("retained dependency group changed or is duplicated")
            recipe_ids.append(item["recipe"])
            result["dependencies"].append(actual)
        windows = wrapper.get("windows_dependencies")
        if windows:
            from sdk_manifest import verify_sdk
            path = Path(windows["root"]).resolve(strict=True)
            actual = {"root": str(path), "sha256": verify_sdk(path, release=True)}
            if actual != windows or read_json(path / "sdk.json")["recipe_id"] not in recipe_ids:
                raise ValueError("Windows dependency export differs from its retained identity")
            result["windows_dependencies"] = actual
        group = wrapper.get("gui_input_group")
        if group:
            actual = {"root": str(Path(group["root"]).resolve(strict=True)),
                      "sha256": verify_gui_group(group["root"])}
            if actual != group:
                raise ValueError("GUI input group differs from its retained identity")
            result["gui_input_group"] = actual
    declared = set(filter(None, cache.get("FOUNDATION_DEPENDENCY_RECIPES", "").split(";")))
    if sdk_root:
        declared.add(read_json(Path(sdk_root) / "sdk.json")["recipe_id"])
    primary = cache.get("FOUNDATION_DEPENDENCY_RECIPE", "native-unprepared")
    if (sorted(declared) != sorted(recipe_ids)
            or (primary != "native-unprepared" and primary not in recipe_ids)):
        raise ValueError("configured dependencies need complete verified retained input identities")
    return result


def test_definitions(build):
    programs, environment = execution_context(build)
    raw = subprocess.check_output([programs["ctest"], "--test-dir", str(build), "--show-only=json-v1"],
                                  text=True, env=environment)
    tests = json.loads(raw)["tests"]
    encoded = json.dumps(tests, sort_keys=True).replace(str(build.resolve()), "<BUILD>").replace(str(ROOT), "<SOURCE>")
    return json.loads(encoded)


def inventory(build):
    tests = sorted(item["name"] for item in test_definitions(build))
    if not tests or len(set(tests)) != len(tests):
        raise ValueError("test inventory is empty or duplicated")
    return tests


def configuration_id(build):
    build = build.resolve()
    inputs = build_inputs(build)
    # Normalize checkout/build locations while preserving actual compiler and
    # retained-input digests, complete cache values and external locations.
    normalized = json.dumps(inputs, sort_keys=True).replace(str(build), "<BUILD>").replace(str(ROOT), "<SOURCE>")
    info = (build / "build-info.txt").read_text()
    return digest({"inputs": json.loads(normalized), "build_info": info, "tests": test_definitions(build)})


def require_current(build, plan):
    if (configuration_id(build) != plan["configuration"] or source_id(build) != plan["source"]
            or inventory(build) != plan["tests"]):
        raise ValueError("source, compiler, prepared inputs or test configuration changed since planning")


def make_plan(tests, shards, identity, configuration="unit-fixture"):
    if shards < 1 or shards > len(tests):
        raise ValueError("shards must be between 1 and the test count")
    plan = {"schema_version": 1, "source": identity, "configuration": configuration, "tests": sorted(tests),
            "shards": [sorted(tests)[index::shards] for index in range(shards)]}
    plan["id"] = digest(plan)
    return plan


def validate_plan(plan):
    body = {key: value for key, value in plan.items() if key != "id"}
    if plan.get("schema_version") != 1 or digest(body) != plan.get("id"):
        raise ValueError("plan identity mismatch")
    flat = [name for shard in plan["shards"] for name in shard]
    if not flat or any(not shard for shard in plan["shards"]) or sorted(flat) != plan["tests"] or len(set(flat)) != len(flat):
        raise ValueError("invalid shard inventory")


def junit_results(path, expected):
    cases = list(ET.parse(path).getroot().iter("testcase"))
    names = [case.attrib.get("name") for case in cases]
    if sorted(names) != sorted(expected) or len(set(names)) != len(names):
        raise ValueError("missing, unexpected or duplicate test results")
    statuses = {}
    for case in cases:
        passed = case.attrib.get("status", "run") in ("run", "passed")
        passed = passed and all(case.find(tag) is None for tag in ("failure", "error", "skipped"))
        statuses[case.attrib["name"]] = "passed" if passed else "failed_or_incomplete"
    return statuses


def merge(plan, reports):
    validate_plan(plan)
    seen = set()
    results = {}
    for report in reports:
        index = report["shard"]
        if report["plan"] != plan["id"] or index in seen or type(index) is not int or not 0 <= index < len(plan["shards"]):
            raise ValueError("duplicate, stale or invalid shard")
        if set(report["results"]) != set(plan["shards"][index]):
            raise ValueError("incomplete shard results")
        if report["exit_code"] != 0 or any(value != "passed" for value in report["results"].values()):
            raise ValueError("failed or incomplete coverage")
        seen.add(index)
        results.update(report["results"])
    if seen != set(range(len(plan["shards"]))) or set(results) != set(plan["tests"]):
        raise ValueError("missing shard coverage")
    return {"schema_version": 1, "plan": plan["id"], "source": plan["source"], "status": "passed", "tests": len(results)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", delete=False) as output:
        staging = Path(output.name)
        output.write(json.dumps(value, indent=2) + "\n")
        output.flush()
        os.fsync(output.fileno())
    try:
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    plan_cmd = sub.add_parser("plan")
    plan_cmd.add_argument("--build", type=Path, required=True)
    plan_cmd.add_argument("--shards", type=int, default=2)
    plan_cmd.add_argument("--jobs", type=int, default=2)
    plan_cmd.add_argument("--output", type=Path, required=True)
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--build", type=Path, required=True)
    run_cmd.add_argument("--plan", type=Path, required=True)
    run_cmd.add_argument("--shard", type=int, required=True)
    run_cmd.add_argument("--jobs", type=int, default=2)
    run_cmd.add_argument("--output", type=Path, required=True)
    merge_cmd = sub.add_parser("merge")
    merge_cmd.add_argument("--plan", type=Path, required=True)
    merge_cmd.add_argument("--output", type=Path, required=True)
    merge_cmd.add_argument("reports", type=Path, nargs="+")
    args = parser.parse_args()
    inputs = ([args.plan] if args.action != "plan" else []) + (args.reports if args.action == "merge" else [])
    if args.output.resolve() in [path.resolve() for path in inputs]:
        raise ValueError("output must not replace an input")
    # A failed attempt must never leave a previous successful receipt behind.
    args.output.unlink(missing_ok=True)
    if args.action in ("plan", "run"):
        if args.jobs < 1:
            raise ValueError("concurrency must be positive")
        cache = (args.build / "CMakeCache.txt").read_text()
        if re.search(r"^CMAKE_CONFIGURATION_TYPES:.*=.+", cache, flags=re.M):
            raise ValueError("test-plan example requires a single-configuration build tree")
        before, inputs_before = source_id(args.build), build_inputs(args.build)
        if args.action == "run":
            planned = json.loads(args.plan.read_text())
            validate_plan(planned)
            require_current(args.build, planned)
        programs, environment = execution_context(args.build)
        subprocess.run([programs["cmake"], "--build", str(args.build), "--target", "foundation-tests",
                        "--parallel", str(args.jobs)], check=True, env=environment)
        if before != source_id(args.build) or inputs_before != build_inputs(args.build):
            raise ValueError("source, compiler or prepared inputs changed while compiling test prerequisites")
    if args.action == "plan":
        save(args.output, make_plan(inventory(args.build), args.shards, source_id(args.build), configuration_id(args.build)))
    else:
        plan = json.loads(args.plan.read_text())
        validate_plan(plan)
        if args.action == "merge":
            save(args.output, merge(plan, [json.loads(path.read_text()) for path in args.reports]))
        else:
            if args.jobs < 1 or not 0 <= args.shard < len(plan["shards"]):
                raise ValueError("invalid shard or concurrency")
            require_current(args.build, plan)
            expected = plan["shards"][args.shard]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            junit = args.output.with_name(args.output.name + ".junit.xml").resolve()
            # Prevent stale JUnit data from surviving a failed test launch.
            junit.unlink(missing_ok=True)
            result = subprocess.run([programs["ctest"], "--test-dir", str(args.build), "--no-tests=error", "--output-on-failure",
                                     "--parallel", str(args.jobs), "-R", "^(" + "|".join(re.escape(x) for x in expected) + ")$",
                                     "--output-junit", str(junit)], env=environment)
            results = junit_results(junit, expected)
            require_current(args.build, plan)
            save(args.output, {"schema_version": 1, "plan": plan["id"], "shard": args.shard,
                               "exit_code": result.returncode, "results": results})
            if result.returncode or any(value != "passed" for value in results.values()):
                return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.CalledProcessError) as error:
        print("test plan: " + str(error), file=sys.stderr)
        sys.exit(1)
