"""Tiny actual-function fixtures: no retained source, donor, SDK or assembly."""
import argparse
import ast
import contextlib
import copy
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RELATIVE = 'recipes/webkitwasm-document-v2/assemble_sources.py'
POSTIMAGE = ROOT / RELATIVE
HELPER = 'tools/appended_engine_successful_donor.py'


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Invalid ' + label)


def path_name(value):
    if type(value) is not str or not value or value.startswith('/') or '..' in value.split('/'):
        raise ValueError('Invalid fixture logical path')
    return value


def text(value, label):
    if type(value) is not str or not value:
        raise ValueError('Invalid ' + label)


def sha256(value, label):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid ' + label)


def functions(path, name):
    """Execute only named assembler functions; project modules are never imported."""
    selected = {'Source', 'digest', 'ordinary', '_state_identity', 'identity',
        'retained_mode', 'snapshot', 'read_small', 'read_json', '_maintained',
        '_preflight_tree', 'prepare', '_recheck', 'main'}
    tree = ast.parse(path.read_text(), str(path))
    body = [node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in selected]
    if {node.name for node in body} != selected:
        raise AssertionError('Expected complete selected assembler function set')
    module = types.ModuleType(name)
    sys.modules[name] = module
    module.__dict__.update({
        'argparse': argparse, 'dataclass': dataclass, 'hashlib': hashlib,
        'os': os, 'Path': Path, 're': re, 'stat': stat, 'sys': sys,
        'ROOT': Path('/nonexistent-fixture-repository'),
        'RECIPE_ROOT': 'recipes/webkitwasm-document-v2',
        'MAX_SMALL_BYTES': 32 * 1024 * 1024,
        'MAX_SOURCE_BYTES': 8 * 1024 * 1024 * 1024,
        'MAX_INPUTS': 4096, 'MAX_DIRECTORIES': 4096 * 8,
        'KIND': 'foundation-document-v2-source-assembly-v1', 'encoded': encoded,
        'contract': types.SimpleNamespace(strict_json=lambda raw, label: json.loads(raw),
            json_copy=copy.deepcopy, validate_sha256=sha256, BASE_HEADER_SHA256='1' * 64),
        'manifest': types.SimpleNamespace(fields=fields, path_name=path_name, text=text,
            ROLES={'source', 'config', 'helper', 'patch', 'license', 'interface'}),
        '_validate_projection': mock.Mock(),
    })
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), module.__dict__)
    return module


class SuccessfulHelperSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='successful-source-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.new = functions(POSTIMAGE, '_successful_source_postimage')
        self.addCleanup(sys.modules.pop, self.new.__name__, None)
        self.driver = types.SimpleNamespace(ROOT=self.root,
            profile_path=lambda selected: 'profile-' + selected + '.json',
            profile=lambda selected: {}, checked_document=lambda *args: {},
            profile_selector=lambda selected: selected, SUCCESSFUL_HELPER=HELPER,
            required_helpers=lambda selected: ('tools/base.py', 'profile-' + selected + '.json'))
        self.bundle = types.SimpleNamespace(load=lambda name: self.driver, snapshots=lambda: [])
        for module in (self.new,):
            module.HelperBundle = lambda repository: self.bundle
            module.BUNDLE = self.bundle
        self.write('tools/base.py', b'# inert base helper\n')
        self.write(HELPER, b'# inert successful donor helper, never executed\n')
        self.write(RELATIVE, b'# inert assembler input, never executed\n')
        self.write('source.cpp', b'// inert selected source\n')
        self.write('original.patch', b'// inert provenance, never applied\n')
        self.write('NOTICE-INDEX.json', encoded({'files': {}}))
        for selected in ('pixel', 'physical', 'editor'):
            self.selection(selected)
        for target in ('subprocess.Popen', 'os.execv', 'os.system', 'shutil.which'):
            patcher = mock.patch(target, side_effect=AssertionError('No program/discovery allowed'))
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
        return path

    def selection(self, selected):
        here = 'recipes/webkitwasm-document-v2/'
        self.write('profile-' + selected + '.json', encoded({}))
        source = (self.root / 'source.cpp').read_bytes()
        mapped = {'source/selected.cpp': {'tracked_path': 'source.cpp', 'sha256': sha(source),
            'bytes': len(source), 'mode': 0o644, 'origin': {'sha256': sha(source)}, 'role': 'source'}}
        source_map = b'{}\n'
        self.write(here + 'provenance/' + selected + '-source-map.json', source_map)
        imports = {'schema_version': 1, 'kind': 'foundation-document-v2-source-imports-v1',
            'document_profile': selected, 'capsule_version': 'inert-fixture',
            'capsule_source_closure_sha256': '2' * 64,
            'capsule_source_map_sha256': sha(source_map), 'files': mapped,
            'original_supplier_patch': {'tracked_path': 'original.patch',
                'sha256': sha((self.root / 'original.patch').read_bytes())},
            'selected_notice_index': {'tracked_path': 'NOTICE-INDEX.json',
                'sha256': sha((self.root / 'NOTICE-INDEX.json').read_bytes())},
            'limits': 'Tiny inert fixture; no actual source or SDK'}
        self.write(here + 'source-imports-' + selected + '.json', encoded(imports))
        self.write(here + 'source-projection-' + selected + '.json', encoded({'files': mapped}))

    @staticmethod
    def logical(entries):
        return {name: (saved.sha256, saved.size, saved.mode, role)
                for name, (saved, role) in entries.items()}

    def test_default_inventory_matches_literal_tiny_catalogue_for_all_profiles(self):
        del self.driver.SUCCESSFUL_HELPER  # Default also supports the old driver API.
        for selected in ('pixel', 'physical', 'editor'):
            with self.subTest(selected=selected):
                prefix = 'recipes/webkitwasm-document-v2/'
                # This is the independent expected input fixture, not another
                # implementation of the producer's selection algorithm.
                catalogue = {
                    'source/selected.cpp': ('source.cpp', 'source'),
                    'tools/base.py': ('tools/base.py', 'helper'),
                    'profile-' + selected + '.json': ('profile-' + selected + '.json', 'helper'),
                    prefix + 'assemble_sources.py': (prefix + 'assemble_sources.py', 'helper'),
                    prefix + 'source-imports-' + selected + '.json':
                        (prefix + 'source-imports-' + selected + '.json', 'config'),
                    prefix + 'source-projection-' + selected + '.json':
                        (prefix + 'source-projection-' + selected + '.json', 'config'),
                    'provenance/document-source-map.json':
                        (prefix + 'provenance/' + selected + '-source-map.json', 'config'),
                    'original.patch': ('original.patch', 'config'),
                    'NOTICE-INDEX.json': ('NOTICE-INDEX.json', 'config'),
                }
                expected = {}
                for name, (physical, role) in catalogue.items():
                    raw = (self.root / physical).read_bytes()
                    expected[name] = (sha(raw), len(raw), 0o644, role)
                default, _, raw = self.new._maintained(self.root, selected)
                explicit, _, explicit_raw = self.new._maintained(self.root, selected,
                    include_successful_donor_helper=False)
                self.assertEqual(self.logical(default), expected)
                self.assertEqual(self.logical(explicit), expected)
                self.assertEqual(raw, explicit_raw)
                self.assertNotIn(HELPER, default)

    def test_opt_in_adds_only_exact_helper_and_preserves_every_other_input(self):
        default, _, before = self.new._maintained(self.root, 'editor')
        selected, snapshots, after = self.new._maintained(self.root, 'editor',
            include_successful_donor_helper=True)
        self.assertEqual(set(selected) - set(default), {HELPER})
        self.assertEqual(self.logical({k: v for k, v in selected.items() if k != HELPER}),
            self.logical(default))
        saved, role = selected[HELPER]
        self.assertEqual((saved.sha256, saved.mode, role),
            (sha((self.root / HELPER).read_bytes()), 0o644, 'helper'))
        self.assertIn(saved, snapshots)
        self.assertEqual(before, after)

    def test_invalid_profile_and_non_boolean_flag_reject_before_any_input_read(self):
        cases = [('pixel', True), ('physical', True), ('editor', 1),
                 ('editor', None), ('editor', 'yes')]
        for selected, option in cases:
            with self.subTest(selected=selected, option=option), \
                    mock.patch.object(self.new, 'HelperBundle', side_effect=AssertionError('read')), \
                    mock.patch.object(self.new, '_recheck', side_effect=AssertionError('read')):
                with self.assertRaises(ValueError):
                    self.new._maintained(self.root, selected, include_successful_donor_helper=option)
                with self.assertRaises(ValueError):
                    self.new.prepare(self.root / 'absent', '1' * 64, '2' * 64,
                        document_profile=selected, repository=self.root,
                        include_successful_donor_helper=option)

    def test_missing_helper_rejects_instead_of_falling_back_to_default(self):
        (self.root / HELPER).unlink()
        with self.assertRaises(FileNotFoundError):
            self.new._maintained(self.root, 'editor', include_successful_donor_helper=True)
        self.assertNotIn(HELPER, self.new._maintained(self.root, 'editor')[0])

    def test_absent_or_foreign_driver_constant_cannot_expand_the_catalogue(self):
        for value in (None, 'tools/other.py', '../escape.py'):
            with self.subTest(value=value):
                self.driver.SUCCESSFUL_HELPER = value
                with self.assertRaisesRegex(ValueError, 'helper path differs'):
                    self.new._maintained(self.root, 'editor', include_successful_donor_helper=True)

    def test_changed_or_replaced_selected_helper_is_rejected_by_existing_recheck(self):
        for replace in (False, True):
            with self.subTest(replace=replace):
                self.write(HELPER, b'# first inert helper\n')
                _, snapshots, _ = self.new._maintained(self.root, 'editor',
                    include_successful_donor_helper=True)
                if replace:
                    replacement = self.write('replacement.py', b'# first inert helper\n')
                    os.replace(replacement, self.root / HELPER)
                else:
                    self.write(HELPER, b'# changed inert helper\n')
                with self.assertRaises(ValueError):
                    self.new._recheck({'snapshots': snapshots})

    def test_cli_forwards_the_explicit_option_and_default(self):
        for include in (False, True):
            with self.subTest(include=include):
                plan = {'document_profile': 'editor', 'source_files': 1, 'source_bytes': 1}
                prepare = mock.Mock(return_value=plan)
                with mock.patch.object(self.new, 'prepare', prepare), contextlib.redirect_stdout(io.StringIO()):
                    code = self.new.main(['plan', '--baseline-sources', str(self.root),
                        '--baseline-recipe-sha256', '1' * 64, '--baseline-sources-sha256', '2' * 64,
                        '--document-profile', 'editor'] +
                        (['--include-successful-donor-helper'] if include else []))
                self.assertEqual(code, 0)
                self.assertEqual(prepare.call_args.kwargs,
                    {'document_profile': 'editor', 'include_successful_donor_helper': include})

    def test_prepare_threads_opt_in_to_selection_and_recipe_without_publishing(self):
        # Exercise actual prepare, with the preexisting retained-contract/parser
        # dependencies replaced by a coherent seven-byte baseline fixture.
        baseline = self.root / 'baseline'
        baseline.mkdir()
        source = baseline / 'source.cpp'
        source.write_bytes(b'// old\n')
        source.chmod(0o644)
        recipe = {'provider': {'format': 'browser-module', 'binding': 'copied-owner-bridge',
            'abi_major': 1, 'abi_minor': 0, 'header_sha256': '1' * 64},
            'target': {'system': 'Emscripten', 'processor': 'wasm32', 'pointer_bits': 32},
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'},
            'inputs': {'source.cpp': {'sha256': sha(source.read_bytes()), 'mode': 0o644, 'role': 'source'}}}
        raw_recipe = encoded(recipe)
        (baseline / 'recipe.json').write_bytes(raw_recipe)
        raw_sources = encoded({'files': {'source.cpp': sha(source.read_bytes()),
            'recipe.json': sha(raw_recipe)}, 'directories': [],
            'modes': {'source.cpp': 0o644, 'recipe.json': 0o644}})
        (baseline / 'sources.json').write_bytes(raw_sources)
        for path in baseline.iterdir():
            path.chmod(0o644)
        sources = json.loads(raw_sources)
        self.new.manifest.source_contract = lambda *args: None
        self.new.manifest.verify_sources = lambda root: (sources, sha(raw_sources), copy.deepcopy(recipe))
        self.new.manifest.recipe_contract = lambda value: None
        self.new.manifest.PathInventory = lambda: types.SimpleNamespace(add=lambda *args: None)
        selected, snapshots, _ = self.new._maintained(self.root, 'editor',
            include_successful_donor_helper=True)
        raw_projection = encoded({'files': {}})
        metadata = types.SimpleNamespace(_assembly_snapshot=self.new.snapshot(self.root / RELATIVE),
            fixed_plan=lambda *args, **kwargs: {})
        self.driver._assembly_snapshot = self.new.snapshot(self.root / 'tools/base.py')
        for include in (False, True):
            with self.subTest(include=include):
                entries = selected if include else {k: v for k, v in selected.items() if k != HELPER}
                with mock.patch.object(self.new, '_maintained', return_value=(entries, snapshots, raw_projection)) as maintained, \
                        mock.patch.object(self.new, '_module', return_value=metadata, create=True):
                    plan = self.new.prepare(baseline, sha(raw_recipe), sha(raw_sources),
                        document_profile='editor', repository=self.root,
                        include_successful_donor_helper=include)
                if include:
                    maintained.assert_called_once_with(self.root, 'editor', include_successful_donor_helper=True)
                else:
                    maintained.assert_called_once_with(self.root, 'editor')
                self.assertEqual(HELPER in plan['recipe']['inputs'], include)
                if include:
                    self.assertEqual(plan['recipe']['inputs'][HELPER],
                        {'sha256': selected[HELPER][0].sha256, 'mode': 0o644, 'role': 'helper'})
                self.assertFalse((self.root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
