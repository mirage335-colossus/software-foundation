#!/usr/bin/env python3
"""Disposable Linux jobs with host-owned outputs and explicit privilege boundaries."""
import argparse
from contextlib import contextmanager
import uuid
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = ('sdk-produce', 'application-build', 'native-gui-check', 'check', 'apt-native-smoke')
IMAGES = ('debian:bookworm', 'debian:trixie', 'ubuntu:24.04')
ENVIRONMENT = ('SDK_PROFILE', 'PROFILE', 'JOBS', 'TARGET', 'RECIPE', 'GITHUB_REPOSITORY', 'GITHUB_SHA',
               'CHECK', 'CHECK_IMAGE', 'CHECK_BROWSER', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'SDK_DEVELOPMENT',
               'CORE_PROVIDER', 'FOUNDATION_PROVIDER_RECIPE')
COMMON = 'ca-certificates python3 git file binutils gnupg openssl curl xz-utils unzip xvfb xauth fonts-dejavu-core'.split()
# Full source suites verify the offline namespace adapter against the real ip tool.
BUILD = 'build-essential cmake ninja-build cpio rsync wget patch bc bzip2 perl gawk libncurses-dev dpkg-dev apt-utils nodejs iproute2'.split()
GUI_RUNTIME = ('libgl1 libopengl0 libgl1-mesa-dri libegl1 libx11-6 libxext6 libxft2 libxinerama1 '
               'libxcursor1 libxrender1 libxfixes3 libxrandr2 libice6 libsm6 libxdamage1 libxxf86vm1 '
               'libwayland-client0 libwayland-cursor0 libwayland-egl1 libxkbcommon0 libdbus-1-3 libibus-1.0-5').split()
GUI_BUILD = ('libx11-dev libxext-dev libxft-dev libxinerama-dev libxcursor-dev libxrender-dev libxfixes-dev '
             'libwayland-dev libxkbcommon-dev libegl1-mesa-dev libdbus-1-dev libibus-1.0-dev').split()


def packages(action, environment, item=None):
    if action not in ACTIONS: raise ValueError('unsupported disposable container operation')
    selected = list(COMMON)
    if action in ('sdk-produce', 'application-build', 'native-gui-check', 'apt-native-smoke') or item and item['scope'] in ('source', 'recovery'):
        selected += BUILD
    gui = action == 'native-gui-check' or environment.get('SDK_PROFILE' if action == 'sdk-produce' else 'PROFILE') == 'all-gui'
    if gui or action == 'check' and item and item['backend'] != 'core': selected += GUI_RUNTIME
    if action == 'sdk-produce' and gui: selected += GUI_BUILD
    return tuple(dict.fromkeys(selected))


def bootstrap_script(selected):
    return 'sh tools/ci-apt.sh install ' + ' '.join(selected)


@contextmanager
def prepared_checks(root, image, items, environment):
    """Bootstrap once, then fork a fresh package database and account per case.

    The committed layer contains setup only: no case, builder account, browser
    receipt or host bind-mount bytes. It is private to this batch and removed
    after every child process and output stream has finished.
    """
    if image not in IMAGES: raise ValueError('unsupported disposable container image')
    root = Path(root).resolve(strict=True)
    if ':' in str(root) or '\n' in str(root): raise ValueError('unsupported bind mount path')
    selected = tuple(dict.fromkeys(name for item in items for name in packages('check', environment, item)))
    name = 'foundation-check-setup-' + uuid.uuid4().hex
    identity = None; created = False
    try:
        subprocess.run(['docker', 'create', '--name', name, '-v', str(root) + ':/work:ro', '-w', '/work',
                        image, 'bash', '-euc', bootstrap_script(selected)], check=True)
        created = True
        subprocess.run(['docker', 'start', '--attach', name], check=True)
        result = subprocess.run(['docker', 'commit', name], check=True, capture_output=True, text=True)
        identity = result.stdout.strip()
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', identity):
            raise ValueError('bootstrap commit did not return an immutable image ID')
        yield identity
    finally:
        # Synchronous Docker subprocesses are joined before resource cleanup.
        if created: subprocess.run(['docker', 'rm', name], check=True)
        if identity and re.fullmatch(r'sha256:[0-9a-f]{64}', identity):
            subprocess.run(['docker', 'image', 'rm', identity], check=True)


def account_id(value):
    if type(value) is not int or not 0 < value < 2 ** 31:
        raise ValueError('a non-root numeric host user/group ID is required')
    return value


