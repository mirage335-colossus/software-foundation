"""Exact source-only native popup history; no Git, ignored evidence or programs."""
import copy
import hashlib
import json
from native_control_keypress_source_history import native_control_keypress_predecessor_bytes, native_control_keypress_document_history

def sha(raw):return hashlib.sha256(raw).hexdigest()

NATIVE_POPUP_REVERSE = {'f0e6119409d960390e4bca8baaa11f766dfe6827b1f3723b190f638a92864770': {'postimage_bytes': 111163, 'preimage_sha256': '204b4b97d131081e9ee77f3fff05ed7147ee496a89b4e08e24e7a0b9cc6e2c1b', 'preimage_bytes': 110553, 'reverse_edits': [[268, 332, ''], [9600, 10277, ''], [11956, 11956, '            require(!secure, "native for-label lookup would read secure ID");\n'], [12280, 12393, '            if (element) require(!NativeAttributeRead::authorOmittedForAssociation(*element, budget),\n'], [12759, 12834, '                const auto& candidateID = NativeAttributeRead::nativeID(*element, budget, true);\n                budget.chargePrivate(candidateID.length());\n'], [13540, 13642, '        require(!secure, "native implicit-label scan would enter secure children");\n'], [93606, 93710, '                        || session.knownID(*actual) != std::optional<uint64_t>(row.node) || row.omitted) return false;\n'], [93774, 93876, '                    if (row.disabled || actual->isDisabledFormControl()) return false;\n']]}, '074ac417f89760a9cf2c59212454e33133c60eaae68c08f7a5ca86d5224cb603': {'postimage_bytes': 80727, 'preimage_sha256': '0705d9421e853b7633cc2a3df2c0448b0b53da0daf48fd2e7158f98b341b0453', 'preimage_bytes': 80117, 'reverse_edits': [[215, 279, ''], [9336, 10013, ''], [11692, 11692, '            require(!secure, "native for-label lookup would read secure ID");\n'], [12016, 12129, '            if (element) require(!NativeAttributeRead::authorOmittedForAssociation(*element, budget),\n'], [12495, 12570, '                const auto& candidateID = NativeAttributeRead::nativeID(*element, budget, true);\n                budget.chargePrivate(candidateID.length());\n'], [13276, 13378, '        require(!secure, "native implicit-label scan would enter secure children");\n']]}, 'c1cae92f150d65944c723c14755cf9bc87a58c64c6c8fe0a7c3fcf06542506aa': {'postimage_bytes': 41947, 'preimage_sha256': '2bc9f9ceca00c644920e2911438dadcf0642257bf43b530863f618deb36dd7ff', 'preimage_bytes': 39829, 'reverse_edits': [[22016, 22588, ''], [24794, 25325, '    owner.rawSubtree(*this, control, result.lightSubtree, false);\n    result.styleComplete = result.styleComplete && owner.subtreeStyleComplete(result.lightSubtree);\n'], [29181, 29340, '                bool inherited = false;\n'], [29423, 30447, '                    auto sampled = owner.presentation(**it, bounds, inherited);\n                    if (graphical) sampled.omitted = inherited || !sampled.styleKnown || sampled.inert\n                        || sampled.display == static_cast<unsigned>(DisplayType::None)\n'], [30540, 30759, '                    inherited = sampled.omitted;\n'], [30865, 30965, ''], [31373, 31703, '                    // Excluded option: no attributes, text, label or submitted value\n                    // are captured. This intentional baseline gap disables the WHOLE\n                    // select descriptor, never a partially actionable live menu.\n                    complete = false;\n']]}, 'c515fab6e801e2b0139130cdc7a5828b31156645f526914fb1edae74f8aab34f': {'postimage_bytes': 18228, 'preimage_sha256': '63a435cd6409a96a0f9bcc23c3f06431c2d4664159a65ae2ce1b8761c06ffd44', 'preimage_bytes': 17620, 'reverse_edits': [[13529, 14314, '            if (o.omitted&&(!o.label.empty()||c.complete||c.capabilities||c.lease))\n                invalid("omitted option leaks text or grants incomplete control authority");\n']]}, '5d9657543b68ac4be23d14c5476f53e49fe8986a61d9a2c0c708b81bed9541f5': {'postimage_bytes': 32014, 'preimage_sha256': 'd8822f18b214cedf9490a758c52c06a3ca3fc70d9b5b48e9dcbe8de55e4594d9', 'preimage_bytes': 29528, 'reverse_edits': [[443, 521, ''], [7349, 9661, ''], [13046, 13094, ''], [20010, 20058, '']]}}
NATIVE_POPUP_FACTS = {'source/document-provider/native/NativeDocumentV2Publisher.cpp': {'sha256': '074ac417f89760a9cf2c59212454e33133c60eaae68c08f7a5ca86d5224cb603', 'bytes': 80727, 'mode': 420, 'tracked_path': 'recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp', 'role': 'source'}, 'source/document-provider/native/NativeFormsV2Combined.cpp': {'sha256': 'c1cae92f150d65944c723c14755cf9bc87a58c64c6c8fe0a7c3fcf06542506aa', 'bytes': 41947, 'mode': 420, 'tracked_path': 'recipes/webkitwasm-document-v2/source/native/NativeFormsV2Combined.cpp', 'role': 'source'}, 'source/document-provider/portable/NativeDocumentV2Types.cpp': {'sha256': 'c515fab6e801e2b0139130cdc7a5828b31156645f526914fb1edae74f8aab34f', 'bytes': 18228, 'mode': 420, 'tracked_path': 'recipes/webkitwasm-document-v2/source/portable/NativeDocumentV2Types.cpp', 'role': 'source'}, 'source/document-provider/popup/BibNativePopupOwner.cpp': {'sha256': '5d9657543b68ac4be23d14c5476f53e49fe8986a61d9a2c0c708b81bed9541f5', 'bytes': 32014, 'mode': 420, 'tracked_path': 'recipes/webkitwasm-document-v2/overlays/ui/popup/BibNativePopupOwner.cpp', 'role': 'source'}}
NATIVE_POPUP_PRIOR_ROWS = {'pixel': {'source/document-provider/native/NativeDocumentV2Publisher.cpp': 'd7954370147f187f1a3e7255685285da9fe696d2433059f72d4be579c0ec4856', 'source/document-provider/native/NativeFormsV2Combined.cpp': '10d44ed9d5e13cbe48b5ee3635705b315a507d4ba5ea46c2746319a414a34c61', 'source/document-provider/portable/NativeDocumentV2Types.cpp': 'fffa686c0e380cfaba8cbd6be7b267309120f295d1a13b01362cc7fce1f64211'}, 'physical': {'source/document-provider/native/NativeDocumentV2Publisher.cpp': 'c80037ca51f9d42e77ed4052db4863a169d8b2375b3f257d150a96a8368f61fa', 'source/document-provider/native/NativeFormsV2Combined.cpp': '124e7fc216f3890f55ace6e2abf981afdc2d0cb82f317bc9ef3a09896fc3a1a5', 'source/document-provider/popup/BibNativePopupOwner.cpp': 'd63a5b1481aae7b89d7609fd4373d50205ac7998cd75170655e52cde79cf9260', 'source/document-provider/portable/NativeDocumentV2Types.cpp': '9c8df5ea57a4a5fd2cc35312f1e5b78906733bebc245ac254e001aa620d1a375'}, 'editor': {'source/document-provider/native/NativeDocumentV2Publisher.cpp': '9b6ca18e0c0da1f480d73e038a8e9027d4b96ac8d19cbdf1cd7c1962a58ffc41', 'source/document-provider/native/NativeFormsV2Combined.cpp': '56c1afb421364a90e4cd8c6d8ad5af89128eb776e96e235c53192026a0c2f960', 'source/document-provider/popup/BibNativePopupOwner.cpp': 'd63a5b1481aae7b89d7609fd4373d50205ac7998cd75170655e52cde79cf9260', 'source/document-provider/portable/NativeDocumentV2Types.cpp': '466c3ad4d374405d11e00767d94e07fc577efd45379077fa1a8851dc66cead6d'}}

