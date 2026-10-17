#!/usr/bin/env python3
"""Offline, bounded qualification of independently pinned appended compositions.

This module validates evidence; it never reconstructs, configures or compiles a
kernel. Hash pins establish the selected bytes, not the producer's identity.
Authenticated evidence acquisition and the decision to trust its producer remain
the caller's responsibility. Certificates always live outside their subject.
"""
import argparse
from contextlib import contextmanager
import copy
import io
import json
import math
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile
import threading

import appended_container as container
import appended_release as appended
import certify_release as legacy
import release as release_tools

coverage = legacy.coverage
POLICY_KIND = 'foundation-appended-qualification-policy'
PLAN_KIND = 'foundation-appended-qualification-plan'
PROOF_KIND = 'foundation-retained-kernel-proof'
CERTIFICATE_KIND = 'foundation-appended-composition-certificate'
SCOPES = frozenset({'composition-integrity', 'offline-recompose', 'retained-runtime',
                    'guest-source', 'install-upgrade', 'browser'})
KERNEL_ASSERTIONS = frozenset({'sealed-kernel', 'loader-contract', 'module-profile', 'service-abi'})
MAX_PROOF = 512 * 1024 * 1024
MAX_PROOF_FILES = 16384
MAX_TOOL_SOURCE = 8 * 1024 * 1024
MAX_TOOL_SOURCES = 32 * 1024 * 1024
TOOL_ROOT = Path(__file__).resolve().parents[1]
COMPLETION_FILE = 'composition-completion.json'
# Immutable schema-v1 source catalog. Changing its filenames requires a new
# plan/catalog schema; historical v1 certificates retain this exact registry.
COMMON_TOOL_SOURCES_V1 = (
    'tools/appended_release_check.py', 'tools/appended_qualification.py',
    'tools/appended_release.py', 'tools/appended_container.py', 'tools/appended_project.py',
    'tools/appended_policy.py', 'tools/appended_wasm.py', 'tools/source_identity.py',
    'tools/artifact.py', 'tools/dependency_archive.py', 'tools/process_tree.py',
    'tools/coverage.py', 'tools/certify_release.py', 'tools/release.py',
    'tools/dependency_store.py', 'tools/rust_sdk.py', 'tools/sdk_environment.py',
    'tools/sdk_manifest.py', 'tools/verify_abi.py',
)
SCOPE_TOOL_SOURCES_V1 = {
    'guest-source': ('tools/appended_guest_check.py', 'tools/appended_compile.py'),
    'install-upgrade': ('tools/appended_install_check.py',),
    'browser': ('tools/appended_browser_check.py', 'gui/tests/browser_test.py'),
}
_RUN_ENVIRONMENT = threading.RLock()


def _version(value, kind):
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1 or value.get('kind') != kind:
        raise ValueError('unsupported ' + kind + ' schema')


def _same(left, right):
    """JSON byte equivalence preserves integer/boolean (and float) types."""
    def encoded(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return encoded(left) == encoded(right)


def _name(value):
    if type(value) is not str or not coverage.NAME.fullmatch(value):
        raise ValueError('invalid qualification identity')
    return value


def _names(value, label):
    if (type(value) is not list or not value or len(value) > 4096 or
            any(type(x) is not str or not coverage.NAME.fullmatch(x) for x in value) or
            len(value) != len(set(value))):
        raise ValueError('invalid nonempty ' + label)
    return value


def _fresh_report(value, *, completed=True):
    required = {'schema_version', 'plan', 'subject', 'check', 'run_id', 'attempt', 'status',
                'exit_code', 'created_at', 'argv', 'host', 'warnings', 'error', 'seconds', 'evidence'}
    coverage.fields(value, required | ({'completion'} if completed else set()))
    if completed:
        _reference(value['completion'])
        if value['completion']['path'] != COMPLETION_FILE:
            raise ValueError('fresh result requires the fixed wrapper completion artifact')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            type(value['run_id']) is not str or not coverage.NAME.fullmatch(value['run_id']) or
            type(value['attempt']) is not int or value['attempt'] < 1 or
            value['exit_code'] is not None and type(value['exit_code']) is not int or
            type(value['seconds']) not in (int, float) or
            type(value['seconds']) is float and not math.isfinite(value['seconds']) or value['seconds'] < 0):
        raise ValueError('invalid typed fresh execution result')
    coverage.text(value['created_at'])
    if type(value['argv']) is not list or not 1 <= len(value['argv']) <= 256 or type(value['warnings']) is not list:
        raise ValueError('invalid fresh command or warning inventory')
    for item in [*value['argv'], *value['warnings']]:
        coverage.text(item)
    return value


def _reference(value):
    coverage.fields(value, {'path', 'sha256'})
    container.resource_path(value['path'])
    appended._sha(value['sha256'])
    return value


def _root(candidate, evidence_root):
    root = Path(evidence_root) if evidence_root is not None else Path(candidate).absolute().parent
    return container._ordinary_path(root, directory=True)


