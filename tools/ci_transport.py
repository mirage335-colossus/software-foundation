#!/usr/bin/env python3
"""Private draft-release transport. Stored bytes never grant qualification.

Every bundle has a complete manifest uploaded last. Large safe tar streams are
split into bounded assets. This module never publishes a release, selects Latest,
deletes remote state, overwrites an asset, or uses Actions artifact storage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
import time
import unicodedata

import dependency_archive as archive
import github_release as delivery

CHUNK_BYTES = 512 * 1024 * 1024
MAX_BYTES = 64 * 1024**3
MAX_FILES = 10000
MAX_MANIFEST = 8 * 1024 * 1024
MAX_PARTS = 256
NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}')
SHA = re.compile(r'[0-9a-f]{64}')


class TransportError(ValueError):
    pass


def _positive(value):
    return type(value) is int and value > 0


def _context(repository, run_id, attempt, source_commit, workflow, name):
    delivery.location(repository)
    if (not _positive(run_id) or not _positive(attempt) or
            not isinstance(source_commit, str) or not delivery.OID.fullmatch(source_commit) or
            not isinstance(workflow, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.yml', workflow) or
            not isinstance(name, str) or not NAME.fullmatch(name)):
        raise TransportError('exact run, attempt, commit, workflow and portable bundle name required')
    return dict(repository=repository, run_id=run_id, attempt=attempt,
                source_commit=source_commit, workflow=workflow, name=name)


def _run(remote, context):
    repo = remote.transport.json(remote.base)
    run = remote.transport.json(remote.base + '/actions/runs/' + str(context['run_id']) +
                                '/attempts/' + str(context['attempt']))
    if (not _positive(repo.get('id')) or repo.get('full_name', '').casefold() != remote.repository.casefold() or
            run.get('id') != context['run_id'] or run.get('run_attempt') != context['attempt'] or
            run.get('head_sha') != context['source_commit'] or
            run.get('path') != '.github/workflows/' + context['workflow'] or
            run.get('event') not in ('workflow_dispatch', 'workflow_call') or
            any(run.get(key, {}).get('id') != repo['id'] or
                run.get(key, {}).get('full_name', '').casefold() != remote.repository.casefold()
                for key in ('repository', 'head_repository'))):
        raise TransportError('producer repository, workflow, attempt or source differs')
    return repo['id']


def _jobs(remote, context):
    rows, total = [], None
    for page in range(1, 101):
        item = remote.transport.json(remote.base + '/actions/runs/' + str(context['run_id']) +
            '/attempts/' + str(context['attempt']) + '/jobs?per_page=100&page=' + str(page))
        if (type(item.get('total_count')) is not int or not 0 <= item['total_count'] <= 10000 or
                not isinstance(item.get('jobs'), list) or total not in (None, item['total_count'])):
            raise TransportError('incomplete or changed producer job inventory')
        total = item['total_count']; rows.extend(item['jobs'])
        if len(rows) >= total:
            if len(rows) != total or len({x.get('id') for x in rows}) != total:
                raise TransportError('ambiguous producer job inventory')
            return rows
        if not item['jobs']: break
    raise TransportError('producer job inventory exceeds supported bounds')


def _producer(remote, context, *, job_id=None, job_name=None, runner_name=None,
              publishing=False, allow_failed=False):
    if job_id is not None:
        if not _positive(job_id): raise TransportError('positive producer job ID required')
        job = remote.transport.json(remote.base + '/actions/jobs/' + str(job_id))
    else:
        runner_name = runner_name or (os.environ.get('RUNNER_NAME') if publishing else None)
        if not job_name and not runner_name: raise TransportError('exact producer job or runner required')
        matches = [x for x in _jobs(remote, context)
                   if (not job_name or x.get('name') == job_name) and
                   (not runner_name or x.get('runner_name') == runner_name) and
                   (not publishing or x.get('status') == 'in_progress')]
        if len(matches) != 1: raise TransportError('producer job selection is absent or ambiguous')
        job = matches[0]
    if (not _positive(job.get('id')) or job.get('run_id') != context['run_id'] or
            job.get('run_attempt') != context['attempt'] or job.get('head_sha') != context['source_commit'] or
            not isinstance(job.get('name'), str) or not job['name'] or
            not _positive(job.get('runner_id')) or not isinstance(job.get('runner_name'), str) or
            not job['runner_name'] or job_name is not None and job['name'] != job_name or
            runner_name is not None and job['runner_name'] != runner_name):
        raise TransportError('producer job identity differs')
    if publishing:
        valid = job.get('status') == 'in_progress' or (
            job.get('status') == 'completed' and job.get('conclusion') in ('success', 'failure'))
    else:
        valid = job.get('status') == 'completed' and job.get('conclusion') in (
            ('success', 'failure') if allow_failed else ('success',))
    if not valid: raise TransportError('producer job has not reached the required completion state')
    return {k: job[k] for k in ('id', 'name', 'runner_id', 'runner_name')}, job


def _tag(context):
    return 'ci-' + str(context['run_id']) + '-attempt-' + str(context['attempt'])


def _store(remote, context, repository_id, *, create=False):
    tag = _tag(context)
    identity = {k: v for k, v in context.items() if k != 'name'}
    identity.update(schema_version=1, kind='private-ci-transport', repository_id=repository_id)
    info = remote.find(tag, required=False)
    if info is None and create:
        ref = remote.reference(tag, missing=True)
        if ref not in (None, context['source_commit']): raise TransportError('transport tag source differs')
        if ref is None:
            try: remote.change('/git/refs', body={'ref': 'refs/tags/' + tag, 'sha': context['source_commit']})
            except delivery.DeliveryError:
                if remote.reference(tag, missing=True) != context['source_commit']: raise
        creation_error = None
        try:
            remote.change('/releases', body={'tag_name': tag, 'target_commitish': context['source_commit'],
                'name': tag, 'body': archive.encoded(identity).decode(), 'draft': True,
                'prerelease': True, 'make_latest': 'false'})
        except delivery.DeliveryError as error:
            creation_error = error
        # A successful creation can precede its appearance in the list endpoint.
        # Reconcile by bounded reads only; never repeat the uncertain mutation.
        for delay in (0, .25, .5, 1, 2, 4):
            if delay: time.sleep(delay)
            info = remote.find(tag, required=False)
            if info is not None: break
        if info is None:
            if creation_error is not None: raise creation_error
            raise TransportError('created transport draft is not visible; preserve and reconcile')
    if (info is None or info.get('draft') is not True or info.get('prerelease') is not True or
            info.get('name') != tag or delivery.parse(info.get('body', 'null')) != identity or
            remote.reference(tag) != context['source_commit']):
        raise TransportError('private transport release identity or lifecycle differs')
    return info


def _prefix(name):
    return 'blob-' + hashlib.sha256(name.encode()).hexdigest() + '-'


def _manifest_name(name):
    return 'bundle-' + name + '.json'


def _assets(remote, info, name):
    rows = remote.transport.pages(remote.base + '/releases/' + str(info['id']) + '/assets?per_page=100')
    result, names, ids = {}, set(), set()
    for row in rows:
        key = row.get('name')
        if not isinstance(key, str) or key.casefold() in names or not _positive(row.get('id')) or row['id'] in ids:
            raise TransportError('duplicate or incomplete remote asset inventory')
        names.add(key.casefold()); ids.add(row['id'])
        if key != _manifest_name(name) and not key.startswith(_prefix(name)): continue
        if (row.get('state') != 'uploaded' or type(row.get('size')) is not int or
                not 0 <= row['size'] < 2 * 1024**3 or not isinstance(row.get('digest'), str) or
                not re.fullmatch(r'sha256:[0-9a-f]{64}', row['digest'])):
            raise TransportError('bundle contains an incomplete or unbound remote asset; preserve it')
        result[key] = {k: row[k] for k in ('id', 'name', 'state', 'size', 'digest')}
    return result


def _path(name):
    path = archive.relative(name)
    if str(path) != unicodedata.normalize('NFC', str(path)) or len(name.encode()) > 4096:
        raise TransportError('noncanonical or oversized portable path')
    if any(re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p) or
           any(ord(c) == 127 for c in p) for p in path.parts):
        raise TransportError('reserved portable path component')
    return path


def _ordinary(path, directory=False):
    info = path.lstat()
    if (getattr(info, 'st_file_attributes', 0) & 0x400 or
            not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) or info.st_mode & 0o7000):
        raise TransportError('only ordinary unprivileged files and directories may be transported')
    return info


def _inventory(root, paths, allow_missing):
    root = Path(root).absolute(); _ordinary(root, True)
    names = set()
    for selected in paths:
        relative = _path(selected); current = root
        missing = False
        for index, component in enumerate(relative.parts):
            current /= component
            try: info = current.lstat()
            except FileNotFoundError:
                if allow_missing: missing = True; break
                raise
            if index + 1 < len(relative.parts): _ordinary(current, True)
        if missing: continue
        if stat.S_ISDIR(info.st_mode):
            _ordinary(current, True)
            for parent, dirs, files in os.walk(current, followlinks=False):
                for d in dirs: _ordinary(Path(parent) / d, True)
                for f in files: names.add((Path(parent) / f).relative_to(root).as_posix())
        else: names.add(relative.as_posix())
    if not names or len(names) > MAX_FILES: raise TransportError('empty or oversized bundle inventory')
    registry = archive.PathInventory(); result = {}; total = 0
    for name in sorted(names):
        _path(name); registry.add(name, False); path = root / name; info = _ordinary(path)
        total += info.st_size
        if total > MAX_BYTES: raise TransportError('bundle exceeds supported byte limit')
        result[name] = dict(size=info.st_size, mode=0o755 if info.st_mode & 0o111 else 0o644, sha256=archive.digest(path))
    return result


def _asset(row):
    return dict(id=row['id'], name=row['name'], size=row['size'], sha256=row['digest'][7:])


def _pointer(context, info, producer, row):
    value = dict(schema_version=1, **context, job_id=producer['id'], release_id=info['id'],
                 tag=info['tag_name'], manifest=_asset(row))
    if len(archive.encoded(value)) > 65536: raise TransportError('transport pointer exceeds output bound')
    return value


def _put(remote, context, info, path, expected):
    rows = _assets(remote, info, context['name']); row = rows.get(path.name)
    if row is None:
        remote.upload(_tag(context), path)
        row = _assets(remote, info, context['name']).get(path.name)
    if row is None or row['size'] != path.stat().st_size or row['digest'] != 'sha256:' + expected:
        raise TransportError('immutable remote asset differs; never overwrite it')
    return row


def publish_bundle(repository, run_id, attempt, source_commit, workflow, name, root, paths, *,
                   job_id=None, job_name=None, runner_name=None, metadata=None, allow_missing=False,
                   transport=None, chunk_bytes=CHUNK_BYTES):
    """Store exact bytes privately; completed failed jobs may retain diagnostics."""
    context = _context(repository, run_id, attempt, source_commit, workflow, name)
    if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= CHUNK_BYTES:
        raise TransportError('chunk size exceeds transport policy')
    metadata = {} if metadata is None else metadata
    if not isinstance(metadata, dict) or len(archive.encoded(metadata)) > 65536:
        raise TransportError('bounded metadata object required')
    # Roundtrip rejects nonfinite values and unsupported JSON values before writes.
    metadata = delivery.parse(archive.encoded(metadata))
    root = Path(root).absolute(); paths = list(paths)
    files = _inventory(root, paths, allow_missing)
    remote = delivery.Remote(repository, transport)
    repository_id = _run(remote, context)
    producer, _ = _producer(remote, context, job_id=job_id, job_name=job_name,
                            runner_name=runner_name, publishing=True)
    with tempfile.TemporaryDirectory(prefix='foundation-ci-publish-') as temporary:
        stage = Path(temporary); bundle = stage / 'payload.tar'
        with tarfile.open(bundle, 'w', format=tarfile.PAX_FORMAT) as output:
            for relative, item in files.items():
                header = tarfile.TarInfo(relative); header.size = item['size']; header.mode = item['mode']; header.mtime = 0
                with (root / relative).open('rb') as stream: output.addfile(header, stream)
        if _inventory(root, paths, allow_missing) != files: raise TransportError('input changed while staging bundle')
        whole = dict(size=bundle.stat().st_size, sha256=archive.digest(bundle), parts=[])
        if whole['size'] > MAX_BYTES + 32 * 1024**2: raise TransportError('bundle archive exceeds supported limit')
        if (whole['size'] + chunk_bytes - 1) // chunk_bytes > MAX_PARTS:
            raise TransportError('bundle needs too many bounded chunks')
        chunks = []
        with bundle.open('rb') as stream:
            index = 0
            while True:
                data = stream.read(chunk_bytes)
                if not data: break
                sha = hashlib.sha256(data).hexdigest(); part = stage / (_prefix(name) + str(index).zfill(4) + '-' + sha)
                part.write_bytes(data); chunks.append((part, sha)); index += 1
        info = _store(remote, context, repository_id, create=True)
        rows = _assets(remote, info, name)
        expected_names = {p.name for p, _ in chunks} | {_manifest_name(name)}
        if set(rows) - expected_names: raise TransportError('unexpected prior bundle assets; preserve and inspect')
        for path, sha in chunks: whole['parts'].append(_asset(_put(remote, context, info, path, sha)))
        manifest = dict(schema_version=1, **context, repository_id=repository_id, release_id=info['id'],
                        producer=producer, metadata=metadata, files=files, archive=whole)
        encoded = archive.encoded(manifest)
        if len(encoded) > MAX_MANIFEST: raise TransportError('manifest exceeds bounded inventory size')
        if _inventory(root, paths, allow_missing) != files: raise TransportError('input changed before commit marker')
        _run(remote, context)
        if _producer(remote, context, job_id=producer['id'], publishing=True)[0] != producer:
            raise TransportError('producer identity changed before commit marker')
        if _store(remote, context, repository_id)['id'] != info['id']: raise TransportError('release changed')
        path = stage / _manifest_name(name); path.write_bytes(encoded)
        row = _put(remote, context, info, path, hashlib.sha256(encoded).hexdigest())
        final = _assets(remote, info, name)
        if (set(final) != expected_names or final[_manifest_name(name)] != row or
                any(_asset(final[p['name']]) != p for p in whole['parts']) or
                _store(remote, context, repository_id)['id'] != info['id']):
            raise TransportError('bundle assets changed after commit marker')
        return _pointer(context, info, producer, row)


def _validate_manifest(value, context, info, repository_id):
    fields = set(context) | {'schema_version', 'repository_id', 'release_id', 'producer', 'metadata', 'files', 'archive'}
    if (not isinstance(value, dict) or set(value) != fields or type(value.get('schema_version')) is not int or value['schema_version'] != 1 or
            any(type(value.get(k)) is not type(v) or value[k] != v for k, v in context.items()) or
            not _positive(value['repository_id']) or value['repository_id'] != repository_id or
            not _positive(value['release_id']) or value['release_id'] != info['id'] or
            not isinstance(value['producer'], dict) or
            set(value['producer']) != {'id', 'name', 'runner_id', 'runner_name'} or
            not _positive(value['producer'].get('id')) or not _positive(value['producer'].get('runner_id')) or
            any(not isinstance(value['producer'].get(k), str) or not value['producer'][k] for k in ('name', 'runner_name')) or
            not isinstance(value['metadata'], dict) or len(archive.encoded(value['metadata'])) > 65536):
        raise TransportError('manifest provenance differs')
    files, bundle = value['files'], value['archive']
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise TransportError('invalid complete file inventory')
    registry = archive.PathInventory(); total = 0
    for name, item in files.items():
        _path(name); registry.add(name, False)
        if (not isinstance(item, dict) or set(item) != {'size', 'mode', 'sha256'} or
                type(item['size']) is not int or item['size'] < 0 or type(item['mode']) is not int or
                item['mode'] not in (0o644, 0o755) or not isinstance(item['sha256'], str) or not SHA.fullmatch(item['sha256'])):
            raise TransportError('invalid file identity or mode')
        total += item['size']
    if total > MAX_BYTES or not isinstance(bundle, dict) or set(bundle) != {'size', 'sha256', 'parts'}:
        raise TransportError('invalid bundle byte inventory')
    if (type(bundle['size']) is not int or not 0 < bundle['size'] <= MAX_BYTES + 32 * 1024**2 or
            not isinstance(bundle['sha256'], str) or not SHA.fullmatch(bundle['sha256']) or
            not isinstance(bundle['parts'], list) or not 1 <= len(bundle['parts']) <= MAX_PARTS):
        raise TransportError('invalid bounded archive identity')
    ids = set(); size = 0
    for index, part in enumerate(bundle['parts']):
        if (not isinstance(part, dict) or set(part) != {'id', 'name', 'size', 'sha256'} or
                not _positive(part['id']) or part['id'] in ids or type(part['size']) is not int or
                not 0 < part['size'] <= CHUNK_BYTES or not isinstance(part['sha256'], str) or
                not SHA.fullmatch(part['sha256']) or
                part['name'] != _prefix(context['name']) + str(index).zfill(4) + '-' + part['sha256']):
            raise TransportError('invalid ordered archive chunk')
        ids.add(part['id']); size += part['size']
    if size != bundle['size']: raise TransportError('archive chunk sizes do not cover complete bytes')


def _extract(bundle, output, files):
    seen = set()
    with tarfile.open(bundle, 'r:') as source:
        for item in source:
            _path(item.name)
            if not item.isfile() or item.sparse is not None or item.name in seen or item.name not in files:
                raise TransportError('unexpected, linked or duplicate transport member')
            expected = files[item.name]
            if item.size != expected['size'] or item.mode != expected['mode']:
                raise TransportError('transport header differs from file inventory')
            destination = output / item.name; destination.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(item) as stream, destination.open('xb') as target: shutil.copyfileobj(stream, target)
            if archive.digest(destination) != expected['sha256']: raise TransportError('transport member bytes differ')
            destination.chmod(expected['mode']); seen.add(item.name)
    if seen != set(files): raise TransportError('transport is missing declared files')


def fetch_bundle(repository, run_id, attempt, source_commit, workflow, name, output, *,
                 job_id=None, job_name=None, manifest_id=None, manifest_sha256=None,
                 allow_failed=False, transport=None):
    """Fetch an exact completed producer; no automatic failed-run fallback."""
    context = _context(repository, run_id, attempt, source_commit, workflow, name)
    if ((manifest_id is None) != (manifest_sha256 is None) or manifest_id is not None and
            (not _positive(manifest_id) or not isinstance(manifest_sha256, str) or not SHA.fullmatch(manifest_sha256))):
        raise TransportError('pin both manifest asset ID and SHA256')
    output = Path(output).absolute()
    if output.exists() or output.is_symlink(): raise TransportError('transport output must be new')
    remote = delivery.Remote(repository, transport); repository_id = _run(remote, context)
    info = _store(remote, context, repository_id); rows = _assets(remote, info, name)
    row = rows.get(_manifest_name(name))
    if (row is None or not 0 < row['size'] <= MAX_MANIFEST or
            manifest_id is not None and (row['id'] != manifest_id or row['digest'] != 'sha256:' + manifest_sha256)):
        raise TransportError('complete pinned transport manifest is absent or differs')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.foundation-ci-fetch-', dir=output.parent) as temporary:
        stage = Path(temporary); path = stage / 'manifest.json'; remote.download(row, path)
        manifest = delivery.parse(path.read_bytes()); _validate_manifest(manifest, context, info, repository_id)
        if job_id is not None and manifest['producer']['id'] != job_id: raise TransportError('manifest producer differs')
        producer, job = _producer(remote, context, job_id=manifest['producer']['id'], job_name=job_name, allow_failed=allow_failed)
        if producer != manifest['producer']: raise TransportError('manifest producer identity differs')
        parts = manifest['archive']['parts']; expected_names = {p['name'] for p in parts} | {row['name']}
        if set(rows) != expected_names or any(_asset(rows[p['name']]) != p for p in parts):
            raise TransportError('remote bundle is not the complete declared asset set')
        bundle = stage / 'payload.tar'
        with bundle.open('xb') as stream:
            for part in parts:
                path = stage / part['name']; remote.download(rows[part['name']], path, part['sha256'])
                with path.open('rb') as source: shutil.copyfileobj(source, stream)
                path.unlink()
        if bundle.stat().st_size != manifest['archive']['size'] or archive.digest(bundle) != manifest['archive']['sha256']:
            raise TransportError('reconstructed archive bytes differ')
        extracted = stage / 'payload'; extracted.mkdir(); _extract(bundle, extracted, manifest['files'])
        _run(remote, context)
        if (_store(remote, context, repository_id)['id'] != info['id'] or _assets(remote, info, name) != rows or
                _producer(remote, context, job_id=producer['id'], allow_failed=allow_failed)[1] != job):
            raise TransportError('producer or release assets changed during fetch')
        pointer = _pointer(context, info, producer, row)
        extracted.rename(output)
        return dict(pointer=pointer, manifest=manifest, producer=job)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('publish', 'fetch'))
    for flag in ('repository', 'source-commit', 'workflow', 'name'): parser.add_argument('--' + flag, required=True)
    for flag in ('run-id', 'attempt'): parser.add_argument('--' + flag, type=int, required=True)
    parser.add_argument('--job-id', type=int); parser.add_argument('--job-name')
    parser.add_argument('--root', type=Path); parser.add_argument('--path', action='append', default=[])
    parser.add_argument('--metadata', type=Path); parser.add_argument('--pointer', type=Path)
    parser.add_argument('--allow-missing', action='store_true'); parser.add_argument('--allow-failed', action='store_true')
    parser.add_argument('--output', type=Path); parser.add_argument('--receipt', type=Path)
    parser.add_argument('--manifest-id', type=int); parser.add_argument('--manifest-sha256')
    args = parser.parse_args(argv)
    common = dict(repository=args.repository, run_id=args.run_id, attempt=args.attempt,
                  source_commit=args.source_commit, workflow=args.workflow, name=args.name,
                  job_id=args.job_id, job_name=args.job_name)
    if args.operation == 'publish':
        if args.root is None or not args.path: parser.error('publish requires --root and --path')
        result = publish_bundle(**common, root=args.root, paths=args.path, allow_missing=args.allow_missing,
                                metadata=delivery.parse(args.metadata.read_bytes()) if args.metadata else None)
        destination = args.pointer
    else:
        if args.output is None: parser.error('fetch requires --output')
        result = fetch_bundle(**common, output=args.output, manifest_id=args.manifest_id,
                              manifest_sha256=args.manifest_sha256, allow_failed=args.allow_failed)
        destination = args.receipt
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream: stream.write(archive.encoded(result))
    print(json.dumps(result if args.operation == 'publish' else result['pointer'], sort_keys=True))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, delivery.DeliveryError) as error:
        raise SystemExit('ci-transport: ' + str(error) + '; preserve remote state and reconcile before retry')