def command(action, root, uid, gid, environment, *, prepared_image=None):
    if action not in ACTIONS:
        raise ValueError('unsupported disposable container operation')
    uid, gid = account_id(uid), account_id(gid)
    image = environment.get('CHECK_IMAGE') if action == 'check' else 'debian:bookworm'
    if image not in IMAGES:
        raise ValueError('unsupported disposable container image')
    root = Path(root).resolve(strict=True)
    if ':' in str(root) or '\n' in str(root):
        raise ValueError('unsupported bind mount path')
    if prepared_image is not None and (action != 'check' or not re.fullmatch(r'sha256:[0-9a-f]{64}', prepared_image)):
        raise ValueError('only checks may use an immutable batch bootstrap image')
    item = selection(root, environment) if action == 'check' else None
    script = '' if prepared_image else bootstrap_script(packages(action, environment, item)) + '; '
    argv = ['docker', 'run', '--rm']
    for name in ENVIRONMENT:
        if name in environment:
            argv += ['-e', name]
    argv += ['-e', 'FOUNDATION_HOST_UID=' + str(uid), '-e', 'FOUNDATION_HOST_GID=' + str(gid),
             '-e', 'FOUNDATION_DISPOSABLE_CHECK=1', '-e', 'PYTHONUTF8=1', '-e', 'PYTHONDONTWRITEBYTECODE=1',
             '-v', str(root) + ':/work', '-w', '/work', prepared_image or image, 'bash', '-euc',
             script + 'exec python3 -B .github/scripts/container_job.py --inside "$1"', 'container-job', action]
    return argv


def offline_restored_sdk(output, name, manifest):
    root = output / name
    receipt = root / manifest
    if (root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != output / name
            or receipt.is_symlink() or not receipt.is_file()):
        raise ValueError('offline execution requires an ordinary completed SDK restoration: ' + name)
    return root