def requirements(policy, profile):
    """Validate the complete versioned support policy, including required gates."""
    coverage.fields(policy, {'schema_version', 'kind', 'profiles'})
    _version(policy, POLICY_KIND)
    if type(policy['profiles']) is not dict or not policy['profiles'] or profile not in policy['profiles']:
        raise ValueError('unknown appended qualification profile')
    for name in policy['profiles']:
        _name(name)
    selected = policy['profiles'][profile]
    coverage.fields(selected, {'description', 'artifacts', 'checks', 'kernel_scopes', 'kernel_assertions'})
    coverage.text(selected['description'])
    artifacts = selected['artifacts']
    if type(artifacts) is not dict or not 1 <= len(artifacts) <= 32:
        raise ValueError('empty or excessive artifact support contract')
    for identity, entry in artifacts.items():
        _name(identity)
        coverage.fields(entry, {'target', 'backend', 'carrier', 'baseline', 'channels'})
        _name(entry['target']); _name(entry['backend']); _name(entry['baseline'])
        _names(entry['channels'], 'delivery channel inventory')
        if entry['channels'] != sorted(entry['channels']):
            raise ValueError('delivery channels must be sorted and unique')
        if entry['carrier'] not in ('elf', 'pe', 'html'):
            raise ValueError('unsupported qualification carrier')
        if entry['carrier'] == 'elf' and not entry['target'].startswith('linux-'):
            raise ValueError('ELF artifact requires a Linux target')
        if entry['carrier'] == 'pe' and not entry['target'].startswith('windows-'):
            raise ValueError('PE artifact requires a Windows target')
    _names(selected['kernel_scopes'], 'kernel scope inventory')
    _names(selected['kernel_assertions'], 'kernel assertion inventory')
    if not {'source', 'archive', 'recovery'} <= set(selected['kernel_scopes']):
        raise ValueError('kernel proof requires original source, archive and recovery scopes')
    if any(row['carrier'] == 'elf' and row['target'].startswith('linux-') for row in artifacts.values()) and 'abi' not in selected['kernel_scopes']:
        raise ValueError('native Linux kernel proof requires applicable original ABI coverage')
    if not KERNEL_ASSERTIONS <= set(selected['kernel_assertions']):
        raise ValueError('kernel proof omits a required appended contract assertion')
    checks = selected['checks']
    if type(checks) is not list or not 1 <= len(checks) <= 4096:
        raise ValueError('empty or excessive composition check inventory')
    ids, keys = set(), set()
    for row in checks:
        coverage.fields(row, {'id', 'artifact', 'scope', 'target', 'backend', 'environment', 'assertions'}, {'scenario'})
        for field in ('id', 'scope', 'target', 'backend', 'environment'):
            _name(row[field])
        _names(row['assertions'], 'executed assertion inventory')
        if row['id'] in ids or row['scope'] not in SCOPES:
            raise ValueError('duplicate check or unsupported composition scope')
        ids.add(row['id'])
        key = tuple(row[k] for k in ('artifact', 'scope', 'target', 'backend', 'environment'))
        if key in keys:
            raise ValueError('duplicate composition qualification scope')
        keys.add(key)
        if row['artifact'] is None:
            expected = (('portable-wasm32', 'guest', 'sdk-host') if row['scope'] == 'guest-source'
                        else ('composition', 'none', 'portable'))
            if (row['scope'] not in ('composition-integrity', 'offline-recompose', 'guest-source') or
                    tuple(row[k] for k in ('target', 'backend', 'environment')) != expected):
                raise ValueError('global scope must name its portable composition or guest environment')
        else:
            if row['artifact'] not in artifacts or row['scope'] not in ('retained-runtime', 'install-upgrade', 'browser'):
                raise ValueError('artifact scope is not in the support contract')
            entry = artifacts[row['artifact']]
            if (row['target'], row['backend']) != (entry['target'], entry['backend']):
                raise ValueError('check target/backend differs from delivered artifact')
            if row['scope'] != 'browser' and row['environment'] != entry['baseline']:
                raise ValueError('runtime/install environment differs from promised artifact baseline')
            if row['scope'] == 'browser' and (entry['carrier'] != 'html' or row['environment'] not in ('firefox', 'chromium')):
                raise ValueError('browser qualification requires an actual named supported browser')
        if 'scenario' in row:
            _reference(row['scenario'])
            if row['scope'] not in ('retained-runtime', 'browser', 'install-upgrade', 'guest-source'):
                raise ValueError('scenario is not applicable to this check')
    for scope in ('composition-integrity', 'offline-recompose'):
        if sum(row['scope'] == scope for row in checks) != 1:
            raise ValueError('exactly one global integrity and recomposition check is required')
    if sum(row['scope'] == 'guest-source' for row in checks) > 1:
        raise ValueError('guest-source executes once per shared payload')
    for identity, entry in artifacts.items():
        rows = [row for row in checks if row['artifact'] == identity]
        if not {'retained-runtime', 'install-upgrade'} <= {row['scope'] for row in rows}:
            raise ValueError('each delivered artifact needs runtime and install-upgrade coverage')
        if entry['carrier'] == 'html' and not any(row['scope'] == 'browser' for row in rows):
            raise ValueError('HTML carrier requires actual browser qualification')
    return selected


def _subject(directory, pin, policy, profile):
    subject = appended.verify_composition_subject(directory, pin)
    selected = requirements(policy, profile)
    composition = subject['composition']
    artifacts = {entry['id']: entry for entry in composition['artifacts']}
    if set(artifacts) != set(selected['artifacts']):
        raise ValueError('composition artifact set differs from support contract')
    # The internal HTML engine is not implemented. HTML carriers of the binary
    # profile are supported only through their actual browser qualification.
    if composition['payload']['mode'] not in ('binary', 'neither') or any(
            entry['profile'] != 'binary' for entry in artifacts.values()):
        raise ValueError('web/both composition qualification awaits the internal engine')
    guest = [row for row in selected['checks'] if row['scope'] == 'guest-source']
    if bool(guest) != (composition['payload']['mode'] == 'binary'):
        raise ValueError('guest-source is required exactly when a binary payload is delivered')
    for identity, row in artifacts.items():
        if row['carrier'] != selected['artifacts'][identity]['carrier']:
            raise ValueError('artifact carrier differs from qualification policy')
    return subject, selected


