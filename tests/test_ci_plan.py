import importlib.util
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
import json
import sys
import copy
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ci_plan", Path(__file__).resolve().parents[1] / "tools/ci_plan.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class CiPlanTests(unittest.TestCase):
    def test_default_disjoint_source_scopes_and_independent_producers(self):
        plan = ci.plan()
        checks = plan["checks"]["include"]
        self.assertEqual(len(checks), 9)
        self.assertEqual(len({(x["target"], x["scope"]) for x in checks}), 9)
        self.assertEqual(len(plan["packages"]["include"]), 3)

    def test_focused_selection_does_not_masquerade_as_full(self):
        checks = ci.plan(True, False)["checks"]["include"]
        self.assertEqual({x["scope"] for x in checks}, {"core"})
        self.assertEqual(len(checks), 2)

    def test_optional_runner_requires_explicit_configuration_and_does_not_move_arm(self):
        with self.assertRaises(ValueError):
            ci.plan(pool="faster")
        with self.assertRaises(ValueError):
            ci.plan(pool="faster", configured="self-hosted")
        result = ci.plan(pool="faster", configured="foundation-linux-large")["packages"]["include"]
        self.assertEqual({x["target"]: x["runner"] for x in result}["linux-aarch64"], "ubuntu-24.04-arm")

    def test_actual_architecture_is_checked(self):
        with patch.object(ci.platform, "machine", return_value="ARM64"), patch.object(ci.platform, "system", return_value="Linux"):
            ci.assert_host("linux-aarch64")
            with self.assertRaises(ValueError):
                ci.assert_host("linux-x86_64")

    def test_empty_or_duplicate_archive_inputs_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                ci.archives(root)
            for name in ("a", "b"):
                (root / name).mkdir()
                (root / name / "same.zip").touch()
            with self.assertRaises(ValueError):
                ci.archives(root)

    def test_cpack_private_duplicates_are_not_deliverables(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'app.zip').write_bytes(b'archive')
            (root / '_CPack_Packages').mkdir()
            (root / '_CPack_Packages/app.zip').write_bytes(b'archive')
            self.assertEqual(ci.archives(root, recursive=False), [root / 'app.zip'])
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                ci.archives(root)

    def test_release_matrix_requires_every_exact_target_recipe(self):
        recipes = {key: 'a' * 64 for key in ci.STANDARD}
        self.assertEqual({x['target'] for x in ci.release_matrix(recipes)['include']}, set(ci.STANDARD))
        for malformed in ({}, {'linux-x86_64': 'a' * 64}, dict(recipes, unknown='b' * 64), dict(recipes, **{'linux-x86_64': 'latest'})):
            with self.assertRaises(ValueError): ci.release_matrix(malformed)

    def test_gui_publication_preflight_preserves_unresolved_supplier_terms(self):
        recipes = {key: 'a' * 64 for key in (*ci.STANDARD, 'browser-wasm32')}
        policy=ci.module('coverage').load(ci.ROOT/'docs/release-policy.json')
        modules={name:ci.module(name) for name in ('coverage','certify_release')}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'third_party').mkdir()
            (root/'third_party/gui-boundary.lock.json').write_text('{"redistribution":{"approved":false}}')
            with patch.object(ci,'ROOT',root),patch.object(ci,'module',side_effect=modules.__getitem__),self.assertRaisesRegex(ValueError,'licensing'):
                ci.release_matrix(recipes,'all-gui',policy)

    def test_complete_commit_required(self):
        self.assertEqual(ci.exact_commit('b' * 40), 'b' * 40)
        for text in ('main', 'HEAD', 'abc123', 'a' * 41, 'B' * 40):
            with self.assertRaises(ValueError): ci.exact_commit(text)


    def test_authorized_faster_arm_and_windows_are_independent(self):
        selected=ci.plan(pool='faster',configured_arm='foundation-arm-large',configured_windows='foundation-windows-large')
        values={row['target']:row['runner'] for row in selected['packages']['include']}
        self.assertEqual(values['linux-x86_64'],'ubuntu-24.04')
        self.assertEqual(values['linux-aarch64'],'foundation-arm-large')
        self.assertEqual(values['windows-x86_64'],'foundation-windows-large')
        for invalid in ('self-hosted','foundation-linux-large','unsafe label'):
            with self.assertRaises(ValueError):ci.plan(pool='faster',configured_windows=invalid)

    def test_validator_never_downloads_an_implicit_supplier(self):
        with tempfile.TemporaryDirectory() as temporary, patch('shutil.which',return_value=None), patch('urllib.request.build_opener') as request:
            with self.assertRaisesRegex(ValueError,'HTTPS'):
                ci.workflow_lint(Path(temporary)/'lint')
            request.assert_not_called()
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);tool=root/'actionlint';tool.write_bytes(b'fixture')
            with patch.object(ci.subprocess,'run',return_value=CompletedProcess([],0,'1.7.12\n')) as run, patch('urllib.request.build_opener') as request:
                result=ci.workflow_lint(root/'lint',executable=str(tool))
                self.assertEqual(result['origin'],'installed');self.assertTrue(result['workflows']);request.assert_not_called()
                self.assertIn('-shellcheck=',run.call_args.args[0])


    def test_retained_validator_rejects_bad_identity_and_insecure_redirect(self):
        import io,urllib.request
        with tempfile.TemporaryDirectory() as temporary, patch('shutil.which',return_value=None):
            output=Path(temporary)/'lint'
            with patch('urllib.request.build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(b'wrong archive')
                with self.assertRaisesRegex(ValueError,'pinned identity'):
                    ci.workflow_lint(output,retained_url='https://example.invalid/retained.tar.gz')
                self.assertFalse(output.exists())
            def redirect(handler):
                request=urllib.request.Request('https://example.invalid/archive')
                handler.redirect_request(request,None,302,'moved',{},'http://example.invalid/archive')
            with patch('urllib.request.build_opener',side_effect=redirect):
                with self.assertRaisesRegex(ValueError,'transfer failed'):
                    ci.workflow_lint(output,retained_url='https://example.invalid/archive')
                self.assertFalse(output.exists())

    def test_validator_changed_inputs_cannot_emit_success(self):
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);tool=root/'actionlint';tool.write_bytes(b'fixture')
            def run(argv,**unused):
                if '-version' not in argv: tool.write_bytes(b'changed')
                return CompletedProcess(argv,0,'1.7.12\n')
            with patch.object(ci.subprocess,'run',side_effect=run):
                with self.assertRaisesRegex(ValueError,'changed during'):
                    ci.workflow_lint(root/'lint',executable=str(tool))
            self.assertFalse((root/'lint/qualification.json').exists())


class PortableProducerAssemblyTests(unittest.TestCase):
    def setUp(self):
        import shutil,zipfile
        from test_release import ReleaseTests
        from unittest.mock import Mock
        self.fixture=ReleaseTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        f=self.fixture;self.root=f.root;self.source=Path(f.spec['source']['path'])
        # Inert archive contents exercise transfer/assembly, not target execution.
        produced=self.root/'producer output';produced.mkdir()
        archive=produced/'windows-x86_64.zip'
        with zipfile.ZipFile(archive,'w') as bundle:
            bundle.writestr('application/bin/foundation-cli.exe',b'inert Windows archive fixture')
            info=(self.root/'application/build-info.txt').read_text().replace('target=linux-x86_64','target=windows-x86_64')
            bundle.writestr('application/build-info.txt',info)
        descriptor=archive.with_name(archive.name+'.json')
        descriptor.write_text(json.dumps(ci.module('artifact').describe(archive)))
        self.entry=dict(path=archive.name,manifest_path=descriptor.name,sha256=ci.module('coverage').sha(archive),
                        target='windows-x86_64',backends=[],sdk_recipe=f.recipe,dependency_recipes=[f.recipe])
        (produced/'artifact.json').write_text(json.dumps(self.entry))
        self.packages=self.root/'receiver packages';self.packages.mkdir()
        self.received=self.packages/'windows-x86_64';shutil.move(str(produced),self.received)
        self.original=ci.module;policy=Mock()
        policy.requirements.return_value=({'targets':{'windows-x86_64':['core']},'checks':[{'scope':'archive'}]},None)
        self.modules=patch.object(ci,'module',side_effect=lambda name:policy if name=='certify_release' else self.original(name))
        self.modules.start();self.addCleanup(self.modules.stop)

    def test_moved_windows_bundle_assembles_with_portable_names(self):
        output=self.root/'released'
        result=ci.assemble_release(self.source,self.packages,self.fixture.base,output,'fixture')
        self.assertEqual(result['artifacts'][0]['archive'],'windows-x86_64.zip')
        self.assertEqual(result['artifacts'][0]['manifest'],'windows-x86_64.zip.json')
        self.assertEqual((output/'windows-x86_64.zip').read_bytes(),(self.received/'windows-x86_64.zip').read_bytes())
        self.assertEqual(result,ci.module('release').verify_release(output))
        for path_type in (PurePosixPath,PureWindowsPath):
            for field in ('path','manifest_path'):
                self.assertEqual(path_type(self.entry[field]).parts,(self.entry[field],))

    def test_foreign_absolute_and_nested_paths_fail_before_assembly(self):
        bad_names=('/work/output/windows-x86_64.zip',r'D:\a\output\windows-x86_64.zip',
                   r'\\server\share\windows-x86_64.zip',r'folder\windows-x86_64.zip',
                   '../windows-x86_64.zip','nested/windows-x86_64.zip','NUL.zip')
        output=self.root/'rejected'
        for field in ('path','manifest_path'):
            for name in bad_names:
                altered=dict(self.entry);altered[field]=name
                (self.received/'artifact.json').write_text(json.dumps(altered))
                with self.subTest(field=field,name=name),self.assertRaises(ValueError):
                    ci.assemble_release(self.source,self.packages,self.fixture.base,output,'fixture')
                self.assertFalse((self.root/'assembly.json').exists());self.assertFalse(output.exists())


