#!/usr/bin/env python3
"""Retire exact temporary draft stores selected by completed full-run cleanup.

The caller owns the successful full-scope marker, preservation policy and exact
predecessor selection. This helper never selects older runs or retained SDKs.
"""
import re
import time

import ci_artifacts as artifacts
import ci_cleanup as cleanup
import ci_cleanup_repository as repository_cleanup
import ci_transport as bundles
import github_release as delivery

WORKFLOWS = frozenset(('candidate.yml', '_release-latest.yml', 'certify.yml',
                       'sdk-application.yml'))
MAX_SECONDS = 120


def _context(value):
    if not isinstance(value, dict) or value.get('workflow') not in WORKFLOWS:
        raise cleanup.CleanupError('draft cleanup requires a selected temporary full-run workflow')
    context = bundles._context(**{key: value.get(key) for key in
        ('repository', 'run_id', 'attempt', 'source_commit', 'workflow')}, name='cleanup')
    if not delivery.positive(value.get('repository_id')):
        raise cleanup.CleanupError('draft cleanup requires the exact selected repository ID')
    return context, value['repository_id']


def _temporary_assets(assets, attempt):
    """Unknown, retained and incomplete namespaces preserve the entire store."""
    names = [name[7:-5] for name in assets if name.startswith('bundle-') and name.endswith('.json')]
    if any(not bundles.NAME.fullmatch(name) or artifacts.slot_for(name, attempt, 0) is None for name in names):
        return False
    expected = {bundles._manifest_name(name) for name in names}
    owned = set(expected)
    for bundle in names:
        marker = assets[bundles._manifest_name(bundle)]
        if not 0 < marker['size'] <= bundles.MAX_MANIFEST:
            return False
        parts = []
        for name, row in assets.items():
            match = re.fullmatch(re.escape(bundles._prefix(bundle)) + r'([0-9]{4})-([0-9a-f]{64})', name)
            if match:
                if not 0 < row['size'] <= bundles.CHUNK_BYTES or row['digest'] != 'sha256:' + match[2]:
                    return False
                parts.append(int(match[1])); owned.add(name)
        if not parts or sorted(parts) != list(range(len(parts))) or len(parts) > bundles.MAX_PARTS:
            return False
    return owned == assets.keys()


def cleanup_drafts(current, predecessor=None, *, transport, cleanup_run_id,
                   sleep=time.sleep, clock=time.monotonic):
    """Delete at most two provenance-bound stores after the caller's barrier.

    Exact release IDs, complete assets and direct commit tags are reread before
    mutation. Deletion responses are never replayed, including uncertain ones.
    Missing releases grant no authority to remove orphaned tags.
    """
    if current is None:
        raise cleanup.CleanupError('draft cleanup requires the completed current full run')
    contexts = [_context(value) for value in (current, predecessor) if value is not None]
    if (not contexts or not delivery.positive(cleanup_run_id) or
            any(context['repository'].casefold() != contexts[0][0]['repository'].casefold() or
                repository_id != contexts[0][1] or context['run_id'] == cleanup_run_id
                for context, repository_id in contexts) or
            len({(context['run_id'], context['attempt']) for context, _ in contexts}) != len(contexts)):
        raise cleanup.CleanupError('draft cleanup contexts must be distinct runs in the same repository')
    started = clock()
    remote = delivery.Remote(contexts[0][0]['repository'], transport)
    tags = {bundles._tag(context): (context, repository_id) for context, repository_id in contexts}
    selected, seen = {}, set()
    for row in transport.pages(remote.base + '/releases?per_page=100'):
        if (not isinstance(row, dict) or not delivery.positive(row.get('id')) or
                row['id'] in seen or not isinstance(row.get('tag_name'), str)):
            raise cleanup.CleanupError('draft cleanup release inventory is incomplete or ambiguous')
        seen.add(row['id'])
        if row['tag_name'] in tags:
            if row['tag_name'] in selected:
                raise cleanup.CleanupError('duplicate selected draft tags require inspection')
            selected[row['tag_name']] = row['id']
    result = dict(selected_drafts=len(selected), deleted_drafts=0, deleted_tags=0,
                  preserved_drafts=0, preserved_tags=[])
    frozen = []
    # Validate every selected store before the first mutation.
    for tag, identity in selected.items():
        context, repository_id = tags[tag]
        info = bundles._store(remote, context, repository_id, release_id=identity)
        assets = remote.assets(info)
        if not _temporary_assets(assets, context['attempt']):
            result['preserved_drafts'] += 1
            result['preserved_tags'].append(tag)
            continue
        frozen.append((context, repository_id, identity, assets))
    mutations = 0
    try:
        for context, repository_id, identity, assets in frozen:
            if clock() - started >= MAX_SECONDS:
                raise cleanup.CleanupError('two-minute draft cleanup budget reached')
            info = bundles._store(remote, context, repository_id, release_id=identity)
            if remote.assets(info) != assets:
                raise cleanup.CleanupError('draft assets changed; preserve the selected store')
            repository_cleanup.require_idle(transport, dict(repository=remote.repository, run_id=cleanup_run_id))
            if mutations: sleep(1.0)
            transport.json(remote.base + '/releases/' + str(identity), method='DELETE')
            mutations += 1
            result['deleted_drafts'] += 1
            tag = bundles._tag(context)
            if remote.reference(tag) != context['source_commit']:
                raise cleanup.CleanupError('transport tag changed; preserve the tag')
            sleep(1.0)
            transport.json(remote.base + '/git/refs/tags/' + tag, method='DELETE')
            mutations += 1
            result['deleted_tags'] += 1
    except (ValueError, OSError) as error:
        raise cleanup.CleanupError(
            f"draft cleanup stopped after {result['deleted_drafts']} confirmed release and "
            f"{result['deleted_tags']} confirmed tag deletions: {error}") from error
    return result
