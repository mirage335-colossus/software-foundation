"""Narrow copied259 completed-object imports; never execution or a passed build.

The only admitted predecessor failed *after* all objects, archive readbacks and
the final link, at raw-export inspection. Imports retain the original compiler
paths and provenance. They do not claim compilation under a new recipe's paths.
All bytes read here must already belong to the selected reuse inventory.
"""
import ast
import hashlib
import os
from pathlib import Path
import re

KIND = 'foundation-copied259-completed-object-donor-v1'
STATUS = 'failed-static-export-inspection-after-link'
SHIM = 'BibEngineWasmShim.cpp'
EVIDENCE = ('plan', 'owner', 'commands', 'source_recipe', 'source_manifest',
            'sdk_manifest', 'helper', 'profile', 'vfs', 'config', 'launcher',
            'ninja_log', 'build_log', 'closure', 'postverify', 'freeze')


def _lexical(value):
    if (type(value) is not str or not value or '\x00' in value or '\n' in value
            or not Path(value).is_absolute() or '..' in Path(value).parts
            or str(Path(value)) != value):
        raise ValueError('Donor provenance requires a canonical lexical absolute path')
    return Path(value)


def _dependency(value):
    # Clang preserves literal ../ spellings from ordinary copied include trees.
    # Retain those exact strings in the original depfile/provenance, but compare
    # their lexical destination. Original plan admission forbids symlinked roots
    # and the complete copied namespaces/VFS view are checked again below.
    if type(value) is not str or not Path(value).is_absolute() or '\x00' in value or '\n' in value:
        raise ValueError('Donor dependencies require absolute copied-input paths')
    return _lexical(os.path.normpath(value))


def _functions(raw, names):
    tree = ast.parse(raw)
    found = {node.name: ast.dump(node, include_attributes=False)
             for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names}
    if set(found) != set(names):
        raise ValueError('Donor helper lacks the required original construction functions')
    return found


def depfile(raw):
    """Parse the single-target Clang -MD grammar, not arbitrary Make syntax."""
    text = raw.decode('utf-8', errors='strict').replace('\\\n', '')
    if '\x00' in text or '\r' in text:
        raise ValueError('Invalid donor dependency file')
    words, word, target, separator = [], [], None, False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '\\':
            index += 1
            if index == len(text) or text[index] not in (' ', '\t', '#', ':', '\\'):
                raise ValueError('Unsupported donor dependency escape')
            word.append(text[index])
        elif char == '$':
            index += 1
            if index == len(text) or text[index] != '$':
                raise ValueError('Make expansion is forbidden in donor dependencies')
            word.append('$')
        elif char == ':':
            if separator or words or not word:
                raise ValueError('Donor depfile requires exactly one target')
            target, word, separator = ''.join(word), [], True
        elif char in ' \t\n':
            if word:
                words.append(''.join(word)); word = []
        elif char == '#':
            raise ValueError('Unexpected donor dependency comment')
        else:
            word.append(char)
        index += 1
    if word:
        words.append(''.join(word))
    if not separator or not words or len(words) != len(set(words)):
        raise ValueError('Donor dependencies must be a nonempty unique single rule')
    _lexical(target)
    for name in words:
        _dependency(name)
    return target, words


def _symbolic(path, roots, build, cache_root):
    path = _dependency(path)
    try:
        relative = path.relative_to(build / 'private/cache').as_posix()
        return 'sdk', cache_root + '/' + relative
    except ValueError:
        pass
    if path == build or build in path.parents:
        raise ValueError('Donor object depends on generated/private build data')
    matches = [(key, path.relative_to(root).as_posix()) for key, root in roots.items()
               if path != root and root in path.parents]
    if len(matches) != 1:
        raise ValueError('Donor dependency escapes its complete retained namespaces')
    return matches[0]


def _namespace(inventory, prefix):
    prefix = prefix.rstrip('/')
    marker = prefix + '/' if prefix else ''
    files = {name: (pin, inventory['modes'].get(name))
             for name, pin in inventory['files'].items() if name.startswith(marker)}
    directories = [name for name in inventory['directories']
                   if name == prefix or name.startswith(marker)]
    return {'files': files, 'directories': directories}


def _search(arguments, source):
    parent = str(Path(source).parent)
    result = [('sources', '' if parent == '.' else parent)]
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == '-isystem':
            index += 1
            if index == len(arguments):
                raise ValueError('Missing donor include directory')
            operand = arguments[index]
        elif arg.startswith('-I'):
            operand = arg[2:]
        else:
            index += 1
            continue
        if operand != '{generated}':
            match = re.fullmatch(r'\{(sources|sdk|reuse)\}(?:/(.+))?', operand)
            if match is None:
                raise ValueError('Unknown donor include-search root')
            result.append((match[1], match[2] or ''))
        index += 1
    return list(dict.fromkeys(result))


