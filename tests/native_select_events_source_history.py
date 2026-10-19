"""Exact source-only history for the native select changed-choice event fix."""
import copy
import hashlib
import json


CURRENT_SHA256 = 'ccabb6855aa4befe7db1f9a2225ae1ef1b942a7508cc3fdeea62783e01f73509'
CURRENT_BYTES = 74829
PREVIOUS_SHA256 = '0b4b077b36193fd5ebea0e29017c54ae2df430b6e6ef78d7a3a06f6c19cfe4b1'
PREVIOUS_BYTES = 74585
REVIEWED_SOURCE_ACCEPTANCE_SHA256 = 'aee6871efc89abbb98119bbf01eb9e71713c1a0db529e6bc1c9ba7f249e469d4'
DOCUMENT_PREVIOUS_ROW_SHA256 = '91445fb2d99df4ff70a56505b22c45bc0a64f3687fc41a3e3e3ef73aaaee5fe8'
NATIVE_PREVIOUS_ROW_SHA256 = 'e5796e05832009af593242731de2882f1d7c557221ef9634b8d5894c36a94c85'
NATIVE_PREVIOUS_SOURCE_MAP_SHA256 = '5033e776046234aad7b60a4adf833e589be45133786315755173933ec7146b1e'
CORRECTION = 'compare-current-selection-before-immediate-changed-user-choice-commit'
INSERTION = (
    b'    // Script may have changed the selection since the popup opened. Compare an\n'
    b'    // immediate user choice with the current value before committing it.\n'
    b'    if (fireOnChangeNow && !m_isProcessingUserDrivenChange)\n'
    b'        saveLastSelection();\n\n'
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def native_select_events_predecessor_bytes(raw):
    """Remove the one accepted insertion only from the exact accepted bytes."""
    if sha(raw) != CURRENT_SHA256 or len(raw) != CURRENT_BYTES:
        return raw
    if raw.count(INSERTION) != 1:
        raise AssertionError('Exact native select event insertion required once')
    previous = raw.replace(INSERTION, b'', 1)
    if len(previous) != PREVIOUS_BYTES or sha(previous) != PREVIOUS_SHA256:
        raise AssertionError('Native select event source reverse projection differs')
    return previous


def native_select_events_document_history(imports, projection=None, *, logical):
    """Restore the one exact prior document row and matching projection hash."""
    imports = copy.deepcopy(imports)
    projection = copy.deepcopy(projection)
    item = imports['files'].get(logical)
    if item is None or item['origin'].get('kind') != 'reviewed-native-select-events-successor':
        return (imports, projection) if projection is not None else imports
    path = item['tracked_path']
    wanted = {'kind': 'reviewed-native-select-events-successor',
              'correction': CORRECTION, 'source_only': True,
              'source_path': path, 'sha256': CURRENT_SHA256,
              'reviewed_source_acceptance_sha256': REVIEWED_SOURCE_ACCEPTANCE_SHA256}
    origin = item['origin']
    if (imports.get('document_profile') not in ('editor', 'physical')
            or item.get('sha256') != CURRENT_SHA256
            or type(item.get('bytes')) is not int or item['bytes'] != CURRENT_BYTES
            or type(item.get('mode')) is not int or item['mode'] != 420
            or item.get('role') != 'source'
            or set(origin) != set(wanted) | {'supersedes'}
            or any(type(origin[key]) is not type(value) or origin[key] != value
                   for key, value in wanted.items())):
        raise AssertionError('Exact native select events current fact/origin required')
    prior = origin['supersedes']
    if type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}:
        raise AssertionError('Complete native select events predecessor required')
    old = dict(item, **prior)
    expected = DOCUMENT_PREVIOUS_ROW_SHA256
    if sha(canonical(old)) != expected:
        raise AssertionError('Native select events predecessor row was restamped')
    if (prior['sha256'] != PREVIOUS_SHA256 or prior['bytes'] != PREVIOUS_BYTES
            or prior['tracked_path'] != path):
        raise AssertionError('Native select events predecessor source identity differs')
    if projection is not None:
        projected = projection['files'].get(logical)
        if type(projected) is not dict or projected.get('sha256') != CURRENT_SHA256:
            raise AssertionError('Native select events current projection differs')
        projected['sha256'] = prior['sha256']
    imports['files'][logical] = old
    return (imports, projection) if projection is not None else imports


def native_select_events_editor_history(imports, projection=None):
    return native_select_events_document_history(
        imports, projection, logical='source/engine/Source/WebCore/html/HTMLSelectElement.cpp')
