"""Source-owned supplier dispatch through the controller's sole source cache.

This pure registry emits declarations, not execution or native authority.  No
request chooses a factory module, supplies a command graph or registers a role.
"""
import copy
import hashlib
from pathlib import Path
import re
import sys
import types

HERE = Path(__file__).resolve().parent
SUPPLIERS = ('icu', 'zlib', 'brotli', 'png', 'jpeg', 'webp', 'harfbuzz',
    'xml2', 'sqlite', 'openssl', 'nghttp2', 'psl', 'curl')
_CORE = ('cmake-core/cmake_supplier_factory.py',
    '0c6d81c2e0b387a91e56b3052611ee09f1e2e78039b767ff864c1d57bbed2b5b', 15324)
# The XML2 source joins both CMAKE_ROOT and FindThreads to the admitted host
# inventory before permitting its observed empty Win32 thread interface.
_NETWORK = ('cmake-network/cmake_supplier_factory.py',
    'eeb8a051c537192d4093f6e535b909850518565d6fe8709ad52e35c6e74bb78a', 177954)
_SQLITE = ('sqlite/factory.py',
    'c7021cb627f293b963612dc3b9f87939abc6d451f085e75acab9773222d9f9e7', 4555)
_JPEG = ('cmake-core/jpeg_supplier_factory.py',
    '80cb37bde2af562af5a434bb47abf60bc041f7cd1d288f34bedb5f25b3d76900', 24875)
_CURL = ('cmake-network/curl_supplier_factory.py',
    'c4d1fc6daedb5205dce6002942a3a3d62598890a72615d4cdffcd18763a8364b', 108158)
_PSL = ('psl/factory.py',
    'ee5630a5a4091d485872c98e03d0ed5bfc8e6532a9b2d9cf58568412078f2c9b', 7059)
_ICU = ('icu/factory.py',
    'fd1795d11a2f826881dd1b0571e375ff3bc332d693b750866a121e6d331c9569', 11817)
_ICU_RESOURCES = (
    ('icu/data-emitter.py.in', '8e0eed8476021071bb37a6762a87a6d3f2f40227c9ef24f5af96f3075eaaa978', 5144),
    ('icu/source-manifest.json', 'abd737be62f3a7e3f9999cefa6edf3afc3a1777ff78d7553ad51421af9cd8bbd', 19715),)
_OPENSSL = ('openssl/factory.py',
    '82c6e4fd33434e746b7bd114d090edcafdfa028a779ae3e43d86c4d4f86f56eb', 12188)
_OPENSSL_RESOURCES = (
    ('openssl/bootstrap-patches.json', 'b7f04dcfbdf90790b1008ad10401fe75b2c264479a005abda72b1eef417cfb01', 22853),
    ('openssl/graph-patches.json', 'caadc8d571d62bcfd7ddb33caf277a3bf393715b3e0427200dbfe4df3c6d27ed', 15981),
    ('openssl/foundation-amd64-static-noasm.conf', 'c8a8ad5567ef549c3b1af7f9deededbd2223f48f1727ef159ada19a0b2d27380', 1012),
    ('openssl/reviewed-sources.json', '77a2e253e8c9c22b4c39f72c088d2de6688dbcb66db89e6c25b50af48ddaf8e1', 5103),
    ('openssl/prepare.py.in', 'f17e55f9d1498e3a38da74528e2b6c55479d76b7d2bfd700ff2b4135d338a80e', 5205),
    ('openssl/install.py.in', 'd39b96e4276af1e346ac52f208a27b6df41545a89de80347539ef6d827a24937', 2771),)
_SQLITE_RESOURCES = (('sqlite/CMakeLists.txt',
    '251324fb79752db3edf925fee4f2ad101101b6c8ade9b11ade9dcee39cb575fc', 2820),)
MAX_MODULE = 256 * 1024
MAX_RESOURCE = 65536


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def helper():
    return _owner()._support_module('supplier_factory_contract')


