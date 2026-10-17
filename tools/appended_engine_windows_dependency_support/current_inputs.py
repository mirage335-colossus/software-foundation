"""Current held inputs for the private H2/D3 producer and retained reader.

The factory obtains its A/Q pair from the single genuine Origin owner reached
through the genuine version issuer.  Pure H2 and inventory validators are only
consistency checks.  No caller facts, Workspace, reader, loader or status callback
can mint a live input capability.  This module performs no work on import.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import types

HERE = Path(__file__).resolve().parent
GAPS = HERE
ISSUER_MODULE_NAME = '_foundation_windows_h2_native_issuer_v1'
# The final source-owned maintained issuer envelope is assigned after its owner
# releases the complete source postimage.  An unbound source is never a native
# qualification or a missing data receipt.
ISSUER_PATH = HERE / 'issuer.py'
ISSUER_SHA256 = '7f4cf89f8c950779378850bab25aca1cc06cc9c9c5e03738aed5f1d924770aea'
_MODULES = {}
_ISSUED = {}
_UNCERTAIN = []
MAX_DOCUMENT = 4 * 1024**2
MAX_INVENTORY = 32 * 1024**2
MAX_FILE = 256 * 1024**2
MAX_READERS = 4096


class MissingSource(ValueError):
    def __init__(self, gaps):
        self.gaps = tuple(gaps)
        super().__init__(', '.join(self.gaps))


class MissingInputs(ValueError):
    def __init__(self, gaps):
        self.gaps = tuple(gaps)
        super().__init__(', '.join(self.gaps))


class HeldNativeInputs:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the fixed genuine native-input factory issues owners')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _source(path, pin, name, maximum=256 * 1024):
    return _owner()._load_verified_source(path, pin, name, maximum)


def _issuer():
    if ISSUER_PATH is None or ISSUER_SHA256 is None:
        raise MissingSource(('windows-dependency-h2-final-issuer-source-binding',))
    return _source(ISSUER_PATH, ISSUER_SHA256, ISSUER_MODULE_NAME, 512 * 1024)


def _proof():
    return _source(HERE / 'proof_h2.py',
        'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9',
        '_foundation_d3_current_input_h2_proof')


def _inventory():
    return _source(HERE / 'inventory_contract.py',
        '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb',
        '_foundation_d3_current_input_inventory')


def _inspection():
    return _source(HERE / 'native_inspection.py',
        '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6',
        '_foundation_d3_current_input_inspection')


def _selection_module():
    return _owner()._support_module('selection')


def inventory_declaration(raw, pin, role, *, provenance_raw, provenance_pin):
    """The six-role pure inventory declaration contract; no native authority."""
    module = _source(HERE / 'inventory.py',
        'b4480452a0a25821203f6ef9448eb9612d969bfd9d5540b92b26463e1a286d07',
        '_foundation_dependency_six_inventory')
    return module.inventory_declaration(raw, pin, role,
        provenance_raw=provenance_raw, provenance_pin=provenance_pin)


def validate_toolchain_identity(raw, pin, actual_facts=None):
    """Strict original H1/H2 kind dispatch, retaining each original document."""
    module = _source(HERE / 'identity.py',
        'b2a66fe02ab1a2890fe53bfc82872421ed00ff53037389d7da9e0d26fb46f919',
        '_foundation_dependency_identity_dispatch')
    return module.validate_toolchain_identity(raw, pin, actual_facts=actual_facts)


def _engine_contract():
    return _source(HERE / 'admission.py',
        'b4ed8350ad0efb2cac897973a784f9a98b93b47e533ded96e2d80edb162c23e3',
        '_foundation_dependency_engine_admission')


def engine_admission_declaration(value, handoff):
    """Pure complete-H validation before its documented eleven-role projection."""
    return _engine_contract().engine_admission_declaration(value, handoff)


def admit_retained_originals(request_ref, *, deadline, limits):
    """Use the issuer's single genuine Origin factory and authority registry."""
    return _issuer().originals_module().admit_retained_originals(
        request_ref, deadline=deadline, limits=limits)


def require_original_membership(token, refs):
    return _issuer().originals_module().require_original_membership(token, refs)


def _equal(left, right, label):
    if _proof().encoded(left) != _proof().encoded(right):
        raise ValueError(label + ' differs')


