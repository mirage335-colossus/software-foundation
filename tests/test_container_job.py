import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('container_job', ROOT / '.github/scripts/container_job.py')
job = importlib.util.module_from_spec(spec); spec.loader.exec_module(job)
spec = importlib.util.spec_from_file_location('container_lifecycle', ROOT / '.github/scripts/lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec); spec.loader.exec_module(lifecycle)


class ContainerJobs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / 'checkout with spaces'
        self.root.mkdir()
        self.environment = {'FOUNDATION_HOST_UID': '1001', 'FOUNDATION_HOST_GID': '1002',
                            'FOUNDATION_DISPOSABLE_CHECK': '1', 'CHECK': 'browser-archive'}

    def test_host_ids_are_explicit_and_bootstrap_does_not_change_tree_permissions(self):
        command = job.command('sdk-produce', self.root, 1001, 1002, {'TARGET': 'linux-x86_64', 'GH_TOKEN': 'private'})
        self.assertIn('FOUNDATION_HOST_UID=1001', command)
        self.assertIn('FOUNDATION_HOST_GID=1002', command)
        self.assertIn('TARGET', command)
        self.assertIn(str(self.root) + ':/work', command)
        self.assertNotIn('GH_TOKEN', command)
        self.assertIn('build-essential', command[-3])
        self.assertNotIn('chown', command[-3]); self.assertNotIn('chmod', command[-3])
        self.assertNotIn('--init', command)
        self.assertEqual(command[-2:], ['container-job', 'sdk-produce'])
        for uid, gid in ((0, 1001), (1001, 0), ('1001', 1002), (True, 1002)):
            with self.assertRaises(ValueError): job.command('sdk-produce', self.root, uid, gid, {})
        with self.assertRaises(ValueError): job.command('check', self.root, 1001, 1002, {'CHECK_IMAGE': 'untrusted:tag'})

    def test_provider_and_recipe_cross_container_boundary_without_ambient_rust_overrides(self):
        command = job.command('application-build', self.root, 1001, 1002,
            {'CORE_PROVIDER': 'rust', 'FOUNDATION_PROVIDER_RECIPE': 'a' * 64,
             'RUSTFLAGS': 'ambient override', 'GH_TOKEN': 'private'})
        self.assertIn('CORE_PROVIDER', command)
        self.assertIn('FOUNDATION_PROVIDER_RECIPE', command)
        self.assertNotIn('RUSTFLAGS', command)
        self.assertNotIn('GH_TOKEN', command)

    def test_package_selection_avoids_gui_headers_for_runtime_or_core_producers(self):
        core = job.packages('application-build', {'PROFILE':'core'})
        gui = job.packages('sdk-produce', {'SDK_PROFILE':'all-gui'})
        runtime = job.packages('check', {}, {'scope':'archive','backend':'fltk'})
        self.assertNotIn('libx11-dev', core); self.assertNotIn('libx11-dev', runtime)
        self.assertIn('libx11-dev', gui); self.assertIn('libgl1', runtime)
        self.assertNotIn('build-essential', runtime)
        self.assertIn('build-essential', job.packages('check', {}, {'scope':'recovery','backend':'core'}))
        self.assertIn('sh tools/ci-apt.sh install', job.command('sdk-produce', self.root, 1001, 1002, {})[-3])
        # These lanes execute tools.offline_namespace, whose trusted PATH must
        # resolve the real ip command supplied by iproute2 before assertions run.
        for action in ('sdk-produce', 'application-build', 'native-gui-check'):
            with self.subTest(action=action):
                selected = job.packages(action, {})
                self.assertIn('iproute2', selected)
                self.assertEqual(job.bootstrap_script(selected).split().count('iproute2'), 1)
        for scope in ('source', 'recovery'):
            with self.subTest(scope=scope):
                selected = job.packages('check', {}, {'scope':scope, 'backend':'core'})
                self.assertIn('iproute2', selected)
                self.assertEqual(job.bootstrap_script(selected).split().count('iproute2'), 1)

    def test_batch_setup_is_committed_once_and_each_case_uses_a_fresh_run(self):
        calls=[]; identity='sha256:'+'d'*64
        def run(argv, **options):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, identity+'\n' if argv[1] == 'commit' else '')
        items=[{'scope':'archive','backend':'fltk'}, {'scope':'archive','backend':'terminal'}]
        with patch.object(job.subprocess, 'run', side_effect=run):
            with job.prepared_checks(self.root, 'debian:bookworm', items, {}) as prepared:
                self.assertEqual(prepared, identity)
                with patch.object(job, 'selection', return_value=items[0]):
                    one=job.command('check', self.root, 1001, 1002, {'CHECK_IMAGE':'debian:bookworm'}, prepared_image=prepared)
                    two=job.command('check', self.root, 1001, 1002, {'CHECK_IMAGE':'debian:bookworm'}, prepared_image=prepared)
                self.assertEqual(one[:4], ['docker','run','--rm','-e'])
                self.assertEqual(one, two); self.assertIn(identity, one)
                self.assertNotIn('apt-get', one[-3]); self.assertNotIn('ci-apt.sh', one[-3])
                self.assertIn('--inside', one[-3])
        self.assertEqual([row[1] for row in calls], ['create','start','commit','rm','image'])
        self.assertNotIn('useradd', calls[0][-1])
        self.assertNotIn('check-prerequisites', calls[0][-1])

    def test_batch_setup_failure_or_case_failure_joins_before_exact_resource_cleanup(self):
        identity='sha256:'+'e'*64
        for fail in ('start', 'case'):
            calls=[]
            def run(argv, **options):
                calls.append(argv)
                if argv[1] == fail: raise subprocess.CalledProcessError(7,argv)
                return subprocess.CompletedProcess(argv,0,identity+'\n' if argv[1]=='commit' else '')
            with self.subTest(fail=fail), patch.object(job.subprocess,'run',side_effect=run):
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    with job.prepared_checks(self.root,'debian:bookworm',[{'scope':'archive','backend':'core'}],{}):
                        raise ValueError('case failed')
            self.assertEqual(calls[-1][1], 'rm' if fail == 'start' else 'image')
            self.assertEqual(sum(row[1]=='rm' for row in calls),1)
            self.assertFalse(any('--force' in row for row in calls))
        with self.assertRaises(ValueError):
            job.command('application-build', self.root, 1001, 1002, {}, prepared_image=identity)

    def test_builder_creation_uses_matching_ids_and_reuses_only_existing_group(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0 if argv[:2] == ['getent', 'group'] else 2 if argv[0] == 'getent' else 0)
        with patch.object(job.subprocess, 'run', side_effect=run): job.create_account(1001, 1002)
        self.assertNotIn('groupadd', [row[0] for row in calls])
        self.assertEqual(calls[-1], ['useradd','--create-home','--uid','1001','--gid','1002','sdkbuilder'])
        with patch.object(job.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            with self.assertRaisesRegex(ValueError, 'already exists'): job.create_account(1001, 1002)
            self.assertEqual(run.call_count, 1)

    def run_inside(self, action, scope='archive', fail=False):
        events = []
        def run(argv, **kwargs):
            events.append(('run', argv))
            if fail and argv[-1] == action:
                raise subprocess.CalledProcessError(7, argv)
            return subprocess.CompletedProcess(argv, 0)
        def handoff(root, names, uid, gid): events.append(('handoff', names))
        with patch.object(job.os, 'geteuid', return_value=0, create=True), \
                patch.object(job.Path, 'is_file', return_value=True), \
                patch.object(job, 'create_account') as account, \
                patch.object(job, 'selection', return_value={'id':'browser-archive','scope':scope}), \
                patch.object(job, 'handoff', side_effect=handoff), \
                patch.object(job.subprocess, 'run', side_effect=run):
            if fail:
                with self.assertRaises(subprocess.CalledProcessError): job.inside(action, self.root, self.environment)
            else: job.inside(action, self.root, self.environment)
            account.assert_called_once_with(1001,1002)
        return events

    def test_build_and_consumer_actions_drop_privilege_with_selected_account(self):
        for action in ('sdk-produce','application-build','native-gui-check'):
            with self.subTest(action=action):
                events = self.run_inside(action)
                self.assertEqual(events[0][1][:5], ['runuser','-u','sdkbuilder','--','xvfb-run'])
                self.assertEqual(events[0][1][-1], action)
                self.assertEqual(events[-1], ('handoff', ()))

    def test_browser_setup_precedes_unprivileged_check_and_receipt_handoff(self):
        events = self.run_inside('check')
        self.assertEqual(events[0][1][-1], 'check-prerequisites')
        self.assertEqual(events[1], ('handoff', ('build/prerequisites/browser-archive',)))
        self.assertEqual(events[2][1][:5], ['runuser','-u','sdkbuilder','--','xvfb-run'])
        self.assertEqual(events[2][1][-1], 'check')

    def test_only_apt_scopes_keep_root_and_handoff_failure_evidence(self):
        for action in ('check', 'apt-native-smoke'):
            with self.subTest(action=action):
                events = self.run_inside(action, scope='apt', fail=True)
                runs = [value for kind,value in events if kind == 'run']
                self.assertFalse(any(argv[0] == 'runuser' for argv in runs))
                self.assertEqual(runs[-1][0], 'xvfb-run')
                self.assertEqual(events[-1][0], 'handoff')
                self.assertTrue(events[-1][1])
                self.assertTrue(all(value.startswith(('build/evidence/','build/prerequisites/','build/apt-evidence'))
                                    for value in events[-1][1]))

    def test_handoff_preserves_private_file_bytes_and_modes_and_avoids_other_trees(self):
        directory = self.root / 'build/evidence/check'; directory.mkdir(parents=True)
        private = directory / 'receipt.json'; private.write_bytes(b'{"retained":true}');private.chmod(0o600)
        outside = self.root / 'build/sdk'; outside.mkdir(); (outside/'compiler').write_bytes(b'unchanged')
        directory.parent.chmod(0o700)
        mode = stat.S_IMODE(private.stat().st_mode)
        with patch.object(job.os, 'chown', create=True) as chown:
            job.handoff(self.root, ('build/evidence/check',), 1001, 1002)
        self.assertEqual(private.read_bytes(), b'{"retained":true}')
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), mode)
        self.assertTrue(chown.called)
        self.assertIn(directory.parent, [call.args[0] for call in chown.call_args_list])
        self.assertIn(self.root / 'build', [call.args[0] for call in chown.call_args_list])
        for call in chown.call_args_list:
            self.assertNotIn(outside, call.args[0].parents)
            self.assertEqual(call.kwargs, {'follow_symlinks':False})
        with self.assertRaises(ValueError): job.handoff(self.root, ('../outside',), 1001, 1002)

    def test_actual_same_owner_handoff_preserves_private_bytes_and_modes(self):
        directory = self.root / 'build/evidence/private check'; directory.mkdir(parents=True)
        private = directory / 'receipt.json'; private.write_bytes(b'{"retained":true}'); private.chmod(0o600)
        directory.parent.chmod(0o700)
        outside = self.root / 'build/sdk'; outside.mkdir(); compiler = outside / 'compiler'
        compiler.write_bytes(b'retained'); compiler.chmod(0o600)
        paths = [directory.parent, directory, private, outside, compiler]
        before = {path: (path.stat().st_uid, path.stat().st_gid, stat.S_IMODE(path.stat().st_mode)) for path in paths}
        job.handoff(self.root, ('build/evidence/private check',), os.getuid(), os.getgid())
        self.assertEqual(private.read_bytes(), b'{"retained":true}')
        self.assertEqual(compiler.read_bytes(), b'retained')
        self.assertEqual(before, {path: (path.stat().st_uid, path.stat().st_gid, stat.S_IMODE(path.stat().st_mode)) for path in paths})

    def test_handoff_rejects_linked_evidence_before_owner_changes(self):
        directory = self.root / 'build/evidence/check'; directory.mkdir(parents=True)
        outside = self.root / 'outside'; outside.write_text('retained')
        os.link(outside, directory/'alias')
        with patch.object(job.os, 'chown', create=True) as chown:
            with self.assertRaisesRegex(ValueError, 'links'): job.handoff(self.root, ('build/evidence/check',),1001,1002)
            chown.assert_not_called()
        self.assertEqual(outside.read_text(),'retained')

    def test_cleanup_diagnostic_keeps_original_failed_command(self):
        def run(argv, **kwargs):
            if argv[0] == 'xvfb-run':
                raise subprocess.CalledProcessError(7, argv)
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(job.os, 'geteuid', return_value=0, create=True), \
                patch.object(job.Path, 'is_file', return_value=True), \
                patch.object(job, 'create_account'), \
                patch.object(job, 'handoff', side_effect=ValueError('evidence handoff failed')), \
                patch.object(job.subprocess, 'run', side_effect=run):
            with self.assertRaises(ValueError) as caught:
                job.inside('apt-native-smoke', self.root, self.environment)
        message = job.diagnostic(caught.exception)
        self.assertIn('evidence handoff failed', message)
        self.assertIn('exit status 7', message)

    def test_development_sdk_mode_crosses_container_boundary_without_credentials(self):
        command = job.command('native-gui-check', self.root, 1001, 1002,
                              {'SDK_DEVELOPMENT': 'true', 'GH_TOKEN': 'not-forwarded'})
        self.assertIn('SDK_DEVELOPMENT', command)
        self.assertNotIn('GH_TOKEN', command); self.assertNotIn('not-forwarded', command)

    def test_all_workflow_callers_use_common_host_identity_adapter(self):
        actions = {'sdk-maintenance':'sdk-produce','sdk-application':'application-build',
                   'native-gui':'native-gui-check','candidate':'apt-native-smoke'}
        for filename, action in actions.items():
            text = (ROOT/'.github/workflows'/f'{filename}.yml').read_text()
            self.assertIn("'.github/scripts/container_job.py', '"+action+"'", text)
            self.assertNotIn("subprocess.run(['docker'",text)
        certification=(ROOT/'.github/workflows/certify.yml').read_text()
        self.assertIn("'.github/scripts/lifecycle.py', 'check-batch'", certification)
        batching=(ROOT/'.github/scripts/lifecycle.py').read_text()
        self.assertIn("str(ROOT / '.github/scripts/container_job.py'), 'check'", batching)
        self.assertNotIn("subprocess.run(['docker'", certification + batching)
        text=(ROOT/'.github/workflows/sdk-application.yml').read_text()
        self.assertIn('graphics_archive_url:',text)
        self.assertIn('build/produced/graphics-qualification.json',text)
        self.assertIn("runner.os == 'Windows' && inputs.profile == 'all-gui'",text)


