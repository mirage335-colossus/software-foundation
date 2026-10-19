"""Closed Theme-direct successor of the accepted F6 editor baseline.

No discovery, subprocess, SDK modification or fallback. Probe derivation is pure;
plan admission requires a separately executed, hash-bound closed probe receipt.
"""
from copy import deepcopy
import hashlib
import os
from pathlib import Path

HELPER = 'tools/appended_engine_theme_successor.py'
PLAN_KIND = 'foundation-document-v2-maintenance-native-theme-repair-plan-v1'
BUILD_KIND = 'foundation-document-v2-maintenance-native-theme-repair-build-v1'
DONOR_KIND = 'foundation-document-v2-successful-donor-native-theme-repair-v1'
SUPPLEMENT_KIND = 'foundation-document-v2-native-theme-supplement-v1'
PROBE_KIND = 'foundation-document-v2-native-theme-dependency-probe-v1'
THEME = 'RenderThemeEmscripten.cpp'
SHIM = 'BibEngineDocumentWasmShim.cpp'
SOURCE = 'source/engine/Source/WebCore/rendering/emscripten/' + THEME
SOURCE_SHA256 = 'b6720505415c23279a3dca6f1e11717260797bc45f64d3a4f29c2233f335cd81'
ORIGINAL_COMMAND = 'b687d7fb86821a4676045faff64330242476461b8cb5bb85f676d8d7225729b9'
FRESH = (SHIM, THEME)
BASELINE_REUSE_SHA256 = '4ba9e2da96bc5e41248639a7dfdf463cb87e1ee942eafdfd13ca497cebe02a3a'
PAIRED_SDK_SHA256 = '217e8ee79c8f825e52cf92338a841cd7c79836666aaee7cbd1f41ee9e070920a'
PINS = {
 'root_acceptance': '1f4feabd15eaa00e4de382912dad6a1093edebe0dee7ac713a4f424e5ea7860e',
 'closed_result': '5426e70a16de40177e23c40c7237469f705918fe613f19aee9f5abf295cd3208',
 'plan': '70485f92de3f4d0f5e4f488cab2524dadacc44f0725df55977db5c5159ff7773',
 'maintenance_build': '96bca4d1e5517be072160daac8e8a0214b9948116b91048cc167deab3e15b08b',
 'commands': '0f891677aed07b32ce090fe0274091cd25a01e853cd63e0144ac27330dce8d39',
 'build_packet': 'ab604073fefca7bf8f2285987a1d75094d225dff0bfb92b00712c30f66602149',
 'input_freeze': '0feb8e28ad9713e8d0eafe07f218ee1b64e33f69f1202d88f0422351573e26a7',
}

def require(condition, label):
    if not condition:
        raise ValueError('Native Theme ' + label)

def integer(value, expected):
    return type(value) is int and value == expected

def reference(value, api, pin=None):
    api.fields(value, ('path', 'sha256'), 'Theme external reference')
    api.sha(value['sha256'], 'Theme reference')
    require(pin is None or value['sha256'] == pin, 'authority pin differs')
    return api._completed_reference(value)

def baseline_shape(inspected):
    p, c = inspected.proof, inspected.profile
    names = c['direct_objects'] + c['engine_objects']
    require(inspected.selection['document_profile'] == 'editor'
        and inspected.selection['reuse_proof_sha256'] == BASELINE_REUSE_SHA256
        and inspected.selection['sdk_manifest_sha256'] == PAIRED_SDK_SHA256
        and len(c['direct_objects']) == 35 and len(c['engine_objects']) == 16
        and len(names) == len(set(names)) == 51 and THEME not in names
        and [o['id'] for o in p['objects']] == names
        and len(p['replacements']) == 16 and len(p['archives']) == 5
        and sum(len(a['members']) for a in p['archives']) - 16 == 2060,
        'requires unchanged editor51 baseline/16 replacements/2060 opaque')
    return names

def _probe_private(inspected, root, api):
    header = api._header_identity(inspected)
    config = ''.join(key+' = '+repr(str(inspected.roots['sdk']/name))+'\n'
        for key,name in inspected.proof['emscripten_config'].items())
    config += 'CACHE = '+repr(str(root/'private/cache'))+'\nFROZEN_CACHE = True\n'
    class Capture:
        def __str__(self): return str(root/'private/sdk-python')
        def write_text(self, text, encoding): self.raw=text.encode(encoding)
        def chmod(self, mode): self.mode=mode
    capture=Capture()
    api.python_launcher(inspected.proof['host_tools']['python']['path'],
        [inspected.roots['sdk']/name for name in inspected.profile['python_entrypoints']],capture)
    blobs=dict(vfs=api.encoded(header['overlay']),configuration=config.encode(),launcher=capture.raw)
    names=dict(vfs='header-identity-vfs.json',configuration='emscripten-config.py',launcher='sdk-python')
    return {key:dict(path=str(root/'private'/names[key]),sha256=hashlib.sha256(raw).hexdigest(),
        mode=capture.mode if key=='launcher' else 420) for key,raw in blobs.items()}

