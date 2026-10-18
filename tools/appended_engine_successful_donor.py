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
