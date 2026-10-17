"""Pure CPython builtin facts; this parser never launches or admits a runtime."""

from protocol_contract import KIND, MissingMethod, closed_fields, explicit_path, integer


METHOD = 'python-direct-builtins-v1'
_FIELDS = ('schema_version', 'kind', 'role', 'implementation',
           'version_info', 'implementation_version')
_VERSION_FIELDS = ('major', 'minor', 'micro', 'releaselevel', 'serial')
_LEVELS = ('alpha', 'beta', 'candidate', 'final')


def _version(value):
    closed_fields(value, _VERSION_FIELDS, 'Python builtin version tuple')
    for name in ('major', 'minor', 'micro', 'serial'):
        integer(value[name], 'Python builtin ' + name)
    if type(value['releaselevel']) is not str or value['releaselevel'] not in _LEVELS:
        raise ValueError('Python builtin releaselevel is unknown')
    return '{}.{}.{}'.format(value['major'], value['minor'], value['micro'])


def observed_numeric(value):
    closed_fields(value, _FIELDS, 'Python builtin version')
    integer(value['schema_version'], 'Python builtin schema', 1, 1)
    if value['kind'] != KIND or value['role'] != 'python':
        raise ValueError('Python builtin kind/role differs')
    release = _version(value['version_info'])
    _version(value['implementation_version'])
    if (type(value['implementation']) is not str or
            not 1 <= len(value['implementation']) <= 64):
        raise ValueError('Python implementation requires a bounded name')
    if value['implementation'] != 'cpython':
        raise MissingMethod('windows-runtime-version-python-engine')
    if value['implementation_version'] != value['version_info']:
        raise ValueError('CPython language and implementation versions differ')
    version = value['version_info']
    if version['major'] != 3 or version['minor'] < 9:
        raise ValueError('Reviewed CPython 3.9+ source domain required')
    return release


def validate(value):
    release = observed_numeric(value)
    version = value['version_info']
    if version['releaselevel'] != 'final':
        raise ValueError('Python prerelease is not a final release')
    if version['serial'] != 0:
        raise ValueError('Python final serial must equal zero by project policy')
    return release


def argv(program_path, emitter_path):
    return [explicit_path(program_path, 'Python program'), '-I', '-S', '-B',
            explicit_path(emitter_path, 'Python emitter')]
