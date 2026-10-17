"""Source-owned Windows20 declarations and held-prefix inspection primitives.

Import is passive. Public declarations are pure consistency checks, not native
authority. The native inspector accepts only the original Core context and its
fixed-registry declaration. Unreviewed source interfaces remain named gaps; a
caller, D receipt, matching archive pin, or installed filename cannot fill them.
No selected input, supplier, SDK, archive, or product is opened during import.
"""

import copy
import hashlib
from pathlib import Path
import re
import struct
import sys
import types


RECIPE_VERSION = 'webkitwasm-native-deps-windows-x86_64-v1'
MAX_FILES = 65536
MAX_ARCHIVE_LONG_NAMES = 65536
MAX_FILE_BYTES = 256 * 1024**2
MAX_PREFIX_BYTES = 32 * 1024**3
_PROOF_SHA256 = 'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9'
_PROFILE_SHA256 = '14b73b412dab26015fdec17027e29526cfc35f1b9f377a675333257b75860ada'
_RESULT_FIELDS = ('commands', 'registration', 'source_files', 'rendered_files',
    'generated_inputs', 'install_artifacts')
_LIBRARY_FIELDS = ('path', 'includes', 'definitions', 'links', 'supplier')
_PREFIX_INSPECTIONS = {}

# Maintained Source-confirmed fallback for bound legacy factory modules that
# predate CONSUMER_FACTS. Published Source constants must agree exactly with
# these rows. New suppliers require their genuine pinned module constants.
# XML's Threads omission applies only to its fixed zero-interface factory gate.
_INTERFACES = {
    'ZLIB::ZLIB': (('include',), (), ()),
    'Brotli::dec': (('include',), (), ('Brotli::common',)),
    'Brotli::common': (('include',), (), ()),
    'PNG::PNG': (('include',), (), ('ZLIB::ZLIB',)),
    'WebP::libwebp': (('include',), (), ('WebP::sharpyuv',)),
    'WebP::demux': (('include',), (), ('WebP::libwebp',)),
    'WebP::sharpyuv': (('include', 'include/webp'), (), ()),
    'HarfBuzz::HarfBuzz': (('include/harfbuzz',), (), ('ICU::uc',)),
    'HarfBuzz::ICU': (('include/harfbuzz',), (), ('HarfBuzz::HarfBuzz', 'ICU::uc')),
    'LibXml2::LibXml2': (('include/libxml2',), ('LIBXML_STATIC',),
        ('ws2_32', 'ICU::data', 'ICU::i18n', 'ICU::uc', 'ZLIB::ZLIB')),
    'SQLite3::SQLite3': (('include',), ('SQLITE_THREADSAFE=1',
        'SQLITE_OMIT_LOAD_EXTENSION', 'SQLITE_ENABLE_FTS5'), ()),
    'FoundationNative::nghttp2': (('include',), ('NGHTTP2_STATICLIB',), ()),
}


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _proof():
    return _owner()._load_verified_source(
        Path(__file__).resolve().with_name('proof_h2.py'), _PROOF_SHA256,
        '_foundation_windows_library_interfaces_pure_h2_v1', 65536)


def _helper():
    return _owner()._support_module('supplier_factory_contract_base')


def _missing(names):
    raise _owner()._support_module('current_inputs').MissingInputs(tuple(names))


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Closed ' + label + ' required')
    return value


def _inside(path, root):
    return path.casefold().startswith(root.casefold() + '/')


def _relative(value):
    if (type(value) is not str or not value or len(value) > 2048
            or value.startswith('/') or '\\' in value or ':' in value):
        raise ValueError('Canonical portable relative path required')
    _proof().legacy().windows_path('C:/relative/' + value)
    return value


def _layout(files, directories):
    """Check complete case-exact file/parent/empty-directory membership."""
    if (type(files) is not dict or not 1 <= len(files) <= MAX_FILES
            or type(directories) is not list or len(directories) > MAX_FILES
            or any(type(name) is not str for name in directories)
            or directories != sorted(set(directories))):
        raise ValueError('Finite complete prefix file/directory maps required')
    names = {}
    for name in directories:
        _relative(name)
        if name.casefold() in names:
            raise ValueError('Prefix directory aliases another logical entry')
        names[name.casefold()] = (name, 'directory')
    total = 0
    h = _proof().legacy()
    for name, row in files.items():
        _relative(name)
        _fields(row, ('sha256', 'bytes'), 'prefix file')
        h._pin(row['sha256'], 'actual prefix file')
        h._integer(row['bytes'], 'actual prefix bytes', 0, MAX_FILE_BYTES)
        total += row['bytes']
        if name.casefold() in names or total > MAX_PREFIX_BYTES:
            raise ValueError('Prefix file aliases or exceeds aggregate byte bound')
        names[name.casefold()] = (name, 'file')
    for name in [*directories, *files]:
        parts = name.split('/')
        for index in range(1, len(parts)):
            parent = '/'.join(parts[:index])
            if names.get(parent.casefold()) != (parent, 'directory'):
                raise ValueError('Prefix inventory omits or aliases a logical parent')


def _profile():
    helper = _helper()
    if helper._PROFILE != _PROFILE_SHA256:
        raise ValueError('Fixed library recipe profile source binding differs')
    profile = helper._profile()
    h = _proof().legacy()
    h._fields(profile['components'], h.SOURCES, 'fixed thirteen supplier profile')
    h._fields(profile['libraries'], h.LIBRARY_SUPPLIERS, 'fixed twenty library profile')
    for target, supplier in h.LIBRARY_SUPPLIERS.items():
        if profile['libraries'][target].get('supplier') != supplier:
            raise ValueError('Fixed library profile supplier differs')
    return profile


def _system_links():
    """D3-only Source policy; H1/D2 and the strict archive decoder stay fixed."""
    links = _owner()._proof_module().SYSTEM_LINKS
    if type(links) is not frozenset or links != _proof().legacy().SYSTEM_LINKS | {'gdi32'}:
        raise ValueError('Exact frozen D3 system-library Source policy required')
    return links


def _consumer_interfaces(supplier, facts):
    """Pure validation of one supplier's closed Source constant, not authority."""
    h = _proof().legacy()
    if type(supplier) is not str or supplier not in h.SOURCES:
        raise ValueError('Closed Source consumer supplier required')
    targets = {target for target, owner in h.LIBRARY_SUPPLIERS.items() if owner == supplier}
    _fields(facts, targets, supplier + ' Source consumer targets')
    interfaces, system_links = {}, _system_links()
    for target, row in facts.items():
        _fields(row, ('includes', 'definitions', 'links'), target + ' Source consumer facts')
        for name, maximum in (('includes', 64), ('definitions', 128), ('links', 64)):
            values = row[name]
            if (type(values) is not list or len(values) > maximum
                    or any(type(value) is not str for value in values)):
                raise ValueError('Finite literal Source consumer ' + name + ' required')
        includes, definitions, links = row['includes'], row['definitions'], row['links']
        if not includes:
            raise ValueError('At least one Source consumer include directory required')
        if len({value.casefold() for value in includes}) != len(includes):
            raise ValueError('Source include directories duplicate or alias')
        for value in includes:
            _relative(value)
            if value != 'include' and not value.startswith('include/'):
                raise ValueError('Source consumer include must remain in prefix include namespace')
        macros = set()
        for value in definitions:
            if (not 1 <= len(value) <= 128 or re.fullmatch(
                    r'[A-Z][A-Z0-9_]*(?:=[A-Za-z0-9_]+)?', value) is None):
                raise ValueError('Bounded public literal Source macro required')
            macro = value.split('=', 1)[0]
            if macro in macros:
                raise ValueError('Source public macro repeated or redefined')
            macros.add(macro)
        if len(set(links)) != len(links):
            raise ValueError('Source consumer link is repeated')
        for value in links:
            if value not in h.LIBRARY_SUPPLIERS and value not in system_links:
                raise ValueError('Source consumer link is outside the closed D3 policy')
        interfaces[target] = (tuple(includes), tuple(definitions), tuple(links))
        if target in _INTERFACES and interfaces[target] != _INTERFACES[target]:
            raise ValueError('Published Source consumer facts differ from maintained static interface')
    return interfaces


