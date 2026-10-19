#!/usr/bin/env python3
"""Prepare a new document source group from pinned retained source inputs.

This copies source inputs only. It never finds or executes SDK/build programs,
extracts a supplier, produces runtime evidence or makes a group eligible.
"""
import argparse
import builtins
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

RECIPE_ROOT = 'recipes/webkitwasm-document-v2'
KIND = 'foundation-document-v2-source-assembly-v1'
MAX_INPUTS = 4096
MAX_DIRECTORIES = MAX_INPUTS * 8
MAX_SOURCE_BYTES = 8 * 1024 * 1024 * 1024
MAX_SMALL_BYTES = 32 * 1024 * 1024
THEME_SOURCE = 'source/engine/Source/WebCore/rendering/emscripten/RenderThemeEmscripten.cpp'
THEME_SOURCE_PATH = ('recipes/webkitwasm-document-v2/overlays/editor/engine/'
    'Source/WebCore/rendering/emscripten/RenderThemeEmscripten.cpp')
THEME_SOURCE_SHA256 = 'b6720505415c23279a3dca6f1e11717260797bc45f64d3a4f29c2233f335cd81'
THEME_SOURCE_BYTES = 625


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ordinary(path, *, directory=False):
    if os.name != 'posix':
        raise ValueError('Source assembly requires the qualified POSIX filesystem adapter')
    path = Path(os.path.abspath(os.fspath(path)))
    for part in reversed((path, *path.parents)):
        state = part.lstat()
        if stat.S_ISLNK(state.st_mode):
            raise ValueError('Linked source path or parent: ' + str(part))
        if part != path or directory:
            if not stat.S_ISDIR(state.st_mode):
                raise ValueError('Expected ordinary source directory')
        elif not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
            raise ValueError('Expected singly linked ordinary source file')
    return path


def _state_identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            stat.S_IMODE(s.st_mode), s.st_nlink)


def identity(path):
    return _state_identity(path.stat())


def retained_mode(mode):
    # Git records the executable bit. A checkout created under umask 0002 may
    # be group writable; retain its physical mode in the identity, while the
    # NEW source group always receives normalized logical modes. The original
    # retained baseline is separately required to pass its strict manifest.
    if mode not in (0o644, 0o664, 0o755, 0o775):
        raise ValueError('Unsupported maintained checkout mode')
    return 0o755 if mode & 0o111 else 0o644


@dataclass(frozen=True)
class Source:
    path: Path
    sha256: str
    size: int
    mode: int
    identity: tuple


def snapshot(path, pin=None, *, maximum=MAX_SMALL_BYTES):
    path = ordinary(path)
    if pin is not None and (type(pin) is not str or not re.fullmatch('[0-9a-f]{64}', pin)):
        raise ValueError('Invalid source input SHA-256')
    before = identity(path)
    mode = retained_mode(before[5])
    if before[2] > maximum:
        raise ValueError('Unbounded or unnormalized source input: ' + str(path))
    actual, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        if _state_identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Source changed before reading')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            if size > before[2]:
                raise ValueError('Source grew while reading')
            actual.update(block)
        if _state_identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Source changed while reading')
    actual = actual.hexdigest()
    if size != before[2] or pin is not None and actual != pin or identity(ordinary(path)) != before:
        raise ValueError('Source input changed or differs from its pin: ' + str(path))
    return Source(path, actual, before[2], mode, before)


def read_small(path, pin=None):
    path = ordinary(path)
    before = identity(path)
    mode = retained_mode(before[5])
    if before[2] > MAX_SMALL_BYTES:
        raise ValueError('Oversized source assembly document')
    with path.open('rb') as stream:
        if _state_identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Source changed before bounded read')
        raw = stream.read(MAX_SMALL_BYTES + 1)
        if _state_identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Source changed during bounded read')
    actual = digest(raw)
    if (len(raw) != before[2] or len(raw) > MAX_SMALL_BYTES
            or pin is not None and actual != pin or identity(ordinary(path)) != before):
        raise ValueError('Source bounded read differs from its identity/pin')
    return raw, Source(path, actual, len(raw), mode, before)


def read_json(path, pin=None):
    raw, saved = read_small(path, pin)
    return contract.strict_json(raw, 'source assembly document'), raw, saved


