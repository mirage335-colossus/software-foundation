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

    def test_optional_c_compiler_is_verified_and_retained(self):
        (self.tree / 'bin/cc').write_text('retained C compiler fixture')
        metadata = read_json(self.tree / 'sdk.json')
        metadata['target']['c_compiler'] = 'bin/cc'
        metadata['files'] = file_inventory(self.tree, exclude=('sdk.json',))
        write_json(self.tree / 'sdk.json', metadata)
        verify_sdk(self.tree)
        (self.tree / 'bin/cc').write_text('changed C compiler')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_sdk(self.tree)

    def test_c_compiler_must_be_contained_file_in_inventory(self):
        metadata = read_json(self.tree / 'sdk.json')
        for name in ('../outside-cc', 'sysroot', ''):
            metadata['target']['c_compiler'] = name
            write_json(self.tree / 'sdk.json', metadata)
            with self.subTest(path=name), self.assertRaises(ValueError):
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
        # This fixture isolates post-use inventory checking from real SDK ABI qualification.
        with patch('sdk.verify_sdk', side_effect=lambda root, release=False: verify_sdk(root)), \
             patch('sdk.smoke', side_effect=mutating_smoke):
            with self.assertRaisesRegex(ValueError, 'inventory'):
                sdk.install(replacement, self.recipe, self.root / 'rejected')
        self.assertFalse((self.root / 'rejected').exists())

    def test_runtime_audit_cannot_claim_another_recipe(self):
        metadata = read_json(self.tree / 'sdk.json')
        metadata['kind'] = 'source-build'
        metadata['audits'] = {'host': {'status': 'passed'}, 'target': {'status': 'passed',
            'scope': 'sdk-sysroot', 'sdk_runtime': {'recipe_id': 'b' * 64}}}
        write_json(self.tree / 'sdk.json', metadata)
        with self.assertRaisesRegex(ValueError, 'bound to its retained'):
            verify_sdk(self.tree, release=True)

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
                (root / name).write_bytes(text.encode('utf-8'))
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

    def test_windows_linker_version_normalizes_only_missing_revision(self):
        import sdk_windows
        self.assertEqual(sdk_windows.linker_version('14.44.35217'), (14, 44, 35217, 0))
        self.assertEqual(sdk_windows.linker_version('14.44.35217'), sdk_windows.linker_version('14.44.35217.0'))
        self.assertLess(sdk_windows.linker_version('14.44.35217'), sdk_windows.linker_version('14.44.35217.1'))
        self.assertLess(sdk_windows.linker_version('14.43.99999.9'), sdk_windows.linker_version('14.44.1'))
        for invalid in ('14.44', '14.44.1.0.0', '14.44.1-preview', ' 14.44.1', '14.44.-1', '', None):
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, 'linker version'):
                sdk_windows.linker_version(invalid)

    def test_windows_dependency_install_compares_three_and_four_components(self):
        import sdk_windows
        recipe = Path(__file__).resolve().parents[1] / 'third_party/sdk/windows-base.json'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (producer, consumer, accepted) in enumerate((
                    ('14.44.35217.0', '14.44.35217', True),
                    ('14.44.35217', '14.44.35217.0', True),
                    ('14.44.35217.1', '14.44.35217', False))):
                provenance = dict(read_json(recipe), linker_version=producer, windows_sdk='10.0.22621.0')
                write_json(root / 'producer.json', provenance)
                group = root / ('group-' + str(index)); output = root / ('installed-' + str(index))
                result = sdk_windows.empty_base(recipe, root / 'producer.json', group)
                if accepted:
                    sdk_windows.install(group, result['recipe_id'], output, consumer)
                    self.assertTrue((output / 'prefix/README.txt').is_file())
                else:
                    with self.assertRaisesRegex(ValueError, 'older'):
                        sdk_windows.install(group, result['recipe_id'], output, consumer)
                    self.assertFalse(output.exists())

    def test_native_gui_recipes_require_rev_display_dependency(self):
        root = Path(__file__).resolve().parents[1] / 'third_party/sdk'
        for profile in ('gui-x86_64', 'gui-aarch64'):
            recipe = read_json(root / profile / 'recipe.json')
            self.assertIn('BR2_PACKAGE_XLIB_LIBXRANDR', recipe['required_packages'])
            self.assertIn('select BR2_PACKAGE_XLIB_LIBXRANDR', (root / profile / 'Config.in').read_text())

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
            write_json(root / 'source-inputs.json', {'schema_version': 1, 'recipe_id': distro_sdk.recipe_id(recipe), 'files': {'downloads/missing.tar': '0' * 64}})
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                distro_sdk.verify_inputs(recipe, root)