def _reference(value):
    _proof().legacy()._reference(value, 'original native input')
    return copy.deepcopy(value)


def _preflight_json(raw, maximum):
    """Cap lexical allocations before the shared duplicate-aware decoder."""
    if type(raw) is not bytes or not 1 <= len(raw) <= maximum:
        raise ValueError('Finite original JSON bytes required')
    depth = tokens = 0
    quoted = escaped = scalar = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
        if byte == 34:
            quoted, scalar = True, False
            tokens += 1
        elif byte in (91, 123):
            depth += 1
            tokens += 1
            scalar = False
            if depth > 32:
                raise ValueError('Original JSON nesting exceeds source limit')
        elif byte in (93, 125):
            depth -= 1
            scalar = False
            if depth < 0:
                raise ValueError('Unbalanced original JSON')
        elif byte in b' \t\r\n,:':
            scalar = False
        elif not scalar:
            tokens += 1
            scalar = True
        if tokens > 1000000:
            raise ValueError('Original JSON token count exceeds source limit')
    if quoted or escaped or depth:
        raise ValueError('Unterminated original JSON')


def _document(raw, reference, maximum=MAX_DOCUMENT):
    _preflight_json(raw, maximum)
    return _inventory()._document(raw, reference['sha256'], 'original input metadata')


def _bootstrap(reference):
    """Tainted bounded bootstrap; genuine A immediately reopens these bytes.

    Its result selects a qualification profile, never supplies native facts.
    No Workspace or subprocess is created before genuine anchored readback.
    """
    reference = _reference(reference)
    with Path(reference['path']).open('rb') as stream:
        raw = stream.read(MAX_DOCUMENT + 1)
    return raw, _document(raw, reference)


def _request(value):
    h = _proof().legacy()
    h._fields(value, ('schema_version', 'kind', 'target', 'dependency_selection',
        'input_qualification', 'version_selection', 'maintained_source'), 'producer request')
    h._equal(value['schema_version'], 2, 'producer request schema')
    h._equal(value['kind'], 'foundation-windows-dependency-probe-production-selection-v2', 'producer request kind')
    h._equal(value['target'], _proof().TARGET, 'producer target')
    paths = h._Paths()
    for name in ('dependency_selection', 'input_qualification', 'version_selection', 'maintained_source'):
        h._reference(value[name], name, paths)
    h._equal(value['maintained_source']['sha256'],
        'd71938060a67c63c3557d1c45c98fe9039462a31e122d47cc0a4dc859e95b4ca', 'fixed maintained probe')
    return copy.deepcopy(value)


def _body(reference):
    h = _proof().legacy()
    h._fields(reference, ('path', 'sha256', 'bytes', 'mode'), 'original body reference')
    _reference({key: reference[key] for key in ('path', 'sha256')})
    h._integer(reference['bytes'], 'original body bytes', 1, MAX_FILE)
    h._equal(reference['mode'], 0o644, 'original logical mode')
    return reference