@contextmanager
def _proof_tree(path, expected_sha256):
    saved = container._snapshot(path, MAX_PROOF)
    if container.digest(saved.content) != appended._sha(expected_sha256):
        raise ValueError('retained proof differs from its independent SHA-256 pin')
    # Parse only ordinary canonical portable entries; no archive extraction API
    # receives untrusted paths. Bound both expanded bytes and member count.
    with tempfile.TemporaryDirectory(prefix='foundation-kernel-proof-') as temporary:
        root = Path(temporary)
        files, seen, total = {}, set(), 0
        with tarfile.open(fileobj=io.BytesIO(saved.content), mode='r:*') as bundle:
            for member in bundle:
                name = member.name.rstrip('/') if member.isdir() else member.name
                container.resource_path(name)
                key = name.casefold()
                if key in seen or len(seen) >= MAX_PROOF_FILES or not (member.isfile() or member.isdir()):
                    raise ValueError('duplicate, excessive or nonordinary retained proof member')
                seen.add(key)
                if member.mode & 0o7000:
                    raise ValueError('privileged retained proof member')
                destination = root.joinpath(*coverage.relative(name).parts)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                total += member.size
                if member.size < 0 or total > MAX_PROOF:
                    raise ValueError('expanded retained proof exceeds bounded offline limits')
                with bundle.extractfile(member) as stream:
                    data = stream.read(member.size + 1)
                if len(data) != member.size:
                    raise ValueError('retained proof member size differs')
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open('xb') as stream:
                    stream.write(data)
                destination.chmod(0o755 if member.mode & 0o111 else 0o644)
                files[name] = container.digest(data)
        manifest = coverage.load(root / 'kernel-proof.json')
        coverage.fields(manifest, {'schema_version', 'kind', 'files', 'descriptor', 'release', 'certificate',
                                  'plan', 'policy', 'profile', 'reports', 'target', 'backend', 'archive',
                                  'runtime_member', 'appended_check'}, {'adoption'})
        _version(manifest, PROOF_KIND)
        if manifest['files'] != {k: v for k, v in files.items() if k != 'kernel-proof.json'}:
            raise ValueError('retained proof complete file inventory differs')
        for key in ('descriptor', 'release', 'certificate', 'plan', 'policy'):
            container.resource_path(manifest[key])
            if manifest[key] not in manifest['files']:
                raise ValueError('retained proof omits a typed evidence document')
        if 'adoption' in manifest:
            container.resource_path(manifest['adoption'])
            if manifest['adoption'] not in manifest['files']:
                raise ValueError('retained proof omits original adoption evidence')
        for key in ('profile', 'target', 'backend', 'appended_check'):
            _name(manifest[key])
        container.resource_path(manifest['archive']); container.resource_path(manifest['runtime_member'])
        if (type(manifest['reports']) is not list or not manifest['reports'] or
                len(manifest['reports']) > 4096 or len(manifest['reports']) != len(set(manifest['reports']))):
            raise ValueError('retained proof needs the complete original report selection')
        for name in manifest['reports']:
            container.resource_path(name)
            if name not in manifest['files']:
                raise ValueError('original report absent from retained proof')
        yield root, manifest
        container._recheck(saved)


def verify_retained_kernel_proof(candidate, artifact_id, proof_bundle, proof_sha256, policy_requirements):
    """Reproduce an original certificate, preserving its original evidence IDs.

    ``candidate`` is the result of verify_composition_subject, not an opaque
    caller status. All original report/evidence bytes are checked by the legacy
    certifier; no old receipt is rewritten or relabelled for the new run.
    """
    artifact_id = _name(artifact_id)
    products = {row['id']: row for row in candidate['composition']['artifacts']}
    kernels = {row['id']: row for row in candidate['selection']['kernels']}
    if artifact_id not in products or artifact_id not in kernels:
        raise ValueError('retained proof names an unknown selected artifact')
    product, kernel = products[artifact_id], kernels[artifact_id]
    with _proof_tree(proof_bundle, proof_sha256) as (root, proof):
        release_path = coverage.local(root, proof['release'])
        if release_path.name != 'release.json':
            raise ValueError('original release metadata must retain its original layout')
        old_root = release_path.parent
        # Full byte/source/dependency verification is offline. In particular this
        # never invokes release_check or a source/recovery builder.
        release_tools.verify_metadata(old_root)
        manifest = release_tools.verify_selection(old_root, proof['target'], proof['backend'], 'recovery')
        old_policy, old_plan = coverage.load(coverage.local(root, proof['policy'])), coverage.load(coverage.local(root, proof['plan']))
        old_certificate = coverage.load(coverage.local(root, proof['certificate']))
        if (type(manifest['schema_version']) is not int or type(old_policy['schema_version']) is not int or
                type(old_plan['schema_version']) is not int):
            raise ValueError('original evidence schema versions must retain integer types')
        reports = [coverage.local(root, name) for name in proof['reports']]
        adoption = coverage.load(coverage.local(root, proof['adoption'])) if 'adoption' in proof else None
        reproduced = legacy.certify(old_root, manifest, old_plan, reports, old_policy, proof['profile'], adoption=adoption)
        if (not _same(old_certificate, reproduced) or reproduced['status'] not in ('passed', 'passed_with_warnings') or
                reproduced['eligible_for_promotion'] is not True or reproduced['experiment'] is not False or reproduced['omitted']):
            raise ValueError('original complete certificate is missing, changed, experimental or ineligible')
        selected = policy_requirements['artifacts'][artifact_id]
        if (proof['target'], proof['backend']) != (selected['target'], selected['backend']):
            raise ValueError('original proof target/backend differs from selected artifact')
        scopes = {row['scope'] for row in old_plan['checks'] if row['target'] == proof['target'] and
                  row['backend'] == proof['backend'] and row['required']}
        if not set(policy_requirements['kernel_scopes']) <= scopes:
            raise ValueError('original kernel source/recovery/ABI coverage is incomplete')
        choices = [row for row in manifest['artifacts'] if row['target'] == proof['target'] and
                   proof['backend'] in (row['backends'] or ['core']) and row['archive'] == proof['archive']]
        if len(choices) != 1 or choices[0]['sha256'] != kernel['archive']['sha256']:
            raise ValueError('original certified archive differs from retained selected archive')
        if (manifest['source']['sha256'] != kernel['original_source']['sha256'] or
                manifest['source']['tree_sha256'] != kernel['original_source']['tree_sha256'] or
                manifest['source']['tree_sha256'] != product['original_source_tree_sha256']):
            raise ValueError('original certified kernel source differs from retained source')
        retained_groups = {row['sha256'] for row in kernel['recovery']}
        selected_recipes = release_tools.dependency_recipes(choices[0])
        selected_dependencies = [group for group in manifest['dependencies'] if group['recipe_id'] in selected_recipes]
        dependency_groups = {value for group in selected_dependencies for value in group['files'].values()}
        if not dependency_groups or not dependency_groups <= retained_groups:
            raise ValueError('candidate omits original complete SDK binary/source/checksum groups')
        descriptor_path = coverage.local(root, proof['descriptor'])
        descriptor_sha256 = coverage.sha(descriptor_path)
        descriptor = container.validate_descriptor(coverage.load(descriptor_path))
        if descriptor_sha256 != kernel['descriptor']['sha256'] or descriptor_sha256 != product['kernel_descriptor_sha256']:
            raise ValueError('certified descriptor differs from selected descriptor bytes')
        _, original_members, _ = appended._members(old_root / proof['archive'])
        if proof['runtime_member'] != kernel['runtime_member'] or proof['runtime_member'] not in original_members:
            raise ValueError('certified runtime member differs from selected member')
        runtime, _ = original_members[proof['runtime_member']]
        parsed = container.parse_artifact(runtime, descriptor)
        binding = {'descriptor_sha256': descriptor_sha256, 'kernel_prefix_sha256': container.digest(parsed.prefix),
                   'kernel_prefix_length': len(parsed.prefix), 'profile': descriptor['profile'], 'abi': descriptor['abi'],
                   'archive_sha256': choices[0]['sha256'], 'runtime_member': proof['runtime_member'],
                   'source_tree_sha256': manifest['source']['tree_sha256']}
        if any(not _same(binding[k], product[k]) for k in ('kernel_prefix_sha256', 'kernel_prefix_length', 'profile', 'abi')):
            raise ValueError('finalized certified prefix/profile/ABI differs from composition')
        checks = {row['id']: row for row in old_plan['checks']}
        check = checks.get(proof['appended_check'])
        if (check is None or check['scope'] != 'appended-kernel' or not check['required'] or
                check['target'] != proof['target'] or check['backend'] != proof['backend'] or
                check['environment'] != selected['baseline'] or
                'qualification' not in check or 'junit' not in check or
                not set(policy_requirements['kernel_assertions']) <= set(check['expected_tests'])):
            raise ValueError('original certificate lacks an explicit executed appended-kernel contract check')
        report = reproduced['coverage'][proof['appended_check']]
        report_path = next(path for path in reports if coverage.load(path).get('check') == proof['appended_check'])
        receipt = coverage.qualification(report_path.parent, check, old_plan, report['host'])
        if (type(receipt['schema_version']) is not int or not _same(receipt['details'].get('appended_kernel'), binding) or
                not set(policy_requirements['kernel_assertions']) <= set(receipt['assertions'])):
            raise ValueError('original appended contract receipt does not bind finalized descriptor and prefix')
        # Archive hash equality binds every original native library/notice/mode.
        # The deep candidate verifier separately checks that composition changes
        # only the selected runtime suffix and keeps this closure unchanged.
        return {'artifact': artifact_id, 'proof_sha256': proof_sha256, 'target': proof['target'],
                'backend': proof['backend'], 'release_sha256': coverage.sha(release_path),
                'source': copy.deepcopy(manifest['source']), 'dependencies': copy.deepcopy(selected_dependencies),
                'certificate_sha256': coverage.sha(coverage.local(root, proof['certificate'])),
                'plan_id': old_plan['id'], 'profile': proof['profile'], 'run_id': reproduced['run_id'],
                'kernel_binding': binding,
                'reports': [{'path': name, 'sha256': proof['files'][name],
                             'run_id': coverage.load(coverage.local(root, name))['run_id'],
                             'attempt': coverage.load(coverage.local(root, name))['attempt'],
                             'host': coverage.load(coverage.local(root, name)).get('host'),
                             'evidence': copy.deepcopy(coverage.load(coverage.local(root, name)).get('evidence', {}))}
                            for name in proof['reports']]}


