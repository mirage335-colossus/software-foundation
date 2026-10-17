"""Independent inert document-v2 admission fixtures, never runtime qualification.

All reports retain parser-fixture-only scope. The tiny Wasm and ESM members are
inspected as owned bytes; no fixture is instantiated, imported or evaluated.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_document_consumer as consumer
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


class Fixture:
    def __init__(self, root, *, document_profile='pixel', data=False):
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


class DocumentConsumerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-document-consumer-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.fixture = Fixture(self.base / 'fixture')
        self.evidence = self.fixture.evidence()

    def pins(self, evidence=None):
        evidence = self.evidence if evidence is None else evidence
        return {key: sha(evidence[label]) for key, label in
                (('recipe', 'recipe'), ('manifest', 'binary_manifest'), ('proof', 'proof'), ('runtime', 'runtime'))}

    def inspect(self, *, fixture=None, evidence=None, assets=None, notices=None, document_profile=None, **kwargs):
        fixture = self.fixture if fixture is None else fixture
        evidence = fixture.evidence() if evidence is None else evidence
        return consumer.inspect_embedded_consumer(evidence=evidence,
            assets=fixture.assets if assets is None else assets, notices=fixture.notices if notices is None else notices,
            pins=self.pins(evidence), kernel_target=copy.deepcopy(TARGET),
            paired_sdk=fixture.toolchain['paired_sdk_sha256'],
            document_profile=fixture.document_profile if document_profile is None else document_profile, **kwargs)

    def changed(self, key, change, *, evidence=None, raw=None):
        """Rebind enclosing hashes so a changed inner contract reaches admission."""
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        value = json.loads(evidence[key]); change(value)
        evidence[key] = encoded(value) if raw is None else raw
        binary, proof = json.loads(evidence['binary_manifest']), json.loads(evidence['proof'])
        if key == 'provider_build':
            build_hash = sha(evidence[key]); proof['provider_build']['sha256'] = build_hash
            proof['engine_profile']['build_sha256'] = build_hash
            runtime = json.loads(evidence['runtime'])
            runtime['provider_build_sha256'] = build_hash
            runtime['engine_profile']['build_sha256'] = build_hash
            runtime['bootstrap'] = bootstrap(runtime['engine_profile'])
            evidence['runtime'] = encoded(runtime); binary['files'][BUILD_PATH] = build_hash
        if key in ('provider_build', 'runtime'):
            proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
            binary['files'][RUNTIME_PATH] = sha(evidence['runtime'])
        if key != 'proof':
            evidence['proof'] = encoded(proof)
        binary['files'][PROOF_PATH] = sha(evidence['proof'])
        if key != 'binary_manifest':
            evidence['binary_manifest'] = encoded(binary)
        return evidence

    def rebind_source(self, recipe, source, *, evidence=None):
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        evidence['recipe'] = encoded(recipe); recipe_hash = sha(evidence['recipe'])
        source['recipe_id'] = recipe_hash; source['files']['recipe.json'] = recipe_hash
        evidence['source_manifest'] = encoded(source)
        build = json.loads(evidence['provider_build'])
        build.update(source_recipe_sha256=recipe_hash, source_inputs_sha256=sha(encoded(recipe['inputs'])))
        evidence = self.changed('provider_build', lambda value: value.update(build), evidence=evidence)
        proof = json.loads(evidence['proof'])
        proof.update(recipe_id=recipe_hash, sources_sha256=sha(evidence['source_manifest']))
        proof['engine_profile']['source_recipe_sha256'] = recipe_hash
        runtime = json.loads(evidence['runtime'])
        runtime.update(recipe_id=recipe_hash, engine_profile=copy.deepcopy(proof['engine_profile']))
        runtime['bootstrap'] = bootstrap(runtime['engine_profile'])
        evidence['runtime'] = encoded(runtime); proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
        evidence['proof'] = encoded(proof)
        binary = json.loads(evidence['binary_manifest'])
        binary.update(recipe_id=recipe_hash, sources_sha256=sha(evidence['source_manifest']), provider={
            **recipe['provider'], 'entry': FACTORY_PATH, 'assets': sorted(self.fixture.assets)})
        for path, label in ((BUILD_PATH, 'provider_build'), (PROOF_PATH, 'proof'), (RUNTIME_PATH, 'runtime')):
            binary['files'][path] = sha(evidence[label])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def with_assets(self, assets, records, *, evidence=None):
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        proof = json.loads(evidence['proof']); proof['assets'] = records
        proof['wasm_facts'] = scan_wasm(assets[WASM_PATH])
        runtime = json.loads(evidence['runtime']); runtime['assets_sha256'] = sha(encoded(records))
        evidence['runtime'] = encoded(runtime); proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
        evidence['proof'] = encoded(proof)
        binary = json.loads(evidence['binary_manifest']); binary['provider']['assets'] = sorted(assets)
        for path, raw in assets.items():
            binary['files'][path] = sha(raw); binary['modes'][path] = records[path]['mode']
        binary['files'][RUNTIME_PATH] = sha(evidence['runtime']); binary['files'][PROOF_PATH] = sha(evidence['proof'])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def group(self, fixture=None, name='group'):
        fixture = self.fixture if fixture is None else fixture
        group = self.base / name
        sdk.export_group(fixture.binary, fixture.sources, group)
        return group

    def group_arguments(self, fixture=None):
        fixture = self.fixture if fixture is None else fixture
        return {**{'expected_' + key: value for key, value in self.pins(fixture.evidence()).items()},
                'kernel_target': copy.deepcopy(TARGET), 'paired_sdk': fixture.toolchain['paired_sdk_sha256'],
                'document_profile': fixture.document_profile}

    def test_embedded_profiles_have_exact_scopes_pins_and_base_header_alias(self):
        for mode in ('pixel', 'physical'):
            fixture = self.fixture if mode == 'pixel' else Fixture(self.base / 'physical', document_profile=mode)
            result = self.inspect(fixture=fixture); metadata = result.as_dict()
            with self.subTest(mode=mode):
                self.assertEqual(metadata['scope'], 'embedded-retained-document-v2-consumer-byte-and-static-contract-only')
                self.assertFalse(metadata['whole_group_verified']); self.assertIsNone(metadata['group_files'])
                self.assertFalse(metadata['production_eligible'])
                self.assertEqual(len(metadata['engine_profile']), 24 if mode == 'pixel' else 30)
                self.assertEqual(metadata['interfaces']['base_header']['path'], HEADER)
                self.assertEqual(metadata['provider_contract'], provider_contract())
                self.assertEqual(dict(result.evidence['interfaces']), fixture.interfaces)
                self.assertEqual(sha(fixture.interfaces[INTERFACE_PATHS['contract']]), CONTRACT_SHA)
                if mode == 'physical':
                    self.assertEqual(sha(PHYSICAL_CATALOG), PHYSICAL_SHA)
                    self.assertIn('physical_catalog', metadata['interfaces'])

    def test_complete_group_is_verified_and_fixture_verify_refuses_both_modes(self):
        for mode in ('pixel', 'physical'):
            fixture = self.fixture if mode == 'pixel' else Fixture(self.base / 'physical', document_profile=mode)
            group = self.group(fixture, 'group-' + mode); args = self.group_arguments(fixture)
            result = consumer.inspect_kernel_consumer(group, **args)
            with self.subTest(mode=mode):
                self.assertEqual(result.metadata['scope'], 'retained-document-v2-consumer-byte-and-static-contract-only')
                self.assertTrue(result.metadata['whole_group_verified'])
                self.assertEqual(set(result.metadata['group_files']), set(sdk.group_names(sha(encoded(fixture.recipe)))))
                self.assertFalse(result.metadata['production_eligible'])
                with self.assertRaisesRegex(ValueError, 'ineligible'):
                    consumer.verify_kernel_consumer(group, **args)

    def test_selector_is_required_closed_and_cannot_be_inferred_from_shared_binding(self):
        for mode in (None, '', True, '1795', 'PIXEL', 'pixel ', 'none'):
            with self.subTest(mode=mode), self.assertRaises((ValueError, TypeError)):
                self.inspect(document_profile=mode) if mode is not None else consumer.validate_engine_profile(self.fixture.profile, document_profile=None)
        with self.assertRaises(TypeError):
            consumer.validate_engine_profile(self.fixture.profile)
        with self.assertRaises(ValueError):
            self.inspect(document_profile='physical')
        physical = Fixture(self.base / 'physical', document_profile='physical')
        with self.assertRaises(ValueError):
            self.inspect(fixture=physical, document_profile='pixel')

    def test_owned_results_and_json_copies_do_not_follow_caller_mutation(self):
        evidence = copy.deepcopy(self.evidence); assets = dict(self.fixture.assets)
        result = self.inspect(evidence=evidence, assets=assets)
        original = result.evidence['interfaces'][HEADER]
        evidence['interfaces'][HEADER] = b'changed'; evidence['reports'][REPORT_PATH] = b'changed'
        assets[WASM_PATH] = b'changed'
        self.assertEqual(result.evidence['interfaces'][HEADER], original)
        self.assertEqual(result.assets[WASM_PATH], self.fixture.assets[WASM_PATH])
        for mapping in (result.metadata, result.evidence, result.evidence['interfaces'], result.evidence['reports']):
            with self.assertRaises(TypeError):
                mapping['injected'] = b'changed'
        exported = result.as_dict(); exported['provider_contract']['queries'][0]['operation'] = 99
        self.assertEqual(result.as_dict()['provider_contract']['queries'][0]['operation'], 3)

    def test_report_and_interface_mappings_are_snapshotted_once(self):
        from collections.abc import Mapping

        class Changing(Mapping):
            def __init__(self, original):
                self.original, self.reads = original, {}
            def __iter__(self):
                return iter(self.original)
            def __len__(self):
                return len(self.original)
            def __getitem__(self, key):
                self.reads[key] = self.reads.get(key, 0) + 1
                return self.original[key] if self.reads[key] == 1 else b'changed after first read'

        evidence = copy.deepcopy(self.evidence)
        evidence['reports'] = Changing(self.fixture.reports)
        evidence['interfaces'] = Changing(self.fixture.interfaces)
        result = self.inspect(evidence=evidence)
        self.assertEqual(dict(result.evidence['reports']), self.fixture.reports)
        self.assertEqual(dict(result.evidence['interfaces']), self.fixture.interfaces)

    def test_each_independent_pin_and_exact_original_bytes_are_required(self):
        for key in self.pins():
            for changed in ('0' * 64, self.pins()[key].upper(), None):
                pins = self.pins(); pins[key] = changed
                with self.subTest(key=key, pin=changed), self.assertRaises((ValueError, TypeError)):
                    consumer.inspect_embedded_consumer(evidence=self.evidence, assets=self.fixture.assets,
                        notices=self.fixture.notices, pins=pins, kernel_target=TARGET,
                        paired_sdk=self.fixture.toolchain['paired_sdk_sha256'], document_profile='pixel')
        evidence = copy.deepcopy(self.evidence); evidence['proof'] += b'\n'
        with self.assertRaises(ValueError):
            consumer.inspect_embedded_consumer(evidence=evidence, assets=self.fixture.assets,
                notices=self.fixture.notices, pins=self.pins(), kernel_target=TARGET,
                paired_sdk=self.fixture.toolchain['paired_sdk_sha256'], document_profile='pixel')

    def test_legacy_proof_build_and_runtime_kinds_do_not_upgrade_by_rehashing(self):
        legacy = {'proof': ('foundation-neutral-engine-provider-proof-v1', 'foundation-neutral-engine-provider-physical-proof-v1'),
                  'provider_build': ('foundation-neutral-engine-provider-build-v1', 'foundation-neutral-engine-provider-physical-build-v1'),
                  'runtime': ('foundation-neutral-engine-runtime-evidence-v1', 'foundation-neutral-engine-physical-runtime-evidence-v1')}
        for key, kinds in legacy.items():
            for kind in kinds:
                with self.subTest(key=key, kind=kind), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed(key, lambda value: value.update(kind=kind)))

    def test_document_evidence_and_document_fields_are_closed(self):
        for key in ('proof', 'provider_build', 'runtime'):
            for mutation in (lambda value: value.pop('kind'), lambda value: value.update(extra=True),
                             lambda value: value.update(schema_version=True)):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed(key, mutation))
        for key in ('interfaces', 'reports'):
            evidence = copy.deepcopy(self.evidence); evidence.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(evidence=evidence)
        evidence = copy.deepcopy(self.evidence); evidence['extra'] = b''
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)

    def test_strict_json_refuses_duplicate_nonfinite_bom_and_invalid_unicode(self):
        original = self.evidence['runtime']
        for raw in (b'{"kind":"duplicate",' + original[1:],
                    original.replace(b'"schema_version": 1', b'"schema_version": NaN'),
                    b'\xef\xbb\xbf' + original,
                    original.replace(b'fixture-not-a-browser', b'\\ud800')):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                self.assertNotEqual(raw, original)
                self.inspect(evidence=self.changed('runtime', lambda value: None, raw=raw))

    def test_source_build_profile_target_sdk_and_provider_abi_joins_are_exact(self):
        for mutation in (lambda value: value.update(contract_header_sha256=BASE_SHA),
                         lambda value: value.update(source_inputs_sha256='f' * 64),
                         lambda value: value['configuration'].update(document_profile=NAMES['physical']),
                         lambda value: value['configuration'].update(fixed_viewport_width=True),
                         lambda value: value.update(capabilities='259')):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('provider_build', mutation))
        for key, changed in (('abi_minor', 0), ('abi_minor', True), ('binding', 'linked-owner')):
            recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
            recipe['provider'][key] = changed
            with self.subTest(key=key, value=changed), self.assertRaises(ValueError):
                self.inspect(evidence=self.rebind_source(recipe, source))
        for target, paired in (({**TARGET, 'processor': 'x86_64'}, self.fixture.toolchain['paired_sdk_sha256']),
                               (TARGET, 'f' * 64)):
            with self.subTest(target=target, sdk=paired), self.assertRaises(ValueError):
                consumer.inspect_embedded_consumer(evidence=self.evidence, assets=self.fixture.assets,
                    notices=self.fixture.notices, pins=self.pins(), kernel_target=target,
                    paired_sdk=paired, document_profile='pixel')

    def test_fixed_provider_contract_and_observation_are_typed_and_exact(self):
        mutations = (lambda value: value['provider_abi'].update(minor=0),
                     lambda value: value.update(getter_maximum_minor=True),
                     lambda value: value['queries'][0].update(required_reply_capacity=1048575),
                     lambda value: value['commands'][0].update(maximum_input_bytes=33120),
                     lambda value: value['commands'][1].update(required_reply_capacity=104),
                     lambda value: value['commands'][1].update(schema_sha256=DOCUMENT_SHA))
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('provider_build', lambda value: mutation(value['provider_contract'])))
        for mutation in (lambda value: value.update(getter_maximum_minor=0),
                         lambda value: value['contract']['commands'][0].update(operation=7),
                         lambda value: value.update(extra=True)):
            with self.subTest(observation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: mutation(value['provider_observation'])))

    def test_interface_roles_bytes_and_reference_shapes_are_exact(self):
        for role, path in INTERFACE_PATHS.items():
            for mutation in (lambda value: value['interfaces'].pop(role),
                             lambda value: value['interfaces'][role].update(sha256='f' * 64),
                             lambda value: value['interfaces'][role].update(extra=True)):
                with self.subTest(role=role, mutation=mutation), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed('proof', mutation))
            evidence = copy.deepcopy(self.evidence); evidence['interfaces'][path] += b'\n'
            with self.subTest(role=role, changed_bytes=True), self.assertRaises(ValueError):
                self.inspect(evidence=evidence)
        evidence = copy.deepcopy(self.evidence); evidence['interfaces']['extra.json'] = b'{}'
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)

    def test_interfaces_join_same_binary_source_and_recipe_path_and_hash(self):
        path = INTERFACE_PATHS['extension_header']
        with self.assertRaises(ValueError):
            self.inspect(evidence=self.changed('binary_manifest', lambda value: value['files'].update({path: 'f' * 64})))
        for missing in (True, False):
            recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
            if missing:
                recipe['inputs'].pop(path); source['files'].pop(path); source['modes'].pop(path)
            else:
                recipe['inputs'][path]['sha256'] = 'f' * 64; source['files'][path] = 'f' * 64
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.inspect(evidence=self.rebind_source(recipe, source))
        recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
        recipe['inputs'][path]['role'] = 'source'
        with self.assertRaisesRegex(ValueError, 'interface inventory'):
            self.inspect(evidence=self.rebind_source(recipe, source))

    def test_interface_metadata_asset_notice_and_report_aliases_reject(self):
        physical = Fixture(self.base / 'physical', document_profile='physical')
        original = physical.evidence()
        for path in (HEADER, PROOF_PATH, BUILD_PATH, RUNTIME_PATH, FACTORY_PATH, WASM_PATH, NOTICE_PATH,
                     INTERFACE_PATHS['extension_header']):
            evidence = self.changed('proof', lambda value: value['interfaces']['physical_catalog'].update(path=path), evidence=original)
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.inspect(fixture=physical, evidence=evidence)
        path = INTERFACE_PATHS['action_ack_schema']
        evidence = self.changed('runtime', lambda value: [check.update(evidence=[{'path': path, 'sha256': ACK_SHA}])
                                                        for check in value['checks'].values()])
        evidence['reports'] = {path: self.fixture.interfaces[path]}
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)

    def test_interface_member_bound_is_measured_before_runtime_asset_reads(self):
        path = INTERFACE_PATHS['extension_header']
        write(self.fixture.binary, path, b'x' * (65536 + 1))
        self.fixture.binary_manifest.update(manifest.tree_inventory(self.fixture.binary, 'engine-sdk.json'))
        write(self.fixture.binary, 'engine-sdk.json', encoded(self.fixture.binary_manifest))
        group = self.group(name='oversized-interface'); materialized = []
        original = consumer._read_members
        def read(archive, wanted, **kwargs):
            materialized.extend(set(wanted) & set(self.fixture.assets))
            return original(archive, wanted, **kwargs)
        with mock.patch.object(consumer, '_read_members', side_effect=read), self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.group_arguments())
        self.assertEqual(materialized, [])

    def test_bootstrap_worker64_exports_signature_markers_and_order_are_exact(self):
        mutations = (lambda value: value.update(worker_epoch='18446744073709551616'),
                     lambda value: value.update(worker_epoch='018446744073709551614'),
                     lambda value: value.update(first_start_worker_epoch='1'),
                     lambda value: value['engine_configure'].update(worker_hi=2147483647),
                     lambda value: value['engine_configure'].update(observed_result=1),
                     lambda value: value['engine_configure'].update(export='bib_engine_wasm_dispatch_v1'),
                     lambda value: value['engine_facts']['signature'].update(params=['i32']),
                     lambda value: value.update(marker_before=65536),
                     lambda value: value.update(marker_after=True),
                     lambda value: value['checks'].update(configure_before_describe=True),
                     lambda value: value['checks'].update(extra='passed'))
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: mutation(value['bootstrap'])))

    def test_failed_or_unexecuted_bootstrap_checks_are_preserved_and_ineligible(self):
        for status in ('failed', 'not-run'):
            evidence = self.changed('runtime', lambda value: value['bootstrap']['checks'].update(configure_before_describe=status))
            result = self.inspect(evidence=evidence)
            with self.subTest(status=status):
                self.assertFalse(result.metadata['production_eligible'])
                self.assertEqual(result.as_dict()['runtime_evidence']['bootstrap']['checks']['configure_before_describe'], status)

    def test_pure_eligibility_predicate_requires_all_original_and_bootstrap_checks(self):
        # This unretained Boolean probe is never inspected or sealed as evidence.
        runtime = copy.deepcopy(self.fixture.runtime)
        runtime['scope'] = 'retained-neutral-provider-runtime'
        self.assertTrue(consumer._production_eligible(runtime))
        for status in ('failed', 'not-run'):
            for check in BOOTSTRAP_CHECKS:
                value = copy.deepcopy(runtime); value['bootstrap']['checks'][check] = status
                with self.subTest(bootstrap=check, status=status):
                    self.assertFalse(consumer._production_eligible(value))
            value = copy.deepcopy(runtime); value['checks'][DOCUMENT_CHECKS[-1]]['status'] = status
            with self.subTest(runtime=status):
                self.assertFalse(consumer._production_eligible(value))
        runtime['scope'] = 'parser-fixture-only'
        self.assertFalse(consumer._production_eligible(runtime))

    def test_facts_preserve_original_whitespace_and_key_order_bytes(self):
        raw = json.dumps(self.fixture.profile, indent=1).encode('utf-8')
        def observed(value):
            value['bootstrap']['engine_facts'].update(observed_output=base64.b64encode(raw).decode('ascii'), observed_bytes=len(raw))
        evidence = self.changed('runtime', observed)
        result = self.inspect(evidence=evidence)
        retained = result.as_dict()['runtime_evidence']['bootstrap']['engine_facts']
        self.assertEqual(base64.b64decode(retained['observed_output']), raw)
        self.assertEqual(retained['observed_bytes'], len(raw))

    def test_bootstrap_facts_use_exact_count_strict_base64_utf8_and_profile_join(self):
        for raw in (b'\xef\xbb\xbf' + encoded(self.fixture.profile), encoded(self.fixture.profile) + b'\0',
                    b'\xff', b'{"schema_version":1,"schema_version":1}', b'x' * 4096):
            def mutate(value):
                facts = value['bootstrap']['engine_facts']
                facts.update(observed_output=base64.b64encode(raw).decode('ascii'), observed_bytes=len(raw))
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', mutate))
        for mutation in (lambda value: value['engine_facts'].update(observed_bytes=True),
                         lambda value: value['engine_facts'].update(observed_result=0),
                         lambda value: value['engine_facts'].update(observed_output='!!!!'),
                         lambda value: value['describe_profile'].update(build_sha256='f' * 64)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: mutation(value['bootstrap'])))

    def test_document_and_current_physical_checks_require_original_reports(self):
        for mode in ('pixel', 'physical'):
            fixture = self.fixture if mode == 'pixel' else Fixture(self.base / 'physical', document_profile=mode)
            evidence = fixture.evidence()
            required = DOCUMENT_CHECKS + (PHYSICAL_CHECKS if mode == 'physical' else ())
            for name in required:
                with self.subTest(mode=mode, missing=name), self.assertRaises(ValueError):
                    self.inspect(fixture=fixture, evidence=self.changed('runtime', lambda value: value['checks'].pop(name), evidence=evidence))
            name = required[-1]
            changed = self.changed('runtime', lambda value: value['checks'][name].update(status='not-run', evidence=[]), evidence=evidence)
            result = self.inspect(fixture=fixture, evidence=changed)
            self.assertFalse(result.metadata['production_eligible'])
            self.assertEqual(result.as_dict()['runtime_evidence']['checks'][name]['status'], 'not-run')
            with self.assertRaises(ValueError):
                self.inspect(fixture=fixture, evidence=self.changed('runtime', lambda value: value['checks'][name].update(evidence=[]), evidence=evidence))

    def test_report_notice_and_status_closure_cannot_be_replaced_by_passed_strings(self):
        for mutation in (lambda value: value.update(checks={'passed': True}),
                         lambda value: value['checks'][DOCUMENT_CHECKS[0]].update(extra=True),
                         lambda value: value['checks'][DOCUMENT_CHECKS[0]]['evidence'][0].update(sha256='f' * 64)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', mutation))
        for key in ('reports', 'interfaces'):
            evidence = copy.deepcopy(self.evidence); evidence[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(evidence=evidence)
        with self.assertRaises(ValueError):
            self.inspect(notices={})
        evidence = copy.deepcopy(self.evidence); evidence['reports']['extra.txt'] = b'unreferenced'
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)
        for status in ('failed', 'incomplete'):
            result = self.inspect(evidence=self.changed('runtime', lambda value: value.update(status=status)))
            self.assertFalse(result.metadata['production_eligible'])

    def test_actual_wasm_document_exports_are_required_even_with_rehashed_facts(self):
        variants = (tiny_wasm(facts_type=0), tiny_wasm(configure_type=1),
                    tiny_wasm(omit=('bib_engine_wasm_document_facts_v1',)),
                    tiny_wasm(omit=('bib_engine_wasm_document_configure_v1',)),
                    tiny_wasm(start=0), tiny_wasm(memory=b'\x03\x01\x02'),
                    tiny_wasm(extra=(('main', 0, 0),)))
        for wasm in variants:
            assets = {**self.fixture.assets, WASM_PATH: wasm}; records = copy.deepcopy(self.fixture.asset_records)
            records[WASM_PATH].update(sha256=sha(wasm), bytes=len(wasm))
            with self.subTest(wasm=sha(wasm)), self.assertRaises(ValueError):
                self.inspect(evidence=self.with_assets(assets, records), assets=assets)

    def test_finite_private_factory_imported_memory_preserves_origin_and_fixture_scope(self):
        wasm = tiny_wasm(imported_memory=True)
        assets = {**self.fixture.assets, WASM_PATH: wasm}
        records = copy.deepcopy(self.fixture.asset_records)
        records[WASM_PATH].update(sha256=sha(wasm), bytes=len(wasm))
        result = self.inspect(evidence=self.with_assets(assets, records), assets=assets)
        memory = result.as_dict()['wasm_facts']['memories']
        self.assertEqual(len(memory), 1)
        self.assertTrue(memory[0]['imported'])
        self.assertFalse(memory[0]['shared'])
        self.assertFalse(memory[0]['memory64'])
        self.assertEqual(memory[0]['maximum'], 2)
        self.assertEqual(result.as_dict()['runtime_evidence']['scope'], 'parser-fixture-only')
        self.assertFalse(result.metadata['production_eligible'])

    def test_factory_dependency_and_bootstrap_execution_are_not_inert(self):
        for raw in (b'import "side-effect.mjs";\n' + FACTORY,
                    FACTORY + b'\ncallMain([]);\n',
                    FACTORY + b'\nawait import("remote.mjs");\n'):
            assets = {**self.fixture.assets, FACTORY_PATH: raw}; records = copy.deepcopy(self.fixture.asset_records)
            records[FACTORY_PATH].update(sha256=sha(raw), bytes=len(raw))
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                evidence = self.with_assets(assets, records)
                self.inspect(evidence=evidence, assets=assets)

    def test_asset_roles_lookup_names_and_measured_bounds_are_enforced(self):
        for mutation in (lambda value: value[WASM_PATH].update(bytes=True),
                         lambda value: value[WASM_PATH].update(lookup_name='../engine.wasm'),
                         lambda value: value[FACTORY_PATH].update(role='wasm'),
                         lambda value: value[WASM_PATH].update(mode=True)):
            records = copy.deepcopy(self.fixture.asset_records); mutation(records)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.with_assets(self.fixture.assets, records))
        for limits in (consumer.ConsumerLimits(max_factory_bytes=len(FACTORY)-1),
                       consumer.ConsumerLimits(max_wasm_bytes=len(self.fixture.assets[WASM_PATH])-1),
                       consumer.ConsumerLimits(max_reports_total_bytes=len(self.fixture.reports[REPORT_PATH])-1),
                       consumer.ConsumerLimits(max_notices_total_bytes=len(self.fixture.notices[NOTICE_PATH])-1)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.inspect(limits=limits)
        self.inspect(limits=consumer.ConsumerLimits(max_factory_bytes=len(FACTORY),
                     max_wasm_bytes=len(self.fixture.assets[WASM_PATH]),
                     max_reports_total_bytes=len(self.fixture.reports[REPORT_PATH]),
                     max_notices_total_bytes=len(self.fixture.notices[NOTICE_PATH])))

    def test_full_group_data_aggregate_refuses_before_runtime_asset_materialization(self):
        fixture = Fixture(self.base / 'data', data=True); group = self.group(fixture, 'data-group')
        materialized = []; original = consumer._read_members
        def read(archive, wanted, **kwargs):
            materialized.extend(set(wanted) & set(fixture.assets))
            return original(archive, wanted, **kwargs)
        with mock.patch.object(consumer, '_read_members', side_effect=read), self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.group_arguments(fixture),
                limits=consumer.ConsumerLimits(max_data_total_bytes=len(fixture.assets[DATA_PATH])-1))
        self.assertEqual(materialized, [])

    def test_full_group_postflight_snapshot_and_stage_a_inventory_are_required(self):
        group = self.group(); original = sdk.group_snapshot; verify = sdk.verify_group; calls = []
        verified = False
        def complete(*args, **kwargs):
            nonlocal verified
            result = verify(*args, **kwargs); verified = True
            return result
        def changed(*args, **kwargs):
            value = original(*args, **kwargs); calls.append(value)
            return {**value, 'injected': 'f' * 64} if verified else value
        with mock.patch.object(sdk, 'group_snapshot', side_effect=changed), mock.patch.object(sdk, 'verify_group', side_effect=complete), self.assertRaisesRegex(ValueError, 'changed'):
            consumer.inspect_kernel_consumer(group, **self.group_arguments())
        self.assertGreaterEqual(len(calls), 3)
        (group / 'unlisted-file').write_bytes(b'not in closed group')
        with self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.group_arguments())

    def test_consumer_never_executes_or_extracts_retained_inputs(self):
        group = self.group()
        with mock.patch('subprocess.run', side_effect=AssertionError('no subprocess')), mock.patch('subprocess.Popen', side_effect=AssertionError('no subprocess')), mock.patch('tarfile.TarFile.extractall', side_effect=AssertionError('no extraction')):
            result = consumer.inspect_kernel_consumer(group, **self.group_arguments())
        self.assertFalse(result.metadata['production_eligible'])

    def test_invalid_stage_a_checksum_prevents_all_consumer_member_reads(self):
        group = self.group(); checksum = sdk.group_names(sha(encoded(self.fixture.recipe)))[2]
        (group / checksum).write_bytes(b'invalid checksum file\n')
        with mock.patch.object(consumer, '_read_members', side_effect=AssertionError('consumer read before Stage A')), self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.group_arguments())


if __name__ == '__main__':
    unittest.main()
