#!/usr/bin/env python3
"""Compile a portable guest with explicit retained tools, without a kernel graph."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import sys
import tempfile
import time

import appended_wasm
import process_tree

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'foundation-guest-v1'
EXPORTS = ('foundation_app_abi_v1', 'foundation_app_alloc_v1', 'foundation_app_free_v1',
           'foundation_app_init_v1', 'foundation_app_dispatch_v1', 'foundation_app_step_v1',
           'foundation_app_shutdown_v1')
SOURCE_SUFFIXES = {'.c', '.h', '.cpp', '.cc', '.cxx', '.hpp', '.hh', '.hxx', '.rs',
                   '.toml', '.lock', '.json', '.md', '.txt'}
FORBIDDEN = re.compile(rb'javascript|wasm[-_]bindgen|js[-_]sys|web[-_]sys|node_modules|'
                       rb'package\.json|\.(?:mjs|cjs|js)(?:[^a-zA-Z0-9_]|$)', re.I)
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_MODULE_BYTES = appended_wasm.MAX_MODULE_BYTES
# Keep the actual owners and streams alive until uncertain writers are handled.
_UNCONFIRMED_RUNS = []


def _json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('expected canonical relative path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('expected canonical relative path: ' + value)
    return p


def _regular(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('input must be an unlinked regular file: ' + str(path))


def _unlinked_ancestors(path):
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('linked input or output path is unsupported: ' + str(component))


def _digest(path):
    _regular(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('input changed while hashing: ' + str(path))
    return digest.hexdigest()


def _tree(root, *, source=False):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('input root must be a real directory: ' + str(root))
    rows = {}
    size = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories):
            if (Path(directory) / name).is_symlink():
                raise ValueError('linked input directory is unsupported')
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            _relative(relative)
            if source:
                if path.suffix.lower() not in SOURCE_SUFFIXES or FORBIDDEN.search(relative.encode('utf-8')):
                    raise ValueError('unsupported binary source file: ' + relative)
                size += path.stat().st_size
                if size > MAX_SOURCE_BYTES:
                    raise ValueError('binary source exceeds byte limit')
                if FORBIDDEN.search(path.read_bytes()):
                    raise ValueError('unsupported binary source dependency or reference: ' + relative)
            rows[relative] = {'sha256': _digest(path), 'executable': bool(path.stat().st_mode & 0o111)}
    if not rows:
        raise ValueError('input tree is empty')
    return dict(sorted(rows.items()))


def load_sdk(path, language):
    """Verify the complete dedicated tool tree before any tool is executed."""
    path = Path(path).absolute()
    _unlinked_ancestors(path)
    _regular(path)
    descriptor_bytes = path.read_bytes()
    data = json.loads(descriptor_bytes.decode('utf-8'), object_pairs_hook=_json)
    fields = {'schema_version', 'profile', 'root', 'tools', 'inventory', 'rust_sysroot'}
    if not isinstance(data, dict) or set(data) - fields or data.get('schema_version') != 1 or data.get('profile') != PROFILE:
        raise ValueError('unsupported guest SDK descriptor')
    root_value = data.get('root')
    if not isinstance(root_value, str):
        raise ValueError('guest SDK requires an explicit root')
    root = Path(root_value)
    if not root.is_absolute():
        root = path.parent / _relative(root_value)
    root = root.absolute()
    _unlinked_ancestors(root)
    inventory = data.get('inventory')
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('guest SDK requires a complete inventory')
    for key, value in inventory.items():
        _relative(key)
        if not isinstance(value, dict) or set(value) != {'sha256', 'executable'} or not isinstance(value['executable'], bool) or not re.fullmatch('[0-9a-f]{64}', str(value['sha256'])):
            raise ValueError('invalid guest SDK inventory row')
    if _tree(root) != inventory:
        raise ValueError('guest SDK complete inventory mismatch')
    tools = data.get('tools')
    allowed = {'clang', 'clangxx', 'wasm_ld', 'rustc'}
    required = {'clang', 'wasm_ld'} | ({'clangxx'} if language == 'c++' else {'rustc'} if language == 'rust' else set())
    if not isinstance(tools, dict) or set(tools) - allowed or not required <= set(tools):
        raise ValueError('missing explicitly pinned guest compiler tools for ' + language)
    selected = {}
    for name, relative in tools.items():
        _relative(relative)
        if relative not in inventory or not inventory[relative]['executable']:
            raise ValueError('guest tool is not an executable inventory member: ' + name)
        selected[name] = str(root / relative)
    if language == 'rust':
        sysroot = data.get('rust_sysroot')
        if not sysroot:
            raise ValueError('missing retained Rust wasm32v1-none sysroot; kernel Rust baseline is unchanged')
        _relative(sysroot)
        libroot = root / sysroot / 'lib/rustlib/wasm32v1-none/lib'
        libraries = [p.name for p in libroot.glob('*.rlib')]
        if not any(p.startswith('libcore-') for p in libraries) or not any(p.startswith('libcompiler_builtins-') for p in libraries):
            raise ValueError('missing retained Rust wasm32v1-none target libraries')
        selected['rust_sysroot'] = str(root / sysroot)
    descriptor_sha = hashlib.sha256(descriptor_bytes).hexdigest()
    if _digest(path) != descriptor_sha:
        raise ValueError('guest SDK descriptor changed during verification')
    return root, data, selected, descriptor_sha


def _environment():
    for key, value in os.environ.items():
        if value and (key in {'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'DYLD_INSERT_LIBRARIES',
                             'DYLD_LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH',
                             'LIBRARY_PATH', 'COMPILER_PATH', 'GCC_EXEC_PREFIX', 'CCC_OVERRIDE_OPTIONS',
                             'CLANG_CONFIG_FILE_SYSTEM_DIR', 'CLANG_CONFIG_FILE_USER_DIR'} or
                      (key.startswith(('RUST', 'CARGO_')) and key not in
                       {'RUST_LOG', 'RUST_BACKTRACE', 'RUST_LIB_BACKTRACE', 'CARGO_HOME', 'RUSTUP_HOME'})):
            raise ValueError('ambient compiler override is unsupported: ' + key)
    # No per-run workspace or ambient temporary path is exposed to Rust's
    # env!/option_env! macros. Direct retained compilers need no user home.
    keep = {'SystemRoot', 'SYSTEMROOT', 'WINDIR'} if os.name == 'nt' else set()
    environment = {key: value for key, value in os.environ.items() if key in keep}
    environment.update({'PATH': '', 'HOME': '', 'LC_ALL': 'C', 'LANG': 'C',
                        'SOURCE_DATE_EPOCH': '0', 'TZ': 'UTC'})
    return environment


def _run(argv, cwd, environment):
    log = tempfile.NamedTemporaryFile(prefix='compiler-', suffix='.log', dir=cwd, delete=False)
    owner, retained = None, False
    try:
        owner = process_tree.launch(argv, cwd=str(cwd), stream=log, env=environment)
        try:
            deadline = time.monotonic() + 120
            while owner.poll() is None:
                if time.monotonic() > deadline or os.fstat(log.fileno()).st_size > 1024 * 1024:
                    owner.terminate()
                    raise ValueError('guest compiler exceeded time or output limit')
                time.sleep(0.01)
            code = owner.finish()
            log.seek(0)
            output = log.read(1024 * 1024).decode('utf-8', errors='replace')
            if code:
                raise ValueError('guest compiler failed (' + str(code) + '):\n' + output)
            return output
        finally:
            try:
                owner.close()
            except BaseException as error:
                retained = True
                _UNCONFIRMED_RUNS.append((owner, log))
                raise process_tree.ProcessTreeError(
                    'guest compiler cleanup uncertain; retain output ownership: ' + str(error)) from error
    except process_tree.ProcessTreeError:
        if owner is None:
            retained = True
            _UNCONFIRMED_RUNS.append((owner, log))
        raise
    finally:
        if not retained:
            log.close()
            Path(log.name).unlink()


@contextmanager
def _workspace(parent):
    work = Path(tempfile.mkdtemp(prefix='.foundation-guest-', dir=parent)).resolve()
    retained = False
    try:
        yield work
    except BaseException as error:
        pending, seen = [error], set()
        while pending:
            current = pending.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            if (isinstance(current, process_tree.ProcessTreeError) or
                    'retain output ownership' in str(current)):
                retained = True
                raise process_tree.ProcessTreeError(
                    str(error) + '; retained compiler workspace: ' + str(work)) from error
            pending.extend((current.__cause__, current.__context__))
        raise
    finally:
        if not retained:
            shutil.rmtree(work)


def _binding_sources(root, language):
    _unlinked_ancestors(root)
    if not root.is_dir():
        raise ValueError('guest bindings root must be a real directory: ' + str(root))
    runtime = root / 'sdk/appended/guest.c'
    _unlinked_ancestors(runtime)
    sources = {'guest.c': runtime}
    include = root / 'sdk/appended/include'
    _unlinked_ancestors(include)
    for relative in _tree(include):
        sources['include/' + relative] = include / relative
    for name in ('abi.h', 'provider_abi.h'):
        path = root / 'include/foundation/appended' / name
        _unlinked_ancestors(path)
        sources['include/foundation/appended/' + name] = path
    if language == 'rust':
        rust = root / 'sdk/appended/rust'
        _unlinked_ancestors(rust)
        for relative in _tree(rust):
            sources['rust/' + relative] = rust / relative
        _regular(rust / 'src/lib.rs')
    return sources


def _dependencies(path, root):
    text = re.sub(r'\\\r?\n', ' ', path.read_text(encoding='utf-8'))
    words = []
    # Rust emits several artifact rules and empty per-source rules. A drive
    # letter colon is not a rule separator; escaped filename colons are not.
    for rule in text.splitlines():
        if not rule.strip() or rule.lstrip().startswith('#'):
            continue
        marker = None
        escaped = False
        for index, character in enumerate(rule):
            if character == ':' and not escaped and (index + 1 == len(rule) or rule[index + 1].isspace()):
                marker = index
                break
            escaped = character == '\\' and not escaped
        if marker is None:
            raise ValueError('missing guest dependency inventory')
        words.extend(re.findall(r'(?:\\.|[^\s\\])+', rule[marker + 1:]))
    if not words:
        raise ValueError('empty guest dependency inventory')
    for word in words:
        word = re.sub(r'\\(.)', r'\1', word).replace('$$', '$')
        dependency = Path(word).resolve(strict=True)
        if not dependency.is_relative_to(root):
            raise ValueError('guest compiler read an undeclared dependency: ' + str(dependency))


def _remove_owned(path, identity):
    try:
        current = path.lstat()
        if stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == identity:
            path.unlink()
    except FileNotFoundError:
        pass


def _publish(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o644)
    opened = os.fstat(descriptor)
    identity = opened.st_dev, opened.st_ino
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        _remove_owned(path, identity)
        raise
    return identity


def compile_guest(source, language, sdk, output, receipt, entries=None, memory_pages=4,
                  max_memory_pages=16, *, bindings_root=None):
    helper_sha = _digest(Path(__file__).resolve())
    validator_sha = _digest(Path(appended_wasm.__file__).resolve())
    if language not in ('c', 'c++', 'rust'):
        raise ValueError('unsupported guest language')
    if type(memory_pages) is not int or type(max_memory_pages) is not int or not 2 <= memory_pages <= max_memory_pages <= 256:
        raise ValueError('guest memory limits require 2 <= initial <= maximum <= 256 pages')
    source = Path(source).absolute()
    output, receipt = Path(output).absolute(), Path(receipt).absolute()
    for path in (source, output, receipt):
        _unlinked_ancestors(path)
    if output == receipt or any(p.exists() or p.is_symlink() for p in (output, receipt)):
        raise ValueError('guest output and receipt must be distinct absent paths')
    for destination in (output, receipt):
        if not destination.parent.is_dir() or destination.parent.is_symlink() or destination.is_relative_to(source):
            raise ValueError('guest outputs require existing private directories outside source')
    sources = _tree(source, source=True)
    sdk_root, sdk_data, tools, sdk_sha = load_sdk(sdk, language)
    if output.is_relative_to(sdk_root) or receipt.is_relative_to(sdk_root):
        raise ValueError('guest outputs must not enter retained SDK')
    if entries is None:
        suffixes = {'.c'} if language == 'c' else {'.cpp', '.cc', '.cxx'} if language == 'c++' else {'.rs'}
        entries = [p for p in sources if Path(p).suffix in suffixes]
    if not entries or len(entries) > 64 or len(set(entries)) != len(entries):
        raise ValueError('guest compilation requires one to 64 distinct entry sources')
    for entry in entries:
        _relative(entry)
        expected = {'.c'} if language == 'c' else {'.cpp', '.cc', '.cxx'} if language == 'c++' else {'.rs'}
        if entry not in sources or Path(entry).suffix not in expected:
            raise ValueError('entry does not match selected guest language: ' + entry)
    if language == 'rust' and len(entries) != 1:
        raise ValueError('Rust guest requires one explicit crate root')
    bindings_root = ROOT if bindings_root is None else Path(bindings_root).absolute()
    sdk_sources = _binding_sources(bindings_root, language)
    bindings = {name: _digest(p) for name, p in sorted(sdk_sources.items())}
    commands = []
    with _workspace(output.parent) as work:
        environment = _environment()
        # The mappings apply to source, bindings and compiler target libraries.
        # '=' cannot be escaped in the shared compiler prefix-map syntax.
        path_maps = ((work, '/foundation/guest/work'), (sdk_root, '/foundation/guest/sdk'))
        if any('=' in str(original) for original, _ in path_maps):
            raise ValueError('guest deterministic prefix maps require workspace and SDK paths without "="')
        shutil.copytree(source, work / 'source')
        for relative, original in sdk_sources.items():
            destination = work / 'bindings' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
        if _tree(work / 'source', source=True) != sources:
            raise ValueError('guest source changed during snapshot')
        if any(_digest(work / 'bindings' / name) != digest for name, digest in bindings.items()):
            raise ValueError('guest bindings changed during snapshot')
        # Source identity binds bytes and executable bits, not the original
        # filesystem dates. __TIMESTAMP__ must observe the same snapshot date.
        for relative in sources:
            os.utime(work / 'source' / relative, ns=(0, 0))
        for relative in bindings:
            os.utime(work / 'bindings' / relative, ns=(0, 0))
        flags = ['--target=wasm32-unknown-unknown', '--no-default-config', '-ffreestanding', '-nostdinc',
                 '-fno-builtin', '-O2', '-fvisibility=hidden', '-ffunction-sections', '-fdata-sections',
                 '-mno-bulk-memory', '-mno-sign-ext', '-mno-nontrapping-fptoint', '-mno-simd128',
                 '-mno-atomics', '-mno-reference-types', '-mno-multivalue', '-mno-tail-call',
                 *[option + '=' + str(original) + '=' + logical
                   for original, logical in path_maps
                   for option in ('-ffile-prefix-map', '-fmacro-prefix-map', '-fdebug-prefix-map')],
                 '-I', str(work / 'bindings/include'), '-I', str(work / 'source')]
        runtime_flags = ['-std=c11']
        if language == 'rust':
            runtime_flags.append('-DFOUNDATION_GUEST_REQUIRE_HOOKS')
        files = [('bindings/guest.c', tools['clang'], runtime_flags)]
        if language != 'rust':
            files += [('source/' + entry, tools['clangxx' if language == 'c++' else 'clang'],
                       ['-std=c++17', '-fno-exceptions', '-fno-rtti', '-fno-threadsafe-statics'] if language == 'c++' else ['-std=c11']) for entry in entries]
        objects = []
        for number, (entry, compiler, extra) in enumerate(files):
            obj, dep = work / ('input' + str(number) + '.o'), work / ('input' + str(number) + '.d')
            command = [compiler, *flags, *extra, '-MD', '-MT', 'foundation-guest', '-MF', str(dep), '-c', str(work / entry), '-o', str(obj)]
            commands.append(command)
            _run(command, work, environment)
            _dependencies(dep, work)
            objects.append(str(obj))
        if language == 'rust':
            common = [tools['rustc'], '--edition=2021', '--target=wasm32v1-none', '--sysroot', tools['rust_sysroot'],
                      *['--remap-path-prefix=' + str(original) + '=' + logical
                        for original, logical in path_maps],
                      '-Cpanic=abort', '-Clto=no', '-Copt-level=2', '-Ccodegen-units=1', '-Cembed-bitcode=no',
                      '-Ctarget-feature=-bulk-memory,-sign-ext,-nontrapping-fptoint,-simd128,-atomics,-reference-types,-multivalue,-tail-call']
            library = work / 'libfoundation_appended_guest.rlib'
            dep = work / 'rust-sdk.d'
            command = [*common, '--crate-name=foundation_appended', '--crate-type=rlib',
                       '--emit=link,dep-info=' + str(dep), str(work / 'bindings/rust/src/lib.rs'), '-o', str(library)]
            commands.append(command); _run(command, work, environment)
            _dependencies(dep, work)
            archive = work / 'application.a'
            dep = work / 'rust-application.d'
            command = [*common, '--crate-name=foundation_appended_application', '--crate-type=staticlib',
                       '--extern', 'foundation_appended=' + str(library), '--emit=link,dep-info=' + str(dep),
                       str(work / 'source' / entries[0]), '-o', str(archive)]
            commands.append(command); _run(command, work, environment)
            _dependencies(dep, work)
            # The required hooks pull the application's real object and its
            # dependencies. Do not force unrelated prebuilt archive members into
            # this profile (some Rust target archives also contain native ones).
            objects.append(str(archive))
        module = work / 'module.wasm'
        command = [tools['wasm_ld'], '--no-entry', '--export-memory', '--gc-sections', '--strip-all',
                   '--compress-relocations', '--initial-memory=' + str(memory_pages * 65536),
                   '--max-memory=' + str(max_memory_pages * 65536), '-z', 'stack-size=32768',
                   *['--export=' + name for name in EXPORTS], *objects, '-o', str(module)]
        commands.append(command); _run(command, work, environment)
        if module.stat().st_size > MAX_MODULE_BYTES:
            raise ValueError('guest module exceeds byte limit')
        module_bytes = module.read_bytes()
        audit = appended_wasm.validate_module(module_bytes)
        if (_tree(source, source=True) != sources or _tree(sdk_root) != sdk_data['inventory'] or
                _digest(Path(sdk).absolute()) != sdk_sha or _digest(Path(__file__).resolve()) != helper_sha or
                _digest(Path(appended_wasm.__file__).resolve()) != validator_sha or
                {name: _digest(path) for name, path in sorted(
                    _binding_sources(bindings_root, language).items())} != bindings):
            raise ValueError('guest inputs changed during compilation')
        # Omit private scratch paths from stable receipt commands.
        normalized = [[part.replace(str(work), '$WORK') for part in argv] for argv in commands]
        result = {'schema_version': 1, 'profile': PROFILE, 'language': language,
                  'sources': sources, 'bindings': bindings, 'sdk_descriptor_sha256': sdk_sha,
                  'sdk_inventory_sha256': hashlib.sha256(_canonical(sdk_data['inventory'])).hexdigest(),
                  'compiler_helper_sha256': helper_sha,
                  'validator_sha256': validator_sha,
                  'host': {'system': platform.system(), 'machine': platform.machine()},
                  'commands': normalized, 'module': {'sha256': hashlib.sha256(module_bytes).hexdigest(),
                                                   'bytes': len(module_bytes)}, 'audit': audit}
        published = _publish(output, module_bytes)
        try:
            _publish(receipt, _canonical(result))
        except BaseException:
            _remove_owned(output, published)
            raise
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    command = commands.add_parser('compile', help='compile only a portable application module')
    command.add_argument('--source', required=True)
    command.add_argument('--language', choices=('c', 'c++', 'rust'), required=True)
    command.add_argument('--sdk', required=True, help='explicit retained guest SDK descriptor')
    command.add_argument('--bindings-root', help='project source root containing the guest bindings (default: current project)')
    command.add_argument('--output', required=True)
    command.add_argument('--receipt', required=True)
    command.add_argument('--entry', action='append')
    command.add_argument('--memory-pages', type=int, default=4)
    command.add_argument('--max-memory-pages', type=int, default=16)
    args = parser.parse_args(argv)
    try:
        result = compile_guest(args.source, args.language, args.sdk, args.output, args.receipt,
                               args.entry, args.memory_pages, args.max_memory_pages,
                               bindings_root=args.bindings_root)
        print('guest module ' + result['module']['sha256'])
        return 0
    except (ValueError, OSError, process_tree.ProcessTreeError) as error:
        print('appended compile: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
