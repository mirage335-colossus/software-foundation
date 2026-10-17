"""Pure original historical publication semantics; no qualification issuance.

Source basis is immutable A53dd. Expected subjects and original raw bytes must
already be independently selected/admitted by the actual retained caller. This
module neither observes current runtime facts nor opens files or native readers.
"""

import copy
import hashlib
import json
from pathlib import PureWindowsPath
import re


A_SOURCE_SHA256 = '53dd02b3789c6418e872b7aeaf7b0d58d47ef632ed4d9b87b3eb38049b7b9ce1'
CONTRACT_SHA256 = '726277627277fda79c2422e34760e3a088466d06f93de26057ab17e03817bbd7'
POLICY = 'native-windows-local-ntfs-atomic-no-replace-v1'
SCOPE = 'actual-native-windows-publication'
MAX_METADATA = 1024 * 1024
MAX_CONSOLE = 64 * 1024 * 1024
SOURCE_FILES = ('tools/appended_engine_windows_publication.py',
    'tests/diagnostics/windows_engine_publication.py', 'tools/process_tree.py',
    'tools/appended_engine_windows_contract.py')
CASE_NAMES = ('test_complete_atomic_no_replace', 'test_existing_directory_and_case_collision',
    'test_ancestor_handles_prevent_rename', 'test_reparse_and_hardlink_rejected',
    'test_complete_output_inventory', 'test_owned_pending_cleanup',
    'test_parent_exit_with_writer_rejected', 'test_joined_owner_seals_log',
    'test_flush_failure_stops_publication', 'test_uncertain_rename_retains_evidence')
_ORIGINALS = ('run_report', 'observations', 'console')
_REPORT_FIELDS = ('schema_version', 'kind', 'scope', 'policy', 'source_identity',
    'runtime_identity', 'filesystem', *_ORIGINALS)


class PublicationDataError(ValueError):
    code = 'DATA'


class PublicationSourceError(ValueError):
    code = 'SOURCE'


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise PublicationSourceError('Unsupported ' + label + ' fields')


def _pin(value, label):
    if (type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None or
            value == '0' * 64):
        raise PublicationDataError('Independent nonzero SHA256 required: ' + label)
    return value


def _text(value, label):
    if (type(value) is not str or not value or len(value) > 4096 or
            any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value)):
        raise PublicationSourceError('Invalid ' + label)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise PublicationSourceError('Invalid UTF-8 ' + label) from error
    return value


def _windows_path(value, label):
    """Already frozen source-owned conservative canonical declaration policy."""
    _text(value, label)
    selected = PureWindowsPath(value)
    if (not re.match('^[A-Z]:/', value) or not selected.is_absolute() or
            selected.as_posix() != value or len(value) <= 3 or '\\' in value or
            any(char in value for char in (';', '"', '$', '@'))):
        raise PublicationSourceError('Explicit canonical local Windows path required: ' + label)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                *('COM' + str(index) for index in range(1, 10)),
                *('LPT' + str(index) for index in range(1, 10)),
                *('COM' + digit for digit in '¹²³'),
                *('LPT' + digit for digit in '¹²³')}
    for part in selected.parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.')) or
                any(char in part for char in ':<>|?*') or
                part.split('.')[0].upper() in reserved):
            raise PublicationSourceError('Aliased or nonportable Windows path: ' + label)
    return value


def _bytes(raw, pin, maximum, label):
    _pin(pin, label)
    if type(raw) is not bytes or not 1 <= len(raw) <= maximum:
        raise PublicationDataError('Original byte type/bound differs: ' + label)
    if hashlib.sha256(raw).hexdigest() != pin:
        raise PublicationDataError('Original raw bytes differ from their independent SHA256: ' + label)
    return raw


