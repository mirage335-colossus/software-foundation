#!/usr/bin/env python3
"""Native package-manager acceptance of exact, signed, already-built release bytes."""
import argparse
import io
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid

import process_tree
from release_check import qualification_work

import distribution_release as release
import distro_client as client

IMAGES = {'apt-bookworm': ('apt', 'debian:bookworm'), 'apt-trixie': ('apt', 'debian:trixie'),
          'apt-ubuntu': ('apt', 'ubuntu:24.04'), 'arch': ('arch', 'archlinux:base'),
          'gentoo': ('gentoo', 'gentoo/stage3:latest')}


def matrix(target):
    if target not in release.TARGETS: raise ValueError('unsupported distribution target')
    # Official Arch Linux and the example Portage image are qualified on x86-64.
    names = list(IMAGES) if target == 'linux-x86_64' else ['apt-bookworm', 'apt-trixie', 'apt-ubuntu']
    return {'include': [dict(id=name, kind=IMAGES[name][0], image=IMAGES[name][1], target=target,
        runner='ubuntu-24.04' if target == 'linux-x86_64' else 'ubuntu-24.04-arm') for name in names]}


def extract_channels(assets, output):
    channels = release.archive.extract(Path(assets)/'channels.tar.gz', output, max_bytes=release.distro.MAX_BYTES*2)
    # Only the fresh owned extraction is normalized. Payload file modes remain
    # authenticated by the signed channel and its native package inventories.
    channels.chmod(0o755)
    for path in channels.rglob('*'):
        if path.is_dir(): path.chmod(0o755)
    return channels


def expected_payload(channels, manifest, backend, kind):
    if kind == 'apt':
        metadata = release.archive.read_json(channels/'apt/repository.json')
        rows = [release.archive.read_json(channels/'apt'/row['receipt']) for row in metadata['packages']]
        matches = [row for row in rows if row['backend'] == backend]
        if len(matches) != 1: raise ValueError('one exact APT backend receipt required')
        return matches[0]['payload']
    spec = manifest['specifications'][backend]
    group = channels/'native/packages'/(spec['architecture']+'-'+backend)
    generated, _ = release.distro.expected_package(release.distro.tree(group))
    packages = [value[0] for name, value in generated.items() if name.startswith('arch/') and name.endswith('.pkg.tar.gz')]
    if len(packages) != 1: raise ValueError('one exact native package required')
    expected = {}
    with tarfile.open(fileobj=io.BytesIO(packages[0]), mode='r:gz') as bundle:
        for entry in bundle:
            if not entry.isfile() or entry.name.startswith('.'): continue
            # Gentoo supplies license acceptance through the authenticated overlay;
            # private notices and every public launcher/manual remain mandatory.
            if kind == 'gentoo' and entry.name.startswith('usr/share/licenses/'): continue
            with bundle.extractfile(entry) as stream: data = stream.read()
            expected[entry.name] = {'sha256': release.distro.digest(data), 'size': len(data), 'mode': entry.mode}
    return expected


def verify_installed(root, expected, backend):
    root = Path(root)
    for name, row in expected.items():
        release.archive.relative(name); path = root/name
        data, mode = release.distro.ordinary(path)
        if {'sha256': release.distro.digest(data), 'size': len(data), 'mode': mode} != row:
            raise ValueError('installed payload differs: '+name)
    private = root/'opt/software-foundation'/backend
    actual = {path.relative_to(root).as_posix() for path in private.rglob('*') if path.is_file() or path.is_symlink()}
    declared = {name for name in expected if name.startswith('opt/software-foundation/'+backend+'/')}
    if actual != declared: raise ValueError('installed private tree contains missing or foreign files')
    return len(expected)


def supervised(argv, stream, *, timeout, env=None):
    """Do not release an evidence stream while command descendants can write."""
    owner = process_tree.launch(argv, Path.cwd(), stream, env=env)
    try:
        status = owner.wait(timeout=timeout)
        owner.finish()
        if status: raise subprocess.CalledProcessError(status, argv)
    finally:
        owner.close()


def image_identity(raw):
    values = release.delivery.parse(raw)
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise ValueError('one exact inspected container image required')
    value = values[0].get('Id', '')
    if not value.startswith('sha256:') or not release.delivery.SHA.fullmatch(value[7:]):
        raise ValueError('invalid inspected container image identity')
    return value


