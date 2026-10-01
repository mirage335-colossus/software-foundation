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


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_id():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    files = {}
    for name in sorted(set(names.decode().split("\0")) - {""}):
        path = ROOT / name
        if path.is_file():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest(files)


def test_definitions(build):
    raw = subprocess.check_output(["ctest", "--test-dir", str(build), "--show-only=json-v1"], text=True)
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
    cache = (build / "CMakeCache.txt").read_text()
    # Retain toolchain/options while normalizing only this checkout's paths.
    lines = [line.replace(str(build), "<BUILD>").replace(str(ROOT), "<SOURCE>")
             for line in cache.splitlines() if line and not line.startswith(("#", "//"))]
    info = (build / "build-info.txt").read_text()
    return digest({"cache": sorted(lines), "build_info": info, "tests": test_definitions(build)})


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
        before = source_id()
        subprocess.run(["cmake", "--build", str(args.build), "--target", "foundation-tests",
                        "--parallel", str(args.jobs)], check=True)
        if before != source_id():
            raise ValueError("source changed while compiling test prerequisites")
    if args.action == "plan":
        save(args.output, make_plan(inventory(args.build), args.shards, source_id(), configuration_id(args.build)))
    else:
        plan = json.loads(args.plan.read_text())
        validate_plan(plan)
        if args.action == "merge":
            save(args.output, merge(plan, [json.loads(path.read_text()) for path in args.reports]))
        else:
            if args.jobs < 1 or not 0 <= args.shard < len(plan["shards"]):
                raise ValueError("invalid shard or concurrency")
            if (inventory(args.build) != plan["tests"] or source_id() != plan["source"]
                    or configuration_id(args.build) != plan["configuration"]):
                raise ValueError("source or test inventory changed since planning")
            expected = plan["shards"][args.shard]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            junit = args.output.with_name(args.output.name + ".junit.xml").resolve()
            # Prevent stale JUnit data from surviving a failed test launch.
            junit.unlink(missing_ok=True)
            result = subprocess.run(["ctest", "--test-dir", str(args.build), "--no-tests=error", "--output-on-failure",
                                     "--parallel", str(args.jobs), "-R", "^(" + "|".join(re.escape(x) for x in expected) + ")$",
                                     "--output-junit", str(junit)])
            results = junit_results(junit, expected)
            if source_id() != plan["source"] or configuration_id(args.build) != plan["configuration"]:
                raise ValueError("source changed during test execution")
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