class ProducerContractTests(unittest.TestCase):
    def test_wasm_inputs_are_build_tools_not_validation_browsers(self):
        recipe = read_json(Path(__file__).resolve().parents[1] / 'third_party/sdk/wasm.json')
        self.assertEqual({i['name'] for i in recipe['inputs']}, {'emsdk', 'compiler', 'node'})

    def test_native_recipes_require_matching_bookworm_hosts(self):
        import distro_sdk
        from unittest.mock import patch
        root = Path(__file__).resolve().parents[1]
        for architecture, path in (('x86_64', 'third_party/sdk/recipe.json'),
                                   ('aarch64', 'third_party/sdk/aarch64/recipe.json')):
            with self.subTest(architecture=architecture):
                recipe = root / path
                manifest = read_json(recipe)
                with patch('distro_sdk.read_json', return_value=manifest), \
                     patch('distro_sdk.platform.system', return_value='Linux'), \
                     patch('distro_sdk.platform.machine', return_value=architecture), \
                     patch('distro_sdk.Path.read_text', return_value='ID=debian\nVERSION_ID="12"\n'), \
                     patch('distro_sdk.shutil.which', return_value='/usr/bin/tool'):
                    self.assertEqual(distro_sdk.host_check(recipe)['host'], 'debian-12-' + architecture)
                with patch('distro_sdk.platform.system', return_value='Linux'), \
                     patch('distro_sdk.platform.machine', return_value='unsupported'):
                    with self.assertRaisesRegex(ValueError, 'native'):
                        distro_sdk.host_check(recipe)
        self.assertNotEqual(distro_sdk.recipe_id(root / 'third_party/sdk/recipe.json'),
                            distro_sdk.recipe_id(root / 'third_party/sdk/aarch64/recipe.json'))

    def test_native_resolution_cannot_omit_or_substitute_pinned_inputs(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); recipe_dir = root / 'recipe'; recipe_dir.mkdir()
            source = Path(__file__).resolve().parents[1] / 'third_party/sdk'
            for name in ('config', 'Config.in', 'external.desc', 'external.mk'):
                (recipe_dir / name).write_bytes((source / name).read_bytes())
            recipe = read_json(source / 'recipe.json')
            files = {}
            for item, directory in ((recipe['buildroot'], 'bootstrap'), (recipe['glibc_source'], 'downloads/glibc')):
                path = root / 'cache' / directory / item['file']; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'Pinned fixture input.'); item['sha256'] = digest(path)
                files[path.relative_to(root / 'cache').as_posix()] = digest(path)
            write_json(recipe_dir / 'recipe.json', recipe)
            resolution = {'glibc': {'dl_dir': 'glibc', 'downloads': [{'source': recipe['glibc_source']['file']}]}}
            write_json(root / 'cache/resolution.json', resolution)
            state = {'schema_version': 1, 'recipe_id': distro_sdk.recipe_id(recipe_dir / 'recipe.json'),
                     'resolution_sha256': digest(root / 'cache/resolution.json'), 'files': files}
            write_json(root / 'cache/source-inputs.json', state)
            # Retained manifests use portable relative names on every host.
            self.assertTrue(all('\\' not in name for name in files))
            self.assertEqual(distro_sdk.verify_inputs(recipe_dir / 'recipe.json', root / 'cache'), state)
            complete = dict(files)
            omitted = next(p for p in files if p.startswith('downloads/')); del state['files'][omitted]
            write_json(root / 'cache/source-inputs.json', state)
            with self.assertRaisesRegex(ValueError, 'complete resolved'):
                distro_sdk.verify_inputs(recipe_dir / 'recipe.json', root / 'cache')
            state['files'] = complete
            bootstrap = 'bootstrap/' + recipe['buildroot']['file']
            (root / 'cache' / bootstrap).write_bytes(b'Substituted fixture input.')
            state['files'][bootstrap] = digest(root / 'cache' / bootstrap)
            write_json(root / 'cache/source-inputs.json', state)
            with self.assertRaisesRegex(ValueError, 'pinned bootstrap'):
                distro_sdk.verify_inputs(recipe_dir / 'recipe.json', root / 'cache')

    def test_windows_empty_fetch_build_recovery_needs_no_supplier(self):
        import sdk_windows
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); recipe_path = Path(__file__).resolve().parents[1] / 'third_party/sdk/windows-base.json'
            recipe = read_json(recipe_path); provenance = dict(recipe, linker_version='14.44.35217.0', windows_sdk='10.0.22621.0')
            write_json(root / 'producer.json', provenance)
            with patch('sdk_windows.host_provenance', return_value=(recipe, provenance)), \
                 patch('sdk_windows.subprocess.run', side_effect=AssertionError('empty recipe invoked supplier')):
                sdk_windows.fetch(recipe_path, root / 'producer.json', root / 'cache')
                result = sdk_windows.build(recipe_path, root / 'producer.json', root / 'cache', root / 'group')
            sdk.restore_sources(root / 'group', result['recipe_id'], root / 'restored')
            self.assertEqual(sdk_windows.recipe_identity(root / 'restored/recipe/windows-base.json'), result['recipe_id'])
            sdk_windows.verify_inputs(root / 'restored/recipe/windows-base.json', root / 'restored/cache')
            sdk_windows.install(root / 'group', result['recipe_id'], root / 'installed', '14.44.35217.0')
            self.assertTrue((root / 'installed/prefix/README.txt').is_file())

    def test_windows_supplier_source_rejects_links_and_wrong_commit(self):
        import sdk_windows, zipfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); archive = root / 'source.zip'; revision = 'a' * 40
            with zipfile.ZipFile(archive, 'w') as output:
                output.comment = revision.encode(); entry = zipfile.ZipInfo('escape')
                entry.external_attr = 0o120777 << 16; output.writestr(entry, '../escape')
            with self.assertRaisesRegex(ValueError, 'unsupported'):
                sdk_windows.extract_supplier(archive, root / 'tree', revision)
            self.assertFalse((root / 'tree').exists())
            with self.assertRaisesRegex(ValueError, 'revision'):
                sdk_windows.extract_supplier(archive, root / 'tree', 'b' * 40)

    def test_windows_offline_environment_blocks_origin_and_ambient_caches(self):
        import sdk_windows
        from unittest.mock import patch
        with patch.dict(os.environ, {'VCPKG_BINARY_SOURCES': 'untrusted', 'VCPKG_OVERLAY_PORTS': 'untrusted'}):
            env = sdk_windows.supplier_environment(Path('supplier'), Path('downloads'), 3, False)
        self.assertEqual(env['VCPKG_BINARY_SOURCES'], 'clear')
        self.assertEqual(env['X_VCPKG_ASSET_SOURCES'], 'clear;x-block-origin')
        self.assertEqual(env['VCPKG_MAX_CONCURRENCY'], '3')
        self.assertNotIn('VCPKG_OVERLAY_PORTS', env)

    def test_windows_fetch_retains_late_downloads_and_discards_maintenance_install(self):
        import sdk_windows, zipfile, subprocess
        from unittest.mock import patch
        for fail in (False, True):
            with self.subTest(failure=fail), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); templates = Path(__file__).resolve().parents[1] / 'third_party/sdk'
                recipe_dir = root / 'recipe'; recipe_dir.mkdir()
                recipe = read_json(templates / 'windows-base.json'); recipe['ports'] = ['example[core]']
                recipe_path = recipe_dir / 'windows-base.json'; write_json(recipe_path, recipe)
                (recipe_dir / 'windows-toolchain.json').write_bytes((templates / 'windows-toolchain.json').read_bytes())
                provenance = dict(recipe, linker_version='14.44.35217.0', windows_sdk='10.0.22621.0',
                                  tools_version='14.44.35217', installation_path=str(root))
                actions = []
                def runner(argv, **kwargs):
                    if argv[:2] == ['git', 'init']:
                        Path(argv[2]).mkdir()
                    elif argv[0] == 'git' and 'archive' in argv:
                        archive = Path(next(a.split('=', 1)[1] for a in argv if a.startswith('--output=')))
                        with zipfile.ZipFile(archive, 'w') as output:
                            output.comment = recipe['vcpkg_ref'].encode()
                            output.writestr('LICENSE.txt', 'Supplier fixture terms.')
                    elif argv[0] == 'git':
                        self.assertTrue('fetch' in argv or 'checkout' in argv)
                    elif argv[0] == 'cmd.exe':
                        (kwargs['cwd'] / 'vcpkg.exe').write_bytes(b'Inert retained supplier.')
                    else:
                        actions.append(argv[1]); self.assertEqual(argv[1], 'install')
                        self.assertNotIn('--only-downloads', argv)
                        self.assertNotIn('--no-downloads', argv)
                        self.assertEqual(kwargs['env']['X_VCPKG_ASSET_SOURCES'], 'clear')
                        self.assertEqual(kwargs['env']['VCPKG_BINARY_SOURCES'], 'clear')
                        self.assertEqual(kwargs['env']['VCPKG_MAX_CONCURRENCY'], '3')
                        downloads = Path(kwargs['env']['VCPKG_DOWNLOADS'])
                        (downloads / 'late-build-tool.tar').write_bytes(b'Available only during full installation.')
                        installed = kwargs['cwd'] / 'installed'; installed.mkdir()
                        (installed / 'discarded.lib').write_bytes(b'Not retained as build evidence.')
                        if fail: raise subprocess.CalledProcessError(1, argv)
                with patch('sdk_windows.host_provenance', return_value=(recipe, provenance)), \
                     patch('sdk_windows.subprocess.check_output', return_value=recipe['vcpkg_ref'] + '\n'), \
                     patch('sdk_windows.subprocess.run', side_effect=runner):
                    if fail:
                        with self.assertRaises(subprocess.CalledProcessError):
                            sdk_windows.fetch(recipe_path, root / 'producer.json', root / 'cache', jobs=3)
                        self.assertFalse((root / 'cache').exists())
                    else:
                        result = sdk_windows.fetch(recipe_path, root / 'producer.json', root / 'cache', jobs=3)
                        self.assertIn('downloads/late-build-tool.tar', result['files'])
                        sdk_windows.verify_inputs(recipe_path, root / 'cache')
                        self.assertFalse(any('discarded.lib' in key or key.startswith('installed/') for key in result['files']))
                self.assertEqual(actions, ['install'])

    def test_windows_nonempty_offline_build_replays_retained_inputs(self):
        import sdk_windows, zipfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); recipe_dir = root / 'recipe'; recipe_dir.mkdir()
            templates = Path(__file__).resolve().parents[1] / 'third_party/sdk'
            recipe = read_json(templates / 'windows-base.json'); recipe['ports'] = ['example[core]']
            write_json(recipe_dir / 'windows-base.json', recipe)
            (recipe_dir / 'windows-toolchain.json').write_bytes((templates / 'windows-toolchain.json').read_bytes())
            cache = root / 'cache'; (cache / 'downloads').mkdir(parents=True)
            with zipfile.ZipFile(cache / 'vcpkg-source.zip', 'w') as output:
                output.comment = recipe['vcpkg_ref'].encode(); output.writestr('LICENSE.txt', 'Supplier fixture terms.')
            (cache / 'vcpkg.exe').write_bytes(b'Retained inert supplier executable.')
            (cache / 'downloads/source.tar').write_bytes(b'Retained source fixture.')
            write_json(cache / 'inputs.json', {'schema_version': 1, 'recipe_id': sdk_windows.recipe_identity(recipe_dir / 'windows-base.json'), 'files': file_inventory(cache)})
            provenance = dict(recipe, linker_version='14.44.35217.0', windows_sdk='10.0.22621.0', tools_version='14.44.35217', installation_path=str(root))
            write_json(root / 'producer.json', provenance); actions = []
            def runner(argv, **kwargs):
                actions.append(argv[1]); self.assertEqual(kwargs['env']['X_VCPKG_ASSET_SOURCES'], 'clear;x-block-origin')
                self.assertIn('--overlay-triplets=', ' '.join(argv))
                if argv[1] == 'install': self.assertIn('--no-downloads', argv)
                elif argv[1] == 'export':
                    self.assertIn('example:x64-windows-static', argv)
                    self.assertNotIn('example[core]:x64-windows-static', argv)
                    output = Path(next(arg.split('=', 1)[1] for arg in argv if arg.startswith('--output-dir='))) / 'prepared'
                    for name in ('.vcpkg-root', 'scripts/buildsystems/vcpkg.cmake', 'installed/x64-windows-static/share/example/copyright', 'installed/vcpkg/info/example_1_x64-windows-static.list'):
                        target = output / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('fixture')
                else: raise AssertionError('unexpected supplier action')
            with patch('sdk_windows.host_provenance', return_value=(recipe, provenance)), patch('sdk_windows.subprocess.run', side_effect=runner):
                result = sdk_windows.build(recipe_dir / 'windows-base.json', root / 'producer.json', cache, root / 'group')
            self.assertEqual(actions, ['install', 'export'])
            sdk.restore_sources(root / 'group', result['recipe_id'], root / 'restored')
            sdk_windows.verify_inputs(root / 'restored/recipe/windows-base.json', root / 'restored/cache')
            (cache / 'downloads/source.tar').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                sdk_windows.verify_inputs(recipe_dir / 'windows-base.json', cache)

    def test_windows_host_sdk_must_match_pinned_policy(self):
        import sdk_windows
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); recipe = Path(__file__).resolve().parents[1] / 'third_party/sdk/windows-base.json'
            provenance = dict(read_json(recipe), linker_version='14.44.35217.0', windows_sdk='10.0.99999.0')
            write_json(root / 'producer.json', provenance)
            with self.assertRaisesRegex(ValueError, 'pinned host policy'):
                sdk_windows.empty_base(recipe, root / 'producer.json', root / 'group')
            self.assertFalse((root / 'group').exists())