def _plan_fields(plan):
    coverage.fields(plan, {'schema_version', 'kind', 'subject', 'policy', 'profile', 'kernel_proofs',
                           'tool_sources', 'coverage_plan', 'id'})
    _version(plan, PLAN_KIND)
    coverage.fields(plan['subject'], {'candidate_sha256', 'composition_sha256', 'selection_sha256', 'policy_sha256'})
    for value in plan['subject'].values():
        appended._sha(value)
    _name(plan['profile'])
    if plan['id'] != coverage.digest({k: v for k, v in plan.items() if k != 'id'}):
        raise ValueError('composition qualification plan digest differs')
    coverage.validate(plan['coverage_plan'])
    if type(plan['coverage_plan']['schema_version']) is not int:
        raise ValueError('execution plan schema version must be an integer')
    return plan


def _frozen_inputs(selected, kernel_proofs, evidence_root):
    inputs = {}

    def retain(ref):
        _reference(ref)
        if ref['path'] in inputs and inputs[ref['path']] != ref['sha256']:
            raise ValueError('conflicting frozen evidence input')
        inputs[ref['path']] = ref['sha256']
        if len(inputs) > 4096:
            raise ValueError('excessive frozen scenario input inventory')

    for ref in kernel_proofs.values():
        retain(ref)
    pending = [row['scenario'] for row in selected['checks'] if 'scenario' in row]
    seen, snapshots = set(), []
    while pending:
        ref = pending.pop()
        retain(ref)
        if ref['path'] in seen:
            continue
        seen.add(ref['path'])
        saved = container._snapshot(coverage.local(evidence_root, ref['path']), 4 * 1024 * 1024)
        if container.digest(saved.content) != ref['sha256']:
            raise ValueError('frozen scenario input changed from its independent hash')
        snapshots.append(saved)
        scenario = appended._json(saved.content)
        if type(scenario) is not dict:
            raise ValueError('frozen scenario must be an object')
        declared = scenario.get('inputs', {})
        if type(declared) is not dict or len(declared) > 4096:
            raise ValueError('invalid frozen scenario input inventory')
        parent = Path(ref['path']).parent
        for name, pin in declared.items():
            container.resource_path(name)
            retain({'path': (parent / name).as_posix(), 'sha256': pin})
        # A guest recovery may execute a separately pinned runtime/browser
        # scenario. Its declared instrument files must survive relocation too.
        if scenario.get('kind') == 'foundation-appended-guest-source-scenario':
            test = scenario.get('test')
            nested = test.get('scenario') if type(test) is dict else None
            if type(nested) is not str or nested not in declared:
                raise ValueError('guest test scenario is absent from declared inputs')
            pending.append({'path': (parent / nested).as_posix(), 'sha256': declared[nested]})
        elif scenario.get('kind') == 'foundation-appended-install-scenario':
            phases = scenario.get('phases')
            if type(phases) is not dict:
                raise ValueError('install phases must be a declared map')
            for name in ('clean', 'previous', 'upgraded'):
                phase = phases.get(name)
                if type(phase) is not dict:
                    continue  # Native phases retain their existing call lists.
                nested = phase.get('scenario')
                if type(nested) is not str or nested not in declared:
                    raise ValueError('install phase scenario is absent from declared inputs')
                pending.append({'path': (parent / nested).as_posix(), 'sha256': declared[nested]})
    for saved in snapshots:
        container._recheck(saved)
    return inputs


def _tool_catalog(selected):
    return tool_source_catalog(row['scope'] for row in selected['checks'])


def tool_source_catalog(scopes):
    """Return the immutable v1 catalog without importing execution helpers."""
    scopes = set(scopes)
    if not scopes or not scopes <= SCOPES:
        raise ValueError('unsupported composition source catalog scope')
    result = set(COMMON_TOOL_SOURCES_V1)
    for scope in scopes:
        result.update(SCOPE_TOOL_SOURCES_V1.get(scope, ()))
    return tuple(sorted(result))