def _closed(value, *, passed):
    if type(value) is not dict:
        raise ValueError('Invalid donor closure record')
    report = value.get('supervisor_report', {})
    if type(report) is not dict:
        raise ValueError('Invalid donor supervision record')
    code = 0 if passed else 1
    if (value.get('status') != ('passed' if passed else 'failed')
            or value.get('closed') is not True or value.get('returncode') != code
            or value.get('deadline_exceeded', False) is not False
            or any(key in value for key in ('error', 'cleanup_error', 'close_error'))
            or report.get('descendants_outlived') is not False or report.get('error') is not None
            or report.get('primary_returncode') != code or report.get('terminated') is not False
            or type(value.get('seconds')) not in (int, float) or value['seconds'] <= 0):
        raise ValueError('Donor original process/input verification did not close cleanly')


def validate(inspection, api):
    """Return admitted object imports after complete, passive context checks."""
    if 'completed_objects' not in inspection.proof:
        return None
    reference = inspection.proof['completed_objects']
    api.fields(reference, api.REFERENCE_FIELDS, 'completed-object donor reference')
    if reference.get('root') != 'reuse':
        raise ValueError('Completed-object donor must be a retained reuse input')
    resolve = lambda ref: api.ref_path(ref, inspection.roots, inspection.inventories)
    record_path = resolve(reference)
    record = api.checked_document(record_path)
    api.fields(record, ('schema_version', 'kind', 'scope', 'profile', 'evidence',
                        'environment_policy', 'objects'), 'completed-object donor')
    if (record['schema_version'] != 1 or record['kind'] != KIND or record['scope'] != api.SCOPE
            or record['profile'] != inspection.selection['profile']):
        raise ValueError('Unsupported completed-object donor scope')
    api.fields(record['evidence'], EVIDENCE, 'completed-object donor evidence')
    retained, originals, raw, documents = {}, {}, {}, {}
    for key, evidence in record['evidence'].items():
        api.fields(evidence, ('input', 'original_path'), 'donor original evidence')
        if evidence['input'].get('root') != 'reuse':
            raise ValueError('All donor evidence must be inventoried in reuse')
        originals[key] = _lexical(evidence['original_path'])
        retained[key] = resolve(evidence['input'])
        raw[key] = api.checked_read(retained[key])
        if key not in ('helper', 'config', 'launcher', 'ninja_log', 'build_log'):
            documents[key] = api.document(raw[key])
    old = documents['plan']
    api.fields(old, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256',
                    'producer_inputs', 'reuse', 'projection', 'production_eligible'), 'donor original plan')
    if (old['schema_version'] != 1 or old['kind'] != api.PLAN_KIND or old['scope'] != api.SCOPE
            or old['production_eligible'] is not False or 'completed_objects' in old['reuse']):
        raise ValueError('Only a single original copied259 predecessor is admitted')
    selection, proof = old['selection'], old['reuse']
    api.fields(selection, api.SELECTION_FIELDS, 'donor original selection')
    old_roots = {key: _lexical(selection[name]) for key, name in
                 (('sources', 'sources'), ('sdk', 'sdk'), ('reuse', 'reuse_root'))}
    if (len(set(old_roots.values())) != 3 or any(a in b.parents for a in old_roots.values()
            for b in old_roots.values() if a != b)):
        raise ValueError('Donor original roots overlap')
    owner = documents['owner']
    api.fields(owner, ('schema_version', 'plan_sha256', 'output', 'producer_sha256'), 'donor original owner')
    build = _lexical(owner['output'])
    if (owner['schema_version'] != 1 or owner['plan_sha256'] != hashlib.sha256(raw['plan']).hexdigest()
            or owner['producer_sha256'] != hashlib.sha256(raw['helper']).hexdigest()
            or originals['owner'] != build / 'maintenance-owner.json'
            or any(build == root or build in root.parents or root in build.parents for root in old_roots.values())):
        raise ValueError('Donor original plan/owner identity differs')
    expected_paths = {'commands': build / 'evidence/commands.json',
        'source_recipe': old_roots['sources'] / 'recipe.json',
        'source_manifest': old_roots['sources'] / 'sources.json',
        'sdk_manifest': old_roots['sdk'] / 'sdk.json',
        'helper': old_roots['sources'] / api.SELF_PATH,
        'profile': old_roots['sources'] / api.PROFILE_PATH,
        'vfs': build / 'private/header-identity-vfs.json',
        'config': build / 'private/emscripten-config.py',
        'launcher': build / 'private/sdk-python', 'ninja_log': build / 'cmake/build/.ninja_log',
        'build_log': build / 'logs/build.log'}
    if any(originals[key] != path for key, path in expected_paths.items()):
        raise ValueError('Donor original evidence paths differ from the selected scope')
    expected_pins = {'source_recipe': selection['recipe_sha256'],
        'source_manifest': selection['sources_sha256'], 'sdk_manifest': selection['sdk_manifest_sha256'],
        'helper': old['producer_inputs'].get(api.SELF_PATH), 'profile': old['profile_sha256']}
    if any(hashlib.sha256(raw[key]).hexdigest() != pin for key, pin in expected_pins.items()):
        raise ValueError('Donor original source/SDK/helper identity differs')
    api.manifest.source_contract(documents['source_manifest'], documents['source_recipe'], selection['recipe_sha256'])
    if (set(old['producer_inputs']) != set(api.REQUIRED_HELPERS) - {'tools/appended_engine_donor.py'}
            or old['producer_inputs'] != {name: documents['source_manifest']['files'].get(name)
                                  for name in old['producer_inputs']}
            or api.SELF_PATH not in old['producer_inputs']
            or selection['sdk_manifest_sha256'] != inspection.selection['sdk_manifest_sha256']
            or old_roots['sdk'] != inspection.roots['sdk']
            or documents['sdk_manifest']['files'] != inspection.inventories['sdk']):
        raise ValueError('Donor producer or complete paired SDK namespace differs')
    if (selection['profile'] != inspection.selection['profile']
            or proof['kind'] != api.REUSE_KIND or proof['profile'] != selection['profile']
            or proof['target'] != inspection.proof['target']
            or proof['paired_sdk_sha256'] != selection['sdk_manifest_sha256']):
        raise ValueError('Donor original target/profile identity differs')
    expected_profile = dict(inspection.profile)
    expected_profile['link_literals'] = [arg for arg in expected_profile['link_literals'] if arg != '-lexports.js']
    if documents['profile'] != expected_profile or proof['link']['flags'].count('-lexports.js') != 0:
        raise ValueError('Donor must precede only the exact raw-export preservation repair')
    new_link = dict(inspection.proof['link'])
    new_link['flags'] = [arg for arg in new_link['flags'] if arg != '-lexports.js']
    if (new_link != proof['link'] or proof['objects'] != inspection.proof['objects']
            or proof['target'] != inspection.proof['target']
            or proof['host_tools'] != inspection.proof['host_tools']
            or proof['sdk_tools'] != inspection.proof['sdk_tools']
            or proof['python_launch'] != inspection.proof['python_launch']
            or proof['private_cache'] != inspection.proof['private_cache']
            or proof['emscripten_config'] != inspection.proof['emscripten_config']
            or proof.get('header_identity') != inspection.proof.get('header_identity')
            or proof['archives'] != inspection.proof['archives']
            or proof['replacements'] != inspection.proof['replacements']):
        raise ValueError('Donor original compile/link context differs beyond the admitted repair')
    api.manifest.inventory_contract(dict(proof['inventory'], schema_version=1), 'reuse-proof.json')
    current_sources = api.checked_document(inspection.roots['sources'] / 'sources.json')
    inventories = {'sources': documents['source_manifest'], 'reuse': proof['inventory']}
    current = {'sources': current_sources, 'reuse': inspection.proof['inventory']}
    old_files = {'sources': documents['source_manifest']['files'], 'reuse': proof['inventory']['files'],
                 'sdk': documents['sdk_manifest']['files']}
    # The unaltered original sanitizer proves exclusion of command-affecting
    # ambient compiler variables. Concrete historical diagnostic locale values
    # were not captured; their absence must remain explicit in provenance.
    functions = ('child_environment', 'python_launcher', '_expand', '_supervise', '_header_identity')
    if _functions(raw['helper'], functions) != _functions(api.checked_read(api.ROOT / api.SELF_PATH), functions):
        raise ValueError('Donor environment/launcher/expansion/VFS construction changed')
    if record['environment_policy'] != 'original-sanitized-construction-values-unrecorded-v1':
        raise ValueError('State the exact limited donor environment provenance')
    config = ''.join(key + ' = ' + repr(str(old_roots['sdk'] / name)) + '\n'
                     for key, name in proof['emscripten_config'].items())
    config += 'CACHE = ' + repr(str(build / 'private/cache')) + '\nFROZEN_CACHE = True\n'
    if raw['config'] != config.encode():
        raise ValueError('Donor private compiler configuration differs')
    helper_tree = ast.parse(raw['helper'])
    launcher_fn = next(node for node in helper_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'python_launcher')
    source = next(node.value.func.value.value for node in launcher_fn.body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'source' for t in node.targets))
    expected_launcher = source.format(python=proof['host_tools']['python']['path'],
        allowed=sorted(str(old_roots['sdk'] / name) for name in documents['profile']['python_entrypoints']),
        launcher=str(build / 'private/sdk-python'))
    if raw['launcher'] != expected_launcher.encode():
        raise ValueError('Donor SDK Python launcher differs')
    view = api._header_identity(inspection)
    if view is None:
        raise ValueError('This donor scope requires its proven physical header view')
    def normalized(value, roots):
        if type(value) is list:
            return [normalized(item, roots) for item in value]
        if type(value) is dict:
            return {key: normalized(item, roots) for key, item in value.items()}
        if type(value) is str and value.startswith('/'):
            matches = [('{' + key + '}/' + str(Path(value).relative_to(root)))
                       for key, root in roots.items() if root in Path(value).parents]
            if len(matches) != 1:
                raise ValueError('Donor VFS names an unknown namespace')
            return matches[0]
        return value
    if normalized(documents['vfs'], old_roots) != normalized(view['overlay'], inspection.roots):
        raise ValueError('Donor VFS alias semantics differ')
    _closed(documents['closure'], passed=False)
    _closed(documents['postverify'], passed=True)
    freeze = documents['freeze']
    api.fields(freeze, ('schema_version', 'status', 'production_eligible', 'runtime_not_run',
                       'cause', 'utc', 'compiled_objects', 'archive_readbacks', 'files'), 'donor closed failure freeze')
    if (freeze['schema_version'] != 1 or freeze['status'] != STATUS or freeze['production_eligible'] is not False
            or freeze['runtime_not_run'] is not True or freeze['compiled_objects'] != 24
            or freeze['archive_readbacks'] != 5):
        raise ValueError('Donor must have completed the precise original object/link scope')
    frozen = {}
    for entry in freeze['files']:
        api.fields(entry, ('path', 'sha256', 'bytes', 'mode'), 'donor frozen file')
        name = str(_lexical(entry['path']))
        api.sha(entry['sha256'], 'donor frozen input')
        if name in frozen or type(entry['bytes']) is not int or entry['bytes'] < 0:
            raise ValueError('Invalid duplicate donor frozen file')
        frozen[name] = entry
    def frozen_bytes(original, content):
        entry = frozen.get(str(original))
        if entry is None or entry['sha256'] != hashlib.sha256(content).hexdigest() or entry['bytes'] != len(content):
            raise ValueError('Donor bytes differ from the original closed freeze')
    for key in ('commands', 'ninja_log', 'build_log', 'closure', 'postverify'):
        frozen_bytes(originals[key], raw[key])
    if (raw['build_log'].count(b'FAILED:') != 1
            or b'Actual factory lacks required copied exports' not in raw['build_log']
            or b'artifact-inspection.json' not in raw['build_log']):
        raise ValueError('Donor failed before the specific final raw-export inspection')
    commands = documents['commands']
    api.fields(commands, ('metadata', 'objects', 'link'), 'donor executed command ledger')
    if set(commands['objects']) != {obj['id'] for obj in proof['objects']}:
        raise ValueError('Donor command ledger omits an object')
    completed, all_completed = {}, set()
    log = raw['ninja_log'].decode('utf-8', errors='strict').splitlines()
    if not log or log.pop(0) not in ('# ninja log v5', '# ninja log v6'):
        raise ValueError('Unsupported donor completion ledger')
    for line in log:
        parts = line.split('\t')
        if (len(parts) != 5 or not all(re.fullmatch('[0-9]+', part) for part in parts[:3])
                or not re.fullmatch('[0-9a-f]+', parts[4]) or int(parts[1]) < int(parts[0])):
            raise ValueError('Invalid donor completed command')
        if parts[3] in all_completed:
            raise ValueError('Donor output has ambiguous repeated executions')
        all_completed.add(parts[3])
        if parts[3].startswith(str(build / 'objects') + '/'):
            if parts[3] in completed:
                raise ValueError('Donor object has ambiguous repeated executions')
            completed[parts[3]] = parts[4]
    if set(completed) != {str(build / ('objects/' + obj['id'] + '.o')) for obj in proof['objects']}:
        raise ValueError('Donor lacks the complete 24-object completion scope')
    expected_completed = set(completed) | {
        str(build / name) for name in ('copied-generated/BibCopiedMetadata.generated.h',
            'copied-generated/provider-build.json', 'artifacts/foundation-retained-engine.mjs',
            'artifacts/foundation-retained-engine.wasm', 'evidence/engine-link.map')}
    for archive in proof['archives']:
        expected_completed.update((str(build / ('archives/lib' + archive['name'] + '.a')),
                                   str(build / ('evidence/archive-' + archive['name'] + '.json'))))
    if all_completed != expected_completed:
        raise ValueError('Donor lacks the exact completed metadata/archive/link graph')
    objects = record['objects']
    expected = [obj['id'] for obj in proof['objects'] if obj['id'] != SHIM]
    if type(objects) is not list or [obj.get('id') for obj in objects] != expected:
        raise ValueError('Only the exact 23 metadata-independent objects may be imported')
    admitted, dependencies, checked_namespaces = {}, [record_path, *retained.values()], set()
    cache_files = set(proof['private_cache']['files'])
    for item in objects:
        api.fields(item, ('id', 'object', 'depfile'), 'completed donor object')
        obj = next(obj for obj in proof['objects'] if obj['id'] == item['id'])
        for ref in (item['object'], item['depfile']):
            if ref.get('root') != 'reuse':
                raise ValueError('Donor object/dependencies must be retained reuse inputs')
        object_path, dep_path = resolve(item['object']), resolve(item['depfile'])
        object_raw, dep_raw = api.checked_read(object_path), api.checked_read(dep_path)
        target = build / ('objects/' + item['id'] + '.o')
        frozen_bytes(target, object_raw); frozen_bytes(Path(str(target) + '.d'), dep_raw)
        dep_target, actual = depfile(dep_raw)
        if dep_target != str(target):
            raise ValueError('Donor dependency target differs from its original object')
        argv = [str(old_roots['sdk'] / proof['sdk_tools']['emxx']['path']),
            '-ivfsoverlay', str(build / 'private/header-identity-vfs.json'),
            *(api._expand(arg, old_roots, build) for arg in obj['arguments']),
            '-MD', '-MT', str(target), '-MF', str(target) + '.d', '-o', str(target),
            '-c', str(old_roots['sources'] / obj['source']['path'])]
        if commands['objects'][obj['id']] != argv:
            raise ValueError('Donor actual compiler argv differs from the pinned original recipe')
        for root, prefix in _search(obj['arguments'], obj['source']['path']):
            if root != 'sdk':
                # Literal ../ includes and availability probes may reach sibling
                # directories. Bind the entire copied top-level compiler tree,
                # as well as the exact search directory; newly shadowing files
                # are changes even when absent from the original positive .d.
                for scope in dict.fromkeys((prefix, prefix.split('/')[0])):
                    if (root, scope) not in checked_namespaces:
                        if _namespace(inventories[root], scope) != _namespace(current[root], scope):
                            raise ValueError('Donor complete include-search namespace changed')
                        checked_namespaces.add((root, scope))
        mapped = []
        for name in actual:
            root, relative = _symbolic(name, old_roots, build, proof['private_cache']['root'])
            old_pin = old_files[root].get(relative)
            if (build / 'private/cache' in _dependency(name).parents
                    and relative not in cache_files):
                raise ValueError('Donor dependency was not in the original frozen private cache seed')
            if old_pin is None or inspection.inventories[root].get(relative) != old_pin:
                raise ValueError('Donor observed source/header dependency changed or is missing')
            mapped.append((root, relative, old_pin))
        if ('sources', obj['source']['path'], obj['source']['sha256']) not in mapped:
            raise ValueError('Donor depfile omits its actual primary source')
        provenance = {'original_plan_sha256': owner['plan_sha256'],
            'original_build_root': str(build), 'original_argv': argv, 'original_cwd': str(build),
            'environment_policy': record['environment_policy'], 'input': item['object'],
            'depfile': item['depfile'], 'observed_inputs_sha256': hashlib.sha256(api.encoded(mapped)).hexdigest(),
            'record': reference, 'failed_predecessor_status': STATUS}
        admitted[item['id']] = {'object': object_path, 'depfile': dep_path, 'provenance': provenance}
        dependencies.extend((object_path, dep_path))
    return {'objects': admitted, 'dependencies': list(dict.fromkeys(dependencies)), 'record': reference}
