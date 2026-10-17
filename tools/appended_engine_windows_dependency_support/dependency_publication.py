"""Same-Core D3/W2/G2 publication, with no owner closure or result issuance.

Only an original registered native factory/context and its actual completed
compile, generated-input lifecycle and held-input capabilities reach this code.
Each publication is checked against the earliest complete stage-output baseline
plus explicit new leaves. No current snapshot silently replaces that baseline.
"""
import copy
import hashlib
import json
import sys
import types


RESULT_KIND = 'foundation-windows-dependency-with-probe-and-generated-inputs-v2'
MAX_INVENTORY = 32 * 1024**2
MAX_REFERENCE_BYTES = 256 * 1024**2
MAX_REFERENCES = 4096
_PUBLICATIONS = {}


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _inventory_bytes(value):
    # This is the canonical 32 MiB inventory domain, including ordinary maps;
    # H/D/W/G and the completed-result serializers keep their own 4 MiB cap.
    _owner()._support_module('supplier_factory_contract_base')._source_preflight(value)
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
        allow_nan=False) + '\n').encode('ascii')
    if len(raw) > MAX_INVENTORY:
        raise ValueError('Publication inventory metadata exceeds source bound')
    return raw


def _ref2(value):
    return {name: value[name] for name in ('path', 'sha256')}


def _body3(value, *, minimum=1):
    c = _owner()
    c._pure()._fields(value, ('path', 'sha256', 'bytes'), 'actual publication body')
    c._reference(_ref2(value))
    c._pure()._int(value['bytes'], 'actual publication bytes', minimum, MAX_REFERENCE_BYTES)
    return copy.deepcopy(value)


def _policy_seal(policy):
    c = _owner()
    return {'identity_raw': _sha(policy['identity_raw']),
        'identity_reference': _sha(c._pure().encoded(policy['identity_reference'])),
        'identity_pin': policy['identity_pin'],
        'commands': _sha(c._pure().encoded(policy['commands'])),
        'generated_inputs': _sha(c._pure().encoded(policy['generated_inputs'])),
        'expected': _sha(c._pure().encoded(policy['expected'])),
        'prefix_inventory': _sha(_inventory_bytes(policy['prefix_inventory'])),
        'notice_refs': _sha(c._pure().encoded(policy['notice_refs'])),
        'library_inspections': _sha(c._pure().encoded(policy['library_inspections']))}


