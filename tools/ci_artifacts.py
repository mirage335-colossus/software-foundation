#!/usr/bin/env python3
"""Bounded same-run evidence artifacts; large inputs keep release transport.

Artifacts only carry bytes. Consumers verify the exact local manifest and archive;
ci_transport authenticates their producer against one shared run/job inventory.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

import ci_transport as bundles
import dependency_archive as archive
import github_release as delivery

MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_FILES = 1000
MAX_EVIDENCE_SLOTS = 48
TARGETS = ('linux-x86_64', 'linux-aarch64', 'windows-x86_64')
SCOPES = ('core', 'tools', 'integration')
CONTROLS = ('qualification-inputs', 'certificate', 'certification-delivery',
            'candidate-coverage', 'apt-mechanism')
FIXED_SLOTS = tuple('source-' + target + '-' + scope for target in TARGETS for scope in SCOPES) + CONTROLS
SLOTS = FIXED_SLOTS + tuple('evidence-' + str(index).zfill(2) for index in range(MAX_EVIDENCE_SLOTS))
MAX_ARTIFACTS = len(SLOTS)
ROOT_ENV = 'FOUNDATION_CI_ARTIFACTS_DIR'


def _error(message):
    raise bundles.TransportError(message)


def _directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        _error('artifact paths require ordinary directories without links')


def _parents(path):
    for current in (path, *path.parents):
        try: _directory(current)
        except FileNotFoundError: pass


def slot_for(name, attempt, index=None):
    """Finite immutable names bound storage even when the check matrix grows."""
    suffix = '-' + str(attempt)
    if not name.endswith(suffix): return None
    label = name[:-len(suffix)]
    if label in FIXED_SLOTS: return label
    if re.fullmatch(r'evidence-batch-[a-z0-9_-]+', label):
        if type(index) is int and 0 <= index < MAX_EVIDENCE_SLOTS:
            return 'evidence-' + str(index).zfill(2)
    return None


def artifact_name(context, slot):
    if slot not in SLOTS: _error('unknown bounded artifact slot')
    return f"foundation-evidence-{context['run_id']}-{context['attempt']}-{slot}"


def current_context():
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    reference = os.environ.get('GITHUB_WORKFLOW_REF', '')
    prefix = repository + '/.github/workflows/'
    if not reference.startswith(prefix) or '@' not in reference[len(prefix):]:
        _error('artifact context requires the exact current workflow reference')
    try:
        value = dict(repository=repository, run_id=int(os.environ['GITHUB_RUN_ID']),
                     attempt=int(os.environ['GITHUB_RUN_ATTEMPT']), source_commit=os.environ['GITHUB_SHA'],
                     workflow=reference[len(prefix):].split('@', 1)[0])
    except (KeyError, ValueError): _error('artifact context requires the exact current workflow run')
    bundles._context(**value, name='context')
    return value


def prepare(repository, run_id, attempt, source_commit, workflow, name, root, paths, output, *,
            slot=None, metadata=None, job_id=None, job_name=None, runner_name=None, allow_missing=False):
    """Stage <=2 MiB complete evidence or choose release fallback without loss."""
    context = bundles._context(repository, run_id, attempt, source_commit, workflow, name)
    selected = slot_for(name, attempt, slot)
    if selected is None: return dict(transport='release', reason='outside finite evidence slots')
    if not isinstance(runner_name, str) or not runner_name or len(runner_name) > 1024:
        _error('artifact producer requires its exact runner name')
    if job_name is not None and (not isinstance(job_name, str) or not job_name or len(job_name) > 1024):
        _error('artifact producer job name must be explicit or absent')
    if job_id is not None and not bundles._positive(job_id):
        _error('artifact producer job ID must be positive or absent')
    files = bundles._inventory(root, paths, allow_missing)
    if len(files) > MAX_FILES or sum(item['size'] for item in files.values()) > MAX_EXPANDED_BYTES:
        return dict(transport='release', reason='evidence exceeds expanded byte or file budget')
    output = Path(output).absolute()
    if output.exists() or output.is_symlink(): _error('artifact staging output must be new')
    _parents(output.parent); output.parent.mkdir(parents=True, exist_ok=True)
    staged = bundles._stage_bundle(output, context, root, paths, metadata=metadata,
                                  allow_missing=allow_missing, compress=True)
    if len(staged['chunks']) != 1: _error('bounded evidence unexpectedly produced multiple parts')
    payload = output / 'payload.tar.gz'
    staged['chunks'][0][0].rename(payload)
    manifest = dict(schema_version=1, kind='actions-ci-evidence', **context, slot=selected,
                    producer=dict(job_id=job_id, job_name=job_name, runner_name=runner_name), metadata=staged['metadata'],
                    files=staged['files'], archive={key: staged['whole'][key] for key in ('size', 'sha256')})
    encoded = archive.encoded(manifest)
    if len(encoded) > MAX_MANIFEST_BYTES or len(encoded) + payload.stat().st_size > MAX_BUNDLE_BYTES:
        shutil.rmtree(output)
        return dict(transport='release', reason='complete compressed evidence exceeds artifact byte budget')
    with (output / 'manifest.json').open('xb') as stream: stream.write(encoded)
    return dict(transport='actions', artifact_name=artifact_name(context, selected), path=str(output),
                bytes=len(encoded) + payload.stat().st_size, manifest_sha256=archive.digest(output / 'manifest.json'))


def _validate(value, context, directory_name):
    fields = set(context) | {'schema_version', 'kind', 'slot', 'producer', 'metadata', 'files', 'archive'}
    if (not isinstance(value, dict) or set(value) != fields or type(value['schema_version']) is not int or
            value['schema_version'] != 1 or value['kind'] != 'actions-ci-evidence' or
            any(type(value.get(key)) is not type(expected) or value[key] != expected for key, expected in context.items())):
        _error('artifact manifest provenance differs')
    slot = value['slot']
    index = int(slot[-2:]) if isinstance(slot, str) and re.fullmatch(r'evidence-[0-9]{2}', slot) else None
    if slot_for(context['name'], context['attempt'], index) != slot or directory_name != artifact_name(context, slot):
        _error('artifact name or fixed slot differs')
    producer = value['producer']
    if (not isinstance(producer, dict) or set(producer) != {'job_id', 'job_name', 'runner_name'} or
            producer['job_id'] is not None and not bundles._positive(producer['job_id']) or
            not isinstance(producer['runner_name'], str) or not 0 < len(producer['runner_name']) <= 1024 or
            producer['job_name'] is not None and (not isinstance(producer['job_name'], str) or
                not 0 < len(producer['job_name']) <= 1024)):
        _error('artifact producer descriptor differs')
    if not isinstance(value['metadata'], dict) or len(archive.encoded(value['metadata'])) > MAX_MANIFEST_BYTES:
        _error('artifact metadata must be a bounded object')
    files = value['files']
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES: _error('artifact file inventory is invalid')
    registry = archive.PathInventory(); total = 0
    for name, item in files.items():
        bundles._path(name); registry.add(name, False)
        if (not isinstance(item, dict) or set(item) != {'size', 'mode', 'sha256'} or
                type(item['size']) is not int or item['size'] < 0 or type(item['mode']) is not int or
                item['mode'] not in (0o644, 0o755) or not isinstance(item['sha256'], str) or
                not bundles.SHA.fullmatch(item['sha256'])):
            _error('artifact file identity differs')
        total += item['size']
    package = value['archive']
    if (total > MAX_EXPANDED_BYTES or not isinstance(package, dict) or set(package) != {'size', 'sha256'} or
            type(package['size']) is not int or not 0 < package['size'] <= MAX_BUNDLE_BYTES or
            not isinstance(package['sha256'], str) or not bundles.SHA.fullmatch(package['sha256'])):
        _error('artifact archive identity or expanded size differs')


def fetch_local(context, request, output_stage):
    """Return validated local bytes, or None only when the exact bundle is absent.

    ci_transport must authenticate the returned producer in its shared job snapshot
    before releasing any staged output. Local manifest fields are not qualification.
    """
    configured = os.environ.get(ROOT_ENV)
    if not configured: return None
    expected = bundles._context(**{key: context[key] for key in ('repository', 'run_id', 'attempt', 'source_commit', 'workflow')},
                                name=request['name'])
    if current_context() != {key: value for key, value in expected.items() if key != 'name'}:
        _error('local artifacts may only satisfy their exact current run and workflow')
    root = Path(configured).absolute(); _parents(root)
    if not root.exists(): return None
    entries = sorted(root.iterdir())
    if len(entries) > MAX_ARTIFACTS: _error('artifact inventory exceeds finite storage slots')
    found = None; selected_manifest = None; selected_bytes = None; names = set()
    prefix = f"foundation-evidence-{expected['run_id']}-{expected['attempt']}-"
    for directory in entries:
        _directory(directory)
        if not directory.name.startswith(prefix) or directory.name[len(prefix):] not in SLOTS:
            _error('unexpected same-run artifact directory')
        if {path.name for path in directory.iterdir()} != {'manifest.json', 'payload.tar.gz'}:
            _error('artifact must contain only its manifest and complete archive')
        manifest_path = directory / 'manifest.json'; info = bundles._ordinary(manifest_path)
        payload_info = bundles._ordinary(directory / 'payload.tar.gz')
        if not 0 < info.st_size <= MAX_MANIFEST_BYTES or info.st_size + payload_info.st_size > MAX_BUNDLE_BYTES:
            _error('artifact exceeds stored byte budget')
        data = manifest_path.read_bytes(); manifest = delivery.parse(data)
        if not isinstance(manifest, dict) or not isinstance(manifest.get('name'), str): _error('artifact name is absent')
        selected = dict(expected, name=manifest['name'])
        bundles._context(**selected); _validate(manifest, selected, directory.name)
        if manifest['name'] in names: _error('duplicate artifact bundle name')
        names.add(manifest['name'])
        if manifest['name'] == expected['name']:
            found, selected_manifest, selected_bytes = directory, manifest, data
    if found is None: return None
    if request.get('manifest_id') is not None or request.get('manifest_sha256') is not None:
        _error('release asset pins cannot be satisfied by an Actions artifact')
    if (request.get('job_name') is not None and selected_manifest['producer']['job_name'] is not None and
            selected_manifest['producer']['job_name'] != request['job_name']):
        _error('artifact producer job name differs')
    payload = found / 'payload.tar.gz'; package = selected_manifest['archive']
    if payload.stat().st_size != package['size'] or archive.digest(payload) != package['sha256']:
        _error('artifact archive bytes differ')
    output_stage = Path(output_stage).absolute()
    if output_stage.exists() or output_stage.is_symlink(): _error('artifact extraction output must be new')
    _parents(output_stage.parent); output_stage.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.artifact-check-', dir=output_stage.parent) as temporary:
        stage = Path(temporary) / 'payload'; stage.mkdir()
        bundles._extract(payload, stage, selected_manifest['files'])
        # Catch replacement during extraction; the whole hash and per-file hashes
        # are independently checked before any bytes leave the private stage.
        if (found / 'manifest.json').read_bytes() != selected_bytes or archive.digest(payload) != package['sha256']:
            _error('artifact changed during verification')
        if output_stage.exists() or output_stage.is_symlink(): _error('artifact extraction output must be new')
        stage.rename(output_stage)
    pointer = dict(schema_version=1, transport='actions', **expected, artifact_name=found.name,
                   manifest_sha256=archive.digest(found / 'manifest.json'))
    return dict(pointer=pointer, manifest=selected_manifest, producer=selected_manifest['producer'])


def _lifecycle():
    path = Path(__file__).resolve().parents[1] / '.github/scripts/lifecycle.py'
    spec = importlib.util.spec_from_file_location('foundation_artifact_lifecycle', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _output(name, value):
    if any(c in str(value) for c in '\r\n'): _error('workflow outputs require single lines')
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as stream:
        stream.write(name + '=' + str(value) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'fallback'))
    args = parser.parse_args(argv)
    lifecycle = _lifecycle()
    if args.operation == 'fallback':
        # Retain every original selected file if size or service quota prevented
        # the Actions upload. Release transport keeps its immutable validation.
        lifecycle.store_bundle()
        return
    context = current_context(); name = os.environ['BUNDLE_NAME']; slot = os.environ.get('ARTIFACT_SLOT', '')
    if slot and not slot.isdecimal(): _error('artifact slot must be a nonnegative matrix index')
    root, paths = lifecycle.bundle_inputs(os.environ['BUNDLE_PATHS'])
    destination = Path(os.environ['RUNNER_TEMP']) / ('foundation-evidence-stage-' + name)
    if os.environ.get('GITHUB_SERVER_URL', 'https://github.com') != 'https://github.com':
        result = dict(transport='release', reason='Actions artifact v4 requires GitHub.com')
    else:
        index = int(slot) if slot else None
        producer = {}
        if slot_for(name, context['attempt'], index) is not None:
            # One shared job inventory pins the real producer, including reused
            # self-hosted runners and nested reusable workflow display names.
            observed, _ = bundles._producer(delivery.Remote(context['repository']),
                dict(context, name=name), runner_name=os.environ.get('RUNNER_NAME'), publishing=True)
            producer = dict(job_id=observed['id'], job_name=observed['name'])
        result = prepare(**context, name=name, root=root, paths=paths, output=destination,
                         slot=index, runner_name=os.environ.get('RUNNER_NAME'), **producer)
    for key in ('transport', 'artifact_name', 'path'):
        _output(key.replace('_', '-'), result.get(key, ''))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    delivery.enable_metrics()
    try: main()
    except (ValueError, OSError, delivery.DeliveryError) as error:
        raise SystemExit('ci-artifacts: ' + str(error))