def offline_command(source, output, group, uid, gid, image, phase, *, target, rust_group=None):
    """Consume a locally prepared immutable image without package setup/pulling.

    Restoration and execution use separate fresh containers with identical
    disconnected policy. The restored SDK becomes a read-only input to execution.
    Only the source snapshot, exact retained groups and owned output are exposed.
    """
    uid, gid = account_id(uid), account_id(gid)
    if (not re.fullmatch(r'sha256:[0-9a-f]{64}', image) or phase not in ('stage', 'execute')
            or target not in ('linux-x86_64', 'linux-aarch64', 'browser-wasm32')):
        raise ValueError('offline acceptance needs an immutable image and explicit phase')
    inputs = (source, output, group)
    if rust_group is not None:
        rust_group = Path(rust_group)
        if rust_group.is_symlink() or not rust_group.is_dir() or rust_group.resolve(strict=True) != rust_group:
            raise ValueError('retained Rust group must be an ordinary canonical directory')
        inputs += (rust_group,)
    paths = [Path(path).resolve(strict=True) for path in inputs]
    if any(any(character in str(path) for character in (',', '\n', '\0')) for path in paths):
        raise ValueError('unsupported offline bind mount path')
    source, output, group = paths[:3]
    argv = ['docker', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user', f'{uid}:{gid}',
            '--tmpfs', '/tmp:rw,nosuid,nodev,mode=1777', '-w', '/work']
    prefix = 'stage-' if phase == 'stage' else ''
    display = phase == 'execute' and target.startswith('linux-')
    if display:
        # Xvfb's readiness handshake requires its xvfb-run parent to be non-PID1.
        argv += ['--init']
    for name, value in {'HOME': '/output/' + prefix + 'home', 'TMPDIR': '/output/' + prefix + 'tmp', 'XDG_CACHE_HOME': '/output/' + prefix + 'cache',
                        'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                        'CCACHE_DISABLE': '1', 'CCACHE_DIR': '/output/' + prefix + 'cache/ccache', 'LIBGL_ALWAYS_SOFTWARE': '1'}.items():
        argv += ['-e', name + '=' + ('/tmp' if name == 'TMPDIR' and display else value)]
    for path, destination, readonly in ((source, '/work', True), (output, '/output', False), (group, '/inputs/group', True)):
        argv += ['--mount', f'type=bind,source={path},target={destination}' + (',readonly' if readonly else '')]
    if rust_group is not None:
        argv += ['--mount', f'type=bind,source={rust_group},target=/inputs/rust-group,readonly']
    if phase == 'execute':
        sdk = offline_restored_sdk(output, 'sdk', 'sdk.json')
        argv += ['--mount', f'type=bind,source={sdk},target=/output/sdk,readonly']
        if rust_group is not None:
            rust_sdk = offline_restored_sdk(output, 'rust-sdk', 'rust-sdk.json')
            argv += ['--mount', f'type=bind,source={rust_sdk},target=/output/rust-sdk,readonly']
    inner = ['python3', '-B', '/work/tools/offline_acceptance.py', '--inside', phase, '--request', '/output/request.json']
    argv += [image, *(['xvfb-run', '-a', 'env', 'TMPDIR=/output/tmp'] if display else []), *inner]
    return argv


def create_account(uid, gid):
    # Conflicting preexisting users fail; never change an unrelated account.
    for identity in (str(uid), 'sdkbuilder'):
        result = subprocess.run(['getent', 'passwd', identity], capture_output=True)
        if result.returncode != 2:
            raise ValueError('container builder account or UID already exists, or lookup failed')
    result = subprocess.run(['getent', 'group', str(gid)], capture_output=True)
    if result.returncode == 2:
        subprocess.run(['groupadd', '--gid', str(gid), 'sdkbuilder'], check=True)
    elif result.returncode != 0:
        raise ValueError('container group lookup failed')
    subprocess.run(['useradd', '--create-home', '--uid', str(uid), '--gid', str(gid), 'sdkbuilder'], check=True)


def selection(root, environment):
    sys.path.insert(0, str(root / 'tools'))
    import coverage as evidence
    plan = evidence.load(root / 'build/check-plan.json')
    evidence.validate(plan)
    selected = [item for item in plan['checks'] if item['id'] == environment.get('CHECK')]
    if len(selected) != 1 or not re.fullmatch(r'[A-Za-z0-9._-]+', selected[0]['id']):
        raise ValueError('check not in frozen inventory')
    return selected[0]


def output_roots(action, item=None):
    if action == 'apt-native-smoke':
        return ('build/apt-evidence',)
    if action == 'check':
        return ('build/evidence/' + item['id'], 'build/prerequisites/' + item['id'])
    return ()


def handoff(root, names, uid, gid):
    """Transfer only ordinary evidence entries; preserve bytes and permission bits."""
    root = Path(root).resolve(strict=True)
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'build':
            raise ValueError('ownership handoff must name explicit build evidence roots')
        directory = root / relative
        current = root
        parents = []
        for part in relative.parts:
            current = current / part
            if not current.exists() and not current.is_symlink():
                break
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise ValueError('evidence directory is not an ordinary contained directory')
            parents.append((current, (info.st_dev, info.st_ino, info.st_mode)))
        if not directory.exists():
            continue
        # Transfer directory nodes on the evidence path too: a root umask of
        # 077 must not prevent the ordinary owner from reaching its own receipt.
        entries = parents
        for parent, directories, files in os.walk(directory, followlinks=False):
            for child in [Path(parent), *[Path(parent) / value for value in directories + files]]:
                info = child.lstat()
                if (not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
                        or stat.S_ISREG(info.st_mode) and info.st_nlink != 1):
                    raise ValueError('ownership handoff rejects links and special evidence entries')
                entries.append((child, (info.st_dev, info.st_ino, info.st_mode)))
        for path, identity in entries:
            before = path.lstat()
            if (before.st_dev, before.st_ino, before.st_mode) != identity:
                raise ValueError('evidence entry changed before ownership handoff')
            os.chown(path, uid, gid, follow_symlinks=False)
            if stat.S_IMODE(path.lstat().st_mode) != stat.S_IMODE(identity[2]):
                raise ValueError('ownership handoff changed evidence permission bits')


def inside(action, root=ROOT, environment=None):
    environment = os.environ if environment is None else environment
    if (action not in ACTIONS or not hasattr(os, 'geteuid') or os.geteuid() != 0
            or environment.get('FOUNDATION_DISPOSABLE_CHECK') != '1' or not Path('/.dockerenv').is_file()):
        raise ValueError('bootstrap requires an explicitly disposable root Docker runtime')
    uid = account_id(int(environment['FOUNDATION_HOST_UID']))
    gid = account_id(int(environment['FOUNDATION_HOST_GID']))
    root = Path(root).resolve(strict=True)
    create_account(uid, gid)
    lifecycle = [sys.executable, '-B', str(root / '.github/scripts/lifecycle.py')]
    item = selection(root, environment) if action == 'check' else None
    roots = output_roots(action, item)
    privileged = action == 'apt-native-smoke' or action == 'check' and item['scope'] == 'apt'
    try:
        if action == 'check':
            subprocess.run([*lifecycle, 'check-prerequisites'], cwd=root, check=True)
            # Root setup writes a receipt; the ordinary user must read it and
            # the host uploader must retain it, even when later assertions fail.
            handoff(root, ('build/prerequisites/' + item['id'],), uid, gid)
        if privileged:
            subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', str(root)], check=True)
            subprocess.run(['xvfb-run', '-a', *lifecycle, action], cwd=root, check=True)
        else:
            subprocess.run(['runuser', '-u', 'sdkbuilder', '--', 'xvfb-run', '-a', *lifecycle, action],
                           cwd=root, check=True)
    finally:
        # Root-only package-manager scopes also leave private 0600 receipts.
        # No source, SDK, dependency or archive tree is recursively reassigned.
        handoff(root, roots, uid, gid)


def diagnostic(error):
    messages, seen = [], set()
    while error is not None and id(error) not in seen and len(messages) < 8:
        seen.add(id(error)); messages.append(str(error))
        error = error.__cause__ or error.__context__
    return ' / caused by: '.join(messages)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--prepared-image')
    parser.add_argument('action', choices=ACTIONS)
    args = parser.parse_args(argv)
    if args.inside:
        if args.prepared_image is not None: raise ValueError('bootstrap image selection belongs to the host launcher')
        inside(args.action)
    else:
        if not hasattr(os, 'getuid') or not hasattr(os, 'getgid'):
            raise ValueError('container launcher requires a Linux host')
        subprocess.run(command(args.action, ROOT, os.getuid(), os.getgid(), os.environ, prepared_image=args.prepared_image), check=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('container job: ' + diagnostic(error), file=sys.stderr)
        sys.exit(1)
