"""Inert, explicitly synthetic SDK facts; never invoke any fixture program."""

import hashlib
import json
import os
from pathlib import Path
import stat


TARGET = {'system': 'Linux', 'processor': 'x86_64',
          'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
CPU = {'baseline': 'sse2', 'source_dispatch': 'supplier-per-source-reviewed'}
RUNTIME = {'c_library': 'glibc', 'c_library_baseline': '2.36',
           'cxx_library': 'libstdc++', 'cxx_library_baseline': '3.4.34',
           'linkage': 'private-native', 'sysroot_inventory': 'sdk',
           'needed_libraries': ['libc.so.6', 'libgcc_s.so.1', 'libm.so.6', 'libstdc++.so.6']}
CONTROL_PATHS = ('tools/appended_engine_native_sdk.py',
    'recipes/webkitwasm-native-rich4083-v1/producer/native-sdk-toolchain.cmake.in')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw, mode=0o644):
    path = Path(path)
    missing, parent = [], path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        directory.chmod(0o755)
    path.write_bytes(raw)
    path.chmod(mode)
    return path


def document(path, value):
    return write(path, encoded(value))


def inventory(root):
    """Complete walk of our tiny owned fixture only, never a real SDK."""
    root = Path(root)
    files, directories, modes = {}, [], {}
    for parent, child_dirs, child_files in os.walk(root, followlinks=False):
        child_dirs.sort()
        child_files.sort()
        for name in child_dirs:
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            directories.append(relative)
            modes[relative] = stat.S_IMODE(path.lstat().st_mode)
        for name in child_files:
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            files[relative] = sha(path.read_bytes())
            modes[relative] = stat.S_IMODE(path.lstat().st_mode)
    return {'files': dict(sorted(files.items())),
            'directories': sorted(directories), 'modes': dict(sorted(modes.items()))}


def snapshot(root):
    """Bytes, modes and identities; reading atime is intentionally immaterial."""
    root = Path(root)
    result = {}
    for parent, child_dirs, child_files in os.walk(root, followlinks=False):
        for name in sorted(child_dirs + child_files):
            path = Path(parent) / name
            state = path.lstat()
            key = path.relative_to(root).as_posix()
            body = (os.readlink(path) if stat.S_ISLNK(state.st_mode)
                    else sha(path.read_bytes()) if stat.S_ISREG(state.st_mode) else None)
            result[key] = (state.st_dev, state.st_ino, state.st_mode, state.st_nlink, body)
    return result


