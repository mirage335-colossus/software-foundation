"""Exact native select keypress source history; no SDK or programs."""
import copy
import hashlib
import json
from native_control_includes_source_history import native_control_includes_predecessor_bytes, native_control_includes_document_history

CURRENT_SHA256 = 'ee79f3bc8488cfd92c9b62abc2e84a9c110221cf2eba805fac4803980bae612a'
PREVIOUS_SHA256 = '94ac6af05af059faaff51e7c4e1f59d90f78430898c4fe6ef9d1255e7c4f9c81'
REVERSE_EDITS = [[241, 570, ''], [1393, 1437, ''], [7359, 14470, ''], [23484, 24662, '']]
EDITOR_PREVIOUS_ROW_SHA256 = 'e6142b11e2dad53874f413f4e406d9bea8e3ed40d4eafd8900aff9485853ce7b'

def native_control_keypress_predecessor_bytes(raw):
    raw = native_control_includes_predecessor_bytes(raw)
    if hashlib.sha256(raw).hexdigest() != CURRENT_SHA256:
        return raw
    text = raw.decode('utf-8')
    for start, end, old in reversed(REVERSE_EDITS):
        text = text[:start] + old + text[end:]
    result = text.encode('utf-8')
    if hashlib.sha256(result).hexdigest() != PREVIOUS_SHA256:
        raise AssertionError('Native control keypress source reverse projection differs')
    return result


def native_control_keypress_document_history(imports, projection=None):
    if projection is None:
        imports = native_control_includes_document_history(imports)
    else:
        imports, projection = native_control_includes_document_history(imports, projection)
    imports = copy.deepcopy(imports)
    projection = copy.deepcopy(projection)
    name = 'source/document-provider/physical/BibDocumentPhysicalProvider.cpp'
    item = imports['files'].get(name)
    if item and item['origin'].get('kind') == 'reviewed-native-control-keypress-successor':
        origin = item['origin']
        wanted = {'kind': 'reviewed-native-control-keypress-successor',
            'correction': 'trusted-cancelable-select-space-keypress-before-native-control-default',
            'source_only': True, 'source_path': item['tracked_path'], 'sha256': CURRENT_SHA256,
            'reviewed_source_map_sha256': '939bb574a2a3e3d5b24a3345d0da1613b8d8526d4b80177d05cd78d27f567b11'}
        if (imports['document_profile'] != 'editor' or item['sha256'] != CURRENT_SHA256
                or type(item['bytes']) is not int or item['bytes'] != 30151
                or type(item['mode']) is not int or item['mode'] != 420
                or set(origin) != set(wanted) | {'supersedes'}
                or any(type(origin[key]) is not type(value) or origin[key] != value for key, value in wanted.items())):
            raise AssertionError('Exact native control keypress current fact/origin required')
        prior = origin['supersedes']
        if type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}:
            raise AssertionError('Complete native control keypress predecessor required')
        old = dict(item, **prior)
        raw = json.dumps(old, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
        if hashlib.sha256(raw).hexdigest() != EDITOR_PREVIOUS_ROW_SHA256:
            raise AssertionError('Native control keypress predecessor restamped')
        if projection is not None:
            if projection['files'][name]['sha256'] != CURRENT_SHA256:
                raise AssertionError('Native control keypress current projection differs')
            projection['files'][name]['sha256'] = PREVIOUS_SHA256
        imports['files'][name] = old
    return (imports, projection) if projection is not None else imports
