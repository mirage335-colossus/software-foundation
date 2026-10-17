"""Tiny inert consumer-contract fixtures; never provider runtime qualification.

Every artifact report deliberately says parser-fixture-only. Wasm/glue bytes are
inspected, never instantiated, imported, evaluated or compiled by this suite.
"""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_consumer as consumer
import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from dependency_archive import encoded


def sha(content):
    return hashlib.sha256(content).hexdigest()


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in path.parents:
        if parent == root:
            break
        parent.chmod(0o755)
    path.write_bytes(content)
    path.chmod(0o644)


def uleb(value):
    out = bytearray()
    while True:
        byte, value = value & 127, value >> 7
        out.append(byte | (128 if value else 0))
        if not value:
            return bytes(out)


def name(value):
    content = value.encode('utf-8')
    return uleb(len(content)) + content


def section(kind, content):
    return bytes([kind]) + uleb(len(content)) + content


def vector(items):
    return uleb(len(items)) + b''.join(items)


MAGIC = b'\0asm\x01\0\0\0'
FACTORY = b'export default async function createEngine(options = {}) { return options; }\n'
CHECKS = ('factory-inert', 'copied-describe', 'offline-entry-resource-load',
          'native-service-result-and-ack', 'outside-engine-owner-pump',
          'opaque-raster-frame', 'worker-failure-close', 'separate-heaps-copied-bridge')
HEADER = 'include/foundation/appended/engine_provider.h'
FACTORY_PATH = 'runtime/engine.mjs'
WASM_PATH = 'runtime/engine.wasm'
BUILD_PATH = 'evidence/provider-build.json'
PROOF_PATH = 'evidence/provider-proof.json'
RUNTIME_PATH = 'evidence/runtime.json'
REPORT_PATH = 'evidence/parser-cases.txt'
NOTICE_PATH = 'licenses/NOTICE.txt'
CATALOG_PATH = 'catalog.json'
# Exact reviewed source-design catalog bytes, retained here without depending on
# an ignored supplier checkout. This is not an engine/runtime fixture or proof.
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
PHYSICAL_FACTS = {'command_catalog_sha256': 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
    'surface_protocol_version': 1, 'surface_capabilities': '8225', 'mouse_input_version': 1,
    'key_mapping_version': 1, 'viewport_width': 800, 'viewport_height': 600, 'display_scale': 1}
PHYSICAL_CHECKS = CHECKS + ('raw-key-location-altgraph', 'mouse-five-buttons-context-cancel',
    'input-context-navigation-retirement', 'native-effect-input-admission')
TARGET = {'system': 'Emscripten', 'processor': 'wasm32',
          'triple': 'wasm32-unknown-emscripten', 'pointer_bits': 32}


def tiny_wasm(*, imported=False, extra_exports=(), memory=b'\x01\x01\x02',
              start=None, dispatch_type=1, code=b'\x00\x41\x00\x0b'):
    """Typed core module with four copied-bridge function exports and memory.

    The optional imported function precedes definitions to exercise actual
    function-index resolution. Bodies are intentionally opaque to the scanner.
    """
    types = [b'\x60\x00\x01\x7f', b'\x60\x05' + b'\x7f'*5 + b'\x01\x7f',
             b'\x60\x01\x7f\x01\x7f', b'\x60\x01\x7f\x00']
    result = MAGIC + section(1, vector(types))
    offset = int(imported)
    if imported:
        result += section(2, vector([name('host') + name('copied_callback') + b'\x00\x00']))
    result += section(3, vector([uleb(i) for i in (0, dispatch_type, 2, 3)]))
    result += section(5, vector([memory]))
    exports = [('bib_engine_wasm_bridge_v1', 0, offset),
               ('bib_engine_wasm_dispatch_v1', 0, offset+1),
               ('malloc', 0, offset+2), ('free', 0, offset+3), ('memory', 2, 0)]
    exports += list(extra_exports)
    result += section(7, vector([name(n)+bytes([k])+uleb(i) for n, k, i in exports]))
    if start is not None:
        result += section(8, uleb(start))
    # Free has no result; these bytes are only an inert fixture, never executed.
    bodies = [code, code, code, b'\x00\x0b']
    return result + section(10, vector([uleb(len(body))+body for body in bodies]))


