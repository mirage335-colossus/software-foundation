"""Owned source projection of the previously reviewed inert fake Fixture.
Only the selected fake import list expands to the exact49 successful lane.
No retained/source/SDK bodies are discovered or read by this fixture.
"""
import copy
import hashlib
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest import mock
# The parent test module supplies its unchanged encoded serializer.
PIN='1'*64
# The actual tested maintenance module is supplied by test_common_tail.
m = None
BASELINE_SOURCE = (
    'def child_environment(build_root, sdk_root, launcher, config, cache, host_tools):\n'
    '    require_clean()\n'
    "    keep = ('LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR')\n"
    '    result = {name: os.environ[name] for name in keep if name in os.environ}\n'
    '    result.update(EMSDK_PYTHON=str(launcher), EM_CONFIG=str(config), EM_CACHE=str(cache),\n'
    "        EM_FROZEN_CACHE='1', CCACHE_DISABLE='1', PYTHONDONTWRITEBYTECODE='1',\n"
    "        HOME=str(build_root / 'private/home'), TMPDIR=str(build_root / 'private/tmp'),\n"
    "        XDG_CACHE_HOME=str(build_root / 'private/user-cache'),\n"
    "        PATH=os.pathsep.join(sorted({str(Path(tool['path']).parent) for tool in host_tools.values()})))\n"
    '    return result\n'
    '\n'
    'def python_launcher(python, allowed_scripts, output):\n'
    '    """One owned real -BE interpreter entry, including recursive SDK shell calls.\n'
    '\n'
    '    SDK config normalizes EMSDK_PYTHON to sys.executable. Keep that value on this\n'
    "    launcher before SDK imports. The shell file_packager's -E cannot undo -B.\n"
    '    """\n'
    '    python = str(python)\n'
    "    if re.search(r'\\s', python) or '\\n' in str(output):\n"
    "        raise ValueError('Pinned Python launcher paths cannot contain whitespace')\n"
    "    source = '''#!{python} -BE\n"
    'import sys\n'
    'sys.dont_write_bytecode = True\n'
    'import os\n'
    'import runpy\n'
    'allowed = {allowed!r}\n'
    'launcher = {launcher!r}\n'
    'args = sys.argv[1:]\n'
    "while args and args[0] in ('-B', '-E', '-BE'):\n"
    '    args.pop(0)\n'
    "if not args or args[0].startswith('-') or args[0] not in allowed:\n"
    "    raise SystemExit('unsupported retained SDK Python invocation')\n"
    'script = args[0]\n'
    'sys.executable = launcher\n'
    "os.environ['EMSDK_PYTHON'] = launcher\n"
    'sys.argv = args\n'
    'sys.path[0] = os.path.dirname(script)\n'
    "runpy.run_path(script, run_name='__main__')\n"
    "'''.format(python=python, allowed=sorted(str(p) for p in allowed_scripts), launcher=str(output))\n"
    "    output.write_text(source, encoding='utf-8')\n"
    '    output.chmod(0o755)\n'
    '    return output\n'
    '\n'
    'def _expand(argument, roots, build_root):\n'
    "    bindings = dict(roots, build=build_root, generated=build_root / 'document-generated')\n"
    "    match = re.search(r'\\{([^{}]+)\\}', argument)\n"
    '    if match is None:\n'
    '        return argument\n'
    '    key, suffix = match[1], argument[match.end():]\n'
    "    if key not in bindings or re.search(r'[{}]', argument[:match.start()] + suffix):\n"
    "        raise ValueError('Unresolved retained command root')\n"
    '    if suffix:\n'
    "        if not suffix.startswith('/'):\n"
    "            raise ValueError('Retained root must precede a canonical relative path')\n"
    '        manifest.path_name(suffix[1:])\n'
    '    return argument[:match.start()] + str(bindings[key]) + suffix\n'
    '\n'
    'def _header_identity(inspection):\n'
    '    """A document successor of original physical identity, with explicit postimages.\n'
    '\n'
    '    The copy receipt proves all original identity classes. COPY-SET supplies the\n'
    '    chosen canonical path. Every changed canonical and alias path has its own\n'
    '    exact preimage -> inventoried projected postimage record.\n'
    '    """\n'
    "    reference = inspection.proof['header_identity']\n"
    '    if reference is None:\n'
    "        raise ValueError('Document maintenance requires complete original physical identity authority')\n"
    "    if reference.get('root') not in ('sources', 'reuse'):\n"
    "        raise ValueError('Header identity sidecar must be a retained source/reuse input')\n"
    '    resolve = lambda ref: ref_path(ref, inspection.roots, inspection.inventories)\n'
    '    sidecar_path = resolve(reference)\n'
    "    record = checked_document(sidecar_path, reference['sha256'])\n"
    "    fields(record, ('schema_version', 'kind', 'projection_sha256', 'evidence', 'classes',\n"
    "                    'postimages'), 'document header identity')\n"
    "    if (type(record['schema_version']) is not int or record['schema_version'] != 1\n"
    "            or record['kind'] != 'foundation-document-v2-header-identity-v1'\n"
    "            or record['projection_sha256'] != inspection.selection['projection_sha256']):\n"
    "        raise ValueError('Unknown document header identity contract')\n"
    "    fields(record['evidence'], ('discovery', 'copy_set', 'copy_receipt'), 'original physical identity authority')\n"
    "    authority_paths = {key: resolve(ref) for key, ref in record['evidence'].items()}\n"
    "    receipt = checked_document(authority_paths['copy_receipt'], record['evidence']['copy_receipt']['sha256'])\n"
    "    copy_set = checked_document(authority_paths['copy_set'], record['evidence']['copy_set']['sha256'])\n"
    "    if (type(receipt) is not dict or type(receipt.get('schema_version')) is not int\n"
    "            or receipt['schema_version'] != 1 or receipt.get('kind') != 'closed-unpublished-baseline-copy-v1'\n"
    "            or receipt.get('status') != 'closed-exact-readback-passed-unpublished'\n"
    "            or type(receipt.get('files')) is not dict or not receipt['files']\n"
    "            or type(copy_set) is not dict or copy_set.get('kind') != 'foundation-original-baseline-prospective-copy-set-v1'\n"
    "            or type(copy_set.get('entries')) is not list):\n"
    "        raise ValueError('Invalid original copy receipt or canonical-path authority')\n"
    '    entries = {}\n'
    "    for entry in copy_set['entries']:\n"
    "        name = manifest.path_name(entry['destination'])\n"
    '        if name in entries:\n'
    "            raise ValueError('Duplicate original copy destination')\n"
    '        entries[name] = entry\n'
    '    originals = {}\n'
    "    for name, item in receipt['files'].items():\n"
    '        manifest.path_name(name)\n'
    "        identity = item.get('source_identity') if type(item) is dict else None\n"
    "        if (type(item) is dict and 'source_identity' in item and identity is None\n"
    "                and name == 'provenance/original-command-ledger.json'):\n"
    "            sha(item.get('sha256'), 'generated original command ledger')\n"
    "            if type(item.get('bytes')) is not int or item['bytes'] < 1:\n"
    "                raise ValueError('Invalid generated original command ledger byte count')\n"
    '            continue  # Generated metadata has no original physical identity.\n'
    '        if (type(identity) is not list or len(identity) != 7\n'
    '                or any(type(part) is not int or part < 0 for part in identity)\n'
    '                or not stat.S_ISREG(identity[2]) or identity[3] < 1\n'
    "                or type(item.get('bytes')) is not int or item['bytes'] != identity[4]):\n"
    "            raise ValueError('Invalid original copied-file physical identity')\n"
    "        sha(item.get('sha256'), 'copied preimage')\n"
    '        originals.setdefault(tuple(identity), set()).add(name)\n'
    '    multiple = {identity: names for identity, names in originals.items() if len(names) > 1}\n'
    "    if type(record['postimages']) is not list or type(record['classes']) is not list:\n"
    "        raise ValueError('Expected explicit document physical classes and postimages')\n"
    '    postimages, dependencies = {}, [sidecar_path, *authority_paths.values()]\n'
    "    for item in record['postimages']:\n"
    "        fields(item, ('input', 'output'), 'physical path postimage')\n"
    "        before, after = item['input'], item['output']\n"
    "        if before.get('root') != 'reuse' or after.get('root') != 'sources':\n"
    "            raise ValueError('Postimages require an original copied path and selected source path')\n"
    '        dependencies.extend((resolve(before), resolve(after)))\n'
    "        _physical_postimage(before, after, receipt['files'], inspection.projection['files'])\n"
    "        if ('reuse', before['path']) in postimages:\n"
    "            raise ValueError('Duplicate original physical postimage path')\n"
    "        postimages['reuse', before['path']] = after\n"
    '    mappings, identities, seen, changed_groups = {}, set(), set(), []\n'
    "    for group in record['classes']:\n"
    "        fields(group, ('original_identity', 'canonical', 'aliases'), 'document physical class')\n"
    "        identity = tuple(group['original_identity'])\n"
    '        if identity in identities or identity not in multiple:\n'
    "            raise ValueError('Duplicate or unproven original physical class')\n"
    '        identities.add(identity)\n'
    "        canonical = group['canonical']\n"
    "        if type(group['aliases']) is not list or not group['aliases']:\n"
    "            raise ValueError('Original physical class requires explicit aliases')\n"
    "        refs = [canonical, *group['aliases']]\n"
    "        if len({ref.get('sha256') for ref in refs}) != 1:\n"
    "            raise ValueError('Original physical aliases must retain identical preimage bytes')\n"
    '        names = set()\n'
    '        for ref in refs:\n'
    '            path = resolve(ref); dependencies.append(path)\n'
    "            old = receipt['files'].get(ref['path'], {})\n"
    "            entry = entries.get(ref['path'], {})\n"
    "            if (ref['root'] != 'reuse' or ref['path'] in seen\n"
    "                    or old.get('source_identity') != list(identity) or old.get('sha256') != ref['sha256']\n"
    "                    or old.get('bytes') != path.stat().st_size\n"
    "                    or entry.get('expected_resolved_path') != canonical['path']\n"
    "                    or entry.get('sha256') != ref['sha256']):\n"
    "                raise ValueError('Physical class differs from exact original receipt/canonical authority')\n"
    "            seen.add(ref['path']); names.add(ref['path'])\n"
    '        if names != multiple[identity]:\n'
    "            raise ValueError('Physical class omits an original alias path')\n"
    "        selected = [postimages.get(('reuse', ref['path'])) for ref in refs]\n"
    '        if any(selected):\n'
    "            if not all(selected) or len({ref['sha256'] for ref in selected}) != 1:\n"
    "                raise ValueError('A changed physical class requires every canonical/alias postimage')\n"
    '            target = resolve(selected[0])\n'
    "            selected_paths = sorted({ref['path'] for ref in selected})\n"
    '            if len(selected_paths) > 1:\n'
    "                changed_groups.append({'canonical': selected[0]['path'], 'paths': selected_paths,\n"
    "                    'preimages': {ref['path']: inspection.projection['files'][ref['path']]['preimage_sha256']\n"
    '                                  for ref in selected},\n'
    "                    'postimages': {ref['path']: ref['sha256'] for ref in selected}})\n"
    '            for ref in refs:\n'
    '                mappings[str(resolve(ref))] = str(target)\n'
    '            for ref in selected[1:]:\n'
    '                alias_path = resolve(ref)\n'
    '                if alias_path != target:\n'
    '                    mappings[str(alias_path)] = str(target)\n'
    '        else:\n'
    '            target = resolve(canonical)\n'
    "            for ref in group['aliases']:\n"
    '                mappings[str(resolve(ref))] = str(target)\n'
    '    if identities != set(multiple):\n'
    "        raise ValueError('Physical identity record omits original alias classes')\n"
    "    if sorted(changed_groups, key=lambda item: item['canonical']) != sorted(\n"
    "            inspection.projection['physical_alias_groups'], key=lambda item: item['canonical']):\n"
    "        raise ValueError('Projected physical alias groups differ from original proven classes')\n"
    '    for key, ref in postimages.items():\n'
    '        if key[1] not in seen:\n'
    "            mappings[str(inspection.roots['reuse'] / key[1])] = str(resolve(ref))\n"
    '    source_aliases = _source_aliases(inspection)\n'
    "    for name, target in source_aliases['mappings'].items():\n"
    '        if name in mappings and mappings[name] != target:\n'
    "            raise ValueError('Declared source aliases conflict with historical physical identity')\n"
    '        mappings[name] = target\n'
    "    dependencies.extend(source_aliases['dependencies'])\n"
    "    overlay = {'version': 0, 'case-sensitive': True, 'use-external-names': False,\n"
    "        'overlay-relative': False, 'fallthrough': True,\n"
    "        'roots': [{'type': 'file', 'name': name, 'external-contents': target}\n"
    '                  for name, target in sorted(mappings.items())]}\n'
    "    return {'overlay': overlay, 'dependencies': dependencies, 'record_ref': reference,\n"
    "            'mapping_count': len(mappings), 'postimages': postimages,\n"
    "            'original_files': receipt['files']}\n"
    '\n'
    'def _graph(inspected, plan, plan_path, plan_hash, output):\n'
    '    p, roots = inspected.proof, inspected.roots\n'
    '    header_view = _header_identity(inspected)\n'
    '    overlay_arguments = []\n'
    '    if header_view is not None:\n'
    "        overlay = output / 'private/header-identity-vfs.json'\n"
    "        checked_read(overlay, hashlib.sha256(encoded(header_view['overlay'])).hexdigest())\n"
    "        overlay_arguments = ['-ivfsoverlay', str(overlay)]\n"
    '    resolve = lambda ref: str(ref_path(ref, roots, inspected.inventories))\n'
    "    tools = {key: str(_tool(value)) for key, value in p['host_tools'].items()}\n"
    "    sdk_tools = {key: str(roots['sdk'] / value['path']) for key, value in p['sdk_tools'].items()}\n"
    "    values = {'FOUNDATION_ENGINE_GRAPH_VERSION': ['1']}\n"
    '    def put(name, *arguments):\n'
    '        values[name] = [str(arg) for arg in arguments]\n'
    "    helper = roots['sources'] / SELF_PATH\n"
    "    internal = [tools['python'], '-BE', str(helper), '_step', '--plan', str(plan_path),\n"
    "                '--plan-sha256', plan_hash, '--build-root', str(output)]\n"
    "    header, provider = output / 'document-generated/BibCopiedDocumentMetadata.generated.h', output / 'document-generated/provider-build.json'\n"
    "    put('ENGINE_HEADER', header); put('ENGINE_PROVIDER_BUILD', provider)\n"
    "    metadata = p['metadata']\n"
    "    metadata_command = [tools['python'], '-BE', resolve(metadata['generator']),\n"
    "        '--source-root', roots['sources'], '--build-root', output,\n"
    "        '--recipe', roots['sources'] / 'recipe.json', '--build-plan', resolve(metadata['prelink_plan']),\n"
    "        '--contract-header', resolve(metadata['contract_header']),\n"
    "        '--document-profile', inspected.selection['document_profile'],\n"
    "        '--document-header', resolve(metadata['document_header']),\n"
    "        '--document-contract', resolve(metadata['document_contract']),\n"
    "        '--document-catalog', resolve(metadata['document_catalog']),\n"
    "        '--document-schema', resolve(metadata['document_schema']),\n"
    "        '--action-ack', resolve(metadata['action_ack']),\n"
    "        '--output-header', header, '--output-build', provider]\n"
    "    if inspected.selection['document_profile'] in ('physical', 'editor'):\n"
    "        metadata_command.extend(('--physical-catalog', resolve(metadata['physical_catalog'])))\n"
    "    if inspected.selection['document_profile'] == 'editor':\n"
    "        for key in ('editor_header', 'editor_contract', 'editor_catalog', 'editor_schema'):\n"
    "            metadata_command.extend(('--' + key.replace('_', '-'), resolve(metadata[key])))\n"
    "    put('ENGINE_METADATA_COMMAND', *metadata_command)\n"
    "    put('ENGINE_METADATA_DEPENDS', *(resolve(ref) for ref in metadata.values()),\n"
    "        *(roots['sources'] / name for name in required_helpers(inspected.selection['document_profile'])),\n"
    "        roots['sources'] / 'recipe.json')\n"
    '    object_outputs = {}\n'
    '    ids = []\n'
    "    for index, obj in enumerate(p['objects']):\n"
    "        key = 'o' + str(index)\n"
    '        ids.append(key)\n'
    "        target = output / ('objects/' + obj['id'] + '.o')\n"
    "        depfile = Path(str(target) + '.d')\n"
    "        object_outputs[obj['id']] = target\n"
    "        put('ENGINE_OBJECT_' + key + '_OUTPUT', target)\n"
    "        put('ENGINE_OBJECT_' + key + '_DEPFILE', depfile)\n"
    "        put('ENGINE_OBJECT_' + key + '_COMMAND', sdk_tools['emxx'],\n"
    '            *overlay_arguments,\n'
    "            *(_expand(arg, roots, output) for arg in obj['arguments']),\n"
    "            '-MD', '-MT', target, '-MF', depfile, '-o', target, '-c', resolve(obj['source']))\n"
    "        put('ENGINE_OBJECT_' + key + '_DEPENDS', resolve(obj['source']),\n"
    "            *(resolve(ref) for ref in obj['dependencies'] + obj['unified_members']),\n"
    "            *(header_view['dependencies'] if header_view else []),\n"
    '            *(overlay_arguments[1:] if overlay_arguments else []),\n'
    "            *_arguments(obj['arguments'], inspection=inspected))\n"
    "    put('ENGINE_OBJECT_IDS', *ids)\n"
    "    replacements = {(r['archive'], r['ordinal']): r['object_id'] for r in p['replacements']}\n"
    '    archive_outputs = {}\n'
    "    for archive in p['archives']:\n"
    "        name = archive['name']\n"
    "        target = output / ('archives/lib' + name + '.a')\n"
    '        archive_outputs[name] = target\n'
    '        members = [str(object_outputs[replacements[(name, i)]]) if (name, i) in replacements\n'
    "                   else resolve(member['input']) for i, member in enumerate(archive['members'])]\n"
    "        put('ENGINE_ARCHIVE_' + name + '_OUTPUT', target)\n"
    "        put('ENGINE_ARCHIVE_' + name + '_REPORT', output / ('evidence/archive-' + name + '.json'))\n"
    '        # Remove only our previous owned output before rebuilding: plain `ar cr`\n'
    '        # against a stale archive can retain members absent from the new recipe.\n'
    "        put('ENGINE_ARCHIVE_' + name + '_COMMAND', *internal,\n"
    "            '--action', 'repack', '--archive', name)\n"
    "        put('ENGINE_ARCHIVE_' + name + '_INDEX', sdk_tools['emranlib'], target)\n"
    "        put('ENGINE_ARCHIVE_' + name + '_READBACK', *internal, '--action', 'archive', '--archive', name)\n"
    "        put('ENGINE_ARCHIVE_' + name + '_DEPENDS', *members, str(helper), str(plan_path))\n"
    "    put('ENGINE_ARCHIVE_NAMES', *(a['name'] for a in p['archives']))\n"
    "    deps = {Path(ref['path']).name: resolve(ref) for ref in p['link']['dependencies']}\n"
    '    ordered = [str(archive_outputs[name]) if name in archive_outputs else deps[name]\n'
    "               for name in p['link']['archives']]\n"
    "    factory, wasm, linkmap = (output / 'artifacts/foundation-retained-engine.mjs',\n"
    "                             output / 'artifacts/foundation-retained-engine.wasm',\n"
    "                             output / 'evidence/engine-link.map')\n"
    "    put('ENGINE_FACTORY', factory); put('ENGINE_WASM', wasm); put('ENGINE_MAP', linkmap)\n"
    "    wrapper_outputs = [object_outputs[name] for name in inspected.profile['direct_objects']]\n"
    "    link_args = [_expand(arg, roots, output) for arg in p['link']['flags']]\n"
    "    link_args += ['--pre-js', resolve(p['link']['pre_js']), '--js-library', resolve(p['link']['host_library'])]\n"
    "    for data in p['link']['data']:\n"
    "        link_args += ['--embed-file', resolve(data['input']) + '@' + data['virtual_path']]\n"
    "    link_command = [sdk_tools['emxx'], *link_args, '-Wl,-Map=' + str(linkmap),\n"
    "                    *map(str, wrapper_outputs), '-o', str(factory), *ordered]\n"
    "    put('ENGINE_LINK_COMMAND', *link_command)\n"
    "    put('ENGINE_LINK_DEPENDS', *(resolve(ref) for ref in p['link']['dependencies']),\n"
    "        resolve(p['link']['pre_js']), resolve(p['link']['host_library']),\n"
    "        *(resolve(item['input']) for item in p['link']['data']), header, provider)\n"
    "    put('ENGINE_INSPECTION', output / 'evidence/artifact-inspection.json')\n"
    "    put('ENGINE_INSPECT_COMMAND', *internal, '--action', 'artifacts')\n"
    "    put('ENGINE_INSPECT_DEPENDS', helper, plan_path)\n"
    "    fragment = output / 'cmake/verified-plan.cmake'\n"
    "    fragment.write_text(''.join('set(' + name + ''.join('\\n  ' + _cmake_value(arg) for arg in args)\n"
    "                                + ')\\n' for name, args in values.items()), encoding='utf-8')\n"
    "    return tools, fragment, {'metadata': list(map(str, metadata_command)),\n"
    "        'objects': {obj['id']: values['ENGINE_OBJECT_o' + str(i) + '_COMMAND']\n"
    "                    for i, obj in enumerate(p['objects'])}, 'link': link_command}\n"
    '\n'
    'def make_plan(selection, output):\n'
    '    inspected = inspect_inputs(selection)\n'
    '    output = engine_sdk.new_destination(output, tuple(inspected.roots.values()))\n'
    "    selected = inspected.selection['document_profile']\n"
    "    plan = {'schema_version': 1, 'kind': PLAN_KIND, 'scope': SCOPE,\n"
    "            'selection': inspected.selection, 'profile_sha256': digest(ROOT / profile_path(selected)),\n"
    "            'producer_inputs': {name: digest(ROOT / name) for name in required_helpers(selected)},\n"
    "            'reuse': inspected.proof, 'projection': inspected.projection,\n"
    "            'production_eligible': False}\n"
    "    with engine_sdk._OwnedTree(output.parent, '.engine-plan-') as staged:\n"
    "        (staged.path / 'plan.json').write_bytes(encoded(plan))\n"
    '        staged.publish(output)\n'
    "    return {'scope': SCOPE, 'plan': str(output / 'plan.json'),\n"
    "            'plan_sha256': digest(output / 'plan.json'), 'production_eligible': False}\n"
)

