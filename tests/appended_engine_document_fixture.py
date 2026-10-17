"""Independent inert document-v2 source and byte fixtures for tooling tests.

Copied from reviewed literal consumer fixtures, without importing a test module.
The tiny Wasm and ESM bytes are never instantiated, imported or evaluated here.
All runtime reports and retained groups are parser-fixture-only and cannot
supply actual engine execution, a qualified SDK or production eligibility.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from appended_engine_consumer import scan_factory, scan_wasm
from dependency_archive import encoded


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(root, path, raw):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    for parent in target.parents:
        if parent == root:
            break
        parent.chmod(0o755)
    target.write_bytes(raw)
    target.chmod(0o644)


def uleb(value):
    result = bytearray()
    while True:
        byte, value = value & 127, value >> 7
        result.append(byte | (128 if value else 0))
        if not value:
            return bytes(result)


def wasm_name(value):
    raw = value.encode('utf-8')
    return uleb(len(raw)) + raw


def section(kind, raw):
    return bytes((kind,)) + uleb(len(raw)) + raw


def vector(items):
    return uleb(len(items)) + b''.join(items)


TARGET = {'system': 'Emscripten', 'processor': 'wasm32',
          'triple': 'wasm32-unknown-emscripten', 'pointer_bits': 32}
HEADER = 'include/foundation/appended/engine_provider.h'
INTERFACE_PATHS = {
    'base_header': HEADER,
    'extension_header': 'include/foundation/appended/engine_provider_document_v2.h',
    'contract': 'abi/engine/document-v2/contract.json',
    'document_catalog': 'abi/engine/document-v2/catalog.json',
    'action_ack_schema': 'abi/engine/document-v2/action-ack.json',
}
PHYSICAL_PATH = 'abi/engine/physical-input-catalog.json'
FACTORY_PATH = 'runtime/engine.mjs'
WASM_PATH = 'runtime/engine.wasm'
DATA_PATH = 'runtime/data/fonts.bin'
NOTICE_PATH = 'licenses/NOTICE.txt'
BUILD_PATH = 'evidence/provider-build.json'
PROOF_PATH = 'evidence/provider-proof.json'
RUNTIME_PATH = 'evidence/runtime.json'
REPORT_PATH = 'evidence/parser-cases.txt'
FACTORY = b'export default async function createDocumentEngine(options = {}) { return options; }\n'
BASE_SHA = 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d'
EXTENSION_SHA = '7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626'
CONTRACT_SHA = 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298'
CATALOG_SHA = '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5'
DOCUMENT_SHA = 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d'
ACK_SHA = '1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5'
PHYSICAL_SHA = 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'
BINDING = 'copied-owner-bridge/direct-worker-document-v2'
PROOF_KIND = 'foundation-neutral-engine-provider-document-v2-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-document-v2-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-document-v2-runtime-evidence-v1'
NAMES = {'pixel': 'foundation-engine-copied1795-ndv2-v1',
         'physical': 'foundation-engine-copied2003-ndv2-v1'}
BOOTSTRAP_CHECKS = ('facts_before_configure', 'configure_once', 'configure_before_describe',
                    'describe_before_start', 'no_host_callbacks_during_facts_or_configure',
                    'one_process_start')
BASE_CHECKS = ('factory-inert', 'copied-describe', 'offline-entry-resource-load',
               'native-service-result-and-ack', 'outside-engine-owner-pump',
               'opaque-raster-frame', 'worker-failure-close', 'separate-heaps-copied-bridge')
DOCUMENT_CHECKS = ('document-bootstrap-worker64', 'document-provider-minor-and-catalog',
                   'document-query3-owned-snapshot', 'document-form6-native-readback',
                   'document-action-replay-and-ack7', 'document-navigation-and-stale-lease',
                   'document-outer-unknown-terminal-no-replay')
PHYSICAL_CHECKS = ('raw-key-location-altgraph', 'mouse-five-buttons-context-cancel',
                   'input-context-navigation-retirement', 'native-effect-input-admission',
                   'document-current-physical-provider')
# Reviewed d244 catalog bytes copied as a literal, with no old-test imports.
PHYSICAL_CATALOG = zlib.decompress(base64.b64decode(
    b'eNrtW1tz28YVfvev2OFrBZEEKZIyJw+2rKRqbcm1onQymQxnASxE1LgVF1GMJ/+93zm7uJKUaMfuNDP1g20Bi91zP985Z/Xp'
    b'hRADN4kiGXv54KX4BT8L8Yn/pjcylU4QBsV2FZeRygIXa8azk+q9p/wgDoogifG8+grPnW2hVknmqQzPB/i+CNXgpHnf7Evv'
    b'X1+9Xl1e/3B1fbm6ePV+9ffLn1c/jdvLPeUm2GuVF7JQ9AX/J1R5bsWJtVahZ+lXrW8i+RhEZbQK4rQsVkRQzrSPWmtiGfF2'
    b'6XqbB64MrY9q294jSVUmDXfjznN6KMPVg8ryPvN89r+SrPsNPQ1ifjqqH/7e2jNTabhdpXIbJtKr6R11Vvy7DDLlrfRSkqGr'
    b'JdhoBMuKTEKy8X29Bz78l3KLNmNl/DFONvHKDyC71YMMy/ZKaxMUa6ullavrn169vXrT3mEDSvps+8Gjakif2Ce7L8uJXVtZ'
    b'9edT56eOWmTe1mklfd/PVbFPRGZBzU9/ZzIlsL3vIxJKSqLsPf+98/PvJ09TboyOuN+hCuo373YprjgOE1fb23NMTz+LLBmG'
    b'yQbSj2T+kWgbHyQgSrwARpHlz1Kw+CIKatX8siP/PSrpK+PXg3TDJZQsniV6bH+hOmfTJ/R5WJyIJ6tQxffF+nnSZjsrSoRW'
    b'2kUv+RaUH7ZECrjHkm6PPov0FwcUWoWI2fT5EHGM8HXkd5O4UI/Pm4Y9PZLKAuH1eQJVDAkiChMhdz9+by2sHAlGZpSwru/e'
    b'7pKjZa0j8nOm0zKvzzOLNlWvbi+urqzRoz0+PR09zpWVZJaK0mL7PG1PGkfbggafIdNVTyG9/IHIEXhVMu4Kf2CyptAkCeRJ'
    b'GebYQPxFNGLEDy26hXqUbhH2mUUSECbP5kIHFfGbypL+MsQz2npIOw6rqD2soicOipwg5oe5kK6r0kJ5gtJqUhYCMCACN7/t'
    b'C/VdqxVRmReaH1GsFbYqggcl0ix5CDw+Ry8Lokh5AWGirXCUn2RKKN9HKu/H8UEmN4Jy4BCMujLLtqCGyI2A0UAi7wYsKGIF'
    b'bCMAC0sfh5bY8GIts/5uxCLoeQiygkiERPjjUN1LdytAYlxogciMqA4eQKLwVKEycuC8CFw6O8UuGg3iwDSFfXZCxq8v+gZU'
    b'm/nzKG8/hjsKSw1yd60iucrX0j6bkUkvZs7ckdIbu+dnju8sPDVReCTP5dydTibOmb2w5wvHcf3FdHx+7sqRYztTpWbjydRz'
    b'3HPNlaH+aZDdhO1vA7K/v7m4u+3B7P3CbPth7dx5mcEulGUM0ILWLT9xy/wQfJ78Hz7/t+EzBYsjoOTn4WeENa/OqXuyL5HK'
    b'drAfY2eqAOetDew/hLe/NaxkVpT3jeD4t6JaZ4mvjODrtC7LI4qysf15VRmMwi0O2AwMRWUIF/uqKjp5E0OWaZLq+u3gilxl'
    b'D4Grnre5r4FPvwyDjmdfpBL1mEJ6yvv6WPcp0MUAamLznkthPIXTv0EpiBQAUDGBAOEkSahkvANH+LOXwCAxoSzRBT8Gx5nt'
    b'qqd0Qp/jpWCzFNqOhpXFCD9LIsA40JABhCQZfRgGCPuiyICsQK9BMPx5LpJ4FxG2I97Lis+hJmqoj4VDj5Y7ROGRW2YZsd9l'
    b'AS+6jFbsE2t5AQAAYCruM4BPUF2sZdwgvpRSJijHpuvgfq3yQ9bVoVu42OQeDEaqkFCoZE75vCB+SD7iDWDge3mvhn+7vRgy'
    b'k5BJGDrS/bgDITsxvC+SPnN7BFMptma7I51Kly2/HnY8uFHvPnVp6qD0KHkAW5UGmCYhSyDwjIBmy06jhI4rIIW4As+1VcSu'
    b'CkMN7rtCgclDYvk2BiwnGAsiXVjWjrBy+Kjl4dOIqKjVIeM4KUBkTuS54LmnzErPZP1ZkkNW8iG4Z0L44E2mgXL/uDfmpJ/G'
    b'Q8I7tGNO/4IPYZwZRp+rVGamWtiSGAi81yZ2X8rMWwLMZ7EKYdtJ3HybC79E6fPD3ZW4YnTfYPY/BtkbuLMfNn4hYlfKn41c'
    b'T9pSzp35+Xg2HTsjdTZa2N7Z2Vi5k7k7HgHIn9uunLrufOyPJ44aSX96NrHH3ucg9rG9eBay1/anq3cWcCNaKoVCFEcUtn6D'
    b'Md5qkN1ImkPfAxlSrVTUpzlCax3PYCNqI7fLRp3N/hyxEYpLdvuWjyKMpVzjsRMMd42oPq+1r5dw1IAxhzKIUNx696qgGJvC'
    b'rPE1q1C0MkgL/jplUSTxygmKPiAYjHaA/5gAVucJgeAuPJ4Qnuk8mXbzabtW+EOF0/ubq+sfLz/0Sif2fYizjAuELPzAn44Q'
    b'b5H0WEp5mSL1QEPwuGreANWVmatO2IWUV2cn+GWRVEHINxFnvBQaQo1PTyc6fnN6Q3bQHowHFFep4PbMzsjLQQb1vU8CKDq7'
    b'JNux+FP9XijU/fmIQ0pUhkVgMSMCqYLtgYhOMsRND6VaEXSh8MBYzwplv5MgZqyq7EK8X3OTo2aCgucwV6HiogREu3CEJbJd'
    b'guPe3LyrQ6M2jXykjZ36UaJuSp+Kf1Jsp4EPtbKHOmZXBo5wWsgAiUKsk7wf672kZasIuUgOCCYm9ld0n+7jDgJV7tYNGWpx'
    b'2SzqCDWBhFxX5TnMPlYbsZb5emILDmovhS7ADO/tdDzsptAThke5BhMnAgCzhw9kMZ4xF/RqJ5vKwp4uBe1vsrpPsCEJvVqm'
    b'+rh8+RSMqBcjATqBR90vUFOnAVhoK0DVLa1aaxLbsRmRGGr5UDi4ePX6yuCPfeJtvOU9xY0MxqLjlMnOOiRVKq/TYce66jZY'
    b'TBz1MrNO4sMqQRNJ0EcBz6kaUjw7pGRcIPefijtYhNmfHeavkHzYaralslizNhI4jyHBQrwstWe5BHTLVGzWsE1QcnMrGMSI'
    b'fE1VX8/GEIaoUahacjDjWNG8zLl/puJ7WLe1gaKTjbi4xb4oSICjoFCQwJGFmoSdfGDUx5GCUFRmUbcyhIfHlLe6h+BQ2sCk'
    b'n04cLzIEMphGtDQ+81EpWISXlE4IKwGzqlbHGmJJKeIIP8T2eY/y1pEIAG6m6CxartlsYaqYRrxC1niFfZpyoVuBDtgKoaS2'
    b'TLttlMVo55W/U8B96hUllLvJ3SFEtVOwwDB4tHF1eXlpzc+mFnV6sy027S2tgI50oJESKubwTWlpxH92eqm6mnvs76OLN0qC'
    b'7Yq9Uxz+TzGwPcjA2exPwQAb8+qwHmbTPxEbh7Uxb/dBmh7ArzsOs9t1/PTi6IF9c16fzoMNoYEO2X3Y104bZEw778xsf3ci'
    b'SKXg3k4nt4x2W1UsOao+DrZJntK6rm73MExg0AzfcvwbImtQKOXmOXJQ7AFD1R11ncsGB3T7EaH0cJw4ktBmSDztU3poQlwT'
    b'oGHaQRKOjVTP3EzoHZcfPK8z2D+O58ln88z44QkaZl+Z6UOXMZoj7dGRRzZDWY26AIyRkg/vOz3aVyvwv9fxUl13dKY2X8WV'
    b'mnsfDBkP+4K9ODbIPYcKjmnpDkxLa3/Ir4maHG2tTcRgUGxVRY0GnVTnWAyQLZ7XWgaMmnKvM3LqNfG53l/xt4fjyOhZ2e1v'
    b'5iz2XbLrhLyDUY6X56l0zfyljHX34FRjyFM+6JQ36X5FjK8o0K9Mc6EB1J1S1EpDWVDy5TLS0oupFNC14lvlFyfvAg+I/+QD'
    b'KqPi5DVq75Pvk2zDXbFr6oYxzg88Ar51YdLqduMla+sUqzslxNAo5kKL/wJCyJKQaouoNDgbOZ6KssTRdi3qvMBVh6doqN8p'
    b'IeJkhaouQm3enyQNiqR0uxc0BmlP3QOu+lHUiTyg/8pYQbQG4hvvzXtbVM2LYicaDtagdKNn/coN8v74caDDDn8LLRcySnsb'
    b'0PWETIXSNGYfFLdNqamkaRGoXro91kFTE9yHiYO9W/VFd2W3WuSSzZRmAdW1UVXsdL+6eyWo/TL0tQm0OrF7JHmgf1Ld/Gj6'
    b'M7zO4oaRMN442Oth7W7o2Z9liG6uB6x8JTnOOHwbbDzZs4RNzcSPhpXxnpUw8yJxk/DAsmMG9wfnWQNzJ+alVkw+Oj2dLE0j'
    b'gjxe9y9QYqO0lfcoWXPWqelWVfUv3wfI+cLQUnRT7ahnLDDtIX80NP2Jepyit9T9L0PM7rcvURxXNFEIqtpmJ3uaJ+Q+FKz0'
    b'T73NmIZDu5lZ2zMbLutBTnWxieNWhpfdszSnL/fseFKdWF+hyoePw62WUCVQ475egPRQuGvBE7u65xfK3HQdeodWctV70Xiq'
    b'Ib2561W1HZf1NMq0xOsVQVF10LUQSDZtYdUabzrjHNWbrSC29gd76awDnTabikmaz3BHhedWGj82fVHq0mkUVn1WU01SrNeN'
    b'hKP0cK1YB+Ao73XOTphq2eqP1sFeZwR6kXl7Ca/sHDKi3mDTLdupCQd7p7yt3reeUIT7bro1w0TRTClYKDvjrm5CjshkBr1x'
    b'PrXGyfFfCh+yWtd23BmH9Aax3cap2NArqB6ozKsv1mmjbFvL0jTsOflRK1I7vRm9Na1q3anlpGeatl2ay5in7J1AE9ejAn3n'
    b'j+xMtzS1T+NoUf/ChODfpaDOmY6OPFDsjv4gqy1sDFx7W5J7DjFzX7BqTNYiNtNSaj3TjvrQVozdm9B0W6JBZ2mSBwzMMoJb'
    b'Q5JhO5A0fU4aDENDbI463uqqhLuGutUidAtlYlvIT6Z96cDbdZsSO2imYWEMpoB3KiFGMhU1MjRvYnXPcl2KW5dw2uvteyLk'
    b'n3Q2w7qlwTnqOx8mTMMxMnYdNqOEtFhG3xFiXLa6mgybvrM0T8OxPaKOO46kraTuqbdvRPKM+8gh6mL/tcezPzhEncnxmTdS'
    b'tr8YT89mU1fZs8nCnnrefGFPJmeOM7HnzmIxU+cLWxJCndjT+Uza587I96ZyYoaoL4wdaMeD/6cAQvbZOR1R55+lmflAFDJM'
    b'7pfITAZEkS3cvHv36vrN8B93lx9+ZscY0MRllZV6OnP711cgWSS+UNJltGymsCzFE5HrbVjAsAK+AS3+dntzXQM07aCx2gBJ'
    b'6KilWy2dWsQy/ez614ZYC5Yh2fIy6eskNGiDGyPWHnhpcBxFuEzyLSgN5PoQrgPe2BQGsBn4M8+fViZxrPj4lvZc31Nzz5ku'
    b'XB+Kmy1cNZYjbzadTPyRN56P/ImrPMeT5+ezxUIt5pPFfDZyfX88Gc3thXIG5qQEjkoXMkysWNVT0kCjrels3ltaAbf+yoVt'
    b'n5mlcMvAXbkrvO+YgX6NMJPpb37RlqMHiNhae+iKxho14+464OvpGtc1CdX0COqLRDosVzE+iBHNpUdGo4OD8qwNdlL8e2UM'
    b'dWLydbKb1nWQZW8ExeVZrJTHN2kqOo+s/tJWcjJdplE7IZr7pnSzBkKs58b9EXy7AqkqD9BvnL4bVyx9jwDpXJdbOlobKSOO'
    b'8w3Owe3N3YeLS+vN5e3VD9fWzfXbn63rmx+tq3fv316+u7z+8fKNdfPB+sfdq7dX319d6nbDk3j9xe8v/gOzdAoB'
))


def tiny_wasm(*, facts_type=4, configure_type=4, omit=(), extra=(),
              memory=b'\x01\x01\x02', start=None, imported_memory=False):
    """Typed six-export core module; its inert bodies are never executed."""
    types = [b'\x60\x00\x01\x7f', b'\x60\x05' + b'\x7f' * 5 + b'\x01\x7f',
             b'\x60\x01\x7f\x01\x7f', b'\x60\x01\x7f\x00',
             b'\x60\x02\x7f\x7f\x01\x7f']
    result = b'\0asm\x01\0\0\0' + section(1, vector(types))
    if imported_memory:
        result += section(2, vector([wasm_name('host') + wasm_name('memory') + b'\x02' + memory]))
    result += section(3, vector([uleb(i) for i in (0, 1, 2, 3, facts_type, configure_type)]))
    if not imported_memory:
        result += section(5, vector([memory]))
    exports = [('bib_engine_wasm_bridge_v1', 0, 0), ('bib_engine_wasm_dispatch_v1', 0, 1),
               ('malloc', 0, 2), ('free', 0, 3), ('bib_engine_wasm_document_facts_v1', 0, 4),
               ('bib_engine_wasm_document_configure_v1', 0, 5), ('memory', 2, 0)]
    exports = [item for item in exports if item[0] not in omit] + list(extra)
    result += section(7, vector([wasm_name(n) + bytes((k,)) + uleb(i) for n, k, i in exports]))
    if start is not None:
        result += section(8, uleb(start))
    bodies = [b'\x00\x41\x00\x0b'] * 3 + [b'\x00\x0b'] + [b'\x00\x41\x00\x0b'] * 2
    return result + section(10, vector([uleb(len(raw)) + raw for raw in bodies]))


def provider_contract():
    return {'provider_abi': {'major': 1, 'minor': 1}, 'host_abi': {'major': 1, 'minor': 0},
            'getter_maximum_minor': 1, 'target': {'system': 3, 'processor': 3, 'pointer_bits': 32},
            'lifetime': 1, 'maximum_starts': 1,
            'queries': [{'operation': 3, 'maximum_input_bytes': 48, 'required_reply_capacity': 1048576,
                         'capability': '512', 'schema_sha256': DOCUMENT_SHA}],
            'commands': [{'operation': 6, 'maximum_input_bytes': 6246, 'required_reply_capacity': 1048576,
                          'capability': '1024', 'schema_sha256': DOCUMENT_SHA},
                         {'operation': 7, 'maximum_input_bytes': 8, 'required_reply_capacity': 16,
                          'capability': '1024', 'schema_sha256': ACK_SHA}]}


def profile(document_profile, build_hash, recipe_hash):
    value = {'schema_version': 1, 'kind': 'foundation-copied-engine-document-v2',
             'target': 'browser-wasm32', 'binding': BINDING, 'pointer_bits': 32,
             'pthread': False, 'shared_memory': False, 'bridge_abi': 65536,
             'capabilities': '2003' if document_profile == 'physical' else '1795',
             'contract_sha256': CONTRACT_SHA, 'build_sha256': build_hash,
             'source_recipe_sha256': recipe_hash, 'provider_abi_major': 1, 'provider_abi_minor': 1,
             'host_abi_major': 1, 'host_abi_minor': 0, 'document_profile': NAMES[document_profile],
             'base_header_sha256': BASE_SHA, 'extension_header_sha256': EXTENSION_SHA,
             'document_catalog_sha256': CATALOG_SHA, 'document_schema_sha256': DOCUMENT_SHA,
             'action_ack_schema_sha256': ACK_SHA, 'viewport_width': 800, 'viewport_height': 600}
    if document_profile == 'physical':
        value.update(command_catalog_sha256=PHYSICAL_SHA, surface_protocol_version=1,
                     surface_capabilities='8225', mouse_input_version=1, key_mapping_version=1,
                     display_scale=1)
    return value


def bootstrap(value):
    raw = encoded(value)
    return {'worker_epoch': '18446744073709551614',
            'engine_facts': {'export': 'bib_engine_wasm_document_facts_v1',
                             'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                             'observed_output': base64.b64encode(raw).decode('ascii'),
                             'observed_bytes': len(raw), 'observed_result': copy.deepcopy(value)},
            'engine_configure': {'export': 'bib_engine_wasm_document_configure_v1',
                                 'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                                 'worker_lo': 4294967294, 'worker_hi': 4294967295, 'observed_result': 0},
            'marker_before': 0, 'marker_after': 65536, 'describe_profile': copy.deepcopy(value),
            'first_start_worker_epoch': '18446744073709551614',
            'checks': {name: 'passed' for name in BOOTSTRAP_CHECKS}}


class DocumentEngineFixture:
    """Construct an explicitly selected, permanently ineligible inert group."""

    def __init__(self, root, *, document_profile, data=False):
        if type(document_profile) is not str or document_profile not in NAMES:
            raise ValueError('Fixture document profile must be explicitly pixel or physical')
        root = Path(root)
        self.root, self.document_profile = root, document_profile
        self.binary, self.sources = root / 'binary', root / 'sources'
        self.binary.mkdir(parents=True, mode=0o755)
        self.sources.mkdir(mode=0o755)
        self.interfaces = {path: (ROOT / path).read_bytes() for path in INTERFACE_PATHS.values()}
        roles = dict(INTERFACE_PATHS)
        if document_profile == 'physical':
            self.interfaces[PHYSICAL_PATH] = PHYSICAL_CATALOG
            roles['physical_catalog'] = PHYSICAL_PATH
        self.interface_refs = {role: {'path': path, 'sha256': sha(self.interfaces[path])}
                               for role, path in roles.items()}
        inputs = {}
        content = {'archives/wrapper.tar.xz': b'inert wrapper marker\n',
                   'archives/engine.tar.xz': b'inert engine marker\n',
                   NOTICE_PATH: b'Parser fixture only; no engine distribution.\n', **self.interfaces}
        content.update({helper: (ROOT / helper).read_bytes() for helper in manifest.HELPERS})
        for path, raw in content.items():
            write(self.sources, path, raw)
            role = ('interface' if path in self.interfaces else 'helper' if path in manifest.HELPERS
                    else 'license' if path == NOTICE_PATH else 'source')
            inputs[path] = {'sha256': sha(raw), 'role': role, 'mode': 0o644}
        self.toolchain = {'cxx_standard': 23, 'identity_sha256': sha(b'document fixture toolchain'),
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
                          'profile': 'browser-wasm32-cpu-direct-owner-document-v2', 'modularized': True,
                          'esm': True, 'auto_main': False, 'pthread': False, 'shared_memory': False,
                          'fixed_viewport_width': 800, 'fixed_viewport_height': 600,
                          'document_profile': NAMES[document_profile]},
                      'capabilities': '2003' if document_profile == 'physical' else '1795',
                      'bridge_abi': 65536, 'provider_contract': provider_contract()}
        self.profile = profile(document_profile, sha(encoded(self.build)), recipe_hash)
        self.assets = {FACTORY_PATH: FACTORY, WASM_PATH: tiny_wasm()}
        if data:
            self.assets[DATA_PATH] = b'tiny inert font marker'
        self.notices = {NOTICE_PATH: content[NOTICE_PATH]}
        self.reports = {REPORT_PATH: b'Synthetic parser evidence, never actual engine execution.\n'}
        self.asset_records = {path: {'role': 'factory' if path == FACTORY_PATH else 'wasm' if path == WASM_PATH else 'data',
                                    'sha256': sha(raw), 'bytes': len(raw), 'mode': 0o644,
                                    'lookup_name': None if path == FACTORY_PATH else 'engine.wasm' if path == WASM_PATH else 'fonts.bin'}
                              for path, raw in self.assets.items()}
        checks = BASE_CHECKS + DOCUMENT_CHECKS + (PHYSICAL_CHECKS if document_profile == 'physical' else ())
        self.runtime = {'schema_version': 1, 'kind': RUNTIME_KIND, 'scope': 'parser-fixture-only',
                        'status': 'passed', 'recipe_id': recipe_hash, 'provider_build_sha256': sha(encoded(self.build)),
                        'assets_sha256': sha(encoded(self.asset_records)), 'target': copy.deepcopy(TARGET),
                        'paired_sdk_sha256': self.toolchain['paired_sdk_sha256'], 'engine_profile': self.profile,
                        'browser': {'name': 'fixture-not-a-browser', 'version': 'never-run'},
                        'checks': {name: {'status': 'passed', 'evidence': [
                            {'path': REPORT_PATH, 'sha256': sha(self.reports[REPORT_PATH])}]} for name in checks},
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
                (('recipe', 'recipe'), ('manifest', 'binary_manifest'),
                 ('proof', 'proof'), ('runtime', 'runtime'))}

    def export_group(self, destination):
        """Write only the synthetic retained-byte group, never qualify it."""
        return sdk.export_group(self.binary, self.sources, destination)

    def group_arguments(self):
        return {**{'expected_' + key: value for key, value in self.pins().items()},
                'kernel_target': copy.deepcopy(TARGET),
                'paired_sdk': self.toolchain['paired_sdk_sha256'],
                'document_profile': self.document_profile}