def _validate_tool_sources(selected, tool_sources):
    if type(tool_sources) is not dict or set(tool_sources) != set(_tool_catalog(selected)):
        raise ValueError('frozen tool sources differ from the complete fixed source catalog')
    for name, ref in tool_sources.items():
        container.resource_path(name)
        _reference(ref)
        if ref['path'] != 'tool-inputs/' + ref['sha256']:
            raise ValueError('frozen tool sources require canonical content-addressed inputs')
    return tool_sources


def _current_tool_sources(tool_sources):
    """Check actual local helper bytes before execution and retain identities."""
    root = container._ordinary_path(TOOL_ROOT, directory=True)
    snapshots, total = {}, 0
    for name, ref in sorted(tool_sources.items()):
        saved = container._snapshot(coverage.local(root, name), MAX_TOOL_SOURCE)
        total += len(saved.content)
        if total > MAX_TOOL_SOURCES:
            raise ValueError('frozen tool source closure exceeds bounded offline limits')
        if container.digest(saved.content) != ref['sha256']:
            raise ValueError('current tool source differs from the before-run frozen pin: ' + name)
        snapshots[name] = saved
    for saved in snapshots.values():
        container._recheck(saved)
    return snapshots


def _retain_tool_sources(candidate, selected, evidence_root):
    root = container._ordinary_path(TOOL_ROOT, directory=True)
    snapshots, total = {}, 0
    for name in _tool_catalog(selected):
        saved = container._snapshot(coverage.local(root, name), MAX_TOOL_SOURCE)
        total += len(saved.content)
        if total > MAX_TOOL_SOURCES:
            raise ValueError('frozen tool source closure exceeds bounded offline limits')
        snapshots[name] = saved
    # Source retention is external, immutable and content addressed. A prior
    # blob may be reused only after checking its exact ordinary-file bytes.
    directory = _external(evidence_root / 'tool-inputs', candidate)
    directory.mkdir(mode=0o755, exist_ok=True)
    container._ordinary_path(directory, directory=True)
    result = {}
    for name, saved in sorted(snapshots.items()):
        pin = container.digest(saved.content)
        destination = directory / pin
        if destination.exists() or destination.is_symlink():
            if container._snapshot(destination, MAX_TOOL_SOURCE).content != saved.content:
                raise ValueError('existing frozen tool input differs from its content address')
        else:
            container._write_new(destination, saved.content, snapshots=(saved,))
        result[name] = {'path': 'tool-inputs/' + pin, 'sha256': pin}
    for saved in snapshots.values():
        container._recheck(saved)
    return _validate_tool_sources(selected, result)


def _plan_inputs(selected, kernel_proofs, tool_sources, evidence_root):
    inputs = _frozen_inputs(selected, kernel_proofs, evidence_root)
    for ref in _validate_tool_sources(selected, tool_sources).values():
        if ref['path'] in inputs and inputs[ref['path']] != ref['sha256']:
            raise ValueError('conflicting frozen tool source input')
        inputs[ref['path']] = ref['sha256']
    return dict(sorted(inputs.items()))


def _validate_plan(candidate, candidate_pin, plan, evidence_root):
    _plan_fields(plan)
    verified, selected = _subject(candidate, candidate_pin, plan['policy'], plan['profile'])
    subject = {k: verified[k] for k in ('candidate_sha256', 'composition_sha256', 'selection_sha256')}
    subject['policy_sha256'] = coverage.digest(plan['policy'])
    if plan['subject'] != subject:
        raise ValueError('composition plan names a different candidate, composition or policy')
    if type(plan['kernel_proofs']) is not dict or set(plan['kernel_proofs']) != set(selected['artifacts']):
        raise ValueError('exactly one independently pinned proof is required for every artifact')
    cp = plan['coverage_plan']
    expected_subject = {'source_sha256': verified['composition']['source']['sha256'],
                        'inventory_sha256': candidate_pin,
                        'configuration_sha256': coverage.digest({'subject': subject, 'profile': plan['profile']})}
    if (cp['mode'] != 'release' or cp['subject'] != expected_subject or
            cp['inputs'] != _plan_inputs(selected, plan['kernel_proofs'], plan['tool_sources'], evidence_root)):
        raise ValueError('frozen execution plan differs from complete composition subject')
    expected = {row['id']: row for row in selected['checks']}
    if {row['id'] for row in cp['checks']} != set(expected):
        raise ValueError('complete exact policy check set is required')
    for item in cp['checks']:
        row = expected[item['id']]
        if (any(item[k] != row[k] for k in ('scope', 'target', 'backend', 'environment')) or
                item['required'] is not True or 'qualification' not in item or 'junit' not in item or
                item['expected_tests'] != row['assertions'] or 'execution' in item or 'sdk_payload' in item):
            raise ValueError('execution check differs from required exact policy assertions')
    coverage.check_inputs(cp, evidence_root)
    proofs = {identity: verify_retained_kernel_proof(verified, identity, coverage.local(evidence_root, ref['path']),
                                                   ref['sha256'], selected)
              for identity, ref in plan['kernel_proofs'].items()}
    coverage.check_inputs(cp, evidence_root)
    if not _same(appended.verify_composition_subject(candidate, candidate_pin), verified):
        raise ValueError('composition subject changed during frozen proof validation')
    return verified, selected, proofs


def freeze_plan(candidate, candidate_pin, policy, profile, kernel_proofs, *, checks, evidence_root=None):
    """Freeze a portable plan only after independently checking every old proof."""
    candidate = container._ordinary_path(candidate, directory=True)
    root = _root(candidate, evidence_root)
    verified, selected = _subject(candidate, candidate_pin, policy, profile)
    subject = {k: verified[k] for k in ('candidate_sha256', 'composition_sha256', 'selection_sha256')}
    subject['policy_sha256'] = coverage.digest(policy)
    tool_sources = _retain_tool_sources(candidate, selected, root)
    plan = {'schema_version': 1, 'kind': PLAN_KIND, 'subject': subject,
            'policy': copy.deepcopy(policy), 'profile': profile, 'kernel_proofs': copy.deepcopy(kernel_proofs),
            'tool_sources': tool_sources,
            'coverage_plan': coverage.freeze({'schema_version': 1, 'mode': 'release',
                'subject': {'source_sha256': verified['composition']['source']['sha256'],
                            'inventory_sha256': candidate_pin,
                            'configuration_sha256': coverage.digest({'subject': subject, 'profile': profile})},
                'inputs': _plan_inputs(selected, kernel_proofs, tool_sources, root), 'checks': copy.deepcopy(checks)})}
    plan['id'] = coverage.digest(plan)
    _validate_plan(candidate, candidate_pin, plan, root)
    _current_tool_sources(tool_sources)
    return plan