def derive_probe(inspected, source, build_root, api):
    """Pure bootstrap: no pre-existing Theme depfile/context is required."""
    baseline_shape(inspected)
    api.fields(source, api.REFERENCE_FIELDS, 'Theme source')
    require(source == dict(root='sources', path=SOURCE, sha256=SOURCE_SHA256),
            'requires exact reviewed625-byte Space-only source')
    selected = api.ref_path(source, inspected.roots, inspected.inventories)
    require(len(api.checked_read(selected, SOURCE_SHA256)) == 625, 'source size differs')
    root = Path(build_root)
    require(root.is_absolute() and '..' not in root.parts, 'probe output must be absolute')
    for base in inspected.roots.values():
        require(root != base and root not in base.parents and base not in root.parents,
                'probe output overlaps retained inputs')
    ledger = api.checked_document(api.ref_path(inspected.proof['baseline']['command_records'],
        inspected.roots, inspected.inventories))
    command = ledger['commands'].get(ORIGINAL_COMMAND)
    require(type(command) is dict and hashlib.sha256(api.encoded(command)).hexdigest() == ORIGINAL_COMMAND,
            'original Theme command is absent or changed')
    args = api._original_arguments(command, inspected.proof['baseline']['original_bindings'])
    require(command['argv'][command['argv'].index('-c') + 1].endswith('/' + THEME)
        and api._exception_policy(args) is False and '-fno-rtti' in args
        and '-std=c++23' in args, 'original engine compiler policy differs')
    header = api._header_identity(inspected)
    require(header is not None, 'requires original header identity environment')
    overlay = root / 'private/header-identity-vfs.json'
    target = root / ('objects/' + THEME + '.o')
    depfile = root / 'evidence/theme-probe.d'
    emxx = inspected.roots['sdk'] / inspected.proof['sdk_tools']['emxx']['path']
    argv = [str(emxx), '-ivfsoverlay', str(overlay),
        *(api._expand(a, inspected.roots, root) for a in args),
        '-fsyntax-only', '-MD', '-MT', str(target), '-MF', str(depfile), '-c', str(selected)]
    return dict(argv=argv, cwd=str(root), target=str(target), depfile=str(depfile),
        source=dict(source), arguments=args, original_command_sha256=ORIGINAL_COMMAND,
        header_overlay_sha256=hashlib.sha256(api.encoded(header['overlay'])).hexdigest(),
        sdk_manifest_sha256=inspected.selection['sdk_manifest_sha256'],
        baseline_reuse_proof_sha256=inspected.selection['reuse_proof_sha256'],
        private=_probe_private(inspected, root, api))

def _dependency_refs(raw, command, inspected, api):
    keys = sorted({os.path.normpath(str(Path(p) if Path(p).is_absolute()
        else Path(command['cwd']) / p)) for p in api._depfile_inputs(raw, target=command['target'])})
    refs = []
    for key in keys:
        path = Path(key)
        roots = [(name, base) for name, base in inspected.roots.items() if base in path.parents]
        if roots:
            require(len(roots) == 1, 'probe dependency has ambiguous root')
            name, base = roots[0]; logical = path.relative_to(base).as_posix()
            pin = inspected.inventories[name].get(logical)
        else:
            private = Path(command['cwd']) / 'private/cache'
            require(private in path.parents, 'probe dependency is outside admitted roots')
            name = 'sdk'; seed = inspected.proof['private_cache']
            logical = seed['root'] + '/' + path.relative_to(private).as_posix()
            require(logical in seed['files'], 'unseeded probe cache input')
            pin = inspected.inventories['sdk'].get(logical)
            require(type(pin) is str, 'probe cache input is not inventoried')
            api.checked_read(api.ordinary(path), pin)
        require(type(pin) is str, 'probe dependency is not inventoried')
        ref = dict(root=name, path=logical, sha256=pin)
        api.ref_path(ref, inspected.roots, inspected.inventories)
        refs.append(ref)
    require(command['source'] in refs and len(refs) <= 8192, 'probe closure omits source or exceeds bound')
    return sorted({(r['root'], r['path']): r for r in refs}.values(), key=lambda r: (r['root'], r['path']))

