"""Explicit D2/D3 generated script/data operands and acyclic G2 consistency.

Pure JSON never issues native capabilities. Native lifecycle construction needs
the exact fixed controller's genuine registered factory/context; inert fixtures
use separate types and registries. No selected file or program is read at import.
"""
import copy
import hashlib
from pathlib import Path
import re
import sys
import types

KIND = 'foundation-native-engine-windows-generated-input-witness-v2'
RESULT_KIND = 'foundation-windows-dependency-with-probe-and-generated-inputs-v2'
MAX_BINDINGS = 4096
# ICU's maintained decimal C emitter can produce a ~152 MiB file from the
# selected packed-data metadata.  Keep the existing actual A member ceiling;
# the aggregate budget below, stage output cap and original deadline also apply.
MAX_FILE_BYTES = 256 * 1024**2
DEFAULT_FILE_BYTES = 32 * 1024**2
MAX_SNAPSHOT_BYTES = 32 * 1024**2
MAX_TOTAL_BYTES = 256 * 1024**2
_CORE_NAME = '_foundation_windows_h2d3_controller_core_v1'
_CORE = None
_NATIVE = {}
_FIXTURE = {}
_NATIVE_FILES = {}
_FIXTURE_FILES = {}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _core():
    return _owner()


def _identity_module():
    c = _core()
    path = Path(__file__).resolve().with_name('proof_h2.py')
    return c._load_verified_source(path,
        'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9',
        '_g3_exact_identity_c2257591754a7aa5')


def _metadata():
    return _core()._support_module('supplier_factory_contract_base')


def _inventory():
    c = _core()
    path = Path(__file__).resolve().with_name('inventory_contract.py')
    return c._load_verified_source(path,
        '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb',
        '_g3_inventory_document_83ff23d4356e454e')


def _fields(value, names, label):
    _core()._pure()._fields(value, names, label)


def _relative(value, workspace):
    if (type(value) is not str or not value or value.startswith('/')
            or ':' in value or '\\' in value or len(value) > 2048):
        raise ValueError('Portable generated output required')
    _core()._pure()._path(workspace + '/' + value)
    return value


def operand(command, path):
    """One finite literal operand from the independently fixed command."""
    _core()._pure()._path(path)
    argv = command.get('argv') if type(command) is dict else None
    if type(argv) is not list or not 1 <= len(argv) <= 512:
        raise ValueError('Finite registered literal argv required')
    program = command.get('program')
    cmake = (type(program) is dict and program.get('kind') == 'original'
        and program.get('role') == 'cmake')
    matches = []
    forms = {None: 'cmake-definition', 'FILEPATH': 'cmake-definition-filepath',
        'PATH': 'cmake-definition-path'}
    for index, argument in enumerate(argv[1:], 1):
        if type(argument) is not str:
            raise ValueError('Literal generated operand argv required')
        if argument == path:
            matches.append({'index': index, 'form': 'path', 'literal': argument})
        elif cmake:
            match = re.fullmatch(r'-D[A-Za-z_][A-Za-z0-9_]*(?::(FILEPATH|PATH))?=(.*)', argument)
            if match is not None and match.group(2) == path:
                matches.append({'index': index, 'form': forms[match.group(1)], 'literal': argument})
    if len(matches) != 1:
        raise ValueError('Exactly one fixed supported generated-file operand required')
    return matches[0]


def file_limit(declaration, commands):
    """One fixed ICU C-data edge uses the existing 256 MiB A ceiling."""
    special = {'producing_command_id': 'icu-render-data',
        'consumer_command_id': 'icu-configure', 'output': 'build/icu-data/icudata.c'}
    if declaration != special:
        return DEFAULT_FILE_BYTES
    by_id = {row['id']: row for row in commands}
    for identifier, stage, role in (('icu-render-data', 'generate', 'python'),
            ('icu-configure', 'configure', 'cmake')):
        row = by_id.get(identifier)
        if (type(row) is not dict or row.get('supplier') != 'icu'
                or row.get('stage') != stage or type(row.get('program')) is not dict
                or row['program'].get('kind') != 'original' or row['program'].get('role') != role):
            raise ValueError('Exact fixed ICU data emitter/consumer Source policy required')
    return MAX_FILE_BYTES


