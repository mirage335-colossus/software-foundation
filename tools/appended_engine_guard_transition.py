"""Pure exact native form Guard/source-history transitions; no admission authority."""
from copy import deepcopy
import hashlib
import json

SOURCE_KIND = 'foundation-native-engine-actions-retired-form-preflight-source-inputs-v1'
PREDECESSOR_SOURCE_KIND = 'foundation-native-engine-actions-input-method-source-inputs-v1'
PREDECESSOR_MAP_SHA256 = '13cbe3ca607bb5cba54f1f880f9b2471b430c9be3563a7f3a623ed9ceb7cff03'
GUARD = 'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
CURRENT_SHA256 = 'c0e73457c85e3b54c956cad124407ff0fd03d53b0abdfdb5003f6146990a8157'
CURRENT_BYTES = 75818
PREDECESSOR_SHA256 = '3aebfcc5b4e838846f23a5c9c61a62acc51fecc73541fd58deaa9c157308b0ff'
PREDECESSOR_BYTES = 74981
PREDECESSOR_INSPECTOR = {'bytes': 59714, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': 'f8f5eaddb0a6948e56c35859dded7676cc176350b000bc0135447176697646e4', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}
PREDECESSOR_PROVENANCE = {'sha256': '124b5904cdf711214ea3ade9cf840f179c1f3e439b29f60cfd01e4408cf4101c', 'bytes': 185327}
INSERTION = b'// Form request identity is inert metadata. Let the publisher reject a\n        // retired cached identity before entering the host turn, while keeping\n        // the in-turn validation below to cover navigation during host entry.\n        if (form) {\n            std::int32_t checked{};\n            try {\n                checked=transport(document_backend.validate_request(backend.context,document_backend.worker_epoch,\n                    &request.expected,0,request.operation,request.request_sequence,&request.payload));\n            } catch (...) {\n                poisoned=true;\n                return reject(BIB_ENGINE_PROCESS_EXIT_REQUIRED);\n            }\n            if (checked) {\n                if (checked==BIB_ENGINE_PROCESS_EXIT_REQUIRED) poisoned=true;\n                return reject(checked);\n            }\n        }\n        '


def _encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def canonical_predecessor_bytes(raw):
    """Reverse only the accepted canonical Guard delta; never accept editor bytes."""
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != CURRENT_SHA256 or len(raw) != CURRENT_BYTES:
        raise ValueError('Exact current canonical form Guard bytes required')
    if raw.count(INSERTION) != 1:
        raise ValueError('Exact form preflight insertion required once')
    previous = raw.replace(INSERTION, b'', 1)
    if len(previous) != PREDECESSOR_BYTES or hashlib.sha256(previous).hexdigest() != PREDECESSOR_SHA256:
        raise ValueError('Exact canonical form Guard predecessor differs')
    return previous


def catalogue_predecessor(value):
    """Recover the exact accepted InputMethod map without opening predecessor paths."""
    value = deepcopy(value)
    if type(value) is not dict or value.get('kind') != SOURCE_KIND:
        return value
    row = value['inputs'][GUARD]
    prior = row['origin']['record']['successor']['supersedes']
    value['inputs'][GUARD] = dict(row, sha256=PREDECESSOR_SHA256, bytes=PREDECESSOR_BYTES,
        origin={'kind': 'mapped-native-actions-runtime', 'record': prior})
    value['kind'] = PREDECESSOR_SOURCE_KIND
    value['inputs']['inspect_sources.py'] = deepcopy(PREDECESSOR_INSPECTOR)
    value['inputs']['provenance.json'].update(PREDECESSOR_PROVENANCE)
    value['provenance']['sha256'] = PREDECESSOR_PROVENANCE['sha256']
    if hashlib.sha256(_encoded(value)).hexdigest() != PREDECESSOR_MAP_SHA256:
        raise ValueError('Exact form Guard catalogue predecessor differs')
    return value


def provenance_predecessor(value):
    """Restore complete prior runtime provenance without cloning ancestor tables."""
    value = deepcopy(value)
    record = value['runtime_files'][GUARD]
    if record.get('successor', {}).get('kind') != 'reviewed-native-retired-form-preflight-successor':
        return value
    value['runtime_files'][GUARD] = record['successor']['supersedes']
    raw = _encoded(value)
    if len(raw) != PREDECESSOR_PROVENANCE['bytes'] or hashlib.sha256(raw).hexdigest() != PREDECESSOR_PROVENANCE['sha256']:
        raise ValueError('Exact form Guard provenance predecessor differs')
    return value