def admit_supplement(ref, inspected, api):
    value = reference(ref, api)
    api.fields(value, ('schema_version', 'kind', 'baseline_plan_sha256', 'source', 'probe'), 'Theme supplement')
    require(integer(value['schema_version'], 1) and value['kind'] == SUPPLEMENT_KIND
        and value['baseline_plan_sha256'] == PINS['plan'], 'supplement baseline/kind differs')
    probe = reference(value['probe'], api)
    api.fields(probe, ('schema_version', 'kind', 'command', 'execution', 'depfile', 'private'), 'Theme probe receipt')
    require(integer(probe['schema_version'], 1) and probe['kind'] == PROBE_KIND, 'probe kind differs')
    expected = derive_probe(inspected, value['source'], probe['command']['cwd'], api)
    require(probe['command'] == expected, 'probe command/context differs from pure derivation')
    execution = probe['execution']
    api.fields(execution, ('caller_exit', 'closed', 'writers_joined', 'inputs_unchanged', 'qualified_report'), 'Theme probe execution')
    require(integer(execution['caller_exit'], 0) and execution['closed'] is True
        and execution['writers_joined'] is True and execution['inputs_unchanged'] is True,
        'probe has no closed successful unchanged caller')
    require(api._supervision_report(execution['qualified_report'], 0), 'probe natural closure is unqualified')
    require(probe['depfile']['path'] == expected['depfile']
        and type(probe['depfile'].get('bytes')) is int and 0 < probe['depfile']['bytes'] <= 32*1024*1024,
        'probe depfile coordinates/bounds differ')
    api.fields(probe['private'], ('vfs', 'configuration', 'launcher'), 'Theme probe private facts')
    for key, expected_fact in expected['private'].items():
        actual=probe['private'][key]
        require(all(actual.get(k)==v for k,v in expected_fact.items()), 'probe private environment differs: '+key)
        api._completed_fact(actual)
    raw = api._completed_fact(probe['depfile'])
    refs = _dependency_refs(raw, expected, inspected, api)
    return dict(reference=dict(ref), source=value['source'], probe=value['probe'], command=expected,
                dependencies=refs, depfile=probe['depfile'])

def effective_inspection(base, supplement, api):
    """Compose52 in memory; no retained profile/proof is rewritten."""
    names = baseline_shape(base)
    proof, profile = deepcopy(base.proof), deepcopy(base.profile)
    profile['direct_objects'].append(THEME)
    profile['source_bindings'][THEME] = SOURCE
    profile['derived_commands'][THEME] = dict(donor_source=THEME, remove=[], append=[])
    args = supplement['command']['arguments']
    obj = dict(id=THEME, source=supplement['source'], arguments=args,
        dependencies=supplement['dependencies'], unified_members=[], exceptions=False,
        provenance=dict(kind='derived-command-v1', donor_command_sha256=ORIGINAL_COMMAND,
            profile_sha256=api.digest(api.ROOT / api.profile_path('editor')),
            source_replacement=dict(before=None, after=supplement['source']), remove=[], append=[]))
    ledger = api.checked_document(api.ref_path(proof['baseline']['command_records'], base.roots, base.inventories))
    original = ledger['commands'][ORIGINAL_COMMAND]
    obj['provenance']['source_replacement']['before'] = original['argv'][original['argv'].index('-c') + 1]
    obj['compile_context'] = dict(source=obj['source'], headers=obj['dependencies'],
        macros=api._macros(args), generated_metadata=[proof['metadata'][k] for k in sorted(proof['metadata'])],
        sdk_manifest_sha256=base.selection['sdk_manifest_sha256'], arguments=args)
    proof['objects'].insert(35, obj)
    result = api.Inspection(base.selection, base.recipe, base.projection, proof, base.roots, base.inventories, profile)
    api._object_provenance(obj, ledger['commands'], result)
    api._current_context(obj, result)
    api._arguments(args, inspection=result)
    require([o['id'] for o in proof['objects']] == profile['direct_objects'] + profile['engine_objects']
        and [o['id'] for o in proof['objects'] if o['id'] != THEME] == names, 'effective order differs')
    return result

def artifact_names(selected, archives):
    require(len(selected) == len(set(selected)) == 52 and set(FRESH) <= set(selected)
        and len(archives) == len(set(archives)) == 5, 'artifact shape differs')
    names = {'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h', 'document-generated/provider-build.json',
        'evidence/engine-link.map'}
    for name in selected:
        names.add('objects/' + name + '.o')
        if name in FRESH:
            names.add('objects/' + name + '.o.d')
        else:
            names.update(('evidence/import-' + name + '.json', 'evidence/import-' + name + '.original.d'))
    for name in archives:
        names.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json',
                      'evidence/import-archive-' + name + '.json'))
    require(len(names) == 174, 'artifact namespace differs from174')
    return names

def final_map(raw, output):
    text = raw.decode('utf-8')
    require('libWebCore.a(' + THEME + '.o)' not in text, 'old Theme archive member was extracted')
    owner = str(Path(output) / ('objects/' + THEME + '.o')) + ':'
    singleton = '_ZN7WebCore11RenderTheme9singletonEv'
    override = '_ZNK7WebCore21RenderThemeEmscripten23popsMenuBySpaceOrReturnEv'
    for symbol in (singleton, override):
        require(any(owner in line and symbol in line for line in text.splitlines()),
                'fresh Theme definition missing: ' + symbol)
    return dict(singleton_owner=owner, space_override_owner=owner, old_archive_member_extracted=False)