def native_popup_predecessor_bytes(raw):
    raw=native_control_keypress_predecessor_bytes(raw)
    projection=NATIVE_POPUP_REVERSE.get(sha(raw))
    if projection is None:return raw
    if len(raw)!=projection['postimage_bytes']:raise AssertionError('Native popup source postimage size differs')
    for start,end,old in reversed(projection['reverse_edits']):raw=raw[:start]+old.encode('utf-8')+raw[end:]
    if sha(raw)!=projection['preimage_sha256'] or len(raw)!=projection['preimage_bytes']:
        raise AssertionError('Exact native popup source reverse projection differs')
    return raw


def native_popup_history(imports,projection=None):
    """Validate exact new facts/full prior row before exposing historical data."""
    if projection is None:imports=native_control_keypress_document_history(imports)
    else:imports,projection=native_control_keypress_document_history(imports,projection)
    imports=copy.deepcopy(imports);projection=copy.deepcopy(projection)
    profile=imports['document_profile'];seen=set()
    for name,item in imports['files'].items():
        origin=item['origin']
        if origin.get('kind')!='reviewed-native-popup-capability-successor':continue
        expected=NATIVE_POPUP_FACTS.get(name)
        if expected is None or any(type(item[key]) is not type(value) or item[key]!=value for key,value in expected.items()):
            raise AssertionError('Exact reviewed native popup source fact differs')
        wanted={'kind':'reviewed-native-popup-capability-successor',
            'correction':'bounded-private-label-association-and-css-opaque-single-menu-popup',
            'source_only':True,'source_path':item['tracked_path'],'sha256':item['sha256'],
            'reviewed_source_map_sha256':'969ca78d0594ba0aeb0191a676319c0f030aa47ae09a613e2f154439011b13e4'}
        if set(origin)!=set(wanted)|{'supersedes'} or any(type(origin[key]) is not type(value) or origin[key]!=value for key,value in wanted.items()):
            raise AssertionError('Exact source-only native popup origin required')
        prior=origin['supersedes']
        if type(prior) is not dict or set(prior)!={'origin','sha256','bytes','tracked_path'} or type(prior['bytes']) is not int:
            raise AssertionError('Complete native popup predecessor required')
        previous=dict(item,**prior)
        canonical=json.dumps(previous,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
        if sha(canonical)!=NATIVE_POPUP_PRIOR_ROWS[profile].get(name):raise AssertionError('Native popup historical predecessor was restamped')
        if projection is not None:
            if projection['files'][name]['sha256']!=item['sha256']:raise AssertionError('Native popup current projection differs')
            projection['files'][name]['sha256']=prior['sha256']
        imports['files'][name]=previous;seen.add(name)
    if seen and seen!=set(NATIVE_POPUP_PRIOR_ROWS[profile]):raise AssertionError('Native popup exact per-profile successor leaves required')
    return (imports,projection) if projection is not None else imports