BASELINE_SHA256 = '11fc0a266d2fc2d5359b612bfaafb06c64d3b161f3b8e59351234847a5c773a4'

def fact(path):
    path=Path(path); s=path.stat()
    return {'path':str(path),'bytes':s.st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode':stat.S_IMODE(s.st_mode),'identity':m._identity7(s)}

def write(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return fact(path)

def save(path,value):
    f=write(path,encoded(value));return {key:f[key] for key in ('path','sha256')}

class Fixture:
    def __init__(self,root, *, all_imports=False):
        self.root=root
        self.bindings={key:root/('old-'+key) for key in ('sources','sdk','reuse','build')}
        self.current={key:root/('new-'+key) for key in ('sources','sdk','reuse')}
        for p in (*self.bindings.values(),*self.current.values()):p.mkdir()
        config=m.profile('editor'); self.config=config
        selected=config['direct_objects']+config['engine_objects']
        eligible=m.COMPLETED_DIRECT|set(config['engine_objects'])
        names=[name for name in selected if name in eligible]
        self.names=[name for name in selected if name not in ('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp')]
        self.files={};self.inventories={key:{} for key in self.current}
        def retained(key,name,raw):
            old=write(self.bindings[key]/name,raw);self.files[old['path']]=old
            new=write(self.current[key]/name,raw);self.inventories[key][name]=new['sha256']
            return {'root':key,'path':name,'sha256':new['sha256']}
        header=retained('sources','units/header.h',b'// header\n')
        retained('sdk','upstream/lib/clang/24/include/stddef.h',b'// compiler builtin\n')
        retained('sdk','cache/sysroot/include/sys.h',b'// target system\n')
        source_refs={name:retained('sources','units/'+name,('void '+str(index)+';').encode())
                     for index,name in enumerate(selected)}
        # Inert original sanitizer source is local to this test, with a fixed pin.
        if hashlib.sha256(BASELINE_SOURCE.encode('utf-8')).hexdigest() != BASELINE_SHA256:
            raise RuntimeError('Fixed baseline source identity changed')
        helper=write(self.bindings['sources']/m.SELF_PATH,BASELINE_SOURCE.encode('utf-8'));self.files[helper['path']]=helper
        for key,name,raw in [('sources','recipe.json',b'{}'),('sources','sources.json',b'{"inert":1}'),
                             ('sdk','sdk.json',b'{"fake_sdk":true}')]:
            f=write(self.bindings[key]/name,raw);self.files[f['path']]=f
        tools={name:{'path':'/fixture/'+name,'sha256':PIN,
            'version':'1.12.1' if name=='ninja' else 'cmake version 3.31.6' if name=='cmake' else '3.13.0',
            'provenance':'inert fixture','recovery_limit':'no execution'} for name in ('python','cmake','ninja')}
        p={'objects':[{'id':name,'source':source_refs[name],'arguments':['-I{sources}/units','-fno-rtti',
                '-fno-exceptions' if name in config['engine_objects'] else '-fexceptions'],
            'dependencies':[header],'unified_members':[],'exceptions':name not in config['engine_objects']}
            for name in selected], 'host_tools':tools,
            'sdk_tools':{'emxx':{'path':'upstream/emscripten/em++','sha256':PIN}},
            'python_launch':{'fixture':True},'emscripten_config':{'LLVM_ROOT':'upstream/bin'},
            'private_cache':{'root':'cache','files':['cache/sysroot/include/sys.h']},
            'archives':[{'name':name,'members':[{'ordinal':i,'name':str(i)+'.o',
                'input':{'root':'reuse','path':'opaque/'+str(i)+'.o','sha256':PIN}}
                    for i in range(config['archive_members'][name])]} for name in config['archive_members']],
            'replacements':[{'archive':'WebCore','ordinal':i,'object_id':name}
                for i,name in enumerate(config['engine_objects'])]}
        self.proof=p
        self.selection={name:PIN for name in m.SELECTION_FIELDS}
        self.selection.update(document_profile='editor',profile=config['name'],
            sources=str(self.bindings['sources']),sdk=str(self.bindings['sdk']),reuse_root=str(self.bindings['reuse']),
            recipe_sha256=self.files[str(self.bindings['sources']/'recipe.json')]['sha256'],
            sources_sha256=self.files[str(self.bindings['sources']/'sources.json')]['sha256'],
            sdk_manifest_sha256=self.files[str(self.bindings['sdk']/'sdk.json')]['sha256'])
        self.old={'schema_version':1,'kind':m.PLAN_KIND,'scope':m.SCOPE,'selection':self.selection,
            'profile_sha256':hashlib.sha256((m.ROOT/m.profile_path('editor')).read_bytes()).hexdigest(),'producer_inputs':{m.SELF_PATH:helper['sha256']},'reuse':p,
            'projection':{},'production_eligible':False}
        records=root/'records';records.mkdir();(records/'root').mkdir()
        self.oldref=save(records/'plan.json',self.old);self.files[self.oldref['path']]=fact(Path(self.oldref['path']))
        self.commands={'metadata':['fixture'],'link':['fixture'],'objects':{}}
        self.rows=[];self.deps={};ninja=[]
        for obj in p['objects']:
            name=obj['id'];target=str(self.bindings['build']/('objects/'+name+'.o'))
            argv=[str(self.bindings['sdk']/'upstream/emscripten/em++'),'-ivfsoverlay',
                str(self.bindings['build']/'private/header-identity-vfs.json'),
                '-I'+str(self.bindings['sources']/'units'),'-fno-rtti',
                '-fno-exceptions' if name in config['engine_objects'] else '-fexceptions',
                '-MD','-MT',target,'-MF',target+'.d','-o',target,'-c',str(self.bindings['sources']/obj['source']['path'])]
            self.commands['objects'][name]=argv
            if name not in self.names:continue
            object_fact=write(Path(target),b'inert object: '+name.encode())
            inputs=[str(self.bindings['sources']/obj['source']['path']),str(self.bindings['sources']/'units/header.h')]
            dep=write(Path(target+'.d'),(target+': '+' '.join(inputs)+'\n').encode())
            for key,ref in [(inputs[0],obj['source']),(inputs[1],header)]:
                self.deps[key]={'fact':self.files[key],'input':ref,'origin':'retained'}
            cwd=str(self.bindings['build']/'cmake/build');source=str(self.bindings['sources']/Path(m.GRAPH_PATH).parent)
            outdep=cwd+'/CMakeFiles/d/'+hashlib.sha256((target+'.d').encode()).hexdigest()+'.d'
            transform=[tools['cmake']['path'],'-E','cmake_transform_depfile','Ninja','gccdepfile',source,source,
                       cwd,cwd,target+'.d',outdep]
            command='cd '+cwd+' && '+' '.join(argv)+' && '+' '.join(transform)
            n=['0','1',str(object_fact['identity'][5]),target,m._completed_ninja_hash(command)];ninja.append(n)
            self.rows.append({'id':name,'object':object_fact,'depfile':dep,
                'command_sha256':hashlib.sha256(encoded({'argv':argv,'cwd':cwd})).hexdigest(),
                'ninja_record':n,'ninja_command':command,'command_script':None,'dependency_keys':sorted(inputs)})
        self.commandsref=save(self.bindings['build']/'evidence/commands.json',self.commands)
        self.expectedref=save(records/'expected-commands.json',self.commands)
        log=write(self.bindings['build']/'cmake/build/.ninja_log',
                  ('# ninja log v6\n'+''.join('\t'.join(row)+'\n' for row in ninja)).encode())
        self.logref={key:log[key] for key in ('path','sha256')}
        self.view={'overlay':{'version':0,'case-sensitive':True,'use-external-names':False,
                    'overlay-relative':False,'fallthrough':True,'roots':[]},'original_files':{'header.h':{'sha256':PIN}}}
        private={}
        private['vfs']=write(self.bindings['build']/'private/header-identity-vfs.json',encoded(self.view['overlay']))
        configtext="LLVM_ROOT = "+repr(str(self.bindings['sdk']/'upstream/bin'))+'\n'
        configtext+='CACHE = '+repr(str(self.bindings['build']/'private/cache'))+'\nFROZEN_CACHE = True\n'
        private['configuration']=write(self.bindings['build']/'private/emscripten-config.py',configtext.encode())
        launcher=self.bindings['build']/'private/sdk-python'
        m.python_launcher(tools['python']['path'],[self.bindings['sdk']/name for name in config['python_entrypoints']],launcher)
        private['launcher']=fact(launcher)
        dirs={str(path):m._identity7(path.stat()) for key in ('sources','sdk','reuse')
              for path in [self.bindings[key],*self.bindings[key].rglob('*')] if path.is_dir()}
        self.freeze={'schema_version':1,'kind':'editor-rich-ui-input-freeze-v1','actual_plan_or_build':False,
            'roots':{key:str(path) for key,path in self.bindings.items() if key!='build'},'files':self.files,'directories':dirs}
        self.freezeref=save(records/'freeze.json',self.freeze)
        self.packet={'schema_version':1,'kind':'editor-rich-ui-build-launch-v1',
            'authorization_status':'root-reviewed-concrete-launch','freeze':self.freezeref['path'],
            'freeze_sha256':self.freezeref['sha256'],'plan':self.oldref['path'],'plan_sha256':self.oldref['sha256'],
            'selection':self.selection,'producer_inputs':self.old['producer_inputs'],'profile_sha256':self.old['profile_sha256'],
            'output':str(self.bindings['build']),'review':str(records/'result'),'policy':{'cold_fallback':False,
                'header_odr_waiver':False,'production_eligible':False,'runtime':False,'timestamp_seeding':False},
            'argv':['./build.sh','engine-maintenance','document-build','--plan',self.oldref['path'],
                '--plan-sha256',self.oldref['sha256'],'--output',str(self.bindings['build']),
                '--jobs','2','--timeout-seconds','60'],'cwd':'/fixture/checkout','environment_identity':{},
            'expected_commands':self.expectedref['path'],'expected_commands_sha256':self.expectedref['sha256']}
        self.packetref=save(records/'packet.json',self.packet)
        self.launch={'kind':'root-editor-incremental-build-launch-intent-v1','Root_owns_single_launch':True,
            'packet_sha256':self.packetref['sha256'],'freeze_sha256':self.freezeref['sha256'],
            'cold_fallback':False,'runtime':False,'cwd':'/fixture/checkout','environment_identity':{},
            'jobs':2,'inner_seconds':60,'argv':['/fixture/python','--packet-sha256',self.packetref['sha256']]}
        self.launchref=save(records/'root/launch.json',self.launch)
        self.handle={'kind':'root-observed-editor-incremental-build-handle-v1',
            'Root_owns_handle_and_output_claim':True,'launch_intent_sha256':self.launchref['sha256'],
            'packet_sha256':self.packetref['sha256'],'actual_session':17}
        self.handleref=save(records/'root/handle.json',self.handle)
        report={'primary_returncode':1,'descendants_outlived':False,'terminated':False,'error':None,'reaped':1}
        self.result={'closed':True,'writers_joined':True,'input_identity_namespace_postflight':'passed',
            'returncode':1,'supervisor_report':report}
        self.resultref=save(records/'result/RESULT.json',self.result)
        self.wrapper={'kind':'root-observed-closed-incremental-document-candidate-failure-v1',
            'status':'failed','actual_caller_exit_code':1,'actual_session':17,'writers_joined':True,
            'all_frozen_input_postflight':'passed','result':self.resultref,'supervisor_report':report}
        self.wrapperref=save(records/'root/FAILED.json',self.wrapper)
        current_selection=dict(self.selection,sources=str(self.current['sources']),sdk=str(self.current['sdk']),
                               reuse_root=str(self.current['reuse']))
        self.inspection=SimpleNamespace(profile=config,proof=p,roots=self.current,inventories=self.inventories,
                                        selection=current_selection)
        context={key:p[key] for key in ('host_tools','sdk_tools','python_launch','emscripten_config','private_cache')}
        context['sdk_manifest_sha256']=self.selection['sdk_manifest_sha256']
        with mock.patch.object(m,'_header_identity',return_value=self.view):
            header_context=m._completed_header_context(self.inspection,
                [item['input'] for item in self.deps.values()],[obj for obj in p['objects'] if obj['id'] in self.names])
        self.sidecar={'schema_version':1,'kind':m.COMPLETED_DEPS_KIND,
            'original_bindings':{key:str(path) for key,path in self.bindings.items()},
            'tool_context':context,'header_context':header_context,'dependencies':self.deps}
        self.sidecarref=save(records/'dependencies.json',self.sidecar)
        self.value={'schema_version':1,'kind':m.COMPLETED_KIND,'document_profile':'editor',
            'original_bindings':{key:str(path) for key,path in self.bindings.items()},'original_plan':self.oldref,
            'original_commands':self.commandsref,'root_failure':self.wrapperref,'candidate_result':self.resultref,
            'original_input_freeze':self.freezeref,'original_build_packet':self.packetref,'root_launch':self.launchref,
            'root_handle':self.handleref,'original_private':private,'ninja_log':self.logref,
            'dependency_sidecar':self.sidecarref,'objects':self.rows}
        self.reference=save(records/'completed.json',self.value)

    def admit(self):
        self.reference=save(self.root/'records/completed.json',self.value)
        with mock.patch.object(m,'_header_identity',return_value=self.view):
            return m._completed_work(self.reference,self.inspection)
