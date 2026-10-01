#!/usr/bin/env python3
"""Qualify immutable local release bytes against a complete explicit policy."""
import argparse
import importlib.util
from pathlib import Path
import sys


def sibling(name):
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    spec = importlib.util.spec_from_file_location("foundation_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coverage = sibling("coverage")


def requirements(policy, profile):
    coverage.fields(policy, {"schema_version", "profiles"})
    if policy["schema_version"] != 1 or profile not in policy["profiles"]:
        raise ValueError("unknown release qualification profile")
    selected = policy["profiles"][profile]
    coverage.fields(selected, {"description", "targets", "checks"})
    if not selected["targets"] or not selected["checks"]:
        raise ValueError("empty release support contract")
    expected = set()
    for target, backends in selected["targets"].items():
        if not coverage.NAME.fullmatch(target) or not backends or len(backends) != len(set(backends)):
            raise ValueError("invalid target/backend contract")
        if any(not coverage.NAME.fullmatch(backend) for backend in backends):
            raise ValueError("invalid backend")
    for row in selected["checks"]:
        coverage.fields(row, {"target", "backend", "environment", "scope"})
        key = tuple(row[k] for k in ("target", "backend", "environment", "scope"))
        if (key in expected or row["target"] not in selected["targets"] or
                row["backend"] not in selected["targets"][row["target"]] or
                any(not isinstance(v, str) or not coverage.NAME.fullmatch(v) for v in row.values())):
            raise ValueError("duplicate or invalid required coverage")
        expected.add(key)
    for target, backends in selected["targets"].items():
        for backend in backends:
            kinds = {r[3] for r in expected if r[:2] == (target, backend)}
            if not {"source", "archive", "recovery"} <= kinds:
                raise ValueError("each delivered backend needs source, archive and recovery coverage")
    return selected, expected


def certify(directory, manifest, plan, reports, policy, profile, experiment=False):
    """verify_release must have verified manifest and file bytes before this call."""
    selected, expected = requirements(policy, profile)
    coverage.validate(plan)
    subject = {"source_sha256": manifest["source"]["sha256"],
               "inventory_sha256": coverage.sha(directory / "release.json"),
               "configuration_sha256": coverage.digest({"policy": policy, "profile": profile})}
    if plan["mode"] != "release" or plan["subject"] != subject:
        raise ValueError("diagnostic, different source, inventory or policy cannot certify these bytes")
    actual_targets = {}
    for artifact in manifest["artifacts"]:
        target = artifact["target"]
        actual_targets.setdefault(target, set())
        for backend in artifact["backends"] or ["core"]:
            if backend in actual_targets[target]:
                raise ValueError("duplicate delivered backend")
            actual_targets[target].add(backend)
    if actual_targets != {t: set(b) for t, b in selected["targets"].items()}:
        raise ValueError("delivered target/backend inventory differs from support contract")
    declared = set()
    for check in plan["checks"]:
        key = tuple(check[k] for k in ("target", "backend", "environment", "scope"))
        if key in declared:
            raise ValueError("duplicate qualification scope")
        declared.add(key)
        if key in expected and not check["required"]:
            raise ValueError("mandatory qualification scope marked optional")
        if key in expected and "qualification" not in check:
            raise ValueError("mandatory scope needs a bound qualification receipt")
    if not expected <= declared:
        raise ValueError("required qualification scope missing from plan")
    if not set(manifest["required_scopes"]) <= {r[3] for r in expected}:
        raise ValueError("release requirements absent from qualification policy")
    result = coverage.merge(plan, reports)
    report_paths = {coverage.load(path)["check"]: path for path in reports}
    for check in plan["checks"]:
        observed = result["checks"][check["id"]]["host"]
        if check["target"].startswith(("linux-", "windows-")):
            system, architecture = check["target"].split("-", 1)
            machine = observed["machine"].lower()
            machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
            if observed["system"].lower() != system or machine != architecture:
                raise ValueError("actual execution host differs from declared target")
            if check["environment"].startswith(("debian-", "ubuntu-")):
                if observed.get("distribution") != check["environment"]:
                    raise ValueError("actual user-space environment differs from required baseline")
            if check["environment"] == "windows-2022" and observed.get("runner_image") != "win22":
                raise ValueError("Windows runner image evidence missing or mismatched")
        if check["environment"] in ("firefox", "chromium") and result["checks"][check["id"]]["status"] == "passed":
            receipt = coverage.load(coverage.local(report_paths[check["id"]].parent, check["qualification"]))
            browser = receipt["details"].get("browser", {})
            if (browser.get("engine") != check["environment"] or not browser.get("browser_version") or
                    browser.get("status") != "passed"):
                raise ValueError("actual browser evidence missing or differs from required engine")
    passed = result["status"] == "passed"
    # Neither an enclosing green workflow nor an advisory warning waives a check.
    warnings = {n: r["warnings"] for n, r in result["checks"].items() if r["warnings"]}
    return {"schema_version": 1, "subject": subject, "profile": profile, "plan": plan["id"],
            "status": ("passed_with_warnings" if warnings else "passed") if passed else "failed",
            "eligible_for_promotion": passed and not experiment, "experiment": experiment,
            "run_id": result["run_id"], "description": selected["description"],
            "warnings": warnings, "omitted": result["omitted"], "coverage": result["checks"],
            "reports": [{"name": str(p.name), "sha256": coverage.sha(p)} for p in reports],
            "limits": ["Evidence applies only to the named environments and exact bytes.",
                       "Containers do not qualify another kernel, physical device or desktop session.",
                       "This helper neither publishes a release nor changes a remote Latest pointer."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experiment", action="store_true")
    parser.add_argument("reports", type=Path, nargs="+")
    args = parser.parse_args()
    directory = args.release.resolve(strict=True)
    if directory == args.output.resolve() or directory in args.output.resolve().parents:
        raise ValueError("certification evidence must not mutate the immutable release directory")
    release = sibling("release")
    manifest = release.verify_release(directory)
    initial = coverage.sha(directory / "release.json")
    result = certify(directory, manifest, coverage.load(args.plan), args.reports,
                     coverage.load(args.policy), args.profile, args.experiment)
    release.verify_release(directory)
    if initial != coverage.sha(directory / "release.json"):
        raise ValueError("release changed during certification")
    coverage.write_new(args.output, result)
    return 0 if result["status"] in ("passed", "passed_with_warnings") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("certification: " + str(error), file=sys.stderr)
        sys.exit(1)