class Fixture:
    def __init__(self, root, *, data=False, physical_input=False):
        self.root = root
        self.physical_input = physical_input
        self.binary, self.sources = root/'binary', root/'sources'
        self.binary.mkdir(parents=True, mode=0o755)
        self.sources.mkdir(mode=0o755)
        header = (ROOT/HEADER).read_bytes()
        inputs = {}
        for path, content, role in (
                ('archives/wrapper.tar.xz', b'inert wrapper marker\n', 'source'),
                ('archives/engine.tar.xz', b'inert engine marker\n', 'source'),
                (NOTICE_PATH, b'Parser fixture only; no engine distribution.\n', 'license'),
                (HEADER, header, 'interface')) + (((CATALOG_PATH, PHYSICAL_CATALOG, 'interface'),) if physical_input else ()):
            write(self.sources, path, content)
            inputs[path] = {'sha256': sha(content), 'role': role, 'mode': 0o644}
        for helper in manifest.HELPERS:
            content = (ROOT/helper).read_bytes()
            write(self.sources, helper, content)
            inputs[helper] = {'sha256': sha(content), 'role': 'helper', 'mode': 0o644}
        self.toolchain = {'cxx_standard': 23, 'identity_sha256': sha(b'fixture toolchain'),
                          'runtime_policy': 'paired-emscripten',
                          'paired_sdk_sha256': sha(b'fixture consuming SDK'),
                          'target_baseline': 'parser fixture; no qualified runtime'}
        self.options = {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'}
        self.provider = {'format': 'browser-module', 'binding': 'copied-owner-bridge',
                         'abi_major': 1, 'abi_minor': 0, 'header': HEADER,
                         'header_sha256': sha(header)}
        self.recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe',
                       'producer_version': 1, 'target': copy.deepcopy(TARGET),
                       'toolchain': copy.deepcopy(self.toolchain), 'options': self.options,
                       'provider': self.provider, 'suppliers': {
                           key: {'repository': 'https://example.invalid/'+key,
                                 'commit': digit*40, 'archive': 'archives/'+key+'.tar.xz'}
                           for key, digit in (('wrapper', '1'), ('engine', '2'))},
                       'inputs': inputs, 'patches': [], 'licenses': [NOTICE_PATH]}
        write(self.sources, 'recipe.json', encoded(self.recipe))
        self.recipe_id = sha(encoded(self.recipe))
        self.source = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
                       'producer_version': 1, 'recipe_id': self.recipe_id,
                       **manifest.tree_inventory(self.sources, 'sources.json')}
        write(self.sources, 'sources.json', encoded(self.source))
        self.assets = {FACTORY_PATH: FACTORY, WASM_PATH: tiny_wasm()}
        if data:
            self.assets['runtime/data/fonts.bin'] = b'tiny font marker'
        self.notices = {NOTICE_PATH: (self.sources/NOTICE_PATH).read_bytes()}
        self.reports = {REPORT_PATH: b'Synthetic parser evidence, never runtime execution.\n'}
        self.build = {'schema_version': 1, 'kind': 'foundation-neutral-engine-provider-build-v1',
                      'target': copy.deepcopy(TARGET), 'toolchain': copy.deepcopy(self.toolchain),
                      'options': self.options, 'source_recipe_sha256': self.recipe_id,
                      'source_inputs_sha256': sha(encoded(inputs)),
                      'contract_header_sha256': sha(header),
                      'binding': 'copied-owner-bridge/direct-worker-v1',
                      'configuration': {'profile': 'browser-wasm32-cpu-direct-owner-v1',
                                        'modularized': True, 'esm': True, 'auto_main': False,
                                        'pthread': False, 'shared_memory': False,
                                        'fixed_viewport_width': 800, 'fixed_viewport_height': 600},
                      'capabilities': '259', 'bridge_abi': 65536}
        if physical_input:
            self.build.update(kind='foundation-neutral-engine-provider-physical-build-v1',
                              binding='copied-owner-bridge/direct-worker-physical-v1', capabilities='467', **PHYSICAL_FACTS)
            self.build['configuration']['profile'] = 'browser-wasm32-cpu-direct-owner-physical-v1'
        self.profile = {'schema_version': 1, 'kind': 'foundation-copied-engine-v1',
                        'target': 'browser-wasm32', 'binding': 'copied-owner-bridge/direct-worker-v1',
                        'pointer_bits': 32, 'pthread': False, 'shared_memory': False,
                        'bridge_abi': 65536, 'capabilities': '259',
                        'contract_sha256': sha(header), 'build_sha256': sha(encoded(self.build)),
                        'source_recipe_sha256': self.recipe_id}
        if physical_input:
            self.profile.update(kind='foundation-copied-engine-physical-v1',
                                binding='copied-owner-bridge/direct-worker-physical-v1', capabilities='467', **PHYSICAL_FACTS)
        self.asset_metadata = {path: {'role': 'factory' if path == FACTORY_PATH else
                                     'wasm' if path == WASM_PATH else 'data',
                                     'sha256': sha(content), 'bytes': len(content), 'mode': 0o644,
                                     'lookup_name': 'fonts.bin' if path.endswith('fonts.bin') else
                                                    'engine.wasm' if path == WASM_PATH else None}
                               for path, content in self.assets.items()}
        apis = ['foundationEngineHost', 'noInitialRun', 'print', 'printErr', 'wasmBinary', 'locateFile']
        if data:
            apis += ['getPreloadedPackage']
        self.runtime = {'schema_version': 1, 'kind': 'foundation-neutral-engine-physical-runtime-evidence-v1' if physical_input else 'foundation-neutral-engine-runtime-evidence-v1',
                        'scope': 'parser-fixture-only', 'status': 'passed',
                        'recipe_id': self.recipe_id, 'provider_build_sha256': sha(encoded(self.build)),
                        'assets_sha256': sha(encoded(self.asset_metadata)), 'target': copy.deepcopy(TARGET),
                        'paired_sdk_sha256': self.toolchain['paired_sdk_sha256'],
                        'engine_profile': self.profile,
                        'browser': {'name': 'fixture-not-a-browser', 'version': 'never-run'},
                        'checks': {key: {'status': 'passed', 'evidence': [
                            {'path': REPORT_PATH, 'sha256': sha(self.reports[REPORT_PATH])}]}
                            for key in (PHYSICAL_CHECKS if physical_input else CHECKS)}}
        self.proof = {'schema_version': 1, 'kind': 'foundation-neutral-engine-provider-physical-proof-v1' if physical_input else 'foundation-neutral-engine-provider-proof-v1',
                      'recipe_id': self.recipe_id, 'sources_sha256': sha(encoded(self.source)),
                      'provider_build': {'path': BUILD_PATH, 'sha256': sha(encoded(self.build))},
                      'engine_profile': self.profile, 'assets': self.asset_metadata,
                      'wasm_facts': consumer.scan_wasm(self.assets[WASM_PATH]),
                      'factory_policy': {'kind': 'inert-esm-copied-owner-v1', 'imports': [],
                                         'data_loading': 'getPreloadedPackage' if data else 'embedded',
                                         'incoming_module_api': sorted(apis),
                                         'syntax': consumer.scan_factory(FACTORY)},
                      'runtime_evidence': {'path': RUNTIME_PATH, 'sha256': sha(encoded(self.runtime))}}
        if physical_input:
            self.proof['command_catalog'] = {'path': CATALOG_PATH, 'sha256': sha(PHYSICAL_CATALOG)}
        for path, content in {**self.assets, **self.notices, **self.reports,
                              **({CATALOG_PATH: PHYSICAL_CATALOG} if physical_input else {}),
                              HEADER: header, BUILD_PATH: encoded(self.build),
                              RUNTIME_PATH: encoded(self.runtime), PROOF_PATH: encoded(self.proof)}.items():
            write(self.binary, path, content)
        self.binary_manifest = {'schema_version': 1, 'kind': 'foundation-appended-engine',
                                'producer_version': 1, 'recipe_id': self.recipe_id,
                                'sources_sha256': sha(encoded(self.source)), 'target': copy.deepcopy(TARGET),
                                'toolchain': self.toolchain, 'options': self.options,
                                'provider': {**self.provider, 'entry': FACTORY_PATH,
                                             'assets': sorted(self.assets)},
                                'licenses': [NOTICE_PATH],
                                'build': {'origin': 'parser-fixture-only', 'link_receipt': PROOF_PATH},
                                **manifest.tree_inventory(self.binary, 'engine-sdk.json')}
        write(self.binary, 'engine-sdk.json', encoded(self.binary_manifest))

    def evidence(self):
        result = {'binary_manifest': encoded(self.binary_manifest), 'source_manifest': encoded(self.source),
                'recipe': encoded(self.recipe), 'proof': encoded(self.proof),
                'provider_build': encoded(self.build), 'runtime': encoded(self.runtime),
                'reports': dict(self.reports)}
        if self.physical_input:
            result['command_catalog'] = PHYSICAL_CATALOG
        return result


