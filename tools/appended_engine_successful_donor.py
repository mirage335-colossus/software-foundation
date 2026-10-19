#!/usr/bin/env python3
"""Explicit admission of the pinned successful FRESH-J1 donor products.

This is a separate continuation contract.  It preserves the failed original
outer readback and requires its subsequent, closed passive qualification.
There is no discovery, subprocess, compiler, archive driver or copy operation.
The supplied maintenance API owns strict metadata and physical-fact reads.
"""
import hashlib
from pathlib import Path


DONOR_KIND = 'foundation-document-v2-successful-donor-v1'
PLAN_KIND = 'foundation-document-v2-maintenance-successful-donor-plan-v1'
BUILD_KIND = 'foundation-document-v2-maintenance-successful-donor-build-v1'
COMPILED_IDS = ('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp')
GUARD_REPAIR_DONOR_KIND = 'foundation-document-v2-successful-donor-guard-repair-v1'
GUARD_REPAIR_PLAN_KIND = 'foundation-document-v2-maintenance-successful-donor-guard-repair-plan-v1'
GUARD_REPAIR_BUILD_KIND = 'foundation-document-v2-maintenance-successful-donor-guard-repair-build-v1'
GUARD_REPAIR_COMPILED_IDS = COMPILED_IDS + ('ProviderGuard.cpp',)
COMPOSITION_REPAIR_DONOR_KIND = 'foundation-document-v2-successful-donor-composition-repair-v1'
COMPOSITION_REPAIR_PLAN_KIND = 'foundation-document-v2-maintenance-successful-donor-composition-repair-plan-v1'
COMPOSITION_REPAIR_BUILD_KIND = 'foundation-document-v2-maintenance-successful-donor-composition-repair-build-v1'
COMPOSITION_REPAIR_COMPILED_IDS = GUARD_REPAIR_COMPILED_IDS + ('BibNativeEditorBackend.cpp', 'main.cpp')

ROOT_ACCEPTANCE_SHA256 = 'fda45ea612c3b1ed86ed3b0edc98fb631fc64caeb8d27562c2a44fab849a9bb1'
ROOT_FAILURE_SHA256 = '6fe22d439e8fbaa6076edb3fbf89de45e46ea1df6f1b9a65bad4bb1bc48f2b00'
PASSIVE_WORKER_SHA256 = '22eae44bae01ce54469763d1c94a5bf1da9d29cf2f6fdaae388d92fa5b1f656d'
MAINTENANCE_BUILD_SHA256 = 'f307a4fcf1e4db9a444d01871004d2dbec9bc7a25cc0daed9142eb90ee45d820'
ORIGINAL_PLAN_SHA256 = '953a4f47bc524d7410c58710f49b5254bf44e0821255b650bfd409c75eb4b8f7'

DESCRIPTOR_FIELDS = ('schema_version', 'kind', 'document_profile', 'original_bindings',
    'original_plan', 'original_commands', 'root_failure', 'candidate_result',
    'original_input_freeze', 'original_build_packet', 'root_launch', 'root_handle',
    'original_private', 'ninja_log', 'dependency_sidecar', 'objects',
    'root_acceptance', 'passive_worker', 'passive_result', 'maintenance_build', 'archives')
ARCHIVE_COUNTS = {'JavaScriptCore': 185, 'PAL': 24, 'Skia': 775, 'WTF': 168, 'WebCore': 924}


def _require(condition, label):
    if not condition:
        raise ValueError('Successful donor ' + label)


def _integer(value, expected):
    return type(value) is int and value == expected


def _reference(value, api, expected=None):
    api.fields(value, ('path', 'sha256'), 'successful donor metadata reference')
    if expected is not None:
        _require(value['sha256'] == expected, 'historical metadata pin differs')
    return api._completed_reference(value)


def _referenced(owner, reference, api):
    rows = owner.get('references')
    _require(type(rows) is list, 'authority references are absent')
    matching = [row for row in rows if type(row) is dict
                and row.get('path') == reference['path']]
    _require(len(matching) == 1 and matching[0].get('sha256') == reference['sha256'],
             'authority metadata reference differs')
    row = matching[0]
    api.fields(row, ('path', 'sha256', 'bytes', 'identity'), 'successful donor attested metadata')
    identity = row['identity']
    _require(type(identity) is list and len(identity) == 7
        and all(type(item) is int for item in identity), 'attested metadata identity differs')
    # Root references record the complete stat mode in identity[2], without a
    # separate permission field.  Preserve that exact physical authority when
    # using the common fact reader; it checks identity before and after hashing.
    api._completed_fact(dict(row, mode=identity[2] & 0o777))


def _natural(report, api):
    api.fields(report, ('schema_version', 'primary_returncode', 'descendants_outlived',
        'terminated', 'reaped', 'error'), 'successful donor natural supervision')
    _require(_integer(report['schema_version'], 1)
        and _integer(report['primary_returncode'], 0)
        and report['descendants_outlived'] is False and report['terminated'] is False
        and report['error'] is None and type(report['reaped']) is int and report['reaped'] >= 1,
        'work did not finish naturally')


def _fact_shape(fact, path, api):
    api.fields(fact, ('path', 'sha256', 'bytes', 'mode', 'identity'), 'successful donor product fact')
    identity = fact['identity']
    _require(fact['path'] == str(path) and type(fact['bytes']) is int and fact['bytes'] > 0
        and type(fact['mode']) is int and 0 <= fact['mode'] <= 0o777
        and type(identity) is list and len(identity) == 7
        and all(type(item) is int for item in identity) and identity[3] == 1
        and identity[4] == fact['bytes'], 'product path/physical fact differs')
    _require(type(fact['sha256']) is str and len(fact['sha256']) == 64
        and all(char in '0123456789abcdef' for char in fact['sha256'])
        and fact['sha256'] != '0' * 64, 'product hash differs')