def _source_interfaces():
    h = _proof().legacy()
    registry = _owner()._support_module('supplier_registry')
    interfaces, gaps = dict(_INTERFACES), []
    for supplier in h.SOURCES:
        # None is exclusively the registry's bound legacy-module sentinel.
        # Unbound factories and invalid Source constants retain their own
        # MissingInputs/errors; neither is converted into a missing fact row.
        facts = registry.reviewed_consumer_facts(supplier)
        if facts is not None:
            interfaces.update(_consumer_interfaces(supplier, facts))
        if any(target not in interfaces for target, owner in h.LIBRARY_SUPPLIERS.items()
                if owner == supplier):
            gaps.append('windows-dependency-library-interface-' + supplier + '-source')
    return interfaces, tuple(sorted(gaps))


def source_interface_gaps():
    """Missing facts from bound Source factories; new constants close these gaps."""
    return _source_interfaces()[1]


def _all_interfaces():
    interfaces, gaps = _source_interfaces()
    if gaps:
        _missing(gaps)
    return interfaces


def declarations(identity, prefix_root, factory_returns):
    """Pure exact20 templates from fixed profile and actual registry returns.

    The genuine factory alone supplies these independently validated six-field
    returns. No output hash, source subject, or build label is learned from D.
    Unknown Source interfaces fail before any prefix inspection or link command.
    """
    identity = _proof().toolchain_identity(identity)
    h, profile = _proof().legacy(), _profile()
    h.windows_path(prefix_root, 'fixed dependency prefix')
    if not prefix_root.endswith('/prefix'):
        raise ValueError('Fixed Workspace prefix directory required')
    for original in [row['root'] for row in identity['inventories'].values()] + [identity['system_root']]:
        if (prefix_root.casefold() == original.casefold()
                or _inside(prefix_root, original) or _inside(original, prefix_root)):
            raise ValueError('Dependency prefix overlaps an original input root')
    _fields(factory_returns, h.SOURCES, 'independent thirteen supplier returns')
    libraries, headers, artifact_paths = {}, {}, {}
    for supplier in h.SOURCES:
        result = _fields(factory_returns[supplier], _RESULT_FIELDS, 'independent supplier return')
        artifacts = _fields(result['install_artifacts'], ('libraries', 'headers'), 'installed artifacts')
        targets = {target for target, row in profile['libraries'].items() if row['supplier'] == supplier}
        _fields(artifacts['libraries'], targets, supplier + ' installed library roles')
        names = artifacts['headers']
        if (type(names) is not list or len(names) > MAX_FILES
                or any(type(name) is not str for name in names)
                or names != sorted(set(names))):
            raise ValueError('Sorted unique installed header names required')
        headers[supplier] = []
        for target, relative in artifacts['libraries'].items():
            _relative(relative)
            if not relative.endswith('.lib'):
                raise ValueError('Source-declared static .lib artifact required')
            libraries[target] = {'path': prefix_root + '/' + relative, 'supplier': supplier}
        for relative in [*artifacts['libraries'].values(), *names]:
            _relative(relative)
            if relative.casefold() in artifact_paths:
                raise ValueError('Independent installed artifacts alias across suppliers')
            artifact_paths[relative.casefold()] = relative
            if len(artifact_paths) > MAX_FILES:
                raise ValueError('Aggregate installed artifact count exceeds prefix bound')
        for relative in names:
            if not relative.startswith('include/'):
                raise ValueError('Installed public header must remain under include/')
            headers[supplier].append(prefix_root + '/' + relative)
    if set(libraries) != set(h.LIBRARY_SUPPLIERS):
        raise ValueError('Exactly twenty independent installed library artifacts required')
    _helper()._file_layout(list(artifact_paths.values()))
    interfaces = _all_interfaces()
    for target, row in libraries.items():
        includes, definitions, links = interfaces[target]
        row.update(includes=[prefix_root + '/' + name for name in includes],
            definitions=list(definitions), links=list(links))
    return {'root': prefix_root, 'libraries': copy.deepcopy(libraries), 'headers': copy.deepcopy(headers)}


def _encoded(value):
    # The generic inventory domain is 32MiB. H2/D's smaller document encoder
    # must never be substituted for complete prefix maps or bare notice maps.
    return _helper()._source_encoded(value)


def _equal(left, right, label):
    if _encoded(left) != _encoded(right):
        raise ValueError(label + ' differs')


def _templates(value):
    _fields(value, ('root', 'libraries', 'headers'), 'source library declarations')
    h = _proof().legacy()
    root = h.windows_path(value['root'], 'declared prefix root')
    _fields(value['libraries'], h.LIBRARY_SUPPLIERS, 'exact twenty source library templates')
    _fields(value['headers'], h.SOURCES, 'exact thirteen installed header sets')
    interfaces, selected = _all_interfaces(), {}
    paths = []
    for target, supplier in h.LIBRARY_SUPPLIERS.items():
        row = _fields(value['libraries'][target], _LIBRARY_FIELDS, target + ' source template')
        h.windows_path(row['path'], target + ' source artifact')
        if not _inside(row['path'], root) or not row['path'].endswith('.lib'):
            raise ValueError('Source library artifact must be a prefix .lib')
        relative = row['path'][len(root) + 1:]
        _relative(relative)
        if relative.casefold() in selected:
            raise ValueError('Source library artifacts alias')
        selected[relative.casefold()] = target
        paths.append(relative)
        includes, definitions, links = interfaces[target]
        _equal(row['supplier'], supplier, 'source library supplier')
        _equal(row['includes'], [root + '/' + name for name in includes], 'source include interface')
        _equal(row['definitions'], list(definitions), 'source definition interface')
        _equal(row['links'], list(links), 'source ordered link interface')
    for supplier, headers in value['headers'].items():
        if (type(headers) is not list or len(headers) > MAX_FILES
                or any(type(path) is not str for path in headers)
                or headers != sorted(set(headers))):
            raise ValueError('Sorted unique source header set required')
        for path in headers:
            h.windows_path(path, supplier + ' header')
            if not path.startswith(root + '/include/'):
                raise ValueError('Source header escapes exact prefix include namespace')
            relative = path[len(root) + 1:]
            _relative(relative)
            if relative.casefold() in selected:
                raise ValueError('Source installed artifacts alias across suppliers')
            selected[relative.casefold()] = supplier
            paths.append(relative)
            if len(selected) > MAX_FILES:
                raise ValueError('Aggregate source artifact count exceeds bound')
    _helper()._file_layout(paths)
    return copy.deepcopy(value)


def prefix_inventory(prefix_root, files, directories):
    """Pure generic inventory subject object, with provenance deliberately absent."""
    _proof().legacy().windows_path(prefix_root, 'prefix inventory root')
    _layout(files, directories)
    value = {'schema_version': 1, 'kind': 'foundation-windows-retained-inventory-v1',
        'role': 'native_dependencies', 'target': copy.deepcopy(_proof().TARGET),
        'version': RECIPE_VERSION, 'root': prefix_root,
        'files': copy.deepcopy(files), 'directories': list(directories)}
    _encoded(value)
    return value


