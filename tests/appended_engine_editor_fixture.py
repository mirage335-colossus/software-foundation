"""Independent inert editor2035 source and byte fixtures for tooling tests.

Only public byte builders and reviewed legacy literals are shared with the
document fixture. Nothing instantiates Wasm or imports the ESM factory. Every
retained runtime is permanently parser-fixture-only and supplies no actual
engine, browser, SDK, kernel or release qualification.
"""
import base64
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from appended_engine_consumer import scan_factory, scan_wasm
from appended_engine_document_fixture import (
    ACK_SHA, BASE_CHECKS, BASE_SHA, BOOTSTRAP_CHECKS, DOCUMENT_CHECKS, DOCUMENT_SHA,
    EXTENSION_SHA, PHYSICAL_CATALOG, PHYSICAL_CHECKS, PHYSICAL_SHA, TARGET,
    encoded, section, sha, uleb, vector, wasm_name, write,
)

HEADER = 'include/foundation/appended/engine_provider.h'
INTERFACE_PATHS = {
    'base_header': HEADER,
    'document_header': 'include/foundation/appended/engine_provider_document_v2.h',
    'document_contract': 'abi/engine/document-v2/contract.json',
    'document_catalog': 'abi/engine/document-v2/catalog.json',
    'action_ack_schema': 'abi/engine/document-v2/action-ack.json',
    'physical_catalog': 'abi/engine/physical-input-catalog.json',
    'editor_header': 'abi/appended/engine_editor_protocol.h',
    'editor_contract': 'abi/appended/editor-v1/contract.json',
    'editor_catalog': 'abi/appended/editor-v1/catalog.json',
    'editor_schema': 'abi/appended/editor-v1/binary-schema.json',
}
DOCUMENT_CONTRACT_SHA = 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298'
DOCUMENT_CATALOG_SHA = '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5'
# Independently frozen editor source/schema handoff, never derived from policy.
EDITOR_HEADER_SHA = 'bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034'
CONTRACT_SHA = '0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c'
EDITOR_CATALOG_SHA = '34fadacf563a00918255e4dc94b196bf0dc5c8ed57c7165e3da1e5fdd4d06bb8'
EDITOR_SCHEMA_SHA = 'f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1'
FACTORY_PATH = 'runtime/engine.mjs'
WASM_PATH = 'runtime/engine.wasm'
DATA_PATH = 'runtime/data/fonts.bin'
NOTICE_PATH = 'licenses/NOTICE.txt'
BUILD_PATH = 'evidence/provider-build.json'
PROOF_PATH = 'evidence/provider-proof.json'
RUNTIME_PATH = 'evidence/runtime.json'
REPORT_PATH = 'evidence/parser-cases.txt'
FACTORY = b'export default async function createEditorEngine(options = {}) { return options; }\n'
BINDING = 'copied-owner-bridge/direct-worker-editor-v1'
PROFILE_NAME = 'foundation-engine-copied2035-ndv2-editor-v1'
PROOF_KIND = 'foundation-neutral-engine-provider-editor-v1-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-editor-v1-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-editor-v1-runtime-evidence-v1'
EDITOR_CHECKS = (
    'editor-profile-and-surface2', 'editor-query4-owned-projection',
    'editor-command8-native-readback', 'editor-command9-native-revocation',
    'editor-full-worker-target-key', 'editor-pending-form-service-barriers',
    'editor-composition-focus-retirement', 'editor-unknown-terminal-no-replay',
)
RUNTIME_CHECKS = BASE_CHECKS + DOCUMENT_CHECKS + PHYSICAL_CHECKS + EDITOR_CHECKS


def tiny_wasm(*, facts_type=4, configure_type=4, omit=(), extra=(),
              memory=b'\x01\x01\x02', start=None, imported_memory=False):
    """Typed six-export editor module; its inert bodies are never executed."""
    types = [b'\x60\x00\x01\x7f', b'\x60\x05' + b'\x7f' * 5 + b'\x01\x7f',
             b'\x60\x01\x7f\x01\x7f', b'\x60\x01\x7f\x00',
             b'\x60\x02\x7f\x7f\x01\x7f']
    raw = b'\0asm\x01\0\0\0' + section(1, vector(types))
    if imported_memory:
        raw += section(2, vector([wasm_name('host') + wasm_name('memory') + b'\x02' + memory]))
    raw += section(3, vector([uleb(i) for i in (0, 1, 2, 3, facts_type, configure_type)]))
    if not imported_memory:
        raw += section(5, vector([memory]))
    exports = [('bib_engine_wasm_bridge_v1', 0, 0), ('bib_engine_wasm_dispatch_v1', 0, 1),
               ('malloc', 0, 2), ('free', 0, 3), ('bib_engine_wasm_editor_facts_v1', 0, 4),
               ('bib_engine_wasm_editor_configure_v1', 0, 5), ('memory', 2, 0)]
    exports = [item for item in exports if item[0] not in omit] + list(extra)
    raw += section(7, vector([wasm_name(n) + bytes((k,)) + uleb(i) for n, k, i in exports]))
    if start is not None:
        raw += section(8, uleb(start))
    bodies = [b'\x00\x41\x00\x0b'] * 3 + [b'\x00\x0b'] + [b'\x00\x41\x00\x0b'] * 2
    return raw + section(10, vector([uleb(len(body)) + body for body in bodies]))


