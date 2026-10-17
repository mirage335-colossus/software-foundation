"""Fixed documented MSBuild property observation; no tool or native I/O.

This component does not issue a version capability. The actual collector must
own the selected program/runtime/project, native Job and whole original log.
"""

import hashlib
import json
from pathlib import PureWindowsPath
import re


METHOD = 'msbuild-reserved-properties-json-v1'
PROJECT_BYTES = b'<Project />\n'
PROJECT_SHA256 = hashlib.sha256(PROJECT_BYTES).hexdigest()
PROPERTIES = ('MSBuildVersion', 'MSBuildFileVersion', 'MSBuildSemanticVersion')
MAX_LOG_BYTES = 16384
_NUMBER = r'(?:0|[1-9][0-9]{0,4})'
_TRIPLE = _NUMBER + r'\.' + _NUMBER + r'\.' + _NUMBER
_SEMVER = re.compile(r'(' + _TRIPLE + r')(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
             *('COM' + str(index) for index in range(1, 10)),
             *('LPT' + str(index) for index in range(1, 10))}


class UnsupportedFormat(ValueError):
    pass


def _path(value):
    if (type(value) is not str or not 3 < len(value) <= 4096 or
            re.match(r'^[A-Z]:/', value) is None or
            PureWindowsPath(value).as_posix() != value or '\\' in value or
            any(ord(c) < 32 or ord(c) > 126 for c in value) or
            any(part in ('', '.', '..') or part.endswith((' ', '.')) or
                any(c in ':*?"<>|;' for c in part) or '~' in part or
                part.split('.')[0].upper() in _RESERVED
                for part in value[3:].split('/'))):
        raise ValueError('Canonical finite local Windows method path required')
    return value


def msbuild_argv(program, project):
    _path(program); _path(project)
    if program.rsplit('/', 1)[-1] != 'MSBuild.exe':
        raise ValueError('Exact selected MSBuild.exe path required')
    return [program, '-nologo', '-noAutoResponse', '-nodeReuse:false',
            '-maxCpuCount:1', '-verbosity:quiet',
            '-getProperty:' + ','.join(PROPERTIES), project]


def verify_project(raw):
    if type(raw) is not bytes or raw != PROJECT_BYTES:
        raise ValueError('Exact task-free, import-free, SDK-free source project required')
    return PROJECT_SHA256


def _numbers(value, count, label):
    if type(value) is not str:
        raise UnsupportedFormat('Original ' + label + ' must be a numeric string')
    if re.fullmatch(r'\.'.join([_NUMBER] * count), value) is None:
        raise UnsupportedFormat('Unsupported original ' + label + ' numeric format')
    result = tuple(int(part) for part in value.split('.'))
    if any(part > 65535 for part in result):
        raise UnsupportedFormat('Original ' + label + ' component exceeds fixed-file range')
    return result


def extract_msbuild(raw):
    """Derive independent numeric/final facts from the whole original JSON log."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_LOG_BYTES:
        raise UnsupportedFormat('Whole original MSBuild JSON log exceeds its bound')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise UnsupportedFormat('Duplicate original MSBuild JSON field')
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(UnsupportedFormat('Invalid MSBuild JSON number')))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, UnsupportedFormat):
            raise
        raise UnsupportedFormat('Unsupported whole original MSBuild JSON output') from error
    if (type(value) is not dict or set(value) != {'Properties'} or
            type(value['Properties']) is not dict or set(value['Properties']) != set(PROPERTIES)):
        raise UnsupportedFormat('Exact three reserved MSBuild property results required')
    properties = value['Properties']
    release = _numbers(properties['MSBuildVersion'], 3, 'MSBuildVersion')
    version = _numbers(properties['MSBuildFileVersion'], 4, 'MSBuildFileVersion')
    semantic = properties['MSBuildSemanticVersion']
    match = _SEMVER.fullmatch(semantic) if type(semantic) is str else None
    if match is None:
        raise UnsupportedFormat('Final MSBuild semver required; prereleases unsupported')
    semantic_core = _numbers(match.group(1), 3, 'MSBuildSemanticVersion')
    if release != version[:3] or release != semantic_core:
        raise UnsupportedFormat('Original reserved MSBuild numeric versions do not join')
    if release < (17, 8, 0):
        raise UnsupportedFormat('Supported original MSBuild17.8 or newer is required')
    return {'version': '.'.join(map(str, version)),
            'release_version': '.'.join(map(str, release)),
            'semantic_version': semantic}
