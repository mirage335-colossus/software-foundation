"""Exact native select inline include source history; no SDK or programs."""
import copy
import hashlib
import json

CURRENT_SHA256 = '9d5d434c1af6109c7a007e67fcceccb48b5549339663ada3621736bcbeefde47'
PREVIOUS_SHA256 = 'ee79f3bc8488cfd92c9b62abc2e84a9c110221cf2eba805fac4803980bae612a'
REVERSE_EDITS = [[355, 381, ''], [862, 896, ''], [904, 932, ''], [1039, 1084, '']]
EDITOR_PREVIOUS_ROW_SHA256 = '5114e261055dcde0aa3d9eab882efab0e9f8c39f3c2155e27bdd144cf2bc4e33'

def native_control_includes_predecessor_bytes(raw):
    if hashlib.sha256(raw).hexdigest() != CURRENT_SHA256:
        return raw
    text = raw.decode('utf-8')
    for start, end, old in reversed(REVERSE_EDITS):
        text = text[:start] + old + text[end:]
    result = text.encode('utf-8')
    if hashlib.sha256(result).hexdigest() != PREVIOUS_SHA256:
        raise AssertionError('Native control includes source reverse projection differs')
    return result


def native_control_includes_document_history(imports, projection=None):
    imports = copy.deepcopy(imports)
    projection = copy.deepcopy(projection)
    name = 'source/document-provider/physical/BibDocumentPhysicalProvider.cpp'
    item = imports['files'].get(name)
    if item and item['origin'].get('kind') == 'reviewed-native-control-includes-successor':
        origin = item['origin']
        wanted = {'kind': 'reviewed-native-control-includes-successor',
            'correction': 'explicit-webcore-inline-definitions-for-native-control-default',
            'source_only': True, 'source_path': item['tracked_path'], 'sha256': CURRENT_SHA256,
            'reviewed_source_map_sha256': 'e627f0e1f16cd71af396cada9c99c8c313fc90c47f6e104252a83db32e19863a'}
        if (imports['document_profile'] != 'editor' or item['sha256'] != CURRENT_SHA256
                or type(item['bytes']) is not int or item['bytes'] != 30284
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
            raise AssertionError('Native control includes predecessor restamped')
        if projection is not None:
            if projection['files'][name]['sha256'] != CURRENT_SHA256:
                raise AssertionError('Native control includes current projection differs')
            projection['files'][name]['sha256'] = PREVIOUS_SHA256
        imports['files'][name] = old
    return (imports, projection) if projection is not None else imports