class Fixture:
    """Create one complete *fake* SDK and its original fake raw observations.

    The caller owns ``parent``. Nothing under a real SDK or repository is changed.
    Mutable control files are exact copies from the frozen source checkout.
    """

    def __init__(self, parent, repository_root, *, group_names=None):
        self.root = Path(parent) / 'fixture'
        self.root.mkdir(mode=0o700)
        self.sdk = self.root / 'sdk'
        self.sdk.mkdir(mode=0o755)
        self.extension = self.root / 'host-extension'
        self.extension.mkdir(mode=0o755)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir(mode=0o755)
        self.group = self.root / 'retained-group'
        self.group.mkdir(mode=0o755)
        self.repository = self.root / 'repository'
        self.repository.mkdir(mode=0o755)
        for name in CONTROL_PATHS:
            source = Path(repository_root) / name
            write(self.repository / name, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
        self.recipe = sha(b'SYNTHETIC native SDK retained recipe, not an actual recipe')
        self.source_identity = sha(b'SYNTHETIC original source-manifest identity')
        self.group_names = group_names or (
            'sdk-' + self.recipe + '-binary.tar.gz',
            'sdk-' + self.recipe + '-sources.tar.gz',
            'sdk-' + self.recipe + '-SHA256SUMS')
        self.binary_name, self.source_name, self.sums_name = self.group_names
        write(self.group / self.binary_name, b'INERT SYNTHETIC BINARY ARCHIVE; NEVER EXTRACT\n')
        write(self.group / self.source_name, b'INERT SYNTHETIC SOURCE ARCHIVE; NEVER EXTRACT\n')
        sums = ''.join(sha((self.group / name).read_bytes()) + '  ' + name + '\n'
                       for name in (self.binary_name, self.source_name))
        write(self.group / self.sums_name, sums.encode('ascii'))
        self.group_files = {name: {'sha256': sha((self.group / name).read_bytes()),
                                  'bytes': (self.group / name).stat().st_size}
                            for name in self.group_names}
        self.sysroot = 'sysroot'
        self.program_paths = {
            'c': 'bin/' + TARGET['triple'] + '-gcc',
            'cxx': 'bin/' + TARGET['triple'] + '-g++',
            'linker': 'bin/' + TARGET['triple'] + '-ld',
            'archiver': 'bin/' + TARGET['triple'] + '-ar',
            'ranlib': 'bin/' + TARGET['triple'] + '-ranlib',
            'inspect': 'bin/' + TARGET['triple'] + '-readelf',
            'cmake': 'bin/cmake', 'ninja': 'bin/ninja', 'pkg_config': 'bin/pkg-config'}
        self.versions = {role: ('15.2.0' if role in ('c', 'cxx') else
            '3.31.0' if role == 'cmake' else '1.12.1' if role == 'ninja' else
            '2.3.0' if role == 'pkg_config' else '2.44.0') for role in self.program_paths}
        for role, name in self.program_paths.items():
            write(self.sdk / name, ('INERT SYNTHETIC ' + role + '; NEVER EXECUTE\n').encode(), 0o755)
        for name in ('libexec/cc1', 'libexec/cc1plus', 'bin/' + TARGET['triple'] + '-as',
                     'bin/python3'):
            write(self.sdk / name, ('INERT SYNTHETIC ' + name + '; NEVER EXECUTE\n').encode(), 0o755)
        self.runtime_files = {}
        for name in ('lib/libc.so.6', 'usr/lib/libstdc++.so.6', 'usr/lib/libgcc_s.so.1'):
            path = write(self.sdk / self.sysroot / name,
                         ('INERT SYNTHETIC target runtime ' + name + '\n').encode())
            self.runtime_files[name] = sha(path.read_bytes())
        for name in ('usr/include/X11/Core.h', 'usr/include/X11/core.h',
                     'usr/lib/pkgconfig/synthetic.pc', 'usr/lib64/pkgconfig/synthetic64.pc'):
            write(self.sdk / self.sysroot / name, ('SYNTHETIC SUPPORT ' + name + '\n').encode())
        for name in ('json/__init__.py', 'hashlib.py', 'pathlib.py'):
            write(self.sdk / 'lib/python3.12' / name, b'# INERT SYNTHETIC PYTHON MODULE\n')
        write(self.sdk / 'share/licenses/sdk.txt', b'SYNTHETIC fixture license data\n')
        for role in ('perl', 'ruby', 'gperf', 'sh'):
            write(self.extension / 'bin' / role,
                  ('INERT SYNTHETIC ' + role + '; NEVER EXECUTE\n').encode(), 0o755)
        for name in ('lib/perl5/English.pm', 'lib/perl5/FindBin.pm', 'lib/perl5/JSON/PP.pm',
                     'lib/ruby/json.rb', 'lib/ruby/fileutils.rb', 'lib/libhost-runtime.so'):
            write(self.extension / name, ('INERT SYNTHETIC host runtime ' + name + '\n').encode())
        self.host_inventory_path = self.inputs / 'host-extension-inventory.json'
        document(self.host_inventory_path, inventory(self.extension))
        self.manifest = {
            'schema_version': 1, 'recipe_id': self.recipe, 'kind': 'source-build',
            'target': {'system': 'Linux', 'processor': 'x86_64', 'triple': TARGET['triple'],
                       'sysroot': self.sysroot, 'c_compiler': self.program_paths['c'],
                       'cxx_compiler': self.program_paths['cxx']},
            'host': {'system': 'Linux', 'processor': 'x86_64', 'glibc': '2.36'},
            'baseline': {'distribution': 'debian-12', 'glibc': '2.36'},
            'host_tools': {'cmake': self.program_paths['cmake'], 'ninja': self.program_paths['ninja'],
                           'pkg-config': self.program_paths['pkg_config'], 'python': 'bin/python3'},
            'files': {}, 'sources_sha256': self.source_identity,
            'licenses': ['share/licenses/sdk.txt'], 'relocation': 'buildroot',
            'audits': {'host': {'status': 'passed'}, 'target': {'status': 'passed',
                'scope': 'sdk-sysroot', 'sdk_runtime': {'recipe_id': self.recipe,
                    'processor': 'x86_64', 'glibc': '2.36',
                    'source_sha256': self.source_identity, 'files': dict(self.runtime_files)}}},
            'installed_root': str(self.sdk),
            'archive_sha256': self.group_files[self.binary_name]['sha256'],
            'path_policy': 'linux-case-sensitive-v1',
            'synthetic_extension_preserved': {'fixture': True}}
        self.manifest['files'] = inventory(self.sdk)['files']
        document(self.sdk / 'sdk.json', self.manifest)
        self.restoration_path = self.inputs / 'restoration.json'
        self.observations_path = self.inputs / 'tool-observations.json'
        self.host_tools_path = self.inputs / 'host-tools.json'
        self.request_path = self.inputs / 'request.json'
        self.helper = write(self.inputs / 'original-helper.py',
                            b'# INERT SYNTHETIC original restoration helper; never run\n')
        python = self.program(self.sdk / 'bin/python3', '3.12.4')
        self.restoration = {
            'schema_version': 1, 'kind': 'foundation-native-sdk-restoration-observations-v1',
            'scope': 'original-supported-sdk-install-observation-only', 'mode': 'production',
            'sdk_root': str(self.sdk), 'sdk_manifest_sha256': self.manifest_pin,
            'recipe': self.recipe, 'group_files': self.group_files,
            'sources_sha256': self.source_identity,
            'helper': {'path': str(self.helper), 'sha256': sha(self.helper.read_bytes())},
            'controller': python,
            'command': self.command('restore', [python['path'], '-B', str(self.helper),
                'install', '--group', str(self.group), '--recipe', self.recipe,
                '--output', str(self.sdk)], 'SYNTHETIC restoration log; no actual install ran\n'),
            'production_eligible': False, 'native_build': False}
        self.observations = {
            'schema_version': 1, 'kind': 'foundation-native-sdk-tool-observations-v1',
            'scope': 'original-retained-sdk-tool-observation-only', 'sdk_root': str(self.sdk),
            'sdk_manifest_sha256': self.manifest_pin, 'tools': {},
            'production_eligible': False, 'native_build': False}
        for role, name in self.program_paths.items():
            program = self.program(self.sdk / name, self.versions[role])
            commands = {'version': self.command(role + '-version',
                [program['path'], '--version'], 'SYNTHETIC ' + role + ' ' + program['version'] + '\n')}
            if role in ('c', 'cxx'):
                frontend = 'cc1' if role == 'c' else 'cc1plus'
                for key, option, stdout in (
                    ('dumpmachine', '-dumpmachine', TARGET['triple']),
                    ('sysroot', '-print-sysroot', str(self.sdk / self.sysroot)),
                    ('frontend', '-print-prog-name=' + frontend, str(self.sdk / 'libexec' / frontend)),
                    ('assembler', '-print-prog-name=as', str(self.sdk / ('bin/' + TARGET['triple'] + '-as'))),
                    ('linker', '-print-prog-name=ld', str(self.sdk / self.program_paths['linker'])),
                    ('search_dirs', '-print-search-dirs',
                        'install: ' + str(self.sdk / 'libexec') + '\nprograms: =' + str(self.sdk / 'bin') +
                        '\nlibraries: =' + str(self.sdk / self.sysroot / 'usr/lib'))):
                    commands[key] = self.command(role + '-' + key, [program['path'], option], stdout + '\n')
            self.observations['tools'][role] = dict(program, commands=commands)
        self.host_tools = {'schema_version': 1,
            'kind': 'foundation-native-engine-prototype-sdk-host-tools-v1',
            'programs': {'python': python, 'perl': self.program(self.extension / 'bin/perl', '5.40.0'),
                'ruby': self.program(self.extension / 'bin/ruby', '3.3.0'),
                'gperf': self.program(self.extension / 'bin/gperf', '3.1.0'),
                'sh': self.program(self.extension / 'bin/sh', '5.2.0'),
                'cmake': self.program(self.sdk / self.program_paths['cmake'], self.versions['cmake']),
                'ninja': self.program(self.sdk / self.program_paths['ninja'], self.versions['ninja'])},
            'module_inventories': {'extension': {'root': str(self.extension),
                'inventory': self.ref(self.host_inventory_path)}}, 'interpreter_bindings': {}}
        for role in ('python', 'perl', 'ruby'):
            fact = {'schema_version': 1, 'kind': 'foundation-native-host-interpreter-runtime-v1',
                'program_sha256': self.host_tools['programs'][role]['sha256'],
                'search_paths': [str(self.sdk / 'lib/python3.12') if role == 'python' else
                    str(self.extension / ('lib/perl5' if role == 'perl' else 'lib/ruby'))],
                'runtime_inventories': ['sdk' if role == 'python' else 'host-extension']}
            path = document(self.inputs / ('interpreter-' + role + '.json'), fact)
            self.host_tools['interpreter_bindings'][role] = self.ref(path)
        self.request = {'schema_version': 1, 'kind': 'foundation-native-sdk-admission-request-v1',
            'target': dict(TARGET), 'sdk': {'root': str(self.sdk), 'manifest_sha256': self.manifest_pin},
            'retained_group': {'root': str(self.group), 'recipe': self.recipe, 'files': self.group_files},
            'restoration': {}, 'observations': {}, 'host_tools': {},
            'policy': {'runtime': dict(RUNTIME), 'cpu': dict(CPU), 'source_date_epoch': '1700000000'},
            'limits': {'prepare_seconds': 30, 'maximum_files': 2048,
                'maximum_input_bytes': 16 * 1024 * 1024, 'maximum_document_bytes': 1024 * 1024,
                'maximum_output_bytes': 8 * 1024 * 1024, 'minimum_free_bytes': 1}}
        self.flush()

    @property
    def manifest_pin(self):
        return sha((self.sdk / 'sdk.json').read_bytes())

    @staticmethod
    def program(path, version):
        return {'path': str(path), 'sha256': sha(Path(path).read_bytes()), 'version': version}

    def ref(self, path, *, base=None):
        base = self.inputs if base is None else Path(base)
        return {'path': Path(path).relative_to(base).as_posix(), 'sha256': sha(Path(path).read_bytes())}

    def command(self, name, argv, stdout):
        out = write(self.inputs / 'raw' / (name + '.stdout'), stdout.encode('utf-8'))
        err = write(self.inputs / 'raw' / (name + '.stderr'), b'')
        return {'argv': argv, 'returncode': 0, 'stdout': self.ref(out), 'stderr': self.ref(err),
                'ownership': {'closed': True, 'descendants_closed': True, 'logs_closed': True}}

    def flush(self):
        document(self.restoration_path, self.restoration)
        document(self.observations_path, self.observations)
        document(self.host_tools_path, self.host_tools)
        self.request.update({'restoration': self.ref(self.restoration_path),
            'observations': self.ref(self.observations_path), 'host_tools': self.ref(self.host_tools_path)})
        document(self.request_path, self.request)
        return sha(self.request_path.read_bytes())

    def rebind_manifest(self):
        """Refresh outer fixture joins to isolate a deliberate semantic change."""
        document(self.sdk / 'sdk.json', self.manifest)
        self.request['sdk']['manifest_sha256'] = self.manifest_pin
        self.restoration['sdk_manifest_sha256'] = self.manifest_pin
        self.observations['sdk_manifest_sha256'] = self.manifest_pin
        return self.flush()

    def rewrite_raw(self, role, command, raw):
        record = self.observations['tools'][role]['commands'][command]
        path = self.inputs / record['stdout']['path']
        write(path, raw if isinstance(raw, bytes) else raw.encode('utf-8'))
        record['stdout'] = self.ref(path)
        return self.flush()

    def output(self, name):
        return self.root / name