def _module(path, importer=None):
    raw, saved = read_small(path)
    path = saved.path
    name = '_document_source_metadata_' + digest(str(path).encode())[:12]
    module = types.ModuleType(name)
    module.__file__ = str(path)
    if importer is not None:
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': importer}
    old = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    finally:
        if old is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = old
    module._assembly_snapshot = saved
    return module


class HelperBundle:
    """Execute the retained helper bytes, independent of cached import names."""
    NAMES = frozenset(('dependency_archive', 'appended_engine_manifest',
        'appended_engine_document_contract', 'appended_engine_editor_contract',
        'appended_engine_sdk', 'process_tree',
        'sdk_environment', 'sdk_manifest', 'appended_engine_document_maintenance',
        'appended_engine_theme_successor', 'appended_engine_showpicker_successor',
        'appended_engine_select_event_successor', 'appended_engine_input_method_successor',
        'appended_engine_retained_successor'))

    def __init__(self, repository):
        self.repository, self.modules = repository, {}

    def importer(self, name, globals=None, locals=None, fromlist=(), level=0):
        if not level and name in self.NAMES:
            return self.load(name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    def load(self, name):
        if name not in self.modules:
            self.modules[name] = _module(self.repository / ('tools/' + name + '.py'), self.importer)
        return self.modules[name]

    def snapshots(self):
        return [module._assembly_snapshot for module in self.modules.values()]


BUNDLE = HelperBundle(ROOT)
contract = BUNDLE.load('appended_engine_document_contract')
manifest = BUNDLE.load('appended_engine_manifest')
encoded = BUNDLE.load('dependency_archive').encoded


def _validate_projection(driver, value, config, files):
    """The planner's exact projection rules, applied to owned logical imports."""
    manifest.fields(value, ('schema_version', 'kind', 'document_profile', 'source_map',
        'files', 'physical_alias_groups', 'declared_source_aliases'), 'document source projection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-document-v2-source-projection-v1'
            or value['document_profile'] != config['document_profile']
            or type(value['files']) is not dict or not value['files']):
        raise ValueError('Projection must select exact retained final source files')
    manifest.fields(value['source_map'], ('path', 'sha256'), 'frozen source map')
    name = manifest.path_name(value['source_map']['path'])
    if (value['source_map']['sha256'] != config['source_map_sha256']
            or files[name][0].sha256 != config['source_map_sha256']):
        raise ValueError('Projection must bind the selected frozen source map')
    for name, item in value['files'].items():
        manifest.path_name(name)
        manifest.fields(item, ('preimage_sha256', 'sha256'), 'projected source pre/postimage')
        if item['preimage_sha256'] is not None:
            contract.validate_sha256(item['preimage_sha256'], 'projected preimage')
        contract.validate_sha256(item['sha256'], 'projected postimage')
        if name not in files or files[name][0].sha256 != item['sha256']:
            raise ValueError('Projection differs from maintained source import: ' + name)
    required = set(config['source_bindings'].values())
    required.update(path for paths in config['owner_postimages'].values() for path in paths)
    if not required <= set(value['files']):
        raise ValueError('Projection omits a direct source or engine owner postimage')
    driver._validate_alias_groups(value['physical_alias_groups'], value['files'])
    driver._validate_alias_groups(value['declared_source_aliases'], value['files'])
    if contract.canonical_json(value['declared_source_aliases']) != contract.canonical_json(config['declared_source_aliases']):
        raise ValueError('Declared aliases differ from maintained layout')
    physical = {path for group in value['physical_alias_groups'] for path in group['paths']}
    declared = {path for group in value['declared_source_aliases'] for path in group['paths']}
    if physical & declared:
        raise ValueError('Physical and declared source aliases overlap')


def _maintained(repository, selected, *, include_successful_donor_helper=False,
                include_theme_successor_helper=False,
                include_showpicker_successor_helper=False, include_select_event_successor_helper=False,
                include_input_method_successor_helper=False, include_retained_successor_helper=False):
    """Read only the maintained selection; no consumer observation is inferred."""
    if type(include_retained_successor_helper) is not bool or include_retained_successor_helper and selected != 'editor':
        raise ValueError('The retained successor helper requires an explicit editor selection')
    if include_retained_successor_helper:
        if any(type(value) is not bool for value in (include_successful_donor_helper,
                include_theme_successor_helper, include_showpicker_successor_helper,
                include_select_event_successor_helper, include_input_method_successor_helper)):
            raise ValueError('Retained successor predecessor helper selectors must be strict booleans')
        include_successful_donor_helper = include_theme_successor_helper = True
        include_showpicker_successor_helper = include_select_event_successor_helper = True
        include_input_method_successor_helper = True
    if (type(include_successful_donor_helper) is not bool
            or include_successful_donor_helper and selected != 'editor'):
        raise ValueError('The successful-donor helper requires an explicit editor selection')
    if (type(include_theme_successor_helper) is not bool
            or include_theme_successor_helper and (selected != 'editor'
                or not include_successful_donor_helper)):
        raise ValueError('The Theme successor helper requires explicit editor and successful-donor selection')
    if (type(include_showpicker_successor_helper) is not bool
            or include_showpicker_successor_helper and (selected != 'editor'
                or not include_successful_donor_helper
                or not include_theme_successor_helper)):
        raise ValueError('The showPicker successor helper requires explicit editor, successful-donor, and Theme-helper selection')
    if (type(include_select_event_successor_helper) is not bool
            or include_select_event_successor_helper and (selected != 'editor'
                or not include_successful_donor_helper or not include_theme_successor_helper
                or not include_showpicker_successor_helper)):
        raise ValueError('The select event successor helper requires explicit editor, successful-donor, Theme, and showPicker selections')
    if (type(include_input_method_successor_helper) is not bool
            or include_input_method_successor_helper and (selected != 'editor'
                or not include_successful_donor_helper or not include_theme_successor_helper
                or not include_showpicker_successor_helper or not include_select_event_successor_helper)):
        raise ValueError('The input method successor helper requires explicit editor and every predecessor helper selection')
    # Each selection owns its executed helper closure. An earlier editor query
    # must not add an unused editor module to a later pixel/physical recipe.
    bundle = HelperBundle(repository)
    here = repository / RECIPE_ROOT
    imports, _, saved_imports = read_json(here / ('source-imports-' + selected + '.json'))
    projection, raw_projection, saved_projection = read_json(here / ('source-projection-' + selected + '.json'))
    manifest.fields(imports, ('schema_version', 'kind', 'document_profile', 'capsule_version',
        'capsule_source_closure_sha256', 'capsule_source_map_sha256', 'files',
        'original_supplier_patch', 'selected_notice_index', 'limits'), 'document source imports')
    if (type(imports['schema_version']) is not int or imports['schema_version'] != 1
            or imports['kind'] != 'foundation-document-v2-source-imports-v1'
            or imports['document_profile'] != selected or type(imports['files']) is not dict
            or not 1 <= len(imports['files']) <= MAX_INPUTS):
        raise ValueError('Source import/projection selection differs')
    manifest.text(imports['capsule_version'], 'source capsule version')
    manifest.text(imports['limits'], 'source limits')
    contract.validate_sha256(imports['capsule_source_closure_sha256'], 'source closure')
    contract.validate_sha256(imports['capsule_source_map_sha256'], 'source map')
    # Load only this checkout's maintained driver. Its entry point is guarded.
    driver = bundle.load('appended_engine_document_maintenance')
    if driver.ROOT != repository:
        raise ValueError('Maintained driver repository differs')
    config, _, saved_config = read_json(repository / driver.profile_path(selected))
    previous = driver.checked_document
    def owned_config(path):
        if path != saved_config.path:
            raise ValueError('Unexpected maintained profile read')
        return contract.json_copy(config)
    driver.checked_document = owned_config
    try:
        config = driver.profile(selected)
    finally:
        driver.checked_document = previous
    snapshots = [saved_imports, saved_projection, saved_config, *bundle.snapshots()]
    result = {}
    for name, item in imports['files'].items():
        manifest.path_name(name)
        manifest.fields(item, ('tracked_path', 'sha256', 'bytes', 'mode', 'origin', 'role'), 'source import')
        manifest.path_name(item['tracked_path'])
        saved = snapshot(repository / item['tracked_path'], item['sha256'])
        if (type(item['bytes']) is not int or saved.size != item['bytes']
                or type(item['mode']) is not int or saved.mode != item['mode']
                or item['role'] not in manifest.ROLES or type(item['origin']) is not dict):
            raise ValueError('Selected source import count/mode differs: ' + name)
        if 'sha256' in item['origin'] and item['origin']['sha256'] != saved.sha256:
            raise ValueError('Selected source origin differs from its postimage: ' + name)
        result[name] = (saved, item['role'])
        snapshots.append(saved)
    helpers = driver.required_helpers(selected)
    if include_successful_donor_helper:
        if getattr(driver, 'SUCCESSFUL_HELPER', None) != 'tools/appended_engine_successful_donor.py':
            raise ValueError('Maintained successful-donor helper path differs')
        helpers += (driver.SUCCESSFUL_HELPER,)
    if include_theme_successor_helper:
        if getattr(driver, 'THEME_SUCCESSOR_HELPER', None) != 'tools/appended_engine_theme_successor.py':
            raise ValueError('Maintained Theme successor helper path differs')
        helpers += (driver.THEME_SUCCESSOR_HELPER,)
    if include_showpicker_successor_helper:
        if getattr(driver, 'SHOWPICKER_SUCCESSOR_HELPER', None) != 'tools/appended_engine_showpicker_successor.py':
            raise ValueError('Maintained showPicker successor helper path differs')
        helpers += (driver.SHOWPICKER_SUCCESSOR_HELPER,)
    if include_select_event_successor_helper:
        if getattr(driver, 'SELECT_EVENT_SUCCESSOR_HELPER', None) != 'tools/appended_engine_select_event_successor.py':
            raise ValueError('Maintained select event successor helper path differs')
        helpers += (driver.SELECT_EVENT_SUCCESSOR_HELPER,)
    if include_input_method_successor_helper:
        if getattr(driver, 'INPUT_METHOD_SUCCESSOR_HELPER', None) != 'tools/appended_engine_input_method_successor.py':
            raise ValueError('Maintained input method successor helper path differs')
        helpers += (driver.INPUT_METHOD_SUCCESSOR_HELPER,)
    if include_retained_successor_helper:
        if getattr(driver, 'RETAINED_SUCCESSOR_HELPER', None) != 'tools/appended_engine_retained_successor.py':
            raise ValueError('Maintained retained successor helper path differs')
        helpers += (driver.RETAINED_SUCCESSOR_HELPER,)
    for name in helpers + (RECIPE_ROOT + '/assemble_sources.py',):
        manifest.path_name(name)
        path = ordinary(repository / name)
        saved = snapshot(path)
        executed = next((old for old in snapshots if old.path == path), None)
        if executed is not None and saved != executed:
            raise ValueError('Executed helper differs from retained source bytes')
        result[name] = (saved, 'helper')
        snapshots.append(saved)
    if include_theme_successor_helper:
        manifest.path_name(THEME_SOURCE)
        if THEME_SOURCE in result:
            raise ValueError('Theme source already exists in maintained imports')
        saved = snapshot(repository / THEME_SOURCE_PATH, THEME_SOURCE_SHA256,
            maximum=THEME_SOURCE_BYTES)
        if saved.size != THEME_SOURCE_BYTES:
            raise ValueError('Maintained Theme source byte count differs')
        result[THEME_SOURCE] = (saved, 'source')
        snapshots.append(saved)
    for basename in ('source-imports-' + selected + '.json', 'source-projection-' + selected + '.json'):
        path = here / basename
        saved = snapshot(path)
        old = saved_imports if basename.startswith('source-imports-') else saved_projection
        if old != saved:
            raise ValueError('Source selection changed during discovery')
        result[RECIPE_ROOT + '/' + basename] = (saved, 'config')
        snapshots.append(saved)
    source_map = here / 'provenance' / (selected + '-source-map.json')
    saved = snapshot(source_map, imports['capsule_source_map_sha256'])
    result['provenance/document-source-map.json'] = (saved, 'config')
    snapshots.append(saved)
    for key in ('original_supplier_patch', 'selected_notice_index'):
        ref = imports[key]
        manifest.fields(ref, ('tracked_path', 'sha256'), 'source provenance reference')
        manifest.path_name(ref['tracked_path'])
        saved = snapshot(repository / ref['tracked_path'], ref['sha256'])
        result[ref['tracked_path']] = (saved, 'config')
        snapshots.append(saved)
        if key == 'selected_notice_index':
            notice_index, _, _ = read_json(saved.path, saved.sha256)
            for name, item in notice_index['files'].items():
                manifest.path_name(name)
                manifest.fields(item, ('tracked_path', 'sha256', 'bytes', 'role'), 'selected notice')
                manifest.path_name(item['tracked_path'])
                notice = snapshot(repository / item['tracked_path'], item['sha256'])
                if type(item['bytes']) is not int or notice.size != item['bytes'] or item['role'] != 'license':
                    raise ValueError('Selected notice differs from retained provenance')
                result[name] = (notice, 'license')
                snapshots.append(notice)
    if set(projection['files']) != set(imports['files']):
        raise ValueError('Every maintained source import requires an explicit pre/postimage')
    _validate_projection(driver, projection, config, result)
    return result, snapshots, raw_projection


def _preflight_tree(root, expected):
    """Reject an overbudget or foreign namespace before hashing source contents."""
    if len(expected['files']) > MAX_INPUTS + 1 or len(expected['directories']) > MAX_DIRECTORIES:
        raise ValueError('Original source namespace exceeds its bounded inventory')
    files, directories, pending, total = set(), set(), [root], 0
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            state = path.lstat()
            name = path.relative_to(root).as_posix()
            if stat.S_ISDIR(state.st_mode):
                ordinary(path, directory=True)
                if stat.S_IMODE(state.st_mode) != 0o755:
                    raise ValueError('Original source directory mode differs')
                directories.add(name)
                if len(directories) > MAX_DIRECTORIES:
                    raise ValueError('Original source directory budget exceeded')
                pending.append(path)
            else:
                ordinary(path)
                files.add(name)
                total += state.st_size
                if len(files) > MAX_INPUTS + 2 or total > MAX_SOURCE_BYTES + 2 * MAX_SMALL_BYTES:
                    raise ValueError('Original source file budget exceeded before hashing')
    if files != set(expected['files']) | {'sources.json'} or directories != set(expected['directories']):
        raise ValueError('Original source namespace differs from its pinned complete inventory')


def prepare(baseline, recipe_sha256, sources_sha256, *, document_profile, repository=ROOT,
            include_successful_donor_helper=False, include_theme_successor_helper=False,
            include_showpicker_successor_helper=False, include_select_event_successor_helper=False,
                include_input_method_successor_helper=False, include_retained_successor_helper=False):
    """Fully inspect inputs and return an owned plan; launch no programs."""
    if type(include_retained_successor_helper) is not bool or include_retained_successor_helper and document_profile != 'editor':
        raise ValueError('The retained successor helper requires an explicit editor selection')
    if include_retained_successor_helper:
        if any(type(value) is not bool for value in (include_successful_donor_helper,
                include_theme_successor_helper, include_showpicker_successor_helper,
                include_select_event_successor_helper, include_input_method_successor_helper)):
            raise ValueError('Retained successor predecessor helper selectors must be strict booleans')
        include_successful_donor_helper = include_theme_successor_helper = True
        include_showpicker_successor_helper = include_select_event_successor_helper = True
        include_input_method_successor_helper = True
    if (type(include_successful_donor_helper) is not bool
            or include_successful_donor_helper and document_profile != 'editor'):
        raise ValueError('The successful-donor helper requires an explicit editor selection')
    if (type(include_theme_successor_helper) is not bool
            or include_theme_successor_helper and (document_profile != 'editor'
                or not include_successful_donor_helper)):
        raise ValueError('The Theme successor helper requires explicit editor and successful-donor selection')
    if (type(include_showpicker_successor_helper) is not bool
            or include_showpicker_successor_helper and (document_profile != 'editor'
                or not include_successful_donor_helper
                or not include_theme_successor_helper)):
        raise ValueError('The showPicker successor helper requires explicit editor, successful-donor, and Theme-helper selection')
    if (type(include_select_event_successor_helper) is not bool
            or include_select_event_successor_helper and (document_profile != 'editor'
                or not include_successful_donor_helper or not include_theme_successor_helper
                or not include_showpicker_successor_helper)):
        raise ValueError('The select event successor helper requires explicit editor, successful-donor, Theme, and showPicker selections')
    if (type(include_input_method_successor_helper) is not bool
            or include_input_method_successor_helper and (document_profile != 'editor'
                or not include_successful_donor_helper or not include_theme_successor_helper
                or not include_showpicker_successor_helper or not include_select_event_successor_helper)):
        raise ValueError('The input method successor helper requires explicit editor and every predecessor helper selection')
    _recheck({'snapshots': BUNDLE.snapshots()})
    driver = BUNDLE.load('appended_engine_document_maintenance')
    selected = driver.profile_selector(document_profile)
    baseline, repository = ordinary(baseline, directory=True), ordinary(repository, directory=True)
    recipe_document, raw_recipe, recipe_snapshot = read_json(baseline / 'recipe.json', recipe_sha256)
    sources_document, raw_sources, source_snapshot = read_json(baseline / 'sources.json', sources_sha256)
    manifest.source_contract(sources_document, recipe_document, recipe_sha256)
    _preflight_tree(baseline, sources_document)
    source_manifest, source_pin, recipe = manifest.verify_sources(baseline)
    if (source_pin != sources_sha256 or digest(raw_recipe) != recipe_sha256
            or digest(raw_sources) != sources_sha256):
        raise ValueError('Original retained source group differs from independent pins')
    if (recipe['provider']['format'] != 'browser-module'
            or recipe['provider']['binding'] != 'copied-owner-bridge'
            or recipe['provider']['abi_major'] != 1
            or recipe['provider']['abi_minor'] != 0
            or recipe['provider']['header_sha256'] != contract.BASE_HEADER_SHA256
            or recipe['target']['system'] != 'Emscripten'
            or recipe['target']['processor'] != 'wasm32'
            or recipe['target']['pointer_bits'] != 32
            or recipe['options'] != {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'}):
        raise ValueError('Original sources are not the copied browser engine')
    entries, snapshots = {}, [recipe_snapshot, source_snapshot]
    total = 0
    for name, item in recipe['inputs'].items():
        saved = snapshot(baseline / name, item['sha256'], maximum=MAX_SOURCE_BYTES)
        if saved.mode != item['mode']:
            raise ValueError('Original source input mode differs')
        total += saved.size
        if total > MAX_SOURCE_BYTES or len(entries) >= MAX_INPUTS:
            raise ValueError('Original retained source input budget exceeded')
        entries[name] = (saved, item['role'])
        snapshots.append(saved)
    if include_retained_successor_helper:
        maintained, checked, raw_projection = _maintained(repository, selected,
            include_retained_successor_helper=True)
    elif include_input_method_successor_helper:
        maintained, checked, raw_projection = _maintained(repository, selected,
            include_successful_donor_helper=True, include_theme_successor_helper=True,
            include_showpicker_successor_helper=True, include_select_event_successor_helper=True,
            include_input_method_successor_helper=True)
    elif include_select_event_successor_helper:
        maintained, checked, raw_projection = _maintained(repository, selected,
            include_successful_donor_helper=True, include_theme_successor_helper=True,
            include_showpicker_successor_helper=True, include_select_event_successor_helper=True)
    elif include_showpicker_successor_helper:
        maintained, checked, raw_projection = _maintained(repository, selected,
            include_successful_donor_helper=True, include_theme_successor_helper=True,
            include_showpicker_successor_helper=True)
    elif include_theme_successor_helper:
        maintained, checked, raw_projection = _maintained(repository, selected,
            include_successful_donor_helper=True, include_theme_successor_helper=True)
    elif include_successful_donor_helper:
        maintained, checked, raw_projection = _maintained(repository, selected,
            include_successful_donor_helper=True)
    else:
        maintained, checked, raw_projection = _maintained(repository, selected)
    snapshots.extend(checked)
    projection = contract.strict_json(raw_projection, 'selected source projection')
    for name, change in projection['files'].items():
        selected_input = maintained.get(name)
        if selected_input is None or selected_input[0].sha256 != change['sha256']:
            raise ValueError('Selected source postimage differs from imports: ' + name)
        original = recipe['inputs'].get(name, {}).get('sha256')
        if (change['preimage_sha256'] is not None and original != change['preimage_sha256']
                or change['preimage_sha256'] is None and original not in (None, change['sha256'])):
            raise ValueError('Original retained source preimage differs: ' + name)
    for name, (saved, role) in maintained.items():
        if role == 'license' and recipe['inputs'].get(name, {}).get('sha256') != saved.sha256:
            raise ValueError('Selected original notice differs from complete retained licenses')
    entries.update(maintained)
    generated = {'provenance/document-predecessor/recipe.json': (raw_recipe, 'config'),
        'provenance/document-predecessor/sources.json': (raw_sources, 'config'),
        'provenance/source-projection.json': (raw_projection, 'config')}
    updated = contract.json_copy(recipe)
    updated['provider'].update(abi_minor=1, header='include/foundation/appended/engine_provider.h',
                               header_sha256=contract.BASE_HEADER_SHA256)
    metadata = _module(repository / RECIPE_ROOT / 'runtime/generate_document_metadata.py')
    snapshots.append(metadata._assembly_snapshot)
    metadata_arguments = {'contract': contract}
    if selected == 'editor':
        editor_contract = BUNDLE.load('appended_engine_editor_contract')
        snapshots.append(editor_contract._assembly_snapshot)
        metadata_arguments['editor_contract'] = editor_contract
    generated['prelink-plan.json'] = (encoded(metadata.fixed_plan(updated, selected, **metadata_arguments)), 'config')
    for name in generated:
        entries.pop(name, None)
    updated['inputs'] = {name: {'sha256': saved.sha256, 'mode': saved.mode, 'role': role}
                         for name, (saved, role) in sorted(entries.items())}
    updated['inputs'].update({name: {'sha256': digest(raw), 'mode': 0o644, 'role': role}
                              for name, (raw, role) in generated.items()})
    manifest.recipe_contract(updated)
    total = sum(saved.size for saved, _ in entries.values()) + sum(len(raw) for raw, _ in generated.values())
    if len(updated['inputs']) > MAX_INPUTS or total > MAX_SOURCE_BYTES:
        raise ValueError('Document source assembly budget exceeded')
    namespace = manifest.PathInventory()
    for name in (*updated['inputs'], 'recipe.json', 'sources.json'):
        namespace.add(name, False)
    for name in source_manifest['directories']:
        namespace.add(name, True)
    forbidden_directories = {identity(ordinary(baseline / name, directory=True))[:2]
                             for name in ('', *source_manifest['directories'])}
    for saved, _ in maintained.values():
        if repository not in saved.path.parents:
            continue
        for parent in saved.path.parents:
            if parent == repository:
                break
            forbidden_directories.add(identity(ordinary(parent, directory=True))[:2])
    return {'document_profile': selected, 'baseline': baseline, 'repository': repository,
        'baseline_recipe_sha256': recipe_sha256, 'baseline_sources_sha256': sources_sha256,
        'entries': entries, 'generated': generated, 'snapshots': snapshots, 'recipe': updated,
        'source_bytes': total, 'source_files': len(updated['inputs']),
        'forbidden_directories': forbidden_directories,
        'directories': source_manifest['directories'],
        'original_source_inventory': source_manifest}


def _recheck(plan):
    if 'original_source_inventory' in plan:
        _preflight_tree(plan['baseline'], plan['original_source_inventory'])
    for old in plan['snapshots']:
        current = snapshot(old.path, old.sha256, maximum=MAX_SOURCE_BYTES)
        if current.identity != old.identity:
            raise ValueError('Source input identity changed before assembly')


def _parents(path, root):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    ordinary(path.parent, directory=True)
    for parent in path.parents:
        if parent == root:
            break
        parent.chmod(0o755)


def _copy(saved, path):
    """Copy a bounded source without keeping opaque supplier archives in memory."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    descriptor = os.open(saved.path, flags)
    try:
        if (identity(saved.path) != saved.identity
                or _state_identity(os.fstat(descriptor)) != saved.identity):
            raise ValueError('Source changed before copy')
        actual, total = hashlib.sha256(), 0
        with os.fdopen(descriptor, 'rb', closefd=False) as source, path.open('xb') as output:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                total += len(block)
                if total > saved.size:
                    raise ValueError('Source grew while copying')
                actual.update(block)
                output.write(block)
        path.chmod(saved.mode)
        if (total != saved.size or actual.hexdigest() != saved.sha256
                or identity(saved.path) != saved.identity
                or _state_identity(os.fstat(descriptor)) != saved.identity):
            raise ValueError('Source changed while copying; partial output retained')
    finally:
        os.close(descriptor)


def assemble(plan, output):
    """Save one NEW source group; partial failures never establish completion."""
    output = Path(os.path.abspath(os.fspath(output)))
    ordinary(output.parent, directory=True)
    if output.exists() or output.is_symlink():
        raise ValueError('Source assembly output must be new')
    if (output == plan['baseline'] or output in plan['baseline'].parents
            or plan['baseline'] in output.parents):
        raise ValueError('Source assembly output and baseline must be disjoint')
    if output == plan['repository'] or plan['repository'] in output.parents:
        relative = output.relative_to(plan['repository'])
        if not relative.parts or relative.parts[0] not in ('.agent-work', 'build'):
            raise ValueError('Source assembly output must stay outside repository inputs')
    if any(identity(ordinary(parent, directory=True))[:2] in plan['forbidden_directories']
           for parent in output.parents):
        raise ValueError('Source assembly output aliases a retained input directory')
    _recheck(plan)
    output.mkdir(mode=0o755)
    output.chmod(0o755)
    for name in plan['directories']:
        # Retain inventoried empty directories as well as file parents; an
        # original empty include-search directory is part of the source layout.
        _parents(output / name / '__unwritten_directory_marker__', output)
    for name, (saved, _) in sorted(plan['entries'].items()):
        path = output / name
        _parents(path, output)
        _copy(saved, path)
    for name, (raw, _) in sorted(plan['generated'].items()):
        path = output / name
        _parents(path, output)
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o644)
    with (output / 'recipe.json').open('xb') as stream:
        stream.write(encoded(plan['recipe']))
    (output / 'recipe.json').chmod(0o644)
    recipe, recipe_pin, inventory = manifest.verify_inputs(output)
    sources = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
        'producer_version': 1, 'recipe_id': recipe_pin, **inventory}
    # The complete source manifest is the final seal. Failures while copying,
    # validating outputs or rechecking the original inputs leave it absent.
    _recheck(plan)
    checked, checked_pin, checked_inventory = manifest.verify_inputs(output)
    if checked != recipe or checked_pin != recipe_pin or checked_inventory != inventory:
        raise ValueError('Document source output changed during verification')
    manifest.source_contract(sources, recipe, recipe_pin)
    raw_sources = encoded(sources)
    with (output / 'sources.json').open('xb') as stream:
        os.fchmod(stream.fileno(), 0o644)
        stream.write(raw_sources)
    return {'schema_version': 1, 'kind': KIND, 'document_profile': plan['document_profile'],
        'recipe_sha256': recipe_pin, 'sources_sha256': digest(raw_sources),
        'source_files': plan['source_files'], 'source_bytes': plan['source_bytes'],
        'scope': 'source-only-no-sdk-engine-or-runtime', 'production_eligible': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'assemble'))
    parser.add_argument('--baseline-sources', type=Path, required=True)
    parser.add_argument('--baseline-recipe-sha256', required=True)
    parser.add_argument('--baseline-sources-sha256', required=True)
    parser.add_argument('--document-profile', choices=('pixel', 'physical', 'editor'), required=True)
    parser.add_argument('--include-successful-donor-helper', action='store_true',
        help='Retain the exact maintained successful-donor helper for an editor continuation')
    parser.add_argument('--include-theme-successor-helper', action='store_true',
        help='Retain the explicit Theme successor helper with the editor successful-donor selection')
    parser.add_argument('--include-showpicker-successor-helper', action='store_true',
        help='Retain the native showPicker successor helper with editor, successful-donor, and Theme-helper selections')
    parser.add_argument('--include-select-event-successor-helper', action='store_true',
        help='Retain the distinct select event producer with all accepted predecessor helper selections')
    parser.add_argument('--include-input-method-successor-helper', action='store_true',
        help='Retain the input method lifecycle producer with every accepted predecessor helper selection')
    parser.add_argument('--include-retained-successor-helper', action='store_true',
        help='Retain the closed editor direct-TU successor and its complete predecessor helper closure')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if (args.action == 'assemble') != (args.output is not None):
            raise ValueError('Only assemble requires an explicit NEW --output')
        plan = prepare(args.baseline_sources, args.baseline_recipe_sha256,
            args.baseline_sources_sha256, document_profile=args.document_profile,
            include_successful_donor_helper=args.include_successful_donor_helper,
            **({'include_theme_successor_helper': True} if args.include_theme_successor_helper else {}),
            **({'include_showpicker_successor_helper': True} if args.include_showpicker_successor_helper else {}),
            **({'include_select_event_successor_helper': True} if args.include_select_event_successor_helper else {}),
            **({'include_input_method_successor_helper': True} if args.include_input_method_successor_helper else {}),
            **({'include_retained_successor_helper': True} if args.include_retained_successor_helper else {}))
        result = (assemble(plan, args.output) if args.action == 'assemble' else
            {'schema_version': 1, 'kind': KIND, 'document_profile': plan['document_profile'],
             'source_files': plan['source_files'], 'source_bytes': plan['source_bytes'],
             'production_eligible': False, 'scope': 'source-plan-no-programs-or-output'})
        print(encoded(result).decode('ascii'), end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('document source assembly: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