class _Owners:
    """Actual independently qualified A owners; no injectable native callbacks."""
    def __init__(self, actual_a, qualification, deadline):
        self.a, self.q, self.deadline = actual_a, qualification, deadline
        self.owners, self.selected, self.trees = [], {}, {}
        self.closed = False

    def _time(self):
        if self.closed or time.monotonic() >= self.deadline:
            raise ValueError('Original native input lifetime expired or closed')

    def _open(self, root):
        self._time()
        if len(self.owners) >= MAX_READERS:
            raise ValueError('Native input owner count exceeds source bound')
        owner = self.a.AnchoredInputs.open_existing(root, qualification=self.q,
            limits=_selection_module().input_limits(self.deadline, time.monotonic()),
            deadline=self.deadline)
        self.owners.append(owner)
        if type(owner) is not self.a.AnchoredInputs or owner.closed or owner.uncertain:
            raise ValueError('Actual known qualified input owner required')
        return owner

    def read_ref(self, reference, maximum=MAX_DOCUMENT):
        self._time()
        ref = {key: reference[key] for key in ('path', 'sha256')}
        _reference(ref)
        if type(maximum) is not int or not 1 <= maximum <= MAX_FILE:
            raise ValueError('Bounded actual input read required')
        previous = self.selected.get(ref['path'].casefold())
        if previous is not None:
            _equal(previous['reference'], ref, 'same held original spelling/pin')
            previous['owner'].check()
            raw = previous['raw']
        else:
            parent, leaf = ref['path'].rsplit('/', 1)
            owner = self._open(parent)
            expected = {'sha256': ref['sha256'], 'mode': 0o644}
            if 'bytes' in reference:
                expected['bytes'] = reference['bytes']
            raw = owner.read(leaf, expected=expected, maximum=maximum)
            if type(raw) is not bytes or _sha(raw) != ref['sha256']:
                raise ValueError('Actual held original pin differs')
            self.selected[ref['path'].casefold()] = {'reference': ref,
                'raw': raw, 'owner': owner}
        if len(raw) > maximum or 'bytes' in reference and len(raw) != reference['bytes']:
            raise ValueError('Actual held original size differs')
        return raw

    def hold_tree(self, inventory):
        """Capture all names, empty directories and original immutable files."""
        self._time()
        root = inventory['root']
        if root.casefold() in self.trees:
            raise ValueError('Repeated complete inventory root')
        owner = self._open(root)
        tree = owner.capture_tree('', files={name: {**row, 'mode': 0o644}
            for name, row in inventory['files'].items()}, directories=inventory['directories'])
        self.trees[root.casefold()] = {'owner': owner, 'tree': tree, 'inventory': inventory}
        # capture_tree closes membership races; it does not hash file contents.
        # Hash every original stream explicitly without whole-file allocation.
        for name, row in inventory['files'].items():
            self._time()
            view, digest, count = tree.open_file(name), hashlib.sha256(), 0
            try:
                while True:
                    self._time()
                    chunk = view.read(1024**2)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > row['bytes']:
                        raise ValueError('Complete retained file exceeded exact EOF')
                    digest.update(chunk)
                if count != row['bytes'] or digest.hexdigest() != row['sha256']:
                    raise ValueError('Complete actual inventory file differs')
            finally:
                view.close()
        owner.check()

    def open_output(self, root):
        return self._open(root)

    def hold_directory(self, root):
        self._open(root)

    def check(self):
        self._time()
        for owner in self.owners:
            owner.check()

    def close(self):
        # Cleanup is allowed after deadline; unknown/uncertain A state still
        # refuses close under A's own rules and is retained by the caller.
        for owner in reversed(self.owners):
            if not owner.closed:
                owner.close()
        self.closed = True


def _selected(reference, inventories, roles):
    _reference(reference)
    matches = []
    for role in roles:
        inventory = inventories[role]
        prefix = inventory['root'] + '/'
        if reference['path'].startswith(prefix):
            name = reference['path'][len(prefix):]
            row = inventory['files'].get(name)
            if row is not None and row['sha256'] == reference['sha256']:
                matches.append(row)
    if len(matches) != 1:
        raise ValueError('Selected original is not in exactly one complete inventory')
    return matches[0]


