import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("foundation_coverage", Path(__file__).resolve().parents[1] / "tools/coverage.py")
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


def plan(command=None):
    return coverage.freeze({"schema_version": 1, "mode": "release", "subject": {
        "source_sha256": "a" * 64, "inventory_sha256": "b" * 64,
        "configuration_sha256": "c" * 64}, "inputs": {}, "checks": [{
        "id": "contract", "scope": "source", "target": "linux-x86_64", "environment": "fixture",
        "backend": "core", "required": True, "argv": command or ["{python}", "-c", "print('checked')"],
        "timeout_seconds": 5, "warning_seconds": 4, "expected_tests": []}]})


class CoverageTests(unittest.TestCase):
    def test_real_success_retains_evidence_and_rejects_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = plan()
            result = coverage.run_case(frozen, "contract", root, root / "one", "local", 1)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(coverage.merge(frozen, [root / "one/result.json"])["status"], "passed")
            with self.assertRaises(FileExistsError):
                coverage.run_case(frozen, "contract", root, root / "one", "local", 2)
            (root / "one/console.log").write_text("replaced")
            with self.assertRaisesRegex(ValueError, "evidence changed"):
                coverage.merge(frozen, [root / "one/result.json"])

    def test_failure_never_becomes_pass_and_missing_duplicate_results_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = plan(["{python}", "-c", "raise SystemExit(7)"])
            coverage.run_case(frozen, "contract", root, root / "one", "run", 1)
            report = root / "one/result.json"
            self.assertEqual(coverage.merge(frozen, [report])["status"], "failed")
            for paths in ([], [report, report]):
                with self.assertRaises(ValueError):
                    coverage.merge(frozen, paths)

    def test_timeout_is_incomplete_and_retains_failed_attempt(self):
        frozen = plan(["{python}", "-c", "import time;time.sleep(60)"])
        del frozen["id"]
        frozen["checks"][0].update(timeout_seconds=0.15, warning_seconds=0.1)
        frozen = coverage.freeze(frozen)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = coverage.run_case(frozen, "contract", root, root / "timeout", "run", 1)
            self.assertEqual(result["status"], "incomplete")
            self.assertLess(result["seconds"], 5)

    def test_input_mutation_after_launch_invalidates_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "input.txt").write_text("before")
            frozen = plan(["{python}", "-c", "from pathlib import Path;Path('input.txt').write_text('after')"])
            del frozen["id"]
            frozen["inputs"] = {"input.txt": coverage.sha(root / "input.txt")}
            frozen = coverage.freeze(frozen)
            result = coverage.run_case(frozen, "contract", root, root / "one", "run", 1)
            self.assertEqual(result["status"], "failed")
            self.assertIn("input changed", result["error"])

    def test_junit_missing_skipped_duplicate_or_failed_is_not_success(self):
        fixtures = ['<testsuite/>', '<testsuite><testcase name="one"><skipped/></testcase></testsuite>',
                    '<testsuite><testcase name="one"/><testcase name="one"/></testsuite>',
                    '<testsuite><testcase name="one"><failure/></testcase></testsuite>']
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "junit.xml"
            for xml in fixtures:
                path.write_text(xml)
                with self.assertRaises(ValueError):
                    coverage.junit(path, ["one"])
            path.write_text('<testsuite><testcase name="one"/></testsuite>')
            coverage.junit(path, ["one"])

    def test_parent_success_with_inherited_log_child_is_rejected(self):
        import os
        if os.name != "posix":
            self.skipTest("POSIX fixture; Windows job-owner fixture is separate")
        command = ["{python}", "-c", "import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = coverage.run_case(plan(command), "contract", root, root / "orphan", "run", 1)
            self.assertEqual(result["status"], "failed")
            self.assertIn("descendants outlived", result["error"])

    def test_fast_exit_still_obeys_final_output_bound(self):
        from unittest.mock import patch
        frozen = plan(["{python}", "-c", "print('x'*1000)"])
        with tempfile.TemporaryDirectory() as temporary, patch.object(coverage, "MAX_LOG", 10):
            root = Path(temporary)
            result = coverage.run_case(frozen, "contract", root, root / "large", "run", 1)
            self.assertEqual(result["status"], "incomplete")
            self.assertIn("output limit", result["error"])

    def test_plan_is_strict_and_digest_bound(self):
        original = plan()
        for change in (lambda x: x.update(mode="other"),
                       lambda x: x["checks"].append(x["checks"][0]),
                       lambda x: x["checks"][0].update(timeout_seconds=float("inf")),
                       lambda x: x["checks"][0].update(required="yes"),
                       lambda x: x.update(inputs={"../outside": "a" * 64})):
            value = copy.deepcopy(original)
            change(value)
            with self.assertRaises(ValueError):
                coverage.validate(value)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError):
                coverage.load(path)


if __name__ == "__main__":
    unittest.main()