class _Publication:
    def __init__(self, context, lifecycle):
        self.c, self.context, self.lifecycle = _owner(), context, lifecycle
        c = self.c
        if type(context) is not c._NativeContext or context not in c._NATIVE_CONTEXTS:
            raise ValueError('Actual same-Core native publication context required')
        state = c._NATIVE_CONTEXTS[context]
        factory = state.get('factory')
        if type(factory) is not c._Factory or factory not in c._NATIVE_FACTORIES:
            raise ValueError('Actual original fixed native factory required')
        policy = c._NATIVE_FACTORIES[factory]
        required = {'context', 'commands', 'generated_inputs', 'expected', 'identity_reference',
            'identity_raw', 'identity_pin', 'prefix_inventory', 'notice_refs', 'library_inspections'}
        if type(policy) is not dict or not required <= set(policy) or policy['context'] is not context:
            raise ValueError('Complete same-context native publication policy required')
        self.factory, self.policy = factory, policy
        self.input_token, self.source_token = state['input_token'], state['source_token']
        self.seal = _policy_seal(policy)
        self.generated = c._support_module('generated_inputs')
        self.current_inputs = c._support_module('current_inputs')
        self.sources = c._support_module('source_inputs')
        self.selection = c._support_module('selection')
        self.witness = c._witness_module()
        self.proof = c._proof_module()
        self.published, self.added_directories = {}, set()
        self.references, self.reference_bytes = {}, 0
        self.complete = False
        self._check()
        self.baseline = copy.deepcopy(context.workspace.inspect_outputs())
        raw = self.generated._snapshot(self.baseline, context.workspace.output)
        if _sha(raw) != context.observations[-1]['output_subject_sha256']:
            raise ValueError('Earliest complete publication baseline differs from actual final stage')
        self._probe()
        self._prefix()
        self._hold_initial()
        self._checkpoint()

    def _check(self):
        c, context, policy = self.c, self.context, self.policy
        if _owner() is not c or type(context) is not c._NativeContext:
            raise ValueError('Original publication Core/context changed')
        state = c._NATIVE_CONTEXTS.get(context)
        if (state is None or state.get('factory') is not self.factory
                or c._NATIVE_FACTORIES.get(self.factory) is not policy or policy['context'] is not context
                or state.get('input_token') is not self.input_token
                or state.get('source_token') is not self.source_token):
            raise ValueError('Original native publication associations changed')
        context._check()
        c._equal(_policy_seal(policy), self.seal, 'original source-owned publication policy')
        c._equal(context.commands, policy['commands'], 'original fixed publication commands')
        c._equal(context.registration, policy['expected']['registration'], 'original stage registration')
        if (not context.commands or context.next_index != len(context.commands)
                or len(context.observations) != len(context.commands)):
            raise ValueError('All actual fixed stages must complete before publication')
        if context.commands[-1]['stage'] != 'probe' or context.commands[-1]['supplier'] != '__closure__':
            raise ValueError('Actual final closure-link stage required')
        lease = self.current_inputs._lease_for_controller(self.input_token)
        if lease['held'] is not context.held:
            raise ValueError('Original current-input owner differs from native context')
        if type(policy['identity_raw']) is not bytes or _sha(policy['identity_raw']) != policy['identity_pin']:
            raise ValueError('Original independently held H2 bytes differ')
        c._reference(policy['identity_reference'])
        c._equal(policy['identity_reference']['sha256'], policy['identity_pin'], 'original H2 reference pin')
        if lease['identity_raw'] != policy['identity_raw']:
            raise ValueError('Current held original H2 bytes changed')
        c._equal(lease['identity'], context.identity, 'actual current H2 identity')
        c._equal(lease['selection']['toolchain_identity'], policy['identity_reference'], 'actual selected H2 reference')
        c._equal(lease['nmake_runtime'], context.nmake_runtime, 'actual original NMake runtime')
        c._equal(lease['nmake_runtime'], policy['expected']['nmake_runtime'], 'fixed original NMake runtime')
        sources = self.sources.require_sources(self.source_token)
        c._pure()._fields(sources, ('projections', 'bindings', 'protected_paths', 'materialized'), 'actual source state')
        source_state, source_lease = self.sources._state(self.source_token)
        if source_state['inputs'] is not self.input_token or source_lease is not lease:
            raise ValueError('Original supplier source capability belongs to another current-input graph')
        if sources['materialized'] is not True:
            raise ValueError('Original supplier sources must be materialized')
        c._equal(sources['bindings'], policy['expected']['bindings']['sources'],
            'actual original selected supplier source bindings')
        projections = sources['projections']
        if type(projections) is not dict or set(projections) != set(sources['bindings']):
            raise ValueError('Every original selected supplier projection is required')
        for supplier, projection in projections.items():
            c._pure()._fields(projection, ('schema_version', 'kind', 'target', 'supplier',
                'archive', 'source_root', 'files', 'directories', 'notices', 'transformations'),
                'original supplier source projection')
            root = context.workspace.output + '/sources/' + supplier
            copied = lease['held'].trees.get(root.casefold())
            if type(copied) is not dict:
                raise ValueError('Original materialized supplier tree is not held')
            c._pure()._fields(copied, ('owner', 'tree', 'inventory'), 'actual held supplier tree')
            inventory = copied['inventory']
            c._pure()._fields(inventory, ('root', 'files', 'directories'), 'actual copied source inventory')
            c._equal(inventory['root'], root, 'actual materialized supplier tree root')
            actual = {name: inventory[name] for name in ('files', 'directories')}
            original = {name: projection[name] for name in ('files', 'directories')}
            if _inventory_bytes(actual) != _inventory_bytes(original):
                raise ValueError('Actual copied supplier tree differs from original complete projection')
        if self.generated._core() is not c or type(self.lifecycle) is not self.generated._NativeLifecycle:
            raise ValueError('Original same-Core generated lifecycle required')
        gstate, _, _ = self.generated._state(self.lifecycle)
        if gstate['context'] is not context or self.lifecycle not in self.generated._NATIVE:
            raise ValueError('Actual original generated lifecycle association differs')
        c._equal(gstate['fixed'], policy['generated_inputs'], 'fixed original generated declarations')

    def _expected_snapshot(self, extra=None):
        additions = self.published if extra is None else extra
        return {'files': {**copy.deepcopy(self.baseline['files']), **copy.deepcopy(additions)},
            'directories': sorted([*self.baseline['directories'], *self.added_directories]),
            'bytes': self.baseline['bytes'] + sum(row['bytes'] for row in additions.values())}

    def _checkpoint(self, *, extra=None):
        self._check()
        actual = self.context.workspace.inspect_outputs()
        self.generated._snapshot(actual, self.context.workspace.output)
        expected = self._expected_snapshot(extra)
        if actual != expected:
            raise ValueError('Earliest complete output baseline changed beyond explicit publication leaves')
        if actual['bytes'] > self.context.limits['maximum_output_bytes']:
            raise ValueError('Complete publication output exceeds original finite byte bound')
        return actual

    def _capture(self, reference, *, minimum=1, physical=None):
        reference = _body3(reference, minimum=minimum)
        capture = self.context._capture(_ref2(reference), reference['bytes'],
            identity=physical, minimum=minimum)
        self._record(reference, minimum=minimum)
        return capture

    def _record(self, reference, *, minimum=1):
        self._check()
        reference = _body3(reference, minimum=minimum)
        key = reference['path'].casefold()
        previous = self.references.get(key)
        if previous is not None:
            if previous != reference:
                raise ValueError('Actual produced reference aliases another spelling or body')
            return
        if (len(self.references) >= MAX_REFERENCES or self.reference_bytes + reference['bytes']
                > self.context.limits['maximum_output_bytes']):
            raise ValueError('Actual produced reference count/bytes exceed original bound')
        self.references[key] = reference
        self.reference_bytes += reference['bytes']

    def _probe(self):
        c, context = self.c, self.context
        token = context.probe
        if type(token) is not c._NativeProbe or token not in c._NATIVE_PROBES:
            raise ValueError('Actual original native compile capability required')
        row = c._NATIVE_PROBES[token]
        if row['context'] is not context or row['workspace'] is not context.workspace:
            raise ValueError('Compile capability belongs to another actual Workspace')
        last = context.observations[-1]
        execution = {key: copy.deepcopy(last[key]) for key in context.commands[-1]}
        execution['program'] = copy.deepcopy(last['resolved_program']['program'])
        if context._check_probe_link(execution) is not row:
            raise ValueError('Actual final link differs from original compile capability')
        if row['identity_raw'] != self.policy['identity_raw'] or row['identity_pin'] != self.policy['identity_pin']:
            raise ValueError('Original compile H2 association differs')
        operation = row['operation']
        if (not any(joined is operation['joined'] for joined in context.workspace.joined)
                or not any(log is operation['log'] for log in context.workspace.logs)
                or operation['log']._workspace is not context.workspace or operation['log']._state != 'sealed'):
            raise ValueError('Original closed compile owner/log required')
        c._equal(operation['joined'].as_dict(), operation['joined_facts'], 'original compile JoinedStage')
        if (operation['joined_facts'].get('returncode') != 0
                or operation['joined_facts'].get('process_tree_closed') is not True):
            raise ValueError('Actual successful original compile must be closed')
        if row['plan']['log_path'] != operation['row']['path']:
            raise ValueError('Actual compile log differs from original W2 plan')
        return row

    def _prefix(self):
        c, policy, root = self.c, self.policy, self.context.workspace.output + '/prefix'
        inventory = policy['prefix_inventory']
        c._pure()._fields(inventory, ('schema_version', 'kind', 'role', 'target', 'version',
            'root', 'files', 'directories'), 'complete native prefix inventory subject')
        for name, wanted in (('schema_version', 1), ('kind', 'foundation-windows-retained-inventory-v1'),
                ('role', 'native_dependencies'), ('target', c._pure().TARGET),
                ('version', 'webkitwasm-native-deps-windows-x86_64-v1'), ('root', root)):
            c._equal(inventory[name], wanted, 'fixed native prefix ' + name)
        prefix = policy['expected']['prefix']
        c._equal(prefix['root'], root, 'fixed original prefix root')
        c._equal(_sha(_inventory_bytes(inventory)), prefix['inventory_subject_sha256'], 'actual full prefix subject')
        relative = root[len(self.context.workspace.output) + 1:] + '/'
        actual_files = {name[len(relative):]: {key: row[key] for key in ('sha256', 'bytes')}
            for name, row in self.baseline['files'].items() if name.startswith(relative)}
        actual_dirs = [name[len(relative):] for name in self.baseline['directories'] if name.startswith(relative)]
        if _inventory_bytes(actual_files) != _inventory_bytes(inventory['files']) or actual_dirs != inventory['directories']:
            raise ValueError('Actual complete prefix membership differs from independently inspected inventory')
        libraries = policy['expected']['libraries']
        if set(policy['library_inspections']) != set(libraries):
            raise ValueError('Complete actual library inspection map required')
        archives = set()
        for target, library in libraries.items():
            path = library['path']
            if not path.startswith(root + '/lib/') or not path.endswith('.lib'):
                raise ValueError('Actual prefix static library namespace required')
            member = path[len(root) + 1:]
            if actual_files.get(member, {}).get('sha256') != library['sha256']:
                raise ValueError('Actual prefix archive is absent or differs')
            for directory in library['includes']:
                if (not (directory == root + '/include' or directory.startswith(root + '/include/'))
                        or directory[len(root) + 1:] not in actual_dirs):
                    raise ValueError('Actual prefix include directory membership required')
            c._equal(policy['library_inspections'][target]['archive_sha256'], library['sha256'],
                'original actual library inspection pin')
            archives.add(member)
        notices = set()
        if type(policy['notice_refs']) is not list or not 1 <= len(policy['notice_refs']) <= 256:
            raise ValueError('Complete finite original notice references required')
        for reference in policy['notice_refs']:
            c._reference(reference)
            if not reference['path'].startswith(root + '/share/licenses/'):
                raise ValueError('Source-owned prefix notice namespace required')
            member = reference['path'][len(root) + 1:]
            if member in notices or actual_files.get(member, {}).get('sha256') != reference['sha256']:
                raise ValueError('Unique original prefix notice membership required')
            notices.add(member)
        actual_notice_names = {name for name in actual_files if name.startswith('share/licenses/')}
        if notices != actual_notice_names:
            raise ValueError('Every actual retained prefix notice must be independently selected')
        c._equal(_sha(_inventory_bytes({name: actual_files[name] for name in sorted(notices)})),
            prefix['notice_subject_sha256'], 'actual C11 prefix notice subject')
        header_data = {'root': root, 'files': {name: row for name, row in actual_files.items()
            if name not in notices | archives}, 'directories': actual_dirs}
        c._equal(_sha(_inventory_bytes(header_data)), prefix['header_data_subject_sha256'],
            'actual C11 prefix header/data subject')

    def _hold_initial(self):
        policy, context = self.policy, self.context
        original_h = {**copy.deepcopy(policy['identity_reference']), 'bytes': len(policy['identity_raw'])}
        self._record(original_h)
        if context.held.read_ref(original_h, MAX_REFERENCE_BYTES) != policy['identity_raw']:
            raise ValueError('Original held H2 document changed before publication')
        lease = self.c._support_module('current_inputs')._lease_for_controller(policy['input_token'])
        original_refs = [policy['request_ref'], policy['request']['dependency_selection'],
            policy['request']['version_selection'], *lease['original_references']]
        for reference in original_refs:
            raw = context.held.read_ref(reference, MAX_REFERENCE_BYTES)
            self._record({**_ref2(reference), 'bytes': len(raw)}, minimum=0)
        for observation in context.observations:
            reference = observation['logs']['combined']
            self._capture(reference, minimum=0)
        # These are derived original runtime subjects from the actual closed
        # producers, already sealed before any consumer. Keep every selected
        # body and original pre-metadata snapshot in the durable input ledger.
        runtime_refs = self.c._runtime_document_references(context)
        runtime_state = self.c._NATIVE_CONTEXTS[context].get('runtime_documents', {})
        for document in runtime_refs:
            matches = [row for row in runtime_state.values() if row['reference'] == document]
            if len(matches) != 1:
                raise ValueError('Exact actual produced-runtime record required')
            row = matches[0]
            self._capture(document, physical=row['document_capture']['physical'])
            self._capture({**row['program'], 'bytes': len(row['program_capture']['raw'])},
                physical=row['program_capture']['physical'])
            for name, capture in row['library_captures'].items():
                self._capture({**row['libraries'][name]['reference'], 'bytes': len(capture['raw'])},
                    physical=capture['physical'])
            relative = 'metadata/stage-output/' + row['operation']['declaration']['id'] + '.json'
            snapshot = self.baseline['files'].get(relative)
            if snapshot is None or snapshot['sha256'] != row['snapshot_subject']:
                raise ValueError('Original produced-runtime stage snapshot is absent')
            self._capture({'path': context.workspace.output + '/' + relative,
                'sha256': snapshot['sha256'], 'bytes': snapshot['bytes']})
        # The prefix inventory owns complete notice membership. Keep the actual
        # selected notice bodies held too, without duplicating that tree in the
        # produced-document/log/witness reference ledger.
        for reference in policy['notice_refs']:
            relative = reference['path'][len(context.workspace.output) + 1:]
            row = self.baseline['files'][relative]
            context._capture(reference, row['bytes'], minimum=0)
        probe = self._probe()
        compiled = {**copy.deepcopy(probe['plan']['source']['compiled']), 'bytes': len(probe['source']['raw'])}
        self._capture(compiled, physical=probe['source']['physical'])
        selected_plan = policy['expected']['bindings']['plan']
        if selected_plan['path'].startswith(context.workspace.output + '/'):
            relative = selected_plan['path'][len(context.workspace.output) + 1:]
            if not relative.startswith('metadata/'):
                raise ValueError('Produced fixed-plan document must use the owned metadata namespace')
            row = self.baseline['files'].get(relative)
            if row is None or row['sha256'] != selected_plan['sha256']:
                raise ValueError('Actual independently fixed plan document is absent')
            self._capture({**copy.deepcopy(selected_plan), 'bytes': row['bytes']})
        for reference, capture, minimum in (
                ({'path': probe['plan']['object_path'], 'sha256': probe['inspection']['object_sha256'],
                    'bytes': len(probe['object']['raw'])}, probe['object'], 1),
                (probe['operation']['row'], probe['operation']['log_capture'], 0)):
            self._capture(reference, minimum=minimum, physical=capture['physical'])

    def _metadata_directory(self):
        self._checkpoint()
        if 'metadata' in self.baseline['directories']:
            return
        if 'metadata' in self.baseline['files']:
            raise ValueError('Reserved publication directory is an existing file')
        self.context.workspace.mkdir_new('metadata')
        self.added_directories.add('metadata')
        self._checkpoint()

    def _publish(self, relative, raw, *, commit=False):
        self._checkpoint()
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_REFERENCE_BYTES:
            raise ValueError('Finite exact publication bytes required')
        if not relative.startswith('metadata/') or '/' in relative[len('metadata/'):]:
            raise ValueError('Fixed publication metadata leaf required')
        if relative.casefold() in {name.casefold() for name in [*self.baseline['files'], *self.published]}:
            raise ValueError('Final publication leaf must be new and unaliased')
        expected = {'path': relative, 'kind': 'file', 'sha256': _sha(raw), 'bytes': len(raw)}
        additions = {**self.published, relative: expected}
        if self._expected_snapshot(additions)['bytes'] > self.context.limits['maximum_output_bytes']:
            raise ValueError('New publication would exceed original complete output bound')
        publish = self.context.workspace.commit_receipt_new if commit else self.context.workspace.publish_bytes_new
        row = publish(relative, raw)
        self.c._pure()._fields(row, ('path', 'sha256', 'bytes'), 'actual published A row')
        if row != {name: expected[name] for name in ('path', 'sha256', 'bytes')}:
            raise ValueError('Actual published metadata row differs from exact bytes')
        self._checkpoint(extra=additions)
        self.published = additions
        reference = {'path': self.context.workspace.output + '/' + relative,
            'sha256': expected['sha256'], 'bytes': expected['bytes']}
        capture = self._capture(reference)
        if capture['raw'] != raw:
            raise ValueError('Actual held publication readback differs')
        self._checkpoint()
        return reference

    def _dependency(self):
        expected, c = self.policy['expected'], self.c
        observations = copy.deepcopy(self.context.observations)
        for observation in observations:
            original = _body3(observation['logs']['combined'], minimum=0)
            observation['logs']['combined'] = _ref2(original)
        h = self.proof._d2().legacy()
        value = {'schema_version': 3, 'kind': self.proof.RECEIPT_KIND,
            'target': copy.deepcopy(c._pure().TARGET), 'scope': h.SCOPE,
            'bindings': copy.deepcopy(expected['bindings']), 'commands': observations,
            'prefix': copy.deepcopy(expected['prefix']),
            'libraries': {target: {**copy.deepcopy(row), 'inspection': copy.deepcopy(self.policy['library_inspections'][target])}
                for target, row in expected['libraries'].items()},
            'postflight': {'toolchain_identity_sha256': self.policy['identity_pin'],
                'sources': {name: row['source_subject_sha256'] for name, row in expected['bindings']['sources'].items()}},
            'probe': copy.deepcopy(expected['probe']), 'facts': {name: False for name in c._pure().FALSE_FACTS}}
        self.proof.validate_receipt(value, expected, self.context.identity)
        raw = self.proof.encoded(value)
        self.proof.validate_dependency_receipt(raw, _sha(raw), expected, self.context.identity)
        return raw, self._publish('metadata/dependency-receipt.json', raw, commit=True)

    def _w2(self, dependency_raw, dependency):
        probe, w, c = self._probe(), self.witness, self.c
        operation, plan = probe['operation'], probe['plan']
        command = copy.deepcopy(plan['command'])
        command.update(logs={'combined': {**copy.deepcopy(operation['row']), 'mode': 0o644}},
            output_subject_sha256=w.output_subject(plan, probe['object']['raw'], operation['log_capture']['raw']),
            job=copy.deepcopy(operation['job']))
        value = {'schema_version': 2, 'kind': w.KIND, 'target': copy.deepcopy(c._pure().TARGET),
            'scope': 'unqualified-static-probe-object', 'dependency_receipt': _ref2(dependency),
            'toolchain_identity_sha256': self.policy['identity_pin'], 'source': copy.deepcopy(plan['source']),
            'command': command, 'object': {'path': plan['object_path'], 'sha256': probe['inspection']['object_sha256']},
            'inspection': copy.deepcopy(probe['inspection']), 'postflight': {
                'source_sha256': w.SOURCE_SHA256, 'toolchain_identity_sha256': self.policy['identity_pin'],
                'object_sha256': probe['inspection']['object_sha256']},
            'facts': {name: False for name in c._pure().FALSE_FACTS}}
        raw = w.encoded(value)
        w.validate_witness(raw, _sha(raw), identity_raw=self.policy['identity_raw'],
            identity_pin=self.policy['identity_pin'], dependency_raw=dependency_raw,
            dependency_pin=dependency['sha256'], dependency_path=dependency['path'], expected=self.policy['expected'],
            maintained_source_raw=probe['source_raw'], compiled_source_raw=probe['source']['raw'],
            object_raw=probe['object']['raw'], log_raw=operation['log_capture']['raw'],
            maintained_source_path=plan['source']['maintained']['path'], workspace_root=self.context.workspace.output,
            limits=plan['limits'])
        return self._publish('metadata/static-probe-object-witness.json', raw)

    def _g2(self, dependency_raw, dependency):
        data = self.generated.witness(self.lifecycle, identity_pin=self.policy['identity_pin'],
            dependency_reference=_ref2(dependency))
        raw = self.c._pure().encoded(data['value'])
        self.generated.validate_witness(raw, _sha(raw), identity_raw=self.policy['identity_raw'],
            identity_pin=self.policy['identity_pin'], dependency_raw=dependency_raw,
            dependency_pin=dependency['sha256'], dependency_path=dependency['path'], expected=self.policy['expected'],
            generated_inputs=self.policy['generated_inputs'], workspace_root=self.context.workspace.output,
            snapshots=data['snapshots'], outputs=data['outputs'])
        for category in ('snapshots', 'outputs'):
            for path, body in data[category].items():
                self._capture({'path': path, 'sha256': _sha(body), 'bytes': len(body)},
                    minimum=0 if category == 'outputs' else 1)
        return self._publish('metadata/generated-input-witness.json', raw)

    def run(self):
        self._metadata_directory()
        dependency_raw, dependency = self._dependency()
        witness = self._w2(dependency_raw, dependency)
        generated = self._g2(dependency_raw, dependency)
        expected, c = self.policy['expected'], self.c
        provenance = {'schema_version': 1, 'kind': 'foundation-windows-retained-provenance-v1',
            'role': 'native_dependencies', 'target': copy.deepcopy(c._pure().TARGET),
            'inventory_subject_sha256': expected['prefix']['inventory_subject_sha256'],
            'sources': [_ref2(row['archive']) for _, row in sorted(expected['bindings']['sources'].items())],
            'notices': copy.deepcopy(self.policy['notice_refs']),
            'original_reports': [_ref2(dependency), _ref2(witness), _ref2(generated)]}
        provenance_ref = self._publish('metadata/dependency-provenance.json', c._pure().encoded(provenance))
        inventory = {**copy.deepcopy(self.policy['prefix_inventory']), 'provenance': _ref2(provenance_ref)}
        inventory_ref = self._publish('metadata/dependency-inventory.json', _inventory_bytes(inventory))
        lease = self.current_inputs._lease_for_controller(self.input_token)
        native = self.selection.native_input_declaration(self.context.identity,
            lease['selection']['inventories'], expected['prefix']['root'], _ref2(inventory_ref), expected['libraries'])
        native_ref = self._publish('metadata/native-inputs.json', c._pure().encoded(native))
        value = {'schema_version': 2, 'kind': RESULT_KIND,
            'toolchain_identity': copy.deepcopy(self.policy['identity_reference']),
            'toolchain_identity_sha256': self.policy['identity_pin'], 'dependency_receipt': dependency,
            'probe_object_witness': witness, 'generated_input_witness': generated,
            'references': {'inventory': inventory_ref, 'native_inputs': native_ref},
            **{name: False for name in c._pure().FALSE_FACTS}}
        raw = c._pure().encoded(value)
        reference = self._publish('metadata/dependency-with-probe-and-generated-inputs.json', raw)
        self.complete = True
        self._probe()
        self._prefix()
        snapshot = self._checkpoint()
        return {'value': copy.deepcopy(value), 'raw': raw, 'reference': reference,
            'snapshot': copy.deepcopy(snapshot),
            'original_references': sorted(copy.deepcopy(list(self.references.values())), key=lambda row: row['path'])}


