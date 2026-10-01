"""Complete SDK byte retention does not grant consumer or publication approval."""
import importlib.util
import copy
import hashlib
import io
import zipfile
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import dependency_archive as archive
import dependency_store as store
import sdk_windows

spec = importlib.util.spec_from_file_location('retention_lifecycle', ROOT / '.github/scripts/lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec); spec.loader.exec_module(lifecycle)


class SdkRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / 'owned checkout'; self.root.mkdir()
        shutil.copytree(ROOT / 'third_party/sdk', self.root / 'third_party/sdk')
        self.recipe_file = self.root / 'third_party/sdk/windows-base.json'
        self.recipe = sdk_windows.recipe_identity(self.recipe_file)
        self.group = self.root / 'build/sdk-group'
        provenance = json.loads(self.recipe_file.read_text())
        policy = json.loads((self.recipe_file.parent / 'windows-toolchain.json').read_text())
        provenance.update(linker_version='14.44.35207', windows_sdk=policy['windows_sdk'])
        provenance_path = self.root / 'provenance.json'; archive.write_json(provenance_path, provenance)
        sdk_windows.empty_base(self.recipe_file, provenance_path, self.group)
        self.files = store.verify_group(self.group, self.recipe)
        archive.write_json(self.root / 'build/sdk-origin.json', {'origin': 'base', 'recipe': self.recipe})
        self.environment = {'TARGET': 'windows-x86_64', 'SDK_PROFILE': 'core', 'JOBS': '2',
            'GITHUB_SHA': 'a' * 40, 'GITHUB_REPOSITORY': 'example/foundation',
            'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2',
            'GITHUB_OUTPUT': str(self.root / 'step-output')}
        self.addCleanup(patch.stopall)
        patch.object(lifecycle, 'ROOT', self.root).start()
        previous = Path.cwd(); lifecycle.os.chdir(self.root)
        self.addCleanup(lifecycle.os.chdir, previous)
        patch.dict(lifecycle.os.environ, self.environment).start()
        self.publisher = patch.object(lifecycle.delivery, 'publish_base', side_effect=AssertionError('unexpected publication')).start()

    def receipt(self): return json.loads((self.root / 'build/sdk-retention.json').read_text())

    def test_failed_consumer_keeps_failure_and_complete_group_can_be_retained(self):
        with patch.object(lifecycle.ci, 'assert_host'), \
             patch.object(lifecycle.ci, 'prepared_check', side_effect=RuntimeError('consumer assertion failed')):
            with self.assertRaisesRegex(RuntimeError, 'consumer assertion failed'):
                lifecycle.main('sdk-produce')
        self.assertFalse((self.root / 'build/sdk-publication-plan.json').exists())
        lifecycle.main('sdk-retain')
        receipt = self.receipt()
        self.assertEqual(receipt['files'], self.files)
        self.assertEqual((receipt['status'], receipt['qualification'], receipt['publication_approved']),
                         ('verified', 'unqualified', False))
        self.assertEqual((receipt['target'], receipt['profile'], receipt['recipe_id']),
                         ('windows-x86_64', 'core', self.recipe))
        self.assertEqual((receipt['source_commit'], receipt['run_id'], receipt['attempt']), ('a' * 40, '123', 2))
        self.assertEqual((self.root / 'step-output').read_text(), 'retained=true\n')
        self.assertEqual(store.verify_group(self.group, self.recipe), self.files)
        self.publisher.assert_not_called()

    def test_retained_group_stays_compatible_with_existing_offline_install(self):
        lifecycle.main('sdk-retain')
        copied = self.root / 'relocated group'
        self.assertEqual(store.copy_group(self.group, copied, self.recipe), self.files)
        installed = sdk_windows.install(copied, self.recipe, self.root / 'relocated dependencies', '14.44.35207')
        self.assertEqual(installed['recipe_id'], self.recipe)
        self.assertEqual(installed['target']['system'], 'Windows')
        self.assertEqual(self.receipt()['qualification'], 'unqualified')
        self.publisher.assert_not_called()

    def test_current_recipe_profile_and_origin_are_revalidated(self):
        origin = self.root / 'build/sdk-origin.json'
        for target, profile in [('windows-x86_64', 'all-gui'), ('linux-x86_64', 'core'), ('browser-wasm32', 'core')]:
            with self.subTest(target=target, profile=profile), patch.dict(lifecycle.os.environ, {'TARGET': target, 'SDK_PROFILE': profile}):
                with self.assertRaisesRegex(ValueError, 'selected current recipe'): lifecycle.main('sdk-retain')
        archive.write_json(origin, {'origin': 'base', 'recipe': 'b' * 64})
        with self.assertRaisesRegex(ValueError, 'selected current recipe'): lifecycle.main('sdk-retain')
        archive.write_json(origin, {'origin': 'base', 'recipe': self.recipe})
        self.recipe_file.write_text(self.recipe_file.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'selected current recipe'): lifecycle.main('sdk-retain')
        self.assertFalse((self.root / 'build/sdk-retention.json').exists())
        self.assertFalse((self.root / 'step-output').exists())

    def test_incomplete_or_unexpected_group_files_never_emit_retention_success(self):
        name = store.names(self.recipe)[1]; data = (self.group / name).read_bytes()
        (self.group / name).unlink()
        with self.assertRaisesRegex(ValueError, 'exactly'): lifecycle.main('sdk-retain')
        (self.group / name).write_bytes(data)
        (self.group / 'foreign.txt').write_text('must remain visible')
        with self.assertRaisesRegex(ValueError, 'exactly'): lifecycle.main('sdk-retain')
        self.assertEqual((self.group / 'foreign.txt').read_text(), 'must remain visible')
        self.assertFalse((self.root / 'build/sdk-retention.json').exists())
        self.assertFalse((self.root / 'step-output').exists())

    def test_changed_inner_content_is_rejected_even_with_rewritten_outer_checksums(self):
        binary, source, sums = store.names(self.recipe)
        extracted = self.root / 'changed binary'; archive.extract(self.group / binary, extracted)
        (extracted / 'prefix/README.txt').write_text('changed after sealing')
        (self.group / binary).unlink(); archive.archive_tree(extracted, self.group / binary)
        (self.group / sums).write_text(''.join(archive.digest(self.group / name) + '  ' + name + '\n'
                                             for name in (binary, source)))
        with self.assertRaisesRegex(ValueError, 'manifest'): lifecycle.main('sdk-retain')
        self.assertFalse((self.root / 'build/sdk-retention.json').exists())
        self.assertFalse((self.root / 'step-output').exists())

    def test_refuses_to_replace_existing_receipt(self):
        receipt = self.root / 'build/sdk-retention.json'; receipt.write_text('foreign receipt')
        with self.assertRaises(FileExistsError): lifecycle.main('sdk-retain')
        self.assertEqual(receipt.read_text(), 'foreign receipt')
        self.assertFalse((self.root / 'step-output').exists())

    def test_unknown_target_or_profile_cannot_select_a_fallback_recipe(self):
        for target, profile in [('unknown', 'core'), ('windows-x86_64', 'unknown')]:
            with self.subTest(target=target, profile=profile), self.assertRaisesRegex(ValueError, 'unknown SDK'):
                lifecycle.sdk_identity(target, profile)

    def test_workflow_retains_only_verified_group_without_masking_failure(self):
        text = (ROOT / '.github/workflows/sdk-maintenance.yml').read_text()
        retention = text.split('    - name: Verify complete SDK bytes', 1)[1].split('    - uses:', 1)[0]
        self.assertIn('id: retain', retention); self.assertIn('if: always()', retention)
        self.assertIn('lifecycle.py sdk-retain', retention)
        group = text.split('name: sdk-group-', 1)[0].rsplit('    - uses:', 1)[1]
        self.assertIn("if: always() && steps.retain.outcome == 'success' && steps.retain.outputs.retained == 'true'", group)
        self.assertNotIn('continue-on-error', text)
        publication = text.split('  publish:', 1)[1]
        self.assertIn('    if: inputs.execute\n    needs: produce\n', publication)
        self.assertNotIn('always()', publication.split('    steps:', 1)[0])
        self.assertIn('          build/sdk-retention.json\n', text)
        self.assertIn('sdk_retention', (ROOT / 'CMakeLists.txt').read_text())



class RetainedSdkRecoveryTests(unittest.TestCase):
    setUp = SdkRetentionTests.setUp

    def prepare(self):
        self.repository = 'example/foundation'
        self.request = dict(schema_version=1, repository=self.repository, target='windows-x86_64', profile='core',
            recipe_id=self.recipe, run_id=123, source_commit='a' * 40, attempt=2, job_id=456,
            group={'id': 789, 'sha256': '0' * 64}, proof={'id': 790, 'sha256': '0' * 64})
        self.repo = {'id': 42, 'full_name': self.repository}
        self.run = dict(id=123, run_attempt=2, head_sha='a' * 40, status='in_progress', conclusion=None,
            event='workflow_dispatch', path='.github/workflows/sdk-maintenance.yml',
            repository=self.repo.copy(), head_repository=self.repo.copy())
        self.job = dict(id=456, run_id=123, run_attempt=2, head_sha='a' * 40,
            name='produce (windows-x86_64, windows-2022)', status='completed', conclusion='failure',
            started_at='2026-01-01T12:00:00Z', completed_at='2026-01-01T13:00:00Z')
        self.base = 'repos/' + self.repository
        self.rows = {self.base: self.repo, self.base + '/actions/runs/123/attempts/2': self.run,
                     self.base + '/actions/jobs/456': self.job}
        self.receipt_value = dict(schema_version=1, status='verified', qualification='unqualified',
            publication_approved=False, target='windows-x86_64', profile='core', recipe_id=self.recipe,
            source_commit='a' * 40, run_id='123', attempt=2, files=self.files)
        self.proof = {'sdk-retention.json': archive.encoded(self.receipt_value),
                      'sdk-origin.json': archive.encoded({'origin':'rebuild', 'recipe':self.recipe}),
                      'other-report.txt': b'No extraction of unrelated proof files.\n'}
        self.payloads = {}; self.downloads = []
        self.pack('group', {p.name:p.read_bytes() for p in self.group.iterdir()})
        self.pack('proof', self.proof)
        from unittest.mock import Mock
        self.transport = Mock(); self.transport.json.side_effect = lambda endpoint: copy.deepcopy(self.rows[endpoint])

    def pack(self, kind, entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as stream:
            for name, data in (entries.items() if isinstance(entries, dict) else entries): stream.writestr(name, data)
        raw = buffer.getvalue(); artifact_id = self.request[kind]['id']; self.payloads[artifact_id] = raw
        digest = hashlib.sha256(raw).hexdigest(); self.request[kind]['sha256'] = digest
        self.rows[self.base + '/actions/artifacts/' + str(artifact_id)] = dict(id=artifact_id,
            name='sdk-' + kind + '-windows-x86_64-2', size_in_bytes=len(raw), expired=False, digest='sha256:' + digest,
            created_at='2026-01-01T12:59:00Z', workflow_run=dict(id=123, repository_id=42, head_repository_id=42, head_sha='a'*40))

    def download(self, repository, artifact_id, output):
        self.assertEqual(repository, self.repository); self.downloads.append(artifact_id)
        with output.open('xb') as stream: stream.write(self.payloads[artifact_id])

    def recover(self):
        return lifecycle.ci.retained_sdk(self.repository, self.request, 'windows-x86_64', 'core', self.recipe,
            self.root / 'restored group', transport=self.transport, download=self.download)

    def test_completed_failed_job_with_active_siblings_reuses_exact_unqualified_triplet(self):
        self.prepare(); result = self.recover()
        self.assertEqual(store.verify_group(self.root / 'restored group', self.recipe), self.files)
        self.assertEqual(self.downloads, [789, 790]); self.assertEqual(result['origin'], 'retained')
        self.assertEqual(result['qualification'], 'unqualified'); self.assertIs(result['publication_approved'], False)
        self.assertEqual(result['request'], self.request); self.assertEqual(result['retention'], self.receipt_value)
        self.assertFalse((self.root / 'other-report.txt').exists()); self.publisher.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'must be new'): self.recover()

    def test_exact_request_rejects_mismatch_unknown_fields_and_coerced_identifiers(self):
        self.prepare(); original = copy.deepcopy(self.request)
        mutations = [('repository','other/foundation'), ('target','linux-x86_64'), ('profile','all-gui'),
            ('recipe_id','b'*64), ('source_commit','main'), ('run_id', '123'), ('attempt', True),
            ('job_id', 0), ('unexpected',1), ('group',{'id':789,'sha256':'x'}), ('proof',original['group'])]
        for key, value in mutations:
            with self.subTest(key=key):
                self.request = copy.deepcopy(original); self.request[key] = value
                with self.assertRaises(ValueError): self.recover()
        self.assertFalse(self.downloads)

    def test_wrong_or_unfinished_producer_is_rejected_before_download(self):
        self.prepare()
        mutations = [(self.run,'id',124), (self.run,'run_attempt',1), (self.run,'head_sha','b'*40),
            (self.run,'path','.github/workflows/candidate.yml'), (self.run,'event','pull_request'),
            (self.run,'head_repository',{'id':43,'full_name':'fork/foundation'}),
            (self.run,'repository',{'id':42,'full_name':'other/foundation'}),
            (self.job,'id',457), (self.job,'run_id',125), (self.job,'run_attempt',1),
            (self.job,'head_sha','c'*40), (self.job,'name','produce (linux-x86_64, ubuntu-24.04)'),
            (self.job,'status','in_progress'), (self.job,'conclusion','cancelled'),
            (self.job,'completed_at','2026-01-01T11:00:00Z')]
        for row, key, value in mutations:
            original = row[key]
            with self.subTest(key=key, value=value):
                row[key] = value
                with self.assertRaises(ValueError): self.recover()
                row[key] = original
        self.assertFalse(self.downloads)

    def test_artifact_metadata_must_bind_bytes_repository_run_target_and_job_interval(self):
        self.prepare(); row = self.rows[self.base + '/actions/artifacts/789']
        for key, value in [('id',791), ('name','sdk-group-windows-x86_64-1'), ('expired',True),
                           ('digest','sha256:'+'b'*64), ('size_in_bytes',0),
                           ('created_at','2026-01-01T11:59:59Z'), ('created_at','2026-01-01T13:00:01Z')]:
            original = row[key]
            with self.subTest(key=key, value=value):
                row[key] = value
                with self.assertRaises(ValueError): self.recover()
                row[key] = original
        for key, value in [('id',124), ('repository_id',43), ('head_repository_id',43), ('head_sha','b'*40)]:
            original = row['workflow_run'][key]; row['workflow_run'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.recover()
            row['workflow_run'][key] = original
        self.assertFalse(self.downloads)

    def test_corrupt_download_or_changed_remote_metadata_never_publishes_group(self):
        self.prepare(); self.payloads[789] += b'changed'
        with self.assertRaisesRegex(ValueError, 'pinned bytes'): self.recover()
        self.assertFalse((self.root/'restored group').exists())
        self.prepare()
        count = 0
        def changed(endpoint):
            nonlocal count
            value = copy.deepcopy(self.rows[endpoint])
            if endpoint.endswith('/artifacts/789'):
                count += 1
                if count > 1: value['expired'] = True
            return value
        self.transport.json.side_effect = changed
        with self.assertRaisesRegex(ValueError, 'changed during verification'): self.recover()
        self.assertFalse((self.root/'restored group').exists())

    def test_receipt_and_origin_are_read_bounded_and_revalidated(self):
        self.prepare()
        for key, value in [('schema_version',True), ('qualification','qualified'), ('status','passed'),
            ('publication_approved',True), ('recipe_id','b'*64), ('target','linux-x86_64'),
            ('profile','all-gui'), ('run_id','124'), ('attempt',1), ('source_commit','b'*40), ('files',{})]:
            with self.subTest(key=key):
                receipt = dict(self.receipt_value, **{key:value})
                self.pack('proof',dict(self.proof, **{'sdk-retention.json':archive.encoded(receipt)}))
                with self.assertRaises(ValueError): self.recover()
        for entry in ({'origin':'rebuild','recipe':'b'*64}, {'origin':'unknown','recipe':self.recipe}, []):
            self.pack('proof',dict(self.proof, **{'sdk-origin.json':archive.encoded(entry)}))
            with self.assertRaises(ValueError): self.recover()
        for entries in ({'sdk-origin.json':b'{}'}, dict(self.proof, **{'sdk-retention.json':b' '*131073}),
                        dict(self.proof, **{'sdk-origin.json':b'{"recipe":1,"recipe":2}'})):
            self.pack('proof',entries)
            with self.assertRaises(ValueError): self.recover()
        self.assertFalse((self.root/'restored group').exists())

    def test_group_and_proof_archives_reject_unsafe_members_and_inexact_triplets(self):
        self.prepare(); group = {p.name:p.read_bytes() for p in self.group.iterdir()}
        symlink = zipfile.ZipInfo('shortcut'); symlink.create_system = 3; symlink.external_attr = 0o120777 << 16
        privileged = zipfile.ZipInfo('privileged'); privileged.external_attr = 0o104755 << 16
        invalid = [('extra',b'x'), ('../escape',b'x'), ('C:/escape',b'x'), ('bad\\name',b'x'),
                   (symlink,b'target'), (privileged,b'x')]
        for kind, good in [('group',group), ('proof',self.proof)]:
            for name, data in invalid:
                with self.subTest(kind=kind, name=str(name)):
                    self.pack(kind,[*good.items(),(name,data)])
                    if kind == 'proof' and name == 'extra':
                        # Unrelated regular proof reports are inspected but never extracted.
                        continue
                    with self.assertRaises(ValueError): self.recover()
                self.pack(kind,good)
            first = next(iter(good))
            self.pack(kind,[*good.items(),(first.upper(),b'alias')])
            with self.assertRaises(ValueError): self.recover()
            self.pack(kind,good)
        self.pack('group',dict(list(group.items())[1:]))
        with self.assertRaisesRegex(ValueError, 'exactly'): self.recover()
        self.assertFalse((self.root/'restored group').exists())

    def test_retained_lifecycle_reruns_consumer_without_cold_production(self):
        archive.write_json(self.root/'build/sdk-origin.json',{'origin':'retained','recipe':self.recipe,
                            'qualification':'unqualified','publication_approved':False})
        self.publisher.side_effect = None; self.publisher.return_value = {'operation':'plan'}
        with patch.object(lifecycle.ci,'assert_host'), patch.object(lifecycle.ci,'prepared_check') as check, \
             patch.object(lifecycle.subprocess,'run',side_effect=AssertionError('cold producer must not run')):
            lifecycle.main('sdk-produce')
        check.assert_called_once(); self.publisher.assert_called_once()
        self.assertNotIn('execute',self.publisher.call_args.kwargs)
        self.assertTrue((self.root/'build/sdk-publication-plan.json').is_file())

    def test_explicit_source_is_required_and_recovery_failure_has_no_cold_fallback(self):
        self.prepare()
        with patch.dict(lifecycle.os.environ,{'SDK_SOURCE':'auto','SDK_RETAINED_INPUT':json.dumps(self.request),
                                             'GITHUB_REPOSITORY':self.repository}):
            with self.assertRaisesRegex(ValueError,'explicit source=retained'): lifecycle.main('sdk-inputs')
        with patch.dict(lifecycle.os.environ,{'SDK_SOURCE':'retained','SDK_RETAINED_INPUT':json.dumps(self.request),
                                             'GITHUB_REPOSITORY':self.repository}), \
             patch.object(lifecycle.ci,'retained_sdk',side_effect=ValueError('exact digest differs')), \
             patch.object(lifecycle.ci,'maintenance_base') as base:
            with self.assertRaisesRegex(ValueError,'exact digest differs'): lifecycle.main('sdk-inputs')
            base.assert_not_called()
        with patch.dict(lifecycle.os.environ,{'SDK_SOURCE':'retained','TARGET':'all'}):
            with self.assertRaisesRegex(ValueError,'one exact target'): lifecycle.main('sdk-plan')



    def test_retained_all_gui_reruns_both_consumers_and_preserves_failure(self):
        origin = {'origin':'retained','recipe':self.recipe,'qualification':'unqualified','publication_approved':False}
        archive.write_json(self.root/'build/sdk-origin.json',origin)
        self.publisher.side_effect = None; self.publisher.return_value = {'operation':'plan'}
        entry = lifecycle.main
        with patch.dict(lifecycle.os.environ,{'SDK_PROFILE':'all-gui'}), \
             patch.object(lifecycle.ci,'assert_host'), patch.object(lifecycle,'main') as gui_input, \
             patch.object(lifecycle.ci,'prepared_check') as check, \
             patch.object(lifecycle.subprocess,'run',side_effect=AssertionError('cold producer must not run')):
            entry('sdk-produce')
        gui_input.assert_called_once_with('gui-maintain'); self.assertEqual(check.call_count,2)
        self.assertEqual(check.call_args.args[5],self.root/'build/gui-group')
        self.assertEqual(check.call_args.kwargs['graphics_archive'],self.root/'build/host-graphics/mesa-windows.7z')
        self.publisher.assert_called_once(); (self.root/'build/sdk-publication-plan.json').unlink()
        self.publisher.reset_mock()
        with patch.dict(lifecycle.os.environ,{'SDK_PROFILE':'all-gui'}), \
             patch.object(lifecycle.ci,'assert_host'), patch.object(lifecycle,'main'), \
             patch.object(lifecycle.ci,'prepared_check',side_effect=[None,RuntimeError('GUI failed')]):
            with self.assertRaisesRegex(RuntimeError,'GUI failed'): entry('sdk-produce')
        self.publisher.assert_not_called(); self.assertFalse((self.root/'build/sdk-publication-plan.json').exists())

    def test_linux_planning_does_not_substitute_for_native_recipe_check(self):
        self.prepare()
        environment={'SDK_SOURCE':'retained','SDK_RETAINED_INPUT':json.dumps(self.request),
                     'GITHUB_REPOSITORY':self.repository,'SDK_PROFILE':'core','TARGET':'windows-x86_64'}
        with patch.dict(lifecycle.os.environ,environment), patch.object(lifecycle,'sdk_identity',return_value='b'*64) as identity:
            lifecycle.main('sdk-plan'); identity.assert_not_called()
            with self.assertRaisesRegex(ValueError,'current recipe differs'): lifecycle.main('sdk-inputs')
            identity.assert_called()
        for raw in ('[]', '{"schema_version":1,"schema_version":1}', ' '*16385):
            with patch.dict(lifecycle.os.environ,dict(environment,SDK_RETAINED_INPUT=raw)),self.assertRaises(ValueError):
                lifecycle.main('sdk-plan')

    def test_workflow_declares_exact_manual_recovery_inputs_for_plan_and_producer(self):
        text=(ROOT/'.github/workflows/sdk-maintenance.yml').read_text()
        self.assertIn('        - retained\n',text)
        self.assertEqual(text.count('SDK_RETAINED_INPUT: ${{ inputs.retained_input }}'),2)
        self.assertEqual(text.count('SDK_PROFILE: ${{ inputs.profile }}'),2)
        self.assertEqual(text.count('SDK_SOURCE: ${{ inputs.source }}'),2)
        self.assertIn('    if: inputs.execute\n    needs: produce\n',text)


if __name__ == '__main__': unittest.main()