def _binding(supplier):
    if type(supplier) is not str or supplier not in SUPPLIERS:
        raise ValueError('Exact fixed supplier required')
    if supplier in ('zlib', 'brotli', 'png', 'webp'):
        return _CORE
    if supplier == 'jpeg':
        return _JPEG
    if supplier in ('harfbuzz', 'xml2', 'nghttp2'):
        return _NETWORK
    if supplier == 'curl':
        return _CURL
    if supplier == 'sqlite':
        return _SQLITE
    if supplier == 'psl':
        return _PSL
    if supplier == 'icu':
        return _ICU
    if supplier == 'openssl':
        return _OPENSSL
    return None


def _resources(supplier):
    if supplier == 'sqlite':
        return _SQLITE_RESOURCES
    if supplier == 'openssl':
        return _OPENSSL_RESOURCES
    return _ICU_RESOURCES if supplier == 'icu' else ()


def _resource(relative, pin, size):
    path = HERE / 'suppliers' / relative
    with path.open('rb') as stream:
        raw = stream.read(MAX_RESOURCE + 1)
    if len(raw) != size or len(raw) > MAX_RESOURCE or hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('Maintained supplier resource changed')
    return {'path': str(path), 'sha256': pin, 'bytes': size}


def _module_name(filename):
    # Separate fixed files in the same supplier directory must not share an
    # actual source-cache slot (the JPEG/CURL companions are distinct code).
    return '_foundation_windows_supplier_source_' + re.sub(r'[^a-zA-Z0-9_]', '_', filename) + '_v1'


def binding_info():
    rows = {}
    for supplier in SUPPLIERS:
        binding = _binding(supplier)
        if binding is None or binding[1] is None:
            rows[supplier] = {'missing_input': supplier + '-supplier-factory-source-binding'}
            continue
        filename, pin, size = binding
        rows[supplier] = {'source': {'path': str(HERE / 'suppliers' / filename),
            'sha256': pin, 'bytes': size}, 'function': 'reviewed_supplier_commands',
            'resources': [{'path': str(HERE / 'suppliers' / name), 'sha256': digest,
                'bytes': length} for name, digest, length in _resources(supplier)]}
    return {'schema_version': 1, 'kind': 'foundation-windows-fixed-supplier-registry-source-v1',
        'suppliers': rows}


def reviewed_supplier_commands(supplier, *, identity, source_layout, build_root,
                               prefix_root, source_recipe_bindings):
    """Re-derive the closed context and invoke one fixed complete source route."""
    contract = helper()
    binding = _binding(supplier)
    context = contract.factory_context(supplier, identity=identity,
        source_layout=source_layout, build_root=build_root, prefix_root=prefix_root,
        source_recipe_bindings=source_recipe_bindings)
    if binding is None or binding[1] is None:
        raise contract.MissingInputs([supplier + '-supplier-factory-source-binding'])
    filename, pin, size = binding
    for relative, resource_pin, resource_size in _resources(supplier):
        _resource(relative, resource_pin, resource_size)
    name = _module_name(filename)
    module = _owner()._load_verified_source(HERE / 'suppliers' / filename,
        pin, name, maximum=MAX_MODULE)
    if not 1 <= size <= MAX_MODULE or Path(module.__file__).stat().st_size != size:
        raise ValueError('Maintained supplier module length differs')
    result = module.reviewed_supplier_commands(supplier, identity=context['identity'],
        source_layout=context['source_layout'], build_root=context['workspace_root'],
        prefix_root=context['prefix_root'], source_recipe_bindings=context['source_recipe_bindings'])
    return contract.validate_factory_result(context, result)


def _fixed_module(supplier):
    binding = _binding(supplier)
    if binding is None or binding[1] is None:
        raise helper().MissingInputs([supplier + '-supplier-factory-source-binding'])
    filename, pin, size = binding
    helper()  # Install only the controller's actual shared Source contract.
    for relative, resource_pin, resource_size in _resources(supplier):
        _resource(relative, resource_pin, resource_size)
    module = _owner()._load_verified_source(HERE / 'suppliers' / filename, pin,
        _module_name(filename), maximum=MAX_MODULE)
    if not 1 <= size <= MAX_MODULE or Path(module.__file__).stat().st_size != size:
        raise ValueError('Maintained supplier module length differs')
    return module


