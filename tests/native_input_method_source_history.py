"""Exact source-only history for native input-method lifecycle retirement."""
import copy
import hashlib
import json


CURRENT_SHA256 = '283876d4a85cd07b800f0c54ee96695ab5345146481f41e1a615a44fc9e5c7aa'
CURRENT_BYTES = 30339
PREVIOUS_SHA256 = '6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43'
PREVIOUS_BYTES = 29858
PREVIOUS_SOURCE_MAP_SHA256 = '9e6b36bcfd6efdbc834c8fb06ef2ab9ca5a7dadb91b9c0d78b7a94fddf0bcf31'
RECIPE = 'recipes/webkitwasm-native-rich4083-v1/'
PREVIOUS_INSPECTOR = {'bytes': 51246, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': '12ae1239503fab0148d7d3872322dfa87d97415ef854c47840b730d1a3b5c0fb', 'tracked_path': RECIPE + 'inspect_sources.py'}
PREVIOUS_PROVENANCE_SHA256 = 'e4b1c122b95fe2b629ad80818552bc354614223d8fadcf7de004aed5b857084c'
PREVIOUS_PROVENANCE_BYTES = 184668
HEADER = 'source/wrapper/src/embedder/BibPageClients.h'
INSERTIONS = (
    b'    void retireInputMethodStateForMainDocument(bool isMainFrame)\n'
    b'    {\n'
    b'#if BIB_ENGINE_PROVIDER_DOCUMENT_V2\n'
    b'        if (isMainFrame)\n'
    b'            setInputMethodState(nullptr);\n'
    b'#else\n'
    b'        (void)isMainFrame;\n'
    b'#endif\n'
    b'    }\n\n',
    b'#if BIB_ENGINE_PROVIDER_DOCUMENT_V2\n'
    b'        if (m_serviceMainFrame) {\n'
    b'            if (auto* page = m_frameLoader->frame().page())\n'
    b'                static_cast<BibEditorClient&>(page->editorClient()).retireInputMethodStateForMainDocument(true);\n'
    b'        }\n'
    b'#endif\n',
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def native_input_method_predecessor_bytes(raw):
    """Remove only the two accepted main-document lifecycle insertions."""
    if sha(raw) != CURRENT_SHA256 or len(raw) != CURRENT_BYTES:
        return raw
    previous = raw
    for insertion in reversed(INSERTIONS):
        if previous.count(insertion) != 1:
            raise AssertionError('Exact native input-method lifecycle insertion required once')
        previous = previous.replace(insertion, b'', 1)
    if len(previous) != PREVIOUS_BYTES or sha(previous) != PREVIOUS_SHA256:
        raise AssertionError('Native input-method source reverse projection differs')
    return previous


def native_input_method_source_map_history(value):
    """Restore the accepted select-events map and its complete header origin."""
    value = copy.deepcopy(value)
    logical = HEADER
    if type(value) is not dict or value.get('kind') != 'foundation-native-engine-actions-input-method-source-inputs-v1':
        return value
    item = value['inputs'][logical]
    origin = item['origin']
    record = origin['record']
    successor = record['successor']
    if (item.get('sha256') != CURRENT_SHA256 or item.get('bytes') != CURRENT_BYTES
            or successor.get('kind') != 'reviewed-native-input-method-successor'):
        raise AssertionError('Exact native input-method current row/successor required')
    old_record = successor['supersedes']
    value['inputs'][logical] = dict(item, sha256=PREVIOUS_SHA256, bytes=PREVIOUS_BYTES,
                                    origin={'kind': origin['kind'], 'record': old_record})
    value['inputs']['inspect_sources.py'] = dict(PREVIOUS_INSPECTOR)
    value['provenance']['sha256'] = PREVIOUS_PROVENANCE_SHA256
    value['inputs']['provenance.json'].update(sha256=PREVIOUS_PROVENANCE_SHA256,
                                               bytes=PREVIOUS_PROVENANCE_BYTES)
    value['kind'] = 'foundation-native-engine-actions-select-events-source-inputs-v1'
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if sha(raw) != PREVIOUS_SOURCE_MAP_SHA256:
        raise AssertionError('Exact native input method source-map predecessor differs')
    return value


DOCUMENT_PREVIOUS_ROW_SHA256 = '27dc10a5bf2c4ade7a0b3a29ff1fa310957acd97070d5277b0d2bfff3ec8cf40'
REVIEWED_SOURCE_ACCEPTANCE_SHA256 = '539a2dd0ee5992cfcf260d35f1014f1df749af371cdfead31658867e211fdda9'
CORRECTION = 'reset-native-input-method-state-on-main-document-lifecycle'


def native_input_method_document_history(imports, projection=None):
    """Restore only the accepted editor header row with all supplier ancestry."""
    imports, projection = copy.deepcopy(imports), copy.deepcopy(projection)
    item = imports['files'].get(HEADER)
    if item is None or item['origin'].get('kind') != 'reviewed-native-input-method-successor':
        return (imports, projection) if projection is not None else imports
    origin = item['origin']
    wanted = {'kind': 'reviewed-native-input-method-successor', 'correction': CORRECTION,
        'source_only': True, 'source_path': item['tracked_path'], 'sha256': CURRENT_SHA256,
        'reviewed_source_acceptance_sha256': REVIEWED_SOURCE_ACCEPTANCE_SHA256}
    if (imports.get('document_profile') != 'editor' or item.get('sha256') != CURRENT_SHA256
            or type(item.get('bytes')) is not int or item['bytes'] != CURRENT_BYTES
            or type(item.get('mode')) is not int or item['mode'] != 420 or item.get('role') != 'source'
            or set(origin) != set(wanted) | {'supersedes'}
            or any(type(origin[key]) is not type(value) or origin[key] != value for key, value in wanted.items())):
        raise AssertionError('Exact native input method editor current fact/origin required')
    prior = origin['supersedes']
    if type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}:
        raise AssertionError('Complete native input method editor predecessor required')
    old = dict(item, **prior)
    if sha(canonical(old)) != DOCUMENT_PREVIOUS_ROW_SHA256:
        raise AssertionError('Native input method editor predecessor was restamped')
    if projection is not None:
        projected = projection['files'].get(HEADER)
        if type(projected) is not dict or projected.get('sha256') != CURRENT_SHA256:
            raise AssertionError('Native input method editor projection differs')
        projected['sha256'] = PREVIOUS_SHA256
    imports['files'][HEADER] = old
    return (imports, projection) if projection is not None else imports