class BrowserPrerequisiteTests(unittest.TestCase):
    def selection(self, target='linux-x86_64', environment='ubuntu-24.04'):
        return ci.browser_prerequisite(target, environment, 'hosted-web')

    def test_only_scopes_executing_browser_assertions_install_prerequisites(self):
        for backend in ('core', 'hosted-web', 'wasm', 'fltk'):
            for scope in ('source', 'recovery', 'archive', 'abi', 'apt'):
                self.assertEqual(ci.needs_browser_prerequisite(backend, scope),
                                 backend == 'hosted-web' and scope == 'archive' or
                                 backend == 'wasm' and scope in ('source', 'recovery', 'archive'))

    def test_distribution_and_engine_selection_is_explicit(self):
        for target, arch in (('linux-x86_64', 'amd64'), ('linux-aarch64', 'arm64')):
            selected = self.selection(target)
            self.assertEqual((selected['image'], selected['architecture'], selected['packages']), ('ubuntu:24.04', arch, ['firefox']))
            self.assertEqual(selected['executable'], '/usr/bin/firefox')
            self.assertEqual(selected['repository'], 'host-preinstalled')
        self.assertEqual(self.selection(environment='debian-12')['packages'], ['firefox-esr'])
        chromium = ci.browser_prerequisite('browser-wasm32', 'chromium', 'wasm')
        self.assertEqual((chromium['image'], chromium['packages']), ('', ['google-chrome', 'chromedriver']))
        self.assertEqual(chromium['repository'], 'host-preinstalled')
        self.assertEqual(chromium['executable'], '/usr/bin/google-chrome')
        for target, environment, backend in (('windows-x86_64', 'ubuntu-24.04', 'hosted-web'),
                ('browser-wasm32', 'ubuntu-24.04', 'wasm'), ('linux-x86_64', 'ubuntu-24.04', 'core')):
            with self.assertRaises(ValueError): ci.browser_prerequisite(target, environment, backend)

    def test_setup_requires_disposable_root_and_actual_distribution_and_architecture(self):
        from contextlib import ExitStack
        from subprocess import CompletedProcess
        with ExitStack() as stack:
            stack.enter_context(patch.object(ci.platform, 'system', return_value='Linux'))
            machine = stack.enter_context(patch.object(ci.platform, 'machine', return_value='x86_64'))
            release = stack.enter_context(patch.object(ci.platform, 'freedesktop_os_release', create=True,
                                                       return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}))
            uid = stack.enter_context(patch.object(ci.os, 'geteuid', create=True, return_value=0))
            marker = stack.enter_context(patch.object(Path, 'is_file', return_value=True))
            launch = stack.enter_context(patch.object(ci.subprocess, 'run', return_value=CompletedProcess([], 0, 'amd64\n')))
            stack.enter_context(patch.dict(ci.os.environ, {'FOUNDATION_DISPOSABLE_CHECK': '1', 'CHECK_IMAGE': 'ubuntu:24.04'}))
            ci.browser_setup_preflight(self.selection())
            for obj, bad, good in ((uid, 1000, 0), (marker, False, True),
                    (release, {'ID': 'debian', 'VERSION_ID': '12'}, {'ID': 'ubuntu', 'VERSION_ID': '24.04'}),
                    (machine, 'aarch64', 'x86_64')):
                launch.reset_mock(); obj.return_value = bad
                with self.assertRaises(ValueError): ci.browser_setup_preflight(self.selection())
                launch.assert_not_called(); obj.return_value = good
            for variable in ('FOUNDATION_DISPOSABLE_CHECK', 'CHECK_IMAGE'):
                with patch.dict(ci.os.environ, {variable: ''}):
                    launch.reset_mock()
                    with self.assertRaises(ValueError): ci.browser_setup_preflight(self.selection())
                    launch.assert_not_called()
            launch.return_value.stdout = 'arm64\n'
            with self.assertRaisesRegex(ValueError, 'package architecture'): ci.browser_setup_preflight(self.selection())

    def test_host_browser_never_installs_or_rewrites_sources(self):
        record = dict(package='firefox', version='Mozilla Firefox 153.4.0', architecture='amd64',
                      policy='native host', executable='/usr/lib/firefox/firefox', files={'/usr/lib/firefox/firefox':'a'*64})
        with tempfile.TemporaryDirectory() as temporary, patch.object(ci, 'inspect_host_firefox', return_value=record) as inspect, \
                patch.object(ci, 'browser_setup_preflight', side_effect=AssertionError('container mutation')), \
                patch.object(ci.subprocess, 'run', side_effect=AssertionError('unexpected installation')):
            output=Path(temporary)/'receipt'
            receipt=ci.install_browser_prerequisite('linux-x86_64','ubuntu-24.04','hosted-web',output)
            self.assertEqual(receipt['installed'],[record]); self.assertIsNone(receipt['signing_key_fingerprint'])
            inspect.assert_called_once_with(self.selection()); self.assertTrue(output.is_dir())
            inspect.side_effect=ValueError('missing browser')
            with self.assertRaisesRegex(ValueError,'missing browser'):
                ci.install_browser_prerequisite('linux-x86_64','ubuntu-24.04','hosted-web',Path(temporary)/'missing')
            self.assertFalse((Path(temporary)/'missing').exists())

    def test_host_browser_requires_real_native_bytes_version_and_architecture(self):
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as temporary:
            binary=Path(temporary)/'firefox'; raw=bytearray(64); raw[:6]=b'\x7fELF\x02\x01';raw[18:20]=(62).to_bytes(2,'little');binary.write_bytes(raw)
            selection=dict(self.selection(),executable=str(binary))
            with patch.object(ci.platform,'system',return_value='Linux'), \
                    patch.object(ci.platform,'freedesktop_os_release',create=True,return_value={'ID':'ubuntu','VERSION_ID':'24.04'}), \
                    patch.object(ci,'assert_host'), patch.object(ci.subprocess,'run',return_value=CompletedProcess([],0,'Mozilla Firefox 153.4.0\n')) as run:
                result=ci.inspect_host_firefox(selection)
                self.assertEqual(result['executable'],str(binary.resolve()))
                self.assertEqual(result['files'],{str(binary.resolve()):ci.module('coverage').sha(binary)})
                raw[18:20]=(183).to_bytes(2,'little');binary.write_bytes(raw);run.reset_mock()
                with self.assertRaisesRegex(ValueError,'architecture'):ci.inspect_host_firefox(selection)
                run.assert_not_called()
                binary.write_bytes(b'#!/bin/sh\nunknown wrapper\n')
                with self.assertRaisesRegex(ValueError,'wrapper'):ci.inspect_host_firefox(selection)

    def test_host_chromium_binds_browser_driver_and_rejects_incompatible_inputs(self):
        from subprocess import CompletedProcess
        selected = ci.browser_prerequisite('browser-wasm32', 'chromium', 'wasm')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); browser = root/'chrome'; driver = root/'chromedriver'
            raw = bytearray(64); raw[:6] = b'\x7fELF\x02\x01'; raw[18:20] = (62).to_bytes(2,'little')
            browser.write_bytes(raw); driver.write_bytes(raw)
            selection = dict(selected, executable=str(browser), driver=str(driver))
            versions = {str(browser): 'Google Chrome 154.0.8037.57', str(driver): 'ChromeDriver 154.0.8037.57 (fixture)'}
            def launch(argv, **kwargs): return CompletedProcess(argv,0,versions[argv[0]])
            with patch.object(ci.platform,'system',return_value='Linux'), \
                    patch.object(ci.platform,'freedesktop_os_release',create=True,return_value={'ID':'ubuntu','VERSION_ID':'24.04'}), \
                    patch.object(ci.os,'geteuid',create=True,return_value=1000) as uid, \
                    patch.object(ci,'assert_host'), patch.object(ci.subprocess,'run',side_effect=launch):
                records = ci.inspect_host_chromium(selection)
                self.assertEqual([r['executable'] for r in records], [str(browser),str(driver)])
                self.assertEqual(records[1]['files'], {str(driver): ci.module('coverage').sha(driver)})
                versions[str(driver)] = 'ChromeDriver 153.0.8037.57 (fixture)'
                with self.assertRaisesRegex(ValueError,'major versions differ'): ci.inspect_host_chromium(selection)
                versions[str(driver)] = 'ChromeDriver 154.0.8037.57 (fixture)'
                raw[18:20] = (183).to_bytes(2,'little'); driver.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'architecture'): ci.inspect_host_chromium(selection)
                driver.write_bytes(b'#!/bin/sh\nunknown wrapper\n')
                with self.assertRaisesRegex(ValueError,'architecture'): ci.inspect_host_chromium(selection)
                raw[18:20] = (62).to_bytes(2,'little'); driver.write_bytes(raw)
                wrapper=root/'google-chrome';wrapper.write_bytes(b'#!/bin/sh\nexec \"$HERE/chrome\" \"$@\"\n')
                selection['executable']=str(wrapper);versions[str(wrapper)]=versions[str(browser)]
                records=ci.inspect_host_chromium(selection)
                self.assertEqual(set(records[0]['files']),{str(wrapper),str(browser)})
                versions[str(wrapper)]='Google Chrome 154.0.8037.58'
                with self.assertRaisesRegex(ValueError,'wrapper and native'):ci.inspect_host_chromium(selection)
                versions[str(wrapper)]=versions[str(browser)];uid.return_value=0
                with self.assertRaisesRegex(ValueError,'unprivileged'):ci.inspect_host_chromium(selection)

    def test_host_chromium_setup_only_inspects_existing_inputs(self):
        records = [dict(package=p,version='Google Chrome 154.0.1.2' if p=='google-chrome' else 'ChromeDriver 154.0.1.2',
                        architecture='amd64',policy='host',executable='/fixture/'+p,files={'/fixture/'+p:'a'*64})
                   for p in ('google-chrome','chromedriver')]
        with tempfile.TemporaryDirectory() as temporary, patch.object(ci,'inspect_host_chromium',return_value=records), \
                patch.object(ci,'browser_setup_preflight',side_effect=AssertionError('no package mutation')), \
                patch.object(ci.subprocess,'run',side_effect=AssertionError('no installation')):
            receipt=ci.install_browser_prerequisite('browser-wasm32','chromium','wasm',Path(temporary)/'receipt')
            self.assertEqual(receipt['installed'],records)
            self.assertEqual(receipt['browser_version'],records[0]['version'])

    def test_lifecycle_receipt_preserves_new_evidence_directory(self):
        helper_spec = importlib.util.spec_from_file_location('ci_lifecycle_fixture', ci.ROOT / '.github/scripts/lifecycle.py')
        helper = importlib.util.module_from_spec(helper_spec); helper_spec.loader.exec_module(helper)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'build').mkdir()
            item = dict(id='ubuntu-check', target='linux-x86_64', environment='ubuntu-24.04', backend='hosted-web', scope='archive')
            frozen = dict(id='plan-id', checks=[item])
            events = []
            def install(*args):
                events.append('setup'); args[-1].mkdir(parents=True)
                return {'schema_version': 1, 'installed': []}
            def run_case(*args):
                events.append('check')
                output = args[3]
                self.assertFalse(output.exists())
                self.assertTrue((root / 'build/prerequisites/ubuntu-check/browser.json').is_file())
                return {'status': 'passed'}
            with patch.object(helper, 'ROOT', root), patch.object(helper.os, 'chdir'), \
                 patch.object(helper.evidence, 'load', return_value=frozen), patch.object(helper.evidence, 'validate'), \
                 patch.object(helper.evidence, 'check_inputs'), patch.object(helper.evidence, 'run_execution', side_effect=run_case), \
                 patch.object(helper.ci.platform, 'system', return_value='Linux'), \
                 patch.object(helper.ci, 'install_browser_prerequisite', side_effect=install), \
                 patch.dict(helper.os.environ, {'CHECK': 'ubuntu-check', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2'}):
                with self.assertRaisesRegex(ValueError, 'browser prerequisite'):
                    helper.main('check')
                self.assertEqual(events, [])
                helper.main('check-prerequisites')
                self.assertEqual(events, ['setup'])
                helper.main('check')
                self.assertEqual(events, ['setup', 'check'])
            receipt = json.loads((root / 'build/prerequisites/ubuntu-check/browser.json').read_text())
            self.assertEqual((receipt['plan'], receipt['check'], receipt['run_id'], receipt['attempt']), ('plan-id', 'ubuntu-check', '123', 2))


class CandidateFetchTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent))
        import test_github_release
        self.fixture = test_github_release.DeliveryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.publish()
        self.remote = self.fixture.remote
        self.root = self.fixture.root
        self.inventory = self.fixture.delivery['inventory_sha256']

    def fetch(self, **changes):
        args = dict(repository='example/project', tag='v1', inventory=self.inventory,
                    output=self.root / 'fetched', transport=self.remote)
        args.update(changes)
        return ci.fetch_candidate(**args)

    def test_fetch_reconstructs_complete_tree_and_never_mutates_remote(self):
        count = len(self.remote.mutations)
        result = self.fetch()
        self.assertEqual(result, self.fixture.delivery)
        self.assertEqual(ci.module('release').verify_release(self.root / 'fetched/candidate'),
                         ci.module('release').verify_release(self.fixture.directory))
        self.assertEqual(len(self.remote.mutations), count)

    def test_metadata_fetch_transfers_no_sdk_or_application_payload_but_checks_every_digest(self):
        self.remote.calls.clear()
        result = self.fetch(metadata_only=True)
        self.assertEqual(result, self.fixture.delivery)
        files = list((self.root / 'fetched/candidate').iterdir())
        self.assertEqual([path.name for path in files], ['release.json'])
        ids = {row['id']: row['name'] for row in self.remote.releases[0]['assets']}
        transferred = [ids[call[1]] for call in self.remote.calls if call[0] == 'download']
        self.assertEqual(set(transferred), {'delivery.json', 'release.json'})
        self.assertFalse(self.remote.mutations)
        sdk = next(row for row in self.remote.releases[0]['assets'] if row['name'].endswith('-binary.tar.gz'))
        sdk['digest'] = 'sha256:' + '0'*64
        with self.assertRaisesRegex(ValueError, 'remote asset differs'):
            self.fetch(metadata_only=True, output=self.root / 'tampered')
        self.assertFalse((self.root / 'tampered').exists())

    def test_complete_fetch_downloads_each_payload_once(self):
        self.remote.calls.clear(); self.fetch()
        counts = {}
        for call in self.remote.calls:
            if call[0] == 'download': counts[call[1]] = counts.get(call[1], 0) + 1
        for row in self.remote.releases[0]['assets']:
            if row['name'] != 'delivery.json': self.assertEqual(counts[row['id']], 1, row['name'])

    def test_retained_builder_capability_is_explicit_and_legacy_groups_remain_complete(self):
        import ast
        import source_identity
        root = self.root / 'builder-source'; (root / 'tools').mkdir(parents=True)
        builder = root / 'tools/build.py'
        builder.write_text("parser.add_argument('--dependency-group')\n")
        legacy = self.root / 'legacy-builder.tar.gz'; source_identity.archive_source(root, legacy)
        self.assertFalse(ci.archived_binary_group_support(self.root, {'source': {'archive': legacy.name}}))
        builder.write_text("parser.add_argument('--binary-dependency-group', action='append')\n")
        modern = self.root / 'modern-builder.tar.gz'; source_identity.archive_source(root, modern)
        self.assertTrue(ci.archived_binary_group_support(self.root, {'source': {'archive': modern.name}}))
        builder.write_text("# --binary-dependency-group\nparser.add_argument('--dependency-group')\n")
        comment = self.root / 'comment-builder.tar.gz'; source_identity.archive_source(root, comment)
        self.assertFalse(ci.archived_binary_group_support(self.root, {'source': {'archive': comment.name}}))
        release = ci.module('release'); metadata = release.verify_release(self.fixture.directory)
        names = release.required_files(metadata, self.fixture.target, 'core', 'source', binary_source=False)
        self.assertTrue(any(name.endswith('-sources.tar.gz') for name in names))

    def test_scope_payload_selection_omits_sdk_sources_except_recovery(self):
        import shutil
        release = ci.module('release'); archive = ci.module('dependency_archive')
        manifest = release.verify_release(self.fixture.directory)
        scope_files = {scope: release.required_files(manifest, self.fixture.target, 'core', scope)
                       for scope in ('archive', 'source', 'recovery')}
        self.assertEqual(set(scope_files['archive']), {manifest['artifacts'][0]['archive'], manifest['artifacts'][0]['manifest']})
        self.assertFalse(any(name.endswith('-sources.tar.gz') for name in scope_files['source']))
        self.assertTrue(any(name.endswith('-sources.tar.gz') for name in scope_files['recovery']))
        for scope, names in scope_files.items():
            destination = self.root / ('sparse-' + scope); destination.mkdir()
            for name in ['release.json', *names]:
                target = destination / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.fixture.directory / name, target)
            self.assertEqual(release.verify_selection(destination, self.fixture.target, 'core', scope), manifest)
            required = destination / manifest['artifacts'][0]['archive']; required.unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                release.verify_selection(destination, self.fixture.target, 'core', scope)

    def test_transport_projects_each_scope_without_repeating_sources_into_binary_bundle(self):
        import shutil, ci_transport
        c = ci.module('coverage'); release = ci.module('release')
        policy = {'schema_version': 1, 'profiles': {'fixture': {'description': 'transport fixture',
            'targets': {self.fixture.target: ['core']}, 'checks': [dict(target=self.fixture.target,
                backend='core', environment='debian-12', scope=scope) for scope in ('source', 'archive', 'recovery')]}}}
        plan_path = self.root / 'projection-plan.json'
        ci.qualification_plan(self.fixture.directory, 'fixture', plan_path, policy)
        plan = c.load(plan_path); destination = self.root / 'transport-checkout'
        for name in plan['inputs']:
            if name.startswith('build/candidate/'): continue
            target = destination / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ci.ROOT / name, target)
        shutil.copytree(self.fixture.directory, destination / 'build/candidate')
        (destination / 'build/check-plan.json').write_text(json.dumps(plan))
        spec = importlib.util.spec_from_file_location('projected_lifecycle', ci.ROOT / '.github/scripts/lifecycle.py')
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        payloads = {}
        def publish(**options):
            payloads[options['name']] = {name: (options['root'] / name).read_bytes() for name in options['paths']}
        with patch.object(helper, 'ROOT', destination), patch.object(helper, 'storage_context', return_value={}), \
                patch.dict(helper.os.environ, GITHUB_RUN_ATTEMPT='1', RUNNER_NAME='fixture-runner'), \
                patch.object(ci_transport, 'publish_bundle', side_effect=publish):
            helper.qualification_payloads()
        self.assertEqual(len(payloads), 4)  # source, target, SDK binary pair, SDK sources
        binary = payloads['qualification-sdk-0-1']; sources = payloads['qualification-sdk-source-0-1']
        self.assertEqual(len(binary), 2); self.assertEqual(len(sources), 1)
        self.assertFalse(any(name.endswith('-sources.tar.gz') for name in binary))
        self.assertTrue(all(name.endswith('-sources.tar.gz') for name in sources))
        manifest = release.verify_release(destination / 'build/candidate')
        for scope in ('archive', 'source', 'recovery'):
            for name in manifest['files']: (destination / 'build/candidate' / name).unlink(missing_ok=True)
            for directory in sorted((destination / 'build/candidate').rglob('*'), reverse=True):
                if directory.is_dir(): directory.rmdir()
            batch = next(row for row in ci.qualification_batches(plan)['include'] if
                         next(item for item in c.executions(plan) if item['id'] in row['checks'])['scope'] == scope)
            fetched = []
            def restore(name, output, **options):
                fetched.append(name)
                for relative, content in payloads[name].items():
                    path = Path(output) / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            with patch.object(helper, 'ROOT', destination), \
                    patch.dict(helper.os.environ, GITHUB_RUN_ATTEMPT='1', BATCH=batch['id']), \
                    patch.object(helper, 'fetch_bundle', side_effect=restore):
                helper.fetch_check_payloads()
            actual = {path.relative_to(destination / 'build/candidate').as_posix() for path in (destination / 'build/candidate').rglob('*') if path.is_file()}
            expected = {'release.json', *release.required_files(manifest, self.fixture.target, 'core', scope)}
            self.assertEqual(actual, expected)
            self.assertEqual('qualification-sdk-source-0-1' in fetched, scope == 'recovery')
            self.assertEqual('qualification-sdk-0-1' in fetched, scope != 'archive')

    def test_sparse_execution_inputs_reject_omitted_inventory_and_changed_selected_bytes(self):
        import shutil
        c = ci.module('coverage'); release = ci.module('release')
        policy = {'schema_version': 1, 'profiles': {'fixture': {'description': 'scope fixture',
            'targets': {self.fixture.target: ['core']},
            'checks': [dict(target=self.fixture.target, backend='core', environment='debian-12', scope=scope) for scope in ('source', 'archive', 'recovery')]}}}
        frozen_path = self.root / 'scope-plan.json'
        ci.qualification_plan(self.fixture.directory, 'fixture', frozen_path, policy)
        plan = c.load(frozen_path); item = next(row for row in c.executions(plan) if row['scope'] == 'archive')
        destination = self.root / 'scoped-checkout'
        for name in plan['inputs']:
            if name.startswith('build/candidate/'): continue
            target = destination / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ci.ROOT / name, target)
        manifest = release.verify_release(self.fixture.directory)
        for name in ['release.json', *release.required_files(manifest, item['target'], item['backend'], item['scope'])]:
            target = destination / 'build/candidate' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(self.fixture.directory / name, target)
        c.check_inputs(plan, destination, check_ids=[item['id']])
        c.check_inputs(plan, destination, metadata_only=True)
        broken = copy.deepcopy(plan); broken.pop('id'); omitted = next(name for name in broken['inputs'] if name.endswith('-sources.tar.gz')); broken['inputs'].pop(omitted)
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            c.check_inputs(c.freeze(broken), destination, check_ids=[item['id']])
        with self.assertRaisesRegex(ValueError, 'unknown'):
            c.check_inputs(plan, destination, check_ids=['absent'])
        (destination / 'build/candidate' / manifest['artifacts'][0]['archive']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'check input changed'):
            c.check_inputs(plan, destination, check_ids=[item['id']])

    def test_wrong_inventory_does_not_publish_local_destination(self):
        with self.assertRaisesRegex(ValueError, 'identity'): self.fetch(inventory='b' * 64)
        self.assertFalse((self.root / 'fetched').exists())

    def test_changed_asset_during_fetch_is_rejected(self):
        self.remote.change_download = lambda: self.remote.replace_asset('delivery.json')
        with self.assertRaisesRegex(ValueError, 'identities changed'): self.fetch()
        self.assertFalse((self.root / 'fetched').exists())

    def test_untrusted_descriptor_cannot_write_outside_destination(self):
        altered = copy.deepcopy(self.fixture.delivery)
        altered['files']['../escape'] = altered['files'].pop('release.json')
        self.remote.replace_asset('delivery.json', ci.module('github_release').archive.encoded(altered))
        with self.assertRaises(ValueError): self.fetch()
        self.assertFalse((self.root / 'escape').exists())


    def test_prepared_producer_uses_one_build_and_retains_matching_inventory(self):
        import shutil
        from unittest.mock import Mock
        original = ci.module
        sdk = Mock()
        artifacts = original('artifact')
        fake_artifact = Mock(describe=artifacts.describe)
        def selected(name):
            if name == 'sdk': return sdk
            if name == 'artifact': return fake_artifact
            return original(name)
        produced = self.root / 'produced'
        archive = self.fixture.directory / ci.module('release').verify_release(self.fixture.directory)['artifacts'][0]['archive']
        commands = []
        def launch(argv, **kwargs):
            commands.append(argv)
            if argv[2] == 'package':
                destination = produced / 'work/build/packages'
                destination.mkdir(parents=True)
                shutil.copyfile(archive, destination / 'application.tar.gz')
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), patch.object(ci.subprocess, 'run', side_effect=launch):
            entry = ci.prepared_package('linux-x86_64', self.fixture.fixture.recipe, self.fixture.root / 'group',
                    self.fixture.directory / ci.module('release').verify_release(self.fixture.directory)['source']['archive'], produced, 2)
        self.assertEqual([x[2] for x in commands], ['test', 'package'])
        self.assertIn('--full', commands[0]); self.assertNotIn('--full', commands[1])
        self.assertNotIn('--junit', commands[1])
        self.assertEqual(entry['path'], 'linux-x86_64.tar.gz')
        self.assertEqual(entry['manifest_path'], 'linux-x86_64.tar.gz.json')
        self.assertEqual(entry['sdk_recipe'], self.fixture.fixture.recipe)
        self.assertEqual(entry['dependency_recipes'], [self.fixture.fixture.recipe])
        self.assertTrue((produced / 'artifact.json').is_file())
        sdk.install.assert_called_once()
        fake_artifact.verify.assert_called_once()

    def test_policy_derived_plan_binds_inputs_and_every_required_scope(self):
        target = self.fixture.target
        rows = [dict(target=target, backend='core', environment='fixture', scope=scope) for scope in ('source', 'archive', 'recovery')]
        policy = {'schema_version': 1, 'profiles': {'fixture': {'description': 'fixture inventory', 'targets': {target: ['core']}, 'checks': rows}}}
        output = self.root / 'check-plan.json'
        matrix = ci.qualification_plan(self.fixture.directory, 'fixture', output, policy)
        plan = json.loads(output.read_text())
        self.assertEqual(len(matrix['include']), 3)
        self.assertEqual({x['scope'] for x in plan['checks']}, {'source', 'archive', 'recovery'})
        self.assertTrue(all(x['required'] and x['qualification'] == 'qualification.json' for x in plan['checks']))
        self.assertEqual(plan['subject']['inventory_sha256'], self.inventory)
        self.assertIn('tools/release_check.py', plan['inputs'])
        self.assertIn('build/candidate/release.json', plan['inputs'])

    def test_ubuntu_check_uses_explicit_real_firefox_and_binds_setup_inputs(self):
        from unittest.mock import Mock
        target = 'linux-x86_64'
        policy = {'schema_version': 1, 'profiles': {'fixture': {'description': 'fixture browser',
                  'targets': {target: ['hosted-web']}, 'checks': [dict(target=target, backend='hosted-web',
                  environment='ubuntu-24.04', scope=scope) for scope in ('source', 'archive', 'recovery')]}}}
        original = ci.module
        release = Mock(verify_release=Mock(return_value=dict(original('release').verify_release(self.fixture.directory))))
        release.dependency_recipes = original('release').dependency_recipes
        release.verify_release.return_value['artifacts'][0]['target'] = target
        release.verify_release.return_value['artifacts'][0]['backends'] = ['hosted-web']
        with patch.object(ci, 'module', side_effect=lambda name: release if name == 'release' else original(name)):
            output = self.root / 'browser-plan.json'
            matrix = ci.qualification_plan(self.fixture.directory, 'fixture', output, policy)
        frozen = json.loads(output.read_text())
        self.assertEqual(matrix['include'][0]['image'], 'ubuntu:24.04')
        self.assertEqual(next(x for x in matrix['include'] if x['scope']=='archive')['image'], '')
        archive = next(item for item in frozen['checks'] if item['scope'] == 'archive')
        self.assertIn('/usr/bin/firefox', archive['argv'])
        self.assertIn('--browser-prerequisite-plan', archive['argv'])
        self.assertIn('{root}/build/check-plan.json', archive['argv'])
        self.assertIn('.github/scripts/lifecycle.py', frozen['inputs'])
        self.assertIn('.github/workflows/certify.yml', frozen['inputs'])
        for case in frozen['checks']:
            self.assertEqual('--browser-prerequisite' in case['argv'], case['scope'] == 'archive')


    def test_all_gui_groups_preserve_106_requirements_with_66_executions(self):
        from unittest.mock import Mock
        original=ci.module;manifest=original('release').verify_release(self.fixture.directory)
        policy=json.loads((ci.ROOT/'docs/release-policy.json').read_text())
        manifest['artifacts']=[dict(manifest['artifacts'][0],target=target,backends=backends) for target,backends in policy['profiles']['all-gui']['targets'].items()]
        release=Mock(verify_release=Mock(return_value=manifest))
        release.dependency_recipes = original('release').dependency_recipes
        with patch.object(ci,'module',side_effect=lambda name:release if name=='release' else original(name)):
            output=self.root/'all-gui-plan.json';matrix=ci.qualification_plan(self.fixture.directory,'all-gui',output,policy)
        frozen=json.loads(output.read_text());self.assertEqual(len(frozen['checks']),106);self.assertEqual(len(matrix['include']),66)
        batches = ci.qualification_batches(frozen)['include']
        self.assertEqual(len(batches), 23)
        self.assertEqual(sorted(check for batch in batches for check in batch['checks']),
                         sorted(row['id'] for row in matrix['include']))
        self.assertTrue(all(len({by['scope'] for by in original('coverage').executions(frozen) if by['id'] in batch['checks']}) == 1 for batch in batches))
        self.assertTrue(all(len(batch['checks']) <= 16 for batch in batches))
        self.assertEqual(sum(batch['browser'] for batch in batches), 10)
        self.assertEqual(sum(batch['graphics'] for batch in batches), 3)
        by_id = {row['id']: row for row in matrix['include']}
        for batch in batches:
            for check in batch['checks']:
                self.assertEqual(tuple(batch[key] for key in ('runner', 'image', 'target', 'environment')),
                                 tuple(by_id[check][key] for key in ('runner', 'image', 'target', 'environment')))
        for target in ('linux-x86_64', 'linux-aarch64'):
            ubuntu = [batch for batch in batches if batch['target'] == target and batch['environment'] == 'ubuntu-24.04']
            self.assertEqual({batch['image'] for batch in ubuntu}, {'', 'ubuntu:24.04'})
            self.assertEqual(next(batch for batch in ubuntu if not batch['image'])['checks'],
                             [target + '-hosted-web-ubuntu-24.04-archive'])
        windows = [batch for batch in batches if batch['target'] == 'windows-x86_64']
        self.assertEqual(len(windows), 3)
        self.assertTrue(all(batch['graphics'] and not batch['browser'] for batch in windows))
        changed = copy.deepcopy(frozen); changed['checks'][0]['environment'] = 'debian-13'
        with self.assertRaises(ValueError): ci.qualification_batches(changed)
        chromium = next(row for row in matrix['include'] if row['id']=='browser-wasm32-wasm-chromium-archive')
        self.assertEqual(chromium['image'], '')
        command = next(row['argv'] for row in frozen['checks'] if row['id']==chromium['id'])
        self.assertIn('/usr/bin/google-chrome', command); self.assertIn('/usr/bin/chromedriver', command)
        grouped=[x for x in frozen['checks'] if 'execution' in x]
        self.assertEqual(len(grouped),48)
        self.assertTrue(all(x['scope'] in ('source','recovery','abi') for x in grouped))
        self.assertEqual(len({x['execution'] for x in grouped}),8)
        for leader in original('coverage').executions(frozen):
            if 'execution' in leader:
                rows=original('coverage').execution_members(frozen,leader)
                self.assertEqual({x['backend'] for x in rows},set(policy['profiles']['all-gui']['targets'][leader['target']]))

    def test_every_supported_profile_batch_name_passes_real_transport_context(self):
        from unittest.mock import Mock
        original = ci.module; policy = json.loads((ci.ROOT / 'docs/release-policy.json').read_text())
        source = original('release').verify_release(self.fixture.directory)
        transport = original('ci_transport')
        for profile in ('core', 'all-gui'):
            with self.subTest(profile=profile):
                manifest = copy.deepcopy(source)
                manifest['artifacts'] = [dict(source['artifacts'][0], target=target, backends=backends)
                    for target, backends in policy['profiles'][profile]['targets'].items()]
                release = Mock(verify_release=Mock(return_value=manifest))
                release.dependency_recipes = original('release').dependency_recipes
                output = self.root / (profile + '-bundle-names.json')
                with patch.object(ci, 'module', side_effect=lambda name: release if name == 'release' else original(name)):
                    matrix = ci.qualification_plan(self.fixture.directory, profile, output, policy)
                frozen = json.loads(output.read_text()); before = copy.deepcopy(frozen)
                batches = ci.qualification_batches(frozen)['include']
                self.assertEqual(frozen, before)
                self.assertEqual(sorted(check for batch in batches for check in batch['checks']),
                                 sorted(row['id'] for row in matrix['include']))
                self.assertEqual(len({batch['id'] for batch in batches}), len(batches))
                for batch in batches:
                    for prefix in ('evidence-', 'browser-prerequisite-'):
                        for attempt in (1, 2**63 - 1):
                            name = prefix + batch['id'] + '-' + str(attempt)
                            context = transport._context('example/project', 123, attempt, 'a'*40, 'certify.yml', name)
                            self.assertEqual(context['name'], name)

    def test_windows_gui_plan_freezes_graphics_inputs_and_passes_explicit_archive(self):
        from unittest.mock import Mock
        target = 'windows-x86_64'
        policy = {'schema_version': 1, 'profiles': {'fixture': {'description': 'fixture graphics',
                  'targets': {target: ['rev']}, 'checks': [dict(target=target, backend='rev',
                  environment='windows-2022', scope=scope) for scope in ('source', 'archive', 'recovery')]}}}
        original = ci.module
        release = Mock(verify_release=Mock(return_value=dict(original('release').verify_release(self.fixture.directory))))
        release.dependency_recipes = original('release').dependency_recipes
        release.verify_release.return_value['artifacts'][0].update(target=target, backends=['rev'])
        with patch.object(ci, 'module', side_effect=lambda name: release if name == 'release' else original(name)):
            output = self.root / 'graphics-plan.json'
            matrix = ci.qualification_plan(self.fixture.directory, 'fixture', output, policy)
        frozen = json.loads(output.read_text())
        self.assertTrue(all(item['graphics'] for item in matrix['include']))
        for item in frozen['checks']:
            self.assertIn('--windows-graphics-archive', item['argv'])
            self.assertNotIn('--browser-prerequisite', item['argv'])
        self.assertIn('tools/windows_gl_probe.cpp', frozen['inputs'])
        self.assertIn('third_party/host-graphics/mesa-windows.json', frozen['inputs'])
        self.assertTrue(all(item.get('sdk_payload') == 'complete' for item in frozen['checks'] if item['scope'] == 'source'))
        with patch.object(ci, 'module', side_effect=lambda name: release if name == 'release' else original(name)), \
                patch.object(ci, 'archived_binary_group_support', return_value=True):
            ci.qualification_plan(self.fixture.directory, 'fixture', self.root / 'modern-graphics-plan.json', policy)
        modern = json.loads((self.root / 'modern-graphics-plan.json').read_text())
        self.assertTrue(all(item.get('sdk_payload') == 'binary' for item in modern['checks'] if item['scope'] == 'source'))



class QualificationBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        spec = importlib.util.spec_from_file_location('batch_lifecycle', ci.ROOT / '.github/scripts/lifecycle.py')
        self.helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.helper)

    def plan(self, backends=('terminal', 'fltk', 'sdl'), target='linux-x86_64', environment='debian-12'):
        c = ci.module('coverage')
        checks = [dict(id='case-' + str(index), target=target, environment=environment, backend=backend,
                       scope='archive', required=True, argv=['python', 'check'], timeout_seconds=5400,
                       warning_seconds=4500, expected_tests=[]) for index, backend in enumerate(backends)]
        plan = c.freeze(dict(schema_version=1, mode='release', subject=dict(source_sha256='a'*64,
                            inventory_sha256='b'*64, configuration_sha256='c'*64), inputs={}, checks=checks))
        (self.root / 'build').mkdir(exist_ok=True)
        (self.root / 'build/check-plan.json').write_text(json.dumps(plan))
        return plan

    def test_failed_case_continues_later_fresh_container_and_fails_batch(self):
        import subprocess
        plan = self.plan(); batch = ci.qualification_batches(plan)['include'][0]; seen = []
        def run(command, **options):
            seen.append((command, options))
            if options['env']['CHECK'] == 'case-1': raise subprocess.CalledProcessError(1, command)
        with patch.object(self.helper, 'ROOT', self.root), patch.object(self.helper.ci.platform, 'system', return_value='Linux'), \
                patch.dict(self.helper.os.environ, BATCH=batch['id'], CHECK_IMAGE=batch['image']), \
                patch.object(self.helper.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'required batch executions failed: case-1'):
                self.helper.check_batch()
        self.assertEqual([options['env']['CHECK'] for command, options in seen], ['case-0', 'case-1', 'case-2'])
        self.assertTrue(all(command[-2:] == [str(self.root / '.github/scripts/container_job.py'), 'check'] for command, options in seen))
        self.assertTrue(all(options['cwd'] == self.root and options['check'] for command, options in seen))
        self.assertFalse((self.root / 'build/evidence').exists())  # No fabricated success or empty output root.

    def test_host_browser_keeps_per_case_prerequisite_before_check(self):
        plan = self.plan(('wasm',), 'browser-wasm32', 'chromium'); batch = ci.qualification_batches(plan)['include'][0]
        with patch.object(self.helper, 'ROOT', self.root), patch.object(self.helper.ci.platform, 'system', return_value='Linux'), \
                patch.dict(self.helper.os.environ, BATCH=batch['id'], CHECK_IMAGE=''), \
                patch.object(self.helper.subprocess, 'run') as run:
            self.helper.check_batch()
        self.assertEqual([call.args[0][-1] for call in run.call_args_list], ['check-prerequisites', 'check'])
        self.assertTrue(all(call.kwargs['env']['CHECK'] == 'case-0' and call.kwargs['env']['CHECK_BROWSER'] == 'yes'
                            for call in run.call_args_list))

    def test_windows_batch_runs_independent_cases_without_container_or_browser_setup(self):
        plan = self.plan(('terminal', 'rev'), 'windows-x86_64', 'windows-2022'); batch = ci.qualification_batches(plan)['include'][0]
        with patch.object(self.helper, 'ROOT', self.root), patch.object(self.helper.ci.platform, 'system', return_value='Windows'), \
                patch.dict(self.helper.os.environ, BATCH=batch['id'], CHECK_IMAGE=''), \
                patch.object(self.helper.subprocess, 'run') as run:
            self.helper.check_batch()
        self.assertEqual([call.args[0][-1] for call in run.call_args_list], ['check', 'check'])
        self.assertEqual([call.kwargs['env']['CHECK'] for call in run.call_args_list], ['case-0', 'case-1'])

    def test_batch_selection_rejects_unknown_id_image_and_changed_frozen_input_before_launch(self):
        plan = self.plan(); batch = ci.qualification_batches(plan)['include'][0]
        with patch.object(self.helper, 'ROOT', self.root), patch.object(self.helper.ci.platform, 'system', return_value='Linux'), \
                patch.object(self.helper.subprocess, 'run') as run:
            for identity, image in (('absent', batch['image']), (batch['id'], 'ubuntu:24.04')):
                with patch.dict(self.helper.os.environ, BATCH=identity, CHECK_IMAGE=image), self.assertRaises(ValueError):
                    self.helper.check_batch()
            (self.root / 'mapping.py').write_text('before')
            plan.pop('id'); plan['inputs'] = {'mapping.py': ci.module('coverage').sha(self.root / 'mapping.py')}
            plan = ci.module('coverage').freeze(plan)
            (self.root / 'build/check-plan.json').write_text(json.dumps(plan))
            (self.root / 'mapping.py').write_text('after')
            with patch.dict(self.helper.os.environ, BATCH=batch['id'], CHECK_IMAGE=batch['image']), \
                    self.assertRaisesRegex(ValueError, 'check input changed'):
                self.helper.check_batch()
            run.assert_not_called()

    def test_future_batch_growth_splits_without_changing_execution_inventory(self):
        plan = self.plan(tuple('backend-' + str(index) for index in range(33)))
        batches = ci.qualification_batches(plan)['include']
        self.assertEqual([len(batch['checks']) for batch in batches], [16, 16, 1])
        self.assertEqual([check for batch in batches for check in batch['checks']], [item['id'] for item in plan['checks']])
        self.assertEqual(len({batch['id'] for batch in batches}), 3)

    def test_normalized_truncated_batch_ids_preserve_checks_and_reject_digest_collision(self):
        c = ci.module('coverage'); plan = self.plan(tuple('backend-' + str(index) for index in range(33)))
        plan.pop('id')
        for index, item in enumerate(plan['checks']):
            item['id'] = ('Case.Shared.' if index % 2 == 0 else 'case-shared-') + 'x'*100 + '-' + str(index)
        plan = c.freeze(plan); before = copy.deepcopy(plan)
        batches = ci.qualification_batches(plan)['include']
        self.assertEqual(plan, before)
        self.assertEqual([check for batch in batches for check in batch['checks']], [item['id'] for item in plan['checks']])
        self.assertEqual(len({batch['id'] for batch in batches}), 3)
        self.assertTrue(all(len(batch['id']) <= 39 and batch['id'].startswith('batch-case-shared-') for batch in batches))
        self.assertEqual(ci.qualification_batches(plan)['include'], batches)
        original, loader = c.digest, ci.module
        with patch.object(ci, 'module', side_effect=lambda name: c if name == 'coverage' else loader(name)), \
                patch.object(c, 'digest', side_effect=lambda value: '0'*64 if 'runner' in value else original(value)):
            with self.assertRaisesRegex(ValueError, 'colliding batch transport identity'):
                ci.qualification_batches(plan)

    def test_evidence_aggregation_fetches_each_batch_once_into_shared_case_root(self):
        plan = self.plan(); batch = ci.qualification_batches(plan)['include'][0]
        with patch.object(self.helper, 'ROOT', self.root), patch.object(self.helper.os, 'chdir'), \
                patch.object(self.helper.evidence, 'load', return_value=plan), \
                patch.dict(self.helper.os.environ, GITHUB_RUN_ATTEMPT='2'), \
                patch.object(self.helper, 'fetch_bundle') as fetch:
            self.helper.main('fetch-evidence-bundles')
        fetch.assert_called_once_with('evidence-' + batch['id'] + '-2', 'build/evidence', allow_failed=True)

    def test_batch_bundle_preserves_case_children_and_disjoint_restore_rejects_collision(self):
        from unittest.mock import Mock
        for name in ('case-a', 'case-b'):
            path = self.root / 'build/evidence' / name; path.mkdir(parents=True)
            (path / 'result.json').write_text(name)
        with patch.object(self.helper, 'ROOT', self.root):
            base, paths = self.helper.bundle_inputs('build/evidence/')
        self.assertEqual(base, self.root / 'build/evidence')
        self.assertEqual(paths, ['case-a', 'case-b'])
        original = ci.module
        def fetched(repository, run, attempt, source, workflow, name, output, **options):
            path = output / name / 'result.json'; path.parent.mkdir(parents=True); path.write_text(name)
            return {'manifest': {'files': {name + '/result.json': {'mode': 0o600}}}}
        transport = Mock(fetch_bundle=Mock(side_effect=fetched)); destination = self.root / 'restored'
        with patch.object(ci, 'module', side_effect=lambda name: transport if name == 'ci_transport' else original(name)):
            for name in ('case-a', 'case-b'):
                ci.restore_run_bundle('example/project', 1, 1, 'a'*40, 'certify.yml', name, destination, allow_failed=True)
            with self.assertRaisesRegex(ValueError, 'existing file'):
                ci.restore_run_bundle('example/project', 1, 1, 'a'*40, 'certify.yml', 'case-a', destination, allow_failed=True)
        self.assertEqual({path.relative_to(destination).as_posix(): path.read_text() for path in destination.rglob('*.json')},
                         {'case-a/result.json': 'case-a', 'case-b/result.json': 'case-b'})


class SdkMaintenanceTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent))
        import test_github_release
        self.fixture = test_github_release.DeliveryTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.remote = self.fixture.remote; self.root = self.fixture.root
        self.recipe = self.fixture.fixture.recipe

    def choose(self, **changes):
        args = dict(repository='example/project', recipe=self.recipe, output=self.root / 'selected', transport=self.remote)
        args.update(changes); return ci.maintenance_base(**args)

    def test_absence_is_explicit_and_base_only_never_rebuilds(self):
        self.assertEqual(self.choose()['origin'], 'absent-base')
        with self.assertRaisesRegex(ValueError, 'absent'): self.choose(source='base')
        self.assertFalse((self.root / 'selected').exists())
        self.remote.refs['base'] = 'a' * 40
        with self.assertRaisesRegex(ValueError, 'orphan'): self.choose()
        self.assertEqual(self.remote.mutations, [])

    def test_complete_base_is_verified_and_reused(self):
        self.fixture.base(execute=True); before = len(self.remote.mutations)
        result = self.choose()
        self.assertEqual(result['origin'], 'base')
        self.assertTrue((self.root / 'selected').is_dir())
        self.assertEqual(len(self.remote.mutations), before)

    def test_partial_corrupt_and_network_errors_never_fall_back(self):
        self.fixture.base(execute=True)
        complete = copy.deepcopy(self.remote.releases[0]['assets'])
        self.remote.releases[0]['assets'].pop()
        with self.assertRaisesRegex(ValueError, 'partial'): self.choose()
        self.remote.releases[0]['assets'] = complete
        first = complete[0]; self.remote.data[first['id']] = b'corrupt'
        with self.assertRaisesRegex(ValueError, 'bytes'): self.choose()
        with patch.object(self.remote, 'pages', side_effect=OSError('network unavailable')):
            with self.assertRaisesRegex(OSError, 'network'): self.choose()
        self.assertFalse((self.root / 'selected').exists())

    def test_only_explicit_rebuild_skips_remote_and_other_recipe_absence_is_checked(self):
        with patch.object(self.remote, 'pages', side_effect=AssertionError('unexpected network')):
            self.assertEqual(self.choose(source='rebuild')['origin'], 'rebuild')
        self.fixture.base(execute=True)
        self.assertEqual(self.choose(recipe='b' * 64)['origin'], 'absent-recipe')
        with self.assertRaises(ValueError): self.choose(source='latest')

    def test_core_sdk_probe_requires_copied_installed_consumer_success(self):
        import shutil
        from unittest.mock import Mock
        original = ci.module; sdk = Mock(); artifacts = original('artifact')
        verifier = Mock(describe=artifacts.describe)
        def selected(name):
            return sdk if name == 'sdk' else verifier if name == 'artifact' else original(name)
        manifest = original('release').verify_release(self.fixture.directory)
        archive = self.fixture.directory / manifest['artifacts'][0]['archive']
        output = self.root / 'probe'; commands = []
        def run(argv, **kwargs):
            commands.append(argv)
            if argv[2] == 'package':
                packages = Path(argv[argv.index('--build-dir') + 1]) / 'packages'; packages.mkdir(parents=True)
                shutil.copyfile(archive, packages / 'application.tar.gz')
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), patch.object(ci.subprocess, 'run', side_effect=run):
            result = ci.prepared_check('linux-x86_64', self.recipe, self.root / 'group', output)
            self.assertIn('installed-consumer', result['checks'])
            self.assertEqual([x[2] for x in commands], ['test', 'package'])
            self.assertIn('--label', commands[0]); self.assertNotIn('--label', commands[1])
            self.assertNotIn('--junit', commands[1]); verifier.verify.assert_called_once()
            verifier.verify.side_effect = ValueError('installed consumer failed')
            with self.assertRaisesRegex(ValueError, 'consumer failed'):
                ci.prepared_check('linux-x86_64', self.recipe, self.root / 'group', self.root / 'failed-probe')
            self.assertFalse((self.root / 'failed-probe/qualification.json').exists())

    def test_browser_core_probe_selects_wasm_for_test_and_package_without_gui(self):
        import shutil
        from unittest.mock import Mock
        original = ci.module; sdk = Mock(); artifacts = original('artifact')
        verifier = Mock(describe=artifacts.describe)
        def selected(name):
            return sdk if name == 'sdk' else verifier if name == 'artifact' else original(name)
        manifest = original('release').verify_release(self.fixture.directory)
        archive = self.fixture.directory / manifest['artifacts'][0]['archive']
        output = self.root / 'browser-probe'; commands = []
        def run(argv, **kwargs):
            commands.append(argv)
            if argv[2] == 'package':
                packages = output / 'build/packages'; packages.mkdir(parents=True)
                shutil.copyfile(archive, packages / 'application.tar.gz')
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci.platform, 'system', return_value='Linux'), patch.object(ci.platform, 'machine', return_value='x86_64'), patch.object(ci.subprocess, 'run', side_effect=run):
            result = ci.prepared_check('browser-wasm32', self.recipe, self.root / 'group', output)
        self.assertEqual([argv[2] for argv in commands], ['test', 'package'])
        for argv in commands:
            self.assertEqual(argv[argv.index('--gui-backends') + 1], 'wasm')
            self.assertNotIn('--gui-input-group', argv); self.assertNotIn('--gui-source', argv)
        self.assertIn('--label', commands[0]); self.assertNotIn('--label', commands[1])
        self.assertEqual(result['target'], 'browser-wasm32')
        self.assertEqual(verifier.verify.call_args.kwargs['sdk'], output / 'sdk')

    def test_gui_qualification_never_packages_or_uploads_inputs(self):
        from unittest.mock import Mock
        original = ci.module; sdk = Mock()
        sdk.install.return_value = {'capabilities': ['core', 'terminal', 'framebuffer', 'fltk', 'rev', 'sdl', 'hosted-web']}
        def selected(name): return sdk if name == 'sdk' else original(name)
        group = self.root / 'group'; output = self.root / 'gui-check'
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), patch.object(ci.subprocess, 'run') as run:
            result = ci.prepared_check('linux-x86_64', self.recipe, group, output, gui_group=group)
        self.assertEqual(run.call_count, 1)
        argv = run.call_args.args[0]
        self.assertEqual(argv[2], 'test'); self.assertIn('--full', argv); self.assertIn('--host-tests', argv)
        self.assertFalse(result['redistribution'])
        self.assertEqual(self.remote.mutations, [])
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), patch.object(ci.subprocess, 'run') as run:
            sdk.install.return_value = {'capabilities': ['core']}
            with self.assertRaisesRegex(ValueError, 'capabilities'):
                ci.prepared_check('linux-x86_64', self.recipe, group, self.root / 'insufficient', gui_group=group)
            run.assert_not_called()