def _metadata(value, bindings, old, api, *, guard_repair=False, composition_repair=False):
    if type(composition_repair) is not bool or composition_repair and guard_repair:
        raise ValueError('Composition repair requires an exclusive boolean opt-in')
    api.fields(value, DESCRIPTOR_FIELDS, 'successful donor selection')
    kind = (COMPOSITION_REPAIR_DONOR_KIND if composition_repair else
            GUARD_REPAIR_DONOR_KIND if guard_repair else DONOR_KIND)
    compiled = (COMPOSITION_REPAIR_COMPILED_IDS if composition_repair else
                GUARD_REPAIR_COMPILED_IDS if guard_repair else COMPILED_IDS)
    _require(_integer(value['schema_version'], 1) and value['kind'] == kind
        and value['document_profile'] == 'editor', 'descriptor identity/profile differs')
    _require(value['original_plan'].get('sha256') == ORIGINAL_PLAN_SHA256,
             'original default plan pin differs')
    root = _reference(value['root_acceptance'], api, ROOT_ACCEPTANCE_SHA256)
    failure = _reference(value['root_failure'], api, ROOT_FAILURE_SHA256)
    worker = _reference(value['passive_worker'], api, PASSIVE_WORKER_SHA256)
    build = _reference(value['maintenance_build'], api, MAINTENANCE_BUILD_SHA256)
    result = _reference(value['passive_result'], api)
    original = _reference(value['candidate_result'], api)
    _referenced(root, value['passive_worker'], api)
    _referenced(root, value['passive_result'], api)
    _referenced(failure, value['candidate_result'], api)
    _referenced(failure, value['maintenance_build'], api)
    _require(value['maintenance_build']['path'] == str(Path(bindings['build']) / 'maintenance-build.json'),
             'maintenance build path differs')

    _require(failure.get('kind') == 'root-closed-build51-execution-and-readback-defect-v1'
        and _integer(failure.get('actual_session'), 6290)
        and _integer(failure.get('actual_caller_returncode'), 1)
        and _integer(failure.get('inner_returncode'), 0)
        and failure.get('original_outer_status') == 'failed-preserved'
        and failure.get('closed') is True and failure.get('writers_joined') is True
        and failure.get('production_eligible') is False and failure.get('runtime_not_run') is True
        and failure.get('input_identity_namespace_postflight') == 'passed',
        'original 6290 failure was restamped or not closed')
    _natural(failure.get('qualified_report'), api)
    _require(original.get('status') == 'failed' and _integer(original.get('returncode'), 0)
        and original.get('closed') is True and original.get('writers_joined') is True
        and original.get('production_eligible') is False and original.get('runtime_not_run') is True
        and original.get('input_identity_namespace_postflight') == 'passed'
        and original.get('supervisor_report') == failure['qualified_report'],
        'original candidate did not preserve its readback failure')

    _require(root.get('kind') == 'root-closed-passive-j1-candidate-readback-accepted-v1'
        and _integer(root.get('actual_session'), 81951)
        and _integer(root.get('actual_caller_returncode'), 0)
        and root.get('closed') is True and root.get('writers_joined') is True
        and root.get('original6290_outer_status') == 'failed-preserved'
        and root.get('input_identity_namespace_postflight') == 'passed'
        and root.get('static_byte_readback') == 'passed'
        and root.get('all_artifact_physical_identities_root_rechecked') is True
        and root.get('production_eligible') is False and root.get('runtime_not_run') is True
        and root.get('new_compile_archive_link_runtime') is False
        and _integer(root.get('actual_objects'), 51)
        and _integer(root.get('actual_archive_reports'), 5)
        and _integer(root.get('opaque_unchanged_members'), 2060)
        and _integer(root.get('verified_artifact_records'), 112),
        'passive root qualification differs')
    _natural(root.get('qualified_report'), api)
    _require(result.get('status') == 'passed' and _integer(result.get('returncode'), 0)
        and result.get('closed') is True and result.get('writers_joined') is True
        and result.get('verified') is True and result.get('production_eligible') is False
        and result.get('new_build_or_runtime') is False and result.get('runtime_not_run') is True
        and result.get('original_outer6290_status') == 'failed-preserved'
        and result.get('input_identity_namespace_postflight') == 'passed'
        and result.get('supervisor_report') == root['qualified_report']
        and result.get('passive_readback') == worker,
        'passive caller/worker qualification differs')
    _require(worker.get('kind') == 'private-passive-j1-readback-result-v1'
        and worker.get('status') == 'passed'
        and worker.get('original_outer6290_status') == 'failed-preserved'
        and worker.get('root_closed_wrapper_sha256') == ROOT_FAILURE_SHA256
        and worker.get('SDK_programs_compiler_archive_link_runtime') is False
        and worker.get('runtime_not_run') is True, 'passive worker identity/status differs')
    packet_reference = {'path': str(Path(value['passive_worker']['path']).parent.parent / 'PACKET.json'),
                        'sha256': worker.get('packet_sha256')}
    _referenced(root, packet_reference, api)
    verification = worker.get('verification')
    api.fields(verification, ('actual_archive_reports', 'actual_objects', 'artifact_records',
        'inspection_sha256', 'maintenance_build_sha256', 'opaque_unchanged_members',
        'runtime_not_run', 'static_byte_readback'), 'successful donor passive verification')
    _require(_integer(verification['actual_archive_reports'], 5)
        and _integer(verification['actual_objects'], 51)
        and _integer(verification['opaque_unchanged_members'], 2060)
        and verification['static_byte_readback'] == 'passed' and verification['runtime_not_run'] is True
        and verification['maintenance_build_sha256'] == MAINTENANCE_BUILD_SHA256,
        'passive product counts/build binding differ')

    selected = [row['id'] for row in old['reuse']['objects']]
    _require(len(selected) == 51 and len(set(selected)) == 51
        and all(name in selected for name in compiled), 'original selected51 differs')
    imported = [name for name in selected if name not in compiled]
    _require(type(value['objects']) is list and all(type(row) is dict for row in value['objects'])
        and [row.get('id') for row in value['objects']] == imported,
             'must import exact46 and compile only Publisher/Shim/ProviderGuard/Backend/main' if composition_repair
             else 'must import exact48 and compile only Publisher/Shim/ProviderGuard' if guard_repair
             else 'must import exact49 and compile only Publisher/Shim')
    objects = build.get('objects')
    _require(_integer(build.get('schema_version'), 1) and build.get('kind') == 'foundation-document-v2-maintenance-build-v1'
        and build.get('status') == 'passed' and build.get('production_eligible') is False
        and build.get('plan_sha256') == ORIGINAL_PLAN_SHA256
        and build.get('source_recipe_sha256') == old['selection']['recipe_sha256']
        and build.get('sources_sha256') == old['selection']['sources_sha256']
        and build.get('paired_sdk_sha256') == old['selection']['sdk_manifest_sha256']
        and type(objects) is list and all(type(row) is dict for row in objects)
        and [row.get('id') for row in objects] == selected
        and build.get('commands') == {'path': 'evidence/commands.json',
                                     'sha256': value['original_commands']['sha256']},
        'successful maintenance receipt differs')
    inspection = build.get('inspection')
    _require(type(inspection) is dict
        and hashlib.sha256(api.encoded(inspection)).hexdigest() == verification['inspection_sha256'],
        'passive inspection bytes differ')
    archives = old['reuse']['archives']
    names = [row['name'] for row in archives]
    _require(len(names) == 5 and len(set(names)) == 5 and set(names) == set(ARCHIVE_COUNTS)
        and all(len(row['members']) == ARCHIVE_COUNTS[row['name']] for row in archives),
        'original five archive boundaries differ')
    records = verification['artifact_records']
    expected = {part for name in selected for part in ('objects/' + name + '.o', 'objects/' + name + '.o.d')}
    expected.update('archives/lib' + name + '.a' for name in names)
    expected.update(('artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h', 'document-generated/provider-build.json',
        'evidence/engine-link.map'))
    _require(type(records) is dict and set(records) == expected and len(records) == 112,
             'passive112 product namespace differs')
    for name, fact in records.items():
        _fact_shape(fact, Path(bindings['build']) / name, api)
    for row in objects:
        fact = records['objects/' + row['id'] + '.o']
        _require(row.get('sha256') == fact['sha256'] and row.get('bytes') == fact['bytes'],
                 'maintenance object differs from passive product fact')
    for row in value['objects']:
        _require(row.get('object') == records['objects/' + row['id'] + '.o']
            and row.get('depfile') == records['objects/' + row['id'] + '.o.d'],
            'selected import differs from passive object/depfile fact')
    return build, records