def _parse(raw, pin, label):
    raw = _bytes(raw, pin, MAX_METADATA, label)

    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise PublicationDataError('Duplicate original JSON field: ' + name)
            result[name] = value
        return result

    def invalid(value):
        raise PublicationDataError('Nonfinite original JSON: ' + value)

    def strings(value):
        if type(value) is str:
            value.encode('utf-8')
        elif type(value) is dict:
            for name, child in value.items():
                strings(name); strings(child)
        elif type(value) is list:
            for child in value:
                strings(child)

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        json.dumps(value, ensure_ascii=True, allow_nan=False)
        strings(value)
        return value
    except (UnicodeError, RecursionError, OverflowError, ValueError) as error:
        if isinstance(error, PublicationDataError):
            raise
        raise PublicationDataError('Invalid bounded original JSON encoding or nesting') from error


def _references(report):
    aliases, files, result = {}, set(), {}
    for role in _ORIGINALS:
        reference = report[role]
        _fields(reference, ('path', 'sha256'), role + ' original reference')
        path = _windows_path(reference['path'], role + ' original reference')
        digest = _pin(reference['sha256'], role)
        if path.casefold() in files:
            raise PublicationSourceError('Repeated/aliased original publication reference')
        files.add(path.casefold())
        parts = PureWindowsPath(path).parts
        for count in range(1, len(parts) + 1):
            component = PureWindowsPath(*parts[:count]).as_posix()
            directory = count < len(parts)
            record = (component, directory, None if directory else digest)
            previous = aliases.get(component.casefold())
            if previous is not None and previous != record:
                raise PublicationSourceError('Original publication reference path spelling/kind aliases')
            aliases[component.casefold()] = record
        result[role] = copy.deepcopy(reference)
    return result


def _report(raw, pin):
    report = _parse(raw, pin, 'historical publication qualification')
    _fields(report, _REPORT_FIELDS, 'historical publication qualification')
    if (type(report['schema_version']) is not int or report['schema_version'] != 1 or
            report['kind'] != 'foundation-windows-publication-qualification-v1' or
            report['scope'] != SCOPE or report['policy'] != POLICY):
        raise PublicationSourceError('Unsupported historical publication qualification subject')
    return report, _references(report)


def original_references(raw, pin):
    """Select original refs only; statuses or dictionaries grant no authority."""
    return _report(raw, pin)[1]


def _source(value):
    _fields(value, SOURCE_FILES, 'independently selected historical source identity')
    for name, digest in value.items():
        _pin(digest, name)
    if value['tools/appended_engine_windows_contract.py'] != CONTRACT_SHA256:
        raise PublicationSourceError('Historical publication uses a different Windows contract source')


def _runtime(value):
    _fields(value, ('python_path', 'python_sha256', 'python_version', 'system', 'machine',
        'pointer_bits', 'windows_version', 'system_root'), 'historical publication runtime identity')
    _windows_path(value['python_path'], 'historical controller Python')
    _pin(value['python_sha256'], 'historical controller Python')
    _windows_path(value['system_root'], 'historical Windows directory')
    _text(value['python_version'], 'historical Python version')
    if (value['system'] != 'Windows' or value['machine'] != 'x86_64' or
            type(value['pointer_bits']) is not int or value['pointer_bits'] != 64 or
            re.fullmatch(r'3\.[0-9]+\.[0-9]+', value['python_version']) is None):
        raise PublicationSourceError('Historical native Windows x64 Python runtime required')
    if tuple(map(int, value['python_version'].split('.'))) < (3, 9, 0):
        raise PublicationSourceError('Historical publication requires Python 3.9 or newer')
    versions = value['windows_version']
    if (type(versions) is not list or len(versions) != 3 or
            any(type(item) is not int or not 0 <= item < 2 ** 32 for item in versions)):
        raise PublicationSourceError('Historical bounded Windows version required')


def _filesystem(value):
    _fields(value, ('name', 'volume_serial'), 'historical qualified local filesystem')
    if (value['name'] != 'NTFS' or type(value['volume_serial']) is not int or
            not 0 < value['volume_serial'] < 2 ** 64):
        raise PublicationDataError('Historical qualified local NTFS volume identity required')


