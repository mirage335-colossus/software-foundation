"""Private fixed version-method adapter; declarations and numeric parsing only.

Importing this module loads only the standard library. Calls may lazily read and
verify the finite frozen parser/helper/emitter source closure below; no selected
program, emitter, native Workspace, SDK, runtime or archive body is read or run.
No pure result authenticates a native observation or an original sealed log.

Source references are relative to this file's directory. The issuer must pin this
adapter separately and admit actual program/emitter identities before using its
literal argv. Path checks here are declarations, never physical path admission.
Private Python namespaces avoid sys.path/sys.modules dependency substitution;
this protocol is not a sandbox against mutation of the running controller code.
"""

import builtins
import hashlib
import os
from pathlib import Path
import stat
import types


ROLE_ORDER = ('compiler', 'linker', 'archiver', 'resource_compiler',
              'manifest_tool', 'cmake', 'ninja', 'python', 'perl', 'ruby', 'gperf',
              'nmake', 'msbuild')
_METHODS = {'cmake': 'cmake-capabilities-3.31-final-v1',
            'python': 'python-direct-builtins-v1',
            'perl': 'perl-builtin-version-series-only-v1',
            'ruby': 'ruby-direct-builtins-v1'}
_FINAL_GAPS = {'perl': 'windows-runtime-version-perl-final-release',
               'ruby': 'windows-runtime-version-ruby-final-release'}
_HERE = Path(__file__).resolve().parent
_BUILTINS = 'builtins/'
_CMAKE = 'cmake_version.py'
_PROOF = '../appended_engine_windows_dependency_proof.py'

# path, exact byte count, independent SHA256 from immutable release/validation.
_SOURCE_ROWS = {
    'cmake': (_CMAKE, 11623, '871c7fe6a8cda6d511aa52377ec024b7ccce5972a8fef3fe2247d9c672fd4d10'),
    'proof': (_PROOF, 35435, '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747'),
    'protocol': (_BUILTINS + 'builtins_protocol.py', 5438,
                 'c334b013d3fcc024784182a461f3ee5837b006629da598788df4fe05fb251cc6'),
    'contract': (_BUILTINS + 'protocol_contract.py', 1454,
                 '478dfa28a66fd3023dbf24803e3b8ef48ec35c12baaf8f3f6947a1c2d0a49d31'),
    'python': (_BUILTINS + 'python/parser.py', 2400,
               '014b378ed23c525dc42ac3719ef0e05db98ef22086b83f3bf375d7b0faaa8ba2'),
    'perl': (_BUILTINS + 'perl/parser.py', 1892,
             '05a3c978918b050b5695116675e9dd7d1dbf3748876892d14876aabd2f65ad75'),
    'ruby': (_BUILTINS + 'ruby/parser.py', 3014,
             '45b43a5afcb97c177b0804c920f7c05fd5ade1447e3d75c799587af42d06ac1a'),
    'python_emitter': (_BUILTINS + 'python/emitter.py', 1799,
                       '90067e97239cacb1c5cc0d45a53d00df4060207cfc6e17e2a626f95c530573ab'),
    'perl_emitter': (_BUILTINS + 'perl/emitter.pl', 806,
                     'bd80d964e46d45891b644f9a1018f7bdc7569105021b186407aca093bfe4e137'),
    'ruby_emitter': (_BUILTINS + 'ruby/emitter.rb', 1285,
                     'e8b4a1fea4b6de2fe2853d75706c1ff34aa3f0a384db4dff5e2c5230778c82ff'),
}
_BUILTIN_HELPERS = ('protocol', 'contract', 'python', 'perl', 'ruby')
_STDLIB = frozenset(('copy', 'hashlib', 'json', 're', 'unicodedata'))


class MissingMethod(ValueError):
    """Named missing source semantics; never an observed incompatible release."""


def method_for(role):
    """Return one fixed source-owned method; nine roles remain missing source."""
    if type(role) is not str or not 1 <= len(role) <= 128:
        raise ValueError('Bounded exact version role required')
    if role not in _METHODS:
        raise MissingMethod('windows-tool-version-method:' + role)
    return _METHODS[role]


def final_method_gaps():
    """Return all eleven known final-method gaps in the fixed thirteen-role order."""
    return tuple('windows-tool-version-method:' + role if role not in _METHODS else
                 _FINAL_GAPS[role] for role in ROLE_ORDER
                 if role not in _METHODS or role in _FINAL_GAPS)


def _closure(role):
    method_for(role)
    if role == 'cmake':
        return ('cmake', 'proof')
    # The frozen protocol eagerly imports all three parsers. All are its actual
    # source closure, although only the selected emitter belongs to this role.
    return _BUILTIN_HELPERS + (role + '_emitter',)