def remove_owned_container(name, token):
    """Stop only the uniquely named, labeled container created by this invocation."""
    ids = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'name=^/'+name+'$'], text=True).split()
    if not ids: return
    if len(ids) != 1: raise ValueError('ambiguous owned container; preserve evidence')
    info = release.delivery.parse(subprocess.check_output(['docker', 'inspect', ids[0]], text=True))
    if (len(info) != 1 or info[0].get('Name') != '/'+name or
            info[0].get('Config', {}).get('Labels', {}).get('foundation.native-check') != token):
        raise ValueError('container ownership changed; preserve it')
    subprocess.run(['docker', 'rm', '--force', '--volumes', ids[0]], check=True, timeout=60)


def require_version_upgrade(previous, candidate):
    client.advance(previous, candidate)
    if previous['request']['sequence'] >= candidate['request']['sequence']:
        raise ValueError('upgrade requires an older exact published channel')
    if any(release.distro.version_key(candidate['specifications'][backend]) <=
           release.distro.version_key(spec)
           for backend, spec in previous['specifications'].items()):
        raise ValueError('upgrade requires a newer package version or package release for every existing backend')


def native(directory, policy, trusted, kind, evidence, *, previous=None):
    if (not hasattr(os, 'geteuid') or os.geteuid() != 0 or not Path('/.dockerenv').is_file() or
            os.environ.get('FOUNDATION_DISPOSABLE_CHECK') != '1'):
        raise ValueError('native package installation requires an explicitly disposable root container')
    if kind not in ('apt', 'arch', 'gentoo'): raise ValueError('unknown package frontend')
    manifest = release.verify(directory, policy, trusted)
    target = manifest['request']['target']
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
    if target != 'linux-'+machine: raise ValueError('native package target differs from execution processor')
    if kind != 'apt' and target != 'linux-x86_64': raise ValueError('this native frontend image is qualified only on x86-64')
    evidence = Path(evidence); evidence.mkdir(parents=True, exist_ok=False)
    commands = []
    def run(*argv):
        commands.append([str(arg) for arg in argv])
        with (evidence/'native.log').open('ab') as stream:
            stream.write(('COMMAND '+json.dumps(commands[-1])+'\n').encode()); stream.flush()
            supervised(commands[-1], stream, timeout=900,
                env=dict(os.environ, DEBIAN_FRONTEND='noninteractive', LC_ALL='C.UTF-8'))
    with qualification_work(evidence) as work:
        rounds = []
        if previous:
            old = release.verify(previous, policy, trusted); require_version_upgrade(old, manifest)
            rounds.append((Path(previous), old))
        rounds.append((Path(directory), manifest)); installed = []
        for index, (assets, value) in enumerate(rounds):
            channels = extract_channels(assets, work/('channels-'+str(index)))
            url = release.base_url(value['request']); backends = value['backends']
            if kind == 'apt':
                key = Path('/etc/apt/keyrings/software-foundation.gpg'); key.parent.mkdir(exist_ok=True)
                shutil.copyfile(assets/'archive-keyring.gpg', key); key.chmod(0o644)
                Path('/etc/apt/sources.list.d/software-foundation.sources').write_text(
                    f'Types: deb\nURIs: {url}\nSuites: ./\nArchitectures: {release.TARGETS[target][1]}\nSigned-By: {key}\n')
                run('apt-get', 'update')
                names = ['software-foundation-'+backend+'='+value['request']['version']+'+r'+str(value['request']['package_release']) for backend in backends]
                run('apt-get', 'install', '-y', '--no-install-recommends', *names)
                run('apt-get', 'update'); run('apt-get', 'install', '-y', '--no-install-recommends', *names)
            elif kind == 'arch':
                if index == 0:
                    run('pacman-key', '--init'); run('pacman-key', '--add', assets/'archive-keyring.gpg')
                    run('pacman-key', '--lsign-key', trusted)
                    with Path('/etc/pacman.conf').open('a') as out:
                        out.write('\n[options]\nNoExtract = !usr/share/man !usr/share/man/ !usr/share/man/man1 !usr/share/man/man1/ !usr/share/man/man7 !usr/share/man/man7/ !usr/share/man/man1/foundation-* !usr/share/man/man7/software-foundation-*\nInclude = /etc/pacman.d/software-foundation.conf\n')
                Path('/etc/pacman.d/software-foundation.conf').write_text(f'[software-foundation]\nSigLevel = Required DatabaseRequired\nServer = {url.rstrip("/")}\n')
                names = ['software-foundation-'+backend+'-bin' for backend in backends]
                run('pacman', '-Syu', '--noconfirm', *names); run('pacman', '-Syu', '--noconfirm')
                for name in names: run('pacman', '-Qkk', name)
            else:
                # The signed recipes only wrap the retained archive; missing host
                # prerequisites must come from binary repositories, never compilation.
                config = dict(schema_version=1, repository=value['request']['repository'], target=target,
                    trusted_fingerprint=trusted, policy_sha256=release.archive.digest(policy),
                    selection={'tag': value['tag'], 'manifest_sha256': release.archive.digest(assets/'distribution.json')},
                    location='/var/lib/software-foundation-channel')
                config_path = Path('/etc/software-foundation-channel.json')
                config_path.write_bytes(release.archive.encoded(config))
                client.refresh(config, policy, prepared=assets)
                client.install_portage(config_path, Path(client.__file__))
                run('emaint', 'sync', '-r', 'software-foundation-bin')
                overlay = Path(config['location'])/'current/channels/native/gentoo'
                for folder in ('package.accept_keywords', 'package.license'): (Path('/etc/portage')/folder).mkdir(exist_ok=True)
                Path('/etc/portage/package.accept_keywords/software-foundation').write_text('app-misc/software-foundation-* ~amd64\n')
                Path('/etc/portage/package.license/software-foundation').write_text('app-misc/software-foundation-* Foundation-Bundled-*\n')
                # Disable only package-byte transformations in this disposable host.
                os.environ['FEATURES'] = subprocess.check_output(['portageq', 'envvar', 'FEATURES'], text=True).strip()+' -compressdebug'
                for backend in backends:
                    files = list((overlay/'app-misc'/('software-foundation-'+backend+'-bin')).glob('*.ebuild'))
                    if len(files) != 1: raise ValueError('one exact binary ebuild required')
                    run('ebuild', files[0], 'package')
                    run('emerge', '--getbinpkgonly', '--usepkgonly', '--binpkg-respect-use=y', '--oneshot', '--with-bdeps=n', '='+ 'app-misc/'+files[0].stem)
                    run('portageq', 'has_version', '/', '=app-misc/'+files[0].stem)
                run('emaint', 'sync', '-r', 'software-foundation-bin')
            installed = []
            for backend in backends:
                expected = expected_payload(channels, value, backend, kind)
                count = verify_installed('/', expected, backend)
                executable = 'foundation-cli'+('-'+backend if backend != 'core' else '')
                run(executable, '--self-check')
                if backend != 'core': run('xvfb-run', '-a', 'foundation-gui-'+('web' if backend == 'hosted-web' else backend), '--self-check')
                installed.append({'backend': backend, 'files': count, 'payload_sha256': release.distro.digest(release.distro.encoded(expected))})
        names = ['software-foundation-'+backend+('' if kind == 'apt' else '-bin') for backend in manifest['backends']]
        if kind == 'apt': run('apt-get', 'purge', '-y', *names)
        elif kind == 'arch': run('pacman', '-R', '--noconfirm', *names)
        else: run('emerge', '--unmerge', *('app-misc/'+name for name in names))
        for backend in manifest['backends']:
            private = Path('/opt/software-foundation')/backend
            if private.exists() and any(private.rglob('*')): raise ValueError('private files remain after removal')
    result = dict(schema_version=1, status='passed', kind=kind, target=target, tag=manifest['tag'],
        manifest_sha256=release.archive.digest(Path(directory)/'distribution.json'),
        checks=['signature', 'published-download', 'install', 'repeated-update', 'exact-payload', 'self-check', 'remove'],
        upgrade_from=rounds[0][1]['tag'] if len(rounds) == 2 else None, backends=installed,
        id=os.environ.get('CHECK_ID'), image=os.environ.get('CHECK_IMAGE'), image_id=os.environ.get('CHECK_IMAGE_ID'),
        os_release=Path('/etc/os-release').read_text(),
        source_commit=os.environ.get('GITHUB_SHA'), run_id=os.environ.get('GITHUB_RUN_ID'),
        attempt=os.environ.get('GITHUB_RUN_ATTEMPT'), commands=commands)
    release.archive.write_json(evidence/'result.json', result)
    return result


