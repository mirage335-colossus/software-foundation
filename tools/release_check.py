#!/usr/bin/env python3
"""Run source, archive or recovery qualification from an immutable candidate."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import shutil

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import artifact
import release
import sdk
from dependency_archive import digest, extract, write_json
from source_identity import source_tree, verify_source_archive
from verify_abi import audit
from build import host_programs

spec = importlib.util.spec_from_file_location("check_coverage", TOOLS / "coverage.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def select(manifest, target, backend):
    matches = [a for a in manifest["artifacts"] if a["target"] == target and backend in (a["backends"] or ["core"])]
    if len(matches) != 1:
        raise ValueError("one exact delivered target/backend is required")
    return matches[0]


def native_target(target):
    if target.startswith("browser-"):
        raise ValueError("browser qualification requires the real-browser adapter and its retained receipts")
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    if target != platform.system().lower() + "-" + machine:
        raise ValueError("execute the qualification inside the actual target environment")


def browser_check(source_root, server, evidence, options, executable=None, wasm=None):
    engine = options.get("browser") or "firefox"
    command = [sys.executable, str(source_root / "gui/tests/browser_test.py"), "--browser", engine,
               "--mode", "wasm" if wasm else "hosted", "--server", str(server),
               "--output", str(evidence / "browser")]
    if wasm:
        command += ["--wasm-dir", str(wasm)]
    else:
        command += ["--executable", str(executable)]
    if engine == "firefox":
        command += ["--firefox", options.get("firefox") or "firefox"]
    else:
        if not options.get("browser_executable"):
            raise ValueError("Chromium qualification needs its explicit executable and matching driver")
        command += ["--browser-executable", options["browser_executable"], "--driver", options.get("driver") or "chromedriver"]
    subprocess.run(command, check=True)
    receipt = c.load(evidence / "browser/qualification.json")
    required = {"editing", "accessible-names", "shared-geometry", "prompt-cancel", "capture", "cleanup"}
    if (receipt.get("schema_version") != 1 or receipt.get("status") != "passed" or receipt.get("engine") != engine or
            not receipt.get("browser_version") or not required <= set(receipt.get("checks", []))):
        raise ValueError("real browser did not complete the required interaction inventory")
    return receipt


def run_source(candidate, manifest, entry, work, evidence, jobs, recovery=False, browser_options=None):
    browser_target = entry["target"] == "browser-wasm32"
    if not browser_target:
        native_target(entry["target"])
    source = candidate / manifest["source"]["archive"]
    expected = verify_source_archive(source)
    extract(source, work / "source")
    if source_tree(work / "source") != expected:
        raise ValueError("extracted source differs from complete archived inventory")
    group = candidate / "dependencies" / entry["sdk_recipe"]
    command = [sys.executable, str(work / "source/tools/build.py"), "test", "release", "--full",
               "--portable", "--jobs", str(jobs), "--build-dir", str(work / "build"),
               "--junit", str(evidence / "source.junit.xml")]
    if entry["target"].startswith("linux-") or browser_target:
        sdk.install(group, entry["sdk_recipe"], work / "sdk", production=True)
        command += ["--sdk", str(work / "sdk")]
    else:
        import sdk_windows
        # Query the selected actual linker; environment setup must already have
        # used the repository's Windows selector. No compiler media is fetched.
        output = subprocess.check_output(["link.exe", "/?"], stderr=subprocess.STDOUT, text=True)
        import re
        version = re.search(r"Version\s+(\d+(?:\.\d+)+)", output)
        if not version:
            raise ValueError("cannot establish the actual consuming linker version")
        sdk_windows.install(group, entry["sdk_recipe"], work / "windows-dependencies", version[1])
        command += ["--dependency-group", str(group), "--windows-dependencies", str(work / "windows-dependencies")]
    for recipe in entry.get("dependency_recipes", [entry["sdk_recipe"]]):
        if recipe != entry["sdk_recipe"]:
            command += ["--dependency-group", str(candidate / "dependencies" / recipe)]
    if entry["backends"] and entry["backends"] != ["core"]:
        gui = work / "source/third_party/retained/gui"
        if not gui.is_dir():
            raise ValueError("GUI source absent from the retained application snapshot")
        command += ["--gui-source", str(gui), "--gui-backends", ",".join(entry["backends"])]
        if not browser_target:
            command += ["--host-tests"]
    # The wrapper checks source identity around compilation and test execution.
    # No base path or fetch fallback is supplied, including during recovery.
    subprocess.run(command, cwd=work, check=True)
    ctest = host_programs(work / "sdk" if (work / "sdk/sdk.json").is_file() else None)["ctest"]
    definitions = json.loads(subprocess.check_output([ctest, "--test-dir", str(work / "build"),
                                                     "--show-only=json-v1"], text=True))["tests"]
    names = sorted(x["name"] for x in definitions)
    if not names or len(names) != len(set(names)):
        raise ValueError("empty or duplicate source test inventory")
    junit = evidence / "source.junit.xml"
    c.junit(junit, names)
    consumer = [sys.executable, str(work / "source/tests/check_install.py"), "--build", str(work / "build"),
                "--source", str(work / "source"), "--config", "Release"]
    if (work / "sdk/sdk.json").is_file():
        consumer += ["--sdk", str(work / "sdk")]
    subprocess.run(consumer, cwd=work, check=True)
    if not recovery:
        # Source checks also consume the exact delivered library/export. A good
        # rebuilt library cannot mask a broken SDK inside the shipped archive.
        artifact.verify(candidate / entry["archive"], candidate / entry["manifest"],
                        sdk=work / "sdk" if (work / "sdk/sdk.json").is_file() else None,
                        abi=entry["target"].startswith("linux-"), processor=entry["target"].split("-", 1)[1])
    reports = []
    excluded = {}
    for name in names:
        if not name.startswith("tools."):
            continue
        suite = name.removeprefix("tools.")
        original = work / "build/test-reports" / (suite + ".json")
        value = c.tool_report(c.load(original))
        destination = evidence / "tool-reports" / original.name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(original, destination)
        reports.append(destination.relative_to(evidence).as_posix())
        excluded.update(value["excluded"])
    if source_tree(work / "source") != expected:
        raise ValueError("source changed during qualification")
    result = {"executed_tests": names, "junit_sha256": digest(junit), "retained_inputs_only": recovery,
              "tool_reports": reports, "platform_exclusions": excluded, "installed_consumer": "passed"}
    if not recovery:
        result["delivered_consumer"] = {"status": "passed", "archive_sha256": entry["sha256"]}
    if browser_target:
        result["browser"] = browser_check(work / "source", work / "build/gui/web/serve.py", evidence,
                                           browser_options or {}, wasm=work / "build/gui")
    return result


def check(candidate, target, backend, scope, evidence, jobs=2, browser_options=None):
    if scope not in ("source", "archive", "recovery", "abi") or jobs < 1:
        raise ValueError("unsupported qualification operation")
    candidate = candidate.resolve(strict=True)
    manifest = release.verify_release(candidate)
    before = digest(candidate / "release.json")
    entry = select(manifest, target, backend)
    if target != "browser-wasm32":
        native_target(target)
    elif backend != "wasm" or scope == "abi":
        raise ValueError("browser target requires its Wasm backend and supported scope")
    evidence.mkdir(parents=True, exist_ok=True)
    receipt = evidence / "qualification.json"
    if receipt.exists():
        raise ValueError("qualification receipt must be a new attempt")
    with tempfile.TemporaryDirectory(prefix="foundation exact release ") as temporary:
        work = Path(temporary)
        if scope in ("source", "recovery"):
            inputs = candidate
            if scope == "recovery":
                release.recover(candidate, work / "recovered")
                # Recovery outputs deliberately omit application binaries. Rebuild
                # from only the retained source and groups, not from the base.
                inputs = work / "recovered"
            details = run_source(inputs, manifest, entry, work / "qualification", evidence, jobs, scope == "recovery", browser_options)
        elif scope == "archive":
            if target != "browser-wasm32":
                artifact.verify(candidate / entry["archive"], candidate / entry["manifest"], runtime_only=True,
                                abi=target.startswith("linux-"), processor=target.split("-", 1)[1], backend=backend)
            details = {"archive_sha256": entry["sha256"], "relocation": "passed"}
            if backend in ("wasm", "hosted-web"):
                extract(candidate / manifest["source"]["archive"], work / "source")
                prefix = work / "relocated archive"
                prefix.mkdir()
                artifact.inspect_archive(candidate / entry["archive"], prefix)
                servers = list(prefix.rglob("share/software-foundation/web/serve.py"))
                if len(servers) != 1:
                    raise ValueError("packaged browser assets missing or ambiguous")
                server = servers[0]
                if backend == "wasm":
                    details["browser"] = browser_check(work / "source", server, evidence, browser_options or {}, wasm=server.parent)
                else:
                    suffix = ".exe" if os.name == "nt" else ""
                    binaries = list(prefix.rglob("bin/foundation-gui-web" + suffix))
                    if len(binaries) != 1:
                        raise ValueError("packaged hosted browser executable missing or ambiguous")
                    details["browser"] = browser_check(work / "source", server, evidence, browser_options or {}, executable=binaries[0])
        else:
            root = work / "archive"
            root.mkdir()
            artifact.inspect_archive(candidate / entry["archive"], root)
            if not target.startswith("linux-"):
                raise ValueError("ELF audit is a Linux qualification scope")
            details = audit(root, target.split("-", 1)[1])
    release.verify_release(candidate)
    if digest(candidate / "release.json") != before:
        raise ValueError("candidate changed during qualification")
    result = {"schema_version": 1, "source_sha256": manifest["source"]["sha256"],
              "inventory_sha256": before, "target": target, "backend": backend, "scope": scope,
              "host": c.host_identity(), "status": "passed", "details": details,
              "assertions": ["immutable-candidate", "exact-target-backend", scope + "-contract"],
              "evidence": {}}
    retained = (["source.junit.xml", *details.get("tool_reports", [])] if scope in ("source", "recovery") else [])
    if "browser" in details:
        retained += [p.relative_to(evidence).as_posix() for p in (evidence / "browser").rglob("*") if p.is_file()]
    result["evidence"] = {name: digest(evidence / name) for name in retained}
    c.write_new(receipt, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scope", choices=("source", "archive", "recovery", "abi"))
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--backend", required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--browser", choices=("firefox", "chromium"), default="firefox")
    p.add_argument("--firefox", default="firefox")
    p.add_argument("--browser-executable")
    p.add_argument("--driver", default="chromedriver")
    a = p.parse_args()
    check(a.release, a.target, a.backend, a.scope, a.evidence, a.jobs,
          {key: getattr(a, key) for key in ("browser", "firefox", "browser_executable", "driver")})


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("release check: " + str(error), file=sys.stderr)
        sys.exit(1)