def publish_completed(context, generated_lifecycle):
    """Publish actual same-run completed metadata; never close or issue owners."""
    c = _owner()
    if type(context) is not c._NativeContext or context not in c._NATIVE_CONTEXTS:
        raise ValueError('Actual original native publication context required')
    if context in _PUBLICATIONS:
        raise ValueError('Original native context already attempted final publication')
    publication = None
    try:
        publication = _Publication(context, generated_lifecycle)
        _PUBLICATIONS[context] = publication
        return publication.run()
    except BaseException as error:
        if type(context) is c._NativeContext and context in c._NATIVE_CONTEXTS:
            context._revoke(error)
            context.workspace.retain_uncertain(None, None, 'native dependency publication: ' + str(error))
        raise


def recheck_completed(context):
    """Original fixed producer's final pre-close check; no caller baseline."""
    c = _owner()
    if type(context) is not c._NativeContext or context not in c._NATIVE_CONTEXTS:
        raise ValueError('Actual original native publication context required')
    publication = _PUBLICATIONS.get(context)
    if (type(context) is not c._NativeContext or type(publication) is not _Publication
            or publication.context is not context or not publication.complete):
        raise ValueError('Actual completed native publication required')
    publication._probe()
    publication._prefix()
    return copy.deepcopy(publication._checkpoint())