def _f6_compiled_rows(value, old_inspection, bindings, freeze, records, commands, api):
    """Read the actual six F6 depfiles; only five become imports."""
    import os
    expected = [row['id'] for row in old_inspection.proof['objects'] if row['id'] in api._successful_module().NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS]
    rows = value['f6_compiled']
    require(type(rows) is list and all(type(row) is dict for row in rows)
        and [row.get('id') for row in rows] == expected, 'F6 compiler evidence must preserve exact ordered six')
    fact = value['f6_ninja_log']
    api._successful_module()._fact_shape(fact, bindings['build'] / 'cmake/build/.ninja_log', api)
    require(fact['bytes'] <= 16 * 1024 * 1024, 'F6 Ninja ledger exceeds read bound')
    ninja = api._completed_fact(fact).decode('utf-8')
    require(ninja.startswith('# ninja log v6\n'), 'F6 Ninja ledger version differs')
    ledger = [line.split('\t') for line in ninja.splitlines()[1:]]
    cwd = str(bindings['build'] / 'cmake/build')
    objects = {row['id']: row for row in old_inspection.proof['objects']}
    all_refs, admitted = [], []
    total = sum(records['objects/' + name + '.o.d']['bytes'] for name in expected)
    require(total <= 256 * 1024 * 1024, 'F6 dependency evidence exceeds read bound')
    for row in rows:
        api.fields(row, ('id', 'ninja_record', 'ninja_command', 'command_script'), 'F6 compiler evidence')
        require(row['command_script'] is None or type(row['command_script']) is dict,
                 'F6 command script requires an explicit fact or null')
        name = row['id']; obj = objects[name]; argv = commands['objects'][name]
        require(api._completed_arguments(argv, cwd, bindings) == obj['arguments'], 'F6 compiler argv differs')
        target = str(bindings['build'] / ('objects/' + name + '.o'))
        product = records['objects/' + name + '.o']; depfile = records['objects/' + name + '.o.d']
        require(argv[argv.index('-o') + 1] == target and argv[argv.index('-MT') + 1] == target
            and argv[argv.index('-MF') + 1] == target + '.d'
            and argv[argv.index('-c') + 1] == str(bindings['sources'] / obj['source']['path']),
            'F6 compiler source/target coordinates differ')
        matching = [item for item in ledger if len(item) == 5 and item[3] == target]
        recorded = row['ninja_record']
        require(len(matching) == 1 and recorded == matching[0]
            and all(item.isdecimal() for item in recorded[:3])
            and int(recorded[1]) >= int(recorded[0]) and int(recorded[2]) == product['identity'][5]
            and recorded[4] == api._completed_ninja_command(row, argv, bindings, old_inspection.proof['host_tools']),
            'F6 object lacks exact successful compiler/Ninja authority')
        normalize = lambda p: os.path.normpath(str(Path(p) if Path(p).is_absolute() else Path(cwd) / p))
        keys = sorted({normalize(p) for p in api._depfile_inputs(api._completed_fact(depfile), target=target)})
        require(str(bindings['sources'] / obj['source']['path']) in keys, 'F6 depfile omits its source')
        refs = []
        for key in keys:
            generated = str(bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h')
            if key == generated:
                require(name == 'BibEngineDocumentWasmShim.cpp', 'F6 generated dependency has unexpected owner')
                continue  # This source-identity-dependent owner always recompiles.
            path = Path(key)
            private_cache = bindings['build'] / 'private/cache'
            if private_cache in path.parents:
                relative = path.relative_to(private_cache).as_posix()
                seed = old_inspection.proof['private_cache']
                logical = seed['root'] + '/' + relative
                require(logical in seed['files'], 'F6 cache dependency is not an exact SDK seed')
                original = str(bindings['sdk'] / logical)
                frozen = freeze['files'].get(original)
                require(type(frozen) is dict, 'F6 cache dependency lacks frozen SDK authority')
                api._completed_fact(frozen, sdk=True)
                api.checked_read(api.ordinary(path), frozen['sha256'])
                reference = dict(root='sdk', path=logical, sha256=frozen['sha256'])
            else:
                roots = [(root, base) for root, base in bindings.items() if root != 'build' and base in path.parents]
                require(len(roots) == 1, 'F6 dependency is generated or outside retained roots')
                root, base = roots[0]; frozen = freeze['files'].get(key)
                require(type(frozen) is dict and frozen.get('path') == key, 'F6 dependency lacks frozen input fact')
                api._completed_fact(frozen, sdk=root == 'sdk')
                reference = dict(root=root, path=path.relative_to(base).as_posix(), sha256=frozen['sha256'])
            api.ref_path(reference, old_inspection.roots, old_inspection.inventories)
            refs.append(reference)
        all_refs.extend(refs)
        require((generated in keys) == (name == 'BibEngineDocumentWasmShim.cpp'),
                 'F6 generated metadata requires its exact fresh Shim owner')
        if name in (set(expected) - {SHIM}):
            require(generated not in keys, 'Generated-dependent F6 object cannot be imported')
            api._completed_fact(product)
            admitted.append(dict(row, object=product, depfile=depfile, dependency_keys=keys,
                command_sha256=hashlib.sha256(api.encoded({'argv': argv, 'cwd': cwd})).hexdigest(),
                original_argv=argv, original_cwd=cwd, dependency_refs=refs))
    return admitted, all_refs


def context_extension(previous, current, api):
    """Exact single new TU; no old namespace byte or header policy changes."""
    key = '{sources}/' + SOURCE
    require(key not in previous['namespace'] and current['namespace'].get(key) == SOURCE_SHA256,
            'context requires exactly reviewed new Theme TU')
    narrowed = deepcopy(current)
    del narrowed['namespace'][key]
    api._completed_context_matches(previous, narrowed)
    require(previous == narrowed, 'context changes an old namespace input')


def admit_donor(ref, base, api):
    value = reference(ref, api)
    api.fields(value, ('schema_version', 'kind', 'document_profile', 'f6_donor',
        'bindings', 'f6_compiled', 'f6_ninja_log', 'f6_private', *PINS), 'Theme F6 donor')
    require(integer(value['schema_version'], 1) and value['kind'] == DONOR_KIND
        and value['document_profile'] == 'editor', 'donor kind/profile differs')
    docs = {name: reference(value[name], api, pin) for name, pin in PINS.items()}
    root, result, old, build, commands, packet, freeze = (docs[k] for k in PINS)
    helper = api._successful_module()
    require(root.get('kind') == 'root-closed-successful-donor-native-control-keypress-repair-candidate-accepted-v1'
        and integer(root.get('actual_session'), 40718) and integer(root.get('caller_observed_exit'), 0)
        and root.get('status') == 'passed' and root.get('closed') is True
        and root.get('writers_joined') is True and root.get('inputs_unchanged') is True
        and root.get('all_artifact_physical_identities_root_rechecked') is True
        and integer(root.get('verified_artifact_records'), 167)
        and root.get('production_eligible') is False, 'F6 accepted Root closure differs')
    require(api._supervision_report(root.get('qualified_report'), 0), 'F6 natural Root closure differs')
    for field in ('closed', 'verified', 'writers_joined', 'runtime_not_run'):
        require(result.get(field) is True, 'F6 result is not closed/verified')
    require(result.get('status') == 'passed' and integer(result.get('returncode'), 0)
        and result.get('supervisor_report') == root['qualified_report']
        and result.get('input_identity_namespace_postflight') == 'passed'
        and result.get('static_byte_readback') == 'passed'
        and integer(result.get('actual_objects'), 51) and integer(result.get('actual_archive_reports'), 5)
        and integer(result.get('opaque_unchanged_members'), 2060), 'F6 accepted result differs')
    for key, name in (('closed', 'closed_result'), ('commands', 'commands'),
                      ('maintenance_build', 'maintenance_build'), ('plan', 'plan')):
        fact = helper._p5_flat_fact(root['records'][key], api)
        require({k: fact[k] for k in ('path', 'sha256')} == value[name], 'F6 Root reference join differs')
    require(root['records']['donor_descriptor']['path'] == value['f6_donor']['path']
        and root['records']['donor_descriptor']['sha256'] == value['f6_donor']['sha256'], 'F6 donor join differs')
    names = baseline_shape(base)
    require(old.get('kind') == api.NATIVE_CONTROL_KEYPRESS_REPAIR_PLAN_KIND
        and old.get('production_eligible') is False and old['reuse'] == base.proof
        and old['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor'))
        and old['successful_donor']['reference'] == value['f6_donor'], 'F6 legacy51 proof/profile changed')
    bindings = api._completed_binding(value['bindings'])
    require(all(str(bindings[k]) == old['selection'][v] for k, v in
        (('sources', 'sources'), ('sdk', 'sdk'), ('reuse', 'reuse_root')))
        and bindings['sdk'] == base.roots['sdk'] and bindings['reuse'] == base.roots['reuse'],
        'F6 bindings/paired retained roots differ')
    require(value['maintenance_build']['path'] == str(bindings['build'] / 'maintenance-build.json')
        and value['commands']['path'] == str(bindings['build'] / 'evidence/commands.json')
        and packet['output'] == str(bindings['build']) and packet['selection'] == old['selection']
        and packet['plan_sha256'] == value['plan']['sha256']
        and packet['freeze'] == value['input_freeze']['path']
        and packet['freeze_sha256'] == value['input_freeze']['sha256'], 'F6 packet/freeze coordinates differ')
    fresh = set(helper.NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS)
    accounting = dict(selected=51, compiled=6, imported=45, archive_imported=5, archive_repacked=0,
        compiled_ids=[n for n in names if n in fresh], imported_ids=[n for n in names if n not in fresh],
        imported_archive_names=[a['name'] for a in old['reuse']['archives']])
    require(build.get('kind') == api.NATIVE_CONTROL_KEYPRESS_REPAIR_BUILD_KIND
        and build.get('status') == 'passed' and build.get('accounting') == accounting
        and result['successful_donor']['accounting'] == accounting
        and build.get('commands') == dict(path='evidence/commands.json', sha256=value['commands']['sha256'])
        and result.get('maintenance_build_sha256') == value['maintenance_build']['sha256']
        and set(commands['objects']) == fresh and set(commands['imports']) == set(names)-fresh,
        'F6 compiler/import accounting differs')
    require(freeze.get('roots') == {k:str(v) for k,v in bindings.items() if k != 'build'}
        and type(freeze.get('files')) is dict, 'F6 frozen roots differ')
    def frozen_json(name):
        fact = freeze['files'].get(str(bindings['sources'] / name))
        require(type(fact) is dict, 'F6 source metadata lacks frozen authority')
        return api.document(api._completed_fact(fact))
    source_manifest = frozen_json('sources.json')
    require(freeze['files'][str(bindings['sources'] / 'sources.json')]['sha256'] == old['selection']['sources_sha256']
        and freeze['files'][str(bindings['sources'] / 'recipe.json')]['sha256'] == old['selection']['recipe_sha256'],
        'F6 frozen source manifest/recipe differs')
    old_inspection = api.Inspection(old['selection'], frozen_json('recipe.json'), old['projection'],
        old['reuse'], {k:v for k,v in bindings.items() if k != 'build'},
        dict(sources=source_manifest['files'], sdk=base.inventories['sdk'], reuse=base.inventories['reuse']), base.profile)
    api.fields(value['f6_private'], ('vfs','configuration','launcher'), 'F6 private compiler facts')
    actual_vfs=api._completed_private_context(value['f6_private'], bindings, old, freeze)
    require(actual_vfs == api._completed_normalize_vfs(api._header_identity(old_inspection)['overlay'], old_inspection.roots)
        and value['f6_private']['configuration']['sha256'] == build['private_configuration']['config_sha256']
        and value['f6_private']['launcher']['sha256'] == build['private_configuration']['launcher_sha256'],
        'F6 actual private compiler environment differs')
    legacy = helper.native_control_keypress_dependency_admission(value['f6_donor'], old_inspection, api)
    records = result['artifact_records']
    require(set(records) == helper.native_control_keypress_artifact_names(names, accounting['imported_archive_names']),
        'F6 complete167 artifact namespace differs')
    compiled, refs = _f6_compiled_rows(value, old_inspection, bindings, freeze, records, commands, api)
    dependencies = legacy.pop('object_dependencies')
    require(type(dependencies) is dict and list(dependencies) == [row['id'] for row in legacy['objects']]
        and all(type(refs) is list and refs for refs in dependencies.values()),
        'historical dependency ownership is incomplete')
    inherited = [ref for refs in dependencies.values() for ref in refs]
    for dep in refs + inherited:
        api.ref_path(dep, base.roots, base.inventories)
    previous = api._completed_header_context(old_inspection, refs + inherited, old['reuse']['objects'])
    current = api._completed_header_context(base, refs + inherited, base.proof['objects'])
    context_extension(previous, current, api)
    by_id = {row['id']: deepcopy(row) for row in legacy['objects']}
    by_id.update({row['id']: row for row in compiled})
    imported = []
    for name in names:
        if name == SHIM:
            continue
        row = by_id[name]
        if name in fresh:
            dependencies = row.pop('dependency_refs')
            for dep in dependencies:
                api.ref_path(dep, base.roots, base.inventories)
        else:
            receipt = api.document(api._completed_fact(records['evidence/import-' + name + '.json']))
            require(receipt.get('object') == row['object'] and receipt.get('original_depfile') == row['depfile']
                and receipt.get('compiler_invoked') is False and receipt.get('hardlinked') is False
                and receipt.get('donor_provenance') == row.get('donor_provenance')
                and receipt.get('destination') == records['objects/'+name+'.o']['path']
                and receipt.get('sha256') == records['objects/'+name+'.o']['sha256'] == row['object']['sha256']
                and receipt.get('bytes') == records['objects/'+name+'.o']['bytes'] == row['object']['bytes'], 'F6 inherited import provenance changed')
            require(api._completed_fact(records['evidence/import-' + name + '.original.d']) == api._completed_fact(row['depfile']),
                'F6 inherited original dependency bytes changed')
            row['object'] = records['objects/' + name + '.o']
            api._completed_fact(row['object'])
        row['donor_provenance'] = dict(kind='foundation-document-v2-native-theme-object-provenance-v1',
            f6_root_acceptance=value['root_acceptance'], f6_object=records['objects/' + name + '.o'],
            predecessor=row.get('donor_provenance'), compile_origin='f6-compiled' if name in fresh else 'f6-imported')
        imported.append(row)
    require(len(imported) == 50, 'requires50 actual F6 imports')
    archives = []
    for row in legacy['archives']:
        name = row['name']; fact = records['archives/lib' + name + '.a']; report = records['evidence/archive-' + name + '.json']
        require(fact['sha256'] == row['archive']['sha256'] and fact['bytes'] == row['archive']['bytes']
            and api._completed_fact(report) == api._completed_fact(row['report']), 'F6 unchanged archive differs')
        api._completed_fact(fact)
        archives.append(dict(name=name, archive=fact, report=report))
    return dict(reference=dict(ref), objects=imported, archives=archives,
        original_bindings=legacy['original_bindings'], dependency_sidecar=legacy['dependency_sidecar'],
        additional_input_directories=sorted(set(legacy.get('additional_input_directories', []) + [str(v) for v in bindings.values()])),
        metadata_directories=sorted(set(legacy['metadata_directories'] + [str(Path(v['path']).parent) for v in value.values() if type(v) is dict and 'path' in v])))