def _factory_policy(policy_token):
    core = _owner()
    if type(policy_token) is not core._Factory or policy_token not in core._NATIVE_FACTORIES:
        raise ValueError('Original fixed Source policy factory required')
    policy = core._NATIVE_FACTORIES[policy_token]
    if (type(policy) is not dict or not {'expected', 'library_declarations',
            'build_instances', 'prefix_notices', 'input_token', 'source_token',
            'state', 'context', 'source_mode'} <= set(policy)
            or policy['state'] not in ('deriving', 'ready')
            or policy['source_mode'] not in ('fresh-owned', 'retained-read-only')):
        raise ValueError('Complete original Source policy factory state required')
    templates = _templates(policy['library_declarations'])
    h = _proof().legacy()
    sources = policy['expected']['bindings']['sources']
    _fields(sources, h.SOURCES, 'fixed source-policy bindings')
    _fields(policy['build_instances'], h.SOURCES, 'fixed supplier build labels')
    root = templates['root']
    if not root.endswith('/prefix'):
        raise ValueError('Fixed policy prefix root required')
    workspace = root[:-len('/prefix')]
    for supplier in h.SOURCES:
        subject = h._pin(sources[supplier]['source_subject_sha256'], supplier + ' source subject')
        label = 'supplier-' + supplier + '-' + hashlib.sha256(core._pure().encoded({
            'workspace': workspace, 'supplier': supplier,
            'source_subject_sha256': subject})).hexdigest()[:16]
        _equal(policy['build_instances'][supplier], label, 'source-owned receipt-local build label')
    notices = policy['prefix_notices']
    if type(notices) is not dict or not 1 <= len(notices) <= MAX_FILES:
        raise ValueError('Finite original source notice copy map required')
    seen, suppliers = set(), set()
    for name, row in notices.items():
        _relative(name)
        parts = name.split('/')
        if len(parts) < 4 or parts[:2] != ['share', 'licenses'] or parts[2] not in h.SOURCES:
            raise ValueError('Source notice escapes exact supplier license namespace')
        if name.casefold() in seen:
            raise ValueError('Source notice paths alias')
        seen.add(name.casefold())
        suppliers.add(parts[2])
        _fields(row, ('sha256', 'bytes'), 'source notice copy')
        h._pin(row['sha256'], 'source notice pin')
        h._integer(row['bytes'], 'source notice bytes', 0, MAX_FILE_BYTES)
    if suppliers != set(h.SOURCES):
        raise ValueError('Every source supplier needs its original notice copy')
    return policy, templates


def _policy_subject(policy):
    return {'libraries': policy['library_declarations'],
        'bindings': policy['expected']['bindings'],
        'build_instances': policy['build_instances'], 'notices': policy['prefix_notices'],
        'source_mode': policy['source_mode']}


def _prefix_seal(facts, inventory, policy):
    parts = {name: hashlib.sha256(_encoded(value)).hexdigest()
        for name, value in (('facts', facts), ('inventory', inventory), ('policy', policy))}
    return hashlib.sha256(_owner()._pure().encoded(parts)).hexdigest()


def _seal_prefix(policy_token, policy, result, inventory, held, context):
    facts = copy.deepcopy(result)
    subject = {'facts': facts, 'inventory': inventory, 'policy': _policy_subject(policy)}
    seal = _prefix_seal(facts, inventory, subject['policy'])
    previous = _PREFIX_INSPECTIONS.get(policy_token)
    if previous is not None and previous['seal'] != seal:
        raise ValueError('Original independently inspected prefix cannot be replaced')
    _PREFIX_INSPECTIONS[policy_token] = {'facts': facts, 'inventory': copy.deepcopy(inventory),
        'policy': copy.deepcopy(subject['policy']), 'seal': seal, 'held': held,
        'context': context, 'input_token': policy['input_token']}
    policy['inspected_prefix_facts'] = copy.deepcopy(facts)
    policy['inspected_prefix_inventory'] = copy.deepcopy(inventory)


def _prefix_record(policy_token):
    policy, _ = _factory_policy(policy_token)
    record = _PREFIX_INSPECTIONS.get(policy_token)
    if record is None or policy['state'] != 'ready' or record['input_token'] is not policy['input_token']:
        raise ValueError('Original successful independent prefix inspection required')
    lease = _owner()._support_module('current_inputs')._lease_for_controller(record['input_token'])
    if lease['held'] is not record['held']:
        raise ValueError('Prefix inspection belongs to another genuine input owner')
    _equal(_policy_subject(policy), record['policy'], 'unchanged original prefix source policy')
    if _prefix_seal(record['facts'], record['inventory'], record['policy']) != record['seal']:
        raise ValueError('Original independent prefix inspection record changed')
    if record['context'] is not None:
        core, context = _owner(), record['context']
        if (type(context) is not core._NativeContext or context not in core._NATIVE_CONTEXTS
                or policy['context'] is not context or context.factory is not policy_token):
            raise ValueError('Original prefix inspection context association changed')
        context._check()
    elif policy['context'] is not None:
        raise ValueError('Read-only retained prefix policy acquired an unrelated native context')
    lease['held'].check()
    return record


def require_prefix_facts(policy_token):
    return copy.deepcopy(_prefix_record(policy_token)['facts'])


def require_prefix_inventory(policy_token):
    return copy.deepcopy(_prefix_record(policy_token)['inventory'])


def _actual_files(snapshot, workspace_root, prefix_root):
    _owner()._inventory_encoded(snapshot)
    if prefix_root != workspace_root + '/prefix':
        raise ValueError('Only the same actual Workspace prefix may be inspected')
    marker, files = 'prefix/', {}
    h = _proof().legacy()
    for name, row in snapshot['files'].items():
        if not name.startswith(marker):
            continue
        relative = name[len(marker):]
        _relative(relative)
        if type(row) is not dict or row.get('kind') != 'file':
            raise ValueError('Complete actual prefix contains a non-file entry')
        h._pin(row.get('sha256'), 'actual prefix output pin')
        h._integer(row.get('bytes'), 'actual prefix output bytes', 0, MAX_FILE_BYTES)
        files[relative] = {'sha256': row['sha256'], 'bytes': row['bytes']}
    directories = sorted(name[len(marker):] for name in snapshot['directories'] if name.startswith(marker))
    _layout(files, directories)
    return files, directories


def _static_inspection(raw, libraries):
    h = _proof().legacy()
    allowed = set(h.CRT_LIBRARIES) | set(h.SYSTEM_LINKS) | {'clang_rt.builtins-x86_64'}
    allowed.update(row['path'].rsplit('/', 1)[-1][:-4].casefold() for row in libraries.values())
    actual = _owner()._native_inspection().inspect_static_archive(raw,
        allowed_default_libraries=allowed)
    if (actual.get('format') != 'coff-archive' or actual.get('machine') != 'x86_64'
            or actual.get('sha256') != hashlib.sha256(raw).hexdigest()
            or actual.get('bytes') != len(raw) or type(actual.get('members')) is not list
            or not 1 <= len(actual['members']) <= 65536):
        raise ValueError('Actual complete AMD64 static archive inspection required')
    # The fixed inspector rejects import/foreign/LTO objects and nonstatic or
    # debug CRT directives. These zeros describe that complete rejection policy.
    return {'archive_sha256': actual['sha256'], 'format': 'coff-static',
        'machine': 'AMD64', 'member_count': len(actual['members']),
        'import_objects': 0, 'foreign_objects': 0, 'dynamic_crt_directives': 0,
        'debug_crt_directives': 0, 'lto_objects': 0}