def _actual_h2(identity_raw, identity_ref, selection, held, versions, issuer, observed_subject):
    proof, inventory_parser = _proof(), _inventory()
    identity = proof.validate_toolchain_identity(identity_raw, identity_ref['sha256'])
    h = proof.legacy()
    h._fields(versions['inventories'], h.INVENTORIES, 'original admitted inventory declarations')
    h._fields(versions['inventory_subjects'], h.INVENTORIES, 'genuine original subjects')
    inventories, facts = {}, {}
    for role in h.INVENTORIES:
        reference = selection['inventories'][role]
        raw = held.read_ref(reference, MAX_INVENTORY)
        document = _document(raw, reference, MAX_INVENTORY)
        provenance = document.get('provenance')
        _reference(provenance)
        provenance_raw = held.read_ref(provenance, MAX_INVENTORY)
        _preflight_json(provenance_raw, MAX_INVENTORY)
        inventory = inventory_parser.inventory_declaration(raw, reference['sha256'], role,
            provenance_raw=provenance_raw, provenance_pin=provenance['sha256'])
        for original in inventory['original_refs']:
            held.read_ref(original, MAX_FILE)
        observed = versions['inventories'][role]
        actual = {'root': inventory['root'], 'version': observed['version'],
            'subject_sha256': inventory['subject_sha256']}
        _equal(actual, observed, 'current bytes vs original admitted inventory ' + role)
        _equal(inventory['version'], observed['version'], 'same declared inventory label ' + role)
        _equal(inventory['subject_sha256'], versions['inventory_subjects'][role], 'current original subject ' + role)
        held.hold_tree(inventory)
        inventories[role], facts[role] = inventory, actual
    programs = {}
    h._fields(versions['programs'], proof.PROGRAM_NAMES, 'genuine original programs13')
    for role, item in versions['programs'].items():
        ref = {key: item[key] for key in ('path', 'sha256')}
        owner = 'llvm' if role in h.LLVM_PROGRAMS else 'host_generators'
        row = _selected(ref, inventories, (owner,))
        raw = held.read_ref({**ref, 'bytes': row['bytes']}, MAX_FILE)
        # MSBuild's managed closure is checked by the issuer's source-owned
        # runtime-profile helper; do not feed CLR into the native-only reader.
        if role != 'msbuild':
            inspection = _inspection().inspect_tool_image(raw)
            if (inspection.get('format') != 'pe32plus' or inspection.get('machine') != 'x86_64'
                    or inspection.get('dll') is not False):
                raise ValueError('Actual original program is not a native AMD64 executable')
        programs[role] = {'path': ref['path'], 'sha256': _sha(raw), 'version': item['version']}
    # Preserve the existing supported native producer baselines at the first
    # actual H admission, after genuine semantic observations and byte joins.
    # Inventory version labels do not supply these per-program observations.
    _engine_contract()._versions({role: row['version'] for role, row in programs.items()})
    allowed = set(h.CRT_LIBRARIES) | set(h.SYSTEM_LINKS) | {'clang_rt.builtins-x86_64'}
    static = {}
    for role, item in [('builtins', identity['builtins']), *identity['crt_libraries'].items()]:
        owners = ('llvm',) if role == 'builtins' else ('windows_sdk',) if role == 'libucrt' else ('msvc_stl',)
        row = _selected(item, inventories, owners)
        raw = held.read_ref({**item, 'bytes': row['bytes']}, MAX_FILE)
        inspection = _inspection().inspect_static_archive(raw, allowed_default_libraries=allowed)
        if inspection.get('format') != 'coff-archive' or inspection.get('machine') != 'x86_64':
            raise ValueError('Actual original CRT/builtins archive differs')
        static[role] = {'path': item['path'], 'sha256': _sha(raw)}
    directories = {}
    for category in ('include_directories', 'library_directories'):
        directories[category] = []
        for path in identity[category]:
            matches = [inv for inv in inventories.values() if path.startswith(inv['root'] + '/')
                and path[len(inv['root']) + 1:] in inv['directories']]
            if len(matches) != 1:
                raise ValueError('Original search directory lacks complete membership')
            held.hold_directory(path)
            directories[category].append(path)
    actual = {'schema_version': 2, 'kind': proof.IDENTITY_KIND,
        'target': copy.deepcopy(proof.TARGET), 'policy': copy.deepcopy(proof.POLICY),
        'inventories': facts, 'programs': programs, 'builtins': static.pop('builtins'),
        'crt_libraries': static, **directories, 'system_root': observed_subject['runtime_identity']['system_root']}
    held.check()
    return proof.validate_toolchain_identity(identity_raw, identity_ref['sha256'], actual_facts=actual), inventories