def publication_qualification(raw, pin, *, source_identity, runtime_identity, originals):
    """Check bounded original historical facts, never issue native authority.

    Expected source/runtime subjects must come from the caller's independently
    reviewed retained catalogue; copying them from the report is not admission.
    Current native reader/runtime equality is deliberately not part of this API.
    """
    _source(source_identity); _runtime(runtime_identity)
    report, references = _report(raw, pin)
    _source(report['source_identity']); _runtime(report['runtime_identity'])
    if report['source_identity'] != source_identity or report['runtime_identity'] != runtime_identity:
        raise PublicationDataError('Historical publication source/runtime identity does not join independent subjects')
    filesystem = report['filesystem']
    _filesystem(filesystem)
    if type(originals) is not dict or set(originals) != {ref['path'] for ref in references.values()}:
        raise PublicationDataError('Exact selected original report/observations/console byte map required')
    run_ref, observed_ref, console_ref = (references[name] for name in _ORIGINALS)
    run = _parse(originals[run_ref['path']], run_ref['sha256'], 'historical complete run report')
    _fields(run, ('schema_version', 'system', 'status', 'inventory', 'excluded', 'results'), 'historical complete native case inventory')
    if (type(run['schema_version']) is not int or run['schema_version'] != 1 or
            run['system'] != 'Windows' or run['status'] != 'passed' or run['excluded'] != {}):
        raise PublicationDataError('Historical native qualification has failed/incomplete/excluded cases')
    inventory = run['inventory']
    if (type(inventory) is not list or len(inventory) != len(CASE_NAMES) or
            any(type(name) is not str for name in inventory) or len(set(inventory)) != len(inventory)):
        raise PublicationDataError('Historical native qualification case inventory is incomplete')
    names = {name.rsplit('.', 1)[-1]: name for name in inventory if '.NativePublication.' in name}
    if (type(run['results']) is not dict or set(names) != set(CASE_NAMES) or
            set(run['results']) != set(inventory) or
            any(run['results'][name] != {'status': 'passed'} for name in inventory)):
        raise PublicationDataError('Historical native cases are missing, repeated or not passed')
    observed = _parse(originals[observed_ref['path']], observed_ref['sha256'], 'historical original observations')
    _fields(observed, ('schema_version', 'kind', 'scope', 'policy', 'source_identity',
        'runtime_identity', 'filesystem', 'cases'), 'historical original native publication observations')
    _source(observed['source_identity']); _runtime(observed['runtime_identity'])
    _filesystem(observed['filesystem'])
    if (type(observed['schema_version']) is not int or observed['schema_version'] != 1 or
            observed['kind'] != 'foundation-windows-publication-observations-v1' or
            any(observed[name] != report[name] for name in
                ('scope', 'policy', 'source_identity', 'runtime_identity', 'filesystem')) or
            type(observed['cases']) is not dict or set(observed['cases']) != set(CASE_NAMES)):
        raise PublicationDataError('Historical original observations do not join the qualification')
    for name, row in observed['cases'].items():
        _fields(row, ('operation', 'observed'), 'historical native case observation')
        if row['operation'] != name or type(row['observed']) is not dict or not row['observed']:
            raise PublicationDataError('Historical native case lacks original operation/readback observations')
    console = _bytes(originals[console_ref['path']], console_ref['sha256'], MAX_CONSOLE, 'historical original console')
    marker = b'WINDOWS_PUBLICATION_OBSERVATIONS_SHA256=' + observed_ref['sha256'].encode('ascii')
    if marker not in console:
        raise PublicationDataError('Historical original console does not bind the complete observations')
    return {'report_sha256': pin, 'kind': report['kind'], 'scope': SCOPE, 'policy': POLICY,
        'source_identity': copy.deepcopy(source_identity), 'runtime_identity': copy.deepcopy(runtime_identity),
        'filesystem': copy.deepcopy(filesystem), 'originals': copy.deepcopy(references),
        'production_eligible': False, 'native_runtime_qualified': False, 'power_loss_guarantee': False}