def create_fixture(root, *, physical_input=False):
    """Share a fresh fixture-only group with producer tests, never qualification."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o755)
    fixture = Fixture(root/'fixture', physical_input=physical_input)
    evidence = fixture.evidence()
    pins = {key: sha(evidence[document]) for key, document in
            (('recipe', 'recipe'), ('manifest', 'binary_manifest'),
             ('proof', 'proof'), ('runtime', 'runtime'))}
    group = root/'group'
    sdk.export_group(fixture.binary, fixture.sources, group)
    paired_sdk = fixture.toolchain['paired_sdk_sha256']
    inspection = consumer.inspect_kernel_consumer(group, expected_recipe=pins['recipe'],
        expected_manifest=pins['manifest'], expected_proof=pins['proof'], expected_runtime=pins['runtime'],
        kernel_target=TARGET, paired_sdk=paired_sdk,
        required_binding=consumer.PHYSICAL_BINDING if physical_input else consumer.BINDING)
    if inspection.metadata['production_eligible']:
        raise AssertionError('Synthetic parser fixtures must never become eligible artifacts')
    return {'group': group, 'pins': pins, 'target': copy.deepcopy(TARGET),
            'sdk': paired_sdk, 'inspection': inspection}


class EngineConsumerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-engine-consumer-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.fixture = Fixture(self.base/'fixture')
        self.evidence = self.fixture.evidence()
        self.assets = dict(self.fixture.assets)
        self.notices = dict(self.fixture.notices)

    def pins(self, evidence=None):
        evidence = self.evidence if evidence is None else evidence
        return {key: sha(evidence[document]) for key, document in
                (('recipe', 'recipe'), ('manifest', 'binary_manifest'),
                 ('proof', 'proof'), ('runtime', 'runtime'))}

    def embedded(self, *, evidence=None, assets=None, notices=None, **kwargs):
        evidence = self.evidence if evidence is None else evidence
        return consumer.inspect_embedded_consumer(evidence=evidence,
            assets=self.assets if assets is None else assets,
            notices=self.notices if notices is None else notices, pins=self.pins(evidence),
            kernel_target=copy.deepcopy(TARGET), paired_sdk=self.fixture.toolchain['paired_sdk_sha256'],
            **kwargs)

    def changed(self, key, change, *, raw=None):
        """Rehash enclosing documents; preserve the intentionally changed contract."""
        evidence = copy.deepcopy(self.evidence)
        value = json.loads(evidence[key])
        change(value)
        evidence[key] = encoded(value) if raw is None else raw
        binary = json.loads(evidence['binary_manifest'])
        proof = json.loads(evidence['proof'])
        if key == 'provider_build':
            build_hash = sha(evidence[key])
            proof['provider_build']['sha256'] = build_hash
            proof['engine_profile']['build_sha256'] = build_hash
            runtime = json.loads(evidence['runtime'])
            runtime['provider_build_sha256'] = build_hash
            runtime['engine_profile']['build_sha256'] = build_hash
            evidence['runtime'] = encoded(runtime)
            binary['files'][BUILD_PATH] = build_hash
        if key in ('runtime', 'provider_build'):
            proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
            binary['files'][RUNTIME_PATH] = sha(evidence['runtime'])
        if key != 'proof':
            evidence['proof'] = encoded(proof)
        binary['files'][PROOF_PATH] = sha(evidence['proof'])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def with_assets(self, assets, metadata):
        """Keep all hashes coherent when probing an actual static asset policy."""
        evidence = copy.deepcopy(self.evidence)
        proof = json.loads(evidence['proof'])
        proof['assets'] = metadata
        proof['wasm_facts'] = consumer.scan_wasm(assets[WASM_PATH])
        runtime = json.loads(evidence['runtime'])
        runtime['assets_sha256'] = sha(encoded(metadata))
        evidence['runtime'] = encoded(runtime)
        proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
        evidence['proof'] = encoded(proof)
        binary = json.loads(evidence['binary_manifest'])
        binary['provider']['assets'] = sorted(assets)
        for path, content in assets.items():
            binary['files'][path] = sha(content)
            binary['modes'][path] = metadata[path]['mode']
        binary['files'][RUNTIME_PATH] = sha(evidence['runtime'])
        binary['files'][PROOF_PATH] = sha(evidence['proof'])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def test_full_fixture_group_is_integrity_checked_but_ineligible(self):
        group = self.base/'group'
        sdk.export_group(self.fixture.binary, self.fixture.sources, group)
        pins = self.pins()
        result = consumer.inspect_kernel_consumer(group, expected_recipe=pins['recipe'],
            expected_manifest=pins['manifest'], expected_proof=pins['proof'], expected_runtime=pins['runtime'],
            kernel_target=TARGET, paired_sdk=self.fixture.toolchain['paired_sdk_sha256'])
        metadata = result.as_dict()
        self.assertTrue(metadata['whole_group_verified'])
        self.assertFalse(metadata['production_eligible'])
        self.assertEqual(set(metadata['group_files']), set(sdk.group_names(self.fixture.recipe_id)))
        self.assertEqual(dict(result.assets), self.assets)
        with self.assertRaises(ValueError):
            consumer.verify_kernel_consumer(group, expected_recipe=pins['recipe'],
                expected_manifest=pins['manifest'], expected_proof=pins['proof'], expected_runtime=pins['runtime'],
                kernel_target=TARGET, paired_sdk=self.fixture.toolchain['paired_sdk_sha256'])

    def test_embedded_path_reports_only_embedded_subset(self):
        result = self.embedded()
        metadata = result.as_dict()
        self.assertEqual(metadata['scope'], 'embedded-retained-consumer-byte-and-static-contract-only')
        self.assertFalse(metadata['whole_group_verified'])
        self.assertIsNone(metadata['group_files'])
        self.assertFalse(metadata['production_eligible'])
        self.assertEqual(metadata['engine_profile']['bridge_abi'], 65536)
        self.assertEqual(metadata['engine_profile']['capabilities'], '259')
        self.assertEqual(metadata['assets'][WASM_PATH]['lookup_name'], 'engine.wasm')

    def test_wasm_lookup_is_explicit_flat_and_distinct_from_data(self):
        for lookup in (None, '', '../engine.wasm', 'sub/engine.wasm', 'engine..wasm'):
            evidence = self.changed('proof', lambda proof: proof['assets'][WASM_PATH].update(lookup_name=lookup))
            with self.subTest(lookup=lookup), self.assertRaises(ValueError):
                self.embedded(evidence=evidence)
        # A Wasm lookup is required even with no external data; it must not
        # consume the independent data-file allowance or imply preload data.
        self.embedded(limits=consumer.ConsumerLimits(max_data_files=0))
        evidence = self.changed('proof', lambda proof: proof['factory_policy']['incoming_module_api'].remove('locateFile'))
        with self.assertRaises(ValueError):
            self.embedded(evidence=evidence)
        fixture = Fixture(self.base / 'lookup-alias-fixture', data=True)
        previous = self.evidence
        self.evidence = fixture.evidence()
        try:
            evidence = self.changed('proof', lambda proof: proof['assets']['runtime/data/fonts.bin'].update(
                lookup_name='ENGINE.WASM'))
            with self.assertRaises(ValueError):
                self.embedded(evidence=evidence, assets=fixture.assets, notices=fixture.notices)
        finally:
            self.evidence = previous

    def test_result_owns_immutable_values_and_json_copy(self):
        result = self.embedded()
        self.assets.clear()
        self.evidence['reports'].clear()
        self.assertEqual(result.assets[FACTORY_PATH], FACTORY)
        self.assertTrue(result.evidence['reports'])
        for mapping, key in ((result.assets, FACTORY_PATH), (result.metadata, 'scope'),
                             (result.evidence, 'proof'), (result.metadata['engine_profile'], 'kind')):
            with self.subTest(key=key), self.assertRaises(TypeError):
                mapping[key] = b'changed'
        metadata = result.as_dict()
        metadata['engine_profile']['bridge_abi'] = 1
        self.assertEqual(result.metadata['engine_profile']['bridge_abi'], 65536)

    def test_returned_report_bytes_are_the_validated_snapshot(self):
        from collections.abc import Mapping
        original = self.evidence['reports'][REPORT_PATH]

        class ChangingReports(Mapping):
            def __init__(self):
                self.lookups = 0

            def __iter__(self):
                return iter((REPORT_PATH,))

            def __len__(self):
                return 1

            def __getitem__(self, path):
                if path != REPORT_PATH:
                    raise KeyError(path)
                self.lookups += 1
                # Eight original case checks can all observe valid bytes;
                # later retention must not re-read this untrusted mapping.
                return original if self.lookups <= len(CHECKS) else b'x' * len(original)

        evidence = copy.deepcopy(self.evidence)
        evidence['reports'] = ChangingReports()
        result = self.embedded(evidence=evidence)
        self.assertEqual(result.evidence['reports'][REPORT_PATH], original)

    def test_full_group_rejects_data_aggregate_before_materializing_assets(self):
        fixture = Fixture(self.base / 'bounded-data-fixture', data=True)
        group = self.base / 'bounded-data-group'
        sdk.export_group(fixture.binary, fixture.sources, group)
        evidence = fixture.evidence()
        pins = self.pins(evidence)
        maximum = len(fixture.assets['runtime/data/fonts.bin']) - 1
        actual_read = consumer._read_members
        materialized = []

        def read(archive, wanted, **kwargs):
            materialized.extend(set(wanted) & set(fixture.assets))
            return actual_read(archive, wanted, **kwargs)

        with mock.patch.object(consumer, '_read_members', side_effect=read), self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, expected_recipe=pins['recipe'],
                expected_manifest=pins['manifest'], expected_proof=pins['proof'], expected_runtime=pins['runtime'],
                kernel_target=TARGET, paired_sdk=fixture.toolchain['paired_sdk_sha256'],
                limits=consumer.ConsumerLimits(max_data_total_bytes=maximum))
        self.assertEqual(materialized, [])

    def test_each_independent_pin_is_required_and_exact(self):
        for key in self.pins():
            for mutation in ('0'*64, self.pins()[key].upper(), None):
                pins = self.pins(); pins[key] = mutation
                with self.subTest(key=key, mutation=mutation), self.assertRaises((ValueError, TypeError)):
                    consumer.inspect_embedded_consumer(evidence=self.evidence, assets=self.assets,
                        notices=self.notices, pins=pins, kernel_target=TARGET,
                        paired_sdk=self.fixture.toolchain['paired_sdk_sha256'])

    def test_external_pin_uses_exact_document_bytes(self):
        evidence = copy.deepcopy(self.evidence)
        evidence['proof'] += b'\n'
        with self.assertRaises(ValueError):
            consumer.inspect_embedded_consumer(evidence=evidence, assets=self.assets, notices=self.notices,
                pins=self.pins(), kernel_target=TARGET,
                paired_sdk=self.fixture.toolchain['paired_sdk_sha256'])

    def test_consuming_target_sdk_and_binding_must_match(self):
        for kwargs in ({'kernel_target': {**TARGET, 'triple': 'wasm32-foreign'}},
                       {'paired_sdk': '0'*64}, {'required_binding': 'linked-owner'},
                       {'kernel_target': {'system': 'Linux', 'processor': 'x86_64',
                                          'triple': 'x86_64-linux-gnu', 'pointer_bits': 64}}):
            args = dict(evidence=self.evidence, assets=self.assets, notices=self.notices,
                        pins=self.pins(), kernel_target=TARGET,
                        paired_sdk=self.fixture.toolchain['paired_sdk_sha256'])
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                consumer.inspect_embedded_consumer(**args)

    def test_failed_and_incomplete_runtime_reports_remain_ineligible(self):
        for status in ('failed', 'incomplete'):
            evidence = self.changed('runtime', lambda value: value.update(status=status))
            result = self.embedded(evidence=evidence)
            self.assertFalse(result.metadata['production_eligible'])
            self.assertEqual(result.as_dict()['runtime_evidence']['status'], status)

    def test_pure_eligibility_predicate_on_synthetic_dictionaries_only(self):
        # This exercises a Boolean predicate only. The synthetic value is never
        # retained, pinned, inspected as an artifact or presented as execution.
        synthetic = {'scope': 'retained-neutral-provider-runtime', 'status': 'passed',
                     'checks': {key: {'status': 'passed', 'evidence': ['synthetic-reference']}
                                for key in CHECKS}}
        self.assertTrue(consumer._production_eligible(synthetic))
        for key, value in (('scope', 'parser-fixture-only'), ('status', 'failed'),
                           ('status', 'incomplete')):
            changed = copy.deepcopy(synthetic); changed[key] = value
            self.assertFalse(consumer._production_eligible(changed))
        for status, evidence in (('failed', ['synthetic-reference']), ('not-run', []), ('passed', [])):
            changed = copy.deepcopy(synthetic)
            changed['checks']['factory-inert'] = {'status': status, 'evidence': evidence}
            self.assertFalse(consumer._production_eligible(changed))

    def test_case_not_run_is_not_a_pass(self):
        evidence = self.changed('runtime', lambda value: value['checks']['factory-inert'].update(
            status='not-run', evidence=[]))
        result = self.embedded(evidence=evidence)
        self.assertFalse(result.metadata['production_eligible'])
        self.assertEqual(result.as_dict()['runtime_evidence']['checks']['factory-inert']['status'], 'not-run')

    def test_passed_case_requires_matching_original_evidence(self):
        for change in (lambda value: value['checks']['factory-inert'].update(evidence=[]),
                       lambda value: value['checks']['factory-inert']['evidence'][0].update(sha256='0'*64),
                       lambda value: value['checks']['factory-inert']['evidence'][0].update(path=FACTORY_PATH)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('runtime', change))
        missing = copy.deepcopy(self.evidence); missing['reports'] = {}
        with self.assertRaises(ValueError):
            self.embedded(evidence=missing)

    def test_all_case_names_and_reference_keys_are_strict(self):
        changes = [lambda value: value['checks'].pop('opaque-raster-frame'),
                   lambda value: value['checks'].update(extra={'status': 'passed', 'evidence': []}),
                   lambda value: value['checks']['factory-inert']['evidence'][0].update(extra=True),
                   lambda value: value['checks']['factory-inert']['evidence'].append(
                       dict(value['checks']['factory-inert']['evidence'][0]))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('runtime', change))

    def test_new_documents_reject_unknown_missing_and_boolean_fields(self):
        for key in ('proof', 'provider_build', 'runtime'):
            for change in (lambda value: value.update(unexpected=True),
                           lambda value: value.pop('kind'),
                           lambda value: value.update(schema_version=True)):
                with self.subTest(key=key, change=change), self.assertRaises(ValueError):
                    self.embedded(evidence=self.changed(key, change))

    def test_new_json_rejects_duplicates_nonfinite_and_invalid_unicode(self):
        raw_values = [self.evidence['proof'].rstrip()[:-1] + b',"schema_version":1}',
                      self.evidence['proof'].replace(b'"schema_version": 1', b'"schema_version": NaN'),
                      self.evidence['proof'].replace(b'"schema_version": 1', b'"schema_version": Infinity'),
                      self.evidence['proof'].replace(b'foundation-neutral-engine-provider-proof-v1', b'\xff'),
                      self.evidence['proof'].replace(b'foundation-neutral-engine-provider-proof-v1', b'\\ud800')]
        for raw in raw_values:
            with self.subTest(raw=raw[:60]), self.assertRaises((ValueError, UnicodeError)):
                self.embedded(evidence=self.changed('proof', lambda value: None, raw=raw))

    def test_production_profile_uses_exact_supported_capabilities_and_bridge(self):
        for field, value in (('capabilities', '467'), ('capabilities', '0259'),
                             ('capabilities', 259), ('capabilities', '771'),
                             ('bridge_abi', 1), ('pthread', 0), ('shared_memory', True),
                             ('pointer_bits', True), ('target', 'browser-wasm64')):
            evidence = self.changed('proof', lambda proof: proof['engine_profile'].update({field: value}))
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.embedded(evidence=evidence)

    def test_provider_build_binds_source_configuration_and_canonical_header(self):
        changes = [lambda value: value.update(source_inputs_sha256='0'*64),
                   lambda value: value.update(contract_header_sha256='0'*64),
                   lambda value: value.update(source_recipe_sha256='0'*64),
                   lambda value: value['configuration'].update(auto_main=True),
                   lambda value: value['configuration'].update(fixed_viewport_width=1024),
                   lambda value: value['toolchain'].update(identity_sha256='0'*64)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('provider_build', change))

    def test_nested_typed_facts_do_not_alias_json_booleans_and_integers(self):
        def boolean_export_index(proof):
            entry = next(item for item in proof['wasm_facts']['exports']
                         if item['name'] == 'bib_engine_wasm_bridge_v1')
            self.assertIs(type(entry['index']), int)
            self.assertEqual(entry['index'], 0)
            entry['index'] = False

        changes = [('proof', boolean_export_index),
                   ('proof', lambda value: value['wasm_facts']['memories'][0].update(shared=0)),
                   ('provider_build', lambda value: value['options'].update(script_enabled=1))]
        for key, change in changes:
            # Rehash proof/build/runtime references and enclosing independent
            # manifest pin, isolating semantic type checks from stale hashes.
            with self.subTest(key=key, change=change), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed(key, change))

    def test_provider_abi_is_exact_one_zero_and_linked_owner_is_ineligible(self):
        for field, value in (('abi_major', 2), ('abi_minor', 1), ('binding', 'linked-owner')):
            evidence = copy.deepcopy(self.evidence)
            binary = json.loads(evidence['binary_manifest'])
            binary['provider'][field] = value
            evidence['binary_manifest'] = encoded(binary)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.embedded(evidence=evidence)

    def test_asset_set_and_hash_size_mode_roles_are_exact(self):
        for change in (lambda value: value['assets'].pop(WASM_PATH),
                       lambda value: value['assets'][WASM_PATH].update(sha256='0'*64),
                       lambda value: value['assets'][WASM_PATH].update(bytes=True),
                       lambda value: value['assets'][WASM_PATH].update(bytes=1),
                       lambda value: value['assets'][WASM_PATH].update(mode=0o755),
                       lambda value: value['assets'][WASM_PATH].update(role='factory'),
                       lambda value: value['assets'][FACTORY_PATH].update(lookup_name='engine.mjs')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('proof', change))
        for assets in ({FACTORY_PATH: FACTORY}, {**self.assets, 'extra.bin': b'extra'}):
            with self.subTest(paths=list(assets)), self.assertRaises(ValueError):
                self.embedded(assets=assets)

    def test_external_data_uses_explicit_portable_lookup_and_preload_policy(self):
        fixture = Fixture(self.base/'data-fixture', data=True)
        result = self.embedded(evidence=fixture.evidence(), assets=fixture.assets, notices=fixture.notices)
        self.assertEqual(result.metadata['assets']['runtime/data/fonts.bin']['lookup_name'], 'fonts.bin')
        original = self.evidence
        self.evidence = fixture.evidence()
        try:
            for lookup in ('../fonts.bin', 'fonts..bin', 'sub/fonts.bin', ''):
                evidence = self.changed('proof', lambda value: value['assets']['runtime/data/fonts.bin'].update(lookup_name=lookup))
                with self.subTest(lookup=lookup), self.assertRaises(ValueError):
                    self.embedded(evidence=evidence, assets=fixture.assets, notices=fixture.notices)
            assets = {**fixture.assets, 'runtime/data/other.bin': b'other tiny marker'}
            metadata = copy.deepcopy(fixture.asset_metadata)
            metadata['runtime/data/other.bin'] = {'role': 'data', 'sha256': sha(assets['runtime/data/other.bin']),
                'bytes': len(assets['runtime/data/other.bin']), 'mode': 0o644, 'lookup_name': 'FONTS.BIN'}
            with self.assertRaises(ValueError):
                self.embedded(evidence=self.with_assets(assets, metadata), assets=assets, notices=fixture.notices)
            evidence = self.changed('proof', lambda value: value['factory_policy'].update(data_loading='embedded'))
            with self.assertRaises(ValueError):
                self.embedded(evidence=evidence, assets=fixture.assets, notices=fixture.notices)
            data_bytes = len(fixture.assets['runtime/data/fonts.bin'])
            for limits in (consumer.ConsumerLimits(max_data_member_bytes=data_bytes-1),
                           consumer.ConsumerLimits(max_data_total_bytes=data_bytes-1),
                           consumer.ConsumerLimits(max_data_files=0)):
                with self.subTest(limits=limits), self.assertRaises(ValueError):
                    self.embedded(evidence=fixture.evidence(), assets=fixture.assets,
                                  notices=fixture.notices, limits=limits)
        finally:
            self.evidence = original

    def test_factory_policy_must_include_complete_sorted_api_and_actual_syntax(self):
        for change in (lambda value: value['factory_policy']['incoming_module_api'].remove('wasmBinary'),
                       lambda value: value['factory_policy']['incoming_module_api'].reverse(),
                       lambda value: value['factory_policy']['incoming_module_api'].append('wasmBinary'),
                       lambda value: value['factory_policy']['syntax'].update(import_meta_url=True),
                       lambda value: value['factory_policy'].update(imports=['other.mjs'])):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('proof', change))

    def test_role_limits_use_measured_exact_boundaries(self):
        bounds = dict(max_factory_bytes=len(FACTORY), max_wasm_bytes=len(self.assets[WASM_PATH]),
                      max_notice_bytes=len(self.notices[NOTICE_PATH]),
                      max_notices_total_bytes=len(self.notices[NOTICE_PATH]), max_notices=1,
                      max_reports_total_bytes=len(self.evidence['reports'][REPORT_PATH]))
        self.embedded(limits=consumer.ConsumerLimits(**bounds))
        for key in bounds:
            smaller = {**bounds, key: bounds[key]-1}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.embedded(limits=consumer.ConsumerLimits(**smaller))

    def test_limit_types_and_nonpositive_required_members_reject(self):
        for kwargs in ({'max_wasm_bytes': True}, {'max_factory_bytes': 0},
                       {'max_notice_bytes': 0}, {'max_data_files': -1},
                       {'max_reports_total_bytes': 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                self.embedded(limits=consumer.ConsumerLimits(**kwargs))

    def test_supplied_notice_and_case_evidence_closure_is_complete(self):
        for notices in ({}, {**self.notices, 'licenses/extra.txt': b'extra'},
                        {NOTICE_PATH: b'changed'}):
            with self.subTest(notices=notices), self.assertRaises(ValueError):
                self.embedded(notices=notices)
        evidence = copy.deepcopy(self.evidence)
        evidence['reports']['evidence/extra.txt'] = b'not referenced'
        with self.assertRaises(ValueError):
            self.embedded(evidence=evidence)

    def test_consumer_does_not_execute_or_extract_fixture_inputs(self):
        with mock.patch('subprocess.run', side_effect=AssertionError('no process launch')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('no process launch')), \
                mock.patch.object(sdk, 'restore', side_effect=AssertionError('no extraction')):
            result = self.embedded()
        self.assertFalse(result.metadata['production_eligible'])

    def test_typed_wasm_scan_resolves_imported_and_defined_function_indexes(self):
        facts = consumer.scan_wasm(tiny_wasm(imported=True))
        self.assertEqual(facts['imports'], [{'module': 'host', 'name': 'copied_callback', 'kind': 'function',
            'details': {'parameters': [], 'results': ['i32']}}])
        exports = {item['name']: item for item in facts['exports']}
        self.assertEqual(exports['bib_engine_wasm_dispatch_v1']['index'], 2)
        self.assertEqual(exports['bib_engine_wasm_dispatch_v1']['details'],
                         {'parameters': ['i32']*5, 'results': ['i32']})
        self.assertEqual(exports['free']['details'], {'parameters': ['i32'], 'results': []})
        self.assertEqual([item['name'] for item in facts['exports']], sorted(exports))
        self.assertEqual(facts['memories'], [{'imported': False, 'module': None, 'name': None,
            'minimum': 1, 'maximum': 2, 'shared': False, 'memory64': False}])
        self.assertIsNone(facts['start'])

    def test_wasm_scan_reports_imported_table_memory_global_and_tag_types(self):
        imports = [name('host')+name('table')+b'\x01\x70\x01\x01\x02',
                   name('host')+name('memory')+b'\x02\x01\x01\x02',
                   name('host')+name('global')+b'\x03\x7e\x01',
                   name('host')+name('tag')+b'\x04\x00\x00']
        module = MAGIC + section(1, vector([b'\x60\x01\x7f\x00'])) + section(2, vector(imports))
        facts = consumer.scan_wasm(module)
        self.assertEqual([item['kind'] for item in facts['imports']], ['table', 'memory', 'global', 'tag'])
        self.assertEqual(facts['imports'][0]['details'], {'element': 'funcref', 'minimum': 1, 'maximum': 2})
        self.assertEqual(facts['imports'][2]['details'], {'value': 'i64', 'mutable': True})
        self.assertEqual(facts['imports'][3]['details'], {'parameters': ['i32'], 'results': []})
        self.assertTrue(facts['memories'][0]['imported'])

    def test_wasm_scan_rejects_truncation_noncanonical_leb_duplicates_and_bad_indexes(self):
        bad = [b'', MAGIC[:-1], MAGIC+b'\x01\x80\x00', MAGIC+b'\x01\x80',
               MAGIC+section(1, b'\x00')+section(1, b'\x00'),
               MAGIC+section(1, vector([b'\x60\x00\x00']))+section(3, vector([b'\x01'])),
               tiny_wasm(extra_exports=[('malloc', 0, 0)]),
               tiny_wasm(extra_exports=[('outside', 0, 99)]),
               tiny_wasm(memory=b'\x01\x02\x01')]
        for data in bad:
            with self.subTest(data=data[:32]), self.assertRaises(ValueError):
                consumer.scan_wasm(data)

    def test_wasm_scan_fails_explicitly_on_unfamiliar_type_encoding(self):
        for data in (MAGIC+section(1, vector([b'\x5f\x00'])),
                     MAGIC+section(1, vector([b'\x60\x01\x6e\x00']))):
            with self.subTest(data=data), self.assertRaises(ValueError):
                consumer.scan_wasm(data)

    def test_wasm_bodies_are_opaque_not_a_claim_of_instruction_validation(self):
        normal = consumer.scan_wasm(tiny_wasm())
        opaque = consumer.scan_wasm(tiny_wasm(code=b'\x00\xff\xff\x0b'))
        self.assertEqual(normal, opaque)

    def test_consumer_rejects_actual_wasm_contract_changes_even_with_rehashed_proof(self):
        for wasm in (tiny_wasm(dispatch_type=0), tiny_wasm(extra_exports=[('bib_eval', 0, 0)]),
                     tiny_wasm(extra_exports=[('_start', 0, 0)]), tiny_wasm(memory=b'\x00\x01'),
                     tiny_wasm(memory=b'\x03\x01\x02'), tiny_wasm(start=0)):
            assets = {**self.assets, WASM_PATH: wasm}
            metadata = copy.deepcopy(self.fixture.asset_metadata)
            metadata[WASM_PATH].update(sha256=sha(wasm), bytes=len(wasm))
            evidence = self.with_assets(assets, metadata)
            with self.subTest(wasm=wasm[:30]), self.assertRaises(ValueError):
                self.embedded(evidence=evidence, assets=assets)

    def test_factory_scan_ignores_inert_literals_and_reports_import_meta_url(self):
        for data, uses_meta in ((FACTORY, False),
                (b'/* import "absent"; bib_pump(); */\nconst text="import(\\\"absent\\\")";\n'+FACTORY, False),
                (b'const base=import.meta.url;\n'+FACTORY, True),
                (b'export default async function createEngine(options = {}) {\n'
                 b'  const base = import.meta.url; return options;\n}\n', True),
                (b'function fallback(url){ return fetch(url); }\n'+FACTORY, False)):
            with self.subTest(data=data[:50]):
                self.assertEqual(consumer.scan_factory(data), {'module_dependencies': [],
                    'default_export': True, 'import_meta_url': uses_meta})

    def test_factory_scan_rejects_static_dynamic_and_reexport_dependencies(self):
        for prefix in (b'import other from "other.mjs";\n', b'import "other.mjs";\n',
                       b'const other=import("other.mjs");\n', b'export {other} from "other.mjs";\n',
                       b'export * from "other.mjs";\n', b'const other=require("other.cjs");\n',
                       b'module.exports = function createEngine() {};\n'):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                consumer.scan_factory(prefix+FACTORY)

    def test_factory_scan_rejects_computed_import_meta_and_bootstrap_execution(self):
        for prefix in (b'const base=import.meta["url"];\n', b'const env=import.meta.env;\n',
                       b'callMain([]);\n', b'_main();\n', b'_bib_pump();\n',
                       b'const helper="engine-pre.js";\n'):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                consumer.scan_factory(prefix+FACTORY)

    def test_factory_scan_requires_one_default_export_and_valid_utf8(self):
        for data in (b'', b'const factory=()=>({});', FACTORY+FACTORY, b'\xff'+FACTORY):
            with self.subTest(data=data[:32]), self.assertRaises((ValueError, UnicodeError)):
                consumer.scan_factory(data)


class PhysicalEngineConsumerTests(unittest.TestCase):
    pins = EngineConsumerTests.pins
    changed = EngineConsumerTests.changed
    with_assets = EngineConsumerTests.with_assets

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-physical-consumer-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.fixture = Fixture(self.base/'fixture', physical_input=True)
        self.evidence = self.fixture.evidence()
        self.assets = dict(self.fixture.assets)
        self.notices = dict(self.fixture.notices)

    def embedded(self, **kwargs):
        kwargs.setdefault('required_binding', consumer.PHYSICAL_BINDING)
        return EngineConsumerTests.embedded(self, **kwargs)

    def test_exact_catalog_and_physical_fixture_are_explicit_and_ineligible(self):
        self.assertEqual(len(PHYSICAL_CATALOG), 14451)
        self.assertEqual(sha(PHYSICAL_CATALOG), 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b')
        self.assertEqual(dict(consumer.PHYSICAL_PROFILE_FACTS), PHYSICAL_FACTS)
        self.assertEqual(consumer.PHYSICAL_RUNTIME_CHECKS, PHYSICAL_CHECKS)
        self.assertEqual(consumer.PHYSICAL_INPUT_CHECKS, PHYSICAL_CHECKS[len(CHECKS):])
        result = self.embedded()
        self.assertFalse(result.metadata['production_eligible'])
        self.assertEqual(len(result.metadata['engine_profile']), 20)
        self.assertEqual(result.metadata['engine_profile']['capabilities'], '467')
        self.assertEqual(result.metadata['engine_profile']['surface_capabilities'], '8225')
        self.assertEqual(result.as_dict()['command_catalog'], {'path': CATALOG_PATH, 'sha256': sha(PHYSICAL_CATALOG)})
        self.assertEqual(result.evidence['command_catalog'], PHYSICAL_CATALOG)
        with self.assertRaises(ValueError):
            EngineConsumerTests.embedded(self)
        fixture = Fixture(self.base/'legacy')
        with self.assertRaises(ValueError):
            self.embedded(evidence=fixture.evidence(), assets=fixture.assets, notices=fixture.notices)
        for binding in ('copied-owner-bridge/direct-worker-physical', None, True):
            with self.subTest(binding=binding), self.assertRaises(ValueError):
                self.embedded(required_binding=binding)

    def test_public_profile_validator_rejects_missing_mistyped_and_unknown_fields(self):
        for field, expected in self.fixture.profile.items():
            bad_type = 0 if type(expected) in (str, bool) else True
            for change in (lambda value, field=field: value.pop(field),
                           lambda value, field=field, bad_type=bad_type: value.update({field: bad_type})):
                value = copy.deepcopy(self.fixture.profile); change(value)
                with self.subTest(field=field, value=value.get(field)), self.assertRaises(ValueError):
                    consumer.validate_engine_profile(value, required_binding=consumer.PHYSICAL_BINDING)
        for change in (lambda value: value.update(extra=True), lambda value: value.update(capabilities='0467'),
                       lambda value: value.update(surface_capabilities='97'), lambda value: value.update(command_catalog_sha256='f'*64),
                       lambda value: value.update(contract_sha256='f'*64), lambda value: value.update(build_sha256='G'*64)):
            value = copy.deepcopy(self.fixture.profile); change(value)
            with self.assertRaises(ValueError):
                consumer.validate_engine_profile(value, required_binding=consumer.PHYSICAL_BINDING)
        with self.assertRaises(ValueError):
            consumer.validate_engine_profile(self.fixture.profile)
        result = consumer.validate_engine_profile(self.fixture.profile, required_binding=consumer.PHYSICAL_BINDING)
        self.fixture.profile['viewport_width'] = 1024
        self.assertEqual(result['viewport_width'], 800)
        with self.assertRaises(TypeError):
            result['viewport_width'] = 1024

    def test_each_physical_profile_value_is_bound_to_its_original_build_and_recipe(self):
        for field, expected in self.fixture.profile.items():
            replacement = 'f'*64 if field.endswith('_sha256') else ('changed' if type(expected) is str else not expected)
            evidence = self.changed('proof', lambda value, field=field, replacement=replacement:
                                    value['engine_profile'].update({field: replacement}))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'profile'):
                self.embedded(evidence=evidence)

    def test_physical_provider_build_has_all_eight_exact_generator_facts(self):
        for field in PHYSICAL_FACTS:
            for change in (lambda value, field=field: value.pop(field),
                           lambda value, field=field: value.update({field: None})):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.embedded(evidence=self.changed('provider_build', change))
        for change in (lambda value: value.update(kind='foundation-neutral-engine-provider-build-v1'),
                       lambda value: value.update(binding=consumer.BINDING), lambda value: value.update(capabilities='259'),
                       lambda value: value['configuration'].update(profile='browser-wasm32-cpu-direct-owner-v1')):
            with self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('provider_build', change))

    def test_catalog_bytes_reference_and_evidence_keys_are_exact_and_bounded(self):
        for raw in (b'{}', PHYSICAL_CATALOG+b'\n', bytearray(PHYSICAL_CATALOG), b'x'*(64*1024+1)):
            evidence = copy.deepcopy(self.evidence); evidence['command_catalog'] = raw
            with self.subTest(length=len(raw)), self.assertRaisesRegex(ValueError, 'catalog'):
                self.embedded(evidence=evidence)
        for reference in ({'path': CATALOG_PATH, 'sha256': 'f'*64}, {'path': 'missing.json', 'sha256': sha(PHYSICAL_CATALOG)},
                          {'path': '../catalog.json', 'sha256': sha(PHYSICAL_CATALOG)}, {'path': CATALOG_PATH},
                          {'path': CATALOG_PATH, 'sha256': sha(PHYSICAL_CATALOG), 'extra': True}):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('proof', lambda value: value.update(command_catalog=reference)))
        for mutate in (lambda value: value.pop('command_catalog'), lambda value: value.update(extra=b'')):
            evidence = copy.deepcopy(self.evidence); mutate(evidence)
            with self.assertRaises(ValueError):
                self.embedded(evidence=evidence)
        for key in ('proof', 'runtime'):
            old_kind = 'foundation-neutral-engine-provider-proof-v1' if key == 'proof' else 'foundation-neutral-engine-runtime-evidence-v1'
            with self.assertRaises(ValueError):
                self.embedded(evidence=self.changed(key, lambda value: value.update(kind=old_kind)))

    def rebind_source(self, evidence, recipe, source):
        evidence = copy.deepcopy(evidence)
        evidence['recipe'] = encoded(recipe); identity = sha(evidence['recipe'])
        source['recipe_id'] = identity; source['files']['recipe.json'] = identity
        evidence['source_manifest'] = encoded(source)
        build = json.loads(evidence['provider_build'])
        build.update(source_recipe_sha256=identity, source_inputs_sha256=sha(encoded(recipe['inputs'])))
        evidence['provider_build'] = encoded(build); build_hash = sha(evidence['provider_build'])
        proof = json.loads(evidence['proof'])
        proof.update(recipe_id=identity, sources_sha256=sha(evidence['source_manifest']))
        proof['provider_build']['sha256'] = build_hash
        proof['engine_profile'].update(build_sha256=build_hash, source_recipe_sha256=identity)
        runtime = json.loads(evidence['runtime'])
        runtime.update(recipe_id=identity, provider_build_sha256=build_hash, engine_profile=proof['engine_profile'])
        evidence['runtime'] = encoded(runtime); proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
        evidence['proof'] = encoded(proof)
        binary = json.loads(evidence['binary_manifest'])
        binary.update(recipe_id=identity, sources_sha256=sha(evidence['source_manifest']))
        for path, key in ((BUILD_PATH, 'provider_build'), (PROOF_PATH, 'proof'), (RUNTIME_PATH, 'runtime')):
            binary['files'][path] = sha(evidence[key])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def test_catalog_requires_same_path_and_hash_in_binary_source_and_recipe(self):
        evidence = self.changed('binary_manifest', lambda value: value['files'].update({CATALOG_PATH: 'f'*64}))
        with self.assertRaisesRegex(ValueError, 'catalog'):
            self.embedded(evidence=evidence)
        recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
        recipe['inputs'].pop(CATALOG_PATH); source['files'].pop(CATALOG_PATH); source['modes'].pop(CATALOG_PATH)
        with self.assertRaisesRegex(ValueError, 'source/recipe inventory'):
            self.embedded(evidence=self.rebind_source(self.evidence, recipe, source))
        recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
        recipe['inputs'][CATALOG_PATH]['sha256'] = 'f'*64; source['files'][CATALOG_PATH] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'source/recipe inventory'):
            self.embedded(evidence=self.rebind_source(self.evidence, recipe, source))

    def test_catalog_cannot_alias_any_other_metadata_asset_notice_or_report(self):
        for path in (HEADER, PROOF_PATH, BUILD_PATH, RUNTIME_PATH, FACTORY_PATH, WASM_PATH, NOTICE_PATH, REPORT_PATH):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('proof', lambda value: value['command_catalog'].update(path=path)))
        metadata = copy.deepcopy(self.fixture.asset_metadata)
        metadata[CATALOG_PATH] = {'role': 'data', 'sha256': sha(PHYSICAL_CATALOG), 'bytes': len(PHYSICAL_CATALOG),
                                  'mode': 0o644, 'lookup_name': 'physical-catalog.json'}
        assets = {**self.assets, CATALOG_PATH: PHYSICAL_CATALOG}
        with self.assertRaisesRegex(ValueError, 'roles'):
            self.embedded(evidence=self.with_assets(assets, metadata), assets=assets)
        def alias_reports(value):
            for check in value['checks'].values():
                check['evidence'] = [{'path': CATALOG_PATH, 'sha256': sha(PHYSICAL_CATALOG)}]
        evidence = self.changed('runtime', alias_reports); evidence['reports'] = {CATALOG_PATH: PHYSICAL_CATALOG}
        with self.assertRaisesRegex(ValueError, 'role'):
            self.embedded(evidence=evidence)

    def test_additional_runtime_checks_are_required_and_not_run_is_not_a_pass(self):
        for name in PHYSICAL_CHECKS[len(CHECKS):]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.embedded(evidence=self.changed('runtime', lambda value: value['checks'].pop(name)))
            evidence = self.changed('runtime', lambda value: value['checks'][name].update(status='not-run', evidence=[]))
            result = self.embedded(evidence=evidence)
            self.assertFalse(result.metadata['production_eligible'])
            self.assertEqual(result.as_dict()['runtime_evidence']['checks'][name]['status'], 'not-run')

    def test_full_physical_fixture_group_remains_ineligible_for_verification(self):
        fixture = create_fixture(self.base/'shared-helper', physical_input=True)
        result = fixture['inspection']
        self.assertTrue(result.metadata['whole_group_verified'])
        self.assertEqual(result.evidence['command_catalog'], PHYSICAL_CATALOG)
        self.assertFalse(result.metadata['production_eligible'])
        args = {'expected_'+key: value for key, value in fixture['pins'].items()}
        with self.assertRaisesRegex(ValueError, 'production-ineligible'):
            consumer.verify_kernel_consumer(fixture['group'], **args, kernel_target=TARGET, paired_sdk=fixture['sdk'],
                                            required_binding=consumer.PHYSICAL_BINDING)
        with self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(fixture['group'], **args, kernel_target=TARGET, paired_sdk=fixture['sdk'])

    def test_archive_catalog_bound_rejects_before_materializing_runtime_assets(self):
        write(self.fixture.binary, CATALOG_PATH, b'x'*(64*1024+1))
        self.fixture.binary_manifest.update(manifest.tree_inventory(self.fixture.binary, 'engine-sdk.json'))
        write(self.fixture.binary, 'engine-sdk.json', encoded(self.fixture.binary_manifest))
        group = self.base/'oversized-group'; sdk.export_group(self.fixture.binary, self.fixture.sources, group)
        pins = self.pins(self.fixture.evidence()); reads = []; original = consumer._read_members
        def read(archive, wanted, **kwargs):
            reads.extend(set(wanted) & set(self.assets)); return original(archive, wanted, **kwargs)
        with mock.patch.object(consumer, '_read_members', side_effect=read), self.assertRaisesRegex(ValueError, 'oversized'):
            consumer.inspect_kernel_consumer(group, **{'expected_'+key: value for key, value in pins.items()},
                kernel_target=TARGET, paired_sdk=self.fixture.toolchain['paired_sdk_sha256'], required_binding=consumer.PHYSICAL_BINDING)
        self.assertEqual(reads, [])

    def test_cli_selects_only_the_explicit_requested_binding(self):
        target = self.base/'target.json'; target.write_bytes(encoded(TARGET))
        args = ['inspect', '--group', str(self.base/'not-opened'), '--kernel-target-json', str(target),
                '--paired-sdk-sha256', self.fixture.toolchain['paired_sdk_sha256']]
        for key, value in self.pins().items(): args += ['--'+key+'-sha256', value]
        result = mock.Mock(); result.as_dict.return_value = {'scope': 'CLI-selection-fixture-only'}
        for flags, binding in (([], consumer.BINDING), (['--physical-input'], consumer.PHYSICAL_BINDING)):
            with mock.patch.object(consumer, 'inspect_kernel_consumer', return_value=result) as inspect, \
                    mock.patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(consumer.main(args+flags), 0)
                self.assertEqual(inspect.call_args.kwargs['required_binding'], binding)
        with mock.patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit):
            consumer.main(args+['--physical-input=yes'])


if __name__ == '__main__':
    unittest.main()
