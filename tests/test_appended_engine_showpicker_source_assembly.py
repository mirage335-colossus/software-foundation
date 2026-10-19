"""Native showPicker helper closure tests; no package copy or toolchain runs."""
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'showpicker_source_assembly_under_test',
    ROOT / 'recipes/webkitwasm-document-v2/assemble_sources.py')
assembly = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assembly
SPEC.loader.exec_module(assembly)


class ShowPickerSourceAssemblyTests(unittest.TestCase):
    def selections(self):
        return dict(include_successful_donor_helper=True,
                    include_theme_successor_helper=True,
                    include_showpicker_successor_helper=True)

    def test_optin_adds_exact_helper_without_changing_legacy_or_theme_closure(self):
        legacy, _, _ = assembly._maintained(
            ROOT, 'editor', include_successful_donor_helper=True)
        theme, _, _ = assembly._maintained(
            ROOT, 'editor', include_successful_donor_helper=True,
            include_theme_successor_helper=True)
        selected, _, _ = assembly._maintained(ROOT, 'editor', **self.selections())

        helper = assembly.BUNDLE.load(
            'appended_engine_document_maintenance').SHOWPICKER_SUCCESSOR_HELPER
        self.assertEqual(helper, 'tools/appended_engine_showpicker_successor.py')
        self.assertIn('appended_engine_showpicker_successor', assembly.HelperBundle.NAMES)
        self.assertEqual(set(theme), set(legacy) | {
            assembly.THEME_SOURCE, 'tools/appended_engine_theme_successor.py'})
        self.assertEqual(set(selected), set(theme) | {helper})
        self.assertEqual(selected[helper], (assembly.snapshot(ROOT / helper), 'helper'))
        for name, item in theme.items():
            self.assertEqual(selected[name], item, name)

    def test_showpicker_optin_requires_editor_donor_and_theme_helper_before_io(self):
        cases = (
            ('pixel', True, True, True,
             'successful-donor helper requires an explicit editor selection'),
            ('editor', False, True, True,
             'Theme successor helper requires explicit editor and successful-donor selection'),
            ('editor', True, False, True,
             'showPicker successor helper requires explicit editor, successful-donor, and Theme-helper selection'),
            ('editor', True, True, 1,
             'showPicker successor helper requires explicit editor, successful-donor, and Theme-helper selection'),
        )
        for profile, donor, theme, showpicker, message in cases:
            kwargs = dict(include_successful_donor_helper=donor,
                          include_theme_successor_helper=theme,
                          include_showpicker_successor_helper=showpicker)
            with self.subTest(profile=profile, **kwargs):
                with mock.patch.object(
                        assembly, 'ordinary',
                        side_effect=AssertionError('source IO before refusal')):
                    with self.assertRaisesRegex(ValueError, message):
                        assembly._maintained(ROOT, profile, **kwargs)
                    with self.assertRaisesRegex(ValueError, message):
                        assembly.prepare(Path('/unavailable-showpicker-source-fixture'),
                            '1' * 64, '2' * 64, document_profile=profile, **kwargs)

    def test_unreviewed_showpicker_helper_path_is_refused(self):
        load = assembly.HelperBundle.load

        def altered(bundle, name):
            module = load(bundle, name)
            if name == 'appended_engine_document_maintenance':
                module.SHOWPICKER_SUCCESSOR_HELPER = 'tools/unreviewed_showpicker.py'
            return module

        with mock.patch.object(assembly.HelperBundle, 'load', altered):
            with self.assertRaisesRegex(
                    ValueError, 'Maintained showPicker successor helper path differs'):
                assembly._maintained(ROOT, 'editor', **self.selections())

    def test_cli_requires_all_explicit_selections(self):
        with redirect_stderr(io.StringIO()) as stderr:
            code = assembly.main([
                'plan', '--baseline-sources', '/unavailable-showpicker-source-fixture',
                '--baseline-recipe-sha256', '1' * 64,
                '--baseline-sources-sha256', '2' * 64,
                '--document-profile', 'editor', '--include-showpicker-successor-helper'])
        self.assertEqual(code, 1)
        self.assertIn('showPicker successor helper requires explicit editor, successful-donor, and Theme-helper selection',
                      stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