def _inspect_existing(held, policy, templates, files, directories, context=None):
    """Private read path; its actual A owner comes only from checked wrappers."""
    root, h = templates['root'], _proof().legacy()
    inventory = prefix_inventory(root, files, directories)
    libraries = templates['libraries']
    library_names = {row['path'][len(root) + 1:] for row in libraries.values()}
    actual_libraries = {name for name in files if name.casefold().endswith('.lib')}
    if actual_libraries != library_names:
        raise ValueError('Actual prefix must contain exactly its twenty source-declared archives')
    if any(name.casefold().endswith(('.dll', '.exe', '.obj', '.o', '.bc', '.a', '.so', '.dylib'))
            for name in files):
        raise ValueError('Unexpected dynamic, executable, object or alternate archive in static prefix')
    header_names = {path[len(root) + 1:] for rows in templates['headers'].values() for path in rows}
    if {name for name in files if name.startswith('include/')} != header_names:
        raise ValueError('Actual public headers differ from independent factory artifact declarations')
    notice_names = {name for name in files if name.startswith('share/licenses/')}
    notices = {name: files[name] for name in sorted(notice_names)}
    _equal(notices, policy['prefix_notices'], 'complete actual original notice copy map')
    for row in libraries.values():
        for include in row['includes']:
            if include[len(root) + 1:] not in directories:
                raise ValueError('Actual source-declared public include directory is absent')

    # One complete capture closes the entire namespace, including empty dirs.
    # Stream all nonlibrary/data bytes without creating one owner per header.
    owner = held.open_output(root)
    if context is not None:
        capture = {'owner': owner}
        context.captures.append(capture)
    tree = owner.capture_tree('', files={name: {**row, 'mode': 0o644}
        for name, row in files.items()}, directories=directories)
    if context is not None:
        capture['tree'] = tree
    for name, row in files.items():
        context._check() if context is not None else held.check()
        view, digest, count = tree.open_file(name), hashlib.sha256(), 0
        try:
            while True:
                context._check() if context is not None else held.check()
                chunk = view.read(1024**2)
                if not chunk:
                    break
                count += len(chunk)
                if count > row['bytes']:
                    raise ValueError('Actual prefix file exceeded independently captured EOF')
                digest.update(chunk)
            if count != row['bytes'] or digest.hexdigest() != row['sha256']:
                raise ValueError('Actual complete prefix file bytes changed')
        finally:
            view.close()
    observed = {}
    for target in sorted(h.LIBRARY_SUPPLIERS):
        template = libraries[target]
        relative = template['path'][len(root) + 1:]
        row = files[relative]
        ref = {'path': template['path'], 'sha256': row['sha256']}
        if context is not None:
            actual = context._capture(ref, row['bytes'])
            raw = actual['raw']
        else:
            view = tree.open_file(relative)
            try:
                raw = view.read(row['bytes'] + 1)
            finally:
                view.close()
            if type(raw) is not bytes or len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Actual retained static archive differs at inspection')
        supplier = template['supplier']
        observed[target] = {**copy.deepcopy(template), 'sha256': row['sha256'],
            'source_subject_sha256': policy['expected']['bindings']['sources'][supplier]['source_subject_sha256'],
            'build_instance': policy['build_instances'][supplier],
            'inspection': _static_inspection(raw, libraries)}
        owner.check()
    owner.check()
    held.check()
    header_data = {name: row for name, row in files.items()
        if name not in library_names and name not in notice_names}
    prefix = {'root': root,
        'inventory_subject_sha256': hashlib.sha256(_encoded(inventory)).hexdigest(),
        'header_data_subject_sha256': hashlib.sha256(_encoded({'root': root,
            'files': header_data, 'directories': directories})).hexdigest(),
        'notice_subject_sha256': hashlib.sha256(_encoded(notices)).hexdigest()}
    _owner()._proof_module().validate_libraries(observed,
        policy['expected']['bindings'], prefix, observations=True)
    return {'prefix': prefix, 'libraries': observed, '_inventory': inventory}


def inspect_prefix(context, declarations):
    """Inspect real held outputs; fixture contexts and caller readers are refused."""
    core = _owner()
    if type(context) is not core._NativeContext or context not in core._NATIVE_CONTEXTS:
        raise ValueError('Original genuine NativeContext required for prefix inspection')
    try:
        context._check()
        policy, templates = _factory_policy(context.factory)
        if (policy['state'] != 'ready' or policy['context'] is not context
                or policy['source_mode'] != 'fresh-owned'):
            raise ValueError('Ready original Source policy must join this actual context')
        _equal(declarations, templates, 'original fixed-registry library declarations')
        if templates['root'] != context.workspace.output + '/prefix':
            raise ValueError('Source factory prefix belongs to another actual Workspace')
        if context.held is not _owner()._support_module('current_inputs')._lease_for_controller(policy['input_token'])['held']:
            raise ValueError('Prefix context differs from the genuine policy input owner')
        native = core._NATIVE_CONTEXTS[context]
        _proof().validate_toolchain_identity(native['identity_raw'], native['identity_pin'], actual_facts=context.identity)
        _equal(context.commands, policy['expected']['commands'], 'original source-factory command sequence')
        if (not context.commands or context.commands[-1]['stage'] != 'probe'
                or context.commands[-1]['supplier'] != '__closure__'
                or context.next_index not in (len(context.commands) - 1, len(context.commands))):
            raise ValueError('All original supplier stages must finish before prefix inspection')
        before = context.workspace.inspect_outputs()
        files, directories = _actual_files(before, context.workspace.output, templates['root'])
        result = _inspect_existing(context.held, policy, templates, files, directories, context)
        _equal(context.workspace.inspect_outputs(), before, 'complete unchanged actual Workspace outputs')
        context._check()
        inventory = result.pop('_inventory')
        _seal_prefix(context.factory, policy, result, inventory, context.held, context)
        return result
    except BaseException as error:
        context._revoke(error)
        raise


def inspect_retained_prefix(input_token, policy_token, inventory):
    """Read-only actual retained prefix; no Workspace or synthetic context exists."""
    lease = _owner()._support_module('current_inputs')._lease_for_controller(input_token)
    policy, templates = _factory_policy(policy_token)
    if (policy['state'] != 'ready' or policy['context'] is not None
            or policy['source_mode'] != 'retained-read-only'
            or policy['input_token'] is not input_token or 'prefix_inventory' not in policy):
        raise ValueError('Retained Source policy must bind the same original input owner and inventory')
    _equal(inventory, policy['prefix_inventory'], 'independently admitted original prefix inventory')
    if inventory['root'] != templates['root']:
        raise ValueError('Retained original prefix root differs from fixed source declaration')
    subject = prefix_inventory(inventory['root'], inventory['files'], inventory['directories'])
    for name in ('version',):
        _equal(inventory[name], subject[name], 'fixed retained inventory ' + name)
    result = _inspect_existing(lease['held'], policy, templates,
        inventory['files'], inventory['directories'])
    if result['prefix']['inventory_subject_sha256'] != inventory['subject_sha256']:
        raise ValueError('Actual retained prefix differs from its complete original inventory subject')
    lease['held'].check()
    actual_inventory = result.pop('_inventory')
    _seal_prefix(policy_token, policy, result, actual_inventory, lease['held'], None)
    return result


def actual_prefix_inventory(context):
    """Return the held actual generic subject after successful native inspection."""
    core = _owner()
    if type(context) is not core._NativeContext or context not in core._NATIVE_CONTEXTS:
        raise ValueError('Original genuine NativeContext required for prefix inventory')
    context._check()
    policy, templates = _factory_policy(context.factory)
    record = _prefix_record(context.factory)
    if record['context'] is not context:
        raise ValueError('Prefix inventory belongs to another original inspection context')
    files, directories = _actual_files(context.workspace.inspect_outputs(),
        context.workspace.output, templates['root'])
    value = prefix_inventory(templates['root'], files, directories)
    _equal(value, record['inventory'], 'same actual held prefix inventory')
    context._check()
    return copy.deepcopy(value)