class OfflineContainers(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source, self.output, self.group = [self.root / name for name in ('source with spaces', 'output', 'group')]
        for path in (self.source, self.output, self.group): path.mkdir()
        (self.output / 'sdk').mkdir(); (self.output / 'sdk/sdk.json').write_text('{}')
        self.image = 'sha256:' + 'a' * 64

    def command(self, phase='execute', target='linux-x86_64', *, rust_group=None):
        return job.offline_command(self.source, self.output, self.group, 1001, 1002, self.image, phase,
                                   target=target, rust_group=rust_group)

    def test_offline_launch_is_disconnected_readonly_and_has_only_declared_mounts(self):
        command = self.command()
        for value in ('--network=none', '--pull=never', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges'):
            self.assertIn(value, command)
        self.assertEqual(command[command.index('--user') + 1], '1001:1002')
        mounts = [command[index + 1] for index, value in enumerate(command) if value == '--mount']
        self.assertEqual(mounts, [f'type=bind,source={self.source},target=/work,readonly',
                                 f'type=bind,source={self.output},target=/output',
                                 f'type=bind,source={self.group},target=/inputs/group,readonly',
                                 f'type=bind,source={self.output / "sdk"},target=/output/sdk,readonly'])
        self.assertNotIn('GH_TOKEN', command); self.assertNotIn('apt-get', command)
        self.assertNotIn('ci-apt.sh', command); self.assertNotIn('/var/run/docker.sock', command)
        self.assertIn('CCACHE_DISABLE=1', command); self.assertIn('HOME=/output/home', command)
        self.assertIn('xvfb-run', command)

    def test_native_display_execution_uses_bundled_init_before_xvfb(self):
        for target in ('linux-x86_64', 'linux-aarch64'):
            with self.subTest(target=target):
                command = self.command(target=target)
                self.assertIn('--init', command[:command.index(self.image)])
                self.assertEqual(command[command.index(self.image) + 1:command.index(self.image) + 3],
                                 ['xvfb-run', '-a'])
                self.assertEqual(command[command.index('--user') + 1], '1001:1002')
                self.assertNotIn('--privileged', command)

    def test_stage_and_wasm_do_not_require_a_display_or_mount_an_unrestored_sdk(self):
        stage = self.command('stage')
        self.assertNotIn('xvfb-run', stage)
        self.assertNotIn('--init', stage)
        self.assertEqual(sum(value == '--mount' for value in stage), 3)
        wasm = self.command(target='browser-wasm32')
        self.assertNotIn('xvfb-run', wasm)
        self.assertNotIn('--init', wasm)
        (self.output / 'sdk/sdk.json').unlink()
        with self.assertRaisesRegex(ValueError, 'completed SDK restoration'): self.command()
        self.command('stage')

    def test_unpinned_images_root_identity_and_mount_separator_fail_closed(self):
        for image, uid, gid in (('debian:bookworm', 1001, 1002), (self.image, 0, 1002), (self.image, 1001, 0)):
            with self.subTest(image=image, uid=uid, gid=gid), self.assertRaises(ValueError):
                job.offline_command(self.source, self.output, self.group, uid, gid, image, 'stage', target='linux-x86_64')
        comma = self.root / 'source,with-comma'; comma.mkdir()
        with self.assertRaisesRegex(ValueError, 'bind mount'):
            job.offline_command(comma, self.output, self.group, 1001, 1002, self.image, 'stage', target='linux-x86_64')

    def test_optional_rust_inputs_are_read_only_and_execution_protects_both_restored_sdks(self):
        rust_group = self.root / 'retained Rust group'; rust_group.mkdir()
        stage = self.command('stage', rust_group=rust_group)
        mounts = [stage[index + 1] for index, value in enumerate(stage) if value == '--mount']
        self.assertEqual(mounts[-1], f'type=bind,source={rust_group},target=/inputs/rust-group,readonly')
        self.assertEqual(len(mounts), 4)
        self.assertFalse(any('target=/output/rust-sdk' in item for item in mounts))
        with self.assertRaisesRegex(ValueError, 'completed SDK restoration: rust-sdk'):
            self.command(rust_group=rust_group)
        rust_sdk = self.output / 'rust-sdk'; rust_sdk.mkdir()
        (rust_sdk / 'rust-sdk.json').write_text('{}')
        execute = self.command(rust_group=rust_group)
        mounts = [execute[index + 1] for index, value in enumerate(execute) if value == '--mount']
        self.assertEqual(mounts[-2:], [f'type=bind,source={self.output / "sdk"},target=/output/sdk,readonly',
                                      f'type=bind,source={rust_sdk},target=/output/rust-sdk,readonly'])
        self.assertEqual(len(mounts), 6)
        self.assertIn('--network=none', execute); self.assertIn('--cap-drop=ALL', execute)
        self.assertNotIn('/inputs/rust-group', ' '.join(self.command()))

    def test_rust_input_separator_aliases_and_restored_root_or_receipt_links_fail_closed(self):
        rust_group = self.root / 'rust-group'; rust_group.mkdir()
        invalid = self.root / 'rust,group'; invalid.mkdir()
        with self.assertRaisesRegex(ValueError, 'bind mount'):
            self.command('stage', rust_group=invalid)
        alias = self.root / 'rust-group-alias'; alias.symlink_to(rust_group, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary canonical directory'):
            self.command('stage', rust_group=alias)
        rust_sdk = self.output / 'rust-sdk'; rust_sdk.mkdir()
        receipt = rust_sdk / 'rust-sdk.json'
        with self.assertRaisesRegex(ValueError, 'completed SDK restoration: rust-sdk'):
            self.command(rust_group=rust_group)
        receipt.write_text('{}')
        receipt.rename(rust_sdk / 'receipt.json'); receipt.symlink_to('receipt.json')
        with self.assertRaisesRegex(ValueError, 'completed SDK restoration: rust-sdk'):
            self.command(rust_group=rust_group)
        receipt.unlink(); (rust_sdk / 'receipt.json').rename(receipt)
        rust_sdk.rename(self.output / 'other-sdk'); rust_sdk.symlink_to('other-sdk', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'completed SDK restoration: rust-sdk'):
            self.command(rust_group=rust_group)


class BrowserPrivilegeSplit(unittest.TestCase):
    def test_setup_receipt_is_frozen_and_check_does_not_reinstall_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan={'id':'a'*64,'checks':[{'id':'one','target':'linux-x86_64','environment':'chromium',
                                       'backend':'wasm','scope':'archive'}]}
            environment={'CHECK':'one','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'2'}
            with patch.object(lifecycle,'ROOT',root), patch.object(lifecycle.os,'chdir'), patch.dict(os.environ,environment), \
                    patch.object(lifecycle.evidence,'load',return_value=plan), \
                    patch.object(lifecycle.evidence,'validate') as validate, \
                    patch.object(lifecycle.evidence,'check_inputs') as check_inputs, \
                    patch.object(lifecycle.ci.platform,'system',return_value='Linux'), \
                    patch.object(lifecycle.ci,'needs_browser_prerequisite',return_value=True), \
                    patch.object(lifecycle.ci,'install_browser_prerequisite',return_value={'selection':{'engine':'chromium'}}) as install, \
                    patch.object(lifecycle.evidence,'write_new') as write, \
                    patch.object(lifecycle.evidence,'run_case',return_value={'status':'passed'}) as run:
                lifecycle.main('check-prerequisites')
                install.assert_called_once();run.assert_not_called()
                self.assertEqual(write.call_args.args[1]['plan'], plan['id'])
                self.assertEqual(write.call_args.args[1]['attempt'],2)
                self.assertEqual(write.call_args.args[1]['run_id'],'123')
                with self.assertRaisesRegex(ValueError,'explicit browser prerequisite'):
                    lifecycle.main('check')
                receipt=root/'build/prerequisites/one/browser.json';receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text('{}')
                lifecycle.main('check')
                self.assertEqual(install.call_count,1)
                run.assert_called_once()
                self.assertGreaterEqual(validate.call_count,3);self.assertEqual(check_inputs.call_count,3)