def selection(raw):
    if not isinstance(raw, str) or len(raw.encode()) > 16384: raise ValueError('bounded exact channel selection required')
    value = release.delivery.parse(raw)
    if not isinstance(value, dict) or set(value) != {'tag', 'manifest_sha256', 'target'}:
        raise ValueError('exact channel tag, manifest digest and target required')
    release.delivery.valid_name(value['tag'])
    if value['target'] not in release.TARGETS or not release.delivery.SHA.fullmatch(str(value['manifest_sha256'])):
        raise ValueError('invalid channel target or digest')
    return value


def container(root, check_id, environment):
    root = Path(root).resolve(strict=True); selected = selection(environment['CHANNEL'])
    rows = [row for row in matrix(selected['target'])['include'] if row['id'] == check_id]
    if len(rows) != 1: raise ValueError('native check is not in selected matrix')
    row = rows[0]
    if environment.get('CHECK_IMAGE') != row['image'] or environment.get('CHECK_KIND') != row['kind']:
        raise ValueError('native execution image or kind differs from plan')
    if ':' in str(root): raise ValueError('unsupported container source path')
    output = root/'build/distro-evidence'; output.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex
    name = 'foundation-native-'+token; snapshot_name = name+'-snapshot'
    args = ['docker', 'create', '--name', name, '--label', 'foundation.native-check='+token, '--init', '-e', 'FOUNDATION_DISPOSABLE_CHECK=1',
        '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONUTF8=1', '-e', 'TRUSTED_FINGERPRINT',
        '-e', 'GITHUB_SHA', '-e', 'GITHUB_RUN_ID', '-e', 'GITHUB_RUN_ATTEMPT', '-e', 'CHECK_ID', '-e', 'CHECK_IMAGE',
        '--mount', f'type=bind,source={root},target=/source,readonly',
        '--mount', f'type=bind,source={output},target=/evidence', '-w', '/source']
    commands = {
        'apt': 'apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 gnupg gpgv dpkg-dev binutils xvfb xauth libgl1 libopengl0 libgl1-mesa-dri',
        'arch': 'pacman -Syu --noconfirm --needed python gnupg binutils xorg-server-xvfb xorg-xauth mesa libglvnd',
        'gentoo': 'emerge --getbinpkgonly --usepkgonly --binpkg-respect-use=y --oneshot --with-bdeps=n app-crypt/gnupg x11-base/xorg-server x11-apps/xauth media-libs/mesa media-libs/libglvnd'
    }
    snapshot = None
    try:
        subprocess.run(['docker', 'pull', row['image']], check=True)
        image = subprocess.check_output(['docker', 'image', 'inspect', row['image']], text=True)
        image_id = image_identity(image)
        (output/'image.json').write_text(image)
        args += ['-e', 'CHECK_IMAGE_ID='+image_id]
        if row['kind'] == 'gentoo':
            subprocess.run(['docker', 'pull', 'gentoo/portage:latest'], check=True)
            snapshot_image = subprocess.check_output(['docker', 'image', 'inspect', 'gentoo/portage:latest'], text=True)
            (output/'portage-image.json').write_text(snapshot_image)
            snapshot = subprocess.check_output(['docker', 'create', '--name', snapshot_name, '--label', 'foundation.native-check='+token, '-v', '/var/db/repos/gentoo', image_identity(snapshot_image), '/bin/true'], text=True).strip()
            if not snapshot or any(c not in '0123456789abcdef' for c in snapshot): raise ValueError('invalid disposable snapshot identity')
            args += ['--volumes-from', snapshot+':ro']
        script = commands[row['kind']] + '\nexec python3 -B tools/distro_check.py native --directory /source/build/channels/current --policy /source/docs/release-policy.json --trusted-fingerprint "$TRUSTED_FINGERPRINT" --kind '+row['kind']+' --evidence /evidence/native'
        if environment.get('PREVIOUS'): script += ' --previous /source/build/channels/previous'
        with (output/'container.log').open('wb') as stream:
            supervised([*args, image_id, 'bash', '-euc', script], stream, timeout=120)
            supervised(['docker', 'start', '--attach', name], stream, timeout=4500)
    finally:
        errors = []
        for owned in (name, snapshot_name):
            try: remove_owned_container(owned, token)
            except Exception as error: errors.append(str(error))
        if errors: raise RuntimeError('container cleanup is uncertain: '+'; '.join(errors))
        # Confirm server-side writers stopped before reassigning the evidence mount.
        if output.exists():
            subprocess.run(['sudo', 'chown', '-R', str(os.getuid())+':'+str(os.getgid()), str(output)], check=True)


