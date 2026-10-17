#!/usr/bin/env python3
"""Validate independent application selections without loading a payload toolchain.

This is a project-selection contract, not evidence that a selected runtime or a
portable module is available. Missing configuration retains the ordinary compiled
application. Merely placing example directories in a checkout enables nothing.
"""
import argparse
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import unicodedata


CONFIG_NAME = 'foundation-project.json'
SCHEMA_VERSION = 1
MAX_CONFIG_BYTES = 1024 * 1024
MODES = ('neither', 'web', 'binary', 'both')
PROFILES = ('auto', 'minimal', 'web', 'binary', 'both')
KERNEL_SELECTIONS = ('project', 'foundation')
PROFILE_CAPABILITIES = {
    'minimal': frozenset(), 'web': frozenset({'web'}),
    'binary': frozenset({'binary'}), 'both': frozenset({'web', 'binary'}),
}
_PROTECTED_PARTS = frozenset({'.git', '.agent-work', '.agents', '.codex'})
_RESERVED_NAMES = frozenset({'con', 'prn', 'aux', 'nul',
                           *('com' + str(i) for i in range(1, 10)),
                           *('lpt' + str(i) for i in range(1, 10)),
                           *('com' + i for i in '¹²³'), *('lpt' + i for i in '¹²³')})


class ProjectError(ValueError):
    """The requested project selection cannot be used safely or unambiguously."""


@dataclass(frozen=True)
class ComponentConfig:
    enabled: bool
    source: str
    entry: object = None


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    configured: bool
    application_id: str
    application_name: str
    application_version: str
    web: ComponentConfig
    binary: ComponentConfig
    startup_primary: str
    kernel_selection: str
    kernel_profile: str
    _source_bytes: object = field(default=None, repr=False, compare=False)

    @property
    def mode(self):
        return ('both' if self.web.enabled and self.binary.enabled else
                'web' if self.web.enabled else 'binary' if self.binary.enabled else 'neither')

    @property
    def required_profile(self):
        return 'minimal' if self.mode == 'neither' else self.mode

    @property
    def selected_profile(self):
        return self.required_profile if self.kernel_profile == 'auto' else self.kernel_profile

    @property
    def data(self):
        """Return an owning JSON document; callers cannot mutate this selection."""
        web = {'enabled': self.web.enabled, 'source': self.web.source}
        if self.web.entry is not None:
            web['entry'] = self.web.entry
        return {
            'schema_version': SCHEMA_VERSION,
            'application': {'id': self.application_id, 'name': self.application_name,
                            'version': self.application_version},
            'appended': {'web': web, 'binary': {'enabled': self.binary.enabled,
                                              'source': self.binary.source}},
            'startup': {'primary': self.startup_primary},
            'kernel': {'selection': self.kernel_selection, 'profile': self.kernel_profile},
        }

    def inspect(self):
        return {'configured': self.configured, 'mode': self.mode,
                'required_profile': self.required_profile,
                'selected_profile': self.selected_profile,
                'readiness': {'web': 'unverified' if self.web.enabled else 'disabled',
                              'binary': 'unverified' if self.binary.enabled else 'disabled'},
                'project': self.data}


def default_document():
    """The foundation's ordinary application; this function performs no I/O."""
    return {
        'schema_version': SCHEMA_VERSION,
        'application': {'id': 'org.software-foundation.foundation', 'name': 'Foundation',
                        'version': '0.1.0'},
        'appended': {'web': {'enabled': False, 'source': 'src-web-appended'},
                     'binary': {'enabled': False, 'source': 'src-bin-appended'}},
        'startup': {'primary': 'compiled'},
        'kernel': {'selection': 'project', 'profile': 'auto'},
    }


def _object(value, name, required, optional=()):
    if not isinstance(value, dict):
        raise ProjectError(name + ' must be an object')
    unknown = set(value) - set(required) - set(optional)
    missing = set(required) - set(value)
    if unknown:
        raise ProjectError(name + ' has unknown fields: ' + ', '.join(sorted(map(str, unknown))))
    if missing:
        raise ProjectError(name + ' is missing fields: ' + ', '.join(sorted(missing)))
    return value


def _text(value, name, limit=256):
    if (not isinstance(value, str) or not value or value != value.strip() or
            len(value) > limit or any(unicodedata.category(c).startswith('C') for c in value) or
            len(value.encode('utf-8')) > limit):
        raise ProjectError(name + ' must be nonempty bounded text without control characters')
    return value


def _choice(value, name, choices):
    if not isinstance(value, str) or value not in choices:
        raise ProjectError(name + ' must be one of: ' + ', '.join(choices))
    return value