def authority(value, bindings, old, api, *, guard_repair=False, composition_repair=False):
    """Return the original four authorities after the composite success joins."""
    result = api._completed_authority(value, bindings, old)
    _metadata(value, bindings, old, api, guard_repair=guard_repair, composition_repair=composition_repair)
    return result


def archive_rows(value, inspection, old, bindings, api, *, guard_repair=False, composition_repair=False):
    """Admit ordered, exact donor archives without executing an archive tool.

    Physical fact reads happen only when this function is explicitly called by
    admission.  A pinned passive readback binds each archive hash to its full
    ordered member table, independently reproduced from the unchanged plan.
    """
    build, records = _metadata(value, bindings, old, api, guard_repair=guard_repair, composition_repair=composition_repair)
    compiled = (COMPOSITION_REPAIR_COMPILED_IDS if composition_repair else
                GUARD_REPAIR_COMPILED_IDS if guard_repair else COMPILED_IDS)
    proof = inspection.proof
    _require(proof['archives'] == old['reuse']['archives']
        and proof['replacements'] == old['reuse']['replacements'],
        'archive member/replacement plan changed')
    archives = proof['archives']
    rows = value['archives']
    names = [row['name'] for row in archives]
    _require(type(rows) is list and all(type(row) is dict for row in rows)
        and [row.get('name') for row in rows] == names,
             'archive rows must preserve the exact five archive order')
    reports = build['inspection'].get('archives')
    _require(type(reports) is list and all(type(row) is dict for row in reports)
        and [row.get('name') for row in reports] == names,
             'maintenance archive reports differ')
    replacements = {(row['archive'], row['ordinal']): row['object_id'] for row in proof['replacements']}
    _require(len(replacements) == 16 and len(proof['replacements']) == 16
        and sum(len(row['members']) for row in archives) - len(replacements) == 2060,
        'archive replacement/opaque accounting differs')
    objects = {row['id']: row for row in build['objects']}
    admitted = []
    for row, archive, prior in zip(rows, archives, reports):
        api.fields(row, ('name', 'archive', 'report'), 'successful donor archive row')
        name = row['name']
        fact = records['archives/lib' + name + '.a']
        _require(row['archive'] == fact, 'archive differs from passive physical fact')
        _fact_shape(row['report'], Path(bindings['build']) / ('evidence/archive-' + name + '.json'), api)
        api._completed_fact(row['archive'])
        report = api.document(api._completed_fact(row['report']))
        api.fields(report, ('name', 'members', 'sha256'), 'successful donor archive report')
        expected = []
        for ordinal, member in enumerate(archive['members']):
            _require(member['ordinal'] == ordinal, 'archive member ordinal differs')
            owner = replacements.get((name, ordinal))
            if owner is None:
                expected.append({'name': Path(member['input']['path']).name,
                    'sha256': member['input']['sha256'], 'bytes': member['bytes']})
            else:
                _require(owner in objects and owner not in compiled,
                         'archive contains a changed direct object')
                product = objects[owner]
                expected.append({'name': owner + '.o', 'sha256': product['sha256'], 'bytes': product['bytes']})
        _require(report == prior and report['name'] == name
            and report['sha256'] == fact['sha256'] and report['members'] == expected
            and len({member['name'] for member in expected}) == len(expected),
            'archive full ordered member table/hash differs')
        admitted.append(dict(row))
    return admitted


# A distinct successor of the accepted P5 candidate. Historical J1/composition
# admission above remains byte-for-byte unchanged; P5 is never restamped J1.
NATIVE_CAPABILITY_REPAIR_DONOR_KIND = 'foundation-document-v2-successful-donor-native-capability-repair-v1'
NATIVE_CAPABILITY_REPAIR_PLAN_KIND = 'foundation-document-v2-maintenance-successful-donor-native-capability-repair-plan-v1'
NATIVE_CAPABILITY_REPAIR_BUILD_KIND = 'foundation-document-v2-maintenance-successful-donor-native-capability-repair-build-v1'
NATIVE_CONTROL_KEYPRESS_REPAIR_DONOR_KIND = 'foundation-document-v2-successful-donor-native-control-keypress-repair-v1'
NATIVE_CONTROL_KEYPRESS_REPAIR_PLAN_KIND = 'foundation-document-v2-maintenance-successful-donor-native-control-keypress-repair-plan-v1'
NATIVE_CONTROL_KEYPRESS_REPAIR_BUILD_KIND = 'foundation-document-v2-maintenance-successful-donor-native-control-keypress-repair-build-v1'
NATIVE_CAPABILITY_REPAIR_COMPILED_IDS = (
    'NativeDocumentV2Publisher.cpp', 'NativeFormsV2Combined.cpp',
    'NativeDocumentV2Types.cpp', 'BibEngineDocumentWasmShim.cpp', 'BibNativePopupOwner.cpp')
P5_IMPORTED_COMPILED_IDS = ('ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp')
NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS = NATIVE_CAPABILITY_REPAIR_COMPILED_IDS + ('BibDocumentPhysicalProvider.cpp',)
P5_PINS = {
    'p5_root_acceptance': 'b045468573caca84a9d4430d4acf284ca54f6bf015ea5be51a736f374364cc3a',
    'p5_closed_result': 'f210dc0bc9ea624c5bf0c5c3bf467b0d1d4551472f0d601fd1c4117013227c89',
    'p5_plan': '40af90e69176f4a65003e820439d82cf8f4b9eaafb45bd7b1b30ac699679ddfd',
    'p5_maintenance_build': '791e9d67bbb0200697ec6d099476008acef03a9a2c97b5e6018b7970e6bebfb6',
    'p5_commands': '5c3da886070ddf7d1eca9c6243ffd99b15a9b61a4314bb643fc1cbc9198bf42c',
    'p5_build_packet': '569d9eff7744e3dc4b96944d39f14c2d39d7dfbbb18b1063cff05744fe124338',
    'p5_input_freeze': 'bb6da97b0df63ee26297cc903412e5e5b1308ac45c0ffa82839958835436eebd',
    'p5_preparation_acceptance': 'c7ca799818bafca63b33aa21b4a77aa7070f03819ebd7c1a336f37edcc990e13',
    'p5_vfs_dependency_gate': 'f0e4344c2a17972c365209f1fdc59ac3d8363235ee8bf027acd8a9ca96f10471',
}
NATIVE_CAPABILITY_DESCRIPTOR_FIELDS = (
    'schema_version', 'kind', 'document_profile', 'p5_bindings',
    *P5_PINS, 'p5_private', 'p5_ninja_log', 'p5_compiled',
    'legacy_donor', 'objects', 'archives')


