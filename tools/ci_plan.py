#!/usr/bin/env python3
"""Checked CI scheduling and package operations shared with local development."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STANDARD = {"linux-x86_64": "ubuntu-24.04", "linux-aarch64": "ubuntu-24.04-arm",
            "windows-x86_64": "windows-2022"}


def plan(devfast=False, include_arm=True, pool="standard", configured=""):
    if pool not in ("standard", "faster"):
        raise ValueError("unknown runner pool")
    if pool == "faster" and not re.fullmatch(r"foundation-linux-[a-z0-9-]+", configured):
        raise ValueError("explicit authorized larger-runner label required")
    targets = [x for x in STANDARD if include_arm or x != "linux-aarch64"]
    packages, checks = [], []
    for target in targets:
        runner = configured if target == "linux-x86_64" and pool == "faster" else STANDARD[target]
        packages.append({"target": target, "runner": runner})
        for scope in (["core"] if devfast else ["core", "tools", "integration"]):
            checks.append({"target": target, "runner": runner, "scope": scope})
    return {"checks": {"include": checks}, "packages": {"include": packages}}


def assert_host(target):
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    system = platform.system().lower()
    if target != system + "-" + machine:
        raise ValueError("actual host differs from selected execution target")
    return {"target": target, "system": system, "machine": machine, "release": platform.release(),
            "python": platform.python_version()}


def run(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def archives(directory, recursive=True):
    find = directory.rglob if recursive else directory.glob
    values = sorted(list(find("*.tar.gz")) + list(find("*.zip")))
    if not values:
        raise ValueError("no application archives found")
    names = [x.name for x in values]
    if len(names) != len(set(names)):
        raise ValueError("duplicate application archive names")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--devfast", action="store_true")
    p.add_argument("--no-arm", action="store_true")
    p.add_argument("--pool", choices=("standard", "faster"), default="standard")
    p.add_argument("--configured", default="")
    p.add_argument("--github-output", type=Path)
    p = sub.add_parser("host")
    p.add_argument("target", choices=tuple(STANDARD))
    p = sub.add_parser("package")
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=2)
    p = sub.add_parser("check-archives")
    p.add_argument("directory", type=Path)
    p.add_argument("--runtime-only", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(args.devfast, not args.no_arm, args.pool, args.configured)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as out:
                for key, value in result.items():
                    out.write(key + "=" + json.dumps(value, separators=(",", ":")) + "\n")
        print(json.dumps(result, indent=2))
    elif args.command == "host":
        print(json.dumps(assert_host(args.target)))
    elif args.command == "package":
        if args.jobs < 1:
            raise ValueError("positive compile concurrency required")
        run([sys.executable, "tools/build.py", "package", "release", "--portable", "--build-dir", args.build,
             "--jobs", str(args.jobs)])
        for archive in archives(args.build / "packages", recursive=False):
            manifest = archive.with_name(archive.name + ".json")
            for operation in ("create", "verify"):
                run([sys.executable, "tools/artifact.py", operation, archive, "--manifest", manifest])
    else:
        for archive in archives(args.directory):
            run([sys.executable, "tools/artifact.py", "verify", archive,
                 "--manifest", archive.with_name(archive.name + ".json"),
                 *(["--runtime-only"] if args.runtime_only else [])])



# Lifecycle operations use the same validators as local release preparation.
def module(name):
    import importlib.util
    if str(ROOT / 'tools') not in sys.path: sys.path.insert(0, str(ROOT / 'tools'))
    spec = importlib.util.spec_from_file_location('ci_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def exact_commit(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
        raise ValueError('complete source commit required')
    return value


def release_matrix(recipes, profile='core', policy=None):
    policy = policy or module('coverage').load(ROOT / 'docs/release-policy.json')
    selected, _ = module('certify_release').requirements(policy, profile)
    if not isinstance(recipes, dict) or set(recipes) != set(selected['targets']):
        raise ValueError('recipe map must cover exactly the selected target inventory')
    if any(not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v) for v in recipes.values()):
        raise ValueError('every target requires its complete prepared recipe')
    if profile == 'all-gui':
        lock = module('coverage').load(ROOT / 'third_party/gui-boundary.lock.json')
        if lock.get('redistribution', {}).get('approved') is not True:
            raise ValueError('GUI redistribution licensing must be resolved before producing release assets')
    rows = []
    for target, backends in selected['targets'].items():
        if target not in (*STANDARD, 'browser-wasm32'):
            raise ValueError('no qualified runner adapter for target')
        rows.append({'target': target, 'runner': STANDARD.get(target, 'ubuntu-24.04'),
                     'recipe': recipes[target], 'backends': backends,
                     'container': 'debian:bookworm' if target.startswith('linux-') else ''})
    return {'include': rows}


def source_archive(output, gui_source=None):
    module('source_identity').archive_source(ROOT, output, gui_source)
    return {'archive': str(output), 'sha256': module('coverage').sha(output)}


def prepared_package(target, recipe, group, source, output, jobs=2, *, graphics_archive=None):
    import shutil
    from dependency_archive import extract
    from dependency_store import verify_group
    if target != 'browser-wasm32':
        assert_host(target)
    elif platform.system() != 'Linux':
        raise ValueError('prepared browser producer requires its declared Linux host')
    if graphics_archive is not None and target != 'windows-x86_64':
        raise ValueError('retained host graphics input applies only to Windows GUI production')
    if jobs < 1 or output.exists():
        raise ValueError('positive concurrency and new package output required')
    verify_group(group, recipe)
    manifest = module('source_identity').verify_source_archive(source)
    output.mkdir(parents=True)
    work = output / 'work'
    extract(source, work / 'source')
    root = work / 'source'
    build = work / 'build'
    command = [sys.executable, str(root / 'tools/build.py'), 'test', 'release', '--full',
               '--portable', '--build-dir', str(build), '--jobs', str(jobs), '--junit', str(output / 'source.junit.xml')]
    if target == 'windows-x86_64':
        version = module('windows_toolchain').inspect_selected_linker()['version']
        sdk_metadata = module('sdk_windows').install(group, recipe, work / 'dependencies', version)
        command += ['--dependency-group', str(group), '--windows-dependencies', str(work / 'dependencies')]
    else:
        sdk_metadata = module('sdk').install(group, recipe, work / 'sdk', production=True)
        command += ['--sdk', str(work / 'sdk')]
    gui = root / 'third_party/retained/gui'
    if gui.is_dir():
        backends = ['wasm'] if target == 'browser-wasm32' else ['terminal', 'framebuffer', 'fltk', 'rev', 'sdl', 'hosted-web']
        capabilities = sdk_metadata.get('capabilities', ['wasm'] if target == 'browser-wasm32' else ['core', 'terminal', 'framebuffer', 'hosted-web'])
        if not set(backends) <= set(capabilities):
            raise ValueError('prepared SDK lacks required GUI capabilities; select the explicit GUI recipe')
        command += ['--gui-source', str(gui), '--gui-backends', ','.join(backends)]
        if target != 'browser-wasm32': command += ['--host-tests']
    else:
        backends = []
        if target == 'browser-wasm32': raise ValueError('browser target requires retained GUI source')
    graphics_needed = target == 'windows-x86_64' and 'rev' in backends
    if graphics_needed != (graphics_archive is not None):
        raise ValueError('Windows GUI production requires one explicit retained host graphics archive; core must omit it')
    graphics_evidence = None
    if graphics_needed:
        module('windows_graphics').verify_archive(Path(graphics_archive))
        graphics_evidence = windows_gui_qualification(command, Path(graphics_archive), build, output, jobs,
            protected_roots=(Path(group).resolve(), root, work / 'dependencies'), cwd=root)
    else:
        subprocess.run(command, cwd=root, check=True)
    # Host DLLs must already be removed before installation or package creation.
    package_command = command.copy()
    package_command[2] = 'package'
    package_command.remove('--full')
    index = package_command.index('--junit')
    del package_command[index:index + 2]
    subprocess.run(package_command, cwd=root, check=True)
    choices = sorted((build / 'packages').glob('*.zip' if target.startswith('windows-') else '*.tar.gz'))
    if len(choices) != 1:
        raise ValueError('producer needs one exact platform archive')
    archive = output / (target + ('.tar.gz' if choices[0].name.endswith('.tar.gz') else '.zip'))
    shutil.copyfile(choices[0], archive)
    a = module('artifact')
    descriptor = archive.with_name(archive.name + '.json')
    module('coverage').write_new(descriptor, a.describe(archive))
    a.verify(archive, descriptor, sdk=work / 'sdk' if (work / 'sdk/sdk.json').is_file() else None,
             abi=target.startswith('linux-'), processor=target.split('-', 1)[1])
    if module('source_identity').source_tree(root) != manifest:
        raise ValueError('source changed during prepared application production')
    entry = {'path': str(archive.resolve()), 'sha256': module('coverage').sha(archive),
             'manifest_path': str(descriptor.resolve()), 'target': target, 'backends': backends,
             'sdk_recipe': recipe, 'dependency_recipes': [recipe]}
    if graphics_evidence is not None:
        module('coverage').write_new(output / 'graphics-qualification.json',
            {'schema_version': 1, 'status': 'passed', 'target': target, 'backends': backends,
             'archive_sha256': entry['sha256'], 'evidence': graphics_evidence})
    module('coverage').write_new(output / 'artifact.json', entry)
    return entry


def assemble_release(source, packages, base, output, profile):
    c = module('coverage')
    selected, _ = module('certify_release').requirements(c.load(ROOT / 'docs/release-policy.json'), profile)
    entries = []
    for path in sorted(packages.glob('*/artifact.json')):
        value = c.load(path)
        value['path'] = str((path.parent / Path(value['path']).name).resolve())
        value['manifest_path'] = str((path.parent / Path(value['manifest_path']).name).resolve())
        entries.append(value)
    observed = {x['target']: x['backends'] or ['core'] for x in entries}
    if len(entries) != len(observed) or observed != selected['targets']:
        raise ValueError('missing, duplicate or unexpected producer target/backend inventory')
    spec = {'schema_version': 1, 'source': {'path': str(source.resolve()), 'sha256': c.sha(source)},
            'artifacts': entries, 'required_scopes': sorted({x['scope'] for x in selected['checks']})}
    spec_path = output.parent / 'assembly.json'
    c.write_new(spec_path, spec)
    return module('release').assemble(spec_path, base, output)


def fetch_candidate(repository, tag, inventory, output, transport=None):
    import tempfile
    g = module('github_release')
    c = module('coverage')
    g.location(repository, tag)
    if not re.fullmatch(r'[0-9a-f]{64}', inventory) or output.exists() or output.is_symlink():
        raise ValueError('exact inventory digest and new candidate destination required')
    remote = g.Remote(repository, transport)
    remote.visible()
    before = remote.find(tag)
    assets = remote.assets(before)
    if 'delivery.json' not in assets:
        raise ValueError('published delivery descriptor is absent')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        staged = Path(temp)
        remote.download(assets['delivery.json'], staged / 'delivery.json')
        delivery = c.load(staged / 'delivery.json')
        if delivery.get('repository') != repository or delivery.get('tag') != tag or delivery.get('inventory_sha256') != inventory:
            raise ValueError('candidate differs from requested identity')
        if not isinstance(delivery.get('files'), dict) or not delivery['files']:
            raise ValueError('missing complete delivery file map')
        candidate = staged / 'candidate'; candidate.mkdir()
        for name, entry in delivery['files'].items():
            path = c.local(candidate, name); path.parent.mkdir(parents=True, exist_ok=True)
            remote.download(assets[entry['asset']], path, entry['sha256'])
        g.verified_remote(remote, delivery, candidate)
        remote.unchanged(tag, before, assets, delivery['tag_commit'])
        staged.rename(output)
    return delivery



MOZILLA_APT = 'https://packages.mozilla.org/apt'
MOZILLA_FINGERPRINT = '35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3'


def needs_browser_prerequisite(backend, scope):
    return backend == 'hosted-web' and scope == 'archive' or backend == 'wasm' and scope in ('source', 'recovery', 'archive')


def browser_prerequisite(target, environment, backend):
    """Select external browser test prerequisites without changing the SDK."""
    if backend not in ('hosted-web', 'wasm'):
        raise ValueError('browser setup requires a browser backend')
    systems = {'debian-12': ('debian', '12', 'debian:bookworm'),
               'debian-13': ('debian', '13', 'debian:trixie'),
               'ubuntu-24.04': ('ubuntu', '24.04', 'ubuntu:24.04')}
    if target == 'browser-wasm32' and backend == 'wasm' and environment in ('firefox', 'chromium'):
        distro, version, image = systems['debian-12']; architecture = 'amd64'; engine = environment
    elif target in ('linux-x86_64', 'linux-aarch64') and backend == 'hosted-web' and environment in systems:
        distro, version, image = systems[environment]
        architecture = 'amd64' if target == 'linux-x86_64' else 'arm64'; engine = 'firefox'
    else:
        raise ValueError('unsupported browser qualification environment')
    packages = ['firefox'] if distro == 'ubuntu' else ['firefox-esr'] if engine == 'firefox' else ['chromium', 'chromium-driver']
    return dict(distribution=distro, version=version, image=image, architecture=architecture,
                engine=engine, packages=packages, executable='/usr/bin/' + packages[0],
                repository=MOZILLA_APT if distro == 'ubuntu' else 'distribution')


def browser_setup_preflight(selection):
    """No package/configuration writes before positive disposable-host checks."""
    if (platform.system() != 'Linux' or not hasattr(os, 'geteuid') or os.geteuid() != 0 or
            os.environ.get('FOUNDATION_DISPOSABLE_CHECK') != '1' or not Path('/.dockerenv').is_file()):
        raise ValueError('browser setup requires an explicitly disposable root Docker runtime')
    actual = platform.freedesktop_os_release()
    if (actual.get('ID'), actual.get('VERSION_ID')) != (selection['distribution'], selection['version']):
        raise ValueError('actual browser runtime distribution differs from selected environment')
    if os.environ.get('CHECK_IMAGE') != selection['image']:
        raise ValueError('browser runtime image differs from selected environment')
    expected = 'linux-x86_64' if selection['architecture'] == 'amd64' else 'linux-aarch64'
    assert_host(expected)
    architecture = subprocess.run(['dpkg', '--print-architecture'], check=True, capture_output=True, text=True).stdout.strip()
    if architecture != selection['architecture']:
        raise ValueError('actual package architecture differs from selected environment')


def mozilla_key_fingerprint(listing):
    primary, pending, public_keys = [], False, 0
    for line in listing.splitlines():
        fields = line.split(':')
        if fields[0] in ('pub', 'sub'):
            pending = fields[0] == 'pub'
            public_keys += int(pending)
        elif fields[0] == 'fpr' and pending:
            primary.append(fields[9] if len(fields) > 9 else '')
            pending = False
    if public_keys != 1 or pending or primary != [MOZILLA_FINGERPRINT]:
        raise ValueError('Mozilla repository primary signing key fingerprint differs')
    return primary[0]


def mozilla_candidate(policy, madison, architecture):
    candidates = re.findall(r'^\s*Candidate: (\S+)\s*$', policy, re.MULTILINE)
    if len(candidates) != 1 or not re.fullmatch(r'[0-9][A-Za-z0-9.+:~_-]*', candidates[0]):
        raise ValueError('missing unambiguous Firefox package candidate')
    version = candidates[0]
    origins = [parts[2].split() for line in madison.splitlines()
               if len(parts := [x.strip() for x in line.split('|')]) == 3 and
               parts[0] == 'firefox' and parts[1] == version]
    if not origins or any(row != [MOZILLA_APT, 'mozilla/main', architecture, 'Packages'] for row in origins):
        raise ValueError('Firefox candidate does not come exclusively from the official Mozilla origin')
    return version


def install_browser_prerequisite(target, environment, backend, output):
    """Mutate only an explicitly disposable supported container, retaining facts."""
    import tempfile
    selection = browser_prerequisite(target, environment, backend)
    browser_setup_preflight(selection)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    def capture(argv, **kwargs):
        return subprocess.run(argv, check=True, capture_output=True, text=True,
                              env=dict(os.environ, LC_ALL='C', LANG='C'), **kwargs).stdout.strip()
    fingerprint = None; selected_version = None
    if selection['distribution'] == 'ubuntu':
        key = capture(['curl', '--fail', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                       '--connect-timeout', '15', '--max-time', '60', MOZILLA_APT + '/repo-signing-key.gpg'])
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            fingerprint = mozilla_key_fingerprint(capture(['gpg', '--no-options', '--homedir', temporary,
                '--batch', '--with-colons', '--show-keys'], input=key))
        key_path = Path('/etc/apt/keyrings/foundation-mozilla.asc')
        key_path.parent.mkdir(parents=True, exist_ok=True)
        files = {key_path: key + '\n',
                 Path('/etc/apt/sources.list.d/foundation-mozilla.list'):
                 'deb [signed-by=' + str(key_path) + '] ' + MOZILLA_APT + ' mozilla main\n',
                 Path('/etc/apt/preferences.d/foundation-mozilla'):
                 'Package: firefox\nPin: origin packages.mozilla.org\nPin-Priority: 1001\n\n'
                 'Package: firefox\nPin: release o=Ubuntu\nPin-Priority: -1\n'}
        for path, content in files.items():
            with path.open('x', encoding='utf-8') as stream: stream.write(content)
            path.chmod(0o644)
        subprocess.run(['apt-get', 'update'], check=True)
        policy = capture(['apt-cache', 'policy', 'firefox'])
        selected_version = mozilla_candidate(policy, capture(['apt-cache', 'madison', 'firefox']), selection['architecture'])
    packages = ['firefox=' + selected_version] if selected_version else selection['packages']
    subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends', *packages], check=True)
    installed = []
    for package in selection['packages']:
        fields = capture(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n', package]).split('\t')
        if (len(fields) != 4 or fields[0] != package or fields[2] != selection['architecture'] or
                fields[3] != 'installed' or selected_version and fields[1] != selected_version):
            raise ValueError('installed browser package differs from selected prerequisite')
        installed.append(dict(package=fields[0], version=fields[1], architecture=fields[2],
                              policy=capture(['apt-cache', 'policy', package])))
    return dict(schema_version=1, selection=selection, signing_key_fingerprint=fingerprint,
                installed=installed, browser_version=capture([selection['executable'], '--version']))


def needs_windows_graphics(target, backends, backend, scope):
    return target == 'windows-x86_64' and 'rev' in backends and (scope in ('source', 'recovery') or backend == 'rev' and scope == 'archive')


def qualification_plan(candidate, profile, output, policy=None):
    c = module('coverage')
    policy = policy or c.load(ROOT / 'docs/release-policy.json')
    selected, _ = module('certify_release').requirements(policy, profile)
    manifest = module('release').verify_release(candidate)
    actual = {x['target']: x['backends'] or ['core'] for x in manifest['artifacts']}
    if len(actual) != len(manifest['artifacts']) or actual != selected['targets']:
        raise ValueError('candidate does not match complete support profile')
    checks, matrix = [], []
    images = {'debian-12': 'debian:bookworm', 'debian-13': 'debian:trixie', 'ubuntu-24.04': 'ubuntu:24.04'}
    for item in selected['checks']:
        target, backend, environment, scope = (item[x] for x in ('target', 'backend', 'environment', 'scope'))
        check_id = '-'.join((target, backend, environment, scope))
        argv = ['{python}', '{root}/tools/release_check.py', scope, '--release', '{root}/build/candidate',
                '--target', target, '--backend', backend, '--evidence', '{evidence}', '--jobs', '2']
        if (target.startswith('linux-') or target == 'browser-wasm32') and needs_browser_prerequisite(backend, scope):
            browser = browser_prerequisite(target, environment, backend)
            argv += ['--browser-prerequisite', '{root}/build/prerequisites/' + check_id + '/browser.json',
                     '--browser-prerequisite-plan', '{root}/build/check-plan.json']
            if browser['engine'] == 'firefox': argv += ['--firefox', browser['executable']]
        if environment in ('chromium', 'firefox'):
            argv += ['--browser', environment]
            if environment == 'chromium': argv += ['--browser-executable', '/usr/bin/chromium', '--driver', '/usr/bin/chromedriver']
        graphics = needs_windows_graphics(target, selected['targets'][target], backend, scope)
        if graphics:
            argv += ['--windows-graphics-archive', '{root}/build/host-graphics/mesa-windows.7z']
        if target == 'windows-x86_64' and backend == 'hosted-web':
            argv += ['--firefox', 'C:/Program Files/Mozilla Firefox/firefox.exe']
        checks.append(dict(item, id=check_id, required=True, argv=argv, timeout_seconds=5400,
                           warning_seconds=4500, expected_tests=[], qualification='qualification.json'))
        matrix.append({'id': check_id, 'target': target, 'runner': STANDARD.get(target, 'ubuntu-24.04'),
                       'image': images.get(environment, 'debian:bookworm' if environment in ('firefox', 'chromium') else ''),
                       'environment': environment, 'scope': scope, 'backend': backend, 'graphics': graphics})
    inputs = {str(p.relative_to(ROOT)).replace('\\', '/'): c.sha(p) for p in (ROOT / 'tools').glob('*.py')}
    for name in ('docs/release-policy.json', '.github/scripts/lifecycle.py', '.github/workflows/certify.yml'):
        inputs[name] = c.sha(ROOT / name)
    if any(item['graphics'] for item in matrix):
        for name in ('tools/windows_gl_probe.cpp', 'third_party/host-graphics/mesa-windows.json'):
            inputs[name] = c.sha(ROOT / name)
    for name in [*manifest['files'], 'release.json']:
        inputs['build/candidate/' + name] = c.sha(candidate / name)
    value = c.freeze({'schema_version': 1, 'mode': 'release',
                      'subject': {'source_sha256': manifest['source']['sha256'], 'inventory_sha256': c.sha(candidate / 'release.json'),
                                  'configuration_sha256': c.digest({'policy': policy, 'profile': profile})},
                      'inputs': inputs, 'checks': checks})
    c.write_new(output, value)
    return {'include': matrix}


def download_run(repository, run_id, source_commit, workflow, name, output):
    g = module('github_release')
    g.location(repository); exact_commit(source_commit)
    if not re.fullmatch(r'[1-9][0-9]*', str(run_id)) or not re.fullmatch(r'[a-z0-9-]+\.yml', workflow):
        raise ValueError('exact run and allowed workflow filename required')
    g.valid_name(name)
    remote = g.Remote(repository); remote.visible()
    observed = remote.transport.json(remote.base + '/actions/runs/' + str(run_id))
    if (observed.get('head_sha') != source_commit or observed.get('status') != 'completed' or
        observed.get('conclusion') != 'success' or observed.get('event') != 'workflow_dispatch' or
        observed.get('path') != '.github/workflows/' + workflow or
        observed.get('head_repository', {}).get('full_name', '').casefold() != repository.casefold()):
        raise ValueError('artifact producer run identity or successful completion differs')
    if output.exists(): raise ValueError('download output must be new')
    subprocess.run(['gh', 'run', 'download', str(run_id), '--repo', repository, '--name', name, '--dir', str(output)], check=True)
    return observed



def retained_sdk_request(request, repository, target, profile, recipe):
    """One explicit producer and two immutable transport objects; no selection fallback."""
    g = module('github_release')
    fields = {'schema_version', 'repository', 'target', 'profile', 'recipe_id',
              'run_id', 'source_commit', 'attempt', 'job_id', 'group', 'proof'}
    if not isinstance(request, dict) or set(request) != fields or type(request['schema_version']) is not int or request['schema_version'] != 1:
        raise ValueError('exact retained SDK request schema required')
    g.location(repository); exact_commit(request['source_commit'])
    if (target not in (*STANDARD, 'browser-wasm32') or profile not in ('core', 'all-gui') or
        request['repository'] != repository or request['target'] != target or
        request['profile'] != profile or request['recipe_id'] != recipe or
        not isinstance(recipe, str) or not re.fullmatch(r'[0-9a-f]{64}', recipe)):
        raise ValueError('retained SDK repository, target, profile or current recipe differs')
    for field in ('run_id', 'attempt', 'job_id'):
        if type(request[field]) is not int or request[field] < 1:
            raise ValueError('retained producer identifiers must be positive integers')
    for field in ('group', 'proof'):
        item = request[field]
        if (not isinstance(item, dict) or set(item) != {'id', 'sha256'} or
            type(item['id']) is not int or item['id'] < 1 or
            not isinstance(item['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])):
            raise ValueError('exact retained artifact ID and SHA256 required')
    if request['group']['id'] == request['proof']['id']:
        raise ValueError('group and proof must be distinct artifacts')
    return request


def _retained_zip(path, *, max_bytes):
    """Validate every member; callers read selected proof files without extraction."""
    import stat
    import zipfile
    a = module('dependency_archive')
    entries, folded, kinds, spelling, total = {}, set(), {}, {}, 0
    with zipfile.ZipFile(path) as source:
        members = source.infolist()
        if len(members) > 10000:
            raise ValueError('retained ZIP inventory exceeds supported limit')
        for item in members:
            name = str(a.relative(item.filename[:-1] if item.is_dir() else item.filename))
            key = name.casefold(); mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (key in folded or kind not in (0, stat.S_IFDIR if item.is_dir() else stat.S_IFREG) or
                mode & 0o7000 or item.flag_bits & 1 or item.file_size < 0):
                raise ValueError('unsafe, linked or duplicate retained ZIP member')
            total += item.file_size
            if total > max_bytes:
                raise ValueError('retained ZIP expands beyond supported limit')
            folded.add(key); kinds[key] = item.is_dir()
            parts = name.split('/')
            for index in range(1, len(parts) + 1):
                prefix = '/'.join(parts[:index]); prior = spelling.setdefault(prefix.casefold(), prefix)
                if prior != prefix:
                    raise ValueError('ambiguous retained ZIP path spelling')
            if not item.is_dir(): entries[name] = item
        for name in entries:
            for parent in a.relative(name).parents:
                if str(parent) != '.' and kinds.get(str(parent).casefold()) is False:
                    raise ValueError('retained ZIP file is also an entry parent')
    return entries


def _download_action_artifact(repository, artifact_id, path):
    with Path(path).open('xb') as stream:
        result = subprocess.run(['gh', 'api', '--hostname', 'github.com',
            f'repos/{repository}/actions/artifacts/{artifact_id}/zip'], stdout=stream,
            stderr=subprocess.PIPE, check=False, timeout=1800)
    if result.returncode:
        raise ValueError('retained artifact download failed; no fallback is permitted')


def retained_sdk(repository, request, target, profile, recipe, output, *, transport=None, download=None):
    """Reuse checked bytes from one finished producer, regardless of sibling status."""
    import datetime
    import shutil
    import tempfile
    import zipfile
    g = module('github_release'); a = module('dependency_archive'); store = module('dependency_store')
    retained_sdk_request(request, repository, target, profile, recipe)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink(): raise ValueError('retained SDK output must be new')
    remote = g.Remote(repository, transport); remote.visible()
    base = remote.base; run_id = request['run_id']; attempt = request['attempt']; commit = request['source_commit']
    repository_info = remote.transport.json(base)
    repository_id = repository_info.get('id')
    if type(repository_id) is not int or repository_id < 1:
        raise ValueError('repository numeric identity is unavailable')
    run_endpoint = f'{base}/actions/runs/{run_id}/attempts/{attempt}'
    job_endpoint = f'{base}/actions/jobs/{request["job_id"]}'
    runner = STANDARD.get(target, 'ubuntu-24.04')

    def producer():
        observed = remote.transport.json(run_endpoint)
        job = remote.transport.json(job_endpoint)
        if (observed.get('id') != run_id or observed.get('run_attempt') != attempt or
            observed.get('head_sha') != commit or observed.get('event') != 'workflow_dispatch' or
            observed.get('path') != '.github/workflows/sdk-maintenance.yml' or
            observed.get('repository', {}).get('id') != repository_id or
            observed.get('repository', {}).get('full_name', '').casefold() != repository.casefold() or
            observed.get('head_repository', {}).get('id') != repository_id or
            observed.get('head_repository', {}).get('full_name', '').casefold() != repository.casefold() or
            job.get('id') != request['job_id'] or job.get('run_id') != run_id or
            job.get('run_attempt') != attempt or job.get('head_sha') != commit or
            job.get('name') != f'produce ({target}, {runner})' or job.get('status') != 'completed' or
            job.get('conclusion') not in ('success', 'failure')):
            raise ValueError('retained producer job, attempt or workflow identity differs')
        try:
            started = datetime.datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
            completed = datetime.datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00'))
            if started.utcoffset() is None or completed.utcoffset() is None or completed < started:
                raise ValueError('invalid producer time interval')
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError('completed producer time interval is unavailable') from error
        return job, started, completed

    job, started, completed = producer()
    observed_artifacts = {}
    for kind in ('group', 'proof'):
        item = request[kind]
        row = remote.transport.json(f'{base}/actions/artifacts/{item["id"]}')
        run = row.get('workflow_run', {})
        expected_name = f'sdk-{kind}-{target}-{attempt}'
        if (row.get('id') != item['id'] or row.get('name') != expected_name or row.get('expired') is not False or
            row.get('digest') != 'sha256:' + item['sha256'] or type(row.get('size_in_bytes')) is not int or
            not 0 < row['size_in_bytes'] <= (16 * 1024**3 if kind == 'group' else 64 * 1024**2) or
            run.get('id') != run_id or run.get('head_sha') != commit or
            run.get('repository_id') != repository_id or run.get('head_repository_id') != repository_id):
            raise ValueError('retained artifact immutable identity or producer differs')
        created = datetime.datetime.fromisoformat(row.get('created_at', '').replace('Z', '+00:00'))
        if created.utcoffset() is None or not started <= created <= completed:
            raise ValueError('retained artifact was not created within the exact producer job')
        observed_artifacts[kind] = row
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.retained-sdk-') as temporary:
        stage = Path(temporary)
        for kind, row in observed_artifacts.items():
            path = stage / (kind + '.zip')
            (download or _download_action_artifact)(repository, row['id'], path)
            if path.stat().st_size != row['size_in_bytes'] or a.digest(path) != request[kind]['sha256']:
                raise ValueError('downloaded retained ZIP differs from pinned bytes')
        proof_entries = _retained_zip(stage / 'proof.zip', max_bytes=64 * 1024**2)
        if any(name not in proof_entries or proof_entries[name].file_size > 128 * 1024
               for name in ('sdk-retention.json', 'sdk-origin.json')):
            raise ValueError('retained proof requires bounded retention and origin records')
        with zipfile.ZipFile(stage / 'proof.zip') as source:
            receipt = g.parse(source.read('sdk-retention.json'))
            origin = g.parse(source.read('sdk-origin.json'))
        expected = dict(schema_version=1, status='verified', qualification='unqualified',
            publication_approved=False, target=target, profile=profile, recipe_id=recipe,
            source_commit=commit, run_id=str(run_id), attempt=attempt)
        if (not isinstance(receipt, dict) or set(receipt) != set(expected) | {'files'} or
            any(type(receipt.get(k)) is not type(v) or receipt[k] != v for k, v in expected.items()) or
            not isinstance(origin, dict) or origin.get('recipe') != recipe or
            origin.get('origin') not in ('base', 'rebuild', 'absent-base', 'absent-recipe', 'retained')):
            raise ValueError('retained SDK receipt or origin does not bind the exact request')
        entries = _retained_zip(stage / 'group.zip', max_bytes=16 * 1024**3)
        with zipfile.ZipFile(stage / 'group.zip') as source:
            if set(entries) != set(store.names(recipe)) or len(source.infolist()) != 3:
                raise ValueError('retained group must contain exactly the SDK triplet')
            group = stage / 'group'; group.mkdir()
            for name in entries:
                with source.open(name) as stream, (group / name).open('xb') as destination:
                    shutil.copyfileobj(stream, destination)
        files = store.verify_group(group, recipe)
        if files != receipt['files']:
            raise ValueError('retained SDK triplet differs from the verified receipt')
        if producer()[0] != job or any(remote.transport.json(f'{base}/actions/artifacts/{row["id"]}') != row
                                      for row in observed_artifacts.values()):
            raise ValueError('retained producer or artifacts changed during verification')
        store.copy_group(group, output, recipe)
    return dict(origin='retained', recipe=recipe, qualification='unqualified', publication_approved=False,
                repository=repository, request=request, producer=job, artifacts=observed_artifacts,
                retention=receipt, previous_origin=origin)


def maintenance_base(repository, recipe, output, source='auto', transport=None):
    """Cold production is allowed only after positively observing complete absence."""
    g = module('github_release'); store = module('dependency_store')
    expected = set(store.names(recipe)); g.location(repository)
    if source not in ('auto', 'base', 'rebuild'):
        raise ValueError('maintenance source must be auto, base or rebuild')
    if source == 'rebuild': return {'origin': 'rebuild', 'recipe': recipe}
    if source == 'base':
        return dict(g.fetch_base(repository, recipe, output, transport=transport), origin='base')
    remote = g.Remote(repository, transport); remote.visible()
    info = remote.find('base', False)
    if info is None:
        if remote.reference('base', True) is not None:
            raise ValueError('orphan base tag requires reconciliation')
        return {'origin': 'absent-base', 'recipe': recipe}
    if info['draft'] or not info['prerelease'] or info['name'] != 'base':
        raise ValueError('base lifecycle requires reconciliation')
    assets = remote.assets(info); reference = remote.reference('base')
    present = expected & assets.keys()
    if present and present != expected:
        raise ValueError('partial dependency group requires reconciliation')
    if not present:
        remote.unchanged('base', info, assets, reference)
        return {'origin': 'absent-recipe', 'recipe': recipe}
    return dict(g.fetch_base(repository, recipe, output, transport=transport), origin='base')


def graphics_test(command, output, staged):
    """Use the shared bounded owner before leaving temporary runtime staging."""
    return module('windows_graphics').run_owned(command, output, output / 'graphics-test.log',
             environment=staged.environment, timeout=3600, max_bytes=16 * 1024 * 1024)


def windows_gui_qualification(command, archive, build, output, jobs, *, protected_roots, cwd):
    """One build, actual host probe and complete GUI tests; cleanup precedes packaging."""
    if command[2:4] != ['test', 'release'] or '--full' not in command or '--host-tests' not in command:
        raise ValueError('Windows GUI qualification requires the complete release host test command')
    prepare = command.copy(); prepare[2] = 'build'; prepare.remove('--full')
    index = prepare.index('--junit'); del prepare[index:index + 2]
    subprocess.run(prepare, cwd=cwd, check=True)
    subprocess.run(['cmake', '--build', str(build), '--target', 'foundation-gui-tests',
                    '--parallel', str(jobs)], cwd=cwd, check=True)
    probe = output / 'graphics-probe'; probe.mkdir()
    graphics = None; setup_receipt = None
    try:
        with module('windows_graphics').qualified_stage(archive, [build / 'gui'],
                probe_directory=probe, compile_log=output / 'graphics-compile.log',
                protected_roots=protected_roots) as graphics:
            module('coverage').write_new(output / 'graphics-probe.json', graphics.probe_receipt)
            graphics_test(command, output, graphics)
    except BaseException as error:
        setup_receipt = getattr(error, 'graphics_receipt', None)
        raise
    finally:
        module('coverage').write_new(output / 'graphics.json', graphics.receipt if graphics else setup_receipt or
            {'status': 'incomplete', 'detail': 'graphics setup did not reach the supervised test context'})
    if graphics.receipt.get('cleanup') != 'removed':
        error = ValueError('Windows GUI host input cleanup did not complete; packaging is prohibited')
        error.graphics_receipt = graphics.receipt
        raise error
    visual = build / 'gui/visual-evidence'
    captures = list(visual.rglob('*')) if visual.is_dir() else []
    files = [p for p in captures if p.is_file()]
    if (any(p.is_symlink() for p in captures) or not any(p.name == 'qualification.json' for p in files) or
            not any(p.suffix == '.png' for p in files) or not any(p.suffix == '.ppm' for p in files) or
            any(p.suffix not in ('.json', '.png', '.ppm', '.log') for p in files)):
        raise ValueError('complete real native GUI capture evidence is required')
    return {p.relative_to(output).as_posix(): module('coverage').sha(p)
            for p in [output / 'graphics.json', output / 'graphics-probe.json', *files]}


def prepared_check(target, recipe, group, output, jobs=2, gui_group=None, graphics_archive=None):
    """Consume a relocated SDK; GUI qualification retains no distributable output."""
    from dependency_store import verify_group
    if target not in (*STANDARD, 'browser-wasm32') or jobs < 1:
        raise ValueError('supported target and positive concurrency required')
    graphics_needed = target == 'windows-x86_64' and gui_group is not None
    if graphics_needed != (graphics_archive is not None):
        raise ValueError('Windows GUI qualification requires one explicit retained host graphics archive; other probes must omit it')
    if graphics_needed: module('windows_graphics').verify_archive(Path(graphics_archive))
    if target != 'browser-wasm32': assert_host(target)
    elif platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('browser SDK requires its declared Linux x64 host')
    output = Path(output).absolute(); group = Path(group).resolve(strict=True)
    if output.exists(): raise ValueError('prepared check output must be new')
    before = verify_group(group, recipe); output.mkdir(parents=True)
    command = [sys.executable, str(ROOT / 'tools/build.py'), 'test', 'release', '--portable',
               '--jobs', str(jobs), '--build-dir', str(output / 'build'), '--junit', str(output / 'source.junit.xml')]
    if target == 'windows-x86_64':
        version = module('windows_toolchain').inspect_selected_linker()['version']
        metadata = module('sdk_windows').install(group, recipe, output / 'dependencies', version)
        command += ['--dependency-group', str(group), '--windows-dependencies', str(output / 'dependencies')]
    else:
        metadata = module('sdk').install(group, recipe, output / 'sdk', production=True)
        command += ['--sdk', str(output / 'sdk')]
    if gui_group is not None:
        backends = ['wasm'] if target == 'browser-wasm32' else ['terminal', 'framebuffer', 'fltk', 'rev', 'sdl', 'hosted-web']
        if not set(backends) <= set(metadata.get('capabilities', ['wasm'] if target == 'browser-wasm32' else [])):
            raise ValueError('prepared SDK lacks required GUI capabilities')
        command += ['--gui-input-group', str(Path(gui_group).resolve(strict=True)), '--gui-backends', ','.join(backends), '--full']
        if target != 'browser-wasm32': command += ['--host-tests']
    if gui_group is None:
        command += ['--label', 'core']
        if target == 'browser-wasm32': command += ['--gui-backends', 'wasm']
    graphics_evidence = None
    if graphics_needed:
        graphics_evidence = windows_gui_qualification(command, Path(graphics_archive), output / 'build', output, jobs,
            protected_roots=(group, Path(gui_group).resolve(), output / 'dependencies', output / 'build/inputs'), cwd=ROOT)
    else:
        subprocess.run(command, cwd=ROOT, check=True)
    if gui_group is None:
        packaging = command.copy(); packaging[2] = 'package'
        for option in ('--junit', '--label'):
            index = packaging.index(option); del packaging[index:index + 2]
        subprocess.run(packaging, cwd=ROOT, check=True)
        choices = list((output / 'build/packages').glob('*.zip' if target.startswith('windows-') else '*.tar.gz'))
        if len(choices) != 1: raise ValueError('prepared check needs one complete archive')
        a = module('artifact'); descriptor = choices[0].with_name(choices[0].name + '.json')
        module('coverage').write_new(descriptor, a.describe(choices[0]))
        a.verify(choices[0], descriptor, sdk=output / 'sdk' if target != 'windows-x86_64' else None,
                 abi=target.startswith('linux-'), processor=target.split('-', 1)[1])
    if verify_group(group, recipe) != before: raise ValueError('SDK group changed during qualification')
    receipt = {'status': 'passed', 'target': target, 'recipe': recipe, 'group_files': before,
               'checks': ['relocated-sdk', 'compile', 'execute', 'installed-consumer'] if gui_group is None
                         else ['relocated-sdk', 'all-native-gui' if target != 'browser-wasm32' else 'wasm-gui', 'full-source-tests'],
               'redistribution': False, 'source_junit': 'source.junit.xml'}
    if graphics_evidence is not None: receipt['graphics_evidence'] = graphics_evidence
    module('coverage').write_new(output / 'qualification.json', receipt)
    return receipt


def gui_group_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('ci_gui_group', ROOT / 'gui/source_group.py')
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def gui_group_names(identity):
    if not isinstance(identity, str) or not re.fullmatch(r'[0-9a-f]{64}', identity):
        raise ValueError('exact GUI group identity required')
    return {name: 'gui-' + identity + '-' + suffix for name, suffix in
            [('gui-inputs.tar.gz', 'inputs.tar.gz'), ('manifest.json', 'manifest.json'), ('SHA256SUMS', 'SHA256SUMS')]}


def fetch_gui_group(repository, identity, output, transport=None):
    import tempfile
    g = module('github_release'); c = module('coverage'); verifier = gui_group_module()
    names = gui_group_names(identity); remote = g.Remote(repository, transport); remote.visible()
    info = remote.find('base'); assets = remote.assets(info); reference = remote.reference('base')
    if info['draft'] or not info['prerelease'] or info['name'] != 'base':
        raise ValueError('GUI inputs require the published prerelease base')
    if not set(names.values()) <= assets.keys():
        raise ValueError('exact complete GUI input group is absent; run explicit maintenance')
    output = Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('GUI input destination must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'group'; stage.mkdir()
        for local, remote_name in names.items(): remote.download(assets[remote_name], stage / local)
        if c.sha(stage / 'manifest.json') != identity: raise ValueError('GUI group identity differs')
        verifier.verify(stage)
        remote.unchanged('base', info, assets, reference)
        stage.rename(output)
    return {'group_sha256': identity, 'fetched': True}


def publish_gui_group(repository, group, source_commit, execute=False, transport=None):
    import shutil
    import tempfile
    g = module('github_release'); c = module('coverage'); verifier = gui_group_module()
    group = Path(group); manifest = verifier.verify(group, redistribution=execute)
    exact_commit(source_commit)
    identity = c.sha(group / 'manifest.json'); names = gui_group_names(identity)
    files = {remote_name: c.sha(group / local) for local, remote_name in names.items()}
    result = g.plan('publish-gui-inputs', repository, group_sha256=identity, files=files,
                    source_commit=source_commit, redistributable=manifest['redistributable'],
                    lifecycle='immutable complete GUI input group; base prerelease; never Latest')
    if not execute: return result
    remote = g.Remote(repository, transport)
    def act():
        remote.visible(); info = remote.find('base', False)
        before = remote.assets(info) if info else {}; reference = remote.reference('base') if info else source_commit
        present = set(files) & before.keys()
        if info and (info['draft'] or not info['prerelease'] or info['name'] != 'base'):
            raise ValueError('existing base lifecycle differs')
        if present and present != set(files): raise ValueError('partial GUI group requires reconciliation')
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            def confirm(assets):
                dest = work / 'confirm'; dest.mkdir()
                for local, remote_name in names.items(): remote.download(assets[remote_name], dest / local, files[remote_name])
                if verifier.verify(dest, redistribution=True) != manifest: raise ValueError('remote GUI group differs')
            if present:
                confirm(before); remote.unchanged('base', info, before, reference); remote.not_latest(info)
                return dict(result, execute=True, reused=True)
            if not info:
                if remote.reference('base', True) is not None: raise ValueError('orphan base tag requires reconciliation')
                remote.change('/git/refs', body={'ref': 'refs/tags/base', 'sha': source_commit})
                info = remote.info(remote.change('/releases', body={'tag_name': 'base', 'target_commitish': source_commit,
                          'name': 'base', 'body': 'Complete retained dependency inputs.', 'draft': True,
                          'prerelease': True, 'make_latest': 'false'}), 'base')
                if not info['draft'] or not info['prerelease'] or info['name'] != 'base': raise ValueError('base draft differs')
            for local, remote_name in names.items():
                path = work / remote_name; shutil.copyfile(group / local, path)
                if c.sha(path) != files[remote_name]: raise ValueError('GUI inputs changed before publication')
                remote.upload('base', path)
            current = remote.find('base'); assets = remote.assets(current)
            if any(current[k] != info[k] for k in ('id', 'name', 'draft', 'prerelease')):
                raise ValueError('base identity changed')
            if set(assets) != set(before) | set(files) or any(assets[n] != v for n, v in before.items()):
                raise ValueError('base assets changed unexpectedly')
            confirm(assets)
            if verifier.verify(group, redistribution=True) != manifest or any(c.sha(group / n) != files[v] for n, v in names.items()):
                raise ValueError('local GUI group changed during publication')
            remote.unchanged('base', current, assets, reference)
            if current['draft']:
                remote.change('/releases/' + str(current['id']), method='PATCH', body={'draft': False, 'prerelease': True, 'make_latest': 'false'})
            final = remote.find('base')
            if final['id'] != info['id'] or final['draft'] or not final['prerelease'] or final['name'] != 'base' or remote.assets(final) != assets:
                raise ValueError('base finalization unconfirmed')
            remote.not_latest(final)
            if remote.reference('base') != reference: raise ValueError('base reference changed')
            return dict(result, execute=True, reused=False, release_id=final['id'])
    return g.run_mutation(remote, act)


def lifecycle_main(argv):
    p = argparse.ArgumentParser(description='Frozen SDK and release lifecycle operations')
    p.add_argument('operation', choices=('release-matrix', 'source', 'prepared-package', 'assemble', 'fetch-candidate',
                                       'qualification-plan', 'download-run', 'delivery-request', 'certify'))
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--github-output', type=Path)
    a = p.parse_args(argv)
    c = module('coverage'); data = c.load(a.input)
    op = a.operation
    if op == 'release-matrix': result = release_matrix(**data)
    elif op == 'source': result = source_archive(Path(data['output']), Path(data['gui_source']) if data.get('gui_source') else None)
    elif op == 'prepared-package':
        result = prepared_package(data['target'], data['recipe'], Path(data['group']).resolve(), Path(data['source']).resolve(), Path(data['output']).resolve(), data.get('jobs', 2))
    elif op == 'assemble': result = assemble_release(*(Path(data[k]) for k in ('source', 'packages', 'base', 'output')), data['profile'])
    elif op == 'fetch-candidate': result = fetch_candidate(data['repository'], data['tag'], data['inventory'], Path(data['output']))
    elif op == 'qualification-plan': result = qualification_plan(Path(data['candidate']).resolve(), data['profile'], Path(data['plan']))
    elif op == 'download-run': result = download_run(data['repository'], data['run_id'], data['source_commit'], data['workflow'], data['name'], Path(data['output']))
    elif op == 'certify':
        manifest = module('release').verify_release(Path(data['directory']))
        plan = c.load(Path(data['check_plan'])); reports = [Path(data['reports']) / x['id'] / 'result.json' for x in plan['checks']]
        result = module('certify_release').certify(Path(data['directory']), manifest, plan, reports,
                  c.load(Path(data['policy'])), data['profile'], data.get('experiment', False))
    else:
        operation = data.pop('operation')
        if operation not in ('publish-candidate', 'attach-certificate', 'promote', 'publish-base'):
            raise ValueError('unknown delivery operation')
        if 'delivery_file' in data: data['delivery'] = c.load(Path(data.pop('delivery_file')))
        if operation == 'attach-certificate':
            frozen = c.load(Path(data['check_plan']))
            data['reports'] = [str(Path(data['reports']) / x['id'] / 'result.json') for x in frozen['checks']]
        result = data
    if a.output: c.write_new(a.output, result)
    if a.github_output:
        with a.github_output.open('a', encoding='utf-8') as out:
            out.write('matrix=' + json.dumps(result, separators=(',', ':')) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "lifecycle":
            lifecycle_main(sys.argv[2:])
        else:
            main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("CI: " + str(error), file=sys.stderr)
        sys.exit(1)
