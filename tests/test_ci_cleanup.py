"""Cleanup freezes all pages and only deletes the current temporary namespace."""
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_cleanup as cleanup


class Transport:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self.fail_delete = None

    def json(self, endpoint, *, method='GET'):
        self.calls.append((method, endpoint))
        if method == 'GET':
            value = self.pages[int(endpoint.rsplit('page=', 1)[1]) - 1]
            if isinstance(value, Exception): raise value
            return copy.deepcopy(value)
        if endpoint.endswith('/' + str(self.fail_delete)):
            raise ValueError('injected deletion failure')
        return None


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.environment = dict(GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY='example/project', GITHUB_REPOSITORY_ID='9', GITHUB_RUN_ID='123',
            GITHUB_RUN_ATTEMPT='2', GITHUB_SHA='a' * 40,
            GITHUB_WORKFLOW_REF='example/project/.github/workflows/_release-latest.yml@refs/heads/main')
        self.sleeps = []

    def row(self, number, name=None):
        return dict(id=number, name=name or 'foundation-evidence-123-2-evidence-' + str(number),
            workflow_run=dict(id=123, repository_id=9, head_repository_id=9, head_sha='a' * 40))

    def transport(self, rows):
        return Transport([dict(total_count=len(rows), artifacts=rows[offset:offset + 100])
                          for offset in range(0, max(1, len(rows)), 100)])

    def run_cleanup(self, remote):
        return cleanup.cleanup(environment=self.environment, transport=remote, sleep=self.sleeps.append)

    def test_exact_attempt_only_and_sequential_pacing(self):
        remote = self.transport([self.row(1), self.row(2, 'ordinary-user-artifact'),
            self.row(3, 'foundation-evidence-123-1-source'), self.row(4, 'foundation-evidence-124-2-source'),
            self.row(5), self.row(6, 'foundation-evidence-123-20-source')])
        result = self.run_cleanup(remote)
        self.assertEqual(result, dict(run_id=123, attempt=2, selected=2, deleted=2))
        self.assertEqual([item for item in remote.calls if item[0] == 'DELETE'], [
            ('DELETE', 'repos/example/project/actions/artifacts/1'),
            ('DELETE', 'repos/example/project/actions/artifacts/5')])
        self.assertEqual(self.sleeps, [1.0])

    def test_complete_pagination_is_frozen_before_first_delete(self):
        remote = self.transport([self.row(number) for number in range(1, 104)])
        result = self.run_cleanup(remote)
        self.assertEqual(result['deleted'], 103)
        self.assertEqual([call[0] for call in remote.calls[:3]], ['GET', 'GET', 'DELETE'])
        self.assertEqual(sum(call[0] == 'GET' for call in remote.calls), 2)
        self.assertEqual(len(self.sleeps), 102)

    def test_native_transport_has_no_quota_wait_or_retry(self):
        remote = self.transport([self.row(1)])
        with mock.patch.object(cleanup.delivery, 'GitHub', return_value=remote) as factory:
            result = cleanup.cleanup(environment=self.environment, sleep=self.sleeps.append)
        factory.assert_called_once_with('example/project')
        self.assertEqual(result['deleted'], 1)
        self.assertEqual(remote.WRITE_HEADROOM, 0)
        self.assertEqual(remote.REQUEST_DEADLINE, 30)
        self.assertEqual(remote.COMMAND_TIMEOUT, 30)
        self.assertEqual(remote.WAIT_BUDGET, 0)
        self.assertEqual(remote.wait_remaining, 0.0)
        self.assertEqual(remote.MAX_ATTEMPTS, 1)
        self.assertEqual([method for method, _ in remote.calls], ['GET', 'DELETE'])
        self.assertFalse(self.sleeps)

    def test_empty_run_only_lists_once(self):
        remote = self.transport([])
        self.assertEqual(self.run_cleanup(remote)['deleted'], 0)
        self.assertEqual(len(remote.calls), 1)
        self.assertFalse(self.sleeps)

    def test_missing_or_foreign_context_never_queries(self):
        changes = [(key, None) for key in self.environment] + [
            ('GITHUB_ACTIONS', 'false'), ('GITHUB_SERVER_URL', 'https://other.example'),
            ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ATTEMPT', '02'),
            ('GITHUB_REPOSITORY_ID', '-9'), ('GITHUB_SHA', 'not-a-commit'),
            ('GITHUB_WORKFLOW_REF', 'other/project/.github/workflows/cleanup.yml@main')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                environment = dict(self.environment)
                if value is None: del environment[key]
                else: environment[key] = value
                remote = self.transport([])
                with self.assertRaises(ValueError):
                    cleanup.cleanup(environment=environment, transport=remote, sleep=self.sleeps.append)
                self.assertFalse(remote.calls)

    def test_duplicate_ids_and_names_reject_before_any_mutation(self):
        for second in (self.row(1, 'other'), self.row(2, self.row(1)['name'])):
            with self.subTest(second=second):
                remote = self.transport([self.row(1), second])
                with self.assertRaisesRegex(ValueError, 'duplicate'):
                    self.run_cleanup(remote)
                self.assertEqual([call[0] for call in remote.calls], ['GET'])

    def test_wrong_run_repository_and_commit_reject_before_deleting(self):
        for key, value in (('id', 124), ('repository_id', 10), ('head_repository_id', 10),
                           ('head_sha', 'b' * 40)):
            with self.subTest(key=key):
                row = self.row(1); row['workflow_run'][key] = value
                remote = self.transport([row])
                with self.assertRaisesRegex(ValueError, 'different run or source'):
                    self.run_cleanup(remote)
                self.assertEqual(len(remote.calls), 1)

    def test_malformed_inventory_and_invalid_slot_never_delete(self):
        cases = [dict(total_count=True, artifacts=[]), dict(total_count=1, artifacts=[]),
                 dict(total_count=10001, artifacts=[]), dict(total_count=0, artifacts=None),
                 dict(total_count=1, artifacts=[self.row(1, 'foundation-evidence-123-2-../other')])]
        for response in cases:
            with self.subTest(response=response):
                remote = Transport([response])
                with self.assertRaises(ValueError): self.run_cleanup(remote)
                self.assertEqual(len(remote.calls), 1)

    def test_failed_or_changed_later_page_prevents_all_deletion(self):
        for last in (ValueError('listing unavailable'), dict(total_count=102, artifacts=[self.row(101), self.row(102)]),
                     dict(total_count=101, artifacts=[self.row(1)])):
            with self.subTest(last=last):
                remote = Transport([dict(total_count=101, artifacts=[self.row(n) for n in range(1, 101)]), last])
                with self.assertRaises(ValueError): self.run_cleanup(remote)
                self.assertEqual([call[0] for call in remote.calls], ['GET', 'GET'])

    def test_deletion_failure_stops_without_retry_or_readback(self):
        remote = self.transport([self.row(1), self.row(2), self.row(3)]); remote.fail_delete = 2
        with self.assertRaisesRegex(ValueError, 'after 1 of 3 confirmed deletions'):
            self.run_cleanup(remote)
        self.assertEqual([call[0] for call in remote.calls], ['GET', 'DELETE', 'DELETE'])
        self.assertFalse(any(endpoint.endswith('/3') for _, endpoint in remote.calls))

    def test_oversized_delete_selection_preserves_every_artifact(self):
        remote = self.transport([self.row(n) for n in range(1, cleanup.MAX_DELETE + 2)])
        with self.assertRaisesRegex(ValueError, 'cleanup budget'):
            self.run_cleanup(remote)
        self.assertTrue(all(method == 'GET' for method, _ in remote.calls))

    def test_cli_has_no_arbitrary_repository_or_run_override(self):
        with mock.patch.object(cleanup, 'cleanup') as run, mock.patch('sys.stderr'):
            with self.assertRaises(SystemExit): cleanup.main(['--run-id', '999'])
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