def reviewed_consumer_facts(supplier):
    """Closed interfaces from one independently pinned fixed Source module.

    None denotes only a bound legacy module whose already maintained interface
    lives in library_interfaces.  Unbound or malformed Source never gets that
    fallback.  This function supplies declarations, not observed output facts.
    """
    value = vars(_fixed_module(supplier)).get('CONSUMER_FACTS')
    if value is None:
        return None
    base = _owner()._support_module('supplier_factory_contract_base')
    h = base._proof().legacy()
    targets = {target for target, owner in h.LIBRARY_SUPPLIERS.items() if owner == supplier}
    if type(value) is not dict or set(value) != targets:
        raise ValueError('Exact fixed supplier consumer targets required')
    system_links = _owner()._proof_module().SYSTEM_LINKS
    if type(system_links) is not frozenset:
        raise ValueError('Closed D3 system-link policy required')
    result = {}
    for target, row in value.items():
        base._fields(row, ('includes', 'definitions', 'links'), 'Source consumer interface')
        for key, maximum in (('includes', 64), ('definitions', 128), ('links', 64)):
            items = row[key]
            if (type(items) is not list or len(items) > maximum
                    or any(type(item) is not str or not 1 <= len(item) <= 2048 for item in items)
                    or len({item.casefold() for item in items}) != len(items)):
                raise ValueError('Finite unique literal Source consumer ' + key + ' required')
        if not row['includes']:
            raise ValueError('Source consumer include directory is required')
        for relative in row['includes']:
            base._relative(relative)
            if relative != 'include' and not relative.startswith('include/'):
                raise ValueError('Source consumer include must stay in the prefix include namespace')
        macros = set()
        for definition in row['definitions']:
            if (len(definition) > 128
                    or re.fullmatch(r'[A-Z][A-Z0-9_]*(?:=[A-Za-z0-9_]+)?', definition) is None):
                raise ValueError('Literal public Source macro required')
            macro = definition.split('=', 1)[0]
            if macro in macros:
                raise ValueError('Source public macro is repeated or redefined')
            macros.add(macro)
        if any(link not in h.LIBRARY_SUPPLIERS and link not in system_links for link in row['links']):
            raise ValueError('Unknown Source consumer library dependency')
        if target in row['links']:
            raise ValueError('Source consumer cannot link itself')
        result[target] = copy.deepcopy(row)
    return result


def reviewed_produced_runtime_facts(supplier, produced_tools):
    """Fixed Source declarations, never a D-authored runtime graph or status."""
    if type(produced_tools) is not dict or len(produced_tools) > 128:
        raise ValueError('Finite independently registered produced tools required')
    if not produced_tools:
        return {}
    value = vars(_fixed_module(supplier)).get('PRODUCED_RUNTIME_FACTS')
    if value is None:
        raise helper().MissingInputs([supplier + '-produced-program-runtime-source-policy'])
    if type(value) is not dict or set(value) != set(produced_tools):
        raise ValueError('Exact Source-owned produced runtime roles required')
    result = {}
    base = _owner()._support_module('supplier_factory_contract_base')
    total = 0
    for role, row in value.items():
        base._fields(row, ('libraries',), 'produced runtime Source policy')
        libraries = row['libraries']
        if type(libraries) is not dict or len(libraries) > 128:
            raise ValueError('Finite Source-owned produced DLL layout required')
        selected, paths = {}, set()
        for name, relative in libraries.items():
            if (type(name) is not str or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,127}\.dll', name) is None
                    or name in _owner()._native_inspection().SYSTEM_IMPORTS):
                raise ValueError('Exact lowercase non-system DLL basename required')
            base._relative(relative)
            if not relative.endswith('.dll') or relative.casefold() in paths:
                raise ValueError('Unique portable produced DLL path required')
            paths.add(relative.casefold())
            selected[name] = relative
            total += len(name) + len(relative)
            if total > 65536:
                raise ValueError('Produced runtime Source declarations exceed byte bound')
        result[role] = {'libraries': selected}
    return copy.deepcopy(result)


def source_gaps():
    """Known incomplete routes before any output owner or program is created."""
    gaps = []
    for supplier in SUPPLIERS:
        row = _binding(supplier)
        if row is None or row[1] is None:
            gaps.append(supplier + '-supplier-factory-source-binding')
    return sorted(set(gaps))
