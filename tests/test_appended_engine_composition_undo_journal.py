"""Pure FakeStep ownership tests; no WebCore/SDK/engine code is compiled."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = ('normal', 'empty', 'cancel', 'commit', 'empty_commit', 'foreign', 'public_undo', 'clear', 'tokens',
         'commit_clear', 'commit_exception', 'finish_exception', 'finish_clear', 'foreign_rollback',
         'limit', 'inverse_exception', 'same_step', 'empty_update', 'owner_identity', 'commit_reentry')

class CompositionUndoJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which(os.environ.get('CXX', 'c++'))
        if not compiler:
            raise RuntimeError('A native host C++ compiler is required for the tiny FakeStep fixture')
        cls.temporary = tempfile.TemporaryDirectory(prefix='composition-undo-journal-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.program = Path(cls.temporary.name) / 'journal-fixture'
        result = subprocess.run([compiler, '-std=c++20', '-O0', '-Wall', '-Wextra', '-Werror',
            str(ROOT / 'tests/appended_engine_composition_undo_journal_test.cpp'), '-o', str(cls.program)],
            cwd=ROOT, text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError('FakeStep fixture compile failed:\n' + result.stdout + result.stderr)
        cls.no_exceptions = Path(cls.temporary.name) / 'journal-no-exceptions'
        result = subprocess.run([compiler, '-std=c++20', '-O0', '-Wall', '-Wextra', '-Werror',
            '-fno-exceptions', '-fno-rtti', '-DCOMPOSITION_JOURNAL_NO_EXCEPTIONS',
            str(ROOT / 'tests/appended_engine_composition_undo_journal_test.cpp'), '-o', str(cls.no_exceptions)],
            cwd=ROOT, text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError('No-exceptions FakeStep fixture compile failed:\n' + result.stdout + result.stderr)
    def test_no_exceptions_host_contract(self):
        result = subprocess.run([str(self.no_exceptions)], cwd=ROOT, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    def run_case(self, name):
        result = subprocess.run([str(self.program), name], cwd=ROOT, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, 'passed ' + name + '\n')

def install_case(name):
    def case(self):
        self.run_case(name)
    case.__name__ = 'test_' + name
    setattr(CompositionUndoJournalTests, case.__name__, case)

for case_name in CASES:
    install_case(case_name)