def native_capability_shape(inspection, old, rows, api):
    """Pure exact5/46 native partition; the historical shape gates are not broadened."""
    proof, config = inspection.proof, inspection.profile
    selected = config['direct_objects'] + config['engine_objects']
    compiled = set(NATIVE_CAPABILITY_REPAIR_COMPILED_IDS)
    _require(len(selected) == 51 and len(set(selected)) == 51
        and len(config['direct_objects']) == 35 and len(config['engine_objects']) == 16
        and compiled <= set(config['direct_objects'])
        and [row['id'] for row in proof['objects']] == selected
        and [row['id'] for row in old['reuse']['objects']] == selected
        and proof['archives'] == old['reuse']['archives']
        and proof['replacements'] == old['reuse']['replacements']
        and {row['name']: len(row['members']) for row in proof['archives']} == ARCHIVE_COUNTS
        and len(proof['archives']) == 5 and len(proof['replacements']) == 16
        and len({(row['archive'], row['ordinal']) for row in proof['replacements']}) == 16
        and {row['object_id'] for row in proof['replacements']} == set(config['engine_objects']),
        'native capability selected/archive/replacement boundary differs')
    wanted = [name for name in selected if name not in compiled]
    _require(type(rows) is list and len(rows) == 46
        and all(type(row) is dict for row in rows)
        and [row.get('id') for row in rows] == wanted,
        'native capability requires exact ordered46 imports and five fresh units')
    for row in rows:
        api.fields(row, ('id', 'origin'), 'native capability object declaration')
        expected = 'p5-compiled' if row['id'] in P5_IMPORTED_COMPILED_IDS else 'legacy-imported'
        _require(row['origin'] == expected, 'native capability object compilation origin differs')
    _require(sum(row['origin'] == 'p5-compiled' for row in rows) == 3,
             'native capability requires exactly43 legacy plus three P5 imports')
    return selected


def native_control_keypress_shape(inspection, old, rows, api):
    """F6's exact six-fresh/45-import partition; native-five stays a separate lane."""
    proof, config = inspection.proof, inspection.profile
    selected = config['direct_objects'] + config['engine_objects']
    compiled = set(NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS)
    _require(len(selected) == 51 and len(set(selected)) == 51
        and len(config['direct_objects']) == 35 and len(config['engine_objects']) == 16
        and compiled <= set(config['direct_objects'])
        and [row['id'] for row in proof['objects']] == selected
        and [row['id'] for row in old['reuse']['objects']] == selected
        and proof['archives'] == old['reuse']['archives']
        and proof['replacements'] == old['reuse']['replacements']
        and {row['name']: len(row['members']) for row in proof['archives']} == ARCHIVE_COUNTS
        and len(proof['archives']) == 5 and len(proof['replacements']) == 16
        and len({(row['archive'], row['ordinal']) for row in proof['replacements']}) == 16
        and {row['object_id'] for row in proof['replacements']} == set(config['engine_objects']),
        'native control keypress selected/archive/replacement boundary differs')
    wanted = [name for name in selected if name not in compiled]
    _require(type(rows) is list and len(rows) == 45
        and all(type(row) is dict for row in rows)
        and [row.get('id') for row in rows] == wanted,
        'native control keypress requires exact ordered45 imports and six fresh units')
    for row in rows:
        api.fields(row, ('id', 'origin'), 'native control keypress object declaration')
        expected = 'p5-compiled' if row['id'] in P5_IMPORTED_COMPILED_IDS else 'legacy-imported'
        _require(row['origin'] == expected, 'native control keypress object compilation origin differs')
    _require(sum(row['origin'] == 'p5-compiled' for row in rows) == 3,
             'native control keypress requires exactly42 legacy plus three P5 imports')
    return selected


def native_capability_artifact_names(selected, archives):
    """The complete candidate namespace, shared with independent outer readback."""
    _require(len(selected) == 51 and len(set(selected)) == 51
        and set(NATIVE_CAPABILITY_REPAIR_COMPILED_IDS) <= set(selected)
        and len(archives) == 5 and set(archives) == set(ARCHIVE_COUNTS),
        'native capability artifact input namespace differs')
    names = {'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h',
        'document-generated/provider-build.json', 'evidence/engine-link.map'}
    for name in selected:
        names.add('objects/' + name + '.o')
        if name in NATIVE_CAPABILITY_REPAIR_COMPILED_IDS:
            names.add('objects/' + name + '.o.d')
        else:
            names.update(('evidence/import-' + name + '.json', 'evidence/import-' + name + '.original.d'))
    for name in archives:
        names.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json',
                      'evidence/import-archive-' + name + '.json'))
    _require(len(names) == 168, 'native capability artifact namespace is not exact168')
    return names


def native_control_keypress_artifact_names(selected, archives):
    """Exact F6 artifact namespace (167 records); no optional artifact expansion."""
    fresh = set(NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS)
    _require(len(selected) == 51 and len(set(selected)) == 51 and fresh <= set(selected)
        and len(archives) == 5 and set(archives) == set(ARCHIVE_COUNTS),
        'native control keypress artifact input namespace differs')
    names = {'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h',
        'document-generated/provider-build.json', 'evidence/engine-link.map'}
    for name in selected:
        names.add('objects/' + name + '.o')
        if name in fresh:
            names.add('objects/' + name + '.o.d')
        else:
            names.update(('evidence/import-' + name + '.json', 'evidence/import-' + name + '.original.d'))
    for name in archives:
        names.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json',
                      'evidence/import-archive-' + name + '.json'))
    _require(len(names) == 167, 'native control keypress artifact namespace is not exact167')
    return names


def _p5_flat_fact(value, api):
    api.fields(value, ('path', 'sha256', 'bytes', 'dev', 'ino', 'mode', 'nlink',
                       'mtime_ns', 'ctime_ns'), 'P5 Root metadata fact')
    for key in ('bytes', 'dev', 'ino', 'mode', 'nlink', 'mtime_ns', 'ctime_ns'):
        _require(type(value[key]) is int and value[key] >= 0, 'P5 flat physical integer differs')
    fact = {key: value[key] for key in ('path', 'sha256', 'bytes', 'mode')}
    fact['identity'] = [value['dev'], value['ino'], 0o100000 | value['mode'],
                        value['nlink'], value['bytes'], value['mtime_ns'], value['ctime_ns']]
    _fact_shape(fact, Path(value['path']), api)
    api._completed_fact(fact)
    return fact


