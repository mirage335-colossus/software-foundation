import copy
import importlib.util
from pathlib import Path
import platform
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_check', Path(__file__).resolve().parents[1] / 'tools/release_check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ReleaseCheckTests(unittest.TestCase):
    def test_windows_source_consumes_verified_file_version_and_rejects_bad_probe(self):
        import sdk_windows
        import windows_toolchain
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); entry = {'target':'windows-x86_64','sdk_recipe':'a'*64,'backends':[]}
            manifest = {'source':{'archive':'source.tar.gz'}}
            with patch.object(check,'native_target'), patch.object(check,'verify_source_archive',return_value='snapshot'), \
                 patch.object(check,'extract'), patch.object(check,'source_tree',return_value='snapshot'), \
                 patch.object(windows_toolchain,'inspect_selected_linker',return_value={'version':'14.44.35207.0'}) as probe, \
                 patch.object(sdk_windows,'install',side_effect=RuntimeError('stop after verified version')) as install:
                with self.assertRaisesRegex(RuntimeError,'stop after verified version'):
                    check.run_source(root,manifest,entry,root/'work',root/'evidence',2)
                install.assert_called_once_with(root/'dependencies'/entry['sdk_recipe'],entry['sdk_recipe'],
                    root/'work/windows-dependencies','14.44.35207.0')
                install.reset_mock();probe.side_effect=ValueError('selected linker identity failed')
                with self.assertRaisesRegex(ValueError,'identity failed'):
                    check.run_source(root,manifest,entry,root/'work',root/'evidence',2)
                install.assert_not_called()

    def test_windows_source_stages_only_after_build_and_saves_final_cleanup(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        import json
        import windows_graphics
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); work = root / 'work'; work.mkdir()
            evidence = root / 'evidence'; evidence.mkdir()
            command = ['python', 'tools/build.py', 'test', 'release', '--full', '--junit', 'report.xml',
                       '--gui-backends', 'terminal,framebuffer,fltk,rev,sdl,hosted-web']
            events = []
            @contextmanager
            def staging(archive, directories, **options):
                self.assertEqual(events, ['build', 'gui-prerequisites'])
                self.assertEqual(directories, [work / 'build/gui'])
                self.assertEqual(options['protected_roots'], (root / 'sdk',))
                value = SimpleNamespace(environment={'GALLIUM_DRIVER': 'llvmpipe'},
                    receipt={'cleanup': 'pending'}, probe_receipt={'renderer': 'verified fixture'})
                try:
                    yield value
                finally:
                    events.append('cleanup'); value.receipt['cleanup'] = 'removed'
            def build(argv, **options):
                if argv[0] == 'python':
                    self.assertEqual(argv[2], 'build')
                    self.assertNotIn('--full', argv); self.assertNotIn('--junit', argv)
                    self.assertIn(command[-1], argv); events.append('build')
                else:
                    self.assertIn('foundation-gui-tests', argv); events.append('gui-prerequisites')
            def execute(argv, cwd, log, **options):
                self.assertEqual(argv, command)
                self.assertEqual(options['environment']['GALLIUM_DRIVER'], 'llvmpipe')
                self.assertFalse((evidence / 'windows-graphics/graphics.json').exists())
                log.write_bytes(b'unchanged full tests completed'); events.append('tests')
            with patch.object(windows_graphics, 'verify_archive'), \
                    patch.object(windows_graphics, 'qualified_stage', staging), \
                    patch.object(windows_graphics, 'run_owned', side_effect=execute), \
                    patch.object(check.subprocess, 'run', side_effect=build):
                result = check.run_windows_source(command, root / 'retained.7z', work, evidence, (root / 'sdk',), 2)
            self.assertEqual(events, ['build', 'gui-prerequisites', 'tests', 'cleanup'])
            self.assertEqual(json.loads((evidence / 'windows-graphics/graphics.json').read_text())['cleanup'], 'removed')
            self.assertEqual(result['graphics_sha256'], check.digest(evidence / 'windows-graphics/graphics.json'))

    def test_windows_graphics_is_required_only_for_actual_rev_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest, unused = self.fixture(root)
            manifest['artifacts'][0].update(target='windows-x86_64', backends=['terminal', 'rev'])
            with patch.object(check.release, 'verify_release', return_value=manifest), \
                    patch.object(check, 'native_target'), patch.object(check.artifact, 'verify') as verify:
                for scope, backend, options in [('source', 'terminal', {}), ('recovery', 'rev', {}),
                    ('archive', 'rev', {}), ('archive', 'terminal', {'windows_graphics_archive': root / 'retained.7z'})]:
                    with self.assertRaisesRegex(ValueError, 'retained graphics'):
                        check.check(root, 'windows-x86_64', backend, scope, root / 'absent', browser_options=options)
                verify.assert_not_called()
                def performed(*args, **options):
                    dest = options['windows_graphics_evidence']; dest.mkdir()
                    (dest / 'graphics.json').write_text('{"cleanup":"removed"}')
                    return {'windows_graphics': {'checks': 'probe-and-smoke'}}
                verify.side_effect = performed
                result = check.check(root, 'windows-x86_64', 'rev', 'archive', root / 'evidence',
                                     browser_options={'windows_graphics_archive': root / 'retained.7z'})
                self.assertIn('windows-graphics/graphics.json', result['evidence'])
                self.assertEqual(result['details']['windows_graphics']['checks'], 'probe-and-smoke')

    def test_visual_capture_retention_rejects_incomplete_or_unexpected_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); build = root / 'build'; source = build / 'gui/visual-evidence/run'
            source.mkdir(parents=True); evidence = root / 'evidence'; evidence.mkdir()
            for name in ['qualification.json', 'native.png', 'framebuffer.ppm']:
                (source / name).write_bytes(name.encode())
            bad = source / 'opengl32.dll'; bad.write_bytes(b'not a capture')
            with self.assertRaisesRegex(ValueError, 'capture evidence'):
                check.retain_native_visuals(build, evidence)
            bad.unlink(); (source / 'framebuffer.ppm').unlink()
            with self.assertRaisesRegex(ValueError, 'capture evidence'):
                check.retain_native_visuals(build, evidence)
            (source / 'framebuffer.ppm').write_bytes(b'pixels fixture')
            inventory = check.retain_native_visuals(build, evidence)
            self.assertEqual(len(inventory), 3)
            for name, digest in inventory.items():
                self.assertEqual(digest, check.digest(evidence / name))
                self.assertEqual((evidence / name).read_bytes(), (source / Path(name).name).read_bytes())

    def test_qualification_workspace_retains_uncertain_writers_and_cleans_safe_failure(self):
        import json
        from process_tree import ProcessTreeError
        import windows_graphics
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); evidence = root / 'evidence'; evidence.mkdir()
            safe = None
            with self.assertRaisesRegex(ValueError, 'ordinary failure'):
                with check.qualification_work(evidence) as safe:
                    (safe / 'output').write_bytes(b'complete')
                    raise ValueError('ordinary failure')
            self.assertFalse(safe.exists())
            for kind in ('uncertain', 'changed'):
                case = evidence / kind; case.mkdir()
                error = ProcessTreeError('writer completion unconfirmed') if kind == 'uncertain' else windows_graphics.GraphicsError('changed owned file')
                if kind == 'changed': error.graphics_receipt = {'cleanup': 'preserved-changed-files'}
                with self.assertRaises(type(error)):
                    with check.qualification_work(case) as retained:
                        (retained / 'output').write_bytes(b'preserve for reconciliation')
                        raise error
                self.assertEqual((retained / 'output').read_bytes(), b'preserve for reconciliation')
                self.assertEqual(json.loads((case / 'retained-work.json').read_text())['workspace'], str(retained))
                # This fixture has no child or other writer; its owned output is reconciled.
                check.shutil.rmtree(retained)

    def browser_fixture(self, root):
        import ci_plan
        import json
        subject = dict(source_sha256='a' * 64, inventory_sha256='b' * 64)
        plan = check.c.freeze(dict(schema_version=1, mode='release',
            subject=dict(subject, configuration_sha256='c' * 64), inputs={}, checks=[dict(
                id='browser-archive', target='linux-x86_64', backend='hosted-web', scope='archive',
                environment='ubuntu-24.04', required=True, argv=['fixture'], timeout_seconds=5,
                warning_seconds=4, expected_tests=[])]))
        selection = ci_plan.browser_prerequisite('linux-x86_64', 'ubuntu-24.04', 'hosted-web')
        receipt = dict(schema_version=1, selection=selection,
            signing_key_fingerprint=ci_plan.MOZILLA_FINGERPRINT,
            installed=[dict(package='firefox', version='153.4.0+build1', architecture='amd64', policy='official origin fixture')],
            browser_version='Mozilla Firefox 153.4.0esr', plan=plan['id'], check='browser-archive', run_id='123', attempt=2)
        plan_path = root / 'plan.json'; plan_path.write_text(json.dumps(plan))
        receipt_path = root / 'browser.json'; receipt_path.write_text(json.dumps(receipt))
        options = dict(browser_prerequisite=receipt_path, browser_prerequisite_plan=plan_path,
                       browser='firefox', firefox='/usr/bin/firefox')
        host = dict(system='Linux', machine='x86_64', distribution='ubuntu-24.04')
        environment = dict(CHECK='browser-archive', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2')
        return subject, receipt, options, host, environment

    def test_browser_prerequisite_is_bound_to_actual_case_and_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subject, receipt, options, host, environment = self.browser_fixture(root)
            with patch.object(check.c, 'host_identity', return_value=host), patch.dict(check.os.environ, environment):
                state = check.browser_prerequisite_snapshot(options, 'linux-x86_64', 'hosted-web', 'archive', subject)
            evidence = root / 'evidence'; (evidence / 'browser').mkdir(parents=True)
            details = dict(browser=dict(status='passed', engine='firefox', browser_version='153.4.0'))
            check.bind_browser_prerequisite(state, details, evidence)
            self.assertEqual((evidence / 'browser/prerequisite.json').read_bytes(), options['browser_prerequisite'].read_bytes())
            self.assertEqual(details['browser_prerequisite']['sha256'], check.digest(evidence / 'browser/prerequisite.json'))
            self.assertEqual(details['browser_prerequisite']['plan'], receipt['plan'])

    def test_browser_prerequisite_rejects_wrong_scope_attempt_host_and_package(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subject, original, options, host, environment = self.browser_fixture(root)
            mutations = [lambda r: r.update(schema_version=True), lambda r: r.update(plan='d' * 64), lambda r: r.update(check='other'),
                         lambda r: r.update(run_id='124'), lambda r: r.update(attempt=1),
                         lambda r: r.update(attempt=True), lambda r: r['selection'].update(architecture='arm64'),
                         lambda r: r.update(signing_key_fingerprint='wrong'), lambda r: r.update(installed=[]),
                         lambda r: r['installed'][0].update(package='chromium'),
                         lambda r: r['installed'][0].update(architecture='arm64')]
            with patch.object(check.c, 'host_identity', return_value=host), patch.dict(check.os.environ, environment):
                for mutate in mutations:
                    receipt = copy.deepcopy(original); mutate(receipt)
                    options['browser_prerequisite'].write_text(json.dumps(receipt))
                    with self.assertRaises(ValueError):
                        check.browser_prerequisite_snapshot(options, 'linux-x86_64', 'hosted-web', 'archive', subject)
                options['browser_prerequisite'].write_text(json.dumps(original))
                for backend, scope in [('core', 'archive'), ('hosted-web', 'apt'), ('hosted-web', 'source')]:
                    with self.assertRaises(ValueError):
                        check.browser_prerequisite_snapshot(options, 'linux-x86_64', backend, scope, subject)
                with self.assertRaises(ValueError):
                    check.browser_prerequisite_snapshot(dict(options, firefox='unrelated'), 'linux-x86_64', 'hosted-web', 'archive', subject)
                host['distribution'] = 'debian-12'
                with self.assertRaises(ValueError):
                    check.browser_prerequisite_snapshot(options, 'linux-x86_64', 'hosted-web', 'archive', subject)

    def test_browser_prerequisite_mutation_or_different_runtime_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subject, receipt, options, host, environment = self.browser_fixture(root)
            with patch.object(check.c, 'host_identity', return_value=host), patch.dict(check.os.environ, environment):
                state = check.browser_prerequisite_snapshot(options, 'linux-x86_64', 'hosted-web', 'archive', subject)
            evidence = root / 'evidence'; (evidence / 'browser').mkdir(parents=True)
            for browser in (dict(status='failed', engine='firefox', browser_version='153.4.0'),
                            dict(status='passed', engine='chromium', browser_version='153.4.0'),
                            dict(status='passed', engine='firefox', browser_version='153.5.0')):
                with self.assertRaises(ValueError): check.bind_browser_prerequisite(state, dict(browser=browser), evidence)
            details = dict(browser=dict(status='passed', engine='firefox', browser_version='153.4.0'))
            for path in (state['path'], state['plan_path']):
                before = path.read_bytes(); path.write_bytes(before + b'\n')
                with self.assertRaisesRegex(ValueError, 'changed during'):
                    check.bind_browser_prerequisite(state, details, evidence)
                path.write_bytes(before)
            self.assertFalse((evidence / 'browser/prerequisite.json').exists())

    def fixture(self, root):
        machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
        target = platform.system().lower() + '-' + machine
        (root / 'release.json').write_text('{}')
        entry = {'target': target, 'backends': [], 'archive': 'app.tar.gz', 'manifest': 'app.json', 'sha256': 'b' * 64}
        return {'source': {'sha256': 'a' * 64}, 'artifacts': [entry]}, target

    @unittest.skipUnless(platform.system() == 'Linux', 'native Linux descendant fixture')
    def test_apt_timeout_stops_descendant_before_cleanup(self):
        import sys
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); pid = root / 'child.pid'
            script = ("import os,subprocess,sys,time; "
                      "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True); "
                      "open(sys.argv[1],'w').write(str(child.pid)); print('started',flush=True); time.sleep(60)")
            with self.assertRaises(check.AptCommandError) as caught:
                check.apt_command([sys.executable, '-c', script, str(pid)], root, timeout=1)
            self.assertTrue(caught.exception.writers_stopped)
            self.assertIn(b'started', caught.exception.output)
            self.assertFalse(Path('/proc/' + pid.read_text()).exists())

    def test_failed_apt_download_cleans_with_its_isolated_index_and_preserves_primary_error(self):
        from contextlib import ExitStack
        from subprocess import CompletedProcess
        from unittest.mock import Mock
        from types import ModuleType
        import sys
        import apt_repo
        import http.server
        import threading
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary); work = root / 'work'; evidence = root / 'evidence'
            commands = []
            receipt = dict(package='fixture.deb', version='1.0', payload={})
            def repository(receipts, output, *args):
                output.mkdir(); (output / 'archive-keyring.gpg').write_bytes(b'fixture public key')
            def executed(argv, cwd):
                commands.append(argv)
                if 'install' in argv:
                    return CompletedProcess(argv, 100, b'404 injected download failure')
                if 'purge' in argv:
                    self.assertIn('Dir::Etc::sourcelist=' + str(work / 'client-valid1/source.list'), argv)
                    return CompletedProcess(argv, 0, b'package is not installed, so not removed')
                return CompletedProcess(argv, 0, b'fixture command completed')
            def unmanaged(argv, **options):
                self.assertIn(argv[0], ('dpkg-query', 'gpg', 'gpgconf'))
                return CompletedProcess(argv, 1 if argv[0] == 'dpkg-query' else 0, b'fixture output')
            stack.enter_context(patch.object(check, 'apt_preflight'))
            stack.enter_context(patch.object(check, 'apt_command', side_effect=executed))
            stack.enter_context(patch.object(check.subprocess, 'run', side_effect=unmanaged))
            stack.enter_context(patch.object(apt_repo, 'package', return_value=receipt))
            stack.enter_context(patch.object(apt_repo, 'fingerprint', return_value='A' * 40))
            stack.enter_context(patch.object(apt_repo, 'repository', side_effect=repository))
            stack.enter_context(patch.object(apt_repo, 'verify_repository', return_value={}))
            server = Mock(); server.server_address = ('127.0.0.1', 12345)
            raw_socket = server.socket
            stack.enter_context(patch.object(http.server, 'ThreadingHTTPServer', return_value=server))
            # This case tests failed-download cleanup, with all transport mocked.
            # Slim offline SDK Python need not load its optional SSL extension.
            ssl = ModuleType('ssl')
            ssl.PROTOCOL_TLS_SERVER = object()
            context = Mock(spec=['load_cert_chain', 'wrap_socket'])
            ssl.SSLContext = Mock(return_value=context)
            stack.enter_context(patch.dict(sys.modules, {'ssl': ssl}))
            thread = Mock(); thread.is_alive.return_value = False
            stack.enter_context(patch.object(threading, 'Thread', return_value=thread))
            entry = dict(target='linux-x86_64', archive='app.tar.gz', manifest='app.json', sha256='b' * 64)
            with self.assertRaisesRegex(ValueError, 'unexpected outcome'):
                check.run_apt(root, entry, 'core', work, evidence)
            ssl.SSLContext.assert_called_once_with(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain.assert_called_once_with(work / 'ca.pem', work / 'tls.key')
            context.wrap_socket.assert_called_once_with(raw_socket, server_side=True)
            self.assertEqual(sum('install' in argv for argv in commands), 1)
            self.assertEqual(sum('purge' in argv for argv in commands), 1)
            self.assertIn(b'404 injected download failure', (evidence / 'apt.log').read_bytes())
            server.shutdown.assert_called_once(); server.server_close.assert_called_once()
            thread.join.assert_called_once()
            self.assertFalse((evidence / 'qualification.json').exists())

    def test_apt_cleanup_fixture_runs_without_optional_ssl_extension(self):
        import subprocess
        import sys
        script = (
            "import sys, unittest\n"
            "sys.modules.pop('ssl', None)\n"
            "sys.modules['_ssl'] = None\n"
            "try:\n import ssl\n"
            "except ImportError:\n pass\n"
            "else:\n raise SystemExit('SSL prerequisite unexpectedly available')\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from test_release_check import ReleaseCheckTests\n"
            "case = ReleaseCheckTests('test_failed_apt_download_cleans_with_its_isolated_index_and_preserves_primary_error')\n"
            "result = unittest.TestResult()\n"
            "case.run(result)\n"
            "if not result.wasSuccessful() or result.testsRun != 1 or result.skipped:\n"
            " raise SystemExit(str(result.errors + result.failures + result.skipped))\n"
            "print('mocked APT cleanup passed without optional SSL extension')\n")
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(Path(__file__).resolve().parent)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'mocked APT cleanup passed without optional SSL extension')

    def test_apt_refuses_ordinary_host_before_any_package_command(self):
        with patch.object(check, 'native_target'), patch.dict(check.os.environ, {}, clear=True), \
                patch.object(check.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'disposable root container'):
                check.apt_preflight('linux-x86_64')
            run.assert_not_called()

    def test_apt_receipt_requires_complete_adapter_and_binds_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest, target = self.fixture(root)
            def performed(candidate, entry, backend, work, evidence):
                (evidence / 'apt.log').write_bytes(b'actual adapter log fixture')
                return {'archive_sha256': entry['sha256'], 'checks': ['install', 'upgrade', 'purge']}
            with patch.object(check.release, 'verify_release', return_value=manifest), \
                    patch.object(check, 'run_apt', side_effect=performed) as apt:
                result = check.check(root, target, 'core', 'apt', root / 'evidence')
                self.assertEqual(apt.call_args.args[2], 'core')
                self.assertEqual(result['evidence'], {'apt.log': check.digest(root / 'evidence/apt.log')})
            with patch.object(check.release, 'verify_release', return_value=manifest), \
                    patch.object(check, 'run_apt', side_effect=ValueError('install failed')):
                with self.assertRaisesRegex(ValueError, 'install failed'):
                    check.check(root, target, 'core', 'apt', root / 'failed')
                self.assertFalse((root / 'failed/qualification.json').exists())

    def test_core_empty_gui_inventory_is_an_exact_scope(self):
        value = {'artifacts': [{'target': 'linux-x86_64', 'backends': []}]}
        self.assertIs(check.select(value, 'linux-x86_64', 'core'), value['artifacts'][0])
        for target, backend in [('linux-aarch64', 'core'), ('linux-x86_64', 'fltk')]:
            with self.assertRaises(ValueError):
                check.select(value, target, backend)
        value['artifacts'] *= 2
        with self.assertRaises(ValueError):
            check.select(value, 'linux-x86_64', 'core')

    def test_exact_archive_receipt_and_immutable_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, target = self.fixture(root)
            with patch.object(check.release, 'verify_release', return_value=manifest) as verify, patch.object(check.artifact, 'verify') as runtime:
                result = check.check(root, target, 'core', 'archive', root / 'evidence')
                self.assertEqual(verify.call_count, 2)
                self.assertEqual(runtime.call_args.kwargs['backend'], 'core')
                self.assertTrue(runtime.call_args.kwargs['runtime_only'])
                self.assertEqual(result['source_sha256'], manifest['source']['sha256'])
                self.assertEqual(result['inventory_sha256'], check.digest(root / 'release.json'))
                self.assertEqual(result['host'], check.c.host_identity())
                with self.assertRaisesRegex(ValueError, 'new attempt'):
                    check.check(root, target, 'core', 'archive', root / 'evidence')

    def test_candidate_mutation_or_runtime_failure_never_leaves_pass_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, target = self.fixture(root)
            def mutate(*args, **kwargs):
                (root / 'release.json').write_text('{"changed":true}')
            with patch.object(check.release, 'verify_release', return_value=manifest), patch.object(check.artifact, 'verify', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    check.check(root, target, 'core', 'archive', root / 'evidence')
                self.assertFalse((root / 'evidence/qualification.json').exists())
            with patch.object(check.release, 'verify_release', return_value=manifest), patch.object(check.artifact, 'verify', side_effect=ValueError('runtime failed')):
                with self.assertRaisesRegex(ValueError, 'runtime failed'):
                    check.check(root, target, 'core', 'archive', root / 'failure')
                self.assertFalse((root / 'failure/qualification.json').exists())

    def test_native_scope_rejects_wrong_os_architecture_and_browser(self):
        with patch.object(check.platform, 'system', return_value='Linux'), patch.object(check.platform, 'machine', return_value='x86_64'):
            check.native_target('linux-x86_64')
            for target in ('linux-aarch64', 'windows-x86_64', 'browser-wasm32'):
                with self.assertRaises(ValueError):
                    check.native_target(target)


if __name__ == '__main__':
    unittest.main()
