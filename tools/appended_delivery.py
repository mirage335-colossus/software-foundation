#!/usr/bin/env python3
"""Plan-first downstream delivery of immutable appended compositions.

This adapter consumes retained subjects and external qualification attempts. It
never acquires a kernel, compiles an application, or invokes legacy candidate
or certification validators. The caller serializes protected remote publication.
Acquisition authenticates retained evidence producers; digest checks here preserve
their selected bytes and original identities without establishing that trust.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
TOOLS = str(Path(__file__).resolve().parent)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import appended_container as container
import appended_release as composition
import dependency_archive as archive
import github_release as github

DeliveryError = github.DeliveryError
DESCRIPTOR = 'appended-delivery.json'
KIND = 'foundation-appended-delivery'
CERT = re.compile(r'appended-certification-([A-Za-z0-9][A-Za-z0-9_.-]*)-attempt-([1-9][0-9]*)\.(json|tar.gz)\Z')
MAX_BUNDLE = 4 * 1024 ** 3


def _load(path):
    # Coverage receipts legitimately contain fractional timing observations;
    # the payload container's integer-only JSON grammar does not apply here.
    value = github.parse(container._snapshot(path, composition.MAX_JSON).content)
    json.dumps(value, allow_nan=False)
    return value


def _same(left, right):
    # Ordinary dict equality aliases JSON booleans with integer 0/1. Frozen
    # delivery and qualification records preserve JSON types as well as values.
    return archive.encoded(left) == archive.encoded(right)


def _qualifier():
    # Import only for qualification operations; candidate publication has no
    # dependency on an available certifier or any of its optional prerequisites.
    import appended_qualification
    return appended_qualification


def _asset(name):
    """Preserve every original path through a collision-checked flat mapping."""
    archive.relative(name)
    basename = Path(name).name
    # Input blobs and retained helpers may have identical basenames. Their
    # original relative paths remain authoritative in the delivery descriptor.
    return github.valid_name('subject-' + github.sha(name.encode())[:24] + '-' + basename)


def delivery_identity(directory, candidate_pin, repository, tag, application_source_commit,
                      packager_commit, publication_id, experiment=False):
    github.location(repository, tag)
    if (tag == 'base' or not isinstance(application_source_commit, str)
            or not github.OID.fullmatch(application_source_commit)
            or not isinstance(packager_commit, str) or not github.OID.fullmatch(packager_commit)
            or type(experiment) is not bool):
        raise DeliveryError('composition needs a distinct downstream tag and exact source/packager commits')
    github.valid_name(publication_id)
    directory = Path(directory)
    verified = composition.verify_composition_subject(directory, candidate_pin)
    mapping, names = {}, {DESCRIPTOR.casefold()}
    expected = dict(verified['candidate']['files'])
    expected['candidate.json'] = {'sha256': verified['candidate_sha256'],
                                  'size': (directory / 'candidate.json').stat().st_size}
    for name, identity in sorted(expected.items()):
        path = archive.checked_file(directory, name)
        asset = _asset(name)
        if asset.casefold() in names or CERT.fullmatch(asset):
            raise DeliveryError('composition asset names collide')
        names.add(asset.casefold())
        if archive.digest(path) != identity['sha256'] or path.stat().st_size != identity['size']:
            raise DeliveryError('composition changed while freezing downstream delivery')
        mapping[name] = {'asset': asset, **identity}
    kernels = []
    for kernel in verified['selection']['kernels']:
        descriptor = _load(archive.checked_file(directory, kernel['descriptor']['path']))
        kernels.append({key: copy.deepcopy(kernel[key]) for key in
                        ('id', 'descriptor', 'original_source', 'recovery', 'evidence')})
        kernels[-1]['provenance'] = copy.deepcopy(descriptor['provenance'])
    if composition.verify_composition_subject(directory, candidate_pin) != verified:
        raise DeliveryError('composition changed while freezing downstream delivery')
    return {'schema_version': 1, 'kind': KIND, 'repository': repository, 'tag': tag,
            'application_source_commit': application_source_commit, 'packager_commit': packager_commit,
            'tag_commit': packager_commit, 'publication_id': publication_id, 'experiment': experiment,
            'candidate_sha256': verified['candidate_sha256'],
            'composition_sha256': verified['composition_sha256'],
            'selection_sha256': verified['selection_sha256'],
            'application': copy.deepcopy(verified['composition']['application']),
            'application_source': copy.deepcopy(verified['composition']['source']),
            'kernels': kernels, 'files': mapping}


def validate_delivery(delivery, directory):
    if type(delivery) is not dict:
        raise DeliveryError('typed composition delivery identity is required')
    keys = ('repository', 'tag', 'application_source_commit', 'packager_commit', 'publication_id', 'experiment')
    try:
        expected = delivery_identity(directory, delivery['candidate_sha256'],
                                     **{key: delivery[key] for key in keys})
    except (KeyError, TypeError) as error:
        raise DeliveryError('incomplete composition delivery identity') from error
    if not _same(expected, delivery):
        raise DeliveryError('delivery differs from the complete typed composition subject')
    return github.sha(archive.encoded(delivery))


def _attempts(names):
    groups = {}
    for name in names:
        match = CERT.fullmatch(name)
        if match is None:
            raise DeliveryError('unexpected asset outside composition delivery and certificate attempts')
        groups.setdefault((match[1], match[2]), set()).add(match[3])
    if any(parts != {'json', 'tar.gz'} for parts in groups.values()):
        raise DeliveryError('partial composition certificate attempt requires reconciliation')


def _inventory(delivery, info, assets, *, draft=False, prerelease=None):
    github.Remote.info(info, delivery['tag'])
    if (info['draft'] != draft or info['name'] != ('experiment' if delivery['experiment'] else delivery['tag'])
            or delivery['experiment'] and not info['prerelease']
            or prerelease is not None and info['prerelease'] != prerelease):
        raise DeliveryError('composition release lifecycle differs from frozen delivery')
    expected = {value['asset'] for value in delivery['files'].values()} | {DESCRIPTOR}
    if not expected <= assets.keys():
        raise DeliveryError('composition delivery is missing required assets')
    extras = set(assets) - expected
    if draft and extras:
        raise DeliveryError('unexpected composition draft assets')
    _attempts(extras)
    for item in delivery['files'].values():
        row = assets[item['asset']]
        if row['digest'] != 'sha256:' + item['sha256'] or row['size'] != item['size']:
            raise DeliveryError('remote composition asset differs from frozen subject')
    raw = archive.encoded(delivery)
    if assets[DESCRIPTOR]['digest'] != 'sha256:' + github.sha(raw) or assets[DESCRIPTOR]['size'] != len(raw):
        raise DeliveryError('remote composition delivery descriptor differs')


def verified_remote(remote, delivery, directory, *, draft=False, prerelease=None, readback=True):
    validate_delivery(delivery, directory)
    info = remote.find(delivery['tag']) if draft else remote.published(delivery['tag'])
    assets = remote.assets(info)
    _inventory(delivery, info, assets, draft=draft, prerelease=prerelease)
    if remote.reference(delivery['tag']) != delivery['tag_commit']:
        raise DeliveryError('downstream tag differs from frozen packager commit')
    with tempfile.TemporaryDirectory(prefix='appended-delivery-verify-') as temporary:
        root = Path(temporary)
        descriptor = root / DESCRIPTOR
        remote.download(assets[DESCRIPTOR], descriptor, github.sha(archive.encoded(delivery)))
        if descriptor.read_bytes() != archive.encoded(delivery):
            raise DeliveryError('remote composition descriptor has different exact bytes')
        if readback:
            restored = root / 'subject'; restored.mkdir()
            selections = []
            for name, item in delivery['files'].items():
                path = restored.joinpath(*archive.relative(name).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                selections.append((item['asset'], path, item['sha256']))
            github.download_files(remote, assets, selections)
            validate_delivery(delivery, restored)
    remote.unchanged(delivery['tag'], info, assets, delivery['tag_commit'])
    return info, assets


def _retain(source, destination, digest=None):
    """Copy an ordinary input without following a changed or linked pathname."""
    saved = container._snapshot(source, MAX_BUNDLE)
    if digest is not None and container.digest(saved.content) != digest:
        raise DeliveryError('retained input differs from frozen expected bytes')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(saved.content)
    container._recheck(saved)


def publish_candidate(repository, tag, directory, candidate_pin, application_source_commit, packager_commit,
                      publication_id, experiment=False, *, execute=False, transport=None):
    delivery = delivery_identity(directory, candidate_pin, repository, tag, application_source_commit,
                                 packager_commit, publication_id, experiment)
    result = github.plan('publish-appended-candidate', repository, delivery=delivery,
                         lifecycle='draft upload; exact readback; publish prerelease with make_latest=false')
    if not execute:
        return result
    with tempfile.TemporaryDirectory(prefix='appended-delivery-stage-') as temporary:
        root = Path(temporary)
        for name, item in delivery['files'].items():
            _retain(archive.checked_file(directory, name), root / item['asset'], item['sha256'])
        (root / DESCRIPTOR).write_bytes(archive.encoded(delivery))
        validate_delivery(delivery, directory)
        remote = github.Remote(repository, transport)
        def act():
            remote.visible()
            if remote.find(tag, False) is not None or remote.reference(tag, True) is not None:
                raise DeliveryError('downstream release or tag already exists; never overwrite or implicitly resume')
            remote.change('/git/refs', body={'ref': 'refs/tags/' + tag, 'sha': delivery['tag_commit']})
            info = remote.info(remote.change('/releases', body={'tag_name': tag,
                'target_commitish': delivery['tag_commit'], 'name': 'experiment' if experiment else tag,
                'body': 'Composition certification pending. Immutable retained-kernel subject.',
                'draft': True, 'prerelease': True, 'make_latest': 'false'}), tag)
            remote.wait_find(tag, release_id=info['id'])
            github.upload_files(remote, tag, [root / item['asset'] for item in delivery['files'].values()], release_info=info)
            remote.upload_to(info, root / DESCRIPTOR)
            current, assets = verified_remote(remote, delivery, directory, draft=True, prerelease=True)
            if current['id'] != info['id']:
                raise DeliveryError('composition draft identity changed')
            remote.change(f'/releases/{info["id"]}', method='PATCH',
                          body={'draft': False, 'prerelease': True, 'make_latest': 'false'})
            final, after = verified_remote(remote, delivery, directory, prerelease=True, readback=False)
            if final['id'] != info['id'] or after != assets:
                raise DeliveryError('composition publication changed immutable assets')
            remote.not_latest(final)
            return dict(result, execute=True, release_id=final['id'])
        return github.run_mutation(remote, act)


def _policy(plan, policy):
    rules = _load(policy)
    if (not _same(plan.get('policy'), rules)
            or plan.get('subject', {}).get('policy_sha256') != github.coverage.digest(rules)):
        raise DeliveryError('current composition policy differs from frozen qualification policy')
    return rules


def _certificate_identity(document, delivery, run_id, attempt, *, eligible=False):
    if (not isinstance(run_id, str) or not github.coverage.NAME.fullmatch(run_id)
            or not github.positive(attempt) or type(document.get('attempt')) is not int
            or document.get('run_id') != run_id
            or document.get('attempt') != attempt):
        raise DeliveryError('composition certificate needs its original exact run and attempt')
    subject = document.get('subject', {})
    if any(subject.get(key) != delivery[key] for key in
           ('candidate_sha256', 'composition_sha256', 'selection_sha256')):
        raise DeliveryError('composition certificate names another immutable subject')
    if eligible and (document.get('status') != 'passed'
                     or document.get('eligible_for_publication') is not True
                     or document.get('eligible_for_promotion') is not True
                     or document.get('experiment') is not False or delivery['experiment']):
        raise DeliveryError('certificate does not qualify an ordinary composition release')


def _report_paths(reports, evidence_root):
    evidence_root = container._ordinary_path(evidence_root, directory=True).resolve(strict=True)
    result = []
    for path in reports:
        path = Path(path).absolute()
        try:
            name = path.relative_to(evidence_root).as_posix()
        except ValueError as error:
            raise DeliveryError('qualification report must be inside its explicit evidence root') from error
        archive.checked_file(evidence_root, name)
        if name in result:
            raise DeliveryError('duplicate qualification report path')
        result.append(name)
    if not result:
        raise DeliveryError('complete fresh composition reports are required')
    return evidence_root, result


def _reproduce(directory, delivery, tree, policy, profile, run_id, attempt, *, eligible=False):
    metadata = _load(tree / 'bundle.json')
    composition._keys(metadata, ('schema_version', 'kind', 'delivery_sha256', 'run_id', 'attempt',
                                'profile', 'reports', 'files'), label='composition evidence bundle')
    if (type(metadata['schema_version']) is not int or metadata['schema_version'] != 1
            or metadata['kind'] != 'foundation-appended-certificate-bundle'
            or metadata['delivery_sha256'] != github.sha(archive.encoded(delivery))
            or metadata['run_id'] != run_id or type(metadata['attempt']) is not int or metadata['attempt'] != attempt
            or metadata['profile'] != profile):
        raise DeliveryError('composition evidence bundle identity differs')
    archive.verify_inventory(tree, metadata['files'], exclude=('bundle.json',))
    document = _load(tree / 'certificate.json')
    frozen = _load(tree / 'plan.json')
    rules = _policy(frozen, policy)
    if not _same(_load(tree / 'policy.json'), rules) or frozen.get('profile') != profile:
        raise DeliveryError('retained composition policy or profile differs')
    _certificate_identity(document, delivery, run_id, attempt, eligible=eligible)
    evidence_root = tree / 'evidence'
    if type(metadata['reports']) is not list or len(set(metadata['reports'])) != len(metadata['reports']):
        raise DeliveryError('complete original composition report order is required')
    reports = [archive.checked_file(evidence_root, name) for name in metadata['reports']]
    reproduced = _qualifier().verify_certificate(directory, delivery['candidate_sha256'], frozen, reports,
                                                document, evidence_root=evidence_root)
    if not _same(reproduced, document):
        raise DeliveryError('composition certificate JSON types differ from reproduced evidence')
    return document


def bundle_certificate(directory, delivery, certificate, check_plan, policy, profile, reports, attempt,
                       destination, *, evidence_root):
    """Retain original proofs and every fresh receipt outside the frozen subject."""
    delivery_hash = validate_delivery(delivery, directory)
    certificate, check_plan, policy = Path(certificate), Path(check_plan), Path(policy)
    document, frozen = _load(certificate), _load(check_plan)
    _policy(frozen, policy)
    if frozen.get('profile') != profile:
        raise DeliveryError('composition qualification profile differs')
    run_id = document.get('run_id')
    _certificate_identity(document, delivery, run_id, attempt)
    evidence_root, report_names = _report_paths(reports, evidence_root)
    report_paths = [archive.checked_file(evidence_root, name) for name in report_names]
    reproduced = _qualifier().verify_certificate(directory, delivery['candidate_sha256'], frozen, report_paths,
                                                document, evidence_root=evidence_root)
    if not _same(reproduced, document):
        raise DeliveryError('composition certificate JSON types differ from reproduced evidence')
    destination = container._ordinary_path(destination, directory=True)
    candidate_root = container._ordinary_path(directory, directory=True)
    if destination == candidate_root or candidate_root in destination.parents:
        raise DeliveryError('certificate outputs must be outside the immutable composition subject')
    stem = github.valid_name(f'appended-certification-{run_id}-attempt-{attempt}')
    for suffix in ('.json', '.tar.gz'):
        path = destination / (stem + suffix)
        if path.exists() or path.is_symlink():
            raise FileExistsError('composition certificate output already exists: ' + str(path))
    tree = destination / 'contents'; tree.mkdir()
    retained = {}
    def retain(source, name, digest=None):
        target = tree.joinpath(*archive.relative(name).parts)
        digest = digest or archive.digest(source)
        if name in retained:
            if retained[name] != digest or archive.digest(target) != digest:
                raise DeliveryError('shared composition evidence changed during retention')
            return
        _retain(source, target, digest)
        retained[name] = digest
    for source, name in ((certificate, 'certificate.json'), (check_plan, 'plan.json'), (policy, 'policy.json')):
        retain(source, name)
    if type(frozen.get('kernel_proofs')) is not dict or not frozen['kernel_proofs']:
        raise DeliveryError('original complete kernel proof bundles are required')
    for proof in frozen['kernel_proofs'].values():
        composition._keys(proof, ('path', 'sha256'), label='retained kernel proof')
        retain(archive.checked_file(evidence_root, proof['path']), 'evidence/' + proof['path'], proof['sha256'])
    # Scenario documents are frozen inputs too. They need not appear in an
    # executed report's evidence map, but the verifier still requires them.
    for name, digest in frozen['coverage_plan']['inputs'].items():
        retain(archive.checked_file(evidence_root, name), 'evidence/' + name, digest)
    for name in report_names:
        path = archive.checked_file(evidence_root, name)
        retain(path, 'evidence/' + name)
        report = _load(path)
        if type(report.get('evidence')) is not dict:
            raise DeliveryError('fresh report needs its complete retained evidence map')
        for relative, digest in report['evidence'].items():
            source = archive.checked_file(path.parent, relative)
            retained_name = source.relative_to(evidence_root).as_posix()
            retain(source, 'evidence/' + retained_name, digest)
    metadata = {'schema_version': 1, 'kind': 'foundation-appended-certificate-bundle',
                'delivery_sha256': delivery_hash, 'run_id': run_id, 'attempt': attempt,
                'profile': profile, 'reports': report_names, 'files': archive.file_inventory(tree)}
    (tree / 'bundle.json').write_bytes(archive.encoded(metadata))
    copied = _reproduce(directory, delivery, tree, policy, profile, run_id, attempt)
    if not _same(copied, document):
        raise DeliveryError('certificate changed while retaining complete composition evidence')
    bundled = destination / (stem + '.tar.gz')
    with tempfile.TemporaryDirectory(prefix='appended-bundle-save-', dir=destination) as temporary:
        staged_bundle = Path(temporary) / bundled.name
        archive.archive_tree(tree, staged_bundle)
        os.link(staged_bundle, bundled, follow_symlinks=False)
    envelope = {'schema_version': 1, 'kind': 'foundation-appended-certificate-attempt',
                'delivery_sha256': delivery_hash, 'run_id': run_id, 'attempt': attempt, 'profile': profile,
                'bundle': bundled.name, 'bundle_sha256': archive.digest(bundled),
                'certificate_sha256': archive.digest(tree / 'certificate.json'), 'subject': document['subject'],
                'status': document['status'], 'eligible_for_publication': document['eligible_for_publication'],
                'eligible_for_promotion': document['eligible_for_promotion'], 'experiment': document['experiment']}
    path = destination / (stem + '.json')
    with path.open('xb') as stream:
        stream.write(archive.encoded(envelope))
    return envelope, path, bundled


def verify_certificate(remote, assets, delivery, directory, policy, profile, run_id, attempt,
                       certificate_sha256, *, eligible=True):
    if (not isinstance(run_id, str) or not github.coverage.NAME.fullmatch(run_id)
            or not github.positive(attempt) or not isinstance(certificate_sha256, str)
            or not github.SHA.fullmatch(certificate_sha256)):
        raise DeliveryError('exact composition certificate run, attempt and digest are required')
    stem = github.valid_name(f'appended-certification-{run_id}-attempt-{attempt}')
    if not {stem + '.json', stem + '.tar.gz'} <= assets.keys():
        raise DeliveryError('complete composition certificate attempt is absent')
    with tempfile.TemporaryDirectory(prefix='appended-certificate-review-') as temporary:
        root = Path(temporary); envelope_path = root / (stem + '.json')
        remote.download(assets[envelope_path.name], envelope_path)
        envelope = _load(envelope_path)
        composition._keys(envelope, ('schema_version', 'kind', 'delivery_sha256', 'run_id', 'attempt', 'profile',
                           'bundle', 'bundle_sha256', 'certificate_sha256', 'subject', 'status',
                           'eligible_for_publication', 'eligible_for_promotion', 'experiment'),
                          label='composition certificate attempt')
        if (type(envelope['schema_version']) is not int or envelope['schema_version'] != 1
                or envelope['kind'] != 'foundation-appended-certificate-attempt'
                or envelope['delivery_sha256'] != github.sha(archive.encoded(delivery))
                or envelope['run_id'] != run_id or type(envelope['attempt']) is not int
                or envelope['attempt'] != attempt or envelope['profile'] != profile
                or envelope['certificate_sha256'] != certificate_sha256 or envelope['bundle'] != stem + '.tar.gz'):
            raise DeliveryError('composition certificate attempt is stale or belongs to another delivery')
        composition._sha(envelope['bundle_sha256'])
        bundled = root / envelope['bundle']
        remote.download(assets[bundled.name], bundled, envelope['bundle_sha256'])
        tree = archive.extract(bundled, root / 'contents', max_bytes=MAX_BUNDLE)
        if archive.digest(tree / 'certificate.json') != certificate_sha256:
            raise DeliveryError('composition certificate exact bytes differ')
        document = _reproduce(directory, delivery, tree, policy, profile, run_id, attempt, eligible=eligible)
        if any(not _same(envelope[key], document[key]) for key in ('subject', 'status', 'eligible_for_publication',
                                                                 'eligible_for_promotion', 'experiment')):
            raise DeliveryError('composition attempt envelope differs from reproduced certificate')
        return {'certificate_sha256': certificate_sha256, 'run_id': run_id, 'attempt': attempt,
                'status': document['status']}


def attach_certificate(repository, tag, directory, delivery, certificate, check_plan, policy, profile,
                       reports, attempt, *, evidence_root, execute=False, transport=None):
    github.location(repository, tag)
    if (repository, tag) != (delivery.get('repository'), delivery.get('tag')):
        raise DeliveryError('composition delivery belongs to another downstream location')
    with tempfile.TemporaryDirectory(prefix='appended-certificate-package-') as temporary:
        envelope, report, bundle = bundle_certificate(directory, delivery, certificate, check_plan, policy,
            profile, reports, attempt, temporary, evidence_root=evidence_root)
        files = {path.name: archive.digest(path) for path in (report, bundle)}
        result = github.plan('attach-appended-certificate', repository, tag=tag, files=files, certificate=envelope,
                             lifecycle='append immutable complete attempt; preserve prior assets')
        if not execute:
            return result
        remote = github.Remote(repository, transport)
        def act():
            remote.visible(); info, before = verified_remote(remote, delivery, directory)
            if set(files) & before.keys():
                raise DeliveryError('composition certificate attempt exists; never overwrite')
            remote.upload_to(info, bundle); remote.upload_to(info, report)
            current = remote.by_id(info['id'], tag); after = remote.assets(current)
            if (any(current[key] != info[key] for key in ('id', 'tag_name', 'name', 'draft', 'prerelease'))
                    or remote.reference(tag) != delivery['tag_commit'] or set(after) != set(before) | set(files)
                    or any(after[name] != row for name, row in before.items())):
                raise DeliveryError('composition attachment changed prior assets or lifecycle')
            with tempfile.TemporaryDirectory(prefix='appended-certificate-upload-check-') as check:
                for name, digest in files.items():
                    remote.download(after[name], Path(check) / name, digest)
            verify_certificate(remote, after, delivery, directory, policy, profile, envelope['run_id'],
                               attempt, envelope['certificate_sha256'], eligible=False)
            remote.unchanged(tag, current, after, delivery['tag_commit'])
            return dict(result, execute=True, release_id=info['id'])
        return github.run_mutation(remote, act)


def promote(repository, tag, directory, delivery, policy, profile, run_id, attempt, certificate_sha256,
            *, execute=False, transport=None):
    github.location(repository, tag); delivery_hash = validate_delivery(delivery, directory)
    if (repository, tag) != (delivery['repository'], delivery['tag']) or delivery['experiment'] or tag == 'base':
        raise DeliveryError('only this ordinary downstream composition can be promoted')
    if (not isinstance(run_id, str) or not github.coverage.NAME.fullmatch(run_id)
            or not github.positive(attempt) or not isinstance(certificate_sha256, str)
            or not github.SHA.fullmatch(certificate_sha256)):
        raise DeliveryError('exact composition certificate run, attempt and digest are required')
    rules = _load(policy)
    if type(rules) is not dict:
        raise DeliveryError('current exact composition policy must be an object')
    _qualifier().requirements(rules, profile)
    policy_hash = archive.digest(policy)
    result = github.plan('promote-appended-composition', repository, tag=tag, delivery_sha256=delivery_hash,
                         policy_sha256=policy_hash, profile=profile, run_id=run_id, attempt=attempt,
                         certificate_sha256=certificate_sha256,
                         lifecycle='reproduce exact complete certificate; promote; verify Latest pointer')
    if not execute:
        return result
    remote = github.Remote(repository, transport)
    def act():
        remote.visible(); info, assets = verified_remote(remote, delivery, directory)
        evidence = verify_certificate(remote, assets, delivery, directory, policy, profile,
                                      run_id, attempt, certificate_sha256)
        info = remote.unchanged(tag, info, assets, delivery['tag_commit'])
        validate_delivery(delivery, directory)
        if archive.digest(policy) != policy_hash:
            raise DeliveryError('current composition policy changed during promotion')
        body = info.get('body')
        if isinstance(body, str) and body.startswith('Composition certification pending.'):
            body = body.replace('Composition certification pending.', 'Composition certification complete.', 1)
        remote.change(f'/releases/{info["id"]}', method='PATCH',
                      body={'draft': False, 'prerelease': False, 'make_latest': 'true', 'body': body})
        final = remote.by_id(info['id'], tag); after = remote.assets(final)
        if (final['draft'] or final['prerelease'] or final['name'] != info['name'] or final.get('body') != body
                or after != assets or remote.reference(tag) != delivery['tag_commit']):
            raise DeliveryError('promoted composition lifecycle or immutable assets changed')
        latest = remote.transport.json(remote.base + '/releases/latest')
        remote.info(latest, tag)
        if latest['id'] != info['id'] or latest['draft'] or latest['prerelease']:
            raise DeliveryError('Latest does not identify the exact certified composition')
        return dict(result, execute=True, release_id=info['id'], latest=True, evidence=evidence)
    return github.run_mutation(remote, act)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    publish = actions.add_parser('publish-candidate')
    publish.add_argument('--candidate-sha256', required=True)
    publish.add_argument('--application-source-commit', required=True)
    publish.add_argument('--packager-commit', required=True)
    publish.add_argument('--publication-id', required=True)
    publish.add_argument('--experiment', action='store_true')
    attach = actions.add_parser('attach-certificate')
    attach.add_argument('--certificate', type=Path, required=True)
    attach.add_argument('--plan', type=Path, required=True)
    attach.add_argument('--evidence-root', type=Path, required=True)
    attach.add_argument('reports', type=Path, nargs='+')
    promote_parser = actions.add_parser('promote')
    promote_parser.add_argument('--run-id', required=True)
    promote_parser.add_argument('--certificate-sha256', required=True)
    for action in (publish, attach, promote_parser):
        action.add_argument('--repository', required=True)
        action.add_argument('--tag', required=True)
        action.add_argument('--input', type=Path, required=True)
        action.add_argument('--execute', action='store_true')
    for action in (attach, promote_parser):
        action.add_argument('--delivery', type=Path, required=True)
        action.add_argument('--policy', type=Path, required=True)
        action.add_argument('--profile', required=True)
        action.add_argument('--attempt', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'publish-candidate':
            result = publish_candidate(args.repository, args.tag, args.input, args.candidate_sha256,
                args.application_source_commit, args.packager_commit, args.publication_id, args.experiment,
                execute=args.execute)
        elif args.action == 'attach-certificate':
            result = attach_certificate(args.repository, args.tag, args.input, _load(args.delivery),
                args.certificate, args.plan, args.policy, args.profile, args.reports, args.attempt,
                evidence_root=args.evidence_root, execute=args.execute)
        else:
            result = promote(args.repository, args.tag, args.input, _load(args.delivery), args.policy,
                args.profile, args.run_id, args.attempt, args.certificate_sha256, execute=args.execute)
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError) as error:
        parser.exit(2, 'appended delivery: ' + str(error) + '\n')
    print(archive.encoded(result).decode('utf-8'), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