def producer_inputs(api):
    return {name:api.digest(api.ROOT / name) for name in
        (*api.required_helpers('editor'), api.SUCCESSFUL_HELPER, HELPER)}

def _helper_admitted(base, api):
    for name in (api.SUCCESSFUL_HELPER, HELPER):
        require(base.inventories['sources'].get(name) == api.digest(api.ROOT / name), 'retain exact Theme producer helper: ' + name)

def _supplement_inputs(donor, supplement):
    result=deepcopy(donor)
    parents={str(Path(supplement['reference']['path']).parent),str(Path(supplement['probe']['path']).parent),
             supplement['command']['cwd']}
    result['metadata_directories']=sorted(set(result['metadata_directories'])|parents)
    return result

def make_plan(selection, output, donor_ref, supplement_ref, api):
    base = api.inspect_inputs(selection)
    _helper_admitted(base, api)
    supplement = admit_supplement(supplement_ref, base, api)
    donor = _supplement_inputs(api._successful_module().native_theme_admission(donor_ref, base, api), supplement)
    inspected = effective_inspection(base, supplement, api)
    destination = api.engine_sdk.new_destination(output, (*base.roots.values(),
        *api._completed_input_directories(donor), Path(supplement_ref['path']).parent, Path(supplement['probe']['path']).parent))
    plan = dict(schema_version=1, kind=PLAN_KIND, scope=api.SCOPE, selection=inspected.selection,
        profile_sha256=api.digest(api.ROOT / api.profile_path('editor')), producer_inputs=producer_inputs(api),
        reuse=inspected.proof, projection=base.projection, production_eligible=False,
        successful_donor=donor, theme_supplement=dict(supplement_ref))
    with api.engine_sdk._OwnedTree(destination.parent, '.engine-theme-plan-') as staged:
        (staged.path / 'plan.json').write_bytes(api.encoded(plan))
        staged.publish(destination)
    return dict(scope=api.SCOPE, plan=str(destination / 'plan.json'),
        plan_sha256=api.digest(destination / 'plan.json'), production_eligible=False)