def _hold_version_evidence(issuer, token, selected, selection, identity, held, *, fresh, subject):
    """Keep original evidence alive independently after the V issuer closed."""
    versions = issuer.require_observed_versions(token)
    originals = issuer.require_observed_original_references(token)
    if type(originals) is not list or not 1 <= len(originals) <= 4096:
        raise ValueError('Complete finite original version evidence is required')
    ledger = {}
    for ref in originals:
        ref = _reference(ref)
        previous = ledger.get(ref['path'].casefold())
        if previous is not None:
            _equal(previous, ref, 'original ledger spelling/pin')
        ledger[ref['path'].casefold()] = ref
        held.read_ref(ref, MAX_FILE)

    def issued(reference):
        ref = {key: reference[key] for key in ('path', 'sha256')}
        _reference(ref)
        _equal(ledger.get(ref['path'].casefold()), ref, 'selected reference vs genuine original ledger')

    source_refs = []
    for body in selected['sources']:
        issued(body)
        source_refs.append({key: body[key] for key in ('path', 'sha256')})
    for category in ('publication', 'input'):
        issued(selected[category]['qualification'])
        for name, pin in selected[category]['source_identity'].items():
            issued({'path': selected['source_root'] + '/' + name, 'sha256': pin})
    batch_ref = versions['batch']
    issued(batch_ref)
    batch = _document(held.read_ref(batch_ref, MAX_DOCUMENT), batch_ref)
    collector = {'program': {key: selected['programs']['python'][key] for key in ('path', 'sha256')},
        'runtime_subject_sha256': versions['inventory_subjects']['host_generators'],
        'sources': source_refs, 'qualification': selected['publication']['qualification']}
    _equal(batch['collector'], collector, 'original V collector vs original selected source/Q')
    _equal(batch['observations'], versions['observations'], 'genuine batch observation map')
    for role, observation_ref in versions['observations'].items():
        issued(observation_ref)
        observation = _document(held.read_ref(observation_ref, MAX_DOCUMENT), observation_ref)
        _equal(observation['role'], role, 'original observation role')
        _equal(observation['collector'], collector, 'same original collector')
        _equal(observation['program'], {key: selected['programs'][role][key]
            for key in ('path', 'sha256')}, 'same selected original executable')
        issued(observation['log'])
        held.read_ref(_body(observation['log']), MAX_DOCUMENT)
    for role, item in selected['programs'].items():
        _body(item)
        _equal({key: item[key] for key in ('path', 'sha256')},
            {key: identity['programs'][role][key] for key in ('path', 'sha256')}, 'original V/D program ' + role)
        held.read_ref(item, MAX_FILE)
    for role, row in selected['inventories'].items():
        issued(row['reference'])
        _equal({key: row['reference'][key] for key in ('path', 'sha256')}, selection['inventories'][role], 'same V/D inventory')
        _equal(row['root'], identity['inventories'][role]['root'], 'same original inventory root')
        _equal(row['subject_sha256'], identity['inventories'][role]['subject_sha256'], 'same original inventory subject')
        held.read_ref(row['reference'], MAX_INVENTORY)
    for role, reference in selected['runtime_profiles'].items():
        issued(reference)
        _equal(reference, versions['runtime_profiles'][role]['reference'], 'same selected original runtime profile')
    for body in selected['sources']:
        _body(body)
        held.read_ref(body, MAX_DOCUMENT)
    for category in ('publication', 'input'):
        held.read_ref(selected[category]['qualification'], MAX_DOCUMENT)
    if fresh:
        # Fresh producer must execute in its selected collection runtime. A
        # retained reader intentionally does not equate current/historical OS
        # or Python; historical origin remains the genuine issuer's evidence.
        for category in ('publication', 'input'):
            _equal(selected[category]['runtime_identity'], subject['runtime_identity'], 'fresh V/D actual runtime')
        _equal(identity['programs']['python'], {'path': subject['runtime_identity']['python_path'],
            'sha256': subject['runtime_identity']['python_sha256'],
            'version': subject['runtime_identity']['python_version']}, 'fresh selected actual Python')
    return versions, originals


def _owned_facts(state):
    """No live A/Q/owner or mutable registry dictionary crosses this getter."""
    return copy.deepcopy({name: state[name] for name in ('request', 'selection',
        'version_selection', 'identity', 'identity_raw', 'inventories',
        'original_program_evidence', 'nmake_runtime', 'runtime_profiles',
        'original_references', 'subject')})


def _inventory_hash(value):
    # Stream the already validated inventory domain.  H/D's 4MiB canonical
    # serializer is deliberately not used for complete SDK file maps.
    total, digest = 0, hashlib.sha256()
    try:
        for fragment in json.JSONEncoder(indent=2, sort_keys=True,
                ensure_ascii=True, allow_nan=False).iterencode(value):
            raw = fragment.encode('ascii')
            total += len(raw)
            if total + 1 > MAX_INVENTORY:
                raise ValueError('Held inventory canonical bytes exceed source bound')
            digest.update(raw)
        digest.update(b'\n')
        return digest.hexdigest()
    except (RecursionError, OverflowError) as error:
        raise ValueError('Invalid held inventory payload') from error


