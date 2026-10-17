"""Synthetic native retained-group fixtures; no provider is built or loaded.

ELF/PE inputs contain header bytes only. All runtime checks are NOT RUN and the
only admitted fixture scope is parser-fixture-only. Neither this utility nor its
reports establish a real native engine, getter, ABI table or runtime result.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import struct

import appended_engine_document_contract as document
import appended_engine_manifest as manifest
import appended_engine_native_consumer as profile
import appended_engine_sdk as sdk
from dependency_archive import encoded

ROOT = Path(__file__).resolve().parents[2]
LINUX_X86_64 = {'system':'Linux','processor':'x86_64','triple':'x86_64-linux-gnu','pointer_bits':64}
LINUX_AARCH64 = {'system':'Linux','processor':'aarch64','triple':'aarch64-linux-gnu','pointer_bits':64}
WINDOWS_X86_64 = {'system':'Windows','processor':'x86_64','triple':'x86_64-w64-mingw32','pointer_bits':64}
GETTER = 'bib_engine_get_provider_v1'
PROOF_KIND = 'foundation-neutral-engine-provider-native-document-v2-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-native-document-v2-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-native-document-v2-runtime-evidence-v1'
RUNTIME_CHECKS = (
    'native-getter-inert-and-table','native-import-export-dependency-closure',
    'native-runtime-floor-and-private-runtime','native-offline-entry-resource-load',
    'native-service-result-and-ack','native-outside-engine-owner-pump',
    'native-opaque-raster-frame','native-failure-close-process-lifetime',
    'document-provider-minor-and-catalog','document-query3-owned-snapshot',
    'document-form6-native-readback','document-action-replay-and-ack7',
    'document-navigation-and-stale-lease','document-outer-unknown-terminal-no-replay',
)
BOOTSTRAP_CHECKS = ('getter_before_start','table_checked_before_start',
    'no_host_callbacks_during_getter','one_process_start','outside_engine_owner_pump',
    'process_lifetime_no_unload')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def elf_header(processor):
    """A parser header, deliberately containing no executable program."""
    machine = {'x86_64':62,'aarch64':183}[processor]
    raw = bytearray(64)
    raw[:16] = b'\x7fELF\x02\x01\x01'+b'\0'*9
    struct.pack_into('<HHIQQQIHHHHHH',raw,16,3,machine,1,0,0,0,0,64,56,0,64,0,0)
    return bytes(raw)


def pe_header():
    """A DOS/PE32+ DLL parser header with no sections or executable code."""
    raw = bytearray(512)
    raw[:2] = b'MZ'
    struct.pack_into('<I',raw,60,128)
    raw[128:132] = b'PE\0\0'
    struct.pack_into('<HHIIIHH',raw,132,0x8664,0,0,0,0,240,0x2022)
    optional = 152
    struct.pack_into('<H',raw,optional,0x20B)
    struct.pack_into('<Q',raw,optional+24,0x180000000)
    struct.pack_into('<II',raw,optional+32,4096,512)
    struct.pack_into('<HH',raw,optional+40,10,0)
    struct.pack_into('<II',raw,optional+56,4096,512)
    struct.pack_into('<HH',raw,optional+68,3,0x8160)
    struct.pack_into('<I',raw,optional+108,16)
    return bytes(raw)


def _directories(paths):
    found = set()
    for path in paths:
        parent = Path(path).parent
        while parent != Path('.'):
            found.add(parent.as_posix())
            parent = parent.parent
    return sorted(found)


def _write_tree(root, files, modes):
    root.mkdir(mode=0o755)
    for directory in _directories(files):
        destination = root/directory
        destination.mkdir(mode=0o755,parents=True,exist_ok=True)
        destination.chmod(0o755)
    for name, raw in files.items():
        with (root/name).open('xb') as stream:
            stream.write(raw)
        (root/name).chmod(modes[name])


def default_limits():
    return {'size':48,'maximum_command_bytes':65536,'maximum_query_bytes':65536,
        'maximum_reply_bytes':1048576,'maximum_service_message_bytes':1048576,
        'maximum_retired_documents':8,'maximum_inflight_resources':64,'reserved':0,
        'maximum_resource_response_bytes':67108864,'maximum_retained_resource_bytes':134217728}


def _native_floor(target):
    windows = target['system'] == 'Windows'
    return {'system':target['system'],'minimum_os':'10.0' if windows else 'Debian 12',
        'GLIBC':None if windows else '2.36','GLIBCXX':None,'CXXABI':None,'GCC':None,
        'CRT':'ucrt' if windows else None,
        'loader_api':'LoadLibraryExW-DLL_LOAD_DIR-SYSTEM32' if windows else 'dlopen-RTLD_NOW-RTLD_LOCAL'}


def build_group(temp_root, *, target=None, scope='parser-fixture-only', mutate=None,
                with_dependency=False, actions_profile=None):
    """Build one self-consistent Stage-A group using only synthetic parser data.

    ``mutate(state)`` runs before hashes are sealed. It may change closed-schema
    fields for refusal tests; semantically invalid Stage-A records may fail in
    the unchanged Stage-A exporter itself. No mutation is executed as code.
    """
    if scope != 'parser-fixture-only':
        raise ValueError('Synthetic native fixture cannot claim actual runtime scope')
    actions = None
    if actions_profile is not None:
        import appended_engine_native_actions_contract as actions
        actions.actions_selector(actions_profile)
    target = copy.deepcopy(LINUX_X86_64 if target is None else target)
    profile.native_target(target)
    root = Path(temp_root).resolve()
    if not root.is_dir():
        raise ValueError('Fixture parent must already be an owned directory')
    windows = target['system'] == 'Windows'
    entry = 'bin/fixture-engine.dll' if windows else 'lib/fixture-engine.so'
    binary_bytes = pe_header() if windows else elf_header(target['processor'])
    assets = {entry:binary_bytes,'share/parser-fixture.dat':b'Unexecuted native parser fixture data.\n'}
    asset_records = {path:{'role':'provider' if path == entry else 'data',
        'sha256':sha(raw),'bytes':len(raw),'mode':0o644} for path,raw in assets.items()}
    if windows:
        assets['lib/fixture-engine.lib'] = b'!<arch>\nsynthetic import-library parser data only\n'
        raw = assets['lib/fixture-engine.lib']
        asset_records['lib/fixture-engine.lib'] = {'role':'import-library','sha256':sha(raw),'bytes':len(raw),'mode':0o644}
    interface_paths = actions.INTERFACE_PATHS if actions else document.INTERFACE_PATHS
    interface_sources = {path:ROOT/path for path in interface_paths.values()}
    if actions:
        # Exact retained canonical source leaves; these are fixture data, never
        # a search for an SDK or an executable native provider.
        interface_sources[interface_paths['physical_catalog']] = ROOT / 'recipes/webkitwasm-document-v2/overlays/physical/foundation/abi/engine/physical-v1/catalog.json'
        interface_sources[interface_paths['document_schema']] = ROOT / 'recipes/webkitwasm-document-v2/source/foundation/abi/engine/document-v2/schema-definition.json'
    interfaces = {path:source.read_bytes() for path,source in interface_sources.items()}
    refs = {role:{'path':path,'sha256':sha(interfaces[path])} for role,path in interface_paths.items()}
    helpers = tuple(manifest.HELPERS) + (('tools/appended_engine_native_actions_contract.py',
        'tools/appended_engine_document_contract.py','tools/appended_engine_editor_contract.py') if actions else ())
    source_bytes = {path:(ROOT/path).read_bytes() for path in helpers}
    source_bytes.update(interfaces)
    source_bytes.update({'upstream/wrapper.tar':b'SYNTHETIC source supplier placeholder, never compiled.\n',
        'upstream/engine.tar':b'SYNTHETIC engine source placeholder, never compiled.\n',
        'src/parser-only.cpp':b'// Parser fixture only; no native provider implementation.\n',
        'LICENSE':b'Parser fixture data dedicated to the public domain under CC0.\n'})
    inputs = {path:{'sha256':sha(raw),'role':'helper' if path in helpers else
        'interface' if path in interfaces else 'license' if path == 'LICENSE' else 'source',
        'mode':0o644} for path,raw in source_bytes.items()}
    toolchain = {'cxx_standard':23,'identity_sha256':sha(b'synthetic private native toolchain, never executed'),
        'runtime_policy':'private-native','paired_sdk_sha256':None,
        'target_baseline':'Windows 10 UCRT' if windows else 'Debian 12 glibc 2.36'}
    options = {'script_enabled':True,'rendering':'cpu','thread_model':'native'}
    provider = {'format':'native-shared','binding':'c-abi','abi_major':1,'abi_minor':1,
        'header':document.INTERFACE_PATHS['base_header'],'header_sha256':document.BASE_HEADER_SHA256}
    recipe = {'schema_version':1,'kind':'foundation-appended-engine-recipe','producer_version':1,
        'target':copy.deepcopy(target),'toolchain':copy.deepcopy(toolchain),'options':copy.deepcopy(options),
        'provider':provider,'suppliers':{'wrapper':{'repository':'https://example.invalid/parser-wrapper',
            'commit':'1'*40,'archive':'upstream/wrapper.tar'},
            'engine':{'repository':'https://example.invalid/parser-engine','commit':'2'*40,'archive':'upstream/engine.tar'}},
        'inputs':inputs,'patches':[],'licenses':['LICENSE']}
    placeholder = sha(b'unsealed parser fixture identity')
    source_manifest = {'schema_version':1,'kind':'foundation-appended-engine-sources','producer_version':1,
        'recipe_id':placeholder,'files':{path:sha(raw) for path,raw in source_bytes.items()},
        'directories':_directories([*source_bytes,'recipe.json']),
        'modes':{**{path:0o644 for path in source_bytes},'recipe.json':0o644,
            **{path:0o755 for path in _directories([*source_bytes,'recipe.json'])}}}
    source_manifest['files']['recipe.json'] = placeholder
    provider_contract = (actions.provider_contract(kernel_target=target, actions_profile=actions_profile) if actions else
        profile.provider_contract(kernel_target=target,document_profile='pixel'))
    limits = default_limits()
    if actions:
        limits.update(maximum_command_bytes=1048576, maximum_query_bytes=236, maximum_reply_bytes=1048576)
    build = {'schema_version':1,'kind':actions.BUILD_KIND if actions else BUILD_KIND,'target':copy.deepcopy(target),
        'toolchain':copy.deepcopy(toolchain),'options':copy.deepcopy(options),
        'source_recipe_sha256':placeholder,'source_inputs_sha256':placeholder,
        'contract_header_sha256':actions.CONTRACT_SHA256 if actions else document.CONTRACT_SHA256,'binding':'private-native',
        'configuration':actions.expected_configuration(actions_profile=actions_profile) if actions else
            profile.expected_configuration(document_profile='pixel'),'capabilities':'4083' if actions else '1795',
        'provider_contract':copy.deepcopy(provider_contract),'provider_limits':copy.deepcopy(limits)}
    engine_profile = (actions.expected_engine_profile(actions_profile=actions_profile,build_sha256=placeholder,
        source_recipe_sha256=placeholder,kernel_target=target) if actions else
        profile.expected_engine_profile(document_profile='pixel',build_sha256=placeholder,
            source_recipe_sha256=placeholder,kernel_target=target))
    audit_path = 'reports/native-parser-audit.json'
    reports = {audit_path:encoded({'schema_version':1,'kind':'native-parser-fixture-audit-v1',
        'executed':False,'scope':'parser-fixture-only','notice':'Synthetic header/table metadata; no native engine was loaded.'})}
    binaries = {entry:{'format':'pe32plus' if windows else 'elf64-le','machine':target['processor'],
        'pointer_bits':64,'exports':[GETTER],'imports':[],'needed':[],
        'soname':None if windows else Path(entry).name,'runpath':[]}}
    dependencies = []
    if with_dependency:
        dependency = 'bin/fixture-private-runtime.dll' if windows else 'lib/fixture-private-runtime.so'
        assets[dependency] = binary_bytes
        asset_records[dependency] = {'role':'dependency','sha256':sha(binary_bytes),'bytes':len(binary_bytes),'mode':0o644}
        library = Path(dependency).name
        binaries[entry]['needed'].append(library)
        binaries[dependency] = {'format':'pe32plus' if windows else 'elf64-le','machine':target['processor'],
            'pointer_bits':64,'exports':[],'imports':[],'needed':[],
            'soname':None if windows else library,'runpath':[]}
        dependencies.append({'library':library,'kind':'retained','path':dependency,'sha256':sha(binary_bytes)})
    native_facts = {'binaries':binaries,'dependencies':dependencies,'runtime_floor':_native_floor(target),
        'private_runtime':{'policy':'private-native','unique_dependencies':True,'ambient_search':False,
            'loader_resolution':'not-run','conflicting_preload':'not-run'},
        'evidence':[{'path':audit_path,'sha256':sha(reports[audit_path])}]}
    environment = {'system':target['system'],'processor':target['processor'],'os_version':'synthetic-fixture',
        'loader':'LoadLibraryExW' if windows else 'dlopen',
        'loader_flags':sorted(['LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR','LOAD_LIBRARY_SEARCH_SYSTEM32'] if windows else ['RTLD_NOW','RTLD_LOCAL'])}
    runtime = {'schema_version':1,'kind':actions.RUNTIME_KIND if actions else RUNTIME_KIND,'scope':scope,'status':'incomplete',
        'recipe_id':placeholder,'provider_build_sha256':placeholder,'assets_sha256':placeholder,
        'target':copy.deepcopy(target),'toolchain_identity_sha256':toolchain['identity_sha256'],
        'engine_profile':copy.deepcopy(engine_profile),'environment':environment,
        'checks':{name:{'status':'not-run','evidence':[]} for name in (actions.RUNTIME_CHECKS if actions else RUNTIME_CHECKS)},
        'provider_observation':{'getter':GETTER,'requested_major':1,'maximum_minor':1,'status':0,
            'provider_contract':copy.deepcopy(provider_contract),'provider_limits':copy.deepcopy(limits)},
        'bootstrap':{'getter':GETTER,'requested_major':1,'maximum_minor':1,
            'checks':{name:'not-run' for name in BOOTSTRAP_CHECKS}},'native_facts_sha256':placeholder}
    proof = {'schema_version':1,'kind':actions.PROOF_KIND if actions else PROOF_KIND,'recipe_id':placeholder,'sources_sha256':placeholder,
        'provider_build':{'path':'evidence/native-build.json','sha256':placeholder},
        'engine_profile':engine_profile,'assets':asset_records,'native_facts':native_facts,
        'runtime_evidence':{'path':'evidence/native-runtime.json','sha256':placeholder},'interfaces':refs}
    binary_provider = {**copy.deepcopy(provider),'entry':entry,'assets':sorted(asset_records)}
    binary = {'schema_version':1,'kind':'foundation-appended-engine','producer_version':1,
        'recipe_id':placeholder,'sources_sha256':placeholder,'target':copy.deepcopy(target),
        'toolchain':copy.deepcopy(toolchain),'options':copy.deepcopy(options),'provider':binary_provider,
        'licenses':['LICENSE'],'build':{'origin':'parser-fixture-only; no native build','link_receipt':'evidence/native-proof.json'},
        'files':{},'directories':[],'modes':{}}
    state = {'recipe':recipe,'source_manifest':source_manifest,'build':build,'profile':engine_profile,
        'runtime':runtime,'proof':proof,'binary':binary,'source_bytes':source_bytes,
        'interfaces':interfaces,'assets':assets,'notices':{'LICENSE':source_bytes['LICENSE']},'reports':reports}
    if mutate is not None:
        mutate(state)
    recipe_raw = encoded(recipe)
    recipe_hash = sha(recipe_raw)
    source_manifest['recipe_id'] = recipe_hash
    source_manifest['files']['recipe.json'] = recipe_hash
    source_raw = encoded(source_manifest)
    source_hash = sha(source_raw)
    build['source_recipe_sha256'] = recipe_hash
    build['source_inputs_sha256'] = sha(encoded(recipe['inputs']))
    build_raw = encoded(build)
    build_hash = sha(build_raw)
    for selected in (proof['engine_profile'],runtime['engine_profile']):
        selected['build_sha256'] = build_hash
        selected['source_recipe_sha256'] = recipe_hash
    runtime.update(recipe_id=recipe_hash,provider_build_sha256=build_hash,
        assets_sha256=sha(encoded(proof['assets'])),native_facts_sha256=sha(encoded(proof['native_facts'])))
    runtime_raw = encoded(runtime)
    runtime_hash = sha(runtime_raw)
    proof.update(recipe_id=recipe_hash,sources_sha256=source_hash)
    proof['provider_build']['sha256'] = build_hash
    proof['runtime_evidence']['sha256'] = runtime_hash
    proof_raw = encoded(proof)
    proof_hash = sha(proof_raw)
    raw_binary = {**assets,**interfaces,**state['notices'],**reports,
        binary['build']['link_receipt']:proof_raw,proof['provider_build']['path']:build_raw,
        proof['runtime_evidence']['path']:runtime_raw}
    binary.update(recipe_id=recipe_hash,sources_sha256=source_hash,
        files={path:sha(raw) for path,raw in raw_binary.items()},directories=_directories(raw_binary),
        modes={**{path:0o644 for path in raw_binary},**{path:0o755 for path in _directories(raw_binary)}})
    binary_raw = encoded(binary)
    binary_root,source_root,group = root/'binary',root/'sources',root/'retained-group'
    _write_tree(source_root,{**source_bytes,'recipe.json':recipe_raw,'sources.json':source_raw},
        {**source_manifest['modes'],'sources.json':0o644})
    _write_tree(binary_root,{**raw_binary,'engine-sdk.json':binary_raw},{**binary['modes'],'engine-sdk.json':0o644})
    sdk.export_group(binary_root,source_root,group)
    pins = {'recipe':recipe_hash,'manifest':sha(binary_raw),'proof':proof_hash,'runtime':runtime_hash}
    evidence = {'binary_manifest':binary_raw,'source_manifest':source_raw,'recipe':recipe_raw,
        'proof':proof_raw,'provider_build':build_raw,'runtime':runtime_raw,
        'reports':copy.deepcopy(reports),'interfaces':copy.deepcopy(interfaces)}
    return {'group':group,'pins':pins,'target':copy.deepcopy(target),'evidence':evidence,
        'assets':copy.deepcopy(assets),'notices':copy.deepcopy(state['notices']),
        'documents':state,'binary_root':binary_root,'source_root':source_root}
