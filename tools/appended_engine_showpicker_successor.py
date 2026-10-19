"""Closed Theme52 -> native showPicker successor; no process or build fallback.

The prior Theme/F6 lanes remain byte-for-byte unchanged. MAIN_AFTER_SHA256 is
bound to independently accepted NC174 source postimage a2883e614f6ff2268f0ab332
d0888b4f72a671c9bf2b27da160f3249137d9f41. New source/plan packages remain separate.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

HELPER = 'tools/appended_engine_showpicker_successor.py'
PLAN_KIND = 'foundation-document-v2-maintenance-native-showpicker-repair-plan-v1'
BUILD_KIND = 'foundation-document-v2-maintenance-native-showpicker-repair-build-v1'
DONOR_KIND = 'foundation-document-v2-successful-donor-native-showpicker-repair-v1'
PROVENANCE_KIND = 'foundation-document-v2-native-showpicker-object-provenance-v1'
MAIN = 'main.cpp'
SHIM = 'BibEngineDocumentWasmShim.cpp'
THEME = 'RenderThemeEmscripten.cpp'
FRESH = (SHIM, MAIN)
MAIN_SOURCE = 'source/wrapper/src/embedder/main.cpp'
MAIN_BEFORE_SHA256 = '2c315a2d08f8f5025f0619db73621d4aaf79dcdc970c1f5e1b7b692a045beb9b'
MAIN_AFTER_SHA256 = 'd86c1384504cb3780e627a935f96d34fa5900702b363e90cdf9646c26f411030'
PINS = {
    'root_acceptance': '0fe2184d858b0fa25adb99457b17e28369387c7992221948f1e7d3227b4f83f1',
    'closed_result': '5a6d1d0313e69b4d4616f977c33627b378da7c691eb3d0e85fe8202ebcb34cbe',
    'plan': 'b814d4b782291d9bf2200935f8950fefcd470aeea31a69759a6350c4e572239c',
    'maintenance_build': '449d4e131dbfe959a10ac66beb3a2c829f7baef04602db4879a7d171b14ebdc8',
    'commands': '4ee4cd47ac1112bddf8247f4d23e46a65a89ccb1a0e5a51227b55fd87febf40b',
    'input_freeze': 'e695fcdd0882a67928f7aa8c1d75283742b948ac607701ec807cbbfdfe38a3ef',
    'theme_donor': '2f314749c125e293d4eab0c1cf635119310786258d2833a29fa4132044f5fee4',
}


def require(condition, message):
    if not condition:
        raise ValueError('Native showPicker ' + message)


def reference(value, api, pin=None):
    api.fields(value, ('path', 'sha256'), 'showPicker external reference')
    api.sha(value['sha256'], 'showPicker external reference')
    require(pin is None or value['sha256'] == pin, 'authority pin differs')
    return api._completed_reference(value)


def _bindings(plan, build_reference, api):
    return api._completed_binding(dict(sources=plan['selection']['sources'],
        sdk=plan['selection']['sdk'], reuse=plan['selection']['reuse_root'],
        build=str(Path(build_reference['path']).parent)))


def artifact_names(selected, archives):
    require(len(selected) == len(set(selected)) == 52 and set(FRESH) <= set(selected)
        and THEME in selected and len(archives) == len(set(archives)) == 5
        and set(archives) == {'JavaScriptCore', 'PAL', 'Skia', 'WTF', 'WebCore'},
        'requires52 unique selected objects and five archives')
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
    require(len(result) == 174, 'artifact namespace differs from174')
    return result


def _fact_join(fact, ref, api):
    value = api._successful_module()._p5_flat_fact(fact, api)
    require({k: value[k] for k in ('path', 'sha256')} == ref, 'Root reference join differs')
    return value


def accepted_authority(ref, api):
    """Authenticate current accepted Theme52 metadata, without old-lane relabeling."""
    value = reference(ref, api)
    api.fields(value, ('schema_version', 'kind', 'document_profile', *PINS,
        'theme_ninja_log', 'theme_private', 'theme_compiled'), 'showPicker Theme donor')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
        and value['kind'] == DONOR_KIND and value['document_profile'] == 'editor',
        'descriptor kind/profile differs')
    docs = {key: reference(value[key], api, pin) for key, pin in PINS.items()}
    root, closed, old, build, commands, freeze, theme_descriptor = (docs[k] for k in PINS)
    theme = api._theme_module()
    require(root.get('kind') == 'root-closed-successful-donor-native-theme-repair-candidate-accepted-v1'
        and type(root.get('actual_session')) is int and root['actual_session'] == 54226
        and type(root.get('caller_observed_exit')) is int and root['caller_observed_exit'] == 0
        and root.get('status') == 'passed' and root.get('production_eligible') is False
        and type(root.get('verified_artifact_records')) is int and root['verified_artifact_records'] == 174
        and all(root.get(k) is True for k in ('closed', 'writers_joined', 'inputs_unchanged',
            'all_artifact_physical_identities_root_rechecked'))
        and api._supervision_report(root.get('qualified_report'), 0),
        'requires actual54226 accepted natural Root closure')
    for key, name in (('closed', 'closed_result'), ('plan', 'plan'), ('commands', 'commands'),
                      ('maintenance_build', 'maintenance_build'), ('donor_descriptor', 'theme_donor')):
        _fact_join(root['records'][key], value[name], api)
    require(old.get('kind') == theme.PLAN_KIND and old.get('production_eligible') is False
        and old['successful_donor']['reference'] == value['theme_donor']
        and old['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor')),
        'accepted Theme plan/profile join differs')
    selected = [row['id'] for row in old['reuse']['objects']]
    archives = [row['name'] for row in old['reuse']['archives']]
    require(len(selected) == len(set(selected)) == 52 and set(FRESH) <= set(selected)
        and selected[35] == THEME and len(archives) == len(set(archives)) == 5,
        'accepted Theme selected graph differs')
    fresh = [name for name in selected if name in theme.FRESH]
    imported = [name for name in selected if name not in theme.FRESH]
    accounting = dict(selected=52, compiled=2, imported=50, archive_imported=5, archive_repacked=0,
        compiled_ids=fresh, imported_ids=imported, imported_archive_names=archives)
    require(build.get('kind') == theme.BUILD_KIND and build.get('status') == 'passed'
        and build.get('production_eligible') is False and build.get('accounting') == accounting
        and build.get('plan_sha256') == value['plan']['sha256']
        and build.get('successful_donor') == value['theme_donor']
        and build.get('commands') == dict(path='evidence/commands.json', sha256=value['commands']['sha256'])
        and set(commands['objects']) == set(theme.FRESH)
        and set(commands['imports']) == set(imported)
        and set(commands['archive_imports']) == set(archives),
        'accepted Theme compiler/import accounting differs')
    require(all(closed.get(k) is True for k in ('closed', 'verified', 'writers_joined', 'runtime_not_run'))
        and closed.get('status') == 'passed' and type(closed.get('returncode')) is int and closed['returncode'] == 0
        and closed.get('production_eligible') is False
        and closed.get('supervisor_report') == root['qualified_report']
        and closed.get('maintenance_build_sha256') == value['maintenance_build']['sha256']
        and closed.get('successful_donor', {}).get('accounting') == accounting
        and closed.get('static_byte_readback') == 'passed'
        and closed.get('input_identity_namespace_postflight') == 'passed'
        and closed.get('actual_objects') == 52 and closed.get('actual_archive_reports') == 5
        and closed.get('opaque_unchanged_members') == 2060,
        'accepted Theme result differs')
    records = closed['artifact_records']
    require(set(records) == theme.artifact_names(selected, archives)
        and hashlib.sha256((json.dumps(records, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()
            == root['artifact_records_sha256'],
        'accepted Theme complete174 artifact authority differs')
    bindings = _bindings(old, value['maintenance_build'], api)
    require(value['commands']['path'] == str(bindings['build'] / 'evidence/commands.json')
        and freeze.get('roots') == {k: str(v) for k, v in bindings.items() if k != 'build'}
        and type(freeze.get('files')) is dict,
        'accepted Theme coordinates/frozen roots differ')
    api.fields(value['theme_private'], ('vfs', 'configuration', 'launcher'), 'Theme compiler private facts')
    actual = api._completed_private_context(value['theme_private'], bindings, old, freeze)
    require(value['theme_private']['configuration']['sha256'] == build['private_configuration']['config_sha256']
        and value['theme_private']['launcher']['sha256'] == build['private_configuration']['launcher_sha256'],
        'accepted Theme private compiler environment differs')
    return dict(reference=dict(ref), descriptor=value, plan=old, build=build, commands=commands,
        closed=closed, root=root, freeze=freeze, bindings=bindings, records=records,
        theme_descriptor=theme_descriptor, actual_vfs=actual)


def compiler_bindings(row, authority, api):
    provenance = row['donor_provenance']
    require(provenance['kind'] == 'foundation-document-v2-native-theme-object-provenance-v1',
        'inherited object lost Theme provenance')
    origin = provenance['compile_origin']
    require(origin in ('f6-compiled', 'f6-imported'), 'unknown inherited compile origin')
    return api._completed_binding(authority['theme_descriptor']['bindings'] if origin == 'f6-compiled'
        else provenance['predecessor']['compile_bindings'])


def dependency_refs(raw, row, bindings, frozen, inspection, api, *, generated=False):
    """Actual per-object depfile owner; private cache maps only to its exact SDK seed."""
    argv, cwd = row['original_argv'], row['original_cwd']
    require(api._completed_arguments(argv, cwd, bindings) ==
        next(o for o in inspection.proof['objects'] if o['id'] == row['id'])['arguments'],
        'actual compiler argv differs')
    target = argv[argv.index('-o') + 1]
    source = next(o for o in inspection.proof['objects'] if o['id'] == row['id'])['source']
    require(argv[argv.index('-MT') + 1] == target and argv[argv.index('-MF') + 1] == target + '.d'
        and argv[argv.index('-c') + 1] == str(bindings['sources'] / source['path']),
        'actual compiler source/target coordinates differ')
    paths = sorted({os.path.normpath(str(Path(p) if Path(p).is_absolute() else Path(cwd) / p))
        for p in api._depfile_inputs(raw, target=target)})
    require(str(bindings['sources'] / source['path']) in paths and len(paths) <= 16384,
        'actual depfile omits source or exceeds bound')
    metadata = str(bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h')
    require((metadata in paths) == generated, 'generated metadata has wrong compiler owner')
    if 'dependency_keys' in row:
        require(paths == row['dependency_keys'], 'actual depfile differs from authenticated dependency keys')
    result = []
    for key in paths:
        if key == metadata:
            require(row['id'] == SHIM, 'generated dependency belongs only to fresh Shim')
            continue
        path = Path(key)
        cache = bindings['build'] / 'private/cache'
        if cache in path.parents:
            seed = inspection.proof['private_cache']
            name = seed['root'] + '/' + path.relative_to(cache).as_posix()
            require(name in seed['files'], 'unseeded private cache dependency')
            frozen_key = str(bindings['sdk'] / name)
            root = 'sdk'
            actual = api.ordinary(path)
        else:
            owners = [(name, base) for name, base in bindings.items()
                if name != 'build' and base in path.parents]
            require(len(owners) == 1, 'dependency escapes actual compiler roots')
            root, base = owners[0]
            name, frozen_key = path.relative_to(base).as_posix(), key
            actual = None
        if frozen is None:
            pin = inspection.inventories[root].get(name)
            require(type(pin) is str, 'fresh dependency is outside admitted current inventory')
        else:
            fact = frozen['files'].get(frozen_key)
            require(type(fact) is dict and fact.get('path') == frozen_key, 'dependency lacks frozen input authority')
            pin = fact['sha256']
        if actual is not None:
            api.checked_read(actual, pin)
        ref = dict(root=root, path=name, sha256=pin)
        api.ref_path(ref, inspection.roots, inspection.inventories)
        result.append(ref)
    return sorted({(r['root'], r['path']): r for r in result}.values(), key=lambda r: (r['root'], r['path']))


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


def context_transition(previous, current, api):
    api._completed_context_matches(previous, current)
    old_key = '{sources}/' + MAIN_SOURCE
    require(previous['namespace'].get(old_key) == MAIN_BEFORE_SHA256
        and current['namespace'].get(old_key) == MAIN_AFTER_SHA256, 'main namespace pre/postimage differs')
    narrowed = deepcopy(current)
    narrowed['namespace'][old_key] = MAIN_BEFORE_SHA256
    require(narrowed == previous, 'include namespace changes beyond reviewed main TU')


def effective_inspection(base, authority, api):
    """Keep original51 profile admission; derive the accepted Theme direct object."""
    require(MAIN_AFTER_SHA256 is not None, 'source binding remains unarmed pending NC174 acceptance')
    api.sha(MAIN_AFTER_SHA256, 'reviewed showPicker main source')
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
    # Only independently validated prelink metadata and the projection-bound
    # header-identity wrapper may change. Physical headers/VFS remain identical.
    prior, changed = deepcopy(old), deepcopy(proof)
    for obj in changed['objects']:
        before = next(o for o in prior['objects'] if o['id'] == obj['id'])
        if obj['id'] == MAIN:
            require(before['source'] == dict(root='sources', path=MAIN_SOURCE, sha256=MAIN_BEFORE_SHA256)
                and obj['source'] == dict(root='sources', path=MAIN_SOURCE, sha256=MAIN_AFTER_SHA256),
                'reviewed main logical source/hash differs')
            obj['source'] = deepcopy(before['source'])
            obj['compile_context']['source'] = deepcopy(before['compile_context']['source'])
            if obj['provenance'].get('kind') == 'derived-command-v1':
                obj['provenance']['source_replacement']['after'] = deepcopy(before['source'])
        obj['compile_context']['generated_metadata'] = deepcopy(before['compile_context']['generated_metadata'])
    for key in ('header_identity',):
        require(proof[key]['root'] == old[key]['root'] and proof[key]['path'] == old[key]['path'],
            'header authority logical coordinate differs')
        changed[key] = deepcopy(prior[key])
        if proof[key]['root'] == 'reuse':
            path = proof[key]['path']
            require(proof['inventory']['files'].get(path) == proof[key]['sha256']
                and old['inventory']['files'].get(path) == old[key]['sha256'],
                'projection wrapper lacks exact old/current reuse inventory join')
            changed['inventory']['files'][path] = prior['inventory']['files'][path]
    require(set(proof['metadata']) == set(old['metadata']), 'metadata role set differs')
    for name in proof['metadata']:
        if name == 'prelink_plan':
            require({k: proof['metadata'][name][k] for k in ('root', 'path')} ==
                {k: old['metadata'][name][k] for k in ('root', 'path')}, 'prelink logical coordinate differs')
            changed['metadata'][name] = deepcopy(prior['metadata'][name])
    require(changed == prior, 'proof changes beyond reviewed main/identity-derived metadata')
    result = api.Inspection(base.selection, base.recipe, base.projection, proof,
        base.roots, base.inventories, config)
    api._current_context(theme, result)
    api.ref_path(theme['source'], result.roots, result.inventories)
    return result


def admit_donor(ref, base, api):
    authority = accepted_authority(ref, api)
    effective = effective_inspection(base, authority, api)
    old_inspection = _old_inspection(authority, base, api)
    require(authority['actual_vfs'] ==
        api._completed_normalize_vfs(api._header_identity(old_inspection)['overlay'], old_inspection.roots),
        'actual Theme compiler VFS differs from accepted header authority')
    old, records, commands, bindings = (authority[k] for k in ('plan', 'records', 'commands', 'bindings'))
    # Exact actual Theme compiler closure; generated-dependent old Shim is never imported.
    row = deepcopy(authority['descriptor']['theme_compiled'])
    api.fields(row, ('id', 'ninja_record', 'ninja_command', 'command_script'), 'Theme compiler declaration')
    require(row['id'] == THEME, 'fresh Theme compiler declaration differs')
    argv, cwd = commands['objects'][THEME], str(bindings['build'] / 'cmake/build')
    product, depfile = records['objects/' + THEME + '.o'], records['objects/' + THEME + '.o.d']
    row.update(object=product, depfile=depfile, original_argv=argv, original_cwd=cwd,
        command_sha256=hashlib.sha256(api.encoded(dict(argv=argv, cwd=cwd))).hexdigest())
    fact = authority['descriptor']['theme_ninja_log']
    api._successful_module()._fact_shape(fact, bindings['build'] / 'cmake/build/.ninja_log', api)
    require(fact['bytes'] <= 16 * 1024 * 1024, 'Ninja evidence exceeds bound')
    ninja = api._completed_fact(fact).decode('utf-8')
    require(ninja.startswith('# ninja log v6\n'), 'Ninja ledger version differs')
    target = str(bindings['build'] / ('objects/' + THEME + '.o'))
    matching = [line.split('\t') for line in ninja.splitlines()[1:]
        if len(line.split('\t')) == 5 and line.split('\t')[3] == target]
    require(len(matching) == 1 and row['ninja_record'] == matching[0]
        and all(v.isdecimal() for v in row['ninja_record'][:3])
        and int(row['ninja_record'][1]) >= int(row['ninja_record'][0])
        and int(row['ninja_record'][2]) == product['identity'][5]
        and row['ninja_record'][4] == api._completed_ninja_command(row, argv, bindings, old_inspection.proof['host_tools']),
        'Theme lacks exact successful compiler/Ninja authority')
    refs = dependency_refs(api._completed_fact(depfile), row, bindings,
        authority['freeze'], old_inspection, api)
    row['dependency_keys'] = sorted({os.path.normpath(str(Path(p) if Path(p).is_absolute()
        else Path(cwd) / p)) for p in api._depfile_inputs(api._completed_fact(depfile), target=target)})
    rows, closures = {THEME: row}, {THEME: refs}
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
            'inherited Theme copy receipt differs')
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
    all_refs.extend(dependency_refs(api._completed_fact(records['objects/' + SHIM + '.o.d']),
        shim, bindings, authority['freeze'], old_inspection, api, generated=True))
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
            theme_root_acceptance=authority['descriptor']['root_acceptance'],
            theme_object=records['objects/' + name + '.o'],
            predecessor=row.get('donor_provenance'),
            compile_bindings={k: str(v) for k, v in
                (bindings if name == THEME else compiler_bindings(row, authority, api)).items()},
            compile_origin='theme-compiled' if name == THEME else 'theme-imported')
        imported.append(row)
    require(len(imported) == 50 and THEME in [r['id'] for r in imported], 'requires50 imports including accepted Theme')
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
        (*api.required_helpers('editor'), api.SUCCESSFUL_HELPER, api.THEME_HELPER, HELPER)}


def _helper_admitted(base, api):
    for name, pin in producer_inputs(api).items():
        require(base.inventories['sources'].get(name) == pin, 'retain exact producer helper: ' + name)


def make_plan(selection, output, donor_ref, api):
    require(MAIN_AFTER_SHA256 is not None, 'source binding remains unarmed pending NC174 acceptance')
    base = api.inspect_inputs(selection)
    _helper_admitted(base, api)
    donor, inspected = admit_donor(donor_ref, base, api)
    destination = api.engine_sdk.new_destination(output,
        (*base.roots.values(), *api._completed_input_directories(donor)))
    plan = dict(schema_version=1, kind=PLAN_KIND, scope=api.SCOPE, selection=inspected.selection,
        profile_sha256=api.digest(api.ROOT / api.profile_path('editor')), producer_inputs=producer_inputs(api),
        reuse=inspected.proof, projection=base.projection, production_eligible=False, successful_donor=donor)
    with api.engine_sdk._OwnedTree(destination.parent, '.engine-showpicker-plan-') as staged:
        (staged.path / 'plan.json').write_bytes(api.encoded(plan))
        staged.publish(destination)
    return dict(scope=api.SCOPE, plan=str(destination / 'plan.json'),
        plan_sha256=api.digest(destination / 'plan.json'), production_eligible=False)


def verify_plan(plan, api):
    api.fields(plan, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256', 'producer_inputs',
        'reuse', 'projection', 'production_eligible', 'successful_donor'), 'showPicker plan')
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1 and plan['kind'] == PLAN_KIND
        and plan['scope'] == api.SCOPE and plan['production_eligible'] is False
        and plan['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor'))
        and plan['producer_inputs'] == producer_inputs(api), 'plan producer/profile identity changed')
    base = api.inspect_inputs(plan['selection'])
    _helper_admitted(base, api)
    donor, effective = admit_donor(plan['successful_donor']['reference'], base, api)
    require(plan['reuse'] == effective.proof and plan['projection'] == base.projection
        and plan['successful_donor'] == donor, 'effective graph or donor changed')
    return plan, effective


def build_receipt(result, plan, inspected, output, commands, api):
    require(plan.get('kind') == PLAN_KIND, 'receipt requires distinct showPicker plan')
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
    # Reuse archive copy/readback and Theme final ownership checks without its
    # old two-fresh/Theme-depfile assumptions.
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
        dependency_refs(api.checked_read(Path(output) / ('objects/' + name + '.o.d')),
            row, bindings, None, inspected, api, generated=name == SHIM)
    api._theme_module().final_map(api.checked_read(Path(output) / 'evidence/engine-link.map'), output)
    result.update(kind=BUILD_KIND, expected_artifact_records=174, archive_imports=reports)
    result['accounting'].update(archive_imported=5, archive_repacked=0, imported_archive_names=archives)