def _p5_metadata(value, inspection, api, *, control_keypress=False):
    api.fields(value, NATIVE_CAPABILITY_DESCRIPTOR_FIELDS, 'native repair donor')
    _require(_integer(value['schema_version'], 1)
        and value['kind'] == (NATIVE_CONTROL_KEYPRESS_REPAIR_DONOR_KIND if control_keypress
                              else NATIVE_CAPABILITY_REPAIR_DONOR_KIND)
        and value['document_profile'] == 'editor'
        and inspection.selection['document_profile'] == 'editor',
        'native capability descriptor identity/profile differs')
    _reference(value['legacy_donor'], api, '747858f13c1878d7829aab79f933e75100f706a76b5f69f4eb0d2a670510b54e')
    docs = {name: _reference(value[name], api, pin) for name, pin in P5_PINS.items()}
    bindings = api._completed_binding(value['p5_bindings'])
    root, result, old, build, commands, packet, freeze, preparation, gate = (
        docs[name] for name in P5_PINS)
    _require(root.get('kind') == 'root-closed-successful-donor-composition-repair-candidate-accepted-v1'
        and root.get('status') == 'passed' and _integer(root.get('schema_version'), 1)
        and _integer(root.get('actual_session'), 4865) and _integer(root.get('caller_observed_exit'), 0)
        and root.get('closed') is True and root.get('writers_joined') is True
        and root.get('inputs_unchanged') is True and root.get('runtime_not_run') is True
        and root.get('production_eligible') is False
        and root.get('input_identity_namespace_postflight') == 'passed'
        and root.get('all_artifact_physical_identities_root_rechecked') is True
        and _integer(root.get('verified_artifact_records'), 168), 'P5 accepted Root identity differs')
    _natural(root.get('qualified_report'), api)
    for field in ('closed', 'verified', 'writers_joined', 'runtime_not_run'):
        _require(result.get(field) is True, 'P5 caller is not closed/verified')
    _require(result.get('status') == 'passed' and _integer(result.get('returncode'), 0)
        and result.get('production_eligible') is False
        and result.get('static_byte_readback') == 'passed'
        and result.get('input_identity_namespace_postflight') == 'passed'
        and result.get('supervisor_report') == root['qualified_report']
        and _integer(result.get('actual_objects'), 51)
        and _integer(result.get('actual_archive_reports'), 5)
        and _integer(result.get('opaque_unchanged_members'), 2060), 'P5 caller acceptance differs')
    fields = {'closed': 'p5_closed_result', 'commands': 'p5_commands',
              'maintenance_build': 'p5_maintenance_build', 'plan': 'p5_plan'}
    api.fields(root['records'], (*fields, 'donor_descriptor', 'inspection'), 'P5 Root references')
    for name, key in fields.items():
        fact = _p5_flat_fact(root['records'][name], api)
        _require({k: fact[k] for k in ('path', 'sha256')} == value[key], 'P5 Root metadata join differs')
    _require(root['records']['donor_descriptor']['sha256'] == value['legacy_donor']['sha256']
        and root['records']['donor_descriptor']['path'] == value['legacy_donor']['path']
        and old.get('kind') == COMPOSITION_REPAIR_PLAN_KIND and old.get('production_eligible') is False
        and _integer(old.get('schema_version'), 1)
        and old.get('scope') == api.SCOPE
        and old['successful_donor']['reference'] == value['legacy_donor']
        and old['selection']['document_profile'] == 'editor'
        and old['selection']['sdk_manifest_sha256'] == inspection.selection['sdk_manifest_sha256']
        and old['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor')),
        'P5 plan/legacy/profile/SDK authority differs')
    for key, selection_key in (('sources', 'sources'), ('sdk', 'sdk'), ('reuse', 'reuse_root')):
        _require(str(bindings[key]) == old['selection'][selection_key], 'P5 selected root differs')
    _require(bindings['sdk'] == inspection.roots['sdk'], 'P5 paired SDK root differs')
    build_root = bindings['build']
    expected_paths = {'p5_maintenance_build': build_root / 'maintenance-build.json',
        'p5_commands': build_root / 'evidence/commands.json'}
    _require(all(value[key]['path'] == str(path) for key, path in expected_paths.items()),
             'P5 product authority path differs')
    _require(packet.get('kind') == 'editor-rich-ui-successful-donor-composition-repair-build-launch-v1'
        and packet.get('selection') == old['selection']
        and packet.get('producer_inputs') == old['producer_inputs']
        and packet.get('plan') == value['p5_plan']['path']
        and packet.get('plan_sha256') == value['p5_plan']['sha256']
        and packet.get('freeze') == value['p5_input_freeze']['path']
        and packet.get('freeze_sha256') == value['p5_input_freeze']['sha256']
        and packet.get('preparation_acceptance') == value['p5_preparation_acceptance']
        and packet.get('output') == str(build_root)
        and packet.get('policy') == {'cold_fallback': False, 'header_odr_waiver': False,
            'production_eligible': False, 'runtime': False, 'timestamp_seeding': False}
        and packet.get('argv') == ['./build.sh', 'engine-maintenance', 'document-build',
            '--plan', value['p5_plan']['path'], '--plan-sha256', value['p5_plan']['sha256'],
            '--output', str(build_root), '--jobs', '1', '--timeout-seconds', '2700'],
        'P5 concrete launch packet differs')
    _require(preparation.get('status') == 'passed' and preparation.get('closed') is True
        and preparation.get('writers_joined') is True and _integer(preparation.get('caller_observed_exit'), 0)
        and preparation.get('input_identity_namespace_postflight') == 'passed'
        and preparation.get('production_eligible') is False
        and freeze.get('kind') == 'editor-rich-ui-input-freeze-v1'
        and _integer(freeze.get('schema_version'), 1) and freeze.get('actual_plan_or_build') is False
        and freeze.get('roots') == {k: str(v) for k, v in bindings.items() if k != 'build'}
        and type(freeze.get('files')) is dict and type(freeze.get('directories')) is dict,
        'P5 prepared/frozen source authority differs')
    for key, path in (('recipe_sha256', 'recipe.json'), ('sources_sha256', 'sources.json')):
        _require(freeze['files'].get(str(bindings['sources'] / path), {}).get('sha256') == old['selection'][key],
                 'P5 source manifest lacks frozen authority')
    for name, pin in old['producer_inputs'].items():
        _require(freeze['files'].get(str(bindings['sources'] / name), {}).get('sha256') == pin,
                 'P5 producer lacks frozen authority')
    _require(freeze['files'].get(str(bindings['sdk'] / 'sdk.json'), {}).get('sha256')
        == inspection.selection['sdk_manifest_sha256'], 'P5 SDK lacks frozen authority')
    selected = [row['id'] for row in old['reuse']['objects']]
    fresh = set(COMPOSITION_REPAIR_COMPILED_IDS)
    names = [row['name'] for row in old['reuse']['archives']]
    accounting = dict(selected=51, compiled=5, imported=46, archive_imported=5, archive_repacked=0,
        compiled_ids=[n for n in selected if n in fresh], imported_ids=[n for n in selected if n not in fresh],
        imported_archive_names=names)
    for counts in (build.get('accounting', {}), result.get('successful_donor', {}).get('accounting', {})):
        _require(all(_integer(counts.get(key), count) for key, count in
            (('selected', 51), ('compiled', 5), ('imported', 46), ('archive_imported', 5), ('archive_repacked', 0))),
            'P5 accounting requires exact plain integers')
    _require(build.get('kind') == COMPOSITION_REPAIR_BUILD_KIND and build.get('status') == 'passed'
        and _integer(build.get('schema_version'), 1) and build.get('production_eligible') is False
        and build.get('accounting') == accounting and result['successful_donor']['accounting'] == accounting
        and build.get('plan_sha256') == value['p5_plan']['sha256']
        and build.get('source_recipe_sha256') == old['selection']['recipe_sha256']
        and build.get('sources_sha256') == old['selection']['sources_sha256']
        and build.get('paired_sdk_sha256') == inspection.selection['sdk_manifest_sha256']
        and build.get('successful_donor') == value['legacy_donor']
        and result['successful_donor'].get('successful_donor') == value['legacy_donor']
        and result['successful_donor'].get('independent_copies') is True
        and result['successful_donor'].get('original_dependencies_retained') is True
        and build.get('commands') == {'path': 'evidence/commands.json', 'sha256': value['p5_commands']['sha256']}
        and [row['id'] for row in build['objects']] == selected
        and result.get('maintenance_build_sha256') == value['p5_maintenance_build']['sha256']
        and result.get('inspection_sha256') == root['records']['inspection']['sha256']
        and hashlib.sha256(api.encoded(build['inspection'])).hexdigest() == result.get('inspection_sha256'),
        'P5 maintenance source/accounting/command identity differs')
    api.fields(commands, ('objects', 'imports', 'archive_imports', 'metadata', 'link'), 'P5 command ledger')
    _require(set(commands['objects']) == fresh and set(commands['imports']) == set(selected) - fresh
        and set(commands['archive_imports']) == set(names), 'P5 compiler/import command partition differs')
    records = result.get('artifact_records')
    expected = {'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h', 'document-generated/provider-build.json',
        'evidence/engine-link.map'}
    for name in selected:
        expected.add('objects/' + name + '.o')
        if name in fresh:
            expected.add('objects/' + name + '.o.d')
        else:
            expected.update(('evidence/import-' + name + '.json', 'evidence/import-' + name + '.original.d'))
    for name in names:
        expected.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json',
                         'evidence/import-archive-' + name + '.json'))
    _require(type(records) is dict and set(records) == expected and len(records) == 168,
             'P5 product namespace is not exact168')
    import json
    # The pinned Root P5 receipt hashes compact ASCII JSON plus one newline.
    compact = (json.dumps(records, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    _require(hashlib.sha256(compact).hexdigest() == root['artifact_records_sha256'], 'P5 product index differs')
    for name, fact in records.items():
        _fact_shape(fact, build_root / name, api)
    for row in build['objects']:
        fact = records['objects/' + row['id'] + '.o']
        _require(row['sha256'] == fact['sha256'] and row['bytes'] == fact['bytes'], 'P5 object product join differs')
    _require(gate.get('kind') == 'root-P5-actual-VFS-five-depfile-gate-v1'
        and gate.get('status') == 'passed' and _integer(gate.get('actual_session'), 4865)
        and gate.get('five_depfile_ownership') == 'passed'
        and gate.get('result_sha256') == value['p5_closed_result']['sha256']
        and gate.get('packet_sha256') == value['p5_build_packet']['sha256']
        and gate.get('production_eligible') is False,
        'P5 VFS/dependency ownership authority differs')
    api.fields(value['p5_private'], ('vfs', 'configuration', 'launcher'), 'P5 private inputs')
    _require(value['p5_private']['vfs'] == gate['actual_VFS'], 'P5 actual VFS fact differs')
    for name in fresh:
        key = 'objects/' + name + '.o.d'
        _require(gate['depfile_records'].get(key) == records[key], 'P5 depfile ownership index differs')
    return docs, bindings, records


def _p5_compiled_rows(value, old_inspection, bindings, freeze, records, commands, api):
    """Read the actual five P5 depfiles; only three become imports."""
    import os
    expected = [row['id'] for row in old_inspection.proof['objects'] if row['id'] in COMPOSITION_REPAIR_COMPILED_IDS]
    rows = value['p5_compiled']
    _require(type(rows) is list and all(type(row) is dict for row in rows)
        and [row.get('id') for row in rows] == expected, 'P5 compiler evidence must preserve exact ordered five')
    fact = value['p5_ninja_log']
    _fact_shape(fact, bindings['build'] / 'cmake/build/.ninja_log', api)
    _require(fact['bytes'] <= 16 * 1024 * 1024, 'P5 Ninja ledger exceeds read bound')
    ninja = api._completed_fact(fact).decode('utf-8')
    _require(ninja.startswith('# ninja log v6\n'), 'P5 Ninja ledger version differs')
    ledger = [line.split('\t') for line in ninja.splitlines()[1:]]
    cwd = str(bindings['build'] / 'cmake/build')
    objects = {row['id']: row for row in old_inspection.proof['objects']}
    all_refs, admitted = [], []
    total = sum(records['objects/' + name + '.o.d']['bytes'] for name in expected)
    _require(total <= 256 * 1024 * 1024, 'P5 dependency evidence exceeds read bound')
    for row in rows:
        api.fields(row, ('id', 'ninja_record', 'ninja_command', 'command_script'), 'P5 compiler evidence')
        _require(row['command_script'] is None or type(row['command_script']) is dict,
                 'P5 command script requires an explicit fact or null')
        name = row['id']; obj = objects[name]; argv = commands['objects'][name]
        _require(api._completed_arguments(argv, cwd, bindings) == obj['arguments'], 'P5 compiler argv differs')
        target = str(bindings['build'] / ('objects/' + name + '.o'))
        product = records['objects/' + name + '.o']; depfile = records['objects/' + name + '.o.d']
        _require(argv[argv.index('-o') + 1] == target and argv[argv.index('-MT') + 1] == target
            and argv[argv.index('-MF') + 1] == target + '.d'
            and argv[argv.index('-c') + 1] == str(bindings['sources'] / obj['source']['path']),
            'P5 compiler source/target coordinates differ')
        matching = [item for item in ledger if len(item) == 5 and item[3] == target]
        recorded = row['ninja_record']
        _require(len(matching) == 1 and recorded == matching[0]
            and all(item.isdecimal() for item in recorded[:3])
            and int(recorded[1]) >= int(recorded[0]) and int(recorded[2]) == product['identity'][5]
            and recorded[4] == api._completed_ninja_command(row, argv, bindings, old_inspection.proof['host_tools']),
            'P5 object lacks exact successful compiler/Ninja authority')
        normalize = lambda p: os.path.normpath(str(Path(p) if Path(p).is_absolute() else Path(cwd) / p))
        keys = sorted({normalize(p) for p in api._depfile_inputs(api._completed_fact(depfile), target=target)})
        _require(str(bindings['sources'] / obj['source']['path']) in keys, 'P5 depfile omits its source')
        refs = []
        for key in keys:
            generated = str(bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h')
            if key == generated:
                _require(name == 'BibEngineDocumentWasmShim.cpp', 'P5 generated dependency has unexpected owner')
                continue  # This source-identity-dependent owner always recompiles.
            path = Path(key)
            private_cache = bindings['build'] / 'private/cache'
            if private_cache in path.parents:
                relative = path.relative_to(private_cache).as_posix()
                seed = old_inspection.proof['private_cache']
                logical = seed['root'] + '/' + relative
                _require(logical in seed['files'], 'P5 cache dependency is not an exact SDK seed')
                original = str(bindings['sdk'] / logical)
                frozen = freeze['files'].get(original)
                _require(type(frozen) is dict, 'P5 cache dependency lacks frozen SDK authority')
                api._completed_fact(frozen, sdk=True)
                api.checked_read(api.ordinary(path), frozen['sha256'])
                reference = dict(root='sdk', path=logical, sha256=frozen['sha256'])
            else:
                roots = [(root, base) for root, base in bindings.items() if root != 'build' and base in path.parents]
                _require(len(roots) == 1, 'P5 dependency is generated or outside retained roots')
                root, base = roots[0]; frozen = freeze['files'].get(key)
                _require(type(frozen) is dict and frozen.get('path') == key, 'P5 dependency lacks frozen input fact')
                api._completed_fact(frozen, sdk=root == 'sdk')
                reference = dict(root=root, path=path.relative_to(base).as_posix(), sha256=frozen['sha256'])
            api.ref_path(reference, old_inspection.roots, old_inspection.inventories)
            refs.append(reference)
        all_refs.extend(refs)
        _require((generated in keys) == (name == 'BibEngineDocumentWasmShim.cpp'),
                 'P5 generated metadata requires its exact fresh Shim owner')
        if name in P5_IMPORTED_COMPILED_IDS:
            _require(generated not in keys, 'Generated-dependent P5 object cannot be imported')
            api._completed_fact(product)
            admitted.append(dict(row, object=product, depfile=depfile, dependency_keys=keys,
                command_sha256=hashlib.sha256(api.encoded({'argv': argv, 'cwd': cwd})).hexdigest(),
                original_argv=argv, original_cwd=cwd, dependency_refs=refs))
    return admitted, all_refs


def native_capability_context_delta(inspection, old, previous, current, api):
    api._completed_context_matches(previous, current)
    before = {row['id']: row for row in old['reuse']['objects']}
    after = {row['id']: row for row in inspection.proof['objects']}
    changed_ids = set(NATIVE_CAPABILITY_REPAIR_COMPILED_IDS) - {'BibEngineDocumentWasmShim.cpp'}
    allowed = set()
    for name in before:
        prior, successor = before[name], after[name]
        for key in ('arguments', 'unified_members', 'exceptions'):
            _require(prior[key] == successor[key], 'native capability compiler/unified policy differs: ' + name)
        source, replacement = prior['source'], successor['source']
        if name in changed_ids:
            api.fields(source, api.REFERENCE_FIELDS, 'P5 direct source')
            api.fields(replacement, api.REFERENCE_FIELDS, 'native capability direct source')
            _require(source['root'] == replacement['root'] == 'sources'
                and source['path'] == replacement['path'] and source['sha256'] != replacement['sha256'],
                'native capability requires exact changed source coordinates/hash: ' + name)
            allowed.add('{sources}/' + source['path'])
        else:
            _require(source == replacement, 'native capability changed an undeclared source: ' + name)
        expected = [replacement if ref == source else ref for ref in prior['dependencies']]
        _require(successor['dependencies'] == expected, 'native capability changed undeclared explicit dependency: ' + name)
    changed = {name for name, pin in previous['namespace'].items() if current['namespace'].get(name) != pin}
    _require(changed == allowed, 'native capability source namespace delta differs')
    for key in ('host_tools', 'sdk_tools', 'python_launch', 'emscripten_config', 'private_cache', 'metadata', 'link'):
        _require(old['reuse'][key] == inspection.proof[key], 'native capability tool/metadata/link context differs: ' + key)


def native_control_keypress_context_delta(inspection, old, previous, current, api):
    api._completed_context_matches(previous, current)
    before = {row['id']: row for row in old['reuse']['objects']}
    after = {row['id']: row for row in inspection.proof['objects']}
    changed_ids = set(NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS) - {'BibEngineDocumentWasmShim.cpp'}
    allowed = set()
    for name in before:
        prior, successor = before[name], after[name]
        for key in ('arguments', 'unified_members', 'exceptions'):
            _require(prior[key] == successor[key], 'native control keypress compiler/unified policy differs: ' + name)
        source, replacement = prior['source'], successor['source']
        if name in changed_ids:
            api.fields(source, api.REFERENCE_FIELDS, 'P5 direct source')
            api.fields(replacement, api.REFERENCE_FIELDS, 'native control keypress direct source')
            _require(source['root'] == replacement['root'] == 'sources'
                and source['path'] == replacement['path'] and source['sha256'] != replacement['sha256'],
                'native control keypress requires exact changed source coordinates/hash: ' + name)
            allowed.add('{sources}/' + source['path'])
        else:
            _require(source == replacement, 'native control keypress changed an undeclared source: ' + name)
        expected = [replacement if ref == source else ref for ref in prior['dependencies']]
        _require(successor['dependencies'] == expected, 'native control keypress changed undeclared explicit dependency: ' + name)
    changed = {name for name, pin in previous['namespace'].items() if current['namespace'].get(name) != pin}
    _require(changed == allowed, 'native control keypress source namespace delta differs')
    for key in ('host_tools', 'sdk_tools', 'python_launch', 'emscripten_config', 'private_cache', 'metadata', 'link'):
        _require(old['reuse'][key] == inspection.proof[key], 'native control keypress tool/metadata/link context differs: ' + key)


def _native_repair_admission(reference, inspection, api, *, control_keypress):
    """Authenticate P5, preserve original compilation histories, then compare inputs.

    No discovery or program execution occurs. The historical composition reader
    receives an authenticated frozen P5 view, never the moving successor view.
    """
    value = _reference(reference, api)
    docs, bindings, records = _p5_metadata(value, inspection, api, control_keypress=control_keypress)
    old, freeze = docs['p5_plan'], docs['p5_input_freeze']
    selected = (native_control_keypress_shape(inspection, old, value['objects'], api) if control_keypress
                else native_capability_shape(inspection, old, value['objects'], api))
    sources = bindings['sources']
    def frozen_document(name):
        fact = freeze['files'].get(str(sources / name))
        _require(type(fact) is dict, 'P5 source metadata lacks its frozen fact')
        return api.document(api._completed_fact(fact))
    source_manifest = frozen_document('sources.json')
    old_inspection = api.Inspection(old['selection'], frozen_document('recipe.json'),
        api._completed_reference({'path': old['selection']['projection'], 'sha256': old['selection']['projection_sha256']}),
        old['reuse'], {key: path for key, path in bindings.items() if key != 'build'},
        {'sources': source_manifest['files'], 'sdk': inspection.inventories['sdk'],
         'reuse': old['reuse']['inventory']['files']}, inspection.profile)
    # Existing old admission rechecks all46 true compiler histories, sidecar,
    # seven fresh-only keys, private inputs, header owners and ordered archives.
    legacy_descriptor = _reference(value['legacy_donor'], api)
    legacy_bytes = sum(row['object']['bytes'] + row['depfile']['bytes']
        + (row['command_script']['bytes'] if row['command_script'] else 0)
        for row in legacy_descriptor['objects'])
    p5_bytes = sum(records['objects/' + name + '.o.d']['bytes']
        for name in COMPOSITION_REPAIR_COMPILED_IDS)
    p5_bytes += sum(records['objects/' + name + '.o']['bytes'] for name in P5_IMPORTED_COMPILED_IDS)
    _require(legacy_bytes + p5_bytes <= 256 * 1024 * 1024,
             'native capability combined compiler evidence exceeds256MiB')
    legacy = api._completed_work(value['legacy_donor'], old_inspection,
        _successful=True, _composition_repair=True)
    private_vfs = api._completed_private_context(value['p5_private'], bindings, old, freeze)
    _require(private_vfs == api._completed_normalize_vfs(api._header_identity(old_inspection)['overlay'], old_inspection.roots),
             'P5 actual private VFS differs from its accepted proof')
    build = docs['p5_maintenance_build']
    _require(value['p5_private']['configuration']['sha256'] == build['private_configuration']['config_sha256']
        and value['p5_private']['launcher']['sha256'] == build['private_configuration']['launcher_sha256'],
        'P5 private configuration/launcher identity differs')
    compiled, refs = _p5_compiled_rows(value, old_inspection, bindings, freeze, records, docs['p5_commands'], api)
    sidecar = api._completed_reference(legacy['dependency_sidecar'])
    legacy_refs = [sidecar['dependencies'][key]['input'] for row in legacy['objects'] for key in row['dependency_keys']]
    previous = api._completed_header_context(old_inspection, refs + legacy_refs, old['reuse']['objects'])
    current = api._completed_header_context(inspection, refs + legacy_refs, inspection.proof['objects'])
    (native_control_keypress_context_delta if control_keypress else native_capability_context_delta)(
        inspection, old, previous, current, api)
    legacy_rows = {row['id']: row for row in legacy['objects']}
    compiled_rows = {row['id']: row for row in compiled}
    admitted = []
    for declaration in value['objects']:
        name = declaration['id']; p5_object = records['objects/' + name + '.o']
        api._completed_fact(p5_object)
        if declaration['origin'] == 'legacy-imported':
            row = dict(legacy_rows[name])
            dependencies = [sidecar['dependencies'][key]['input'] for key in row['dependency_keys']]
            receipt_fact = records['evidence/import-' + name + '.json']
            receipt = api.document(api._completed_fact(receipt_fact))
            provenance = records['evidence/import-' + name + '.original.d']
            _require(receipt.get('kind') == 'foundation-document-v2-object-import-v1'
                and receipt.get('retained_depfile') == provenance['path']
                and receipt.get('depfile_sha256') == row['depfile']['sha256']
                and receipt.get('object') == row['object'] and receipt.get('original_depfile') == row['depfile']
                and receipt.get('original_argv') == row['original_argv'] and receipt.get('original_cwd') == row['original_cwd']
                and receipt.get('original_command_sha256') == row['command_sha256']
                and receipt.get('ninja_record') == row['ninja_record'] and receipt.get('ninja_command') == row['ninja_command']
                and receipt.get('command_script') == row['command_script']
                and receipt.get('compiler_invoked') is False and receipt.get('hardlinked') is False
                and receipt.get('origin') == 'imported' and receipt.get('id') == name
                and receipt.get('production_eligible') is False
                and receipt.get('destination') == p5_object['path']
                and receipt.get('sha256') == p5_object['sha256'] == row['object']['sha256']
                and receipt.get('bytes') == p5_object['bytes'] == row['object']['bytes'],
                'P5 legacy import receipt does not preserve original compilation provenance')
            _require(api._completed_fact(provenance) == api._completed_fact(row['depfile']), 'P5 retained original depfile differs')
            compile_bindings = legacy['original_bindings']
        else:
            row = dict(compiled_rows[name]); dependencies = row.pop('dependency_refs')
            receipt_fact = None; compile_bindings = value['p5_bindings']
        for ref in dependencies:
            api.ref_path(ref, inspection.roots, inspection.inventories)
        row['donor_provenance'] = dict(kind=('foundation-document-v2-native-control-keypress-object-provenance-v1'
            if control_keypress else 'foundation-document-v2-native-capability-object-provenance-v1'),
            p5_root_acceptance=value['p5_root_acceptance'], p5_object=p5_object,
            p5_import_receipt=receipt_fact, compile_bindings=compile_bindings, compile_origin=declaration['origin'])
        admitted.append(row)
    _require(sum(row['object']['bytes'] + row['depfile']['bytes'] +
        (row['command_script']['bytes'] if row['command_script'] else 0) for row in admitted)
        <= 256 * 1024 * 1024, 'native capability import evidence exceeds256MiB')
    names = [row['name'] for row in old['reuse']['archives']]
    _require(type(value['archives']) is list and all(type(row) is dict for row in value['archives'])
        and [row.get('name') for row in value['archives']] == names,
             'native capability requires exact ordered five archive rows')
    archives = []
    for row, prior in zip(value['archives'], legacy['archives']):
        api.fields(row, ('name', 'archive', 'report'), 'P5 archive import')
        name = row['name']
        _require(row['archive'] == records['archives/lib' + name + '.a']
            and row['report'] == records['evidence/archive-' + name + '.json']
            and api._completed_fact(row['report']) == api._completed_fact(prior['report'])
            and row['archive']['sha256'] == prior['archive']['sha256']
            and row['archive']['bytes'] == prior['archive']['bytes'], 'P5 archive copy provenance differs')
        api._completed_fact(row['archive'])
        archives.append(dict(row))
    directories = set(legacy['metadata_directories'])
    directories.update(str(Path(value[name]['path']).parent) for name in P5_PINS)
    directories.add(str(Path(reference['path']).parent))
    return dict(reference=dict(reference), objects=admitted, archives=archives,
        original_bindings=legacy['original_bindings'], dependency_sidecar=legacy['dependency_sidecar'],
        additional_input_directories=[str(path) for path in bindings.values()],
        metadata_directories=sorted(directories))


def native_capability_admission(reference, inspection, api):
    return _native_repair_admission(reference, inspection, api, control_keypress=False)


def native_control_keypress_admission(reference, inspection, api):
    return _native_repair_admission(reference, inspection, api, control_keypress=True)