def qualification(selected, records, environment):
    expected = matrix(selected['target'])['include']; by_id = {}
    required = {'signature', 'published-download', 'install', 'repeated-update', 'exact-payload', 'self-check', 'remove'}
    for record in records:
        name = record.get('id')
        if name in by_id: raise ValueError('duplicate native result')
        by_id[name] = record
    if set(by_id) != {row['id'] for row in expected}: raise ValueError('missing or foreign native result')
    for row in expected:
        result = by_id[row['id']]
        if (result.get('status') != 'passed' or result.get('schema_version') != 1 or result.get('target') != selected['target'] or
                result.get('kind') != row['kind'] or result.get('image') != row['image'] or result.get('tag') != selected['tag'] or
                result.get('manifest_sha256') != selected['manifest_sha256'] or set(result.get('checks', [])) != required or
                result.get('source_commit') != environment['GITHUB_SHA'] or result.get('run_id') != environment['GITHUB_RUN_ID'] or
                result.get('attempt') != environment['GITHUB_RUN_ATTEMPT'] or not result.get('backends') or not result.get('commands') or
                not isinstance(result.get('image_id'), str) or not result['image_id'].startswith('sha256:') or
                not release.delivery.SHA.fullmatch(result['image_id'][7:])):
            raise ValueError('native result scope or execution identity differs')
    return dict(schema_version=1, target=selected['target'], source_commit=environment['GITHUB_SHA'],
        run_id=int(environment['GITHUB_RUN_ID']), attempt=int(environment['GITHUB_RUN_ATTEMPT']),
        checks={name:release.distro.digest(release.distro.encoded(result)) for name,result in sorted(by_id.items())})


