"""Theme opt-in source closure checks; they never build or inspect an SDK."""
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'theme_source_assembly_under_test',
    ROOT / 'recipes/webkitwasm-document-v2/assemble_sources.py')
assembly = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assembly
SPEC.loader.exec_module(assembly)


class ThemeSourceAssemblyTests(unittest.TestCase):
    def test_optin_adds_only_the_pinned_theme_source_and_helper(self):
        legacy, _, _ = assembly._maintained(
            ROOT, 'editor', include_successful_donor_helper=True)
        selected, _, _ = assembly._maintained(
            ROOT, 'editor', include_successful_donor_helper=True,
            include_theme_successor_helper=True)

        helper = assembly.BUNDLE.load(
            'appended_engine_document_maintenance').THEME_SUCCESSOR_HELPER
        self.assertEqual(helper, 'tools/appended_engine_theme_successor.py')
        self.assertNotIn(assembly.THEME_SOURCE, legacy)
        self.assertEqual(set(selected), set(legacy) | {
            assembly.THEME_SOURCE, helper})
        self.assertEqual(selected[assembly.THEME_SOURCE][1], 'source')
        self.assertEqual(selected[assembly.THEME_SOURCE][0].path,
                         ROOT / assembly.THEME_SOURCE_PATH)
        self.assertEqual(selected[assembly.THEME_SOURCE][0].sha256,
                         assembly.THEME_SOURCE_SHA256)
        self.assertEqual(selected[assembly.THEME_SOURCE][0].size,
                         assembly.THEME_SOURCE_BYTES)
        self.assertEqual(selected[helper], (
            assembly.snapshot(ROOT / helper), 'helper'))
        for name, item in legacy.items():
            self.assertEqual(selected[name], item, name)

    def test_invalid_optins_refuse_before_source_io(self):
        cases = (
            (True, 'pixel', True),
            (True, 'editor', False),
            (1, 'editor', True),
            (None, 'editor', True),
        )
        for method in ('_maintained', 'prepare'):
            for flag, profile, donor in cases:
                with self.subTest(method=method, flag=flag,
                                  profile=profile, donor=donor):
                    message = (
                        'The successful-donor helper requires an explicit '
                        'editor selection' if profile != 'editor' and donor
                        else 'The Theme successor helper requires explicit '
                        'editor and successful-donor selection')
                    with mock.patch.object(
                            assembly, 'ordinary',
                            side_effect=AssertionError(
                                'source IO before refusal')):
                        with self.assertRaisesRegex(ValueError, message):
                            if method == '_maintained':
                                assembly._maintained(
                                    ROOT, profile,
                                    include_successful_donor_helper=donor,
                                    include_theme_successor_helper=flag)
                            else:
                                assembly.prepare(
                                    Path('/unavailable-theme-source-fixture'),
                                    '1' * 64, '2' * 64,
                                    document_profile=profile,
                                    include_successful_donor_helper=donor,
                                    include_theme_successor_helper=flag)

    def test_unreviewed_helper_path_is_refused(self):
        load = assembly.HelperBundle.load

        def altered(bundle, name):
            module = load(bundle, name)
            if name == 'appended_engine_document_maintenance':
                module.THEME_SUCCESSOR_HELPER = 'tools/unreviewed_theme_helper.py'
            return module

        with mock.patch.object(assembly.HelperBundle, 'load', altered):
            with self.assertRaisesRegex(
                    ValueError, 'Maintained Theme successor helper path differs'):
                assembly._maintained(
                    ROOT, 'editor', include_successful_donor_helper=True,
                    include_theme_successor_helper=True)

    def test_cli_requires_both_explicit_selections(self):
        with redirect_stderr(io.StringIO()) as stderr:
            code = assembly.main([
                'plan', '--baseline-sources',
                '/unavailable-theme-source-fixture',
                '--baseline-recipe-sha256', '1' * 64,
                '--baseline-sources-sha256', '2' * 64,
                '--document-profile', 'editor',
                '--include-theme-successor-helper'])
        self.assertEqual(code, 1)
        self.assertIn(
            'Theme successor helper requires explicit editor and '
            'successful-donor selection', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