def verify_plan(plan, api):
    api.fields(plan, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256', 'producer_inputs',
        'reuse', 'projection', 'production_eligible', 'successful_donor', 'theme_supplement'), 'Theme plan')
    require(integer(plan['schema_version'], 1) and plan['kind'] == PLAN_KIND
        and plan['scope'] == api.SCOPE and plan['production_eligible'] is False
        and plan['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor'))
        and plan['producer_inputs'] == producer_inputs(api), 'plan producer/profile identity changed')
    base = api.inspect_inputs(plan['selection'])
    _helper_admitted(base, api)
    supplement = admit_supplement(plan['theme_supplement'], base, api)
    donor = _supplement_inputs(api._successful_module().native_theme_admission(plan['successful_donor']['reference'], base, api), supplement)
    effective = effective_inspection(base, supplement, api)
    require(plan['reuse'] == effective.proof and plan['projection'] == base.projection
        and plan['successful_donor'] == donor, 'effective graph or donor changed')
    return plan, effective

def validate_compile_depfile(plan, inspected, output, api):
    supplement = admit_supplement(plan['theme_supplement'], api.Inspection(inspected.selection,
        inspected.recipe, inspected.projection, dict(inspected.proof, objects=[o for o in inspected.proof['objects'] if o['id'] != THEME]),
        inspected.roots, inspected.inventories, api.profile('editor')), api)
    command = dict(supplement['command'], cwd=str(output), target=str(Path(output)/('objects/'+THEME+'.o')))
    raw = api.checked_read(Path(output)/('objects/'+THEME+'.o.d'))
    require(_dependency_refs(raw, command, inspected, api) == supplement['dependencies'], 'actual Theme compile closure differs from sealed probe')