class NativeLinuxToolchainTests(unittest.TestCase):

    def test_exact_host_compatibility_alias_is_omitted_without_target_changes(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); host = root / 'host'
            (host / 'bin').mkdir(parents=True); (host / 'lib').mkdir()
            (host / 'bin/compiler').write_bytes(b'compiler input')
            (host / 'lib/support').write_bytes(b'host support')
            target = host / 'target/sysroot/usr/include'; target.mkdir(parents=True)
            (target / 'header.h').write_bytes(b'target header')
            # Exact Buildroot2026.08 package/skeleton/skeleton.mk host aliases.
            (host / 'usr').symlink_to('.'); (host / 'lib64').symlink_to('lib')
            with self.assertRaisesRegex(ValueError, 'directory link cycle'):
                sdk.materialize(host, root / 'before')
            distro_sdk.remove_host_compatibility_alias(host)
            distro_sdk.remove_host_compatibility_alias(host)
            sdk.materialize(host, root / 'after')
            self.assertFalse((host / 'usr').exists()); self.assertFalse((host / 'usr').is_symlink())
            self.assertTrue((host / 'target/sysroot/usr').is_dir())
            self.assertEqual((root / 'after/target/sysroot/usr/include/header.h').read_bytes(), b'target header')
            self.assertEqual((root / 'after/bin/compiler').read_bytes(), b'compiler input')
            self.assertEqual((root / 'after/lib64/support').read_bytes(), b'host support')
            self.assertFalse((root / 'after/lib64').is_symlink())

    def test_host_compatibility_alias_rejects_variations_and_replacements(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); host = root / 'host'; (host / 'lib').mkdir(parents=True)
            (host / 'lib/support').write_bytes(b'preserve')
            alias = host / 'usr'
            for value in ('..', './', str(host.resolve()), 'lib', 'missing'):
                with self.subTest(target=value):
                    alias.symlink_to(value)
                    with self.assertRaisesRegex(ValueError, 'alias target: usr'):
                        distro_sdk.remove_host_compatibility_alias(host)
                    self.assertTrue(alias.is_symlink()); self.assertEqual(os.readlink(alias), value)
                    self.assertEqual((host / 'lib/support').read_bytes(), b'preserve'); alias.unlink()
            alias.write_bytes(b'preserve ordinary file')
            with self.assertRaisesRegex(ValueError, 'alias entry: usr'):
                distro_sdk.remove_host_compatibility_alias(host)
            self.assertEqual(alias.read_bytes(), b'preserve ordinary file'); alias.unlink(); alias.mkdir()
            (alias / 'child').write_bytes(b'preserve directory')
            with self.assertRaisesRegex(ValueError, 'alias entry: usr'):
                distro_sdk.remove_host_compatibility_alias(host)
            self.assertEqual((alias / 'child').read_bytes(), b'preserve directory')
            redirected = root / 'redirected'; redirected.symlink_to('host')
            with self.assertRaisesRegex(ValueError, 'host root'):
                distro_sdk.remove_host_compatibility_alias(redirected)

    def test_other_host_or_target_directory_cycles_still_fail(self):
        import distro_sdk
        for name, target in (('lib/unrelated', '..'), ('target/sysroot/usr', '.')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); host = root / 'host'; (host / 'lib').mkdir(parents=True)
                (host / 'target/sysroot').mkdir(parents=True); (host / 'usr').symlink_to('.')
                other = host / name; other.symlink_to(target)
                distro_sdk.remove_host_compatibility_alias(host)
                with self.assertRaisesRegex(ValueError, 'directory link cycle'):
                    sdk.materialize(host, root / 'copy')
                self.assertTrue(other.is_symlink()); self.assertEqual(os.readlink(other), target)

    def runtime_projection_fixture(self, root):
        import distro_sdk
        tree = root / 'sdk'; sysroot = tree / 'sysroot'
        for name in distro_sdk.GLIBC_TARGET_PROGRAMS:
            path = sysroot / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'retained target program')
        for name in distro_sdk.GLIBC_TARGET_DIRECTORIES:
            path = sysroot / name; path.mkdir(parents=True, exist_ok=True)
            (path / 'module').write_bytes(b'target runtime module')
        keep = ('bin/iconv', 'bin/c++', 'sysroot/usr/bin/fltk-config', 'sysroot/usr/bin/sdl2-config',
                'sysroot/usr/bin/unrelated', 'sysroot/usr/include/iconv.h', 'sysroot/usr/lib/libmvec.so.1',
                'sysroot/usr/lib/gconv-extra/keep', 'sysroot/usr/libexec/getconf-extra/keep')
        for name in keep:
            path = tree / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('preserve ' + name).encode())
        relocations = tree / 'share/buildroot/sdk-relocs'; relocations.parent.mkdir(parents=True)
        relocations.write_text('./sysroot/usr/bin/fltk-config\n./sysroot/usr/lib/gconv/module\n./bin/c++\n')
        return tree, {name: (tree / name).read_bytes() for name in keep}

    def test_exact_target_runtime_projection_preserves_compiler_inputs(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            tree, keep = self.runtime_projection_fixture(Path(temporary))
            report = distro_sdk.omit_target_runtime(tree, 'sysroot', distro_sdk.GLIBC_RUNTIME_SOURCE)
            expected = ['sysroot/' + name for name in distro_sdk.GLIBC_TARGET_PROGRAMS + distro_sdk.GLIBC_TARGET_DIRECTORIES]
            self.assertEqual(sorted(expected), report['paths'])
            for name in expected: self.assertFalse((tree / name).exists(), name)
            for name, content in keep.items(): self.assertEqual(content, (tree / name).read_bytes(), name)
            self.assertEqual('./sysroot/usr/bin/fltk-config\n./bin/c++\n', (tree / 'share/buildroot/sdk-relocs').read_text())
            self.assertEqual([], distro_sdk.omit_target_runtime(tree, 'sysroot', distro_sdk.GLIBC_RUNTIME_SOURCE)['paths'])

    def test_runtime_projection_rejects_changed_source_before_removal(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            tree, _ = self.runtime_projection_fixture(Path(temporary)); before = file_inventory(tree)
            with self.assertRaisesRegex(ValueError, 'reviewed glibc source'):
                distro_sdk.omit_target_runtime(tree, 'sysroot', '0' * 64)
            self.assertEqual(before, file_inventory(tree))

    def test_runtime_projection_rejects_unexpected_entries_before_removal(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            tree, _ = self.runtime_projection_fixture(Path(temporary))
            bad = tree / 'sysroot/usr/lib/gconv/module'; bad.unlink(); bad.symlink_to('../../include/iconv.h')
            with self.assertRaisesRegex(ValueError, 'unsupported entry'):
                distro_sdk.omit_target_runtime(tree, 'sysroot', distro_sdk.GLIBC_RUNTIME_SOURCE)
            self.assertTrue((tree / 'sysroot/usr/bin/iconv').is_file()); self.assertTrue(bad.is_symlink())
            bad.unlink(); bad.write_bytes(b'ordinary')
            relocations = tree / 'share/buildroot/sdk-relocs'; relocations.write_text('./../outside\n')
            before = file_inventory(tree)
            with self.assertRaisesRegex(ValueError, 'relative path'):
                distro_sdk.omit_target_runtime(tree, 'sysroot', distro_sdk.GLIBC_RUNTIME_SOURCE)
            self.assertEqual(before, file_inventory(tree))

    def test_target_os_aliases_do_not_obstruct_retained_sdk_materialization(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); supplier = root / 'supplier'; sysroot = supplier / 'sysroot'
            (sysroot / 'etc').mkdir(parents=True); (sysroot / 'usr/include').mkdir(parents=True)
            (sysroot / 'usr/include/example.h').write_bytes(b'/* compiler input */')
            (sysroot / 'usr/include/alias.h').symlink_to('example.h')
            (sysroot / 'etc/mtab').symlink_to('../proc/self/mounts')
            (sysroot / 'etc/resolv.conf').symlink_to('../run/resolv.conf')
            # These exact links exist in the pinned supplier skeleton. Runtime
            # service directories are absent from the compiler-only sysroot.
            with self.assertRaises(FileNotFoundError): sdk.materialize(supplier, root / 'before')
            distro_sdk.remove_runtime_aliases(sysroot)
            distro_sdk.remove_runtime_aliases(sysroot)
            sdk.materialize(supplier, root / 'after')
            self.assertEqual((root / 'after/sysroot/usr/include/alias.h').read_bytes(), b'/* compiler input */')
            self.assertFalse((root / 'after/sysroot/usr/include/alias.h').is_symlink())
            self.assertFalse((sysroot / 'etc/mtab').is_symlink())
            self.assertFalse((sysroot / 'etc/resolv.conf').is_symlink())

    def test_changed_runtime_aliases_are_rejected_before_any_removal(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            sysroot = Path(temporary); (sysroot / 'etc').mkdir()
            known = sysroot / 'etc/mtab'; known.symlink_to('../proc/self/mounts')
            changed = sysroot / 'etc/resolv.conf'; changed.symlink_to('../usr/include/important.h')
            with self.assertRaisesRegex(ValueError, 'unexpected runtime alias target'):
                distro_sdk.remove_runtime_aliases(sysroot)
            self.assertTrue(known.is_symlink()); self.assertTrue(changed.is_symlink())
            changed.unlink(); changed.write_bytes(b'real retained input')
            with self.assertRaisesRegex(ValueError, 'unexpected runtime alias entry'):
                distro_sdk.remove_runtime_aliases(sysroot)
            self.assertTrue(known.is_symlink()); self.assertEqual(changed.read_bytes(), b'real retained input')

    def test_other_broken_or_escaping_supplier_aliases_remain_rejected(self):
        import distro_sdk
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); supplier = root / 'supplier'; sysroot = supplier / 'sysroot'
            (sysroot / 'etc').mkdir(parents=True)
            other = sysroot / 'etc/other'; other.symlink_to('../proc/other')
            distro_sdk.remove_runtime_aliases(sysroot)
            with self.assertRaises(FileNotFoundError): sdk.materialize(supplier, root / 'broken')
            self.assertTrue(other.is_symlink())
            outside = root / 'outside'; outside.write_bytes(b'not a supplier input')
            other.unlink(); other.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'escapes'): sdk.materialize(supplier, root / 'escaped')
            self.assertEqual(outside.read_bytes(), b'not a supplier input')


    def make_sdk(self, root, c=True):
        import platform, shlex, shutil
        tree = root / 'sdk'; (tree / 'bin').mkdir(parents=True); (tree / 'sysroot').mkdir()
        for name, program in (('cc', 'cc'), ('c++', 'c++')):
            compiler = shutil.which(program)
            if not compiler: raise ValueError('native compiler fixture requires ' + program)
            path = tree / 'bin' / name
            path.write_text('#!/bin/sh\nexec ' + shlex.quote(compiler) + ' "$@"\n'); path.chmod(0o755)
        target = {'system':'Linux','processor':platform.machine(),'triple':platform.machine()+'-linux-gnu',
                  'sysroot':'sysroot','cxx_compiler':'bin/c++'}
        if c: target['c_compiler'] = 'bin/cc'
        write_json(tree / 'sdk.json', {'schema_version':1,'recipe_id':'a'*64,'kind':'diagnostic',
                   'target':target,'files':file_inventory(tree)})
        return tree

    def configure(self, source, build, sdk_root, extra=()):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        command = ['cmake','-S',str(source),'-B',str(build),'-G','Ninja',
                   '-DCMAKE_TOOLCHAIN_FILE='+str(root/'cmake/toolchains/sdk.cmake'),
                   '-DFOUNDATION_SDK_ROOT='+str(sdk_root),'-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY',*extra]
        return subprocess.run(command,text=True,capture_output=True)

    def test_declared_c_compiler_is_used_in_nested_checks_and_build(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);sdk_root=self.make_sdk(root);source=root/'source';source.mkdir();build=root/'build'
            (source/'probe.c').write_text('int probe(void) { return 0; }\n')
            (source/'probe.cpp').write_text('int value() { return 0; }\n')
            (source/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.24)\nproject(CompilerProbe LANGUAGES C CXX)\ntry_compile(CHECK_C "${CMAKE_BINARY_DIR}/nested" SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/probe.c")\nif(NOT CHECK_C)\n message(FATAL_ERROR "nested retained C compiler check failed")\nendif()\nadd_library(c_probe STATIC probe.c)\nadd_library(cxx_probe STATIC probe.cpp)\nfile(WRITE "${CMAKE_BINARY_DIR}/selected-c.txt" "${CMAKE_C_COMPILER}")\n')
            result=self.configure(source,build,sdk_root)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((build/'selected-c.txt').read_text(),str(sdk_root/'bin/cc'))
            result=subprocess.run(['cmake','--build',str(build),'--parallel','2'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            verify_sdk(sdk_root)

    def test_legacy_cxx_manifest_cannot_fall_back_to_host_c(self):
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);sdk_root=self.make_sdk(root,c=False);source=root/'source';source.mkdir()
            cmake=source/'CMakeLists.txt';cmake.write_text('cmake_minimum_required(VERSION 3.24)\nproject(CompilerProbe LANGUAGES CXX)\n')
            result=self.configure(source,root/'cxx-build',sdk_root)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            cmake.write_text(cmake.read_text()+'enable_language(C)\n')
            result=self.configure(source,root/'c-build',sdk_root,('-DCMAKE_C_COMPILER='+shutil.which('cc'),))
            self.assertNotEqual(result.returncode,0)
            self.assertIn('SDK-manifest-does-not-declare-a-C-compiler',result.stdout+result.stderr)
            verify_sdk(sdk_root)

if __name__ == '__main__': unittest.main()