def source_refs(role):
    """Owned finite source refs; no reads, own hash, generated log or product refs."""
    return [{'path': _SOURCE_ROWS[name][0], 'sha256': _SOURCE_ROWS[name][2]}
            for name in _closure(role)]


def _read_source(name):
    relative, count, expected_pin = _SOURCE_ROWS[name]
    path = _HERE / relative
    # These are fixed candidate source reads, not native retained-input admission.
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != count or count > 131072:
            raise ValueError('Frozen method source size/type differs: ' + relative)
        raw = stream.read(count + 1)
        after = os.fstat(stream.fileno())
    identity = lambda record: (record.st_dev, record.st_ino, record.st_size,
                               record.st_mtime_ns, record.st_ctime_ns)
    if (len(raw) != count or identity(before) != identity(after) or
            hashlib.sha256(raw).hexdigest() != expected_pin):
        raise ValueError('Frozen method source identity/pin differs: ' + relative)
    return raw


def _load(role):
    """Load only verified immutable helpers using fixed isolated import routing."""
    names = _closure(role)
    sources = {name: _read_source(name) for name in names}
    modules = {}
    packages = {}
    original_import = builtins.__import__

    def selected_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0:
            raise ImportError('Frozen method source cannot request relative imports')
        if name == '__future__' and tuple(fromlist) == ('annotations',):
            return original_import(name, globals, locals, fromlist, level)
        if name == 'appended_engine_windows_dependency_proof':
            return module('proof')
        if name == 'protocol_contract':
            return module('contract')
        if name in ('python', 'perl', 'ruby'):
            if tuple(fromlist) != ('parser',):
                raise ImportError('Frozen builtin import must select its fixed parser')
            if name not in packages:
                package = types.ModuleType('_frozen_version_' + name)
                package.parser = module(name)
                packages[name] = package
            return packages[name]
        if name in _STDLIB:
            return original_import(name, globals, locals, fromlist, level)
        raise ImportError('Unreviewed frozen-method import: ' + name)

    def module(name):
        if name not in sources or name.endswith('_emitter'):
            raise ImportError('Source outside selected parser/helper closure')
        if name not in modules:
            selected = types.ModuleType('_frozen_version_' + name)
            selected.__file__ = str(_HERE / _SOURCE_ROWS[name][0])
            selected.__builtins__ = {**vars(builtins), '__import__': selected_import}
            # A private incomplete module cannot escape this local closure on a
            # failed import. Nothing is installed in the process module registry.
            modules[name] = selected
            exec(compile(sources[name], selected.__file__, 'exec'), vars(selected))
        return modules[name]

    return module('cmake' if role == 'cmake' else 'protocol')


def _path(value, label):
    # Literal argv cannot turn an emitter path into an interpreter option. This
    # bounded absolute declaration is still not a physical/native path admission.
    if (type(value) is not str or not 4 <= len(value) <= 4096 or not value.isascii() or
            not 'A' <= value[0] <= 'Z' or value[1:3] != ':/' or
            any(ord(c) < 32 or ord(c) == 127 or c in '\\;"$@~<>|?*' for c in value) or
            any(not part or part in ('.', '..') or part.endswith((' ', '.')) or ':' in part
                for part in value[3:].split('/'))):
        raise ValueError('Explicit canonical Windows ' + label + ' path required')
    return value


def argv(role, program_path, emitter_path=None):
    """Return the fixed literal reviewed argv; never launch or read selected paths."""
    method = method_for(role)
    program_path = _path(program_path, 'program')
    if program_path.rsplit('/', 1)[-1] != role + '.exe':
        raise ValueError('Selected version program basename/role differs')
    if role == 'cmake':
        if emitter_path is not None:
            raise ValueError('CMake capabilities takes no emitter')
        return [program_path, '-E', 'capabilities']
    emitter_path = _path(emitter_path, 'emitter')
    selected = _load(role)
    try:
        return selected.version_argv(role, method, program_path, emitter_path)
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error


def extract(role, method, raw_log, *, final=True):
    """Derive an independent numeric release from the frozen whole-log grammar.

    No expected/declared version is accepted. Perl/Ruby final extraction retains
    its named MissingMethod; numeric-only extraction requires explicit final=False.
    """
    selected_method = method_for(role)
    if type(method) is not str or method != selected_method:
        raise MissingMethod('windows-tool-version-method:' + role)
    if type(final) is not bool:
        raise ValueError('Exact final-method selector required')
    selected = _load(role)
    try:
        if role == 'cmake':
            return selected.extract_observed_version(role, method, raw_log)
        if final:
            return selected.parse_final_builtin_version(role, method, raw_log)
        return selected.parse_numeric_observation(role, method, raw_log)
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error
