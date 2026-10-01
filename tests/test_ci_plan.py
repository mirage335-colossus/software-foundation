import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ci_plan", Path(__file__).resolve().parents[1] / "tools/ci_plan.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class CiPlanTests(unittest.TestCase):
    def test_default_disjoint_source_scopes_and_independent_producers(self):
        plan = ci.plan()
        checks = plan["checks"]["include"]
        self.assertEqual(len(checks), 9)
        self.assertEqual(len({(x["target"], x["scope"]) for x in checks}), 9)
        self.assertEqual(len(plan["packages"]["include"]), 3)

    def test_focused_selection_does_not_masquerade_as_full(self):
        checks = ci.plan(True, False)["checks"]["include"]
        self.assertEqual({x["scope"] for x in checks}, {"core"})
        self.assertEqual(len(checks), 2)

    def test_optional_runner_requires_explicit_configuration_and_does_not_move_arm(self):
        with self.assertRaises(ValueError):
            ci.plan(pool="faster")
        with self.assertRaises(ValueError):
            ci.plan(pool="faster", configured="self-hosted")
        result = ci.plan(pool="faster", configured="foundation-linux-large")["packages"]["include"]
        self.assertEqual({x["target"]: x["runner"] for x in result}["linux-aarch64"], "ubuntu-24.04-arm")

    def test_actual_architecture_is_checked(self):
        with patch.object(ci.platform, "machine", return_value="ARM64"), patch.object(ci.platform, "system", return_value="Linux"):
            ci.assert_host("linux-aarch64")
            with self.assertRaises(ValueError):
                ci.assert_host("linux-x86_64")

    def test_empty_or_duplicate_archive_inputs_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                ci.archives(root)
            for name in ("a", "b"):
                (root / name).mkdir()
                (root / name / "same.zip").touch()
            with self.assertRaises(ValueError):
                ci.archives(root)


if __name__ == "__main__":
    unittest.main()
