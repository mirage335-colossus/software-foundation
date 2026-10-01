import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('run_tests', Path(__file__).resolve().parents[1] / 'tools/run_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def result(self, body):
        class Case(unittest.TestCase):
            def runTest(self):
                body(self)
        return runner.execute(unittest.TestSuite([Case()]), stream=io.StringIO())

    def test_actual_success_is_complete(self):
        result = self.result(lambda case: case.assertEqual(2 + 3, 5))
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(set(result['inventory']), set(result['results']))

    def test_internal_skip_or_subtest_failure_cannot_hide(self):
        for body in (lambda case: case.skipTest('missing prerequisite'), lambda case: case.fail('incorrect')):
            self.assertEqual(self.result(body)['status'], 'failed')
        def subtest(case):
            with case.subTest('one'):
                case.assertEqual(1, 2)
        self.assertEqual(self.result(subtest)['status'], 'failed')

    def test_empty_duplicate_inventories_rejected(self):
        with self.assertRaises(ValueError):
            runner.execute(unittest.TestSuite(), stream=io.StringIO())
        case = unittest.FunctionTestCase(lambda: None)
        with self.assertRaises(ValueError):
            runner.execute(unittest.TestSuite([case, case]), stream=io.StringIO())

    def test_platform_exclusion_is_explicit_and_narrow(self):
        class Named:
            def __init__(self, name): self.name = name
            def id(self): return self.name
        name = Named('test_process_tree.NativeProcessTree.test_windows_child_cannot_break_out_of_its_job')
        self.assertIsNotNone(runner.inapplicable(name, 'Linux'))
        self.assertIsNone(runner.inapplicable(name, 'Windows'))
        self.assertIsNone(runner.inapplicable(Named('unknown.missing_tool'), 'Linux'))
        native = Named('test_sdk.NativeLinuxToolchainTests.test_compiler_selection')
        self.assertIsNone(runner.inapplicable(native, 'Linux'))
        self.assertIsNotNone(runner.inapplicable(native, 'Windows'))
        self.assertIsNone(runner.inapplicable(Named('test_sdk.SdkTests.test_inventory'), 'Windows'))
        apt = Named('test_release_check.ReleaseCheckTests.test_apt_timeout_stops_descendant_before_cleanup')
        self.assertIsNone(runner.inapplicable(apt, 'Linux'))
        self.assertIsNotNone(runner.inapplicable(apt, 'Windows'))
        self.assertIsNone(runner.inapplicable(Named('test_release_check.ReleaseCheckTests.test_apt_refuses_ordinary_host_before_any_package_command'), 'Windows'))


if __name__ == '__main__':
    unittest.main()
