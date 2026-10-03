"""Fail-closed orchestration contracts and exact final remote pointer verification."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import latest_release as L
import test_github_release as fixtures


def request(execute=True):
    return {'repository': 'example/project', 'source_commit': 'a' * 40, 'run_id': '123', 'attempt': 1,
            'tag': 'v1', 'profile': 'core', 'recipes': {target: 'b' * 64 for target in L.ci.STANDARD},
            'gui_group': '', 'graphics_archive_url': '', 'execute': execute, 'jobs': '2'}


def results(execute=True):
    value = {name: {'result': 'success', 'outputs': {}} for name in L.STAGES}
    value['application']['outputs'] = {'source_commit': 'a' * 40, 'tag': 'v1', 'inventory_sha256': 'c' * 64,
                                      'delivery_sha256': 'd' * 64, 'published': 'true' if execute else 'false'}
    value['certification']['outputs'] = {'inventory_sha256': 'c' * 64, 'certificate_sha256': 'e' * 64,
        'certification_run': '123', 'certification_attempt': '1', 'eligible_for_promotion': 'true', 'attached': 'true'}
    value['promotion']['outputs'] = {'promoted': 'true'}
    if not execute:
        for name in L.STAGES[3:]: value[name] = {'result': 'skipped', 'outputs': {}}
    return value


class LatestReleaseTests(unittest.TestCase):
    def test_cli_creates_fresh_receipt_parent_without_overwriting(self):
        # Supply a fixture request and preflight response in a fresh child;
        # argument parsing, Git identity and file publication remain real.
        program = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
import latest_release as L
L.ROOT = Path(sys.argv.pop(1))
request = json.loads(sys.argv.pop(1))
L.environment_request = lambda: request
L.preflight = lambda value: dict(value, status='prepared')
L.main()
'''
        with tempfile.TemporaryDirectory() as temporary:
            # Source releases deliberately omit Git history. Keep this real Git
            # fixture independent of the checkout containing the test itself.
            repository = Path(temporary) / 'fixture-repository'
            repository.mkdir()
            def git(*args):
                return subprocess.run(['git', *args], cwd=repository, check=True,
                                      capture_output=True, text=True).stdout.strip()
            git('init', '--quiet')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '--quiet', '--allow-empty', '-m', 'fixture')
            value = dict(request(False), source_commit=git('rev-parse', 'HEAD'))
            output = Path(temporary) / 'absent' / 'build' / 'receipt.json'
            command = [sys.executable, '-B', '-c', program, str(L.ROOT / 'tools'), str(repository),
                       json.dumps(value), 'preflight', '--output', str(output)]
            environment = dict(os.environ, GITHUB_OUTPUT=str(Path(temporary) / 'workflow-output'))
            first = subprocess.run(command, cwd=temporary, capture_output=True, text=True, env=environment)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_bytes()
            self.assertEqual(json.loads(original)['status'], 'prepared')
            second = subprocess.run(command, cwd=temporary, capture_output=True, text=True, env=environment)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn('FileExistsError', second.stderr)
            self.assertEqual(output.read_bytes(), original)
            mismatch = command.copy()
            mismatch[6] = json.dumps(dict(value, source_commit='0' * 40))
            mismatch[-1] = str(Path(temporary) / 'mismatch.json')
            rejected = subprocess.run(mismatch, cwd=temporary, capture_output=True, text=True, env=environment)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('checked-out source does not match workflow commit', rejected.stderr)
            self.assertFalse(Path(mismatch[-1]).exists())

    def test_preflight_requires_complete_target_recipes_and_separate_tag(self):
        self.assertEqual(L.preflight(request(), remote=False)['tag'], 'v1')
        for changes in ({'recipes': {}}, {'tag': 'base'}, {'tag': 'screenshots-1'}, {'tag': 'ci-1'},
                        {'execute': 'true'}, {'source_commit': 'main'}, {'gui_group': 'a' * 64}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                L.preflight(dict(request(), **changes), remote=False)
        self.assertEqual(L.preflight(dict(request(), tag=''), remote=False)['tag'], 'release-123-attempt-1')

    def test_unresolved_gui_redistribution_fails_before_remote_work(self):
        policy=(L.ci.ROOT/'docs/release-policy.json').read_bytes()
        modules={name:L.ci.module(name) for name in ('coverage','certify_release')}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'third_party').mkdir();(root/'docs').mkdir()
            (root/'docs/release-policy.json').write_bytes(policy)
            (root/'third_party/gui-boundary.lock.json').write_text('{"redistribution":{"approved":false}}')
            with mock.patch.object(L.ci,'ROOT',root),mock.patch.object(L.ci,'module',side_effect=modules.__getitem__),self.assertRaisesRegex(ValueError,'licens'):
                L.preflight(dict(request(),profile='all-gui',recipes={**request()['recipes'],'browser-wasm32':'b'*64}),remote=False)

    def test_preflight_missing_base_has_no_cold_build_or_mutation(self):
        remote = fixtures.FakeGitHub()
        with self.assertRaisesRegex(ValueError, 'absent'):
            L.preflight(request(), transport=remote)
        self.assertEqual(remote.mutations, [])

    def test_every_mandatory_stage_must_actually_succeed(self):
        L.require_stages(results(), request())
        for stage in L.STAGES:
            for outcome in ('failure', 'cancelled', 'skipped', 'neutral'):
                value = results(); value[stage]['result'] = outcome
                with self.subTest(stage=stage, outcome=outcome), self.assertRaisesRegex(ValueError, 'mandatory'):
                    L.require_stages(value, request())

    def test_incomplete_inventory_is_not_a_successful_orchestration(self):
        value = results(); value.pop('regression')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            L.require_stages(value, request())

    def test_source_tag_inventory_and_publication_outputs_are_bound(self):
        for key, changed in [('source_commit', 'b' * 40), ('tag', 'v2'), ('inventory_sha256', ''),
                             ('delivery_sha256', ''), ('published', 'false')]:
            value = results(); value['application']['outputs'][key] = changed
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'application outputs'):
                L.require_stages(value, request())

    def test_certificate_cannot_come_from_another_attempt_or_delivery(self):
        for key, changed in [('inventory_sha256', 'f' * 64), ('certificate_sha256', ''),
                             ('certification_run', '124'), ('certification_attempt', '2'),
                             ('eligible_for_promotion', 'false'), ('attached', 'false')]:
            value = results(); value['certification']['outputs'][key] = changed
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'certificate'):
                L.require_stages(value, request())

    def test_plan_only_explicitly_omits_qualification_and_remote_calls(self):
        remote = fixtures.FakeGitHub()
        value = L.verify_latest(request(False), results(False), transport=remote)
        self.assertEqual(value['status'], 'prepared'); self.assertFalse(value['qualified'])
        self.assertFalse(value['published']); self.assertEqual(remote.calls, [])
        unexpected = results(False); unexpected['certification']['result'] = 'success'
        with self.assertRaisesRegex(ValueError, 'unexpectedly entered'):
            L.verify_latest(request(False), unexpected, transport=remote)

    def test_final_remote_review_reproduces_real_certificate_and_detects_latest_change(self):
        fixture = fixtures.DeliveryTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.publish(); cert = fixture.cert()
        L.delivery.attach_certificate(**cert, execute=True, transport=fixture.remote)
        fixture.promotion(cert, execute=True)
        req = dict(request(), profile='fixture', run_id='qualification-run')
        value = results(); app = value['application']['outputs']; app['inventory_sha256'] = fixture.delivery['inventory_sha256']
        app['delivery_sha256'] = L.delivery.sha(L.delivery.archive.encoded(fixture.delivery))
        value['certification']['outputs'].update(inventory_sha256=app['inventory_sha256'],
            certificate_sha256=L.delivery.archive.digest(cert['certificate']), certification_run='qualification-run')
        real_verify = L.delivery.verify_certificate
        def verify(*args, **kwargs):
            args = list(args); args[4] = cert['policy']
            return real_verify(*args, **kwargs)
        with mock.patch.object(L.delivery, 'verify_certificate', side_effect=verify):
            checked = L.verify_latest(req, value, transport=fixture.remote)
            self.assertTrue(checked['qualified']); self.assertEqual(checked['assets'].keys(),
                {a['name'] for a in fixture.remote.releases[0]['assets']})
            fixture.remote.releases[0]['prerelease'] = True
            with mock.patch.object(L.delivery, 'verify_certificate') as replay:
                with self.assertRaisesRegex(ValueError, 'lifecycle'):
                    L.verify_latest(req, value, transport=fixture.remote)
            replay.assert_not_called()
            fixture.remote.releases[0]['prerelease'] = False
            fixture.remote.releases.append(dict(id=99, tag_name='different', draft=False, prerelease=False, name='different', assets=[]))
            fixture.remote.latest = 99
            with self.assertRaisesRegex(ValueError, 'identity|Latest'):
                L.verify_latest(req, value, transport=fixture.remote)


class WorkflowOverlapTests(unittest.TestCase):
    def test_certification_restores_exact_frozen_payloads_once_and_keeps_diagnostics(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root/'.github/workflows/certify.yml').read_text()
        prepare = workflow.split('  prepare:\n', 1)[1].split('  check:\n', 1)[0]
        self.assertIn('qualification-metadata', prepare)
        self.assertNotIn('qualification-payloads', prepare)
        self.assertNotIn('qualification-inputs-', prepare)
        self.assertNotIn('bundle-store', prepare)
        check = workflow.split('  check:\n', 1)[1].split('  record:\n', 1)[0]
        self.assertEqual(check.count("'fetch-published-check-inputs'"), 1)
        self.assertIn('CHECK_PAYLOADS: ${{ toJSON(matrix.payloads) }}', check)
        self.assertNotIn("'bundle-fetch'", check)
        self.assertNotIn("'fetch-check-payloads'", check)
        self.assertIn('    - if: always()\n      name: Retain verified evidence-', check)
        self.assertIn('BUNDLE_PATHS: |-\n          build/evidence/\n          build/prerequisites/', check)
        self.assertNotIn('browser-prerequisite-', check)
        self.assertIn('      fail-fast: false', check)
        self.assertIn("'check-batch'", check)
        record = workflow.split('  record:\n',1)[1].split('  attach:\n',1)[0]
        self.assertIn("if: always() && needs.prepare.result == 'success'", record)
        self.assertEqual(record.count("'fetch-certification-evidence'"),1)
        self.assertIn('CHECK_BATCHES: ${{ needs.prepare.outputs.matrix }}',record)
        self.assertIn('build/candidate-remote.json',record)

    def test_nested_regression_receipt_fails_closed_and_does_not_repeat_work(self):
        root = Path(__file__).resolve().parents[1]
        latest = (root/'.github/workflows/_release-latest.yml').read_text()
        application = (root/'.github/workflows/sdk-application.yml').read_text()
        gate = latest.split('  regression:\n', 1)[1].split('  application:\n', 1)[0]
        code = gate.split('      run: |\n', 1)[1]
        code = '\n'.join(line[8:] for line in code.splitlines())
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory)/'summary.md'
            for app, result in (('failure', 'success'), ('success', 'failure'), ('success', 'cancelled'),
                                ('success', 'skipped'), ('success', '')):
                with mock.patch.dict(os.environ, {'APPLICATION_RESULT': app, 'REGRESSION_RESULT': result,
                                                  'GITHUB_STEP_SUMMARY': str(summary)}):
                    with self.assertRaises(SystemExit): exec(compile(code, 'regression-receipt', 'exec'), {})
            self.assertFalse(summary.exists())
            with mock.patch.dict(os.environ, {'APPLICATION_RESULT': 'success', 'REGRESSION_RESULT': 'success',
                                              'GITHUB_STEP_SUMMARY': str(summary)}):
                exec(compile(code, 'regression-receipt', 'exec'), {})
            self.assertIn('does not repeat regression', summary.read_text())
        outer_app = latest.split('  application:\n', 1)[1].split('  certification:\n', 1)[0]
        self.assertIn('    needs: prepare\n', outer_app)
        self.assertIn('      require_regression: true', outer_app)
        nested = application.split('jobs:\n', 1)[1].split('  prepare:\n', 1)[0]
        self.assertIn('uses: ./.github/workflows/candidate.yml', nested)
        self.assertNotIn('needs:', nested)
        assembly = application.split('  assemble:\n', 1)[1].split('\nenv:\n', 1)[0]
        self.assertIn('needs: [prepare, application, regression]', assembly)
        self.assertIn("inputs.require_regression && needs.regression.result == 'success'", assembly)
        self.assertIn("!inputs.require_regression && needs.regression.result == 'skipped'", assembly)
        self.assertIn('environment: ${{ inputs.execute', assembly)
        self.assertIn('group: foundation-release-lifecycle', assembly)
        self.assertIn('publish-candidate', assembly)
        self.assertIn('regression_result: ${{ needs.regression.result }}', assembly)
        self.assertIn('value: ${{ jobs.assemble.outputs.regression_result }}', application)
        self.assertNotIn('  publish:\n', application)
        self.assertIn('    - if: ${{ !inputs.execute }}\n      name: Retain verified candidate-', assembly)
        self.assertNotIn('BUNDLE_OUTPUT: build\n', assembly)


if __name__ == '__main__': unittest.main()