def provider_contract():
    """Literal ABI1.1 descriptor, independent of the production descriptor."""
    return {'provider_abi': {'major': 1, 'minor': 1}, 'host_abi': {'major': 1, 'minor': 0},
            'getter_maximum_minor': 1, 'target': {'system': 3, 'processor': 3, 'pointer_bits': 32},
            'lifetime': 1, 'maximum_starts': 1,
            'queries': [
                {'operation': 3, 'maximum_input_bytes': 48, 'required_reply_capacity': 1048576,
                 'capability': '512', 'schema_sha256': DOCUMENT_SHA},
                {'operation': 4, 'maximum_input_bytes': 236, 'required_reply_capacity': 1048576,
                 'capability': '32', 'schema_sha256': EDITOR_SCHEMA_SHA}],
            'commands': [
                {'operation': 1, 'maximum_input_bytes': 160, 'required_reply_capacity': 16,
                 'capability': '16', 'schema_sha256': '86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9'},
                {'operation': 3, 'maximum_input_bytes': 32, 'required_reply_capacity': 16,
                 'capability': '64', 'schema_sha256': 'eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9'},
                {'operation': 5, 'maximum_input_bytes': 80, 'required_reply_capacity': 16,
                 'capability': '128', 'schema_sha256': '6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3'},
                {'operation': 6, 'maximum_input_bytes': 6246, 'required_reply_capacity': 1048576,
                 'capability': '1024', 'schema_sha256': DOCUMENT_SHA},
                {'operation': 7, 'maximum_input_bytes': 8, 'required_reply_capacity': 16,
                 'capability': '1024', 'schema_sha256': ACK_SHA},
                {'operation': 8, 'maximum_input_bytes': 1048576, 'required_reply_capacity': 1048576,
                 'capability': '32', 'schema_sha256': EDITOR_SCHEMA_SHA},
                {'operation': 9, 'maximum_input_bytes': 1048576, 'required_reply_capacity': 1048576,
                 'capability': '32', 'schema_sha256': EDITOR_SCHEMA_SHA}]}


def profile(build_hash, recipe_hash):
    return {'schema_version': 1, 'kind': 'foundation-copied-engine-editor-v1',
            'target': 'browser-wasm32', 'binding': BINDING, 'pointer_bits': 32,
            'pthread': False, 'shared_memory': False, 'bridge_abi': 65536,
            'capabilities': '2035', 'contract_sha256': CONTRACT_SHA,
            'build_sha256': build_hash, 'source_recipe_sha256': recipe_hash,
            'provider_abi_major': 1, 'provider_abi_minor': 1, 'host_abi_major': 1, 'host_abi_minor': 0,
            'editor_profile': PROFILE_NAME, 'base_header_sha256': BASE_SHA,
            'document_header_sha256': EXTENSION_SHA, 'document_contract_sha256': DOCUMENT_CONTRACT_SHA,
            'document_catalog_sha256': DOCUMENT_CATALOG_SHA, 'physical_catalog_sha256': PHYSICAL_SHA,
            'editor_header_sha256': EDITOR_HEADER_SHA, 'editor_catalog_sha256': EDITOR_CATALOG_SHA,
            'editor_schema_sha256': EDITOR_SCHEMA_SHA, 'document_schema_sha256': DOCUMENT_SHA,
            'action_ack_schema_sha256': ACK_SHA, 'viewport_width': 800, 'viewport_height': 600,
            'surface_protocol_version': 2, 'surface_capabilities': '8255', 'mouse_input_version': 1,
            'key_mapping_version': 1, 'editor_protocol_version': 1, 'display_scale': 1,
            'editor_query_max_bytes': 236, 'editor_reply_capacity': 1048576, 'editor_command_max_bytes': 1048576}


