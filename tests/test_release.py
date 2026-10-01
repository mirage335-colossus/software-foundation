from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import artifact
from dependency_archive import archive_tree, digest, read_json, write_json
from dependency_store import put
import release
from test_sdk import fixture
from source_identity import archive_source


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.recipe, _, _, group = fixture(self.root)
        self.base = self.root / 'base'
        put(self.base, group, self.recipe)
        source = self.root / 'application-source.tar.gz'
        source_manifest = archive_source(self.root / 'sources', source)
        tree = self.root / 'application'
        (tree / 'bin').mkdir(parents=True)
        (tree / 'bin/foundation-cli').write_text('inert archive fixture')
        (tree / 'build-info.txt').write_text('sdk_recipe_id=' + self.recipe + '\nsource_tree_sha256=' + source_manifest['tree_sha256'] + '\ntarget=linux-x86_64\ngui_backends=\ndependency_recipes=' + self.recipe + '\n')
        archive = self.root / 'application.tar.gz'
        archive_tree(tree, archive)
        manifest = self.root / 'application.tar.gz.json'
        write_json(manifest, artifact.describe(archive))
        self.spec = {'schema_version': 1, 'source': {'path': str(source), 'sha256': digest(source)},
          'artifacts': [{'path': str(archive), 'manifest_path': str(manifest), 'sha256': digest(archive),
                         'target': 'linux-x86_64', 'backends': [], 'sdk_recipe': self.recipe}],
          'required_scopes': ['core', 'installed-consumer', 'abi', 'offline-recovery']}
        self.spec_path = self.root / 'spec.json'
        write_json(self.spec_path, self.spec)

    def tearDown(self): self.temp.cleanup()

    def test_release_owns_exact_groups_and_recovers_without_base(self):
        output = self.root / 'release'
        release.assemble(self.spec_path, self.base, output)
        shutil.rmtree(self.base)
        metadata = release.verify_release(output)
        release.recover(output, self.root / 'restored')
        self.assertEqual(metadata['dependencies'][0]['recipe_id'], self.recipe)
        self.assertTrue((self.root / 'restored/dependencies' / self.recipe).is_dir())
        self.assertEqual(metadata['qualification'], 'candidate')

    def test_missing_base_fails_without_partial_release(self):
        shutil.rmtree(self.base)
        with self.assertRaisesRegex(ValueError, 'missing'):
            release.assemble(self.spec_path, self.base, self.root / 'release')
        self.assertFalse((self.root / 'release').exists())

    def test_wrong_sdk_in_package_fails(self):
        self.spec['artifacts'][0]['sdk_recipe'] = 'b' * 64
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'packaged SDK'):
            release.assemble(self.spec_path, self.base, self.root / 'release')

    def test_frozen_source_digest_required(self):
        self.spec['source']['sha256'] = '0' * 64
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'source archive differs'):
            release.assemble(self.spec_path, self.base, self.root / 'release')

    def test_changed_retained_asset_invalidates_release(self):
        output = self.root / 'release'
        release.assemble(self.spec_path, self.base, output)
        (output / 'application.tar.gz').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify_release(output)

    def test_added_untracked_asset_invalidates_release(self):
        output = self.root / 'release'
        release.assemble(self.spec_path, self.base, output)
        (output / 'extra').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify_release(output)

    def test_declared_target_cannot_relabel_package(self):
        self.spec['artifacts'][0]['target'] = 'linux-aarch64'
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'packaged target'):
            release.assemble(self.spec_path, self.base, self.root / 'release')

    def test_declared_backend_cannot_relabel_package(self):
        self.spec['artifacts'][0]['backends'] = ['terminal']
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'packaged backends'):
            release.assemble(self.spec_path, self.base, self.root / 'release')

    def test_unrelated_source_archive_cannot_substitute(self):
        (self.root / 'sources/other.cpp').write_text('different source')
        replacement = self.root / 'replacement-source.tar.gz'
        archive_source(self.root / 'sources', replacement)
        self.spec['source'] = {'path': str(replacement), 'sha256': digest(replacement)}
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'packaged source tree'):
            release.assemble(self.spec_path, self.base, self.root / 'release')

    def test_unbound_dependency_cannot_be_omitted(self):
        self.spec['artifacts'][0]['dependency_recipes'] = [self.recipe, 'b' * 64]
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'packaged dependency list'):
            release.assemble(self.spec_path, self.base, self.root / 'release')

    def test_duplicate_required_scope_rejected(self):
        self.spec['required_scopes'] = ['core', 'core']
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'unique'):
            release.assemble(self.spec_path, self.base, self.root / 'release')


if __name__ == '__main__': unittest.main()
