#!/usr/bin/env python3
"""Run a complete registered unit suite and expose every case and exclusion."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def inapplicable(case, system):
    """Only platform facts exclude cases; missing tools/permissions are failures."""
    name = case.id()
    if system != 'Linux' and name.startswith('test_process_tree.LinuxSubreaper.'):
        return 'Native Linux descendant supervision belongs to the Linux runner.'
    if system != 'Windows' and name == 'test_process_tree.NativeProcessTree.test_windows_child_cannot_break_out_of_its_job':
        return 'Native Windows Job Object check belongs to the Windows runner.'
    if system == 'Windows':
        if name == 'test_coverage.CoverageTests.test_parent_success_with_inherited_log_child_is_rejected':
            return 'POSIX process-group fixture; Windows Job Object cases remain required.'
        if name.startswith('test_portability.Portability.') or name.startswith('test_portability.PortabilityTests.'):
            return 'ELF runtime qualification belongs to Linux runners; PE checks remain required.'
        if name == 'test_source_identity.SourceIdentityTests.test_executable_mode_changes_identity':
            return 'POSIX executable metadata belongs to POSIX runners.'
    return None


class Recorded(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = {'status': 'passed'}

    def addError(self, test, error):
        super().addError(test, error)
        self.outcomes[test.id()] = {'status': 'failed', 'reason': 'error'}

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.outcomes[test.id()] = {'status': 'failed', 'reason': 'assertion'}

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = {'status': 'incomplete', 'reason': reason}

    def addExpectedFailure(self, test, error):
        super().addExpectedFailure(test, error)
        self.outcomes[test.id()] = {'status': 'incomplete', 'reason': 'expected failure'}

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = {'status': 'failed', 'reason': 'unexpected success'}

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.outcomes[test.id()] = {'status': 'failed', 'reason': 'subtest'}


def execute(suite, system=None, stream=None):
    tests = list(flatten(suite))
    names = [test.id() for test in tests]
    if not names or len(set(names)) != len(names):
        raise ValueError('empty or duplicate test inventory')
    system = system or platform.system()
    excluded, selected = {}, []
    for test in tests:
        reason = inapplicable(test, system)
        if reason:
            excluded[test.id()] = reason
        else:
            selected.append(test)
    if not selected:
        raise ValueError('no applicable checks; do not schedule this suite on this host')
    result = unittest.TextTestRunner(stream=stream or sys.stderr, verbosity=2, resultclass=Recorded).run(unittest.TestSuite(selected))
    required = {test.id() for test in selected}
    complete = (result.wasSuccessful() and set(result.outcomes) == required and
                all(item['status'] == 'passed' for item in result.outcomes.values()))
    return {'schema_version': 1, 'system': system, 'status': 'passed' if complete else 'failed',
            'inventory': names, 'excluded': excluded, 'results': result.outcomes}


def publish(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_]*', args.suite):
        raise ValueError('invalid registered suite')
    name = 'test_' + args.suite
    path = ROOT / 'tests' / (name + '.py')
    if not path.is_file():
        raise ValueError('missing registered suite')
    args.output.unlink(missing_ok=True)
    # Test modules can import local fixtures and maintained tools explicitly.
    sys.path.insert(0, str(ROOT / 'tests'))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = execute(unittest.defaultTestLoader.loadTestsFromModule(module))
    publish(args.output, result)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, ImportError) as error:
        print('unit runner: ' + str(error), file=sys.stderr)
        sys.exit(1)