def completion_record(plan, report, receipt):
    """Build the cycle-free wrapper guard binding, without writing evidence.

    The wrapper and qualification-file hashes are excluded from the report's
    evidence projection. The receipt's self-edge to this wrapper is excluded as
    well. All result/receipt fields and every original evidence hash remain
    bound, so adding the wrapper creates no self-hash cycle.
    """
    choices = [row for row in plan['coverage_plan']['checks'] if row['id'] == report['check']]
    if len(choices) != 1:
        raise ValueError('completion requires one known frozen check')
    qualification = choices[0]['qualification']
    return {'schema_version': 1, 'kind': 'foundation-appended-check-completion',
            'plan_id': plan['id'], 'coverage_plan_id': plan['coverage_plan']['id'],
            'subject': copy.deepcopy(plan['subject']), 'check': report['check'],
            'run_id': report['run_id'], 'attempt': report['attempt'],
            'checker_sources': {name: ref['sha256'] for name, ref in plan['tool_sources'].items()},
            'report_core_sha256': coverage.digest({k: v for k, v in report.items()
                                                   if k not in ('evidence', 'completion')}),
            'receipt_core_sha256': coverage.digest({k: v for k, v in receipt.items() if k != 'evidence'}),
            'report_evidence': {k: v for k, v in report['evidence'].items()
                                if k not in (COMPLETION_FILE, qualification)},
            'receipt_evidence': {k: v for k, v in receipt['evidence'].items() if k != COMPLETION_FILE}}


def _verify_completion(plan, report, receipt, root):
    reference = report['completion']
    if (reference['path'] != COMPLETION_FILE or
            report['evidence'].get(COMPLETION_FILE) != reference['sha256'] or
            receipt['evidence'].get(COMPLETION_FILE) != reference['sha256']):
        raise ValueError('fresh result lacks a bound wrapper completion artifact')
    path = coverage.local(root, COMPLETION_FILE)
    if (coverage.sha(path) != reference['sha256'] or
            not _same(coverage.load(path), completion_record(plan, report, receipt))):
        raise ValueError('wrapper completion differs from the exact frozen result and receipt')


def certify(candidate, candidate_pin, plan, reports, *, evidence_root=None):
    """Aggregate a complete fresh run, with original kernel references kept apart."""
    candidate = container._ordinary_path(candidate, directory=True)
    root = _root(candidate, evidence_root)
    verified, selected, proofs = _validate_plan(candidate, candidate_pin, plan, root)
    paths = [container._ordinary_path(path) for path in reports]
    references = []
    for path in paths:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError('fresh reports must be retained under the explicit evidence root') from error
        container.resource_path(relative)
        report = _fresh_report(coverage.load(path))
        references.append({'check': report['check'], 'path': relative, 'sha256': coverage.sha(path)})
    merged = coverage.merge(plan['coverage_plan'], paths)
    if merged['status'] != 'passed' or merged['omitted']:
        raise ValueError('unexecuted, failed, skipped or missing composition checks cannot certify')
    by_id = {coverage.load(path)['check']: path for path in paths}
    for row in selected['checks']:
        report = merged['checks'][row['id']]
        if (type(report['schema_version']) is not int or type(report['run_id']) is not str or
                not coverage.NAME.fullmatch(report['run_id'])):
            raise ValueError('invalid original fresh run identity')
        coverage.check_host(plan['coverage_plan'], row['id'], report, by_id[row['id']].parent)
        check = next(x for x in plan['coverage_plan']['checks'] if x['id'] == row['id'])
        receipt = coverage.qualification(by_id[row['id']].parent, check, plan['coverage_plan'], report['host'])
        _verify_completion(plan, report, receipt, by_id[row['id']].parent)
        details = receipt['details']
        bindings = {**{k: verified[k] for k in ('candidate_sha256', 'composition_sha256', 'selection_sha256')},
                    'qualification_policy_sha256': plan['subject']['policy_sha256'], 'profile': plan['profile'],
                    'plan': plan['coverage_plan']['id'], 'composition_check_id': row['id'],
                    'run_id': report['run_id'], 'attempt': report['attempt']}
        if (type(receipt['schema_version']) is not int or receipt['assertions'] != row['assertions'] or
                any(not _same(details.get(k), value) for k, value in bindings.items())):
            raise ValueError('fresh receipt has stale composition, plan, policy or executed assertions')
        source_pins = {name: ref['sha256'] for name, ref in plan['tool_sources'].items()}
        if (not _same(details.get('checker_sources'), source_pins) or any(
                receipt['evidence'].get('checker-sources/' + name) != pin for name, pin in source_pins.items())):
            raise ValueError('fresh receipt lacks exact before-run frozen checker source evidence')
        if 'scenario' in row and details.get('scenario_sha256') != row['scenario']['sha256']:
            raise ValueError('fresh receipt does not bind the pinned scenario')
        if row['artifact'] is not None and details.get('artifact_id') != row['artifact']:
            raise ValueError('fresh receipt names another delivered artifact')
        if row['scope'] == 'guest-source':
            if not details.get('executed_tests') or 'guest.junit.xml' not in receipt['evidence']:
                raise ValueError('guest recovery requires retained nonempty actual test outcomes')
            _names(details['executed_tests'], 'guest test inventory')
            coverage.junit(coverage.local(by_id[row['id']].parent, 'guest.junit.xml'), details['executed_tests'])
            tools = details.get('tool_reports', [])
            if type(tools) is not list or len(tools) != len(set(tools)):
                raise ValueError('guest recovery needs a complete tool outcome inventory')
            for name in tools:
                if name not in receipt['evidence']:
                    raise ValueError('guest tool outcomes absent from retained evidence')
                coverage.tool_report(coverage.load(coverage.local(by_id[row['id']].parent, name)))
        if row['scope'] == 'install-upgrade':
            if (not receipt['evidence'] or
                    details.get('channels') != selected['artifacts'][row['artifact']]['channels']):
                raise ValueError('installation/upgrade qualification needs actual channel evidence')
    # Re-read all selected bytes after parsing retained evidence, including the
    # complete candidate. A certificate never changes or completes candidate.json.
    if not _same(appended.verify_composition_subject(candidate, candidate_pin), verified):
        raise ValueError('composition subject changed during certification')
    coverage.check_inputs(plan['coverage_plan'], root)
    if not _same(coverage.merge(plan['coverage_plan'], paths), merged):
        raise ValueError('fresh results or retained evidence changed during certification')
    if any(coverage.sha(coverage.local(root, ref['path'])) != ref['sha256'] for ref in references):
        raise ValueError('fresh report changed during certification')
    return {'schema_version': 1, 'kind': CERTIFICATE_KIND, 'subject': copy.deepcopy(plan['subject']),
            'plan_id': plan['id'], 'profile': plan['profile'], 'description': selected['description'],
            'status': 'passed', 'eligible_for_publication': True, 'eligible_for_promotion': True,
            'experiment': False, 'run_id': merged['run_id'],
            'attempt': next(iter(merged['checks'].values()))['attempt'],
            'kernel_evidence': proofs, 'coverage': merged,
            'reports': sorted(references, key=lambda row: row['check']),
            'limits': ['Applies only to exact selected bytes and the named actual environments.',
                       'Original kernel evidence retains its original source, run, attempt and host identities.',
                       'Recomposition is not kernel reconstruction; no native build is performed by this verifier.',
                       'Hashes establish byte identities; callers authenticate evidence producers separately.']}