def sdk_link_names(declarations):
    """Exact Source system-link names; this does not select any SDK file."""
    templates, h = _templates(declarations), _proof().legacy()
    system_links = _system_links()
    names = set()
    for row in templates['libraries'].values():
        for name in row['links']:
            if name not in h.LIBRARY_SUPPLIERS:
                if name not in system_links:
                    raise ValueError('Unreviewed source system link')
                names.add(name)
    return tuple(sorted(names))


def _span(raw, offset, size, label):
    if offset < 0 or size < 0 or offset > len(raw) or size > len(raw) - offset:
        raise ValueError('Truncated system import ' + label)
    return raw[offset:offset + size]


def _ascii_name(raw, label, maximum=8192, *, allow_del=False):
    if not raw or len(raw) > maximum or any(byte < 33 or byte > (127 if allow_del else 126) for byte in raw):
        raise ValueError('Bounded ASCII system import ' + label + ' required')
    return raw


def _short_system_import(raw, system_name):
    # Microsoft PE/COFF Import Header: 20 bytes, then exactly two NUL strings.
    # https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#import-header
    # Version zero is this project's supported subset, not a vendor guarantee.
    _span(raw, 0, 20, 'short header')
    sig1, sig2, version, machine, _, size, ordinal, flags = struct.unpack_from('<HHHHIIHH', raw)
    if (sig1 != 0 or sig2 != 0xffff or version != 0 or machine != 0x8664
            or size != len(raw) - 20 or not 4 <= size <= 8192 + 128 + 2
            or flags >> 5 or flags & 3 not in (0, 1, 2)
            or (flags >> 2) & 7 not in (0, 1, 2, 3)):
        raise ValueError('Unsupported AMD64 system short import header/type/flags')
    strings = raw[20:].split(b'\0')
    if len(strings) != 3 or strings[-1] != b'':
        raise ValueError('Exactly two complete short import strings required')
    symbol, dll = _ascii_name(strings[0], 'symbol'), _ascii_name(strings[1], 'DLL', 128)
    if dll.decode('ascii').casefold() != system_name + '.dll':
        raise ValueError('System short import names another DLL')
    return {'kind': 'short-import', 'symbol': symbol,
        'symbols': {symbol, b'__imp_' + symbol}, 'dll': dll.decode('ascii').casefold(),
        'type': flags & 3, 'name_type': (flags >> 2) & 7, 'ordinal_hint': ordinal}


