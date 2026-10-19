"""Exact source-only select showPicker lineage helpers; no SDK or programs."""
import copy
import hashlib
import json

DOCUMENT_CURRENT_SHA256 = 'd86c1384504cb3780e627a935f96d34fa5900702b363e90cdf9646c26f411030'
DOCUMENT_PREVIOUS_SHA256 = '2c315a2d08f8f5025f0619db73621d4aaf79dcdc970c1f5e1b7b692a045beb9b'
DOCUMENT_CURRENT_BYTES = 164706
DOCUMENT_REVERSE_EDITS = [[35642, 35697, '']]
DOCUMENT_PREVIOUS_ROW_SHA256 = 'a23c7c6ef09f0c4b61bab1fda4eb80080e6cfd3bd7117880d7c5878b94a72e02'

NATIVE_CURRENT_SHA256 = '559ee65304dcda907f8c574ce664710435740366555036113063d94946b335ad'
NATIVE_PREVIOUS_SHA256 = '3c2c7beb2b582ab91fb8174aa7d5f6022ce1a4b29ec66918674f9f13fadd88ac'
NATIVE_CURRENT_BYTES = 48401
NATIVE_REVERSE_EDITS = [[35856, 35911, '']]
NATIVE_PREVIOUS_ROW_SHA256 = '5be6358ab3ae931afdb1c7944450662ff77367c2135ec119e93c5c324bf646e3'

CORRECTION = 'provider-page-startup-enables-native-select-show-picker'
REVIEWED_SOURCE_ACCEPTANCE_SHA256 = 'a2883e614f6ff2268f0ab332d0888b4f72a671c9bf2b27da160f3249137d9f41'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def native_select_showpicker_predecessor_bytes(raw, *, current_sha256, current_bytes,
                                                predecessor_sha256, reverse_edits):
    """Apply the reviewed reverse edits only to the exact current source bytes."""
    if sha(raw) != current_sha256 or len(raw) != current_bytes:
        return raw
    for start, end, previous in reversed(reverse_edits):
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(raw):
            raise AssertionError('Invalid select showPicker source reverse edit')
        if type(previous) is not str:
            raise AssertionError('Select showPicker reverse edit must be UTF-8 text')
        raw = raw[:start] + previous.encode('utf-8') + raw[end:]
    if sha(raw) != predecessor_sha256:
        raise AssertionError('Exact select showPicker source reverse projection differs')
    return raw


def native_select_showpicker_document_history(imports, projection=None, *, logical,
                                                current_sha256, current_bytes,
                                                prior_row_sha256, correction,
                                                reviewed_source_acceptance_sha256):
    """Restore one exact prior document row before the existing history chain."""
    imports = copy.deepcopy(imports)
    projection = copy.deepcopy(projection)
    item = imports['files'].get(logical)
    if item is None or item['origin'].get('kind') != 'reviewed-native-select-showpicker-successor':
        return (imports, projection) if projection is not None else imports
    wanted = {
        'kind': 'reviewed-native-select-showpicker-successor',
        'correction': correction,
        'source_only': True,
        'source_path': item['tracked_path'],
        'sha256': current_sha256,
        'reviewed_source_acceptance_sha256': reviewed_source_acceptance_sha256,
    }
    origin = item['origin']
    if (imports.get('document_profile') != 'editor' or item['sha256'] != current_sha256
            or type(item['bytes']) is not int or item['bytes'] != current_bytes
            or type(item['mode']) is not int or item['mode'] != 420
            or set(origin) != set(wanted) | {'supersedes'}
            or any(type(origin[key]) is not type(value) or origin[key] != value
                   for key, value in wanted.items())):
        raise AssertionError('Exact native select showPicker source fact/origin required')
    prior = origin['supersedes']
    if type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}:
        raise AssertionError('Complete select showPicker historical predecessor required')
    old = dict(item, **prior)
    canonical = json.dumps(old, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=True, allow_nan=False).encode('ascii')
    if sha(canonical) != prior_row_sha256:
        raise AssertionError('Select showPicker predecessor row was restamped')
    if projection is not None:
        projected = projection['files'][logical]
        if projected['sha256'] != current_sha256:
            raise AssertionError('Select showPicker current projection differs')
        projected['sha256'] = prior['sha256']
    imports['files'][logical] = old
    return (imports, projection) if projection is not None else imports


def native_select_showpicker_main_predecessor_bytes(raw, *, native=False):
    current_sha256 = NATIVE_CURRENT_SHA256 if native else DOCUMENT_CURRENT_SHA256
    current_bytes = NATIVE_CURRENT_BYTES if native else DOCUMENT_CURRENT_BYTES
    predecessor_sha256 = NATIVE_PREVIOUS_SHA256 if native else DOCUMENT_PREVIOUS_SHA256
    reverse_edits = NATIVE_REVERSE_EDITS if native else DOCUMENT_REVERSE_EDITS
    return native_select_showpicker_predecessor_bytes(
        raw, current_sha256=current_sha256, current_bytes=current_bytes,
        predecessor_sha256=predecessor_sha256, reverse_edits=reverse_edits)


def native_select_showpicker_editor_history(imports, projection=None):
    return native_select_showpicker_document_history(
        imports, projection, logical='source/wrapper/src/embedder/main.cpp',
        current_sha256=DOCUMENT_CURRENT_SHA256, current_bytes=DOCUMENT_CURRENT_BYTES,
        prior_row_sha256=DOCUMENT_PREVIOUS_ROW_SHA256, correction=CORRECTION,
        reviewed_source_acceptance_sha256=REVIEWED_SOURCE_ACCEPTANCE_SHA256)

