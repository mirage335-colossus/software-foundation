"""Native select event helper closure tests; no package copy or toolchain runs."""
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'select_event_source_assembly_under_test',
    ROOT / 'recipes/webkitwasm-document-v2/assemble_sources.py')
assembly = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assembly
SPEC.loader.exec_module(assembly)


class SelectEventSourceAssemblyTests(unittest.TestCase):
    def selections(self):
        return dict(include_successful_donor_helper=True,
                    include_theme_successor_helper=True,
                    include_showpicker_successor_helper=True, include_select_event_successor_helper=True)

    def test_optin_adds_exact_helper_without_changing_legacy_or_theme_closure(self):
        legacy, _, _ = assembly._maintained(
            ROOT, 'editor', include_successful_donor_helper=True)
        theme, _, _ = assembly._maintained(
            ROOT, 'editor', include_successful_donor_helper=True,
            include_theme_successor_helper=True)
        selected, _, _ = assembly._maintained(ROOT, 'editor', **self.selections())

        helper = assembly.BUNDLE.load(
            'appended_engine_document_maintenance').SELECT_EVENT_SUCCESSOR_HELPER
        self.assertEqual(helper, 'tools/appended_engine_select_event_successor.py')
        self.assertIn('appended_engine_select_event_successor', assembly.HelperBundle.NAMES)
        self.assertEqual(set(theme), set(legacy) | {
            assembly.THEME_SOURCE, 'tools/appended_engine_theme_successor.py'})
        self.assertEqual(set(selected), set(theme) | {helper, 'tools/appended_engine_showpicker_successor.py'})
        self.assertEqual(selected[helper], (assembly.snapshot(ROOT / helper), 'helper'))
        for name, item in theme.items():
            self.assertEqual(selected[name], item, name)

    def test_optin_requires_every_predecessor_selection_before_io(self):
        for key in self.selections():
            options=self.selections();options[key]=False
            if key=='include_select_event_successor_helper': options[key]=1
            with self.subTest(key=key),mock.patch.object(assembly,'ordinary',side_effect=AssertionError('IO before refusal')):
                with self.assertRaises(ValueError):assembly._maintained(ROOT,'editor',**options)
                with self.assertRaises(ValueError):assembly.prepare(Path('/unavailable'), '1'*64,'2'*64,document_profile='editor',**options)

    def test_unreviewed_select_event_helper_path_is_refused(self):
        load = assembly.HelperBundle.load

        def altered(bundle, name):
            module = load(bundle, name)
            if name == 'appended_engine_document_maintenance':
                module.SELECT_EVENT_SUCCESSOR_HELPER = 'tools/unreviewed_select_event.py'
            return module

        with mock.patch.object(assembly.HelperBundle, 'load', altered):
            with self.assertRaisesRegex(
                    ValueError, 'Maintained select event successor helper path differs'):
                assembly._maintained(ROOT, 'editor', **self.selections())

    def test_cli_requires_all_explicit_selections(self):
        with redirect_stderr(io.StringIO()) as stderr:
            code = assembly.main([
                'plan', '--baseline-sources', '/unavailable-select-event-source-fixture',
                '--baseline-recipe-sha256', '1' * 64,
                '--baseline-sources-sha256', '2' * 64,
                '--document-profile', 'editor', '--include-select-event-successor-helper'])
        self.assertEqual(code, 1)
        self.assertIn('select event successor helper requires explicit editor, successful-donor, Theme, and showPicker selections',
                      stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