class WindowsGraphicsCiTests(unittest.TestCase):
    def test_graphics_selection_covers_combined_source_and_specific_archive_only(self):
        for backend in ('terminal', 'fltk', 'rev', 'hosted-web'):
            for scope in ('source', 'recovery', 'archive', 'abi', 'apt'):
                self.assertEqual(ci.needs_windows_graphics('windows-x86_64', ['fltk', 'rev'], backend, scope),
                                 scope in ('source', 'recovery') or backend == 'rev' and scope == 'archive')
                self.assertFalse(ci.needs_windows_graphics('windows-x86_64', ['core'], backend, scope))
                self.assertFalse(ci.needs_windows_graphics('linux-x86_64', ['rev'], backend, scope))

    def test_graphics_input_cannot_enter_core_or_non_windows_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for target, gui, archive in (('windows-x86_64', root, None),
                    ('windows-x86_64', None, root / 'graphics.7z'), ('linux-x86_64', root, root / 'graphics.7z')):
                with self.assertRaisesRegex(ValueError, 'explicit retained'):
                    ci.prepared_check(target, 'a' * 64, root, root / 'output', gui_group=gui, graphics_archive=archive)
            self.assertFalse((root / 'output').exists())

    def test_gui_runner_uses_bounded_shared_owner_and_propagates_failures(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); runtime = Mock(); staged = SimpleNamespace(environment={'PATH': 'controlled'})
            with patch.object(ci, 'module', return_value=runtime):
                ci.graphics_test(['test-command'], root, staged)
                runtime.run_owned.assert_called_once_with(['test-command'], root, root / 'graphics-test.log',
                    environment=staged.environment, timeout=3600, max_bytes=16 * 1024 * 1024)
                runtime.run_owned.side_effect = RuntimeError('writer cleanup unknown')
                with self.assertRaisesRegex(RuntimeError, 'cleanup unknown'):
                    ci.graphics_test(['test-command'], root, staged)

    def test_windows_gui_uses_shared_build_then_probe_and_test_before_cleanup(self):
        from types import SimpleNamespace
        from contextlib import contextmanager
        from unittest.mock import Mock
        sys.path.insert(0, str(Path(__file__).parent)); import test_github_release
        fixture = test_github_release.DeliveryTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        root = fixture.root; output = root / 'graphics-check'; events = []; commands = []
        original = ci.module; sdk = Mock(); graphics = Mock(); compiler = Mock()
        sdk.install.return_value = {'capabilities': ['terminal', 'framebuffer', 'fltk', 'rev', 'sdl', 'hosted-web']}
        @contextmanager
        def stage(archive, directories, **options):
            self.assertEqual(events, ['build', 'prerequisites'])
            self.assertEqual(directories, [output / 'build/gui'])
            self.assertIn(output / 'dependencies', options['protected_roots'])
            current = SimpleNamespace(environment={'TEST_GRAPHICS': 'owned'}, receipt={'cleanup': 'active'},
                                      probe_receipt={'status': 'passed'})
            events.append('probe')
            try: yield current
            finally: events.append('cleanup'); current.receipt['cleanup'] = 'removed'
        graphics.qualified_stage.side_effect = stage
        def selected(name):
            if name == 'windows_toolchain':
                import windows_toolchain
                return windows_toolchain
            return {'sdk_windows': sdk, 'windows_graphics': graphics, 'windows_compiler': compiler}.get(name) or original(name)
        def command(argv, **kwargs):
            self.assertEqual(kwargs, {'cwd': ci.ROOT})
            commands.append(argv)
            if argv[0] == 'cmake': events.append('prerequisites')
            else:
                self.assertEqual(argv[2], 'build'); self.assertNotIn('--junit', argv); self.assertNotIn('--full', argv)
                (output / 'build/gui').mkdir(parents=True); events.append('build')
        compiler.run.side_effect = command
        def tested(argv, destination, staged):
            self.assertEqual(argv[2], 'test'); self.assertIn('--full', argv); self.assertIn('--host-tests', argv)
            self.assertEqual(staged.environment, {'TEST_GRAPHICS': 'owned'}); events.append('test')
            captures = output / 'build/gui/visual-evidence/run-one'; captures.mkdir(parents=True)
            for name in ('qualification.json', 'capture.png', 'capture.ppm'): (captures / name).write_bytes(b'fixture')
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), \
             patch('windows_toolchain.inspect_selected_linker', return_value={'version':'14.44.35207.0'}), \
             patch.object(ci.subprocess, 'run', side_effect=AssertionError('unowned compiler launch')), patch.object(ci, 'graphics_test', side_effect=tested):
            result = ci.prepared_check('windows-x86_64', fixture.fixture.recipe, root / 'group', output,
                                      gui_group=root / 'group', graphics_archive=root / 'graphics.7z')
        sdk.install.assert_called_once_with((root / 'group').resolve(strict=True), fixture.fixture.recipe, output / 'dependencies', '14.44.35207.0')
        self.assertEqual(events, ['build', 'prerequisites', 'probe', 'test', 'cleanup'])
        self.assertEqual(compiler.run.call_count, 2)
        self.assertEqual(compiler.run.call_args_list[1].args[0],
                         ['cmake', '--build', str(output / 'build'), '--target', 'foundation-gui-tests', '--parallel', '2'])
        self.assertEqual(json.loads((output / 'graphics.json').read_text())['cleanup'], 'removed')
        self.assertIn('graphics.json', result['graphics_evidence'])
        self.assertIn('build/gui/visual-evidence/run-one/capture.png', result['graphics_evidence'])
        self.assertFalse(result['redistribution'])
        self.assertNotIn('package', [item[2] for item in commands])
        graphics.fetch.assert_not_called(); graphics.fetch_retained.assert_not_called()
        events.clear(); commands.clear(); output = root / 'failed-graphics-check'
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), \
             patch('windows_toolchain.inspect_selected_linker', return_value={'version':'14.44.35207.0'}), \
             patch.object(ci.subprocess, 'run', side_effect=AssertionError('unowned compiler launch')), \
             patch.object(ci, 'graphics_test', side_effect=RuntimeError('GUI assertion failed')):
            with self.assertRaisesRegex(RuntimeError, 'GUI assertion failed'):
                ci.prepared_check('windows-x86_64', fixture.fixture.recipe, root / 'group', output,
                                  gui_group=root / 'group', graphics_archive=root / 'graphics.7z')
        self.assertEqual(events, ['build', 'prerequisites', 'probe', 'cleanup'])
        self.assertFalse((output / 'qualification.json').exists())
        self.assertEqual(json.loads((output / 'graphics.json').read_text())['cleanup'], 'removed')
        events.clear(); output = root / 'failed-setup'
        failure = RuntimeError('probe setup failed'); failure.graphics_receipt = {'cleanup': 'retained-uncertain'}
        graphics.qualified_stage.side_effect = failure
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), \
             patch('windows_toolchain.inspect_selected_linker', return_value={'version':'14.44.35207.0'}), \
             patch.object(ci.subprocess, 'run', side_effect=AssertionError('unowned compiler launch')):
            with self.assertRaisesRegex(RuntimeError, 'probe setup failed'):
                ci.prepared_check('windows-x86_64', fixture.fixture.recipe, root / 'group', output,
                                  gui_group=root / 'group', graphics_archive=root / 'graphics.7z')
        self.assertFalse((output / 'qualification.json').exists())
        self.assertEqual(json.loads((output / 'graphics.json').read_text()), failure.graphics_receipt)

    def test_only_explicit_maintenance_uses_supplier_fetch(self):
        from unittest.mock import Mock
        helper_spec = importlib.util.spec_from_file_location('graphics_ci_lifecycle', ci.ROOT / '.github/scripts/lifecycle.py')
        helper = importlib.util.module_from_spec(helper_spec); helper_spec.loader.exec_module(helper)
        for command in ('graphics-input', 'graphics-maintain'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / 'build/host-graphics/mesa-windows.7z'
                graphics = Mock()
                def acquired(*args, **kwargs):
                    self.assertTrue(archive.parent.is_dir())
                    self.assertFalse(archive.exists())
                    return {'acquisition': command}
                graphics.fetch.side_effect = acquired; graphics.fetch_retained.side_effect = acquired
                with patch.dict(sys.modules, {'windows_graphics': graphics}), patch.object(helper, 'ROOT', root), \
                     patch.object(helper.os, 'chdir'), patch.object(helper.ci, 'assert_host'), \
                     patch.object(helper, 'write') as published, \
                     patch.dict(helper.os.environ, {'GRAPHICS_ARCHIVE_URL': 'https://storage.example/retained.7z'}):
                    helper.main(command)
                    if command == 'graphics-input':
                        graphics.fetch.assert_not_called()
                        graphics.fetch_retained.assert_called_once_with('https://storage.example/retained.7z', archive)
                    else:
                        graphics.fetch.assert_called_once_with(archive, network=True)
                        graphics.fetch_retained.assert_not_called()
                    published.assert_called_once_with('build/host-graphics/acquisition.json', {'acquisition': command})
                    graphics.reset_mock(); published.reset_mock()
                    archive.parent.rmdir(); archive.parent.write_bytes(b'not a directory')
                    with self.assertRaises(FileExistsError): helper.main(command)
                    graphics.fetch.assert_not_called(); graphics.fetch_retained.assert_not_called()
                    published.assert_not_called()
        for workflow in ('sdk-maintenance.yml', 'native-gui.yml', 'certify.yml'):
            text = (ci.ROOT / '.github/workflows' / workflow).read_text()
            self.assertNotIn('path: build/host-graphics/', text)
            self.assertNotIn('mesa-windows.7z\n', text)


class WindowsGraphicsPackageTests(unittest.TestCase):
    """Real source/group/archive inventories with isolated host-operation fixtures."""
    def setUp(self):
        from unittest.mock import Mock
        from test_sdk import fixture
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.recipe, _, _, self.group = fixture(self.root)
        source = self.root / 'source'; source.mkdir()
        (source / 'LICENSE').write_text('Inert source fixture\n')
        self.core_source = self.root / 'core-source.tar.gz'
        ci.module('source_identity').archive_source(source, self.core_source)
        gui = source / 'third_party/retained/gui'; gui.mkdir(parents=True)
        (gui / 'interface.hpp').write_text('/* retained GUI source fixture */\n')
        self.gui_source = self.root / 'gui-source.tar.gz'
        ci.module('source_identity').archive_source(source, self.gui_source)
        self.output = self.root / 'produced'; self.archive = self.root / 'retained.7z'
        self.archive.write_bytes(b'inert retained archive fixture')
        self.graphics = Mock(); self.sdk = Mock(); self.compiler = Mock(); self.events = []; self.commands = []
        self.compiler_failure = None
        self.sdk.install.return_value = {'capabilities': ['terminal', 'framebuffer', 'fltk', 'rev', 'sdl', 'hosted-web']}
        self.real_module = ci.module
        self.artifacts = Mock(describe=self.real_module('artifact').describe)
        self.cleanup = 'removed'; self.test_error = None; self.write_captures = True; self.setup_error = None

    def produce(self, *, source=None, target='windows-x86_64', graphics=True):
        from contextlib import contextmanager
        from types import SimpleNamespace
        import zipfile
        build = self.output / 'work/build'
        drivers = []
        @contextmanager
        def stage(archive, directories, **options):
            self.assertEqual(archive, self.archive)
            self.assertEqual(self.events, ['build', 'prerequisites'])
            self.assertEqual(directories, [build / 'gui'])
            self.assertEqual(options['compile_log'], self.output / 'graphics-compile.log')
            self.assertIn(self.group.resolve(), options['protected_roots'])
            self.assertIn(self.output / 'work/source', options['protected_roots'])
            self.assertIn(self.output / 'work/dependencies', options['protected_roots'])
            if self.setup_error: raise self.setup_error
            for directory in [*directories, options['probe_directory']]:
                for name in ('opengl32.dll', 'libgallium_wgl.dll'):
                    path = directory / name; path.write_bytes(b'host-only fixture'); drivers.append(path)
            current = SimpleNamespace(environment={'GRAPHICS_FIXTURE': 'owned'},
                receipt={'cleanup': 'active'}, probe_receipt={'status': 'passed'})
            self.events.append('probe')
            try: yield current
            finally:
                self.events.append('cleanup'); current.receipt['cleanup'] = self.cleanup
                if self.cleanup == 'removed':
                    for path in drivers: path.unlink()
        def run_test(argv, cwd, log, **options):
            self.assertEqual(argv[2:4], ['test', 'release'])
            self.assertIn('--full', argv); self.assertIn('--host-tests', argv)
            self.assertEqual(Path(argv[argv.index('--build-dir') + 1]), build)
            self.assertEqual(options['environment'], {'GRAPHICS_FIXTURE': 'owned'})
            self.assertEqual((options['timeout'], options['max_bytes']), (3600, 16 * 1024 * 1024))
            self.assertEqual(cwd, self.output); self.assertEqual(log, self.output / 'graphics-test.log')
            self.assertTrue(all(path.is_file() for path in drivers)); self.events.append('test')
            log.write_text('fixture command output\n')
            if self.test_error: raise self.test_error
            if self.write_captures:
                capture = build / 'gui/visual-evidence/fixture'; capture.mkdir(parents=True)
                for name in ('qualification.json', 'capture.png', 'capture.ppm'): (capture / name).write_bytes(b'fixture')
        def selected(name):
            if name == 'windows_toolchain':
                import windows_toolchain
                return windows_toolchain
            return {'sdk_windows': self.sdk, 'windows_graphics': self.graphics, 'artifact': self.artifacts,
                    'windows_compiler': self.compiler}.get(name) or self.real_module(name)
        def launched(argv, **options):
            self.commands.append(argv)
            if argv[0] == 'cmake':
                self.assertEqual(argv[2], str(build)); self.events.append('prerequisites'); return
            self.assertEqual(options['cwd'], self.output / 'work/source')
            self.assertEqual(Path(argv[argv.index('--build-dir') + 1]), build)
            if argv[2] == 'build':
                self.assertNotIn('--full', argv); self.assertNotIn('--junit', argv)
                (build / 'gui').mkdir(parents=True); self.events.append('build')
            elif argv[2] == 'package':
                self.assertEqual(self.events, ['build', 'prerequisites', 'probe', 'test', 'cleanup'])
                self.assertFalse(any(path.exists() for path in drivers))
                self.assertNotIn('--full', argv); self.assertNotIn('--junit', argv)
                self.events.append('package'); destination = build / 'packages'; destination.mkdir()
                with zipfile.ZipFile(destination / 'application.zip', 'x') as archive:
                    archive.writestr('Foundation/bin/foundation-cli.exe', 'inert program fixture')
            else: raise AssertionError(argv)
        def owned(argv, **options):
            phase = 'prerequisites' if argv[0] == 'cmake' else 'build'
            self.assertEqual(options, {'cwd': self.output / 'work/source'})
            if self.compiler_failure == phase:
                import process_tree
                raise process_tree.ProcessTreeError('compiler cleanup unknown: ' + phase)
            return launched(argv, **options)
        def unmanaged(argv, **options):
            self.assertEqual(argv[2], 'package', 'compiler launch bypassed its private owner')
            return launched(argv, **options)
        self.compiler.run.side_effect = owned
        self.graphics.qualified_stage.side_effect = stage
        self.graphics.run_owned.side_effect = run_test
        with patch.object(ci, 'module', side_effect=selected), patch.object(ci, 'assert_host'), \
             patch('windows_toolchain.inspect_selected_linker', return_value={'version':'14.44.35207.0'},
                   side_effect=getattr(self, 'probe_error', None)), \
             patch.object(ci.subprocess, 'run', side_effect=unmanaged):
            return ci.prepared_package(target, self.recipe, self.group, source or self.gui_source,
                self.output, 2, graphics_archive=self.archive if graphics else None)

    def test_unverified_windows_linker_stops_before_dependency_install_or_build(self):
        self.probe_error = ValueError('selected linker identity invalid')
        with self.assertRaisesRegex(ValueError, 'linker identity invalid'): self.produce()
        self.sdk.install.assert_not_called()
        self.assertEqual(self.commands, [])
        self.graphics.qualified_stage.assert_not_called()

    def test_package_follows_complete_test_and_host_cleanup_and_binds_evidence(self):
        result = self.produce()
        self.assertEqual(result['path'], 'windows-x86_64.zip')
        self.assertEqual(result['manifest_path'], 'windows-x86_64.zip.json')
        self.sdk.install.assert_called_once_with(self.group, self.recipe, self.output / 'work/dependencies', '14.44.35207.0')
        self.assertEqual(self.events, ['build', 'prerequisites', 'probe', 'test', 'cleanup', 'package'])
        self.graphics.verify_archive.assert_called_once_with(self.archive)
        self.graphics.fetch.assert_not_called(); self.graphics.fetch_retained.assert_not_called()
        self.artifacts.verify.assert_called_once()
        receipt = json.loads((self.output / 'graphics-qualification.json').read_text())
        self.assertEqual(receipt['archive_sha256'], result['sha256'])
        self.assertEqual(receipt['backends'], result['backends'])
        self.assertEqual(json.loads((self.output / 'graphics.json').read_text())['cleanup'], 'removed')
        self.assertIn('work/build/gui/visual-evidence/fixture/capture.png', receipt['evidence'])
        for name, digest in receipt['evidence'].items():
            self.assertEqual(self.real_module('coverage').sha(self.output / name), digest)
        self.assertFalse(list(self.output.rglob('*.dll')))

    def test_compiler_owner_failure_stops_graphics_and_packaging(self):
        import process_tree
        for phase in ('build', 'prerequisites'):
            with self.subTest(phase=phase):
                self.output = self.root / ('failed-' + phase)
                self.compiler_failure = phase
                self.events.clear(); self.commands.clear(); self.compiler.reset_mock()
                with self.assertRaisesRegex(process_tree.ProcessTreeError, 'compiler cleanup unknown: ' + phase):
                    self.produce()
                self.assertEqual(self.compiler.run.call_count, 1 if phase == 'build' else 2)
                self.assertEqual(self.events, [] if phase == 'build' else ['build'])
                self.graphics.qualified_stage.assert_not_called()
                self.graphics.run_owned.assert_not_called()
                self.artifacts.verify.assert_not_called()
                self.assertFalse((self.output / 'graphics-qualification.json').exists())
                self.assertFalse((self.output / 'artifact.json').exists())
                self.assertNotIn('package', self.events)

    def test_absent_gui_input_and_unexpected_core_or_linux_input_never_build(self):
        for label, options in [('missing', {'graphics': False}), ('core', {'source': self.core_source}),
                               ('linux', {'target': 'linux-x86_64'})]:
            with self.subTest(case=label):
                self.output = self.root / label
                with self.assertRaisesRegex(ValueError, 'retained host graphics'): self.produce(**options)
                self.assertEqual(self.commands, [])
                self.graphics.qualified_stage.assert_not_called()
                self.assertFalse((self.output / 'artifact.json').exists())
        self.graphics.fetch.assert_not_called(); self.graphics.fetch_retained.assert_not_called()

    def test_failed_gui_assertion_never_packages_and_keeps_cleanup_receipt(self):
        self.test_error = RuntimeError('GUI assertion failed')
        with self.assertRaisesRegex(RuntimeError, 'GUI assertion failed'): self.produce()
        self.assertEqual(self.events[-1], 'cleanup')
        self.assertNotIn('package', self.events); self.artifacts.verify.assert_not_called()
        self.assertFalse((self.output / 'artifact.json').exists())
        self.assertFalse((self.output / 'graphics-qualification.json').exists())
        self.assertEqual(json.loads((self.output / 'graphics.json').read_text())['cleanup'], 'removed')

    def test_retained_or_uncertain_host_files_block_packaging_and_survive(self):
        self.cleanup = 'retained-changed'
        with self.assertRaisesRegex(ValueError, 'cleanup did not complete') as caught: self.produce()
        self.assertEqual(caught.exception.graphics_receipt['cleanup'], 'retained-changed')
        self.assertEqual(len(list(self.output.rglob('*.dll'))), 4)
        self.assertNotIn('package', self.events); self.assertFalse((self.output / 'artifact.json').exists())

    def test_pre_yield_failure_preserves_evidence_and_output(self):
        self.setup_error = RuntimeError('probe completion uncertain')
        self.setup_error.graphics_receipt = {'cleanup': 'retained-uncertain'}
        with self.assertRaisesRegex(RuntimeError, 'completion uncertain'): self.produce()
        self.assertEqual(json.loads((self.output / 'graphics.json').read_text()), self.setup_error.graphics_receipt)
        self.assertTrue((self.output / 'work/source').is_dir())
        self.assertNotIn('package', self.events); self.assertFalse((self.output / 'artifact.json').exists())

    def test_missing_rendered_capture_inventory_prevents_package(self):
        self.write_captures = False
        with self.assertRaisesRegex(ValueError, 'capture evidence'): self.produce()
        self.assertNotIn('package', self.events); self.assertFalse((self.output / 'artifact.json').exists())


class AptMechanismLifecycleTests(unittest.TestCase):
    def test_early_package_failure_retains_started_receipt_without_success(self):
        from subprocess import CalledProcessError
        helper_spec = importlib.util.spec_from_file_location('apt_ci_lifecycle', ci.ROOT / '.github/scripts/lifecycle.py')
        helper = importlib.util.module_from_spec(helper_spec); helper_spec.loader.exec_module(helper)
        import release_check
        original_write = helper.write
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(helper, 'ROOT', root), patch.object(helper.os, 'chdir'), \
                 patch.object(release_check, 'apt_preflight'), patch.object(release_check, 'run_apt') as execute, \
                 patch.object(helper.subprocess, 'run', side_effect=CalledProcessError(1, ['build'])), \
                 patch.object(helper, 'write', side_effect=lambda path, item: original_write(root / path, item)), \
                 patch.dict(helper.os.environ, {'GITHUB_SHA': 'a' * 40}):
                with self.assertRaises(CalledProcessError): helper.main('apt-native-smoke')
                execute.assert_not_called()
            record = json.loads((root / 'build/apt-evidence/started.json').read_text())
            self.assertEqual(record, dict(operation='apt-native-smoke', target='linux-x86_64', backend='core',
                                         status='started', source_commit='a' * 40))
            self.assertFalse((root / 'build/apt-evidence/result.json').exists())


class GuiInputDeliveryTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        import test_github_release
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.group = self.root / 'group'; self.group.mkdir()
        self.files = {'gui-inputs.tar.gz': b'retained inputs', 'manifest.json': b'{"redistributable":true}', 'SHA256SUMS': b'complete group'}
        for name, data in self.files.items(): (self.group / name).write_bytes(data)
        self.remote = test_github_release.FakeGitHub()
        def verify(group, redistribution=False):
            if {p.name: p.read_bytes() for p in Path(group).iterdir()} != self.files:
                raise ValueError('fixture group differs')
            return {'redistributable': True}
        self.patch = patch.object(ci, 'gui_group_module', return_value=SimpleNamespace(verify=verify))
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.identity = ci.module('coverage').sha(self.group / 'manifest.json')

    def publish(self, execute=False):
        return ci.publish_gui_group('example/project', self.group, 'a' * 40, execute=execute, transport=self.remote)

    def test_plan_never_contacts_remote_and_complete_group_roundtrips(self):
        self.assertFalse(self.publish()['execute']); self.assertEqual(self.remote.calls, [])
        self.assertFalse(self.publish(True)['reused']); self.assertIsNone(self.remote.latest)
        self.assertTrue(self.publish(True)['reused'])
        ci.fetch_gui_group('example/project', self.identity, self.root / 'fetched', self.remote)
        self.assertEqual({p.name: p.read_bytes() for p in (self.root / 'fetched').iterdir()}, self.files)

    def test_missing_partial_and_conflicting_groups_fail_without_replacement(self):
        with self.assertRaises(ValueError): ci.fetch_gui_group('example/project', self.identity, self.root / 'missing', self.remote)
        self.publish(True)
        self.remote.releases[0]['assets'].pop()
        count = len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError, 'partial'): self.publish(True)
        self.assertEqual(len(self.remote.mutations), count)

    def test_replaced_asset_identity_blocks_fetch_even_with_same_bytes(self):
        self.publish(True)
        asset = ci.gui_group_names(self.identity)['manifest.json']
        self.remote.change_download = lambda: self.remote.replace_asset(asset)
        with self.assertRaisesRegex(ValueError, 'identities changed'):
            ci.fetch_gui_group('example/project', self.identity, self.root / 'fetched', self.remote)
        self.assertFalse((self.root / 'fetched').exists())

    def test_unresolved_redistribution_prevents_all_remote_mutations(self):
        from types import SimpleNamespace
        with patch.object(ci, 'gui_group_module', return_value=SimpleNamespace(verify=lambda *a, **k: (_ for _ in ()).throw(ValueError('unresolved terms')))):
            with self.assertRaisesRegex(ValueError, 'unresolved'): self.publish(True)
        self.assertEqual(self.remote.mutations, [])



if __name__ == "__main__":
    unittest.main()