def relative_path(value, name='path'):
    """Require canonical portable repository-relative spelling without I/O."""
    _text(value, name, limit=4096)
    parts = value.split('/')
    if (PurePosixPath(value).is_absolute() or '\\' in value or ':' in value or
            any(part in ('', '.', '..') for part in parts)):
        raise ProjectError(name + ' must be a canonical portable relative path')
    for part in parts:
        if (part.endswith(('.', ' ')) or any(c in '<>"|?*' for c in part) or
                part.casefold().split('.')[0] in _RESERVED_NAMES or
                part.casefold() in _PROTECTED_PARTS):
            raise ProjectError(name + ' contains a reserved or nonportable path component')
    return value


def _root(root):
    try:
        result = Path(root).resolve(strict=True)
        if not result.is_dir():
            raise ProjectError('project root must be an existing directory')
        return result
    except OSError as error:
        raise ProjectError('project root is unavailable: ' + str(error)) from error


def _existing_path(root, relative, *, directory, label):
    path = root
    try:
        for part in relative.split('/'):
            path = path / part
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ProjectError(label + ' must not use symbolic links')
        if not (stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)):
            raise ProjectError(label + (' must be a directory' if directory else ' must be a regular file'))
    except OSError as error:
        raise ProjectError(label + ' is unavailable: ' + relative) from error
    return path


def validate_document(data, root, *, check_sources=True, configured=True):
    """Validate schema and selection, inspecting only enabled roots when requested.

    A binary source selection deliberately does not assert module readiness. A
    pack operation must separately require and verify a produced portable module.
    `check_sources=False` supports identity/classification of a source snapshot;
    it never establishes that enabled sources or runtime implementations exist.
    """
    root = _root(root)
    _object(data, 'project', ('schema_version', 'application', 'appended', 'startup', 'kernel'))
    if type(data['schema_version']) is not int or data['schema_version'] != SCHEMA_VERSION:
        raise ProjectError('unsupported foundation-project schema_version')
    app = _object(data['application'], 'application', ('id', 'name', 'version'))
    app_id = _text(app['id'], 'application.id')
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+', app_id):
        raise ProjectError('application.id must be a lowercase namespaced identifier')
    app_name = _text(app['name'], 'application.name')
    app_version = _text(app['version'], 'application.version', 128)
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?'
                        r'(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?', app_version):
        raise ProjectError('application.version must have a major.minor.patch version')
    appended = _object(data['appended'], 'appended', ('web', 'binary'))
    components = {}
    for name in ('web', 'binary'):
        component = _object(appended[name], 'appended.' + name, ('enabled', 'source'),
                            ('entry',) if name == 'web' else ())
        if type(component['enabled']) is not bool:
            raise ProjectError('appended.' + name + '.enabled must be a boolean')
        source = relative_path(component['source'], 'appended.' + name + '.source')
        if source.casefold() == CONFIG_NAME:
            raise ProjectError('an appended source cannot be the project configuration')
        entry = relative_path(component['entry'], 'appended.web.entry') if 'entry' in component else None
        if entry is not None and (not entry.isascii() or len(entry) > 240 or len(entry.split('/')) > 16):
            raise ProjectError('appended.web.entry exceeds the portable resource path profile')
        if name == 'web' and component['enabled'] and entry is None:
            raise ProjectError('enabled web source requires a declared entry')
        components[name] = ComponentConfig(component['enabled'], source, entry)
    web, binary = components['web'], components['binary']
    left = unicodedata.normalize('NFC', web.source).casefold().split('/')
    right = unicodedata.normalize('NFC', binary.source).casefold().split('/')
    if left[:len(right)] == right or right[:len(left)] == left:
        raise ProjectError('web and binary source roots must not overlap or alias')
    startup = _object(data['startup'], 'startup', ('primary',))
    primary = _choice(startup['primary'], 'startup.primary', ('compiled', 'web', 'binary'))
    if primary != 'compiled' and not components[primary].enabled:
        raise ProjectError('startup.primary selects a disabled component')
    kernel = _object(data['kernel'], 'kernel', ('selection', 'profile'))
    selection = _choice(kernel['selection'], 'kernel.selection', KERNEL_SELECTIONS)
    profile = _choice(kernel['profile'], 'kernel.profile', PROFILES)
    required = frozenset(name for name, component in components.items() if component.enabled)
    if profile != 'auto' and not required.issubset(PROFILE_CAPABILITIES[profile]):
        raise ProjectError('kernel.profile lacks an enabled appended capability')
    if check_sources:
        for name, component in components.items():
            if not component.enabled:
                continue
            _existing_path(root, component.source, directory=True, label='enabled ' + name + ' source')
            if component.entry is not None:
                _existing_path(root, component.source + '/' + component.entry,
                               directory=False, label='web entry')
    return ProjectConfig(root, configured, app_id, app_name, app_version, web, binary,
                         primary, selection, profile)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProjectError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ProjectError('nonstandard JSON constant: ' + value)


def _read_config(path):
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ProjectError('project configuration is too large')
        return (json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=_invalid_constant), raw)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ProjectError('cannot read project configuration: ' + str(error)) from error


