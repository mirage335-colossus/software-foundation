"""Closed accepted SelectEvent52 -> native input-method lifecycle successor.

Only metadata Shim and the sole affected header consumer (main) compile. The
accepted unified select owner remains an imported direct link input. Five
archives copy unchanged; no archive repack, SDK/kernel/full-engine fallback.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

HELPER = 'tools/appended_engine_input_method_successor.py'
PLAN_KIND = 'foundation-document-v2-maintenance-input-method-repair-plan-v1'
BUILD_KIND = 'foundation-document-v2-maintenance-input-method-repair-build-v1'
DONOR_KIND = 'foundation-document-v2-successful-donor-input-method-repair-v1'
PROVENANCE_KIND = 'foundation-document-v2-input-method-object-provenance-v1'
MAIN = 'main.cpp'
SHIM = 'BibEngineDocumentWasmShim.cpp'
THEME = 'RenderThemeEmscripten.cpp'
HEADER_SOURCE = 'source/wrapper/src/embedder/BibPageClients.h'
HEADER_BEFORE_SHA256 = '6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43'
# Root source acceptance 539a2dd0ee5992cfcf260d35f1014f1df749af371cdfead31658867e211fdda9.
HEADER_AFTER_SHA256 = '283876d4a85cd07b800f0c54ee96695ab5345146481f41e1a615a44fc9e5c7aa'
HEADER_AFTER_BYTES = 30339
OWNER = 'UnifiedSource-950a39b6-13.cpp'
FRESH = (SHIM, MAIN)
PROOF_SOURCE = 'provenance/input-method-reuse-proof.json'
HEADER_IDENTITY_SOURCE = 'provenance/input-method-header-identity.json'
PINS = {
    'root_acceptance': 'b54335756ec47ca63432f079775a472635af07492210ba17005e578add234485',
    'closed_result': '92b7bbb0699096ffea1e59370e7af5903a393cca50b99d452e157feb6ba6e966',
    'plan': '2c65205cb0112b94a0e5b5522fed0d08bd52d9e602395bff7d17c25205884029',
    'maintenance_build': '41a217195ab21e41269dbef51c8edc8a68403ca8142a62b08cdf60ade6dbdd3f',
    'commands': '41a598ceb9f092cf2507aacf008a35ab047cbfb93c8dea38bd288a8fabdbc40f',
    'input_freeze': '50b0090724dc5aee39eae418fa33e673974ccf5db8bd8170623e981a7bc0b35b',
    'select_event_donor': '1e57d57b51c59eb013287267251ba0b83bc221e81c24bf2c7b176351ff3f7b35',
}


def require(condition, message):
    if not condition:
        raise ValueError('Input method ' + message)


def reference(value, api, pin=None):
    api.fields(value, ('path', 'sha256'), 'input-method external reference')
    api.sha(value['sha256'], 'input-method external reference')
    require(pin is None or value['sha256'] == pin, 'authority pin differs')
    return api._completed_reference(value)


def freeze_reference(value, api, pin):
    api.fields(value, ('path', 'sha256'), 'input method frozen reference')
    require(value['sha256'] == pin, 'frozen authority pin differs')
    path = api.ordinary(value['path'])
    require(path.stat().st_size <= 192 * 1024 * 1024, 'frozen authority exceeds 192 MiB')
    raw = api.checked_read(path, pin)
    return api.document_contract.strict_json(raw, 'input method complete physical freeze', maximum=192 * 1024 * 1024)


def _bindings(plan, build_reference, api):
    return api._completed_binding(dict(sources=plan['selection']['sources'],
        sdk=plan['selection']['sdk'], reuse=plan['selection']['reuse_root'],
        build=str(Path(build_reference['path']).parent)))


def artifact_names(selected, archives):
    require(len(selected) == len(set(selected)) == 52 and set(FRESH) <= set(selected)
        and THEME in selected and OWNER in selected and len(archives) == len(set(archives)) == 5
        and set(archives) == {'JavaScriptCore', 'PAL', 'Skia', 'WTF', 'WebCore'},
        'requires 52 unique selected objects and five archives')
    result = {'artifacts/foundation-retained-engine.mjs',
        'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h',
        'document-generated/provider-build.json', 'evidence/engine-link.map'}
    for name in selected:
        result.add('objects/' + name + '.o')
        if name in FRESH:
            result.add('objects/' + name + '.o.d')
        else:
            result.update(('evidence/import-' + name + '.json',
                'evidence/import-' + name + '.original.d'))
    for name in archives:
        result.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json',
            'evidence/import-archive-' + name + '.json'))
    require(len(result) == 174, 'artifact namespace differs from 174')
    return result


def _fact_join(fact, ref, api):
    value = api._successful_module()._p5_flat_fact(fact, api)
    require({k: value[k] for k in ('path', 'sha256')} == ref, 'Root reference join differs')
    return value


def accepted_authority(ref, api):
    """Use closed immutable current donor metadata, never replay old live catalogues."""
    value = reference(ref, api)
    api.fields(value, ('schema_version', 'kind', 'document_profile', *PINS,
        'select_event_ninja_log', 'select_event_private', 'owner_compiled'), 'input method donor')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
        and value['kind'] == DONOR_KIND and value['document_profile'] == 'editor',
        'descriptor kind/profile differs')
    # The accepted complete physical freeze includes all eight historical roots and
    # exceeds the generic 64 MiB document limit. Only this pinned role gets a
    # separate bounded parser; all other lane documents retain their old limits.
    docs = {key: (freeze_reference(value[key], api, pin) if key == 'input_freeze'
        else reference(value[key], api, pin)) for key, pin in PINS.items()}
    root, closed, old, build, commands, freeze, predecessor = (docs[k] for k in PINS)
    picker = api._select_event_module()
    require(root.get('kind') == 'root-closed-successful-donor-select-event-repair-candidate-accepted-v1'
        and type(root.get('actual_session')) is int and root['actual_session'] == 66597
        and type(root.get('caller_observed_exit')) is int and root['caller_observed_exit'] == 0
        and root.get('status') == 'passed' and root.get('production_eligible') is False
        and type(root.get('verified_artifact_records')) is int and root['verified_artifact_records'] == 174
        and all(root.get(k) is True for k in ('closed', 'writers_joined', 'inputs_unchanged',
            'all_artifact_physical_identities_root_rechecked'))
        and api._supervision_report(root.get('qualified_report'), 0),
        'requires actual 66597 accepted natural Root closure')
    for key, name in (('closed', 'closed_result'), ('plan', 'plan'), ('commands', 'commands'),
                      ('maintenance_build', 'maintenance_build'), ('donor_descriptor', 'select_event_donor')):
        _fact_join(root['records'][key], value[name], api)
    require(old.get('kind') == picker.PLAN_KIND and old.get('production_eligible') is False
        and old['successful_donor']['reference'] == value['select_event_donor']
        and old['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor')),
        'accepted select-event plan/profile join differs')
    selected = [row['id'] for row in old['reuse']['objects']]
    archives = [row['name'] for row in old['reuse']['archives']]
    picker.artifact_names(selected, archives)
    require(selected[35] == THEME and OWNER in selected, 'accepted selected graph differs')
    fresh = [name for name in selected if name in picker.FRESH]
    imported = [name for name in selected if name not in picker.FRESH]
    accounting = dict(selected=52, compiled=2, imported=50, archive_imported=5, archive_repacked=0,
        compiled_ids=fresh, imported_ids=imported, imported_archive_names=archives)
    require(build.get('kind') == picker.BUILD_KIND and build.get('status') == 'passed'
        and build.get('production_eligible') is False and build.get('accounting') == accounting
        and build.get('plan_sha256') == value['plan']['sha256']
        and build.get('successful_donor') == value['select_event_donor']
        and build.get('commands') == dict(path='evidence/commands.json', sha256=value['commands']['sha256'])
        and set(commands['objects']) == set(picker.FRESH)
        and set(commands['imports']) == set(imported) and set(commands['archive_imports']) == set(archives),
        'accepted select-event compiler/import accounting differs')
    require(all(closed.get(k) is True for k in ('closed', 'verified', 'writers_joined', 'runtime_not_run'))
        and closed.get('status') == 'passed' and type(closed.get('returncode')) is int and closed['returncode'] == 0
        and closed.get('production_eligible') is False and closed.get('supervisor_report') == root['qualified_report']
        and closed.get('maintenance_build_sha256') == value['maintenance_build']['sha256']
        and closed.get('successful_donor', {}).get('accounting') == accounting
        and closed.get('static_byte_readback') == 'passed'
        and closed.get('input_identity_namespace_postflight') == 'passed'
        and closed.get('actual_objects') == 52 and closed.get('actual_archive_reports') == 5
        and closed.get('opaque_unchanged_members') == 2060, 'accepted select-event result differs')
    records = closed['artifact_records']
    require(set(records) == picker.artifact_names(selected, archives)
        and hashlib.sha256((json.dumps(records, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()
            == root['artifact_records_sha256'], 'accepted complete 174 artifact authority differs')
    bindings = _bindings(old, value['maintenance_build'], api)
    require(value['commands']['path'] == str(bindings['build'] / 'evidence/commands.json')
        and type(freeze.get('files')) is dict
        and all(str(base) in freeze['roots'].values() for key, base in bindings.items() if key != 'build'),
        'accepted coordinates/frozen roots differ')
    actual = api._completed_private_context(value['select_event_private'], bindings, old, freeze)
    require(value['select_event_private']['configuration']['sha256'] == build['private_configuration']['config_sha256']
        and value['select_event_private']['launcher']['sha256'] == build['private_configuration']['launcher_sha256'],
        'accepted private compiler environment differs')
    return dict(reference=dict(ref), descriptor=value, plan=old, build=build, commands=commands,
        closed=closed, root=root, freeze=freeze, bindings=bindings, records=records,
        predecessor=predecessor, actual_vfs=actual)


def compiler_bindings(row, authority, api):
    provenance = row['donor_provenance']
    require(provenance['kind'] == api._select_event_module().PROVENANCE_KIND
        and provenance['compile_origin'] in ('showpicker-compiled', 'showpicker-imported'),
        'inherited object lost accepted SelectEvent compiler provenance')
    return api._completed_binding(provenance['compile_bindings'])


def dependency_refs(raw, row, bindings, frozen, inspection, api, *, generated=False):
    return api._select_event_module().dependency_refs(raw, row, bindings, frozen,
        inspection, api, generated=generated)


def _old_inspection(authority, current, api):
    old, frozen, bindings = authority['plan'], authority['freeze'], authority['bindings']
    def frozen_json(name):
        fact = frozen['files'].get(str(bindings['sources'] / name))
        require(type(fact) is dict, 'old source metadata lacks frozen authority')
        return api.document(api._completed_fact(fact))
    sources = frozen_json('sources.json')
    require(frozen['files'][str(bindings['sources'] / 'sources.json')]['sha256'] == old['selection']['sources_sha256']
        and frozen['files'][str(bindings['sources'] / 'recipe.json')]['sha256'] == old['selection']['recipe_sha256'],
        'old source metadata pins differ')
    config = deepcopy(current.profile)
    config['direct_objects'].append(THEME)
    config['source_bindings'][THEME] = api._theme_module().SOURCE
    config['derived_commands'][THEME] = dict(donor_source=THEME, remove=[], append=[])
    return api.Inspection(old['selection'], frozen_json('recipe.json'), old['projection'], old['reuse'],
        {k: v for k, v in bindings.items() if k != 'build'},
        dict(sources=sources['files'], sdk=current.inventories['sdk'],
            reuse=old['reuse']['inventory']['files']), config)


def _header_pin(api):
    api.sha(HEADER_AFTER_SHA256, 'accepted input-method header postimage')
    require(type(HEADER_AFTER_BYTES) is int and HEADER_AFTER_BYTES > 0,
        'accepted header postimage is not armed')
    return HEADER_AFTER_SHA256


def context_transition(previous, current, api):
    """One reviewed header delta; preserve every other include/SDK/VFS byte."""
    key = '{sources}/' + HEADER_SOURCE
    require(previous['namespace'].get(key) == HEADER_BEFORE_SHA256
        and current['namespace'].get(key) == _header_pin(api), 'header namespace pre/postimage differs')
    narrowed = deepcopy(current)
    narrowed['namespace'][key] = HEADER_BEFORE_SHA256
    api._completed_context_matches(previous, narrowed)
    require(narrowed == previous, 'include namespace changes beyond reviewed input-method header')


def effective_inspection(base, authority, api):
    """Raw51 plus unchanged Theme; no object/source/compiler graph delta."""
    old = authority['plan']['reuse']
    proof, config = deepcopy(base.proof), deepcopy(base.profile)
    require(base.selection['document_profile'] == 'editor'
        and base.selection['sdk_manifest_sha256'] == authority['plan']['selection']['sdk_manifest_sha256']
        and base.roots['sdk'] == authority['bindings']['sdk'], 'paired editor SDK differs')
    theme = deepcopy(next(o for o in old['objects'] if o['id'] == THEME))
    theme['compile_context']['generated_metadata'] = [proof['metadata'][k] for k in sorted(proof['metadata'])]
    proof['objects'].insert(35, theme)
    config['direct_objects'].append(THEME)
    config['source_bindings'][THEME] = api._theme_module().SOURCE
    config['derived_commands'][THEME] = dict(donor_source=THEME, remove=[], append=[])
    require([o['id'] for o in proof['objects']] == [o['id'] for o in old['objects']]
        == config['direct_objects'] + config['engine_objects'], 'ordered52 graph differs')
    changed = deepcopy(proof)
    for obj, before in zip(changed['objects'], old['objects']):
        obj['compile_context']['generated_metadata'] = deepcopy(before['compile_context']['generated_metadata'])
    require(proof['header_identity']['root'] == 'sources'
        and proof['header_identity']['path'] == HEADER_IDENTITY_SOURCE
        and base.inventories['sources'].get(HEADER_IDENTITY_SOURCE) == proof['header_identity']['sha256'],
        'header identity lacks exact inventoried metadata relocation')
    changed['header_identity'] = deepcopy(old['header_identity'])
    require(set(proof['metadata']) == set(old['metadata']), 'metadata role set differs')
    for name in proof['metadata']:
        if name == 'prelink_plan':
            require({k: proof['metadata'][name][k] for k in ('root', 'path')} ==
                {k: old['metadata'][name][k] for k in ('root', 'path')}, 'prelink coordinate differs')
            changed['metadata'][name] = deepcopy(old['metadata'][name])
    require(changed == old, 'proof changes beyond identity-derived metadata')
    result = api.Inspection(base.selection, base.recipe, base.projection, proof, base.roots, base.inventories, config)
    for name in (MAIN, OWNER, THEME):
        api._current_context(next(o for o in proof['objects'] if o['id'] == name), result)
    api.ref_path(theme['source'], result.roots, result.inventories)
    require(base.inventories['sources'].get(HEADER_SOURCE) == _header_pin(api)
        and len(api.checked_read(result.roots['sources'] / HEADER_SOURCE, HEADER_AFTER_SHA256)) == HEADER_AFTER_BYTES,
        'accepted header source identity/byte count differs')
    return result


def validate_dependency_owners(closures):
    require(len(closures) == 52 and set(FRESH) <= set(closures) and OWNER in closures,
        'dependency census requires all52 selected objects')
    consumers = {name for name, refs in closures.items()
        if any(ref.get('root') == 'sources' and ref.get('path') == HEADER_SOURCE for ref in refs)}
    require(consumers == {MAIN}, 'reviewed header must have main as its sole actual compiler owner')


def admit_donor(ref, base, api):
    authority = accepted_authority(ref, api)
    effective = effective_inspection(base, authority, api)
    old_inspection = _old_inspection(authority, base, api)
    require(authority['actual_vfs'] ==
        api._completed_normalize_vfs(api._header_identity(old_inspection)['overlay'], old_inspection.roots),
        'actual select-event compiler VFS differs from accepted header authority')
    old, records, commands, bindings = (authority[k] for k in ('plan', 'records', 'commands', 'bindings'))
    # Exact actual select-event compiler closure; generated-dependent old Shim is never imported.
    row = deepcopy(authority['descriptor']['owner_compiled'])
    api.fields(row, ('id', 'ninja_record', 'ninja_command', 'command_script'), 'select-event compiler declaration')
    require(row['id'] == OWNER, 'fresh select-event compiler declaration differs')
    argv, cwd = commands['objects'][OWNER], str(bindings['build'] / 'cmake/build')
    product, depfile = records['objects/' + OWNER + '.o'], records['objects/' + OWNER + '.o.d']
    row.update(object=product, depfile=depfile, original_argv=argv, original_cwd=cwd,
        command_sha256=hashlib.sha256(api.encoded(dict(argv=argv, cwd=cwd))).hexdigest())
    fact = authority['descriptor']['select_event_ninja_log']
    api._successful_module()._fact_shape(fact, bindings['build'] / 'cmake/build/.ninja_log', api)
    require(fact['bytes'] <= 16 * 1024 * 1024, 'Ninja evidence exceeds bound')
    ninja = api._completed_fact(fact).decode('utf-8')
    require(ninja.startswith('# ninja log v6\n'), 'Ninja ledger version differs')
    target = str(bindings['build'] / ('objects/' + OWNER + '.o'))
    matching = [line.split('\t') for line in ninja.splitlines()[1:]
        if len(line.split('\t')) == 5 and line.split('\t')[3] == target]
    require(len(matching) == 1 and row['ninja_record'] == matching[0]
        and all(v.isdecimal() for v in row['ninja_record'][:3])
        and int(row['ninja_record'][1]) >= int(row['ninja_record'][0])
        and int(row['ninja_record'][2]) == product['identity'][5]
        and row['ninja_record'][4] == api._completed_ninja_command(row, argv, bindings, old_inspection.proof['host_tools']),
        'select-event lacks exact successful compiler/Ninja authority')
    refs = dependency_refs(api._completed_fact(depfile), row, bindings,
        authority['freeze'], old_inspection, api)
    row['dependency_keys'] = sorted({os.path.normpath(str(Path(p) if Path(p).is_absolute()
        else Path(cwd) / p)) for p in api._depfile_inputs(api._completed_fact(depfile), target=target)})
    rows, closures = {OWNER: row}, {OWNER: refs}
    all_refs = list(refs)
    for inherited in old['successful_donor']['objects']:
        name = inherited['id']
        receipt = api.document(api._completed_fact(records['evidence/import-' + name + '.json']))
        require(receipt.get('object') == inherited['object']
            and receipt.get('original_depfile') == inherited['depfile']
            and receipt.get('donor_provenance') == inherited['donor_provenance']
            and receipt.get('compiler_invoked') is False and receipt.get('hardlinked') is False
            and receipt.get('destination') == records['objects/' + name + '.o']['path']
            and receipt.get('sha256') == records['objects/' + name + '.o']['sha256'] == inherited['object']['sha256']
            and receipt.get('bytes') == records['objects/' + name + '.o']['bytes'] == inherited['object']['bytes'],
            'inherited select-event copy receipt differs')
        raw = api._completed_fact(records['evidence/import-' + name + '.original.d'])
        require(raw == api._completed_fact(inherited['depfile']), 'inherited compiler depfile bytes differ')
        origin = compiler_bindings(inherited, authority, api)
        deps = dependency_refs(raw, inherited, origin, authority['freeze'], old_inspection, api)
        all_refs.extend(deps)
        rows[name], closures[name] = deepcopy(inherited), deps
        rows[name]['object'] = records['objects/' + name + '.o']
    # Preserve the old Shim-only search coordinates in the full include context.
    shim_argv = commands['objects'][SHIM]
    shim = dict(id=SHIM, original_argv=shim_argv, original_cwd=cwd)
    closures[SHIM] = dependency_refs(api._completed_fact(records['objects/' + SHIM + '.o.d']),
        shim, bindings, authority['freeze'], old_inspection, api, generated=True)
    all_refs.extend(closures[SHIM])
    validate_dependency_owners(closures)
    previous = api._completed_header_context(old_inspection, all_refs, old_inspection.proof['objects'])
    current = api._completed_header_context(effective, all_refs, effective.proof['objects'])
    context_transition(previous, current, api)
    imported = []
    for obj in effective.proof['objects']:
        name = obj['id']
        if name in FRESH:
            continue
        row = rows[name]
        for dep in closures[name]:
            api.ref_path(dep, effective.roots, effective.inventories)
        api._completed_fact(row['object'])
        row['donor_provenance'] = dict(kind=PROVENANCE_KIND,
            select_event_root_acceptance=authority['descriptor']['root_acceptance'],
            select_event_object=records['objects/' + name + '.o'],
            predecessor=row.get('donor_provenance'),
            compile_bindings={k: str(v) for k, v in
                (bindings if name == OWNER else compiler_bindings(row, authority, api)).items()},
            compile_origin='select-event-compiled' if name == OWNER else 'select-event-imported')
        imported.append(row)
    require(len(imported) == 50 and OWNER in [r['id'] for r in imported] and MAIN not in [r['id'] for r in imported], 'requires50 imports including accepted Unified13 and excluding fresh main')
    archives = []
    for row in old['successful_donor']['archives']:
        name = row['name']
        fact, report = records['archives/lib' + name + '.a'], records['evidence/archive-' + name + '.json']
        require(fact['sha256'] == row['archive']['sha256'] and fact['bytes'] == row['archive']['bytes']
            and api._completed_fact(report) == api._completed_fact(row['report']), 'accepted unchanged archive differs')
        api._completed_fact(fact)
        archives.append(dict(name=name, archive=fact, report=report))
    inherited = old['successful_donor']
    metadata = set(inherited['metadata_directories'])
    metadata.update(str(Path(v['path']).parent) for v in authority['descriptor'].values()
        if type(v) is dict and 'path' in v)
    return dict(reference=dict(ref), objects=imported, archives=archives,
        original_bindings=inherited['original_bindings'], dependency_sidecar=inherited['dependency_sidecar'],
        additional_input_directories=sorted(set(inherited.get('additional_input_directories', []))
            | {str(v) for v in bindings.values()}), metadata_directories=sorted(metadata)), effective


def producer_inputs(api):
    return {name: api.digest(api.ROOT / name) for name in
        (*api.required_helpers('editor'), api.SUCCESSFUL_HELPER, api.THEME_HELPER, api.SHOWPICKER_SUCCESSOR_HELPER, api.SELECT_EVENT_SUCCESSOR_HELPER, HELPER)}


def _helper_admitted(base, api):
    for name, pin in producer_inputs(api).items():
        require(base.inventories['sources'].get(name) == pin, 'retain exact producer helper: ' + name)


def make_plan(selection, output, donor_ref, api):
    base = api.inspect_inputs(selection, _input_method_repair=True)
    _helper_admitted(base, api)
    donor, inspected = admit_donor(donor_ref, base, api)
    destination = api.engine_sdk.new_destination(output,
        (*base.roots.values(), *api._completed_input_directories(donor)))
    plan = dict(schema_version=1, kind=PLAN_KIND, scope=api.SCOPE, selection=inspected.selection,
        profile_sha256=api.digest(api.ROOT / api.profile_path('editor')), producer_inputs=producer_inputs(api),
        reuse=inspected.proof, projection=base.projection, production_eligible=False, successful_donor=donor)
    with api.engine_sdk._OwnedTree(destination.parent, '.engine-input-method-plan-') as staged:
        (staged.path / 'plan.json').write_bytes(api.encoded(plan))
        staged.publish(destination)
    return dict(scope=api.SCOPE, plan=str(destination / 'plan.json'),
        plan_sha256=api.digest(destination / 'plan.json'), production_eligible=False)


def verify_plan(plan, api):
    api.fields(plan, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256', 'producer_inputs',
        'reuse', 'projection', 'production_eligible', 'successful_donor'), 'input-method plan')
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1 and plan['kind'] == PLAN_KIND
        and plan['scope'] == api.SCOPE and plan['production_eligible'] is False
        and plan['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor'))
        and plan['producer_inputs'] == producer_inputs(api), 'plan producer/profile identity changed')
    base = api.inspect_inputs(plan['selection'], _input_method_repair=True)
    _helper_admitted(base, api)
    donor, effective = admit_donor(plan['successful_donor']['reference'], base, api)
    require(plan['reuse'] == effective.proof and plan['projection'] == base.projection
        and plan['successful_donor'] == donor, 'effective graph or donor changed')
    return plan, effective


def build_receipt(result, plan, inspected, output, commands, api):
    require(plan.get('kind') == PLAN_KIND, 'receipt requires distinct input-method plan')
    api._theme_module()._record_import_receipts(result, plan, output, commands, api)
    counts = result['accounting']
    names = [row['id'] for row in inspected.proof['objects']]
    archives = [row['name'] for row in inspected.proof['archives']]
    require(counts['compiled'] == 2 and counts['imported'] == 50 and set(counts['compiled_ids']) == set(FRESH)
        and [r['id'] for r in plan['successful_donor']['objects']] == counts['imported_ids']
        and set(commands.get('archive_imports', {})) == set(archives), 'receipt partition differs')
    for row in plan['successful_donor']['objects']:
        receipt = api.checked_document(Path(output) / ('evidence/import-' + row['id'] + '.json'))
        require(receipt.get('donor_provenance') == row['donor_provenance']
            and row['donor_provenance']['kind'] == PROVENANCE_KIND, 'import lost original compiler history')
    # Archive copies retain their original readback; direct Theme and unified
    # owner definitions are checked separately in the final map.
    reports = []
    for row in plan['successful_donor']['archives']:
        file = Path(output) / ('evidence/import-archive-' + row['name'] + '.json')
        receipt = api.checked_document(file)
        target = api.ordinary(Path(output) / ('archives/lib' + row['name'] + '.a'))
        require(receipt.get('kind') == 'foundation-document-v2-archive-import-v1'
            and receipt.get('archive') == row['archive'] and receipt.get('original_report') == row['report']
            and receipt.get('name') == row['name'] and receipt.get('origin') == 'imported'
            and receipt.get('destination') == str(target) and receipt.get('hardlinked') is False
            and receipt.get('archive_program_invoked') is False and receipt.get('production_eligible') is False
            and receipt.get('sha256') == api.digest(target) == row['archive']['sha256']
            and receipt.get('bytes') == target.stat().st_size == row['archive']['bytes']
            and target.stat().st_nlink == 1 and api._identity7(target.stat())[:2] != row['archive']['identity'][:2],
            'archive copy/readback differs')
        reports.append(dict(name=row['name'], receipt=str(file.relative_to(output)), sha256=api.digest(file)))
    expected = artifact_names(names, archives)
    for name in expected:
        api.ordinary(Path(output) / name)
    bindings = api._completed_binding(dict(sources=str(inspected.roots['sources']),
        sdk=str(inspected.roots['sdk']), reuse=str(inspected.roots['reuse']), build=str(output)))
    for name in FRESH:
        row = dict(id=name, original_argv=commands['objects'][name],
            original_cwd=str(Path(output) / 'cmake/build'))
        refs = dependency_refs(api.checked_read(Path(output) / ('objects/' + name + '.o.d')),
            row, bindings, None, inspected, api, generated=name == SHIM)
        validate_fresh_members(name, refs, inspected)
    final_map(api.checked_read(Path(output) / 'evidence/engine-link.map'), output, api)
    result.update(kind=BUILD_KIND, expected_artifact_records=174, archive_imports=reports)
    result['accounting'].update(archive_imported=5, archive_repacked=0, imported_archive_names=archives)



def final_map(raw, output, api):
    return api._select_event_module().final_map(raw, output, api)


def validate_fresh_members(name, refs, inspected):
    if name == MAIN:
        require(dict(root='sources', path=HEADER_SOURCE, sha256=HEADER_AFTER_SHA256) in refs,
            'fresh main depfile omits reviewed input-method header')


def validate_proof_location(selection, path, sources, source_files):
    require(selection['document_profile'] == 'editor' and path == sources / PROOF_SOURCE
        and source_files.get(PROOF_SOURCE) == selection['reuse_proof_sha256'],
        'proof must be the pinned inventoried source metadata overlay')


def validate_metadata_overlay(proof):
    require(proof['header_identity']['root'] == 'sources'
        and proof['header_identity']['path'] == HEADER_IDENTITY_SOURCE,
        'header identity must use the declared source metadata relocation')
    def visit(value):
        if type(value) is dict:
            require(not (value.get('root') == 'sources'
                and value.get('path') in (PROOF_SOURCE, 'sources.json', 'recipe.json')),
                'metadata overlay contains a source-manifest or self hash cycle')
            for item in value.values(): visit(item)
        elif type(value) is list:
            for item in value: visit(item)
    visit(proof)
