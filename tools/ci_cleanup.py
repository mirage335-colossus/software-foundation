#!/usr/bin/env python3
"""Delete only this attempt's temporary evidence after its final consumers.

The caller owns the dependency barrier and preservation option. Cleanup never
deletes workflow runs, release assets, SDKs or artifacts from another attempt.
One-day artifact expiry remains the fallback if cleanup cannot finish.
"""
import argparse
import json
import os
import re
import time

import github_release as delivery

PAGE_SIZE = 100
MAX_ARTIFACTS = 10000
MAX_DELETE = 512


class CleanupError(ValueError):
    pass


def current_context(environment=None):
    environment = os.environ if environment is None else environment
    if (environment.get('GITHUB_ACTIONS') != 'true' or
            environment.get('GITHUB_SERVER_URL') != 'https://github.com'):
        raise CleanupError('cleanup requires a native GitHub.com Actions context')
    repository = delivery.location(environment.get('GITHUB_REPOSITORY', ''))
    reference = environment.get('GITHUB_WORKFLOW_REF', '')
    prefix = repository + '/.github/workflows/'
    if (not reference.startswith(prefix) or
            not re.fullmatch(r'[A-Za-z0-9_-]+\.ya?ml@[^\r\n]+', reference[len(prefix):])):
        raise CleanupError('cleanup workflow must belong to the current repository')
    values = {}
    for field, variable in (('run_id', 'GITHUB_RUN_ID'), ('attempt', 'GITHUB_RUN_ATTEMPT'),
                            ('repository_id', 'GITHUB_REPOSITORY_ID')):
        value = environment.get(variable, '')
        if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', value):
            raise CleanupError('cleanup requires a positive exact ' + field)
        values[field] = int(value)
    commit = environment.get('GITHUB_SHA', '')
    if not isinstance(commit, str) or not delivery.OID.fullmatch(commit):
        raise CleanupError('cleanup requires the exact current source commit')
    return dict(repository=repository, source_commit=commit, **values)


def selected_artifacts(transport, context):
    """Freeze the complete paginated ID set before any deletion shifts its pages."""
    rows, expected_total = [], None
    ids, names = set(), set()
    selected = []
    prefix = f"foundation-evidence-{context['run_id']}-{context['attempt']}-"
    base = f"repos/{context['repository']}/actions/runs/{context['run_id']}/artifacts"
    for page in range(1, MAX_ARTIFACTS // PAGE_SIZE + 1):
        response = transport.json(base + f'?per_page={PAGE_SIZE}&page={page}')
        if (not isinstance(response, dict) or type(response.get('total_count')) is not int or
                not 0 <= response['total_count'] <= MAX_ARTIFACTS or
                not isinstance(response.get('artifacts'), list) or
                expected_total not in (None, response['total_count'])):
            raise CleanupError('artifact listing is incomplete, changed or oversized')
        expected_total = response['total_count']
        batch = response['artifacts']
        if len(batch) != min(PAGE_SIZE, expected_total - len(rows)):
            raise CleanupError('artifact page does not match the complete inventory')
        for row in batch:
            if (not isinstance(row, dict) or not delivery.positive(row.get('id')) or
                    not isinstance(row.get('name'), str) or not 0 < len(row['name']) <= 255 or
                    row['id'] in ids or row['name'] in names):
                raise CleanupError('artifact inventory has duplicate or invalid identities')
            ids.add(row['id']); names.add(row['name'])
            run = row.get('workflow_run')
            if (not isinstance(run, dict) or type(run.get('id')) is not int or
                    run['id'] != context['run_id'] or
                    type(run.get('repository_id')) is not int or
                    run['repository_id'] != context['repository_id'] or
                    type(run.get('head_repository_id')) is not int or
                    run['head_repository_id'] != context['repository_id'] or
                    run.get('head_sha') != context['source_commit']):
                raise CleanupError('listed artifact belongs to a different run or source')
            if row['name'].startswith(prefix):
                slot = row['name'][len(prefix):]
                if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,159}', slot):
                    raise CleanupError('reserved evidence artifact has an invalid slot')
                selected.append(row['id'])
        rows.extend(batch)
        if len(rows) == expected_total:
            if len(selected) > MAX_DELETE:
                raise CleanupError('temporary artifact selection exceeds cleanup budget')
            return selected
    raise CleanupError('artifact listing exceeds supported pagination')


def cleanup(*, environment=None, transport=None, sleep=time.sleep):
    context = current_context(environment)
    if transport is None:
        transport = delivery.GitHub(context['repository'])
        # Cleanup is optional: never wait for quota or retry a partial mutation.
        transport.WRITE_HEADROOM = 0
        transport.REQUEST_DEADLINE = 30
        transport.COMMAND_TIMEOUT = 30
        transport.WAIT_BUDGET = 0
        transport.wait_remaining = 0.0
        transport.MAX_ATTEMPTS = 1
    selected = selected_artifacts(transport, context)
    deleted = 0
    for artifact_id in selected:
        if deleted:
            sleep(1.0)
        try:
            transport.json(f"repos/{context['repository']}/actions/artifacts/{artifact_id}", method='DELETE')
        except (ValueError, OSError) as error:
            raise CleanupError(f'cleanup stopped after {deleted} of {len(selected)} confirmed deletions; '
                               'remaining artifacts retain their expiry: ' + str(error)) from error
        deleted += 1
    return dict(run_id=context['run_id'], attempt=context['attempt'], selected=len(selected), deleted=deleted)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(cleanup(), sort_keys=True))


if __name__ == '__main__':
    delivery.enable_metrics()
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit('ci-cleanup: ' + str(error))
