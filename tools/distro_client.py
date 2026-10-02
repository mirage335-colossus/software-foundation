#!/usr/bin/env python3
"""Authenticated native package channels, cached locally for normal package updates.

The operator supplies an independent signing fingerprint and policy digest. Public
HTTPS retrieval needs no GitHub account. Refresh is explicit; ordinary APT/pacman
operations consume the last complete verified generation without network access to
the upstream software suppliers. This helper never compiles application sources.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

import distribution_release as release

MAX_JSON = 16 * 1024 * 1024
MAX_DOWNLOAD_SECONDS = 600


class ReleaseRedirects(HTTPRedirectHandler):
    """Bound public release redirects before issuing the next HTTPS request."""
    max_redirections = 5
    max_repeats = 2

    def __init__(self, initial):
        self.initial = initial

    def validate(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc not in ('github.com', 'release-assets.githubusercontent.com') or
                parsed.fragment or not parsed.path.startswith('/') or
                parsed.netloc == 'github.com' and url != self.initial):
            raise ValueError('public asset redirect escaped its selected HTTPS release')
        return url

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicGitHub:
    """Read-only public transport with bounded pages, timeouts and exact downloads."""
    def __init__(self, repository):
        self.repository = release.delivery.location(repository)
        self.releases = {}
        self.assets = {}

    def request(self, endpoint, accept='application/vnd.github+json'):
        if not endpoint.startswith('repos/' + self.repository + '/'):
            raise ValueError('public client request escaped its configured repository')
        response = urlopen(Request('https://api.github.com/' + endpoint,
            headers={'Accept': accept, 'User-Agent': 'software-foundation-channel/1'}), timeout=60)
        if urlsplit(response.url).scheme != 'https':
            response.close(); raise ValueError('public transport redirected away from HTTPS')
        return response

    def json(self, endpoint, **kwargs):
        if kwargs.get('method', 'GET') != 'GET' or kwargs.get('body') is not None:
            raise ValueError('public client cannot mutate remote state')
        try:
            with self.request(endpoint) as response:
                data = response.read(MAX_JSON + 1)
        except HTTPError as error:
            if error.code == 404 and kwargs.get('missing') is True:
                return None
            raise
        if len(data) > MAX_JSON: raise ValueError('public JSON exceeds bound')
        return release.delivery.parse(data)

    def pages(self, endpoint):
        result = []
        for page in range(1, 101):
            rows = self.json(endpoint + ('&' if '?' in endpoint else '?') + 'page=' + str(page))
            if not isinstance(rows, list): raise ValueError('expected complete array page')
            result.extend(rows)
            if len(rows) < 100:
                self.remember(endpoint, result)
                return result
        raise ValueError('public pagination exceeds bound; no partial inventory accepted')

    def remember(self, endpoint, rows):
        """Bind download IDs only after complete metadata pagination succeeds."""
        route = endpoint.split('?', 1)[0]
        base = 'repos/' + self.repository + '/releases'
        if route == base:
            observed = {}
            for row in rows:
                if (not isinstance(row, dict) or not release.delivery.positive(row.get('id')) or
                        not isinstance(row.get('tag_name'), str) or row['id'] in observed):
                    raise ValueError('invalid complete public release inventory')
                observed[row['id']] = row['tag_name']
            if any(key in self.releases and self.releases[key] != value for key, value in observed.items()):
                raise ValueError('public release identity changed')
            self.releases.update(observed)
            return
        match = re.fullmatch(re.escape(base) + r'/([1-9][0-9]*)/assets', route)
        if match is None:
            return
        identity = int(match[1])
        if identity not in self.releases:
            raise ValueError('asset inventory needs its observed public release')
        tag = release.delivery.valid_name(self.releases[identity])
        observed = {}; names = set()
        for row in rows:
            if not isinstance(row, dict): raise ValueError('invalid public asset inventory')
            name = release.delivery.valid_name(row.get('name'))
            url = 'https://github.com/' + self.repository + '/releases/download/' + tag + '/' + name
            if (not release.delivery.positive(row.get('id')) or row['id'] in observed or name.casefold() in names or
                    row.get('state') != 'uploaded' or type(row.get('size')) is not int or not 0 <= row['size'] <= release.MAX_ASSET or
                    not isinstance(row.get('digest'), str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', row['digest']) or
                    row.get('browser_download_url') != url):
                raise ValueError('public asset lacks its exact release URL, size or digest')
            observed[row['id']] = dict(url=url, size=row['size'], sha256=row['digest'][7:])
            names.add(name.casefold())
        if any(key in self.assets and self.assets[key] != value for key, value in observed.items()):
            raise ValueError('public asset identity changed')
        self.assets.update(observed)

    def download(self, asset_id, path):
        if not release.delivery.positive(asset_id) or asset_id not in self.assets:
            raise ValueError('download requires an observed complete public asset inventory')
        item = self.assets[asset_id]; path = Path(path)
        if path.exists() or path.is_symlink(): raise ValueError('public download destination must be new')
        redirects = ReleaseRedirects(item['url'])
        request = Request(redirects.validate(item['url']), headers={'User-Agent': 'software-foundation-channel/1'})
        deadline = time.monotonic() + MAX_DOWNLOAD_SECONDS
        # Stage only this response. A timeout or truncated body never becomes a
        # destination, and the caller publishes its generation only after replay.
        with tempfile.TemporaryDirectory(prefix='.public-asset-', dir=path.parent) as temporary:
            staged = Path(temporary) / 'payload'
            with build_opener(redirects).open(request, timeout=60) as response, staged.open('xb') as output:
                redirects.validate(response.url)
                total = 0; hashed = hashlib.sha256()
                while True:
                    if time.monotonic() >= deadline: raise ValueError('public asset transfer deadline exceeded')
                    # read1 performs one bounded socket read; read(n) can wait for
                    # n bytes indefinitely while a peer keeps trickling data.
                    data = response.read1(min(1024 * 1024, item['size'] - total + 1))
                    if time.monotonic() >= deadline: raise ValueError('public asset transfer deadline exceeded')
                    if not data: break
                    total += len(data)
                    if total > item['size']: raise ValueError('public asset exceeds declared size')
                    hashed.update(data); output.write(data)
            if total != item['size'] or hashed.hexdigest() != item['sha256']:
                raise ValueError('public asset bytes differ from complete inventory')
            release.copy_new(staged, path)


def configuration(value):
    required = {'schema_version', 'repository', 'target', 'trusted_fingerprint', 'policy_sha256',
                'selection', 'location'}
    if not isinstance(value, dict) or set(value) != required or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('complete client configuration required')
    release.delivery.location(value['repository']); release.apt.full_fingerprint(value['trusted_fingerprint'])
    if value['target'] not in release.TARGETS or not release.delivery.SHA.fullmatch(str(value['policy_sha256'])):
        raise ValueError('supported native target and exact policy required')
    location = value['location']
    if (not isinstance(location, str) or not re.fullmatch(r'/[A-Za-z0-9_./-]+', location) or
            Path(location).absolute() != Path(location).resolve() or Path(location) == Path('/') or '..' in Path(location).parts):
        raise ValueError('dedicated absolute physical client location required')
    selected = value['selection']
    if selected != {'track': 'qualified'}:
        if not isinstance(selected, dict) or set(selected) != {'tag', 'manifest_sha256'}:
            raise ValueError('exact tag/digest or explicitly qualified tracking selection required')
        release.delivery.valid_name(selected['tag'])
        if not release.delivery.SHA.fullmatch(str(selected['manifest_sha256'])):
            raise ValueError('exact selected manifest digest required')
    return value


def select(value, transport):
    selected = value['selection']
    if 'tag' in selected: return selected
    rows = transport.pages('repos/' + value['repository'] + '/releases?per_page=100')
    candidates = []
    suffix = release.TARGETS[value['target']][0]
    for row in rows:
        tag = row.get('tag_name', '')
        match = re.fullmatch(r'distro-([0-9]+\.[0-9]+\.[0-9]+)-' + suffix + r'-r([1-9][0-9]*)-s([1-9][0-9]*)', tag)
        if not match or row.get('draft') is not False or row.get('prerelease') is not False: continue
        body = release.delivery.parse(row.get('body', ''))
        if (body.get('kind') != 'signed-distribution' or not release.delivery.SHA.fullmatch(str(body.get('manifest_sha256', ''))) or
                not isinstance(body.get('native_qualification'), dict)):
            raise ValueError('qualified channel lacks its exact native qualification marker')
        release.native_marker(body['native_qualification'], value['target'])
        order = (int(match[3]), tuple(map(int, match[1].split('.'))), int(match[2]))
        candidates.append((order, {'tag': tag, 'manifest_sha256': body['manifest_sha256']}))
    if not candidates: raise ValueError('no qualified public channel for selected target')
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > 1 and candidates[-1][0][0] == candidates[-2][0][0]:
        raise ValueError('ambiguous same-sequence qualified channels')
    return candidates[-1][1]


@contextmanager
def locked(location):
    if os.name != 'posix': raise ValueError('native channel activation requires POSIX')
    import fcntl
    location = Path(location)
    location.mkdir(mode=0o755, parents=True, exist_ok=True)
    if location.resolve() != location or location.is_symlink(): raise ValueError('linked client root')
    lock = location / '.refresh.lock'
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+b') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise ValueError('invalid refresh lock')
        fcntl.flock(stream, fcntl.LOCK_EX)
        if lock.stat().st_ino != info.st_ino: raise ValueError('refresh lock identity changed')
        yield


def current(location):
    pointer = Path(location) / 'current'
    if not pointer.is_symlink():
        if pointer.exists(): raise ValueError('current is not a managed pointer')
        return None
    target = os.readlink(pointer)
    if not re.fullmatch(r'generations/[1-9][0-9]*-[0-9a-f]{64}', target):
        raise ValueError('invalid active generation pointer')
    root = Path(location) / target
    if root.is_symlink() or not root.is_dir(): raise ValueError('invalid generation directory')
    return root


def previous_identity(root, value):
    """Verify the signed old manifest, without requiring unexpired old metadata."""
    data, _ = release.distro.ordinary(root / 'assets/distribution.json', 8 * 1024 * 1024)
    manifest = release.delivery.parse(data)
    request = release.request(manifest['request'])
    if request['repository'] != value['repository'] or request['target'] != value['target'] or request['trusted_fingerprint'] != value['trusted_fingerprint']:
        raise ValueError('active channel trust or target differs')
    release.distro.verify_signature(data, release.distro.ordinary(root/'assets/distribution.json.sig')[0],
        release.distro.ordinary(root/'assets/archive-keyring.gpg')[0], value['trusted_fingerprint'])
    if root.name != str(request['sequence']) + '-' + hashlib.sha256(data).hexdigest():
        raise ValueError('active manifest identity differs from generation name')
    return manifest


def advance(previous, candidate):
    before, after = previous['request'], candidate['request']
    if (before['repository'], before['target'], before['trusted_fingerprint']) != (after['repository'], after['target'], after['trusted_fingerprint']):
        raise ValueError('channel identity changed')
    if after['sequence'] < before['sequence'] or (after['sequence'] == before['sequence'] and candidate != previous):
        raise ValueError('rollback or same-sequence replacement')
    if set(previous['backends']) - set(candidate['backends']): raise ValueError('package removal')
    for backend, spec in previous['specifications'].items():
        next_spec = candidate['specifications'][backend]
        if release.distro.version_key(next_spec) < release.distro.version_key(spec) or (release.distro.version_key(next_spec) == release.distro.version_key(spec) and next_spec != spec):
            raise ValueError('package downgrade or same-version replacement')


def sync_tree(root):
    """Persist every verified payload and descendant entry before publication."""
    root = Path(root)
    directories = [root]
    for path in root.rglob('*'):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            directories.append(path)
        elif stat.S_ISREG(info.st_mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                if os.fstat(descriptor).st_ino != info.st_ino:
                    raise ValueError('generation file identity changed')
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        else:
            raise ValueError('generation contains a non-regular entry')
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        release.distro.sync_directory(directory)


def refresh(value, policy, *, transport=None, prepared=None):
    value = configuration(value); policy = Path(policy).resolve(strict=True)
    if release.archive.digest(policy) != value['policy_sha256']: raise ValueError('trusted policy bytes differ')
    location = Path(value['location']); transport = transport or PublicGitHub(value['repository'])
    with locked(location):
        prior = current(location); previous = previous_identity(prior, value) if prior else None
        selected = select(value, transport)
        with tempfile.TemporaryDirectory(prefix='.refresh-', dir=location) as temporary:
            stage = Path(temporary)/'generation'; stage.mkdir(mode=0o755); stage.chmod(0o755)
            if prepared is None:
                manifest = release.fetch(value['repository'], selected['tag'], selected['manifest_sha256'],
                    stage/'assets', policy, value['trusted_fingerprint'], transport=transport)
            else:
                if release.archive.digest(Path(prepared)/'distribution.json') != selected['manifest_sha256']:
                    raise ValueError('prepared manifest differs from selected bytes')
                manifest = release.verify(prepared, policy, value['trusted_fingerprint'])
                if manifest['tag'] != selected['tag'] or manifest['request']['repository'] != value['repository']:
                    raise ValueError('prepared channel identity differs')
                shutil.copytree(prepared, stage/'assets')
                if release.verify(stage/'assets', policy, value['trusted_fingerprint']) != manifest:
                    raise ValueError('prepared bytes changed while copying')
            if manifest['request']['target'] != value['target']: raise ValueError('selected channel target differs')
            if previous: advance(previous, manifest)
            release.archive.extract(stage/'assets/channels.tar.gz', stage/'channels', max_bytes=release.distro.MAX_BYTES * 2)
            # Only freshly created owned directories: transport deliberately omits their modes.
            for tree in (stage/'assets', stage/'channels'):
                tree.chmod(0o755)
                for path in tree.rglob('*'):
                    if path.is_dir(): path.chmod(0o755)
            identity = str(manifest['request']['sequence']) + '-' + selected['manifest_sha256']
            generations = location/'generations'; generations.mkdir(mode=0o755, exist_ok=True)
            if generations.is_symlink(): raise ValueError('linked generation root')
            destination = generations/identity
            if destination.exists():
                # Exact assets must remain untouched; derived Portage metadata belongs outside assets.
                if release.verify(destination/'assets', policy, value['trusted_fingerprint']) != manifest:
                    raise ValueError('existing generation differs')
                if release.distro.tree(destination/'channels') != release.distro.tree(stage/'channels'):
                    raise ValueError('derived channel changed; preserve state for inspection')
            else:
                # Publish one complete directory before switching the active pointer.
                # A crash cannot expose a half-populated named generation.
                sync_tree(stage)
                stage.rename(destination)
                release.distro.sync_directory(generations)
            if prior == destination: return {'changed': False, 'tag': selected['tag'], 'sequence': manifest['request']['sequence']}
            pointer = Path(temporary)/'current'; pointer.symlink_to('generations/'+identity)
            if current(location) != prior: raise ValueError('active pointer changed during refresh')
            os.replace(pointer, location/'current')
            try: release.distro.sync_directory(location)
            except OSError as error:
                raise release.distro.CommitUncertain('active channel changed; inspect current before retry') from error
        return {'changed': True, 'tag': selected['tag'], 'sequence': manifest['request']['sequence']}


def native_config(value, kind, helper, config_path):
    value = configuration(value); location = value['location']; helper = str(Path(helper).resolve()); config_path = str(Path(config_path).resolve())
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+', path) for path in (helper, config_path)):
        raise ValueError('native configuration requires simple absolute paths')
    if kind == 'apt':
        return f'Types: deb\nURIs: file:{location}/current/channels/apt\nSuites: ./\nArchitectures: {release.TARGETS[value["target"]][1]}\nSigned-By: {location}/current/assets/archive-keyring.gpg\n'
    if kind == 'arch':
        return f'[software-foundation]\nSigLevel = Required DatabaseRequired\nServer = file://{location}/current/channels/native/arch\n'
    if kind == 'gentoo':
        return f'[software-foundation-bin]\nlocation = {location}/current/channels/native/gentoo\nmasters = gentoo\nsync-type = foundation-release\nsync-uri = https://github.com/{value["repository"]}/releases\nauto-sync = yes\nsync-user = root\nsync-foundation-helper = {helper}\nsync-foundation-config = {config_path}\n'
    raise ValueError('unknown native client')


PORTAGE_ADAPTER = '''"""Verified retained release overlay adapter."""
import subprocess
import json
from portage.sync.config_checks import CheckSyncConfig
from portage.sync.syncbase import SyncBase
module_spec = {'name': 'foundation_release', 'description': 'Verified release overlay',
    'provides': {'foundation-release-module': {'name': 'foundation-release',
        'sourcefile': '__init__', 'class': 'FoundationRelease', 'description': 'Verified release assets',
        'functions': ['sync'], 'func_desc': {'sync': 'Refresh authenticated release overlay'},
        'validate_config': CheckSyncConfig,
        'module_specific_options': ('sync-foundation-helper', 'sync-foundation-config')}}}
class FoundationRelease(SyncBase):
    def __init__(self): super().__init__(None, None)
    @staticmethod
    def name(): return 'FoundationRelease'
    def sync(self, **kwargs):
        self._kwargs(kwargs)
        options = self.repo.module_specific_options
        helper, config = options.get('sync-foundation-helper'), options.get('sync-foundation-config')
        if not helper or not config: return (1, False)
        result = subprocess.run(['/usr/bin/python3', '-B', helper, 'refresh', '--config', config],
            text=True, capture_output=True)
        if result.stderr: print(result.stderr, end='')
        if result.returncode: return (result.returncode, False)
        try:
            value = json.loads(result.stdout)
            if type(value['changed']) is not bool: return (1, False)
            return (0, value['changed'])
        except (ValueError, KeyError, TypeError): return (1, False)
'''


def install_portage(config, helper=Path(__file__)):
    """Install only the adapter, from an already operator-trusted retained tool tree."""
    if not hasattr(os, 'geteuid') or os.geteuid() != 0: raise ValueError('Portage installation requires root')
    import portage.sync.modules
    value = configuration(release.archive.read_json(config)); module = Path(portage.sync.modules.__path__[0])/'foundation_release'
    files = {module/'__init__.py': PORTAGE_ADAPTER,
        Path('/etc/portage/repos.conf/software-foundation-bin.conf'): native_config(value, 'gentoo', helper, config)}
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.is_symlink() or path.read_text() != text: raise ValueError('preserve existing different Portage configuration')
        else:
            with path.open('x') as stream: stream.write(text)
            path.chmod(0o644)
    return {'adapter': str(module), 'config': str(Path(config).resolve())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('refresh', 'config', 'install-portage'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=Path(__file__).resolve().parents[1]/'docs/release-policy.json')
    parser.add_argument('--kind', choices=('apt', 'arch', 'gentoo'))
    args = parser.parse_args(argv); value = configuration(release.archive.read_json(args.config))
    if args.operation == 'refresh': result = refresh(value, args.policy)
    elif args.operation == 'install-portage': result = install_portage(args.config)
    else:
        if not args.kind: parser.error('--kind required')
        print(native_config(value, args.kind, Path(__file__), args.config), end=''); return
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('distribution client: '+str(error)+'; preserve current state')