def _system_descriptor(raw, system_name):
    """Narrow ordinary COFF descriptor companions; never arbitrary native code."""
    _span(raw, 0, 20, 'COFF descriptor header')
    machine, count, _, symbols_at, symbols_count, optional, flags = struct.unpack_from('<HHIIIHH', raw)
    if machine != 0x8664 or not 1 <= count <= 16 or optional or flags or not 1 <= symbols_count <= 4096:
        raise ValueError('Unsupported ordinary AMD64 import descriptor header')
    table_end = 20 + count * 40
    _span(raw, 20, count * 40, 'descriptor section table')
    if symbols_at < table_end:
        raise ValueError('Descriptor symbols overlap headers')
    _span(raw, symbols_at, symbols_count * 18 + 4, 'descriptor symbols')
    strings_at = symbols_at + symbols_count * 18
    strings_size = struct.unpack_from('<I', raw, strings_at)[0]
    if not 4 <= strings_size <= 1024**2:
        raise ValueError('Bounded descriptor string table required')
    strings = _span(raw, strings_at, strings_size, 'descriptor string table')
    starts, cursor = set(), 4
    while cursor < len(strings):
        if len(starts) >= MAX_ARCHIVE_LONG_NAMES:
            raise ValueError('Descriptor string-table entry bound exceeded')
        starts.add(cursor)
        end = strings.find(b'\0', cursor)
        if end < 0:
            raise ValueError('Incomplete descriptor string table')
        _ascii_name(strings[cursor:end], 'COFF name', allow_del=True)
        cursor = end + 1

    def name(value):
        if value[:4] == bytes(4):
            at = struct.unpack_from('<I', value, 4)[0]
            if at not in starts:
                raise ValueError('Descriptor symbol points inside/after a string')
            return strings[at:strings.index(0, at)]
        parts = value.split(b'\0', 1)
        if len(parts) == 2 and any(parts[1]):
            raise ValueError('Descriptor short symbol is not NUL-padded')
        return _ascii_name(parts[0], 'COFF short name', allow_del=True)

    descriptor_name = ('__IMPORT_DESCRIPTOR_' + system_name).encode('ascii').lower()
    thunk_name = ('\x7f' + system_name + '_NULL_THUNK_DATA').encode('ascii').lower()
    allowed = {b'__null_import_descriptor', descriptor_name, thunk_name}
    primary, defined, positions, symbol_details, index = set(), {}, [], {}, 0
    while index < symbols_count:
        symbol = _span(raw, symbols_at + index * 18, 18, 'descriptor primary symbol')
        section = struct.unpack_from('<h', symbol, 12)[0]
        aux = symbol[17]
        if aux > symbols_count - index - 1 or not -2 <= section <= count:
            raise ValueError('Descriptor auxiliary records/section index exceed bounds')
        symbol_name = name(symbol[:8])
        value = struct.unpack_from('<I', symbol, 8)[0]
        storage = symbol[16]
        # PE/COFF Storage Class: STATIC(3), Value=0 denotes a section name.
        # FILE(103) instead denotes source-file metadata and is deliberately
        # unsupported, including as a relocation target, in this subset.
        # https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#storage-class
        if storage not in (2, 3) or struct.unpack_from('<H', symbol, 14)[0]:
            raise ValueError('Unsupported import descriptor symbol storage class')
        if storage == 2:
            if symbol_name.lower() not in allowed or section < 0 or value:
                raise ValueError('Unreviewed absolute/common/external import descriptor symbol')
            if section > 0:
                if symbol_name in defined:
                    raise ValueError('Repeated external descriptor definition')
                defined[symbol_name] = section
        elif section <= 0 or value:
            raise ValueError('Only zero-offset static descriptor section definitions are supported')
        if section > 0:
            positions.append((section, value))
        symbol_details[index] = (section, value, storage, symbol_name)
        primary.add(index)
        index += 1 + aux
    if len(defined) != 1:
        raise ValueError('Unrecognized ordinary SDK import member; descriptor-only subset required')
    spans = [(0, table_end), (symbols_at, symbols_count * 18 + strings_size)]
    sections, section_order, relocations, graphs = {}, [], {}, {}

    def extent(at, size, label):
        if not size:
            return b''
        data = _span(raw, at, size, label)
        if at < table_end or any(at < old + length and old < at + size for old, length in spans):
            raise ValueError('Overlapping descriptor data/symbol/header ranges')
        spans.append((at, size))
        return data

    for section_index in range(count):
        at = 20 + section_index * 40
        section_name = raw[at:at + 8].rstrip(b'\0')
        if section_name.startswith(b'/'):
            if not section_name[1:].isdigit() or int(section_name[1:]) not in starts:
                raise ValueError('Invalid descriptor long section name')
            string_at = int(section_name[1:])
            section_name = strings[string_at:strings.index(0, string_at)]
        virtual_size, virtual_at, size, data_at, relocs_at, lines_at, relocs_count, lines_count, characteristics = struct.unpack_from('<IIIIIIHHI', raw, at + 8)
        # Explicit Source-supported .idata data-section subset. Microsoft's
        # Section Flags table defines INITIALIZED_DATA(0x40), READ/WRITE and
        # alignment encodings 1..14. All other bits, including LNK_REMOVE,
        # LNK_INFO, COMDAT, executable/code and relocation overflow, reject.
        # https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#section-flags
        supported_flags = 0xc0f00040
        alignment = (characteristics >> 20) & 15
        if (section_name not in (b'.idata$2', b'.idata$3', b'.idata$4', b'.idata$5', b'.idata$6', b'.idata$7')
                or section_name in sections or virtual_size or virtual_at or lines_at or lines_count
                or characteristics & ~supported_flags
                or characteristics & 0x40000040 != 0x40000040 or alignment == 15):
            raise ValueError('Unsupported executable/overflow/long-form import descriptor section')
        data = extent(data_at, size, 'descriptor section bytes')
        relocation_data = extent(relocs_at, relocs_count * 10, 'descriptor relocations')
        graph = []
        for reloc_index in range(relocs_count):
            address, symbol_index, relocation_type = struct.unpack_from('<IIH', relocation_data, reloc_index * 10)
            if symbol_index not in primary or relocation_type not in (0, 3) or address >= max(size, 1):
                raise ValueError('Unrecognized descriptor relocation or auxiliary symbol target')
            if relocation_type == 3 and address + 4 > size:
                raise ValueError('Descriptor RVA relocation exceeds its section')
            graph.append((address, symbol_index, relocation_type))
        sections[section_name] = data
        section_order.append(section_name)
        relocations[section_name] = relocs_count
        graphs[section_name] = graph
    if any(value > len(sections[section_order[section - 1]]) for section, value in positions):
        raise ValueError('Descriptor symbol value exceeds its actual section')
    if any(storage == 3 and symbol_name != section_order[section - 1]
            for section, _, storage, symbol_name in symbol_details.values()):
        raise ValueError('Static descriptor definition must name its exact actual section')
    symbol_name, symbol_section = next(iter(defined.items()))
    symbol_kind = symbol_name.lower()
    if symbol_kind == descriptor_name:
        dll_data = sections.get(b'.idata$6', b'')
        expected_dll = (system_name + '.dll').encode('ascii')
        if (section_order[symbol_section - 1] != b'.idata$2'
                or set(sections) != {b'.idata$2', b'.idata$4', b'.idata$5', b'.idata$6'}
                or sections[b'.idata$2'] != bytes(20) or not dll_data.endswith(b'\0')
                or not len(expected_dll) + 1 <= len(dll_data) <= len(expected_dll) + 4
                or dll_data.rstrip(b'\0').lower() != expected_dll
                or any(sections[name] not in (b'', bytes(8)) for name in (b'.idata$4', b'.idata$5') if name in sections)):
            raise ValueError('Descriptor directory/DLL data differs from selected system DLL')
        # This supported companion has the three PE import-directory RVA
        # relocations only: ILT(0)->.idata$4, Name(12)->.idata$6, IAT(16)->.idata$5.
        # Checking the target's section AND zero value prevents unused selected
        # DLL bytes from masking a relocation to a different name or substring.
        wanted_graph = {0: b'.idata$4', 12: b'.idata$6', 16: b'.idata$5'}
        actual_graph = {}
        for address, symbol_index, relocation_type in graphs[b'.idata$2']:
            target_section, target_value, target_storage, target_name = symbol_details[symbol_index]
            if (address not in wanted_graph or address in actual_graph or relocation_type != 3
                    or target_section <= 0 or target_value or target_storage != 3
                    or section_order[target_section - 1] != wanted_graph[address]
                    or target_name != wanted_graph[address]):
                raise ValueError('System descriptor import-directory relocation graph differs')
            actual_graph[address] = wanted_graph[address]
        if actual_graph != wanted_graph or any(graph for name, graph in graphs.items() if name != b'.idata$2'):
            raise ValueError('Incomplete or extra system descriptor relocation graph')
    elif symbol_kind == b'__null_import_descriptor':
        if (set(sections) != {b'.idata$3'} or section_order[symbol_section - 1] != b'.idata$3'
                or sections[b'.idata$3'] != bytes(20) or any(relocations.values())):
            raise ValueError('Null system import descriptor must be twenty nonrelocated zero bytes')
    elif symbol_kind == thunk_name:
        # Explicit supported companion grammar: the null-thunk definition is
        # offset zero in IAT contribution .idata$5; ILT .idata$4 is also zero.
        if (set(sections) != {b'.idata$4', b'.idata$5'}
                or section_order[symbol_section - 1] != b'.idata$5'
                or sections[b'.idata$4'] != bytes(8) or sections[b'.idata$5'] != bytes(8)
                or any(relocations.values())):
            raise ValueError('AMD64 null import thunk companion differs from supported grammar')
    cursor = 0
    for at, size in sorted(spans):
        if any(raw[cursor:at]):
            raise ValueError('Unrecognized nonzero bytes outside descriptor tables')
        cursor = at + size
    if any(raw[cursor:]):
        raise ValueError('Unrecognized descriptor trailing bytes')
    return {'kind': 'descriptor', 'symbols': set(defined)}