def load_project(root, *, config_path=None, check_sources=True):
    root = _root(root)
    path = root / CONFIG_NAME
    if config_path is not None and Path(os.path.abspath(config_path)) != path:
        raise ProjectError('project configuration must be ' + str(path))
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return validate_document(default_document(), root, check_sources=check_sources, configured=False)
    except OSError as error:
        raise ProjectError('cannot inspect project configuration: ' + str(error)) from error
    if not stat.S_ISREG(metadata.st_mode):
        raise ProjectError('project configuration must be a regular file without symbolic links')
    data, raw = _read_config(path)
    return replace(validate_document(data, root, check_sources=check_sources), _source_bytes=raw)


def set_mode(root, mode, *, create=False, application=None, primary=None, profile=None,
             kernel_selection=None, web_source=None, binary_source=None, web_entry=None):
    """Make reviewable working-tree settings; never change a Git snapshot or roots.

    The caller must exclude concurrent writers of an existing configuration.
    Snapshot checks preserve observed intervening edits; replace is not a
    filesystem compare-and-swap operation.
    """
    _choice(mode, 'mode', MODES)
    current = load_project(root, check_sources=False)
    if not current.configured and not create:
        raise ProjectError('no project configuration exists; explicitly create one')
    path = current.root / CONFIG_NAME
    previous = current._source_bytes
    data = current.data
    if application is not None:
        _object(application, 'application overrides', (), ('id', 'name', 'version'))
        data['application'].update(application)
    for name in ('web', 'binary'):
        data['appended'][name]['enabled'] = mode in (name, 'both')
    if web_source is not None:
        data['appended']['web']['source'] = web_source
    if binary_source is not None:
        data['appended']['binary']['source'] = binary_source
    if web_entry is not None:
        data['appended']['web']['entry'] = web_entry
    elif data['appended']['web']['enabled'] and 'entry' not in data['appended']['web']:
        data['appended']['web']['entry'] = 'index.html'
    if profile is not None:
        data['kernel']['profile'] = profile
    if kernel_selection is not None:
        data['kernel']['selection'] = kernel_selection
    if primary is not None:
        data['startup']['primary'] = primary
    elif current.startup_primary != 'compiled' and not data['appended'][current.startup_primary]['enabled']:
        data['startup']['primary'] = 'compiled'
    selected = validate_document(data, current.root)
    encoded = (json.dumps(selected.data, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.' + CONFIG_NAME + '-', dir=current.root,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if previous is None:
            # An atomic no-clobber creation keeps an independently appearing file.
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise ProjectError('project configuration appeared during configuration') from error
        else:
            if path.is_symlink() or path.read_bytes() != previous:
                raise ProjectError('project configuration changed during configuration')
            temporary.replace(path)
    except OSError as error:
        raise ProjectError('cannot write project configuration: ' + str(error)) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect_parser = sub.add_parser('inspect', help='validate selections; no runtime readiness claim')
    inspect_parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    inspect_parser.add_argument('--json', action='store_true', help='emit the selection as JSON')
    configure_parser = sub.add_parser('configure', help='write reviewable project settings')
    configure_parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    configure_parser.add_argument('--mode', choices=MODES, required=True)
    configure_parser.add_argument('--application-id')
    configure_parser.add_argument('--name')
    configure_parser.add_argument('--version')
    configure_parser.add_argument('--primary', choices=('compiled', 'web', 'binary'))
    configure_parser.add_argument('--kernel-profile', choices=PROFILES)
    configure_parser.add_argument('--kernel-selection', choices=KERNEL_SELECTIONS)
    configure_parser.add_argument('--web-source')
    configure_parser.add_argument('--binary-source')
    configure_parser.add_argument('--web-entry')
    args = parser.parse_args(argv)
    try:
        if args.command == 'configure':
            overrides = {key: value for key, value in
                         (('id', args.application_id), ('name', args.name), ('version', args.version))
                         if value is not None}
            selected = set_mode(args.root, args.mode, create=True, application=overrides,
                                primary=args.primary, profile=args.kernel_profile,
                                kernel_selection=args.kernel_selection, web_source=args.web_source,
                                binary_source=args.binary_source, web_entry=args.web_entry)
        else:
            selected = load_project(args.root)
        if args.command == 'inspect' and args.json:
            print(json.dumps(selected.inspect(), indent=2, sort_keys=True))
        else:
            print('Project mode: ' + selected.mode)
            print('Kernel profile: ' + selected.selected_profile)
            if args.command == 'configure':
                print('Working-tree configuration: ' + str(selected.root / CONFIG_NAME))
            if selected.mode != 'neither':
                print('Payload/runtime readiness remains unverified; no toolchain was invoked.')
    except ProjectError as error:
        parser.exit(1, 'project configuration error: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