def validate_payload_evidence(channels, value, result):
    backends = result['backends']
    if ({item['backend'] for item in backends} != set(value['backends']) or len(backends) != len(value['backends'])):
        raise ValueError('native result does not cover every packaged backend')
    for item in backends:
        expected = expected_payload(channels, value, item['backend'], result['kind'])
        if item != dict(backend=item['backend'], files=len(expected), payload_sha256=release.distro.digest(release.distro.encoded(expected))):
            raise ValueError('native payload evidence differs from exact signed channel')


def accept(selected, records, environment, output):
    """Called after verified successful workflow bundles, under publication ownership."""
    marker = qualification(selected, records, environment)
    value = release.fetch(environment['GITHUB_REPOSITORY'], selected['tag'], selected['manifest_sha256'],
        output, release.ROOT/'docs/release-policy.json', environment['TRUSTED_FINGERPRINT'])
    if value['request']['target'] != selected['target']: raise ValueError('qualified channel target differs')
    with tempfile.TemporaryDirectory(prefix='foundation-accept-') as temporary:
        channels = extract_channels(output, Path(temporary)/'channels')
        for result in records:
            validate_payload_evidence(channels, value, result)
    remote = release.delivery.Remote(environment['GITHUB_REPOSITORY'])
    def mutation():
        info = remote.find(selected['tag']); assets = remote.assets(info)
        body = release.delivery.parse(info.get('body', ''))
        base = {'kind': 'signed-distribution', 'manifest_sha256': selected['manifest_sha256']}
        desired = dict(base, native_qualification=marker)
        if info['draft'] or body not in (base, desired): raise ValueError('unexpected channel lifecycle; preserve it')
        expected = {p.name: release.asset_info(p) for p in Path(output).iterdir()}
        if set(assets) != set(expected) or any(assets[name]['digest'] != 'sha256:'+item['sha256'] or assets[name]['size'] != item['size'] for name,item in expected.items()):
            raise ValueError('native checked remote assets changed')
        remote.unchanged(selected['tag'], info, assets, value['request']['packager_commit'])
        if body != desired or info['prerelease']:
            remote.change('/releases/'+str(info['id']), method='PATCH', body={
                'body': json.dumps(desired, sort_keys=True), 'prerelease': False, 'make_latest': 'false'})
        final = remote.find(selected['tag'])
        if final['id'] != info['id'] or final['draft'] or final['prerelease'] or remote.assets(final) != assets or release.delivery.parse(final['body']) != desired:
            raise ValueError('native channel acceptance outcome differs; inspect remote state')
        remote.not_latest(final)
        return desired
    return release.delivery.run_mutation(remote, mutation)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=('plan', 'native'))
    p.add_argument('--target'); p.add_argument('--directory', type=Path); p.add_argument('--previous', type=Path)
    p.add_argument('--policy', type=Path); p.add_argument('--trusted-fingerprint'); p.add_argument('--kind'); p.add_argument('--evidence', type=Path)
    a = p.parse_args(argv)
    if a.operation == 'plan': result = matrix(a.target)
    else:
        if not all((a.directory, a.policy, a.trusted_fingerprint, a.kind, a.evidence)): p.error('complete native inputs required')
        result = native(a.directory, a.policy, a.trusted_fingerprint, a.kind, a.evidence, previous=a.previous)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__': main()
