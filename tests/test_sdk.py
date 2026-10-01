import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dependency_archive import digest, file_inventory, read_json, write_json
import sdk
from sdk_manifest import verify_sdk


def fixture(root, recipe='a' * 64):
    root = Path(root)
    sources = root / 'sources'
    sources.mkdir(parents=True)
    (sources / 'compiler-input.txt').write_text('An inert retained source fixture.\n')
    write_json(sources / 'sources.json', {'schema_version': 1, 'recipe_id': recipe, 'files': file_inventory(sources)})
    tree = root / 'tree'
    (tree / 'bin').mkdir(parents=True)
    (tree / 'sysroot/usr/include').mkdir(parents=True)
    (tree / 'sysroot/usr/include/example.h').write_text('/* retained target header */\n')
    (tree / 'bin/c++').write_text('#!/bin/sh\nexit 0\n')
    (tree / 'bin/c++').chmod(0o755)
    (tree / 'LICENSE').write_text('Fixture license\n')
    target = {'system': 'Linux', 'processor': 'x86_64', 'triple': 'x86_64-linux-gnu',
              'sysroot': 'sysroot', 'cxx_compiler': 'bin/c++'}
    sdk.seal(tree, recipe, target, digest(sources / 'sources.json'), kind='diagnostic', licenses=['LICENSE'], production=False)
    group = root / 'group'
    sdk.export_group(tree, sources, group)
    return recipe, tree, sources, group


class SDKTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.recipe, self.tree, self.sources, self.group = fixture(self.root)

    def tearDown(self): self.temp.cleanup()

    def test_roundtrip_relocation_and_sources(self):
        result = sdk.install(self.group, self.recipe, self.root / 'moved SDK with spaces', production=False)
        self.assertEqual(result['recipe_id'], self.recipe)
        verify_sdk(self.root / 'moved SDK with spaces')
        sdk.restore_sources(self.group, self.recipe, self.root / 'restored')
        self.assertEqual(file_inventory(self.sources), file_inventory(self.root / 'restored'))

    def test_fixture_cannot_claim_release_readiness(self):
        with self.assertRaisesRegex(ValueError, 'preparation kind'):
            sdk.install(self.group, self.recipe, self.root / 'production')
        self.assertFalse((self.root / 'production').exists())

    def test_complete_file_inventory(self):
        (self.tree / 'unexpected').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_sdk(self.tree)

    def test_changed_compiler(self):
        (self.tree / 'bin/c++').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_sdk(self.tree)

    def test_archive_export_is_deterministic(self):
        other = self.root / 'second-group'
        sdk.export_group(self.tree, self.sources, other)
        self.assertEqual(file_inventory(self.group), file_inventory(other))

    def test_wrong_sources_rejected(self):
        (self.sources / 'compiler-input.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            sdk.export_group(self.tree, self.sources, self.root / 'bad-group')
        self.assertFalse((self.root / 'bad-group').exists())

    def test_existing_installation_preserved(self):
        destination = self.root / 'existing'
        destination.mkdir()
        (destination / 'keep').write_text('untouched')
        with self.assertRaisesRegex(ValueError, 'must be new'):
            sdk.install(self.group, self.recipe, destination, production=False)
        self.assertEqual((destination / 'keep').read_text(), 'untouched')

    def test_escaping_supplier_link(self):
        supplier = self.root / 'supplier'
        supplier.mkdir()
        try: (supplier / 'escape').symlink_to(self.sources / 'compiler-input.txt')
        except (OSError, NotImplementedError): self.skipTest('link creation unavailable')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            sdk.materialize(supplier, self.root / 'copy')

    def test_contained_alias_materialized(self):
        supplier = self.root / 'supplier'
        supplier.mkdir()
        (supplier / 'file').write_text('input')
        try: (supplier / 'alias').symlink_to('file')
        except (OSError, NotImplementedError): self.skipTest('link creation unavailable')
        sdk.materialize(supplier, self.root / 'copy')
        self.assertFalse((self.root / 'copy/alias').is_symlink())
        self.assertEqual((self.root / 'copy/alias').read_text(), 'input')

    def test_production_smoke_must_not_change_sdk_inventory(self):
        from unittest.mock import patch
        metadata = read_json(self.tree / 'sdk.json')
        metadata['kind'] = 'source-build'
        metadata['audits'] = {'host': {'status': 'passed'}, 'target': {'status': 'passed'}}
        write_json(self.tree / 'sdk.json', metadata)
        replacement = self.root / 'production-group'
        sdk.export_group(self.tree, self.sources, replacement)
        def mutating_smoke(root, work):
            (Path(root) / 'unexpected-cache.pyc').write_bytes(b'changed by a tool')
        with patch('sdk.smoke', side_effect=mutating_smoke):
            with self.assertRaisesRegex(ValueError, 'inventory'):
                sdk.install(replacement, self.recipe, self.root / 'rejected')
        self.assertFalse((self.root / 'rejected').exists())

    def test_moved_installed_root_rejected(self):
        metadata = read_json(self.tree / 'sdk.json')
        metadata['installed_root'] = '/different/location'
        write_json(self.tree / 'sdk.json', metadata)
        with self.assertRaisesRegex(ValueError, 'moved'):
            verify_sdk(self.tree)



class SupplierRecipeTests(unittest.TestCase):
    def test_browser_launcher_patch_disables_bytecode_even_with_ignored_environment(self):
        import sdk_wasm
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            text = '#!/bin/sh\nexec "$_EM_PY" -E "$0.py" "$@"\n'
            for name in ('emcc', 'em++', 'emar', 'emranlib'):
                (root / name).write_text(text)
            self.assertEqual(len(sdk_wasm.prepare_launchers(root)), 4)
            self.assertIn('-B -E', (root / 'em++').read_text())
            with self.assertRaisesRegex(ValueError, 'pinned patch contract'):
                sdk_wasm.prepare_launchers(root)

    def test_windows_empty_base_is_complete_and_checks_consumer_linker(self):
        import sdk_windows
        from dependency_store import verify_group
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = Path(__file__).resolve().parents[1] / 'third_party/sdk/windows-base.json'
            provenance = read_json(recipe)
            provenance.update(linker_version='14.44.35217.0', windows_sdk='10.0.22621.0')
            write_json(root / 'producer.json', provenance)
            result = sdk_windows.empty_base(recipe, root / 'producer.json', root / 'group')
            verify_group(root / 'group', result['recipe_id'])
            with self.assertRaisesRegex(ValueError, 'older'):
                sdk_windows.install(root / 'group', result['recipe_id'], root / 'too-old', '14.38.33130.0')
            self.assertFalse((root / 'too-old').exists())
            sdk_windows.install(root / 'group', result['recipe_id'], root / 'installed', '14.44.35217.0')
            self.assertTrue((root / 'installed/prefix/README.txt').is_file())

    def test_windows_wrong_runtime_policy_rejected(self):
        import sdk_windows
        recipe = read_json(Path(__file__).resolve().parents[1] / 'third_party/sdk/windows-base.json')
        provenance = dict(recipe, crt_linkage='dynamic', linker_version='14.44.35217.0', windows_sdk='10.0.22621.0')
        with self.assertRaisesRegex(ValueError, 'provenance'):
            sdk_windows.check_provenance(recipe, provenance)

    def test_browser_preparation_missing_pinned_input_never_downloads(self):
        import sdk_wasm
        with tempfile.TemporaryDirectory() as temporary:
            recipe = Path(__file__).resolve().parents[1] / 'third_party/sdk/wasm.json'
            with self.assertRaisesRegex(ValueError, 'missing pinned input'):
                sdk_wasm.prepare(recipe, Path(temporary) / 'empty', Path(temporary) / 'group')
            self.assertFalse((Path(temporary) / 'group').exists())

    def test_source_recipe_requires_complete_offline_inputs(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = Path(__file__).resolve().parents[1] / 'third_party/sdk/recipe.json'
            write_json(root / 'source-inputs.json', {'recipe_id': distro_sdk.recipe_id(recipe), 'files': {'downloads/missing.tar': '0' * 64}})
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                distro_sdk.verify_inputs(recipe, root)

if __name__ == '__main__': unittest.main()