def _inspect_system_import_archive(raw, *, system_name):
    """Bounded Microsoft short-import archive mode for one Source-selected DLL.

    Official layout: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
    This accepts version-zero short records and the explicitly decoded ordinary
    descriptor companions above. BigObj, bitcode, arbitrary ordinary code and
    unimplemented verbose import forms fail closed. It is never the Windows20
    dependency-output inspector and confers no selected-SDK membership authority.
    """
    if type(system_name) is not str or system_name not in _system_links():
        raise ValueError('Source-fixed SDK system-library name required')
    if type(raw) is not bytes or not 8 <= len(raw) <= MAX_FILE_BYTES or raw[:8] != b'!<arch>\n':
        raise ValueError('Bounded regular Microsoft system import archive required')
    members, indexes, longnames, long_starts, cursor, symbols_seen, claimed_symbols = {}, [], None, set(), 8, set(), set()
    while cursor < len(raw):
        if len(members) + len(indexes) >= 65536:
            raise ValueError('System import archive member bound exceeded')
        offset = cursor
        header = _span(raw, cursor, 60, 'archive member header')
        cursor += 60
        if header[58:] != b'`\n':
            raise ValueError('Malformed system import archive member terminator')
        for start, end, pattern, optional in ((16, 28, rb'[0-9]+', True),
                (28, 34, rb'[0-9]+', True), (34, 40, rb'[0-9]+', True),
                (40, 48, rb'[0-7]+', True), (48, 58, rb'[0-9]+', False)):
            value = header[start:end].rstrip(b' ')
            if (not value and not optional) or value and re.fullmatch(pattern, value) is None:
                raise ValueError('Invalid ASCII system archive header number')
        size = int(header[48:58].rstrip(b' '))
        body = _span(raw, cursor, size, 'archive member')
        cursor += size
        if cursor & 1:
            if _span(raw, cursor, 1, 'archive padding') != b'\n':
                raise ValueError('Invalid system import archive alignment padding')
            cursor += 1
        archive_name = header[:16].rstrip(b' ')
        if archive_name == b'/':
            if len(indexes) >= 2 or members or longnames is not None:
                raise ValueError('Misplaced/extra Microsoft archive linker member')
            indexes.append(body)
            continue
        if archive_name == b'//':
            if len(indexes) != 2 or longnames is not None or members:
                raise ValueError('Misplaced/repeated archive long-name table')
            longnames, at = body, 0
            while at < len(body):
                if len(long_starts) >= MAX_ARCHIVE_LONG_NAMES:
                    raise ValueError('Archive long-name entry bound exceeded')
                long_starts.add(at)
                end = body.find(b'\0', at)
                if end < 0:
                    raise ValueError('Incomplete Microsoft archive long-name table')
                _ascii_name(body[at:end], 'archive long member name', 240)
                at = end + 1
            continue
        if len(indexes) != 2:
            raise ValueError('Both Microsoft archive linker members are required')
        if archive_name.startswith(b'/'):
            if not archive_name[1:].isdigit() or longnames is None or int(archive_name[1:]) not in long_starts:
                raise ValueError('Archive long-name reference does not name an entry boundary')
            at = int(archive_name[1:])
            archive_name = longnames[at:longnames.index(0, at)]
        elif archive_name.endswith(b'/'):
            archive_name = archive_name[:-1]
        else:
            raise ValueError('Microsoft ordinary archive member needs its slash terminator')
        if re.fullmatch(rb'[A-Za-z0-9_.$+()-]{1,240}', archive_name) is None:
            raise ValueError('Unsafe/unsupported system archive member name')
        if body[:4] == b'\0\0\xff\xff':
            member = _short_system_import(body, system_name)
            if member['symbol'] in symbols_seen:
                raise ValueError('Repeated system short import symbol')
            symbols_seen.add(member['symbol'])
        else:
            member = _system_descriptor(body, system_name)
        if claimed_symbols.intersection(member['symbols']):
            raise ValueError('Archive members claim overlapping imported/descriptor symbol identities')
        claimed_symbols.update(member['symbols'])
        members[offset] = member
    if cursor != len(raw) or not symbols_seen:
        raise ValueError('Complete system import archive needs at least one selected-DLL short import')
    mappings = []
    for index, body in enumerate(indexes):
        _span(body, 0, 4, 'linker count')
        count = struct.unpack_from('>I' if index == 0 else '<I', body)[0]
        maximum = 3 * len(members) if index == 0 else len(members)
        if not 1 <= count <= maximum:
            raise ValueError('Finite nonempty archive index required')
        _span(body, 4, count * 4, 'linker offsets')
        offsets = list(struct.unpack_from(('>' if index == 0 else '<') + str(count) + 'I', body, 4))
        if offsets != sorted(offsets) or any(at not in members for at in offsets):
            raise ValueError('Archive linker offset does not name an ordered real member boundary')
        at, symbol_count = 4 + count * 4, count
        if index == 1:
            if offsets != sorted(members):
                raise ValueError('Second linker member must cover every actual object exactly once')
            _span(body, at, 4, 'second linker symbol count')
            symbol_count = struct.unpack_from('<I', body, at)[0]
            at += 4
            if not 1 <= symbol_count <= 3 * len(members):
                raise ValueError('Finite second archive symbol index required')
            _span(body, at, symbol_count * 2, 'second linker indices')
            indices = struct.unpack_from('<' + str(symbol_count) + 'H', body, at)
            if any(not 1 <= number <= count for number in indices):
                raise ValueError('Second archive member index out of range')
            offsets = [offsets[number - 1] for number in indices]
            at += symbol_count * 2
        names_raw = body[at:]
        if names_raw.count(b'\0') != symbol_count:
            raise ValueError('Archive symbol count exceeds complete bounded string table')
        names = names_raw.split(b'\0')
        if len(names) != symbol_count + 1 or names[-1] != b'':
            raise ValueError('Archive index strings do not exactly match their count/EOF')
        names = [_ascii_name(name, 'indexed symbol', allow_del=True) for name in names[:-1]]
        if len(set(names)) != len(names) or index == 1 and names != sorted(names):
            raise ValueError('Archive index symbol names duplicate or are not lexical')
        mapping = dict(zip(names, offsets))
        if any(name not in members[offset]['symbols'] for name, offset in mapping.items()):
            raise ValueError('Archive index symbol differs from its actual import/descriptor member')
        mappings.append(mapping)
    if mappings[0] != mappings[1]:
        raise ValueError('First and second Microsoft archive indexes disagree')
    # Every admitted short/descriptor member defines at least one identity;
    # no zero-definition object form is supported by this narrow decoder.
    if set(mappings[0].values()) != set(members):
        raise ValueError('Archive symbol indexes omit an actual admitted defining member')
    return {'format': 'coff-system-import-archive', 'machine': 'AMD64',
        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
        'member_count': len(members), 'short_import_count': len(symbols_seen),
        'dll': system_name + '.dll'}


def select_sdk_libraries(input_token, policy_token):
    """Select only Source-named members of the actual complete held SDK inventory."""
    lease = _owner()._support_module('current_inputs')._lease_for_controller(input_token)
    policy, templates = _factory_policy(policy_token)
    if policy['input_token'] is not input_token or policy['context'] is not None:
        raise ValueError('Original deriving/read-only Source policy must bind this genuine input owner')
    identity = _proof().toolchain_identity(lease['identity'])
    inventory = lease['inventories']['windows_sdk']
    _equal(inventory['root'], identity['inventories']['windows_sdk']['root'], 'held complete SDK root')
    _equal(inventory['subject_sha256'], identity['inventories']['windows_sdk']['subject_sha256'], 'held complete SDK subject')
    refs, inspections = [], {}
    for name in sdk_link_names(templates):
        matches = []
        for member, row in inventory['files'].items():
            path = inventory['root'] + '/' + member
            if (path.rsplit('/', 1)[-1].casefold() == name + '.lib'
                    and path.rsplit('/', 1)[0] in identity['library_directories']):
                matches.append((path, row))
        if len(matches) != 1:
            _missing(('windows-dependency-sdk-' + name.replace('_', '-') + '-library-unique-member',))
        path, row = matches[0]
        ref = {'path': path, 'sha256': row['sha256']}
        raw = lease['held'].read_ref({**ref, 'bytes': row['bytes']}, MAX_FILE_BYTES)
        inspection = _inspect_system_import_archive(raw, system_name=name)
        if inspection['sha256'] != ref['sha256'] or inspection['bytes'] != row['bytes']:
            raise ValueError('Actual independently selected SDK system import library changed')
        refs.append(ref)
        inspections[name] = {'reference': copy.deepcopy(ref), 'inspection': inspection}
    refs.sort(key=lambda row: row['path'])
    lease['held'].check()
    if 'sdk_library_inspections' in policy:
        _equal(policy['sdk_library_inspections'], inspections, 'same original SDK library inspections')
    policy['sdk_library_inspections'] = copy.deepcopy(inspections)
    return refs


def _sdk_tail(identity, libraries, sdk_refs):
    h = _proof().legacy()
    wanted = {name for row in libraries.values() for name in row['links']
        if name not in h.LIBRARY_SUPPLIERS}
    if not wanted <= _system_links() or type(sdk_refs) is not list or len(sdk_refs) > len(_system_links()):
        raise ValueError('Finite Source-reviewed SDK system link refs required')
    seen, refs = set(), []
    for reference in sdk_refs:
        h._reference(reference, 'independently selected SDK system library')
        path = reference['path']
        name = path.rsplit('/', 1)[-1]
        stem = name[:-4].casefold() if name.casefold().endswith('.lib') else None
        if (stem not in wanted or stem in seen
                or not _inside(path, identity['inventories']['windows_sdk']['root'])
                or path.rsplit('/', 1)[0] not in identity['library_directories']):
            raise ValueError('SDK refs differ from exact Source system-library names/directories')
        seen.add(stem)
        refs.append(copy.deepcopy(reference))
    if seen != wanted:
        raise ValueError('Complete exact Source system-library SDK refs required')
    refs.sort(key=lambda row: row['path'])
    return [copy.deepcopy(identity['crt_libraries'][name]) for name in h.CRT_LIBRARIES] + [
        copy.deepcopy(identity['builtins'])] + refs


