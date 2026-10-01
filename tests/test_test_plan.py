import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("test_plan", Path(__file__).resolve().parents[1] / "tools/test_plan.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


class CoverageTests(unittest.TestCase):
    def test_partition_and_complete_merge(self):
        recipe = plan.make_plan(["c", "a", "b"], 2, "source")
        reports = [{"plan": recipe["id"], "shard": index, "exit_code": 0,
                    "results": {name: "passed" for name in shard}}
                   for index, shard in enumerate(recipe["shards"])]
        self.assertEqual(plan.merge(recipe, reports)["tests"], 3)
        for broken in (reports[:1], reports + reports[:1]):
            with self.assertRaises(ValueError):
                plan.merge(recipe, broken)
        reports[0]["results"]["a"] = "skipped"
        with self.assertRaises(ValueError):
            plan.merge(recipe, reports)

    def test_junit_requires_every_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.xml"
            path.write_text('<testsuite><testcase name="a" status="run"/><testcase name="b"><skipped/></testcase></testsuite>')
            self.assertEqual(plan.junit_results(path, ["a", "b"])["b"], "failed_or_incomplete")
            with self.assertRaises(ValueError):
                plan.junit_results(path, ["a", "b", "c"])

    def test_tampered_and_empty_inventory_rejected(self):
        with self.assertRaises(ValueError):
            plan.make_plan([], 1, "source")
        recipe = plan.make_plan(["a", "b"], 2, "source")
        recipe["tests"].append("c")
        with self.assertRaises(ValueError):
            plan.validate_plan(recipe)

class ReceiptTests(unittest.TestCase):
    def test_failed_attempt_removes_stale_receipt(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "plan.json"
            invalid.write_text(json.dumps({"schema_version": 0}))
            for operation in ("run", "merge"):
                output = root / "previous.json"
                output.write_text('{"status":"passed"}')
                command = [sys.executable, str(Path(plan.__file__)), operation,
                           "--plan", str(invalid), "--output", str(output)]
                if operation == "run":
                    command += ["--build", str(root / "missing-build"), "--shard", "0"]
                else:
                    command += [str(root / "missing-report")]
                result = subprocess.run(command, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