def verify_certificate(candidate, candidate_pin, plan, reports, certificate, *, evidence_root=None):
    expected = certify(candidate, candidate_pin, plan, reports, evidence_root=evidence_root)
    if not _same(certificate, expected):
        raise ValueError('composition certificate differs from fully reproduced evidence')
    return expected


def _run_command(candidate, pin, plan, selected, check_id, evidence_root):
    choices = [item for item in plan['coverage_plan']['checks'] if item['id'] == check_id]
    if len(choices) != 1:
        raise ValueError('one known frozen check is required for execution')
    check = choices[0]
    row = next(item for item in selected['checks'] if item['id'] == check_id)
    root = container._ordinary_path(TOOL_ROOT, directory=True)
    prefix = ['{python}', '-I', '-S', str(root / 'tools/appended_release_check.py'), row['scope']]
    argv = check['argv']
    if argv[:len(prefix)] != prefix or (len(argv) - len(prefix)) % 2:
        raise ValueError('execution requires the exact isolated trusted built-in checker entrypoint')
    substitutions = ('{python}', '{root}', '{evidence}', '{plan_id}', '{run_id}', '{attempt}')
    for index, value in enumerate(argv[1:], 1):
        if value == '{evidence}' and argv[index - 1] == '--evidence':
            continue
        if any(token in value for token in substitutions):
            raise ValueError('actual checker arguments cannot contain reserved supervision substitutions')
    flags = {}
    allowed = {'--release', '--candidate-sha256', '--target', '--backend', '--artifact',
               '--scenario', '--scenario-sha256', '--evidence', '--junit', '--timeout'}
    for index in range(len(prefix), len(argv), 2):
        name, value = argv[index:index + 2]
        if name not in allowed or name in flags:
            raise ValueError('unknown or duplicate frozen checker argument')
        flags[name] = value
    expected = {'--release': str(candidate), '--candidate-sha256': pin,
                '--target': row['target'], '--backend': row['backend'],
                '--evidence': '{evidence}', '--junit': check['junit']}
    if check['qualification'] != 'qualification.json':
        raise ValueError('built-in execution requires its fixed qualification receipt path')
    if row['artifact'] is not None:
        expected['--artifact'] = row['artifact']
    if 'scenario' in row:
        expected['--scenario'] = str(coverage.local(evidence_root, row['scenario']['path']))
        expected['--scenario-sha256'] = row['scenario']['sha256']
    if '--timeout' in flags:
        try:
            timeout = float(flags.pop('--timeout'))
        except (ValueError, OverflowError) as error:
            raise ValueError('invalid frozen checker timeout') from error
        if not math.isfinite(timeout) or not 0 < timeout <= min(check['timeout_seconds'], 300):
            raise ValueError('checker timeout exceeds its frozen supervision allowance')
    if flags != expected:
        raise ValueError('checker arguments differ from the exact candidate, artifact, scenario or evidence bindings')
    return check


def _complete_attempt(raw, output, plan, check, report):
    """Finalize only private owned copies after all wrapper guards succeeded."""
    if report['status'] != 'passed':
        return raw, report
    receipt = coverage.load(coverage.local(raw, check['qualification']))
    record = completion_record(plan, report, receipt)
    output.mkdir()
    excluded = {'result.json', check['qualification'], COMPLETION_FILE}
    for path in sorted(raw.rglob('*')):
        relative = path.relative_to(raw).as_posix()
        if relative in excluded:
            continue
        target = output / relative
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('private supervised evidence contains a link or special entry')
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, target, follow_symlinks=False)
    coverage.write_new(output / COMPLETION_FILE, record)
    reference = {'path': COMPLETION_FILE, 'sha256': coverage.sha(output / COMPLETION_FILE)}
    receipt = copy.deepcopy(receipt)
    receipt['evidence'][COMPLETION_FILE] = reference['sha256']
    receipt_path = coverage.local(output, check['qualification'])
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    coverage.write_new(receipt_path, receipt)
    result = copy.deepcopy(report)
    result['completion'] = reference
    result['evidence'][COMPLETION_FILE] = reference['sha256']
    result['evidence'][check['qualification']] = coverage.sha(receipt_path)
    _fresh_report(result)
    coverage.qualification(output, check, plan['coverage_plan'], report['host'])
    _verify_completion(plan, result, receipt, output)
    coverage.write_new(output / 'result.json', result)
    return output, result