def probe_link_tail(identity, declarations, sdk_refs):
    """Pure fixed CRT/builtins/SDK order; genuine SDK membership is still separate."""
    identity = _proof().toolchain_identity(identity)
    templates = _templates(declarations)
    return _sdk_tail(identity, templates['libraries'], sdk_refs)


def _render_probe(identity, root, libraries, *, workspace_root, object_path,
                  sdk_refs, maximum_jobs):
    h = _proof().legacy()
    h._integer(maximum_jobs, 'finite dependency jobs', 1, 4)
    h.windows_path(workspace_root, 'probe Workspace')
    h.windows_path(object_path, 'original compiled probe object')
    if root != workspace_root + '/prefix' or object_path != workspace_root + '/probe/static-closure-probe.obj':
        raise ValueError('Exact same-Workspace prefix and original W2 object paths required')
    protected = [row['root'] for row in identity['inventories'].values()] + [identity['system_root']]
    if any(workspace_root.casefold() == original.casefold() or _inside(workspace_root, original)
            or _inside(original, workspace_root) for original in protected):
        raise ValueError('Probe Workspace overlaps an original input root')
    parents = sorted({row['path'].rsplit('/', 1)[0] for row in identity['programs'].values()})
    if len({name.casefold() for name in parents}) != len(parents):
        raise ValueError('Original program search parents alias')
    tail = _sdk_tail(identity, libraries, sdk_refs)
    output_path = workspace_root + '/probe/static-closure-probe.exe'
    argv = [identity['programs']['linker']['path'], object_path, '/NODEFAULTLIB',
        '/OPT:NOREF', '/OPT:NOICF', '/MACHINE:X64', '/OUT:' + output_path]
    argv += ['/WHOLEARCHIVE:' + libraries[target]['path'] for target in sorted(h.LIBRARY_SUPPLIERS)]
    argv += [row['path'] for row in tail]
    for argument in argv:
        h._safe_argument(argument)
    return {'id': 'closure-probe-link', 'supplier': '__closure__', 'stage': 'probe',
        'program': {'kind': 'original', 'role': 'linker',
            'declaration': copy.deepcopy(identity['programs']['linker'])},
        'argv': argv, 'cwd': workspace_root,
        'environment': {'SystemRoot': identity['system_root'], 'PATH': ';'.join(parents),
            'TEMP': workspace_root + '/tmp', 'TMP': workspace_root + '/tmp'},
        'initial_cache': None, 'response_files': [], 'log_policy': 'stdout-stderr-combined'}


def probe_declaration(identity, declarations, *, workspace_root, object_path,
                      link_inputs, maximum_jobs=4):
    """Pre-output G2 declaration from Source artifact paths, never future hashes.

    ``link_inputs`` contains only independently selected Source-named SDK refs.
    H2 CRT and builtins refs are inserted in fixed Source order automatically.
    """
    identity = _proof().toolchain_identity(identity)
    templates = _templates(declarations)
    return _render_probe(identity, templates['root'], templates['libraries'],
        workspace_root=workspace_root, object_path=object_path,
        sdk_refs=link_inputs, maximum_jobs=maximum_jobs)


def probe_command(identity, prefix, libraries, *, workspace_root, object_path,
                  link_inputs, maximum_jobs=4):
    """Pure finite W2 linker declaration; SDK refs still require native joins.

    ``link_inputs`` is the full receipt order: canonical twenty dependencies,
    followed by each H2 CRT/builtins reference and independently selected SDK refs.
    This helper never reads an SDK or promotes caller references to native facts.
    """
    identity = _proof().toolchain_identity(identity)
    h, interfaces = _proof().legacy(), _all_interfaces()
    h._integer(maximum_jobs, 'finite dependency jobs', 1, 4)
    h.windows_path(workspace_root, 'probe Workspace')
    h.windows_path(object_path, 'original compiled probe object')
    h._prefix(prefix, h._Paths())
    if prefix['root'] != workspace_root + '/prefix' or object_path != workspace_root + '/probe/static-closure-probe.obj':
        raise ValueError('Exact same-Workspace prefix and original W2 object paths required')
    _fields(libraries, h.LIBRARY_SUPPLIERS, 'complete independently inspected static closure')
    selected, build_instances = set(), {}
    for target, supplier in h.LIBRARY_SUPPLIERS.items():
        row = _fields(libraries[target], _LIBRARY_FIELDS + ('sha256',
            'source_subject_sha256', 'build_instance', 'inspection'), target + ' inspected library')
        h._reference({key: row[key] for key in ('path', 'sha256')}, target)
        if not _inside(row['path'], prefix['root']) or not row['path'].endswith('.lib') or row['path'].casefold() in selected:
            raise ValueError('Unique independently selected prefix static archives required')
        selected.add(row['path'].casefold())
        includes, definitions, links = interfaces[target]
        _equal(row['supplier'], supplier, 'probe source supplier')
        _equal(row['includes'], [prefix['root'] + '/' + name for name in includes], 'probe source includes')
        _equal(row['definitions'], list(definitions), 'probe source definitions')
        _equal(row['links'], list(links), 'probe ordered source links')
        h._pin(row['source_subject_sha256'], 'probe original source subject')
        h._text(row['build_instance'], 'probe original build instance', 128)
        previous = build_instances.setdefault(supplier, row['build_instance'])
        _equal(previous, row['build_instance'], 'one original supplier build instance')
        inspection = _fields(row['inspection'], h.INSPECTION_FIELDS, 'probe archive inspection')
        for name, expected in (('archive_sha256', row['sha256']), ('format', 'coff-static'), ('machine', 'AMD64')):
            _equal(inspection[name], expected, 'probe inspected ' + name)
        h._integer(inspection['member_count'], 'probe archive members', 1, 65536)
        for name in h.INSPECTION_FIELDS[4:]:
            if type(inspection[name]) is not int or inspection[name] != 0:
                raise ValueError('Unreviewed static archive inspection facts')
    if type(link_inputs) is not list or not 26 <= len(link_inputs) <= 64:
        raise ValueError('Complete finite twenty-library plus CRT/SDK link inputs required')
    refs, paths = [], set()
    for row in link_inputs:
        h._reference(row, 'independently selected direct link input')
        if row['path'].casefold() in paths:
            raise ValueError('Direct link inputs alias')
        paths.add(row['path'].casefold())
        refs.append(copy.deepcopy(row))
    expected = [{key: libraries[target][key] for key in ('path', 'sha256')}
        for target in sorted(h.LIBRARY_SUPPLIERS)]
    _equal(refs[:20], expected, 'canonical twenty-library direct link prefix')
    required = list(identity['crt_libraries'].values()) + [identity['builtins']]
    tail = refs[20:]
    if any(tail.count(row) != 1 for row in required):
        raise ValueError('Each independently admitted H2 CRT and builtins archive is required once')
    for row in tail:
        if row in required:
            continue
        if (not row['path'].endswith('.lib')
                or not _inside(row['path'], identity['inventories']['windows_sdk']['root'])
                or row['path'].rsplit('/', 1)[0] not in identity['library_directories']):
            raise ValueError('Extra direct link refs require independent exact SDK library selection')
    sdk_refs = [row for row in tail if row not in required]
    _equal(tail, _sdk_tail(identity, libraries, sdk_refs), 'fixed Source CRT/builtins/SDK link order')
    return _render_probe(identity, prefix['root'], libraries, workspace_root=workspace_root,
        object_path=object_path, sdk_refs=sdk_refs, maximum_jobs=maximum_jobs)