def declarations(value, commands, workspace):
    _core()._pure()._path(workspace)
    if type(value) is not list or len(value) > MAX_BINDINGS:
        raise ValueError('Finite fixed generated input declarations required')
    if type(commands) is not list or not 1 <= len(commands) <= 512:
        raise ValueError('Finite fixed registered command sequence required')
    ids, outputs, seen = {}, {}, set()
    for index, command in enumerate(commands):
        if (type(command) is not dict or type(command.get('id')) is not str
                or re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', command['id']) is None or command['id'] in ids):
            raise ValueError('Unique fixed command IDs required')
        ids[command['id']] = (index, command)
    for row in value:
        _fields(row, ('consumer_command_id', 'producing_command_id', 'output'), 'generated input')
        output = _relative(row['output'], workspace)
        if output.split('/', 1)[0].casefold() in ('metadata', 'logs', 'probe', 'recipes'):
            raise ValueError('Generated supplier output overlaps controller-owned namespace')
        producer, consumer = row['producing_command_id'], row['consumer_command_id']
        if producer not in ids or consumer not in ids or ids[producer][0] >= ids[consumer][0]:
            raise ValueError('Generated input needs a strictly earlier fixed producer')
        if (consumer, output.casefold()) in seen:
            raise ValueError('Generated input consumer/output alias')
        seen.add((consumer, output.casefold()))
        previous = outputs.setdefault(output.casefold(), (producer, output))
        if previous != (producer, output):
            raise ValueError('Retained generated outputs must have one exact producer/spelling')
        operand(ids[consumer][1], workspace + '/' + output)
    return copy.deepcopy(value)


def _snapshot(value, workspace):
    _fields(value, ('files', 'directories', 'bytes'), 'complete stage output snapshot')
    files, directories = value['files'], value['directories']
    if (type(files) is not dict or len(files) > 65536 or type(directories) is not list
            or len(directories) > 65536 or any(type(item) is not str for item in directories)
            or directories != sorted(set(directories))):
        raise ValueError('Finite complete stage output snapshot required')
    kinds, total = {}, 0
    for directory in directories:
        _relative(directory, workspace)
        if directory.casefold() in kinds:
            raise ValueError('Stage snapshot paths alias')
        kinds[directory.casefold()] = 'directory'
    for name, row in files.items():
        _relative(name, workspace)
        _fields(row, ('path', 'kind', 'bytes', 'sha256'), 'stage file snapshot')
        if row['path'] != name or row['kind'] != 'file' or name.casefold() in kinds:
            raise ValueError('Exact unaliased stage file path required')
        _core()._pure()._int(row['bytes'], 'stage file bytes', 0, 2**63 - 1)
        _core()._pure()._pin(row['sha256'])
        kinds[name.casefold()] = 'file'
        total += row['bytes']
    for name in kinds:
        parts = name.split('/')[:-1]
        if any(kinds.get('/'.join(parts[:i])) != 'directory' for i in range(1, len(parts) + 1)):
            raise ValueError('Complete snapshot parent directories required')
    _core()._equal(value['bytes'], total, 'complete snapshot byte sum')
    _metadata()._source_preflight(value)
    raw = _core()._inventory_encoded(value)
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError('Stage snapshot byte bound exceeded')
    return raw


def _snapshot_document(raw, pin, workspace):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_SNAPSHOT_BYTES:
        raise ValueError('Bounded original stage snapshot bytes required')
    # Structural pre-parser only; the existing inventory decoder owns JSON,
    # duplicate fields and Unicode. Stop depth/token amplification before loads.
    depth = nodes = 0
    quoted = escaped = scalar = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted, scalar = True, False
            nodes += 1
        elif byte in (91, 123):
            depth += 1
            nodes += 1
            scalar = False
        elif byte in (93, 125):
            depth -= 1
            scalar = False
        elif byte in (9, 10, 13, 32, 44, 58):
            scalar = False
        elif not scalar:
            scalar = True
            nodes += 1
        if depth > 32 or depth < 0 or nodes > 1000000:
            raise ValueError('Stage snapshot pre-parse depth/token bound exceeded')
    value = _inventory()._document(raw, pin, 'original stage output snapshot')
    if _snapshot(value, workspace) != raw:
        raise ValueError('Original canonical stage snapshot required')
    return value


def validate_witness(raw, pin, *, identity_raw, identity_pin, dependency_raw,
        dependency_pin, dependency_path, expected, generated_inputs, workspace_root,
        snapshots, outputs):
    """Pure complete H2/D2/G2 joins; never historical/native issuer authority."""
    c, w = _core(), _core()._pure()
    identity = _identity_module().validate_toolchain_identity(identity_raw, identity_pin)
    declaration = w._document(dependency_raw, dependency_pin)
    tag = (declaration.get('schema_version'), declaration.get('kind'))
    if tag == (2, 'foundation-native-engine-windows-dependencies-build-v2'):
        receipt = _identity_module().validate_dependency_receipt(
            dependency_raw, dependency_pin, expected, identity)
    elif tag == (3, 'foundation-native-engine-windows-dependencies-build-v3'):
        receipt = c._proof_module().validate_dependency_receipt(
            dependency_raw, dependency_pin, expected, identity)
    else:
        raise ValueError('Exact original D2 or D3 dependency artifact required')
    c._reference({'path': dependency_path, 'sha256': dependency_pin})
    fixed = declarations(generated_inputs, expected['commands'], workspace_root)
    value = w._document(raw, pin)
    _fields(value, ('schema_version', 'kind', 'target', 'toolchain_identity_sha256',
        'dependency_receipt', 'bindings', *w.FALSE_FACTS), 'G2 witness')
    c._equal(value['schema_version'], 2, 'G2 schema')
    c._equal(value['kind'], KIND, 'G2 kind')
    c._equal(value['target'], w.TARGET, 'G2 target')
    c._equal(value['toolchain_identity_sha256'], identity_pin, 'G2 H2 binding')
    c._equal(value['dependency_receipt'], {'path': dependency_path, 'sha256': dependency_pin}, 'G2 D2 binding')
    for name in w.FALSE_FACTS:
        if value[name] is not False:
            raise ValueError('G2 cannot claim ' + name)
    if type(value['bindings']) is not list or len(value['bindings']) != len(fixed):
        raise ValueError('Exact fixed generated bindings required')
    if type(snapshots) is not dict or type(outputs) is not dict:
        raise ValueError('Exact supplied original snapshot/output bytes required')
    commands = {row['id']: row for row in receipt['commands']}
    used_snapshots, used_outputs, decoded, total = set(), set(), {}, 0
    for row, declaration in zip(value['bindings'], fixed):
        _fields(row, ('producing_command_id', 'consumer_command_id', 'output',
            'producer_snapshot', 'consumer_launch_intent_sha256', 'consumer_operand'), 'G2 binding')
        for key in ('producing_command_id', 'consumer_command_id'):
            c._equal(row[key], declaration[key], 'G2 fixed ' + key)
        producer = commands[row['producing_command_id']]
        consumer = commands[row['consumer_command_id']]
        for field in ('output', 'producer_snapshot'):
            _fields(row[field], ('path', 'sha256', 'bytes'), 'G2 ' + field)
            c._reference({key: row[field][key] for key in ('path', 'sha256')})
            w._int(row[field]['bytes'], 'G2 original bytes', 0 if field == 'output' else 1,
                file_limit(declaration, expected['commands']) if field == 'output' else MAX_SNAPSHOT_BYTES)
        output, snapshot = row['output'], row['producer_snapshot']
        c._equal(output['path'], workspace_root + '/' + declaration['output'], 'G2 generated path')
        snapshot_path = workspace_root + '/metadata/stage-output/' + producer['id'] + '.json'
        c._equal(snapshot['path'], snapshot_path, 'G2 fixed snapshot path')
        c._equal(snapshot['sha256'], producer['output_subject_sha256'], 'original producer output subject')
        body = snapshots.get(snapshot['path'])
        if type(body) is not bytes or len(body) != snapshot['bytes']:
            raise ValueError('Original stage snapshot bytes missing/different')
        if snapshot['path'] not in decoded:
            total += len(body)
            if total > MAX_TOTAL_BYTES:
                raise ValueError('Aggregate G2 original bytes exceed bound')
            decoded[snapshot['path']] = _snapshot_document(body, snapshot['sha256'], workspace_root)
        original = decoded[snapshot['path']]['files'].get(declaration['output'])
        if original is None:
            raise ValueError('Generated output absent from original producer snapshot')
        c._equal({key: original[key] for key in ('sha256', 'bytes')},
            {key: output[key] for key in ('sha256', 'bytes')}, 'G2 original generated row')
        body = outputs.get(output['path'])
        if type(body) is not bytes or len(body) != output['bytes'] or _sha(body) != output['sha256']:
            raise ValueError('Original generated output bytes differ')
        if output['path'] not in used_outputs:
            total += len(body)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('Aggregate G2 original bytes exceed bound')
        fixed_command = next(item for item in expected['commands'] if item['id'] == consumer['id'])
        c._equal(row['consumer_operand'], operand(fixed_command, output['path']), 'fixed G2 operand')
        c._equal(row['consumer_operand'], operand(consumer, output['path']), 'actual G2 operand')
        c._equal(row['consumer_launch_intent_sha256'], consumer['job']['launch_intent_sha256'], 'G2 original consumer Job')
        used_snapshots.add(snapshot['path'])
        used_outputs.add(output['path'])
    if set(snapshots) != used_snapshots or set(outputs) != used_outputs:
        raise ValueError('G2 supplied original scope must be exact')
    return {'witness': copy.deepcopy(value), 'native_admitted': False}


class _NativeLifecycle:
    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the fixed genuine native factory creates G2 lifecycle')


class _FixtureLifecycle:
    def __new__(cls, *args, **kwargs):
        raise ValueError('Use the separate inert lifecycle')


class _NativeFile:
    def __new__(cls, *args, **kwargs):
        raise ValueError('Only an actual original closed producer issues a file')


class _FixtureFile:
    def __new__(cls, *args, **kwargs):
        raise ValueError('Use the separate inert producer')


def _lifecycle(context, fixed, *, native):
    c = _core()
    if native:
        if type(context) is not c._NativeContext or context not in c._NATIVE_CONTEXTS:
            raise ValueError('Actual native controller context required')
        factory = c._NATIVE_CONTEXTS[context].get('factory')
        if type(factory) is not c._Factory or factory not in c._NATIVE_FACTORIES:
            raise ValueError('Actual fixed native factory association required')
        policy = c._NATIVE_FACTORIES[factory]
        if policy.get('context') is not context:
            raise ValueError('Same original native factory/context required')
        c._equal(fixed, policy['generated_inputs'], 'original fixed generated declarations')
        c._equal(context.commands, policy['commands'], 'original fixed command registration')
        kind, registry = _NativeLifecycle, _NATIVE
    else:
        if type(context) is not c._FixtureContext or context not in c._FIXTURE_CONTEXTS:
            raise ValueError('Separate registered inert context required')
        kind, registry = _FixtureLifecycle, _FIXTURE
    context._check()
    if context.next_index or context.observations:
        raise ValueError('Generated lifecycle must precede supplier stages')
    fixed = declarations(fixed, context.commands, context.workspace.output)
    token = object.__new__(kind)
    registry[token] = {'context': context, 'fixed': fixed, 'files': {}, 'snapshots': {},
        'bindings': [], 'next_index': 0, 'revoked': False, 'total_bytes': 0}
    return token


def _for_native(context):
    c = _core()
    if type(context) is not c._NativeContext or context not in c._NATIVE_CONTEXTS:
        raise ValueError('Actual native controller context required')
    factory = c._NATIVE_CONTEXTS[context].get('factory')
    if type(factory) is not c._Factory or factory not in c._NATIVE_FACTORIES:
        raise ValueError('Actual original fixed factory required')
    return _lifecycle(context, c._NATIVE_FACTORIES[factory]['generated_inputs'], native=True)


def _for_fixture(context, fixed):
    return _lifecycle(context, fixed, native=False)


def _state(token):
    if type(token) is _NativeLifecycle:
        registry, files, kind = _NATIVE, _NATIVE_FILES, _NativeFile
    elif type(token) is _FixtureLifecycle:
        registry, files, kind = _FIXTURE, _FIXTURE_FILES, _FixtureFile
    else:
        raise ValueError('Exact generated lifecycle token required')
    state = registry.get(token)
    if state is None or state['revoked']:
        raise ValueError('Original unrevoked generated lifecycle required')
    context = state['context']
    context._check()
    if state['next_index'] != context.next_index:
        raise ValueError('Every supplier step must pass through generated lifecycle')
    return state, files, kind


def _closed(context, row):
    joined, log = row['joined'], row['log']
    if (not any(value is joined for value in context.workspace.joined)
            or not any(value is log for value in context.workspace.logs)
            or log._workspace is not context.workspace or log._state != 'sealed'):
        raise ValueError('Original same-Workspace closed producer/log changed')
    _core()._equal(joined.as_dict(), row['joined_facts'], 'original producer JoinedStage')


def step(token):
    state, files, kind = _state(token)
    context, c = state['context'], _core()
    try:
        if context.next_index >= len(context.commands):
            raise ValueError('Fixed generated lifecycle is complete')
        command = context.commands[context.next_index]
        pending = []
        for declaration in state['fixed']:
            if declaration['consumer_command_id'] != command['id']:
                continue
            file_token = state['files'].get((declaration['producing_command_id'], declaration['output']))
            row = files.get(file_token) if type(file_token) is kind else None
            if row is None or row['context'] is not context or row['workspace'] is not context.workspace:
                raise ValueError('Original earlier same-Workspace generated file capability required')
            _closed(context, row)
            c._equal(row['producer_id'], declaration['producing_command_id'], 'original generated producer')
            context._capture({key: row['output'][key] for key in ('path', 'sha256')},
                row['output']['bytes'], identity=row['physical'], minimum=0)
            _, execution = context.resolve(command)
            literal = operand(command, row['output']['path'])
            c._equal(execution['argv'], command['argv'], 'exact actual resolved consumer argv')
            c._equal(execution['argv'][literal['index']], literal['literal'], 'actual resolved generated operand')
            pending.append((declaration, row, literal))
        joined_before, logs_before = len(context.workspace.joined), len(context.workspace.logs)
        observation = context.step()
        state['next_index'] = context.next_index
        for declaration, row, literal in pending:
            state['bindings'].append({'producing_command_id': declaration['producing_command_id'],
                'consumer_command_id': declaration['consumer_command_id'], 'output': copy.deepcopy(row['output']),
                'producer_snapshot': copy.deepcopy(row['snapshot']), 'consumer_operand': literal,
                'consumer_launch_intent_sha256': observation['job']['launch_intent_sha256']})
        producing = [row for row in state['fixed'] if row['producing_command_id'] == command['id']]
        runtime_producing = (type(token) is _NativeLifecycle
            and command['id'] in c._runtime_producing_stage_ids(context))
        if producing or runtime_producing:
            if len(context.workspace.joined) != joined_before + 1 or len(context.workspace.logs) != logs_before + 1:
                raise ValueError('Exactly one actual closed producer/log required')
            joined, log = context.workspace.joined[-1], context.workspace.logs[-1]
            facts = joined.as_dict()
            c._equal(facts.get('tagged_command'), command, 'actual original producer declaration')
            execution = copy.deepcopy(command)
            execution['program'] = copy.deepcopy(observation['resolved_program']['program'])
            c._equal(facts.get('execution_command'), execution, 'actual original producer execution')
            if (facts.get('returncode') != 0 or facts.get('process_tree_closed') is not True
                    or facts.get('closure') != 'actual-bound-job-finish-and-close'):
                raise ValueError('Actual original producer must be closed successfully')
            snapshot = context.workspace.inspect_outputs()
            raw = _snapshot(snapshot, context.workspace.output)
            if _sha(raw) != observation['output_subject_sha256']:
                raise ValueError('Actual original producer snapshot changed')
            if state['total_bytes'] + len(raw) > MAX_TOTAL_BYTES:
                raise ValueError('Aggregate retained generated snapshots exceed bound')
            if not state['snapshots']:
                for directory in ('metadata', 'metadata/stage-output'):
                    if directory not in context.workspace.directories:
                        context.workspace.mkdir_new(directory)
            relative = 'metadata/stage-output/' + command['id'] + '.json'
            published = context.workspace.publish_bytes_new(relative, raw)
            snapshot_ref = {'path': context.workspace.output + '/' + relative,
                'sha256': published['sha256'], 'bytes': published['bytes']}
            if snapshot_ref['sha256'] != observation['output_subject_sha256'] or snapshot_ref['bytes'] != len(raw):
                raise ValueError('Owned original snapshot publication differs')
            context._capture({key: snapshot_ref[key] for key in ('path', 'sha256')}, len(raw))
            state['snapshots'][snapshot_ref['path']] = raw
            state['total_bytes'] += len(raw)
            for declaration in producing:
                key = (command['id'], declaration['output'])
                if key in state['files']:
                    continue
                actual = snapshot['files'].get(declaration['output'])
                if actual is None or actual['bytes'] > file_limit(declaration, context.commands):
                    raise ValueError('Actual bounded generated output absent')
                output = {'path': context.workspace.output + '/' + declaration['output'],
                    'sha256': actual['sha256'], 'bytes': actual['bytes']}
                if state['total_bytes'] + output['bytes'] > MAX_TOTAL_BYTES:
                    raise ValueError('Aggregate retained generated files exceed bound')
                capture = context._capture({key: output[key] for key in ('path', 'sha256')}, output['bytes'], minimum=0)
                state['total_bytes'] += output['bytes']
                if state['total_bytes'] > MAX_TOTAL_BYTES:
                    raise ValueError('Aggregate retained generated bytes exceed bound')
                file_token = object.__new__(kind)
                files[file_token] = {'context': context, 'workspace': context.workspace,
                    'producer_id': command['id'], 'joined': joined, 'joined_facts': facts, 'log': log,
                    'snapshot': snapshot_ref, 'output': output, 'physical': capture['physical'], 'raw': capture['raw']}
                _closed(context, files[file_token])
                state['files'][key] = file_token
        if runtime_producing:
            # The Source-owned runtime body has no D/G2/snapshot back-reference.
            # Seal it after the original producer snapshot, before any consumer.
            c._flush_runtime_documents(context)
        context._check()
        return observation
    except BaseException as error:
        state['revoked'] = True
        context._revoke(error)
        raise


def witness(token, *, identity_pin, dependency_reference):
    """Assemble post-D2 metadata; the native factory still validates all joins."""
    state, files, kind = _state(token)
    context, c, w = state['context'], _core(), _core()._pure()
    if context.next_index != len(context.commands):
        raise ValueError('All actual fixed stages must complete before G2')
    c._reference(dependency_reference)
    w._pin(identity_pin)
    by_key = {(row['consumer_command_id'], row['producing_command_id'],
        row['output']['path']): row for row in state['bindings']}
    bindings = []
    for declaration in state['fixed']:
        key = (declaration['consumer_command_id'], declaration['producing_command_id'],
            context.workspace.output + '/' + declaration['output'])
        if key not in by_key:
            raise ValueError('Complete original generated consumer bindings required')
        bindings.append(copy.deepcopy(by_key[key]))
    value = {'schema_version': 2, 'kind': KIND, 'target': copy.deepcopy(w.TARGET),
        'toolchain_identity_sha256': identity_pin, 'dependency_receipt': copy.deepcopy(dependency_reference),
        'bindings': bindings, **{name: False for name in w.FALSE_FACTS}}
    w.encoded(value)
    output_bytes = {}
    for file_token in state['files'].values():
        if type(file_token) is not kind or file_token not in files:
            raise ValueError('Original generated file token required')
        row = files[file_token]
        _closed(context, row)
        context._capture({key: row['output'][key] for key in ('path', 'sha256')},
            row['output']['bytes'], identity=row['physical'], minimum=0)
        output_bytes[row['output']['path']] = row['raw']
    used_snapshots = {row['producer_snapshot']['path'] for row in bindings}
    return {'value': value, 'snapshots': {path: copy.deepcopy(state['snapshots'][path])
            for path in sorted(used_snapshots)},
        'outputs': output_bytes, 'native_admitted': False}