def _publish_attempt(staged, output):
    """Publish exclusive evidence, exposing result.json only after every file."""
    container._ordinary_path(output.parent, directory=True)
    files = appended._files(staged)
    if 'result.json' not in files:
        raise ValueError('private attempt lacks its complete supervised result')
    names = {path.relative_to(staged).as_posix() for path in staged.rglob('*') if path.is_dir()}
    output.mkdir()
    directories = {output: output.lstat()}

    def check_directories():
        for path, before in directories.items():
            container._ordinary_path(path, directory=True)
            current = path.lstat()
            if not stat.S_ISDIR(current.st_mode) or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError('reserved attempt directory identity changed')

    try:
        for name in sorted(names):
            check_directories()
            target = output / name
            target.mkdir()
            directories[target] = target.lstat()
        for name in sorted(set(files) - {'result.json'}):
            check_directories()
            os.link(staged / name, output / name, follow_symlinks=False)
        check_directories()
        if (appended._files(staged) != files or
                appended._files(output) != {name: value for name, value in files.items() if name != 'result.json'} or
                {path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_dir()} != names):
            raise ValueError('reserved attempt evidence changed before result publication')
        os.link(staged / 'result.json', output / 'result.json', follow_symlinks=False)
    except BaseException as error:
        raise ValueError('attempt publication incomplete; preserve and inspect reserved output: ' + str(output)) from error
    return output


def run_check(candidate, candidate_pin, plan, check_id, output, run_id, attempt, *, evidence_root=None):
    """Supervise one explicitly selected fresh check with composition bindings.

    The frozen argv defines the requested check. This function adds no builder
    and never substitutes a legacy source/recovery operation. The short-lived
    CLI is the preferred interface for parallel execution, giving each process
    its own environment and evidence directory.
    """
    candidate = container._ordinary_path(candidate, directory=True)
    root = _root(candidate, evidence_root)
    _, selected, _ = _validate_plan(candidate, candidate_pin, plan, root)
    check = _run_command(candidate, candidate_pin, plan, selected, check_id, root)
    tool_snapshots = _current_tool_sources(plan['tool_sources'])
    output = _external(output, candidate)
    if output.exists() or output.is_symlink():
        raise ValueError('supervised attempt output must be new')
    # coverage owns supervised child creation, process-tree joining, JUnit,
    # authoritative qualification receipts, elapsed limits and immutable results.
    # Its legacy API obtains child variables from the process environment. Lock
    # our uses and always restore them, including exception paths.
    additions = {'FOUNDATION_COMPOSITION_POLICY_SHA256': plan['subject']['policy_sha256'],
                 'FOUNDATION_COMPOSITION_PROFILE': plan['profile'],
                 'FOUNDATION_COMPOSITION_TOOL_SOURCES': container.canonical_json(
                     {name: ref['sha256'] for name, ref in plan['tool_sources'].items()}).decode('utf-8')}
    workspace = Path(tempfile.mkdtemp(prefix='.appended-check-', dir=output.parent))
    workspace_state = workspace.lstat()
    pending = False
    try:
        raw = workspace / 'raw'
        with _RUN_ENVIRONMENT:
            previous = {key: os.environ.get(key) for key in additions}
            try:
                os.environ.update(additions)
                pending = True
                result = coverage.run_case(plan['coverage_plan'], check_id, root, raw, run_id, attempt)
                pending = 'writer cleanup uncertain' in str(result.get('error', '')).lower()
                if pending:
                    raise ValueError('supervised writer cleanup is uncertain')
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
        for saved in tool_snapshots.values():
            container._recheck(saved)
        _validate_plan(candidate, candidate_pin, plan, root)
        for saved in tool_snapshots.values():
            container._recheck(saved)
        _fresh_report(result, completed=False)
        if not _same(coverage.load(raw / 'result.json'), result):
            raise ValueError('supervised result differs from its immutable private receipt')
        completed, result = _complete_attempt(raw, workspace / 'complete', plan, check, result)
        _publish_attempt(completed, output)
        return result
    except BaseException as error:
        if pending:
            message = 'Private evidence retained because supervised writers may remain active: ' + str(workspace)
            if hasattr(error, 'add_note'):
                error.add_note(message)
            else:
                print(message, file=sys.stderr)
        raise
    finally:
        if not pending:
            try:
                container._ordinary_path(workspace, directory=True)
                current = workspace.lstat()
                if (current.st_dev, current.st_ino) != (workspace_state.st_dev, workspace_state.st_ino):
                    raise ValueError('private attempt directory identity changed')
            except (OSError, ValueError):
                print('Private attempt namespace changed; preserve and inspect: ' + str(workspace), file=sys.stderr)
            else:
                shutil.rmtree(workspace)


def _external(path, candidate):
    output = Path(path).absolute()
    subject = Path(candidate).resolve(strict=True)
    if output == subject or subject in output.resolve(strict=False).parents:
        raise ValueError('qualification outputs must remain outside the immutable candidate')
    container._ordinary_path(output.parent, directory=True)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('freeze', 'run', 'certify', 'verify-certificate'):
        command = sub.add_parser(name)
        command.add_argument('--release', type=Path, required=True)
        command.add_argument('--candidate-sha256', required=True)
        command.add_argument('--evidence-root', type=Path)
        if name == 'freeze':
            command.add_argument('--policy', type=Path, required=True)
            command.add_argument('--profile', required=True)
            command.add_argument('--kernel-proofs', type=Path, required=True)
            command.add_argument('--checks', type=Path, required=True)
        elif name == 'run':
            command.add_argument('--plan', type=Path, required=True)
            command.add_argument('--check', required=True)
            command.add_argument('--run-id', required=True)
            command.add_argument('--attempt', type=int, required=True)
        else:
            command.add_argument('--plan', type=Path, required=True)
            command.add_argument('reports', type=Path, nargs='+')
        if name == 'verify-certificate':
            command.add_argument('--certificate', type=Path, required=True)
        else:
            command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == 'freeze':
        result = freeze_plan(args.release, args.candidate_sha256, coverage.load(args.policy), args.profile,
                             coverage.load(args.kernel_proofs), checks=coverage.load(args.checks), evidence_root=args.evidence_root)
    elif args.action == 'run':
        result = run_check(args.release, args.candidate_sha256, coverage.load(args.plan), args.check,
                           args.output, args.run_id, args.attempt, evidence_root=args.evidence_root)
    elif args.action == 'certify':
        result = certify(args.release, args.candidate_sha256, coverage.load(args.plan), args.reports,
                         evidence_root=args.evidence_root)
    else:
        result = verify_certificate(args.release, args.candidate_sha256, coverage.load(args.plan), args.reports,
                                    coverage.load(args.certificate), evidence_root=args.evidence_root)
    if args.action not in ('verify-certificate', 'run'):
        coverage.write_new(_external(args.output, args.release), result)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0 if args.action != 'run' or result['status'] == 'passed' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError) as error:
        raise SystemExit('appended qualification: ' + str(error))