def bootstrap(value):
    raw = encoded(value)
    return {'worker_epoch': '18446744073709551614',
            'engine_facts': {'export': 'bib_engine_wasm_editor_facts_v1',
                             'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                             'observed_output': base64.b64encode(raw).decode('ascii'),
                             'observed_bytes': len(raw), 'observed_result': copy.deepcopy(value)},
            'engine_configure': {'export': 'bib_engine_wasm_editor_configure_v1',
                                 'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                                 'worker_lo': 4294967294, 'worker_hi': 4294967295, 'observed_result': 0},
            'marker_before': 0, 'marker_after': 65536, 'describe_profile': copy.deepcopy(value),
            'first_start_worker_epoch': '18446744073709551614',
            'checks': {name: 'passed' for name in BOOTSTRAP_CHECKS}}


class EditorEngineFixture:
    """Complete inert source/binary group that always remains ineligible."""

    def __init__(self, root, *, editor_profile='editor', data=False):
        if type(editor_profile) is not str or editor_profile != 'editor':
            raise ValueError('Fixture editor profile must be explicitly editor')
        self.root, self.editor_profile = Path(root), editor_profile
        self.binary, self.sources = self.root / 'binary', self.root / 'sources'
        self.binary.mkdir(parents=True, mode=0o755)
        self.sources.mkdir(mode=0o755)
        self.interfaces = {path: PHYSICAL_CATALOG if role == 'physical_catalog' else (ROOT / path).read_bytes()
                           for role, path in INTERFACE_PATHS.items()}
        self.interface_refs = {role: {'path': path, 'sha256': sha(self.interfaces[path])}
                               for role, path in INTERFACE_PATHS.items()}
        content = {'archives/wrapper.tar.xz': b'inert wrapper marker\n',
                   'archives/engine.tar.xz': b'inert engine marker\n',
                   NOTICE_PATH: b'Parser fixture only; no engine distribution.\n', **self.interfaces}
        content.update({helper: (ROOT / helper).read_bytes() for helper in manifest.HELPERS})
        inputs = {}
        for path, raw in content.items():
            write(self.sources, path, raw)
            role = ('interface' if path in self.interfaces else 'helper' if path in manifest.HELPERS
                    else 'license' if path == NOTICE_PATH else 'source')
            inputs[path] = {'sha256': sha(raw), 'role': role, 'mode': 0o644}
        self.toolchain = {'cxx_standard': 23, 'identity_sha256': sha(b'editor fixture toolchain'),
                          'runtime_policy': 'paired-emscripten', 'paired_sdk_sha256': sha(b'fixture SDK'),
                          'target_baseline': 'parser fixture; no qualified runtime'}
        options = {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'}
        self.provider = {'format': 'browser-module', 'binding': 'copied-owner-bridge',
                         'abi_major': 1, 'abi_minor': 1, 'header': HEADER, 'header_sha256': BASE_SHA}
        self.recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe',
                       'producer_version': 1, 'target': copy.deepcopy(TARGET),
                       'toolchain': self.toolchain, 'options': options, 'provider': self.provider,
                       'suppliers': {key: {'repository': 'https://example.invalid/' + key,
                                           'commit': digit * 40, 'archive': 'archives/' + key + '.tar.xz'}
                                     for key, digit in (('wrapper', '1'), ('engine', '2'))},
                       'inputs': inputs, 'patches': [], 'licenses': [NOTICE_PATH]}
        write(self.sources, 'recipe.json', encoded(self.recipe))
        recipe_hash = sha(encoded(self.recipe))
        self.source = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
                       'producer_version': 1, 'recipe_id': recipe_hash,
                       **manifest.tree_inventory(self.sources, 'sources.json')}
        write(self.sources, 'sources.json', encoded(self.source))
        self.build = {'schema_version': 1, 'kind': BUILD_KIND, 'target': copy.deepcopy(TARGET),
                      'toolchain': self.toolchain, 'options': options, 'source_recipe_sha256': recipe_hash,
                      'source_inputs_sha256': sha(encoded(inputs)), 'contract_header_sha256': CONTRACT_SHA,
                      'binding': BINDING, 'configuration': {
                          'profile': 'browser-wasm32-cpu-direct-owner-editor-v1', 'modularized': True,
                          'esm': True, 'auto_main': False, 'pthread': False, 'shared_memory': False,
                          'fixed_viewport_width': 800, 'fixed_viewport_height': 600,
                          'editor_profile': PROFILE_NAME},
                      'capabilities': '2035', 'bridge_abi': 65536, 'provider_contract': provider_contract()}
        self.profile = profile(sha(encoded(self.build)), recipe_hash)
        self.assets = {FACTORY_PATH: FACTORY, WASM_PATH: tiny_wasm()}
        if data:
            self.assets[DATA_PATH] = b'tiny inert font marker'
        self.notices = {NOTICE_PATH: content[NOTICE_PATH]}
        self.reports = {REPORT_PATH: b'Synthetic parser evidence, never actual engine execution.\n'}
        self.asset_records = {path: {'role': 'factory' if path == FACTORY_PATH else 'wasm' if path == WASM_PATH else 'data',
                                    'sha256': sha(raw), 'bytes': len(raw), 'mode': 0o644,
                                    'lookup_name': None if path == FACTORY_PATH else 'engine.wasm' if path == WASM_PATH else 'fonts.bin'}
                              for path, raw in self.assets.items()}
        self.runtime = {'schema_version': 1, 'kind': RUNTIME_KIND, 'scope': 'parser-fixture-only',
                        'status': 'passed', 'recipe_id': recipe_hash, 'provider_build_sha256': sha(encoded(self.build)),
                        'assets_sha256': sha(encoded(self.asset_records)), 'target': copy.deepcopy(TARGET),
                        'paired_sdk_sha256': self.toolchain['paired_sdk_sha256'], 'engine_profile': self.profile,
                        'browser': {'name': 'fixture-not-a-browser', 'version': 'never-run'},
                        'checks': {name: {'status': 'passed', 'evidence': [
                            {'path': REPORT_PATH, 'sha256': sha(self.reports[REPORT_PATH])}]} for name in RUNTIME_CHECKS},
                        'provider_observation': {'getter_maximum_minor': 1, 'contract': provider_contract()},
                        'bootstrap': bootstrap(self.profile)}
        incoming = ['foundationEngineHost', 'noInitialRun', 'print', 'printErr', 'wasmBinary', 'locateFile']
        if data:
            incoming.append('getPreloadedPackage')
        self.proof = {'schema_version': 1, 'kind': PROOF_KIND, 'recipe_id': recipe_hash,
                      'sources_sha256': sha(encoded(self.source)),
                      'provider_build': {'path': BUILD_PATH, 'sha256': sha(encoded(self.build))},
                      'engine_profile': self.profile, 'assets': self.asset_records,
                      'wasm_facts': scan_wasm(self.assets[WASM_PATH]),
                      'factory_policy': {'kind': 'inert-esm-copied-owner-v1', 'imports': [],
                                         'data_loading': 'getPreloadedPackage' if data else 'embedded',
                                         'incoming_module_api': sorted(incoming), 'syntax': scan_factory(FACTORY)},
                      'runtime_evidence': {'path': RUNTIME_PATH, 'sha256': sha(encoded(self.runtime))},
                      'interfaces': self.interface_refs}
        for path, raw in {**self.assets, **self.notices, **self.reports, **self.interfaces,
                          BUILD_PATH: encoded(self.build), RUNTIME_PATH: encoded(self.runtime),
                          PROOF_PATH: encoded(self.proof)}.items():
            write(self.binary, path, raw)
        self.binary_manifest = {'schema_version': 1, 'kind': 'foundation-appended-engine',
                                'producer_version': 1, 'recipe_id': recipe_hash,
                                'sources_sha256': sha(encoded(self.source)), 'target': copy.deepcopy(TARGET),
                                'toolchain': self.toolchain, 'options': options,
                                'provider': {**self.provider, 'entry': FACTORY_PATH, 'assets': sorted(self.assets)},
                                'licenses': [NOTICE_PATH], 'build': {'origin': 'parser-fixture-only', 'link_receipt': PROOF_PATH},
                                **manifest.tree_inventory(self.binary, 'engine-sdk.json')}
        write(self.binary, 'engine-sdk.json', encoded(self.binary_manifest))

    def evidence(self):
        return {'binary_manifest': encoded(self.binary_manifest), 'source_manifest': encoded(self.source),
                'recipe': encoded(self.recipe), 'proof': encoded(self.proof), 'provider_build': encoded(self.build),
                'runtime': encoded(self.runtime), 'reports': dict(self.reports), 'interfaces': dict(self.interfaces)}

    def pins(self):
        evidence = self.evidence()
        return {key: sha(evidence[label]) for key, label in
                (('recipe', 'recipe'), ('manifest', 'binary_manifest'), ('proof', 'proof'), ('runtime', 'runtime'))}

    def export_group(self, destination):
        """Write only the synthetic retained-byte group, never qualify it."""
        return sdk.export_group(self.binary, self.sources, destination)

    def group_arguments(self):
        return {**{'expected_' + key: value for key, value in self.pins().items()},
                'kernel_target': copy.deepcopy(TARGET), 'paired_sdk': self.toolchain['paired_sdk_sha256'],
                'editor_profile': self.editor_profile}
