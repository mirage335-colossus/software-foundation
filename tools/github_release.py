#!/usr/bin/env python3
"""Plan-first immutable GitHub delivery; remote mutation requires explicit execution.

Callers serialize publication and retain one reviewed input snapshot throughout
an operation. A failed mutation has an unknown remote outcome: reconcile exact
IDs and bytes before a new attempt. This helper never deletes or replaces assets.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
TOOLS = str(Path(__file__).resolve().parent)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import dependency_archive as archive
import dependency_store as store
import release
import certify_release as certification
coverage = certification.coverage

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,180}\Z')
OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
CERT = re.compile(r'certification-([A-Za-z0-9][A-Za-z0-9_.-]*)-attempt-([1-9][0-9]*)\.(json|tar.gz)\Z')


class DeliveryError(ValueError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def valid_name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value) or value.endswith('.') or '..' in value:
        raise DeliveryError('expected one safe nonempty asset or tag name')
    stem = value.split('.', 1)[0].upper()
    if stem in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch(r'(?:COM|LPT)[1-9]', stem):
        raise DeliveryError('asset or tag name is reserved on a supported platform')
    return value


def location(repository, tag=None):
    if not isinstance(repository, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repository):
        raise DeliveryError('repository must be OWNER/REPO')
    for part in repository.split('/'):
        valid_name(part)
    if tag is not None:
        valid_name(tag)
    return repository


def sha(value):
    return hashlib.sha256(value).hexdigest()


def parse(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    if len(raw) > 16 * 1024 * 1024:
        raise DeliveryError('remote JSON exceeds supported inventory limit')
    return json.loads(raw, object_pairs_hook=coverage.object_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(DeliveryError('nonfinite remote JSON')))


def positive(value):
    return type(value) is int and value > 0


class GitHub:
    """Argument-array transport; never return command stderr or credentials."""
    def __init__(self, repository):
        self.repository = location(repository)

    def _run(self, arguments, *, body=None, output=None):
        result = subprocess.run(['gh', *arguments], input=body,
                                stdout=output if output is not None else subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        return result

    def json(self, endpoint, *, method='GET', body=None, missing=False):
        arguments = ['api', '--hostname', 'github.com', '--include', '--method', method, endpoint]
        if body is not None:
            arguments += ['--input', '-']
        result = self._run(arguments, body=archive.encoded(body) if body is not None else None)
        raw = result.stdout.replace(b'\r\n', b'\n')
        head, separator, payload = raw.partition(b'\n\n')
        status = re.match(rb'HTTP/\S+ ([0-9]{3})(?:\s|$)', head)
        if missing and status and status[1] == b'404' and result.returncode:
            return None
        if (not separator or not status or not 200 <= int(status[1]) < 300 or result.returncode):
            raise DeliveryError('GitHub API request failed; inspect authenticated CLI diagnostics privately')
        return parse(payload)

    def pages(self, endpoint):
        # Distribution CLI versions support --paginate without the newer
        # --slurp option. Decode its complete concatenated JSON page stream.
        result = self._run(['api', '--hostname', 'github.com', '--paginate', endpoint])
        if result.returncode:
            raise DeliveryError('complete remote pagination failed')
        raw = result.stdout.decode('utf-8')
        if len(raw) > 16 * 1024 * 1024:
            raise DeliveryError('remote pagination exceeds supported inventory limit')
        decoder = json.JSONDecoder(object_pairs_hook=coverage.object_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(DeliveryError('nonfinite remote JSON')))
        pages, offset = [], 0
        while offset < len(raw):
            while offset < len(raw) and raw[offset] in ' \r\n\t': offset += 1
            if offset == len(raw): break
            page, offset = decoder.raw_decode(raw, offset)
            if not isinstance(page, list):
                raise DeliveryError('expected every page of a remote array')
            pages.append(page)
        if not pages:
            raise DeliveryError('complete remote pagination returned no pages')
        return [item for page in pages for item in page]

    def upload(self, tag, path):
        result = self._run(['release', 'upload', tag, '--repo', 'github.com/' + self.repository, str(path)])
        if result.returncode:
            raise DeliveryError('asset upload failed; remote outcome requires reconciliation', True)

    def download(self, asset_id, path):
        with Path(path).open('xb') as stream:
            result = self._run(['api', '--hostname', 'github.com',
                                f'repos/{self.repository}/releases/assets/{asset_id}',
                                '-H', 'Accept:application/octet-stream'], output=stream)
        if result.returncode:
            raise DeliveryError('asset download failed; incomplete local staging must not be reused')


class Remote:
    def __init__(self, repository, transport=None):
        self.repository = location(repository)
        self.transport = transport or GitHub(repository)
        self.base = f'repos/{repository}'
        self.mutated = False

    def visible(self):
        value = self.transport.json(self.base)
        if (not isinstance(value, dict) or not isinstance(value.get('full_name'), str)
                or value['full_name'].casefold() != self.repository.casefold()):
            raise DeliveryError('repository visibility or identity is unconfirmed')

    def find(self, tag, required=True):
        rows = self.transport.pages(self.base + '/releases?per_page=100')
        seen = set()
        matches = []
        for row in rows:
            if not isinstance(row, dict) or not positive(row.get('id')) or row['id'] in seen:
                raise DeliveryError('invalid or duplicate release inventory entry')
            seen.add(row['id'])
            if not isinstance(row.get('tag_name'), str):
                raise DeliveryError('incomplete release inventory')
            if row['tag_name'] == tag:
                self.info(row, tag)
                matches.append(row)
        if len(matches) > 1:
            raise DeliveryError('duplicate release tags require inspection')
        if not matches:
            if required:
                raise DeliveryError('required release is absent; no implicit build or publication')
            return None
        return matches[0]

    def wait_find(self, tag, *, release_id=None):
        """Bounded observation after initialization; never repeat a mutation."""
        for delay in (0, .25, .5, 1, 2, 4, 8):
            if delay: time.sleep(delay)
            found = self.find(tag, required=False)
            if found is not None:
                if release_id is not None and found['id'] != release_id:
                    raise DeliveryError('observed release ID differs from creation response')
                return found
        raise DeliveryError('release is not visible; preserve initialization state and reconcile')

    @staticmethod
    def info(value, tag):
        if (not isinstance(value, dict) or not positive(value.get('id')) or value.get('tag_name') != tag
                or type(value.get('draft')) is not bool or type(value.get('prerelease')) is not bool
                or not isinstance(value.get('name'), str)):
            raise DeliveryError('invalid release identity or lifecycle fields')
        return value

    def assets(self, info):
        rows = self.transport.pages(self.base + f'/releases/{info["id"]}/assets?per_page=100')
        assets, ids, folded = {}, set(), set()
        for row in rows:
            if not isinstance(row, dict):
                raise DeliveryError('invalid asset entry')
            name = valid_name(row.get('name'))
            if (name.casefold() in folded or not positive(row.get('id')) or row['id'] in ids
                    or row.get('state') != 'uploaded' or type(row.get('size')) is not int or row['size'] < 0
                    or not isinstance(row.get('digest'), str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', row['digest'])):
                raise DeliveryError('duplicate, incomplete or unbound asset inventory')
            assets[name] = {key: row[key] for key in ('id', 'name', 'state', 'size', 'digest')}
            ids.add(row['id']); folded.add(name.casefold())
        return assets

    def reference(self, tag, missing=False):
        value = self.transport.json(self.base + '/git/ref/tags/' + tag, missing=missing)
        if value is None:
            return None
        obj = value.get('object', {}) if isinstance(value, dict) else {}
        if (not isinstance(obj, dict) or obj.get('type') != 'commit'
                or not isinstance(obj.get('sha'), str) or not OID.fullmatch(obj['sha'])):
            raise DeliveryError('tag must directly identify the frozen commit')
        return obj['sha']

    def change(self, endpoint, *, method='POST', body=None):
        self.mutated = True
        return self.transport.json(self.base + endpoint, method=method, body=body)

    def upload(self, tag, path):
        self.mutated = True
        self.transport.upload(tag, path)

    def download(self, row, path, expected=None):
        expected = expected or row['digest'][7:]
        if row['digest'] != 'sha256:' + expected:
            raise DeliveryError('remote asset differs from expected bytes')
        self.transport.download(row['id'], path)
        if Path(path).stat().st_size != row['size'] or archive.digest(path) != expected:
            raise DeliveryError('downloaded asset bytes differ from complete inventory')

    def unchanged(self, tag, before, assets, expected_ref=None):
        after = self.find(tag)
        for key in ('id', 'tag_name', 'name', 'draft', 'prerelease'):
            if after[key] != before[key]:
                raise DeliveryError('release identity changed during operation')
        if self.assets(after) != assets:
            raise DeliveryError('remote asset identities changed during operation')
        if expected_ref is not None and self.reference(tag) != expected_ref:
            raise DeliveryError('tag identity changed during operation')

    def not_latest(self, info):
        value = self.transport.json(self.base + '/releases/latest', missing=True)
        if value is not None:
            self.info(value, value.get('tag_name'))
            if value['id'] == info['id']:
                raise DeliveryError('candidate or base was unexpectedly selected as Latest')


def plan(operation, repository, **details):
    value = dict(operation=operation, repository=location(repository), execute=False, **details)
    value['plan_sha256'] = coverage.digest(value)
    return value


def run_mutation(remote, action):
    try:
        return action()
    except BaseException as error:
        if remote.mutated:
            raise DeliveryError('remote outcome uncertain; reconcile tag, release ID, inventory and bytes before retry: '
                                + str(error), True) from error
        raise


def candidate_identity(directory, repository, tag, source_commit, packager_commit, publication_id, experiment=False):
    location(repository, tag)
    if tag == 'base' or not OID.fullmatch(source_commit) or not OID.fullmatch(packager_commit):
        raise DeliveryError('candidate needs a distinct tag and complete source/packager commits')
    valid_name(publication_id)
    if type(experiment) is not bool or (not experiment and source_commit != packager_commit):
        raise DeliveryError('different packaging revision requires an experiment')
    directory = Path(directory)
    manifest = release.verify_release(directory)
    mapping, seen = {}, {'delivery.json'}
    for name in sorted([*manifest['files'], 'release.json']):
        path = archive.checked_file(directory, name)
        asset = valid_name(path.name)
        if asset.casefold() in seen or CERT.fullmatch(asset):
            raise DeliveryError('flattened asset names collide with another asset or evidence namespace')
        seen.add(asset.casefold())
        mapping[name] = {'asset': asset, 'sha256': archive.digest(path), 'size': path.stat().st_size}
    if (release.verify_release(directory) != manifest
            or archive.digest(directory / 'release.json') != mapping['release.json']['sha256']):
        raise DeliveryError('local release changed while freezing delivery identity')
    return {'schema_version': 1, 'repository': repository, 'tag': tag, 'source_commit': source_commit,
            'packager_commit': packager_commit, 'tag_commit': packager_commit,
            'publication_id': publication_id, 'experiment': experiment,
            'source_sha256': manifest['source']['sha256'], 'inventory_sha256': archive.digest(directory / 'release.json'),
            'files': mapping}


def validate_delivery(delivery, directory):
    if not isinstance(delivery, dict):
        raise DeliveryError('delivery identity must be an object')
    expected = candidate_identity(directory, **{key: delivery[key] for key in
        ('repository', 'tag', 'source_commit', 'packager_commit', 'publication_id', 'experiment')})
    if expected != delivery:
        raise DeliveryError('delivery identity differs from complete local release')
    return sha(archive.encoded(delivery))


def evidence_pairs(names):
    groups = {}
    for name in names:
        match = CERT.fullmatch(name)
        if not match:
            raise DeliveryError('unexpected asset outside immutable delivery and certificate attempts')
        groups.setdefault((match[1], match[2]), set()).add(match[3])
    if any(parts != {'json', 'tar.gz'} for parts in groups.values()):
        raise DeliveryError('partial certificate attempt requires reconciliation')


def verified_remote(remote, delivery, directory, *, draft=False, prerelease=None):
    validate_delivery(delivery, directory)
    if prerelease is not None and type(prerelease) is not bool:
        raise DeliveryError('prerelease pin must be a boolean or None')
    tag = delivery['tag']; info = remote.find(tag)
    title = 'experiment' if delivery['experiment'] else tag
    # Ordinary candidates are prereleases until certification permits promotion.
    # Experiment identity remains immutable and can never become an ordinary release.
    if (info['draft'] != draft or info['name'] != title
            or (delivery['experiment'] and not info['prerelease'])
            or (prerelease is not None and info['prerelease'] != prerelease)):
        raise DeliveryError('release lifecycle does not match frozen delivery')
    if remote.reference(tag) != delivery['tag_commit']:
        raise DeliveryError('tag commit differs from frozen delivery')
    assets = remote.assets(info)
    expected = {item['asset'] for item in delivery['files'].values()} | {'delivery.json'}
    if not expected <= assets.keys():
        raise DeliveryError('published delivery is missing required assets')
    extras = set(assets) - expected
    if draft and extras:
        raise DeliveryError('unexpected draft assets')
    evidence_pairs(extras)
    with tempfile.TemporaryDirectory(prefix='delivery-verify-') as temporary:
        staged = Path(temporary)
        descriptor = staged / 'delivery.json'
        remote.download(assets['delivery.json'], descriptor, sha(archive.encoded(delivery)))
        if coverage.load(descriptor) != delivery:
            raise DeliveryError('remote frozen delivery differs')
        restored = staged / 'release'; restored.mkdir()
        for name, item in delivery['files'].items():
            path = restored.joinpath(*archive.relative(name).parts); path.parent.mkdir(parents=True, exist_ok=True)
            remote.download(assets[item['asset']], path, item['sha256'])
        release.verify_release(restored)
    remote.unchanged(tag, info, assets, delivery['tag_commit'])
    return info, assets


def fetch_base(repository, recipe, output, *, transport=None):
    expected = store.names(recipe); remote = Remote(repository, transport); remote.visible()
    info = remote.find('base')
    if info['draft'] or not info['prerelease'] or info['name'] != 'base':
        raise DeliveryError('base must be a published prerelease')
    assets = remote.assets(info)
    reference = remote.reference('base')
    if not set(expected) <= assets.keys():
        raise DeliveryError('exact complete dependency group is absent; no cold build fallback')
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise DeliveryError('fetch destination must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.base-fetch-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'group'; stage.mkdir()
        for name in expected:
            remote.download(assets[name], stage / name)
        files = store.verify_group(stage, recipe)
        remote.unchanged('base', info, assets, reference)
        stage.rename(output)
    return {'fetched': True, 'recipe': recipe, 'files': files}


def publish_base(repository, recipe, group, source_commit, *, execute=False, transport=None):
    files = store.verify_group(group, recipe)
    if not OID.fullmatch(source_commit):
        raise DeliveryError('complete source commit required')
    result = plan('publish-base', repository, recipe=recipe, source_commit=source_commit, files=files,
                  lifecycle='prerelease; never Latest; immutable complete group')
    if not execute:return result
    remote = Remote(repository, transport)
    def act():
        remote.visible(); info = remote.find('base', False)
        before = remote.assets(info) if info else {}
        reference = remote.reference('base') if info else source_commit
        present = set(files) & before.keys()
        if present and present != set(files):
            raise DeliveryError('partial existing dependency group requires reconciliation')
        if info and (info['draft'] or not info['prerelease'] or info['name'] != 'base'):
            raise DeliveryError('existing base has incompatible lifecycle')
        if present:
            with tempfile.TemporaryDirectory(prefix='base-compare-') as temporary:
                for name in files:remote.download(before[name], Path(temporary) / name, files[name])
                if store.verify_group(temporary, recipe) != files:raise DeliveryError('immutable group conflicts')
            remote.unchanged('base', info, before, reference); remote.not_latest(info)
            return dict(result, execute=True, reused=True)
        if info is None:
            if remote.reference('base', True) is not None:raise DeliveryError('base tag already exists without its release')
            remote.change('/git/refs', body={'ref':'refs/tags/base','sha':source_commit})
            info = remote.info(remote.change('/releases', body={'tag_name':'base','target_commitish':source_commit,
                'name':'base','body':'Complete reusable dependency groups indexed by recipe identity.',
                'draft':True,'prerelease':True,'make_latest':'false'}), 'base')
            if not info['draft'] or not info['prerelease'] or info['name']!='base':
                raise DeliveryError('created base does not match requested draft lifecycle')
            remote.wait_find('base', release_id=info['id'])
        for name in store.names(recipe):remote.upload('base', Path(group) / name)
        current = remote.find('base'); assets = remote.assets(current)
        if any(current[key]!=info[key] for key in ('id','name','draft','prerelease')):
            raise DeliveryError('base release identity changed during upload')
        if set(assets) != set(before) | set(files) or any(assets[n] != v for n,v in before.items()):
            raise DeliveryError('base inventory changed unexpectedly')
        with tempfile.TemporaryDirectory(prefix='base-confirm-') as temporary:
            for name in files:remote.download(assets[name], Path(temporary) / name, files[name])
            if store.verify_group(temporary, recipe) != files:raise DeliveryError('uploaded group differs')
        if store.verify_group(group, recipe) != files:raise DeliveryError('local dependency group changed')
        remote.unchanged('base', current, assets, reference)
        if current['draft']:
            remote.change(f'/releases/{current["id"]}', method='PATCH', body={'draft':False,'prerelease':True,'make_latest':'false'})
        final = remote.find('base')
        if (final['id'] != current['id'] or final['name']!='base' or final['draft']
                or not final['prerelease'] or remote.assets(final) != assets):
            raise DeliveryError('base finalization could not be verified')
        remote.not_latest(final)
        if remote.reference('base') != reference:raise DeliveryError('base tag identity changed')
        return dict(result, execute=True, reused=False, release_id=final['id'])
    return run_mutation(remote, act)


def publish_candidate(repository, tag, directory, source_commit, packager_commit, publication_id,
                      experiment=False, *, execute=False, transport=None):
    delivery = candidate_identity(directory, repository, tag, source_commit, packager_commit, publication_id, experiment)
    result = plan('publish-candidate', repository, delivery=delivery, lifecycle='draft upload, verify every byte, publish prerelease until certified promotion; never Latest')
    if not execute:return result
    remote = Remote(repository, transport)
    def act():
        remote.visible()
        if remote.find(tag, False) is not None or remote.reference(tag, True) is not None:
            raise DeliveryError('release or tag already exists; no overwrite or implicit resume')
        remote.change('/git/refs', body={'ref':'refs/tags/'+tag,'sha':delivery['tag_commit']})
        info = remote.info(remote.change('/releases', body={'tag_name':tag,'target_commitish':delivery['tag_commit'],
            'name':'experiment' if experiment else tag,'body':'Certification pending. Immutable application assets.',
            'draft':True,'prerelease':True,'make_latest':'false'}), tag)
        remote.wait_find(tag, release_id=info['id'])
        for name in delivery['files']:remote.upload(tag, Path(directory) / name)
        with tempfile.TemporaryDirectory(prefix='delivery-metadata-') as temporary:
            path=Path(temporary)/'delivery.json';path.write_bytes(archive.encoded(delivery));remote.upload(tag,path)
        current, assets = verified_remote(remote, delivery, directory, draft=True, prerelease=True)
        if current['id'] != info['id']:raise DeliveryError('draft release identity changed')
        remote.change(f'/releases/{info["id"]}', method='PATCH', body={'draft':False,'prerelease':True,'make_latest':'false'})
        final, final_assets = verified_remote(remote, delivery, directory, prerelease=True)
        if final['id'] != info['id'] or final_assets != assets:raise DeliveryError('publication identity changed')
        remote.not_latest(final)
        return dict(result, execute=True, release_id=final['id'])
    return run_mutation(remote, act)


def bundle_certificate(directory, delivery, certificate, check_plan, policy, profile, reports, attempt, destination):
    validate_delivery(delivery, directory)
    if not positive(attempt):raise DeliveryError('certificate attempt must be positive')
    certificate = Path(certificate); reports = [Path(p) for p in reports]
    document = coverage.load(certificate)
    frozen = coverage.load(check_plan); rules = coverage.load(policy)
    expected = certification.certify(Path(directory), release.verify_release(directory), frozen, reports,
                                     rules, profile, delivery['experiment'])
    if document != expected:raise DeliveryError('certificate does not match current complete policy and evidence')
    run_id = document['run_id']
    if not isinstance(run_id, str) or not coverage.NAME.fullmatch(run_id):raise DeliveryError('invalid certification run')
    stem = valid_name(f'certification-{run_id}-attempt-{attempt}')
    tree = Path(destination) / 'contents'; tree.mkdir()
    report_paths = {}
    def retain(source, name):
        source = Path(source)
        if source.is_symlink() or not source.is_file():raise DeliveryError('evidence must be an ordinary file')
        target = tree.joinpath(*archive.relative(name).parts);target.parent.mkdir(parents=True,exist_ok=True)
        with source.open('rb') as incoming, target.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
        if archive.digest(source) != archive.digest(target):raise DeliveryError('local evidence changed during retention')
    for source,name in ((certificate,'certificate.json'),(check_plan,'plan.json'),(policy,'policy.json')):retain(source,name)
    for path in reports:
        report=coverage.load(path); check=valid_name(report['check'])
        relative='reports/'+check+'/'+valid_name(path.name)
        if check in report_paths:raise DeliveryError('duplicate evidence check')
        report_paths[check]=relative;retain(path,relative)
        for name in report['evidence']:
            retain(coverage.local(path.parent,name),'reports/'+check+'/'+name)
    copied_reports = [tree / name for name in report_paths.values()]
    copied_certificate = coverage.load(tree / 'certificate.json')
    if (copied_certificate != document or coverage.load(tree / 'plan.json') != frozen
            or coverage.load(tree / 'policy.json') != rules
            or certification.certify(Path(directory), release.verify_release(directory), frozen,
                                     copied_reports, rules, profile, delivery['experiment']) != document):
        raise DeliveryError('certificate evidence changed while creating the complete bundle')
    metadata={'schema_version':1,'delivery_sha256':sha(archive.encoded(delivery)), 'run_id':run_id,
              'attempt':attempt,'profile':profile,'reports':report_paths,
              'report_order':list(report_paths),'files':archive.file_inventory(tree)}
    (tree/'bundle.json').write_bytes(archive.encoded(metadata))
    bundled=Path(destination)/(stem+'.tar.gz');archive.archive_tree(tree,bundled)
    envelope={'schema_version':1,'delivery_sha256':metadata['delivery_sha256'],'run_id':run_id,'attempt':attempt,
              'bundle':bundled.name,'bundle_sha256':archive.digest(bundled),
              'certificate_sha256':archive.digest(tree/'certificate.json'),'subject':document['subject'],
              'status':document['status'],'eligible_for_promotion':document['eligible_for_promotion'],
              'experiment':document['experiment']}
    path=Path(destination)/(stem+'.json');path.write_bytes(archive.encoded(envelope))
    return envelope,path,bundled


def attach_certificate(repository, tag, directory, delivery, certificate, check_plan, policy, profile,
                       reports, attempt, *, execute=False, transport=None):
    location(repository,tag)
    if (repository,tag)!=(delivery.get('repository'),delivery.get('tag')):raise DeliveryError('delivery belongs to another location')
    with tempfile.TemporaryDirectory(prefix='certificate-package-') as temporary:
        envelope,report,bundle=bundle_certificate(directory,delivery,certificate,check_plan,policy,profile,reports,attempt,temporary)
        files={p.name:archive.digest(p) for p in (report,bundle)}
        result=plan('attach-certificate',repository,tag=tag,files=files,certificate=envelope,
                    lifecycle='append one immutable attempt; preserve every previous asset; no promotion')
        if not execute:return result
        remote=Remote(repository,transport)
        def act():
            remote.visible();info,before=verified_remote(remote,delivery,directory)
            if set(files)&before.keys():raise DeliveryError('certificate attempt already exists; inspect it, never overwrite')
            remote.upload(tag,bundle);remote.upload(tag,report)
            current,after=verified_remote(remote,delivery,directory,prerelease=info['prerelease'])
            if current['id']!=info['id'] or set(after)!=set(before)|set(files) or any(after[n]!=v for n,v in before.items()):
                raise DeliveryError('certificate attachment changed an existing asset')
            with tempfile.TemporaryDirectory(prefix='certificate-confirm-') as check:
                for name,digest in files.items():remote.download(after[name],Path(check)/name,digest)
            remote.unchanged(tag,current,after,delivery['tag_commit'])
            return dict(result,execute=True,release_id=info['id'])
        return run_mutation(remote,act)


def verify_certificate(remote, assets, delivery, directory, policy, profile, run_id, attempt, certificate_sha256):
    if not positive(attempt) or not coverage.NAME.fullmatch(run_id) or not SHA.fullmatch(certificate_sha256):
        raise DeliveryError('exact certificate run, attempt and digest are required')
    stem=valid_name(f'certification-{run_id}-attempt-{attempt}')
    names={stem+'.json',stem+'.tar.gz'}
    if not names<=assets.keys():raise DeliveryError('complete certificate attempt is missing')
    with tempfile.TemporaryDirectory(prefix='certificate-review-') as temporary:
        temporary=Path(temporary);path=temporary/(stem+'.json');remote.download(assets[path.name],path)
        envelope=coverage.load(path)
        expected_fields={'schema_version','delivery_sha256','run_id','attempt','bundle','bundle_sha256',
                         'certificate_sha256','subject','status','eligible_for_promotion','experiment'}
        coverage.fields(envelope,expected_fields)
        if (envelope['schema_version']!=1 or envelope['delivery_sha256']!=sha(archive.encoded(delivery))
                or envelope['run_id']!=run_id or envelope['attempt']!=attempt
                or envelope['certificate_sha256']!=certificate_sha256 or envelope['bundle']!=stem+'.tar.gz'
                or not isinstance(envelope['bundle_sha256'],str) or not SHA.fullmatch(envelope['bundle_sha256'])):
            raise DeliveryError('certificate attempt is stale or belongs to another delivery')
        bundled=temporary/envelope['bundle'];remote.download(assets[bundled.name],bundled,envelope['bundle_sha256'])
        tree=archive.extract(bundled,temporary/'contents',max_bytes=4*1024**3)
        metadata=coverage.load(tree/'bundle.json')
        coverage.fields(metadata,{'schema_version','delivery_sha256','run_id','attempt','profile','reports','report_order','files'})
        if (metadata['schema_version']!=1 or metadata['delivery_sha256']!=envelope['delivery_sha256']
                or metadata['run_id']!=run_id or metadata['attempt']!=attempt or metadata['profile']!=profile):
            raise DeliveryError('bundled evidence identity differs')
        archive.verify_inventory(tree,metadata['files'],exclude=('bundle.json',))
        if archive.digest(tree/'certificate.json')!=certificate_sha256:raise DeliveryError('certificate bytes changed')
        rules=coverage.load(policy)
        if coverage.load(tree/'policy.json')!=rules:raise DeliveryError('current promotion policy differs from tested policy')
        reports=[]
        if not isinstance(metadata['reports'],dict) or not metadata['reports']:raise DeliveryError('complete reports required')
        if (not isinstance(metadata['report_order'],list) or len(set(metadata['report_order']))!=len(metadata['report_order'])
                or set(metadata['report_order'])!=set(metadata['reports'])):
            raise DeliveryError('complete original report order required')
        for check in metadata['report_order']:
            name=metadata['reports'][check]
            valid_name(check);path=archive.checked_file(tree,name)
            if coverage.load(path)['check']!=check:raise DeliveryError('report identity mismatch')
            reports.append(path)
        # Preserve original caller order when comparing the certifier's report list.
        frozen=coverage.load(tree/'plan.json')
        saved=coverage.load(tree/'certificate.json')
        result=certification.certify(Path(directory),release.verify_release(directory),frozen,reports,rules,profile,False)
        if result!=saved or result['subject']!=envelope['subject']:
            raise DeliveryError('saved certificate does not reproduce from complete retained evidence')
        if (result['status'] not in ('passed','passed_with_warnings') or result['eligible_for_promotion'] is not True
                or result['experiment'] is not False or envelope['eligible_for_promotion'] is not True
                or envelope['experiment'] is not False or envelope['status']!=result['status']):
            raise DeliveryError('certificate does not qualify this ordinary release')
        return {'certificate_sha256':certificate_sha256,'run_id':run_id,'attempt':attempt,'status':result['status']}


def promote(repository,tag,directory,delivery,policy,profile,run_id,attempt,certificate_sha256,*,execute=False,transport=None):
    location(repository,tag);validate_delivery(delivery,directory)
    if (repository,tag)!=(delivery['repository'],delivery['tag']) or delivery['experiment'] or tag=='base':
        raise DeliveryError('only this ordinary application release can be promoted')
    if not positive(attempt) or not coverage.NAME.fullmatch(run_id) or not SHA.fullmatch(certificate_sha256):
        raise DeliveryError('exact certificate run, attempt and digest are required')
    certification.requirements(coverage.load(policy),profile)
    result=plan('promote',repository,tag=tag,delivery_sha256=sha(archive.encoded(delivery)),
                policy_sha256=archive.digest(policy),profile=profile,run_id=run_id,attempt=attempt,
                certificate_sha256=certificate_sha256,lifecycle='verify exact certificate and every remote asset, change Latest, verify pointer')
    if not execute:return result
    remote=Remote(repository,transport)
    def act():
        remote.visible();info,assets=verified_remote(remote,delivery,directory)
        evidence=verify_certificate(remote,assets,delivery,directory,policy,profile,run_id,attempt,certificate_sha256)
        # Reread all byte identities immediately before the final mutation.
        current,again=verified_remote(remote,delivery,directory,prerelease=info['prerelease'])
        if current['id']!=info['id'] or again!=assets:raise DeliveryError('remote delivery changed after certificate review')
        if archive.digest(policy)!=result['policy_sha256']:raise DeliveryError('promotion policy changed')
        remote.change(f'/releases/{info["id"]}',method='PATCH',body={'draft':False,'prerelease':False,'make_latest':'true'})
        final,after=verified_remote(remote,delivery,directory,prerelease=False)
        if final['id']!=info['id'] or after!=assets:raise DeliveryError('promoted assets changed')
        latest=remote.transport.json(remote.base+'/releases/latest')
        remote.info(latest,tag)
        if latest['id']!=info['id'] or latest['draft'] or latest['prerelease']:
            raise DeliveryError('Latest pointer does not identify the exact certified release')
        return dict(result,execute=True,release_id=info['id'],latest=True,evidence=evidence)
    return run_mutation(remote,act)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('fetch-base','publish-base','publish-candidate','attach-certificate','promote'))
    parser.add_argument('--input',default='-',help='strict JSON request file or stdin')
    parser.add_argument('--execute',action='store_true',help='explicitly execute planned remote mutations')
    args=parser.parse_args(argv)
    request=parse(sys.stdin.buffer.read() if args.input=='-' else Path(args.input).read_bytes())
    if not isinstance(request,dict) or 'execute' in request or 'transport' in request:
        raise DeliveryError('request must be an object; execution is a separate explicit CLI option')
    operation=globals()[args.operation.replace('-','_')]
    result=operation(**request,**({} if args.operation=='fetch-base' else {'execute':args.execute}))
    try:
        print(json.dumps(result,sort_keys=True,indent=2),flush=True)
    except (OSError,ValueError) as error:
        if args.execute and args.operation!='fetch-base':
            raise DeliveryError('execution completed but its receipt could not be delivered; reconcile remote before retry',True) from error
        raise
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
        print(json.dumps({'ok':False,'uncertain':getattr(error,'uncertain',False),
                          'error':str(error),'action':'reconcile remote before retry' if getattr(error,'uncertain',False)
                          else 'correct the request or inspect read-only state'}),file=sys.stderr)
        sys.exit(1)