def _seal(state):
    small = {name: state[name] for name in ('request', 'selection', 'version_selection',
        'identity', 'original_program_evidence', 'nmake_runtime', 'runtime_profiles',
        'original_references', 'subject')}
    return {'facts': _inventory_hash(small), 'identity_raw': _sha(state['identity_raw']),
        'inventories': {role: _inventory_hash(value) for role, value in state['inventories'].items()}}


def _require_state(value):
    if type(value) is not HeldNativeInputs or value not in _ISSUED:
        raise ValueError('Genuine original current-input owner required')
    state = _ISSUED[value]
    if state['closed'] or 'seal' not in state:
        raise ValueError('Current-input admission is incomplete or closed')
    _equal(_seal(state), state['seal'], 'sealed current native-input facts')
    if (state['held'].a is not state['a'] or state['held'].q is not state['qualification']
            or state['held'].deadline != state['deadline']):
        raise ValueError('Original current-input owner association differs')
    state['issuer'].require_observed_versions(state['versions'])
    state['held'].check()
    return state


def _lease_for_controller(value):
    """Trusted fixed controller composition only; public facts stay owned copies."""
    return _require_state(value)


def admit_current_inputs(request_ref, version_token, *, deadline, originals=None,
                         version_origin_ref=None):
    """Open current originals internally; return a live genuine owner token.

    `originals` may only be a genuine token from the issuer's single Origin
    instance.  It selects the current read-only Q profile for retained reads;
    caller dictionaries and historical collector profiles cannot replace it.
    `version_origin_ref` is the retained V selector's Origin request reference,
    checked by the issuer against its own stored association; it is not a
    caller-supplied Origin capability or a historical runtime assertion.
    """
    if os.name != 'nt':
        raise MissingInputs(('windows-dependency-native-windows-host',))
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= time.monotonic():
        raise ValueError('Initial live overall deadline required')
    issuer = _issuer()
    versions = issuer.require_observed_versions(version_token)
    request_raw, request = _bootstrap(request_ref)
    request = _request(request)
    selection_raw, selection = _bootstrap(request['dependency_selection'])
    selection = _selection_module().validate_selection(selection)
    version_raw, selected = _bootstrap(request['version_selection'])
    selected = issuer._selection(selected)
    origin_module = issuer.originals_module()
    origin_facts = origin_module.require_retained_originals(originals) if originals is not None else None
    if originals is None:
        if version_origin_ref is not None:
            raise ValueError('Fresh V admission has no retained Origin request')
        version_origin = None
    else:
        version_origin = issuer.require_observed_origin(version_token, _reference(version_origin_ref))
    current_profile = ({key: origin_facts['input'][key] for key in
        ('qualification', 'source_identity', 'runtime_identity')} if origin_facts is not None else selected['input'])
    actual_a, actual_q, subject = origin_module._admit_input_subject(current_profile)
    held = _Owners(actual_a, actual_q, deadline)
    token = object.__new__(HeldNativeInputs)
    state = {'held': held, 'a': actual_a, 'qualification': actual_q,
        'subject': subject, 'versions': version_token, 'issuer': issuer,
        'request': request, 'selection': selection, 'version_selection': selected,
        'originals': originals, 'closed': False, 'deadline': deadline}
    _ISSUED[token] = state  # Retain every owner before fallible body captures.
    try:
        for ref, raw in ((request_ref, request_raw), (request['dependency_selection'], selection_raw),
                (request['version_selection'], version_raw)):
            if held.read_ref(ref, MAX_DOCUMENT) != raw:
                raise ValueError('Native bootstrap changed before anchored readback')
        # These join historical producer facts on both paths.  The current
        # read-only A/Q pair above remains separate for retained admission.
        _equal(request['input_qualification'], selected['input']['qualification'], 'original V/D input Q')
        _equal(selection['publication'], selected['publication'], 'original V/D publication profile')
        identity_ref = selection['toolchain_identity']
        identity_raw = held.read_ref(identity_ref, MAX_DOCUMENT)
        identity, inventories = _actual_h2(identity_raw, identity_ref, selection, held,
            versions, issuer, subject)
        versions, refs = _hold_version_evidence(issuer, version_token, selected, selection,
            identity, held, fresh=origin_facts is None, subject=subject)
        evidence = issuer.require_original_program_evidence(version_token)
        nmake = issuer.require_nmake_runtime(version_token)
        runtime_profiles = issuer.require_runtime_profiles(version_token)
        h = _proof().legacy()
        h._fields(evidence, _proof().PROGRAM_NAMES, 'original thirteen program evidence rows')
        for role, row in evidence.items():
            h._fields(row, ('observation', 'inventory_subject_sha256', 'runtime_subject_sha256'),
                'original program evidence')
            _equal(row['observation'], versions['observations'][role], 'genuine original role observation')
            owner = 'llvm' if role in h.LLVM_PROGRAMS else 'host_generators'
            _equal(row['inventory_subject_sha256'], versions['inventory_subjects'][owner],
                'genuine original program inventory')
            h._pin(row['runtime_subject_sha256'], 'original program runtime subject')
            if role in runtime_profiles:
                _equal(row['runtime_subject_sha256'], runtime_profiles[role]['subject_sha256'],
                    'original frontend runtime subject')
        # Actual recomputation uses the same fixed source-owned helper as V.
        # It owns its exact profile schema/closure; no independent digest guess.
        runtime = issuer._runtime_module()
        host = inventories['host_generators']
        inventory_raw = held.read_ref(selection['inventories']['host_generators'], MAX_INVENTORY)
        provenance_raw = held.read_ref(host['provenance'], MAX_INVENTORY)
        held_inventory = {'reference': selection['inventories']['host_generators'], 'raw': inventory_raw,
            'provenance_reference': host['provenance'], 'provenance_raw': provenance_raw}
        for role, binding in runtime_profiles.items():
            profile = binding['reference']
            raw = held.read_ref(profile, 2 * 1024**2)
            refs3 = runtime.profile_references(role, profile, raw)
            system_refs = runtime.system_references(role, profile, raw)
            actual_bytes = {ref['path']: held.read_ref(ref, 64 * 1024**2)
                for ref in [*refs3, *system_refs]}
            program = identity['programs'][role]
            program_row = _selected({key: program[key] for key in ('path', 'sha256')},
                inventories, ('host_generators',))
            selected_program = {key: program[key] for key in ('path', 'sha256')}
            selected_program['bytes'] = program_row['bytes']
            actual = runtime.runtime_profile(role, profile, raw,
                held_inventory=held_inventory, held_bytes=actual_bytes,
                system_identity={'root': subject['runtime_identity']['system_root'],
                    'windows_version': subject['runtime_identity']['windows_version']},
                selected_program=selected_program)
            _equal(actual['binding'], binding, 'current original runtime profile ' + role)
        if origin_facts is not None:
            # D originals cover D's executed selector metadata. Genuine V
            # originals independently cover H/inventory/provenance and V's
            # ledger. Holding both scopes does not merge their authorities.
            origin_module.require_original_membership(originals,
                [request_ref, request['dependency_selection']])
            selected_refs = [request['version_selection'], identity_ref,
                *selection['inventories'].values(), *refs]
            selected_refs += [ref for inventory in inventories.values()
                for ref in inventory['original_refs']]
            unique = {}
            for ref in selected_refs:
                ref = _reference({key: ref[key] for key in ('path', 'sha256')})
                previous = unique.setdefault(ref['path'].casefold(), ref)
                _equal(previous, ref, 'V original reference spelling/pin')
            origin_module.require_original_membership(version_origin,
                sorted(unique.values(), key=lambda item: item['path'].casefold()))
        state.update(identity=identity, identity_raw=identity_raw,
            inventories=inventories, original_program_evidence=evidence,
            nmake_runtime=nmake, runtime_profiles=runtime_profiles,
            original_references=copy.deepcopy(refs))
        held.check()
        state['seal'] = _seal(state)
        return token
    except BaseException:
        try:
            held.close()
            state['closed'] = True
        except BaseException as cleanup:
            _UNCERTAIN.append((token, cleanup))
        raise


def require_current_inputs(value):
    return _owned_facts(_require_state(value))


def close_current_inputs(value):
    if type(value) is not HeldNativeInputs or value not in _ISSUED:
        raise ValueError('Genuine current-input owner required')
    state = _ISSUED[value]
    state['held'].close()
    state['closed'] = True