def _record_import_receipts(result, plan, output, commands, api):
    selected = [row['id'] for row in plan['reuse']['objects']]
    rows = result.get('objects')
    if (type(rows) is not list or any(type(row) is not dict for row in rows)
            or [row.get('id') for row in rows] != selected):
        raise ValueError('Resume receipt must contain the exact ordered selected object union')
    imported = {row['id']: row for row in plan['successful_donor']['objects']}
    imported_ids = [name for name in selected if name in imported]
    compiled_ids = [name for name in selected if name not in imported]
    if (set(commands['objects']) != set(compiled_ids) or set(commands['imports']) != set(imported_ids)
            or set(compiled_ids) & set(imported_ids) or len(selected) != 52):
        raise ValueError('Resume accounting does not preserve the exact disjoint selected union')
    result['kind'] = BUILD_KIND
    result['successful_donor'] = plan['successful_donor']['reference']
    result['accounting'] = {'selected': 52, 'imported': len(imported_ids), 'compiled': len(compiled_ids),
                            'imported_ids': imported_ids, 'compiled_ids': compiled_ids}
    for obj in result['objects']:
        obj['origin'] = 'imported' if obj['id'] in imported else 'compiled'
        if obj['id'] in imported:
            receipt = output / ('evidence/import-' + obj['id'] + '.json')
            value = api.checked_document(receipt)
            original = imported[obj['id']]
            if (value.get('kind') != 'foundation-document-v2-object-import-v1'
                    or value.get('production_eligible') is not False
                    or value.get('id') != obj['id'] or value.get('origin') != 'imported'
                    or value.get('compiler_invoked') is not False or value.get('hardlinked') is not False
                    or value.get('sha256') != obj['sha256'] or value.get('bytes') != obj['bytes']
                    or value.get('object') != original['object'] or value.get('original_depfile') != original['depfile']
                    or value.get('original_command_sha256') != original['command_sha256']
                    or value.get('original_argv') != original['original_argv']
                    or value.get('original_cwd') != original['original_cwd']
                    or value.get('ninja_record') != original['ninja_record']
                    or value.get('ninja_command') != original['ninja_command']
                    or value.get('command_script') != original['command_script']):
                raise ValueError('Resume imported receipt/readback differs')
            obj['import_receipt'] = {'path': str(receipt.relative_to(output)), 'sha256': api.digest(receipt)}


def build_receipt(result, plan, inspected, output, commands, api):
    require(plan.get('kind') == PLAN_KIND, 'receipt requires distinct Theme plan')
    _record_import_receipts(result, plan, output, commands, api)
    counts = result['accounting']; donor = plan['successful_donor']
    archives = [a['name'] for a in inspected.proof['archives']]
    require(counts['compiled'] == 2 and counts['imported'] == 50
        and set(counts['compiled_ids']) == set(FRESH)
        and [r['id'] for r in donor['objects']] == counts['imported_ids']
        and [r['name'] for r in donor['archives']] == archives
        and set(commands.get('archive_imports', {})) == set(archives), 'receipt partition differs')
    for row in donor['objects']:
        receipt = api.checked_document(Path(output)/('evidence/import-'+row['id']+'.json'))
        require(receipt.get('donor_provenance') == row['donor_provenance']
            and row['donor_provenance']['kind'] == 'foundation-document-v2-native-theme-object-provenance-v1',
            'import lost F6 compiler history')
    archive_imports = []
    for row in donor['archives']:
        name = row['name']; file = Path(output)/('evidence/import-archive-'+name+'.json')
        receipt = api.checked_document(file)
        target = api.ordinary(Path(output)/('archives/lib'+name+'.a'))
        require(receipt.get('kind') == 'foundation-document-v2-archive-import-v1'
            and receipt.get('archive') == row['archive'] and receipt.get('original_report') == row['report']
            and receipt.get('name') == name and receipt.get('origin') == 'imported'
            and receipt.get('destination') == str(target) and receipt.get('hardlinked') is False
            and receipt.get('archive_program_invoked') is False and receipt.get('production_eligible') is False
            and receipt.get('sha256') == api.digest(target) == row['archive']['sha256']
            and receipt.get('bytes') == target.stat().st_size == row['archive']['bytes']
            and target.stat().st_nlink == 1 and api._identity7(target.stat())[:2] != row['archive']['identity'][:2],
            'archive copy receipt differs')
        archive_imports.append(dict(name=name, receipt=str(file.relative_to(output)), sha256=api.digest(file)))
    expected = artifact_names([o['id'] for o in inspected.proof['objects']], archives)
    for name in expected:
        api.ordinary(Path(output)/name)
    validate_compile_depfile(plan, inspected, output, api)
    final_map(api.checked_read(Path(output)/'evidence/engine-link.map'), output)
    result['kind'] = BUILD_KIND
    result['expected_artifact_records'] = len(expected)
    result['theme_supplement'] = plan['theme_supplement']
    result['accounting'].update(archive_imported=5, archive_repacked=0, imported_archive_names=archives)
    result['archive_imports'] = archive_imports
