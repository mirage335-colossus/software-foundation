"""Source-only document metadata fixtures; no engine or SDK program executes.

The generated facts describe retained sources. Even the real consumer's static
inspection below remains permanently ineligible parser evidence, never runtime
proof. These tests import no old test classes and preserve their identities.
"""
import base64
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_engine_document_contract as contract
import appended_engine_document_consumer as consumer
import appended_engine_manifest as manifest
import appended_engine_document_fixture as inert
import appended_engine_editor_contract as editor_contract
import appended_engine_editor_consumer as editor_consumer

GENERATOR = ROOT / 'recipes/webkitwasm-document-v2/runtime/generate_document_metadata.py'
TEMPLATE = GENERATOR.with_name('engine-document-copied-metadata.h.in')
RETAINED_GENERATOR = 'source/document-provider/runtime/generate_document_metadata.py'
# Exact f11 source-only schema bytes from the reviewed source definition. This
# literal is independent of ignored work directories and claims no public schema.
SCHEMA = zlib.decompress(base64.b64decode(
    b'eJyNWttu40YSfd+vaPApianIkmWNxxoFyGUGO8HckkkWizW8BEW2JK4pNsMmLSuB/31PVXU3SY8X2JcZkexLdV1Onar2X1Ga'
    b'tYWpbHT9V/SD3hVVdH0T6YdaZ63O1T90Y/E1iqPK5Fp1y0V0G0dviqqw+9HAdzq1mr59rHX1ydRd/X+s86uuyzTTv+mH9pnF'
    b'8D2tdvR/iwHKtg3N+azbH/c6u9P5s1My+aY2xpRu+MeaDvjsaMOfWJw4srqUr35uXtisKQ5Flbamia6j7upasYrW5/FA9PUs'
    b'7oVaz+Ow5foiDtpYL2LR2voyeoyjjemqnHWetm1TbLpWJ5k51KbSVWuTtMoTfV/kusp0YltdY+ji/OWSJuanBIJh91PStdvZ'
    b'MrpeXl5e4FNmqrYxJYbOzxdXEF/XLYw0v1zyUdqiytpEP/CvXWJ1c19g9QYHOSWbU6sxcYaJly8wflvoMvfry3Jb0xwgWVlC'
    b'oAYr2Cfbl8W9To46vUv2EL+k5dyXQ/rwP7Y56DbN0zZNIFvZ5SRXm36xchjVmGM4HflReBA72mRXmk1a+rd1U9ynpNi0brtG'
    b'J5W+101yLPBzvEGTHhO33tXs5fyRdLeFtcRvItgfZ5vkJusOMM/kfj6pU6ySTzbwjeY0yXDgAhKSS/UzoQe7T2pTFtkJq3z+'
    b'+/cwhTJbheGmKrK0VL//9uZK/fz544drZU1DvnenTzZW5AqIS2V1nTbkfXiHZTHj3ZuVomOcFNkjbZVp1H1a0u6mmchmKttT'
    b'4MQqaFWleV7QIdwnLNfoPzqcwapUVfqoSFZIr6vuwG4JnaWbosQkzc9bF/KzJWlbVzgXx/gC2pNQSFoO4xkFUptkPkbn8mxc'
    b'EF49kqMe6lKzijJonZbfdPbEc4uKT5MIKkXXl+RYhwILv8DGd9H1OW2Y5ps0u0u2aVHSHrC1bdOSQohDgMWSN95o0fVFHHVV'
    b'eo8p6abULFhX2a6uWfHwhccQQsldUeWsBTrFxjzwbKhmoxt3wowcigQxVQnJlx4+kkNanVhs94yIZnFEO+fyI8XMLyV4wY63'
    b'a8jZ+fBAh67dmyaxe2x05K23TXpgx4+jna40vEPnfG4+JDbC8XSZ1A388CEZnXgWpCTVjz6xBk/QV1fdVeaIvS/G0iXHfYHY'
    b'hVdi9HIBSTU8CqJtSwSseEyV0DuWkh4QIIZXpgfAnWHx4GiCdNaF15yMXnfQnMZZgXsViZSTuNjFdC1Gs4+kWQZEoy/sA/9h'
    b'sObdgtDzR0zZwypkpxsAz67IFIOOWujF4nJ5MY8EyRA53Wy5pkec6U63imyuuquI1iZw1PS0PqdEICPYKwSzsyB678ts9Lrb'
    b'IAKd+eAzf3QIVZaRARAaePTLjVa68VLH0S88JY6+l0+34z2eGehUJLJnnF7pFxsGP5XebqEqizTFMctnlnAEnnwaCHz7RP7B'
    b'Xk+GuWN9IcxtOOczco7WeGR4PjAosSYESpGIr6O3r1+/fnG5UECfttQTDXBNK6UfCBE3Ratq5EzdVCvFSKtXKi8Q4sQvrAKy'
    b'VnrHgB1RtjSlTivO3bJAeVLnhJmziNyu1TsQE/qM6bsKJpc9lewZYznslhOEDpSG8TX5CJKzcjuodq8rDD2VJs1Vsd0qGdES'
    b'r2iZPFzM2RNVqatdu5cJfSaw+CdtJCHoBw/bH35/t1Kv1pTO6NNsqTqcGJgNV321Xs4WC/HuFQmKrHw4kKSPZIXMNOKsTEw+'
    b't5SdYJURPyIV5Bq6ZI6jA/H50cPoTU/X4qgPkOBaoBUcrPAtwsKEwBAMaAvQ5Q9gPfwbI65iA2u3NHYZO4/Wa47HYa5RHb+y'
    b'JC9xAdrlYCrDL8C7WiFcfAzsJHC2vsCUkjhd4tTuzyepO2lPtWYC6eDR/WYayNYaTfb7e3uSSl4z2pFGGhAz27NGimDsMNCT'
    b'0w7OQfOqvDZF1T6vS0XHETKCQ+EslKqQO4sylzDdbpE8/VpvwQfbouXoSuvaBxPIE8QlZ/Q8VpidSw+9qD4XgvshgP2EW6cH'
    b'9g5hSs/ydThL7ie8d4zsyangM17NjqK6J04eCWcPz+M/cOa/8YsSKjZkuLF+nEqgHDb8fOh8h9Teset5x5rHwR8XMaUidsEr'
    b'MVKXlonzBtYvklBXtc7dyNFE0lBqkO8c/GnASTr/e4/M6g/RlxZf2v9K+YICIgbB5kHaxcgZb8f4iBWDteOot0bbdFWWtn0A'
    b'O78cEQd3KBJpdMrAo4cvPeUZvgvZ4bNnC5EY7KZf8zbq3eBmvDJ9chByM1r+lo75i88dgwMihYGZj9xy4K5EVbVtk97/pDDE'
    b'GnD8xkutyWX4Vw5im4kmrigjEHAg6R/ThmxB1JF/zqUGzTg4H1TIQHF0Gj4cixx4PXix18Vu3/ZvuMwkRQWU7X20K9sCUIdt'
    b'cZQuKVF9DRLwSOviTDfDL7f92s4rEOcghCrACrEZAOzwRbAeHw0LUJEaRBu6MsUI11y90/eTWcW3vfNh7heIomuT7X3wD3GR'
    b'8rst/iRINWbbM53EUSlXCC7ni+WoHhh/fjmbXV6+6H0UjBZMlMpJN+BqTqUqvXQJz3+4mM+4sisq+A4KCgLN6OpscX62OJst'
    b'Ls8oo37z1WKOH2dX87PZxddnF99wNfjNhVor2RgpVrlSdaVcMalqxJ3iShLx3RRY+0+wUClyAeRXIkFSw58Z1xPK2MwFQ5CI'
    b'xE7S+bmL1NHbxTy4yOj9DOuQBLyqTXSa7UMVK9wtoc+WN3QvpFz3K1xevbyaL0ZM78kWizGPfcYms4unIzhPDoecXzqW+GQ6'
    b'1eXSC3jG1BePknk7oWSN3iFcNOUja7oGwBAKbbKHoQZJo1CNik+ibPZE4hQrUBrECRElIaLq09sPYE+pFaInoC5lc6jR/+qb'
    b'YaEImPypGwODWwJd+FijS95tpTyJocgpQE1zzeSbtkQxgtFc1mBYDTjRwB/tqThKeN+JKhwIIpu1IDVWMTwSn6tkYyw5FU+Y'
    b'MkmJpdxXDcWnCkgXMxK+WgMEHV8kObjNhF0owFdCcib8TkkqVBu8KREkPFqKTRImsMQTUoB1uYdaT1CMPtQYIRl1SiEvGp/U'
    b'SE2YQue0rROSqJV3+yk3kBRPj9WANp0zzQ6F6Ur1Sc7tVZbmiKdjARyG5mAsVAFh1HSY+pi4rXyAnirQbMIhBRhqv1UfkAsG'
    b'4nt6MaGvOigFNBBYgvlylphIN3w52OTtTxYHKInx4tgUB3ZPwspiyhEZCEMtMUXMDB6CM3NDDta5ZDgxUsA6EyomJYpR/9Xa'
    b'icdP0Idp8eDf9ePsqzW1q1ZsXvYUq/YptuRn4uJsVpbZC8eZaTpYJBrXly4Chp4uen82HnyKVi5FQzUr5ev0vsXEcWHuWJpt'
    b'V4azSBdNDaBk5UMkwaoc+W5zpyxYZFPkiBkYBdTdFf5QJ1W2/YYhzho4X1Fx5Poz0ruGKg3xEe5esUOIlyPXWJypSXacMF2j'
    b'QXGm++73tx9+u5gn77//Z6yk/6F82vtu8GlwIKo1Je4Ct/YzphzbLrf5GH+i2AH3+W7+78uLyWyl+iwcA/xS8kzegfxS0IfY'
    b'lApsqtEH6MDVz+LiywVXjPSlnrpAot1//vyBm1wIF4CEVL3aVT59gndxsBJnUmyC82+/vZitRmFNR9dCdoP79R1JYe9Tx4aV'
    b'sJhD2tzpZqVc0aiccgI4DpZfCby+56bRa+kZqW1jDt4LejyTqHY+J4T5x7IgcchVrTXY8VAA5qrddNAVc15nAywM+Lk0kZL/'
    b'GLovCZ13iKQIJZXAh+DVEw1Yqire/hTLmUgTbnmqUacoROJQVYsxZb47Lo+yhC3yqB8o1tSma1uYj2K0ndpugzluAGwgH2Pl'
    b'G49Tbu7TSLOhA07hL5KoEPK2Nmx4xZIIKE+AmlPPZGlveb1S0gZlmXAcynICPdCNMhubdc4KZluU5UpUQwOmXEO5TEBl1poL'
    b'IU5tnV73XZE3UHJgr/JVvKrmskGuJBrdUfXqWD82h+uyla6vUSVrSoDX1y7Z9w3hRNIR2yjX2xTH4+3eUVPKDnvnQ/tQXRpL'
    b'kon7lOW7N5xaUwIXYIBuJlzFIu7xKBHqs31IKePol8wilxiiKHexEfuIeLXmxlVoBERyF+BfTO+FrE+fFFQhYh2ZH2CIYoJs'
    b'la/G1LOdBfJEIftu+JdNBrGvz/IMNm63FYPsaTrAYPkeskZfCR5CZyFyKnoaQIRyozgD6rTqYCylPEr0R9K9H74iRxZYpO7E'
    b'1PUlpqOOxB5hEXgKM3yqhBgSOCd6kIIancsj1WZNUVMCGDTJz0KnCgbn0t6xDecG6/MQM4MFKHKgUkPhE6KdGo+u4thzwuup'
    b'GvEOG/WXXg6EnJv2nuRDMt24jlgOXlmEziRqU1KZDPfK5XAAnJPfi3urlDJlyqTOv2FGYxoKEh8dA8QLwOZxLIA86QEHI+hf'
    b'+aN6CZ7qiyh0Q1HoWHYsCowxv3S3t0AX3z+PnqQT9g7BOQkkQpkpA8gIfEKXaAsLwGrBCdwdpx9H5gKSpBU1X1mfK5fBmOM+'
    b'uQ8aWtdD9UpILhtfgEwawdNwAWynrINpgJXpcNedpqa3GH/lte44hZgSNkmZi5KfeieRWivNe2cmNi3hPdk2Wisu/pTcF0lc'
    b'TkJRUpdIyj2SDThhWFF9xWWeZ4QOaWJHqPzrcKVCH78GvSH+ZVrl7g77WspNk1pqpZyweva++EHRnfvpV15JhHhaVQW2B9Az'
    b'OdcvdPVTHA4dWznm7DvhNjyxwFBa0I1rtQXsUTvEC+WILXMA1qQwMQ+qyCTEq6hWZA1MWdXPMbdeKf4anlnwciF8ZYzVK6eC'
    b'IVo+t2bQ6L9e//oRmshSIsSEvm4BVwvA635y011PrmQ3EuRtzZ2mixRHyoX5h32HPLYQg6Vhtc8gj/CSjK0ioc2EeptuGprE'
    b'V8u8PvWk061OBs14S+0kISb+jzbompXodyntTHebjv/aAjYjNyBUJi5L/4NR0HfBRkqJh5T/VAQI3NJFtruspbaytUegE1kw'
    b'zQvD/8uflTBd4oZ52mQ0SZgTd4FL1wum/7A//usaenfU+i5yfx8hs4VESRMTcR4Nbnj9dSsRqP7BMylqrtm+txf1lWRXOTjr'
    b'Kg9o2vX3rK+CKX9SVLrqT24KrGe5cln0DC3xQO/G+1Lzmda4v17jNqLsOrhcG9y5rdSzl8pqWJZL3WZHDWVpmyQS6n2l5Wo6'
    b'17axU/6ThCmXGtQoqHp26O7e7JRuzWK6LKOMJJ0HAVdUulwog/w2EIuC292XscvxgwwRJVkPKT1IsmeLOrn1l4Es7ODbIBB8'
    b'RggvdRJ2qGzIR5Dx2IBK8ZZdIyVoVwmEBwTzglCHq9tgBQnBTZcD7vGxqyDNTrM6D+ZeTzi7BDxTnxr6AxGdD64OBFM83T0T'
    b'JPTHqsyk3RNDclVuPuEApZiHn8Hi/AcVlAz47044L2ugiCUygmRmS0MGkj8igetJuh6uQVuYOiQo1z0SimWl+JE/ZHHD673k'
    b'8tDNYd0NqDUzTya5vhh8QgQ87EvDIyQS11uQinKQkC0XEL6J1POLQfNQ8uJgSvT4+Lf/Aidt6bU='
))

# Frozen c0c preimage template from the isolated PREIMAGES ledger. Identity
# values are rendered from the new retained recipe; all old output spelling stays.
LEGACY_TEMPLATE = zlib.decompress(base64.b64decode(
    b'eJytV21v2kgQ/u5fsddIPSwR3kM4J6lijJO4Bxhh015VVavFXsI2xra86zRpm/9+s8Y45gJtrqmlGDI7M8/O+1CvI2cy+OdwyDwa'
    b'cnpo+TQUbMFooiHDaBw2aw2lXkeXNKQJEdRHURjcIxYiEqLoSwgEn/HPEQsFilIRpwKJhNIacqI08ShaEE9wRBKKwkigJAXdK4ro'
    b'LQMYj9ak6jiJFiyg+DOPQpRyypFYUrSMuPiTI3oHClCrcwg3CnwUszsaoChB7caGsrznzCMB8qJQJMB8InUu0iBAAVuxHNxbUu8G'
    b'7sppTKQZaxMMtKKC+EQQsMbPYBMgMGlVnNCAhTcoDkhYUw7YIvTpAl3Ys/FAdy17jPXJxBwPzAEe2MZsZI5dbNgTC/43x5fW2MQj'
    b'09WBVcdXygGIgtJflWahF6Q+RackScj9mxLB48IHz5dJXCQsvMa3jH4pkxdRGoKhLArrJI4pGOPXaXgNt8LgfxmOBPuRl64g+vi2'
    b'VVuWhF/12dzMeI0oZtQf5HwXMra15StFCcmK8pjIeBc4mrYB0rRCs5cpwIXbvyksDKRrIHpc0Ls4QXM217Q1n6ZtoNbAk3WmAPMq'
    b'hk8f56mDzp4hpWnnhj2aWENw8mRqX8CX85On8OBRTUvBqd0OFsgjMZmzgAkGaXmGZtbYBbpROTf0id63hpZrmc65+iM97RbomSfM'
    b'v6YYdIGW7tFRu5vuk8mCfFqI97CoonbrTZHfeEmJjBZfktZRF9R9+waGjd2pbrjYudKBiPsfXLjWw8P/xZgTTnfp7+uOia9MfWBO'
    b'XwpRpMIOmKIWfjOUB6kWRNe7sQyosqF9+VIwTlcEmpuHeUhivowE5tB0VmQL1DFH+ti1DOyM9YlzZUPAjCugvRR8ESUrDLkBZbcL'
    b'9sKejjCkh2w8vweQeDe7gHTj798EME9Z4GOWDSNxv52MM2s4wNYAgme5H14ct2xO4YR6LKbbwbJnU8PEU9OwJuYzYLwlSbaG2cdP'
    b'oOg87zX4rWOPdzWcorn2pcnvmmvT5RUUBA9nX2m0qPyXS62ivtXfTIuh/sGeufhds5rJlE5cfXppurg/td87UFHvdWe0JWlMZhmx'
    b'3ZLuSJ/ID60L07VGpmyZhuk4VdRMq6gBf72GfHezd7lNrlXs7UlV9JMISoYfuV7Z5fvCPcNs5oMX8+G/z40bPvBjt9Xpgg2dHrya'
    b'jU7v6Lhb/paJy7NuJ7e8mALd42aj1+t21BKt2e60msfHrZ4qL1oaa1EUFOuGIcnQLvg7EjC/osJyRO88GgtlfdtMDJFURHASfqVJ'
    b'BIZ8/FR5pL9G83tBuZqbJx9oAqiSycgjpG042AJVMsofZ6ihyg0nTULY0lJ6UsjmxAUJeE59WH/kB3vdh87OpOcKRa9fb25c2VnC'
    b'apljV+2pZVWVytNR/7xZv14UQcX2BC+N8ObxX0fqI5p8vn9Hvw642UN/hNlqNNqqumVieTPYrAZb59KLtVgu2DAt51lOn8lSlYd5'
    b'WMpNR0VvoETLGnYyHQITOt22zN+yLNvuDLDEg+idKA8KZKycb4RzmojKvlR+3IW2Mn5PoufptbcupAN+csUREd6yUhicdfjSErxl'
    b'd3W/M6CGM1dX885RfbJlqtIJDwh+XfzquqscAANbKP8CLMlvQA=='
))


def load_generator(path):
    module = types.ModuleType('_metadata_fixture_generator')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


adapter = load_generator(GENERATOR)


def write(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    for parent in path.parents:
        if parent == root:
            break
        parent.chmod(0o755)
    path.write_bytes(raw)
    path.chmod(0o644)
    return path


class DocumentMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='document-metadata-source-only-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.assertEqual(adapter.digest(SCHEMA), contract.DOCUMENT_SCHEMA_SHA256)

    def fixture(self, selected='pixel'):
        source, output = self.base / 'sources', self.base / 'output'
        source.mkdir(mode=0o755)
        output.mkdir(mode=0o755)
        inputs = {}
        def retain(name, raw, role='source'):
            write(source, name, raw)
            inputs[name] = {'sha256': adapter.digest(raw), 'role': role, 'mode': 0o644}
        retain(RETAINED_GENERATOR, GENERATOR.read_bytes(), 'tool')
        retain(str(Path(RETAINED_GENERATOR).with_name(TEMPLATE.name)), TEMPLATE.read_bytes(), 'config')
        helpers = (*adapter.HELPERS, adapter.CONTRACT_HELPER)
        if selected == 'editor':
            helpers += (adapter.EDITOR_CONTRACT_HELPER,)
        for name in helpers:
            retain(name, (ROOT / name).read_bytes(), 'helper')
        for _, (name, _) in adapter.PIN_FILES.items():
            retain(name, SCHEMA if name.endswith('/schema-definition.json') else (ROOT / name).read_bytes(), 'interface')
        if selected in ('physical', 'editor'):
            retain(adapter.PHYSICAL_CATALOG, inert.PHYSICAL_CATALOG, 'interface')
        if selected == 'editor':
            for name, _ in adapter.EDITOR_PIN_FILES.values():
                retain(name, (ROOT / name).read_bytes(), 'interface')
        retain('archives/wrapper.tar.xz', b'inert source marker, never unpacked\n')
        retain('archives/engine.tar.xz', b'inert engine marker, never unpacked\n')
        retain(inert.NOTICE_PATH, b'Parser fixture only; no engine distribution.\n', 'license')
        recipe = {
            'schema_version': 1, 'kind': 'foundation-appended-engine-recipe', 'producer_version': 1,
            'target': {'system': 'Emscripten', 'processor': 'wasm32',
                       'triple': 'wasm32-unknown-emscripten', 'pointer_bits': 32},
            'toolchain': {'cxx_standard': 23, 'identity_sha256': adapter.digest(b'inert toolchain'),
                'runtime_policy': 'paired-emscripten', 'paired_sdk_sha256': adapter.digest(b'inert SDK identity'),
                'target_baseline': 'source metadata fixture only'},
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'},
            'provider': {'format': 'browser-module', 'binding': 'copied-owner-bridge', 'abi_major': 1,
                'abi_minor': 1, 'header': 'include/foundation/appended/engine_provider.h',
                'header_sha256': contract.BASE_HEADER_SHA256},
            'suppliers': {name: {'repository': 'https://example.invalid/' + name,
                'commit': digit * 40, 'archive': 'archives/' + name + '.tar.xz'}
                for name, digit in (('wrapper', '1'), ('engine', '2'))},
            'inputs': inputs, 'patches': [], 'licenses': [inert.NOTICE_PATH],
        }
        retain('prelink-plan.json', adapter.encoded(adapter.fixed_plan(recipe, selected)), 'config')
        write(source, 'recipe.json', adapter.encoded(recipe))
        module = load_generator(source / RETAINED_GENERATOR)
        arguments = dict(source_root=str(source), build_root=str(output), recipe=str(source / 'recipe.json'),
            build_plan=str(source / 'prelink-plan.json'), document_profile=selected,
            physical_catalog=str(source / adapter.PHYSICAL_CATALOG) if selected in ('physical', 'editor') else None,
            output_header=str(output / 'BibDocumentCopiedMetadata.generated.h'),
            output_build=str(output / 'provider-build.json'))
        arguments.update({argument: str(source / name) for argument, (name, _) in adapter.PIN_FILES.items()})
        arguments.update({argument: str(source / name) if selected == 'editor' else None
                          for argument, (name, _) in adapter.EDITOR_PIN_FILES.items()})
        return module, types.SimpleNamespace(**arguments), recipe

    def save_recipe(self, args, recipe):
        write(Path(args.source_root), 'recipe.json', adapter.encoded(recipe))

    def replace_input(self, args, recipe, name, raw):
        write(Path(args.source_root), name, raw)
        recipe['inputs'][name]['sha256'] = adapter.digest(raw)
        self.save_recipe(args, recipe)

    def outputs_absent(self, args):
        self.assertFalse(Path(args.output_header).exists())
        self.assertFalse(Path(args.output_build).exists())

    def decoded(self, args):
        raw = Path(args.output_build).read_bytes()
        header = Path(args.output_header).read_text()
        literal = re.search(r'inline constexpr char profile_json\[\] = (.+);', header).group(1)
        facts_raw = json.loads(literal)
        return raw, contract.strict_json(raw), header, facts_raw, contract.strict_json(facts_raw)

    def assert_consumer(self, args, recipe, raw_build, facts):
        # Rebind a permanently ineligible inert group to the adapter's ACTUAL
        # emitted Build/recipe bytes. Only the real consumer's pure inspection
        # runs: no Wasm/factory/report/SDK tool is instantiated or evaluated.
        group = inert.DocumentEngineFixture(self.base / 'inert-consumer', document_profile=args.document_profile)
        recipe_hash, build_hash = adapter.digest(Path(args.recipe).read_bytes()), adapter.digest(raw_build)
        group.recipe = recipe
        group.toolchain = recipe['toolchain']
        group.build = contract.strict_json(raw_build)
        group.profile = facts
        group.source = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
            'producer_version': 1, 'recipe_id': recipe_hash,
            **manifest.tree_inventory(Path(args.source_root), 'sources.json')}
        source_hash = adapter.digest(adapter.encoded(group.source))
        group.runtime.update(recipe_id=recipe_hash, provider_build_sha256=build_hash,
            paired_sdk_sha256=recipe['toolchain']['paired_sdk_sha256'], engine_profile=facts,
            bootstrap=inert.bootstrap(facts))
        group.proof.update(recipe_id=recipe_hash, sources_sha256=source_hash,
            provider_build={'path': inert.BUILD_PATH, 'sha256': build_hash}, engine_profile=facts,
            runtime_evidence={'path': inert.RUNTIME_PATH, 'sha256': adapter.digest(adapter.encoded(group.runtime))})
        group.binary_manifest.update(recipe_id=recipe_hash, sources_sha256=source_hash,
            toolchain=recipe['toolchain'], options=recipe['options'])
        for path, raw in ((inert.BUILD_PATH, raw_build), (inert.RUNTIME_PATH, adapter.encoded(group.runtime)),
                          (inert.PROOF_PATH, adapter.encoded(group.proof))):
            group.binary_manifest['files'][path] = adapter.digest(raw)
        inspection = consumer.inspect_embedded_consumer(evidence=group.evidence(), assets=group.assets,
            notices=group.notices, pins=group.pins(), kernel_target=recipe['target'],
            paired_sdk=recipe['toolchain']['paired_sdk_sha256'], document_profile=args.document_profile)
        self.assertFalse(inspection.metadata['production_eligible'])
        self.assertEqual(inspection.metadata['provider_build_sha256'], build_hash)

    def assert_editor_consumer(self, args, recipe, raw_build, facts):
        # The independent inert byte builder supplies only typed Wasm sections;
        # nothing is instantiated. Runtime/bootstrap checks remain not-run and
        # scope stays parser-fixture-only regardless of generated source facts.
        group = inert.DocumentEngineFixture(self.base / 'inert-editor-consumer', document_profile='physical')
        recipe_hash, build_hash = adapter.digest(Path(args.recipe).read_bytes()), adapter.digest(raw_build)
        group.recipe = recipe
        group.toolchain = recipe['toolchain']
        group.build = contract.strict_json(raw_build)
        group.profile = facts
        group.interfaces = {name: (Path(args.source_root) / name).read_bytes()
                            for name in editor_contract.INTERFACE_PATHS.values()}
        group.interface_refs = {role: {'path': name, 'sha256': adapter.digest(group.interfaces[name])}
                                for role, name in editor_contract.INTERFACE_PATHS.items()}
        group.source = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
            'producer_version': 1, 'recipe_id': recipe_hash,
            **manifest.tree_inventory(Path(args.source_root), 'sources.json')}
        source_hash = adapter.digest(adapter.encoded(group.source))
        group.assets[inert.WASM_PATH] = inert.tiny_wasm(
            omit=('bib_engine_wasm_document_facts_v1', 'bib_engine_wasm_document_configure_v1'),
            extra=(('bib_engine_wasm_editor_facts_v1', 0, 4), ('bib_engine_wasm_editor_configure_v1', 0, 5)))
        group.asset_records[inert.WASM_PATH].update(sha256=adapter.digest(group.assets[inert.WASM_PATH]),
                                                   bytes=len(group.assets[inert.WASM_PATH]))
        bootstrap = inert.bootstrap(facts)
        bootstrap['engine_facts']['export'] = 'bib_engine_wasm_editor_facts_v1'
        bootstrap['engine_configure']['export'] = 'bib_engine_wasm_editor_configure_v1'
        bootstrap['checks'] = {name: 'not-run' for name in editor_contract.BOOTSTRAP_CHECKS}
        group.reports = {}
        group.runtime.update(kind=editor_contract.RUNTIME_KIND, scope='parser-fixture-only', status='incomplete',
            recipe_id=recipe_hash, provider_build_sha256=build_hash, engine_profile=facts,
            assets_sha256=adapter.digest(adapter.encoded(group.asset_records)),
            paired_sdk_sha256=recipe['toolchain']['paired_sdk_sha256'], bootstrap=bootstrap,
            provider_observation={'getter_maximum_minor': 1, 'contract': group.build['provider_contract']},
            checks={name: {'status': 'not-run', 'evidence': []}
                    for name in editor_contract.runtime_checks(editor_profile='editor')})
        group.proof.update(kind=editor_contract.PROOF_KIND, recipe_id=recipe_hash,
            sources_sha256=source_hash, provider_build={'path': inert.BUILD_PATH, 'sha256': build_hash},
            engine_profile=facts, interfaces=group.interface_refs, assets=group.asset_records,
            wasm_facts=inert.scan_wasm(group.assets[inert.WASM_PATH]),
            runtime_evidence={'path': inert.RUNTIME_PATH, 'sha256': adapter.digest(adapter.encoded(group.runtime))})
        group.binary_manifest.update(recipe_id=recipe_hash, sources_sha256=source_hash,
            toolchain=recipe['toolchain'], options=recipe['options'])
        binary = self.base / 'editor-inert-binary'
        binary.mkdir()
        for name, raw in {**group.assets, **group.notices, **group.interfaces,
                          inert.BUILD_PATH: raw_build, inert.RUNTIME_PATH: adapter.encoded(group.runtime),
                          inert.PROOF_PATH: adapter.encoded(group.proof)}.items():
            write(binary, name, raw)
        group.binary_manifest.update(manifest.tree_inventory(binary, 'engine-sdk.json'))
        inspection = editor_consumer.inspect_embedded_consumer(evidence=group.evidence(), assets=group.assets,
            notices=group.notices, pins=group.pins(), kernel_target=recipe['target'],
            paired_sdk=recipe['toolchain']['paired_sdk_sha256'], editor_profile='editor')
        self.assertFalse(inspection.metadata['production_eligible'])
        self.assertFalse(inspection.metadata['whole_group_verified'])
        self.assertEqual(inspection.metadata['provider_build_sha256'], build_hash)
        self.assertEqual(inspection.metadata['recipe_id'], recipe_hash)
        self.assertEqual(group.runtime['status'], 'incomplete')
        self.assertEqual(group.runtime['scope'], 'parser-fixture-only')
        self.assertEqual(group.reports, {})
        self.assertTrue(all(check['status'] == 'not-run' and not check['evidence']
                            for check in group.runtime['checks'].values()))

    def test_editor_actual_build_passes_ineligible_static_consumer_with_exact_38_facts(self):
        module, args, recipe = self.fixture('editor')
        result = module.generate(args)
        raw, build, header, facts_raw, facts = self.decoded(args)
        editor_contract.require_fields(build, editor_contract.BUILD_FIELDS, 'editor build')
        self.assertEqual(len(build), 13)
        self.assertEqual(build['kind'], editor_contract.BUILD_KIND)
        self.assertEqual(build['binding'], editor_contract.BINDING)
        self.assertEqual(build['contract_header_sha256'], editor_contract.CONTRACT_SHA256)
        self.assertEqual(build['configuration'], editor_contract.expected_configuration(editor_profile='editor'))
        self.assertEqual(build['provider_contract'], editor_contract.provider_contract(editor_profile='editor'))
        self.assertEqual(build['source_inputs_sha256'], adapter.digest(adapter.encoded(recipe['inputs'])))
        self.assertEqual(result['contract_header_sha256'], editor_contract.CONTRACT_SHA256)
        self.assertEqual(facts, editor_contract.expected_engine_profile(editor_profile='editor',
            build_sha256=adapter.digest(raw), source_recipe_sha256=adapter.digest(Path(args.recipe).read_bytes())))
        self.assertEqual(len(facts), 38)
        self.assertEqual(facts_raw, editor_contract.canonical_json(facts).decode().rstrip('\n'))
        self.assertLessEqual(len(facts_raw), 4095)
        self.assertIn('DocumentCopiedProfile::editor', header)
        self.assertIn('capabilities = UINT64_C(2035)', header)
        self.assertIn('sizeof(BibEngineLimitsV1), 1048576u, 236u, 1048576u', header)
        self.assertIn('surface_protocol_version = 2u', header)
        self.assertIn('surface_capabilities = UINT64_C(8255)', header)
        self.assertNotRegex(header, r'@[A-Z_0-9]+@')
        self.assert_editor_consumer(args, recipe, raw, facts)

    def test_editor_interfaces_are_explicit_and_rejected_by_old_profiles(self):
        module, args, _ = self.fixture('editor')
        for name in ('physical_catalog', *module.EDITOR_PIN_FILES):
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.generate(types.SimpleNamespace(**{**vars(args), name: None}))
        for selected in ('pixel', 'physical', '2035', 'Editor', 'editor ', None, True):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                module.generate(types.SimpleNamespace(**{**vars(args), 'document_profile': selected}))
        self.outputs_absent(args)

    def test_editor_interfaces_require_canonical_paths_and_original_bytes(self):
        module, args, recipe = self.fixture('editor')
        for argument, (name, _) in module.EDITOR_PIN_FILES.items():
            original = Path(args.source_root, name).read_bytes()
            with self.subTest(path=argument), self.assertRaisesRegex(ValueError, 'canonical retained input'):
                module.generate(types.SimpleNamespace(**{**vars(args), argument: args.document_contract}))
            self.replace_input(args, recipe, name, original + b'\n')
            with self.subTest(bytes=argument), self.assertRaisesRegex(ValueError, 'approved profile'):
                module.generate(args)
            self.replace_input(args, recipe, name, original)
        self.outputs_absent(args)

    def test_editor_helper_is_retained_and_does_not_use_cached_contracts(self):
        module, args, recipe = self.fixture('editor')
        with mock.patch.dict(sys.modules, {'appended_engine_document_contract': object(),
                                           'appended_engine_editor_contract': object(),
                                           '_foundation_editor_metadata_contract': object()}):
            module.generate(args)
        recipe['inputs'][module.EDITOR_CONTRACT_HELPER]['role'] = 'source'
        self.save_recipe(args, recipe)
        with self.assertRaisesRegex(ValueError, 'absent from recipe'):
            module.generate(args)

    def test_old_editor_contract_pins_require_explicit_adapter_revision(self):
        module, args, recipe = self.fixture('editor')
        name = module.EDITOR_CONTRACT_HELPER
        raw = Path(args.source_root, name).read_bytes().replace(
            editor_contract.CONTRACT_SHA256.encode(),
            b'21da51816310805f9153388d4dc120c6730f940d099078fa8d7f21c8939d5f1d')
        self.replace_input(args, recipe, name, raw)
        with self.assertRaisesRegex(ValueError, 'explicit metadata adapter revision'):
            module.generate(args)
        self.outputs_absent(args)

    def test_editor_prelink_is_exact_and_cannot_downgrade(self):
        module, args, recipe = self.fixture('editor')
        original = module.document(Path(args.build_plan).read_bytes())
        mutations = (
            lambda plan: plan.update(capabilities='2003'),
            lambda plan: plan['configuration'].update(editor_profile=contract.PROFILE_NAMES['physical']),
            lambda plan: plan['limits'].update(maximum_command_bytes=6246),
            lambda plan: plan.update(surface_protocol_version=1),
            lambda plan: plan['provider_contract']['commands'][-1].update(operation=2),
            lambda plan: plan.update(extra=True),
        )
        for change in mutations:
            changed = copy.deepcopy(original)
            change(changed)
            self.replace_input(args, recipe, 'prelink-plan.json', module.encoded(changed))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'prelink plan differs'):
                module.generate(args)
            self.outputs_absent(args)

    def test_all_fixture_modules_are_isolated_workingroot_copies(self):
        for module in (contract, consumer, manifest, inert, editor_contract, editor_consumer):
            self.assertTrue(Path(module.__file__).resolve().is_relative_to(ROOT), module.__file__)

    def golden(self, selected, count):
        module, args, recipe = self.fixture(selected)
        result = module.generate(args)
        raw, build, header, facts_raw, facts = self.decoded(args)
        self.assertEqual(set(build), {'schema_version', 'kind', 'target', 'toolchain', 'options',
            'source_recipe_sha256', 'source_inputs_sha256', 'contract_header_sha256', 'binding',
            'configuration', 'capabilities', 'bridge_abi', 'provider_contract'})
        self.assertEqual(len(build), 13)
        self.assertEqual(build['kind'], 'foundation-neutral-engine-provider-document-v2-build-v1')
        self.assertEqual(build['configuration'], contract.expected_configuration(document_profile=selected))
        self.assertEqual(build['provider_contract'], contract.provider_contract(document_profile=selected))
        self.assertEqual(build['contract_header_sha256'], contract.CONTRACT_SHA256)
        self.assertEqual(build['source_recipe_sha256'], adapter.digest(Path(args.recipe).read_bytes()))
        self.assertEqual(build['source_inputs_sha256'], adapter.digest(adapter.encoded(recipe['inputs'])))
        self.assertNotEqual(build['source_inputs_sha256'], adapter.digest(contract.canonical_json(recipe['inputs'])))
        self.assertEqual(result['provider_build_sha256'], adapter.digest(raw))
        self.assertEqual(result['scope'], 'source-metadata-only-no-runtime-evidence')
        self.assertEqual(len(facts), count)
        self.assertEqual(facts, contract.expected_engine_profile(document_profile=selected,
            build_sha256=adapter.digest(raw), source_recipe_sha256=adapter.digest(Path(args.recipe).read_bytes())))
        self.assertEqual(facts_raw, contract.canonical_json(facts).decode().rstrip('\n'))
        self.assertLessEqual(len(facts_raw), 4095)
        self.assertIn('DocumentCopiedProfile::' + selected, header)
        self.assertIn('static_assert(metadataConstantsValid());', header)
        self.assertIn('sizeof(profile_json) - 1u < bib::copied::documentCopiedFactsCapacity', header)
        self.assertIn('sizeof(BibEngineLimitsV1), 6246u, 48u, 1048576u', header)
        self.assertNotRegex(header, r'@[A-Z_0-9]+@')
        self.assert_consumer(args, recipe, raw, facts)

    def legacy_render_golden(self, selected):
        self.assertEqual(adapter.digest(LEGACY_TEMPLATE),
                         'c0c05c88e3e40de13e30d9696dab7ad5218dfba23823a580753e352db3d57d1a')
        module, args, recipe = self.fixture(selected)
        module.generate(args)
        raw, _, header, facts_raw, _ = self.decoded(args)
        hashes = {**module.PINS, 'build_identity_sha256': module.digest(raw),
                  'source_recipe_sha256': module.digest(Path(args.recipe).read_bytes())}
        expected = LEGACY_TEMPLATE.decode()
        replacements = {'@' + key.upper() + '_BYTES@':
                        ', '.join('0x' + value[i:i + 2] for i in range(0, 64, 2))
                        for key, value in hashes.items()}
        replacements.update({'@COMPILED_PROFILE@': selected,
                             '@CAPABILITIES@': contract.CAPABILITIES[selected],
                             '@PROFILE_JSON@': json.dumps(facts_raw, ensure_ascii=True)})
        for name, value in replacements.items():
            self.assertIn(name, expected)
            expected = expected.replace(name, value)
        self.assertEqual(header, expected)
        physical = ({**contract.PHYSICAL_FACTS, 'physical_catalog_path': module.PHYSICAL_CATALOG}
                    if selected == 'physical' else {})
        legacy_plan = {
            'schema_version': 1, 'kind': 'foundation-copied-engine-document-prelink-plan-v1',
            'target': recipe['target'], 'toolchain': recipe['toolchain'], 'options': recipe['options'],
            'binding': contract.BINDING,
            'configuration': contract.expected_configuration(document_profile=selected),
            'capabilities': contract.CAPABILITIES[selected], 'bridge_abi': 65536,
            'profile': contract.PROFILE_NAMES[selected], 'abi_major': 1, 'abi_minor': 1,
            **module.PINS, 'limits': dict(module.LIMITS), 'retention': dict(module.RETENTION),
            'provider_contract': contract.provider_contract(document_profile=selected), **physical,
        }
        self.assertEqual(Path(args.build_plan).read_bytes(), module.encoded(legacy_plan))
        self.assertNotIn(module.EDITOR_CONTRACT_HELPER, recipe['inputs'])
        self.assertNotIn('editor_header_sha256', header)

    def test_pixel_header_matches_original_rendering_with_truthful_new_identities(self):
        self.legacy_render_golden('pixel')

    def test_physical_header_matches_original_rendering_with_truthful_new_identities(self):
        self.legacy_render_golden('physical')

    def test_pixel_actual_build_passes_static_consumer_with_exact_24_facts(self):
        self.golden('pixel', 24)

    def test_physical_actual_build_passes_static_consumer_with_exact_30_facts(self):
        self.golden('physical', 30)

    def test_selection_is_required_explicit_and_catalog_is_profile_specific(self):
        module, args, _ = self.fixture()
        for selected in (None, True, 1, '', '1795', 'Pixel', 'physical ', 'copied259'):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                module.generate(types.SimpleNamespace(**{**vars(args), 'document_profile': selected}))
        for changed in ({'document_profile': 'physical'}, {'physical_catalog': args.document_catalog}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                module.generate(types.SimpleNamespace(**{**vars(args), **changed}))
        self.outputs_absent(args)

    def test_prelink_configuration_and_provider_operations_are_exact(self):
        module, args, recipe = self.fixture()
        original = module.document(Path(args.build_plan).read_bytes())
        mutations = (
            lambda plan: plan['configuration'].update(profile='browser-wasm32-cpu-direct-owner-v1'),
            lambda plan: plan['configuration'].update(document_profile=contract.PROFILE_NAMES['physical']),
            lambda plan: plan['provider_contract']['commands'][0].update(maximum_input_bytes=6247),
            lambda plan: plan.update(extra=True),
            lambda plan: plan.update(nested={'generated_header_sha256': 'f' * 64}),
        )
        for change in mutations:
            plan = copy.deepcopy(original)
            change(plan)
            self.replace_input(args, recipe, 'prelink-plan.json', module.encoded(plan))
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.generate(args)
            self.outputs_absent(args)

    def test_provider_minor_is_exact_integer_one(self):
        module, args, recipe = self.fixture()
        for minor in (0, 2, True, 1.0):
            recipe['provider']['abi_minor'] = minor
            self.save_recipe(args, recipe)
            with self.subTest(minor=minor), self.assertRaises(ValueError):
                module.generate(args)
        self.outputs_absent(args)

    def test_base_header_requires_actual_file_hash_and_canonical_path(self):
        module, args, recipe = self.fixture()
        recipe['provider']['header_sha256'] = contract.CONTRACT_SHA256
        self.save_recipe(args, recipe)
        with self.assertRaises(ValueError):
            module.generate(args)
        recipe['provider']['header_sha256'] = contract.BASE_HEADER_SHA256
        self.save_recipe(args, recipe)
        args.contract_header = args.document_header
        with self.assertRaisesRegex(ValueError, 'canonical retained input'):
            module.generate(args)
        self.outputs_absent(args)

    def test_physical_catalog_must_have_fixed_bytes_and_top_canonical_path(self):
        module, args, recipe = self.fixture('physical')
        args.physical_catalog = args.document_catalog
        with self.assertRaisesRegex(ValueError, 'canonical retained input'):
            module.generate(args)
        args.physical_catalog = str(Path(args.source_root) / module.PHYSICAL_CATALOG)
        self.replace_input(args, recipe, module.PHYSICAL_CATALOG, b'changed catalog\n')
        with self.assertRaisesRegex(ValueError, 'approved document profile'):
            module.generate(args)
        self.outputs_absent(args)

    def test_every_fixed_interface_requires_original_bytes_despite_recipe_rebinding(self):
        module, args, recipe = self.fixture()
        name = module.PIN_FILES['action_ack'][0]
        self.replace_input(args, recipe, name, b'{}\n')
        with self.assertRaisesRegex(ValueError, 'approved profile'):
            module.generate(args)
        self.outputs_absent(args)

    def test_common_contract_is_retained_as_helper_not_cached_import(self):
        module, args, recipe = self.fixture()
        with mock.patch.dict(sys.modules, {'_foundation_document_metadata_contract': object(),
                                           'appended_engine_document_contract': object()}):
            result = module.generate(args)
        self.assertEqual(result['scope'], 'source-metadata-only-no-runtime-evidence')
        recipe['inputs'][module.CONTRACT_HELPER]['role'] = 'source'
        self.save_recipe(args, recipe)
        with self.assertRaisesRegex(ValueError, 'absent from recipe'):
            module.generate(args)

    def test_generator_template_and_old_helpers_remain_hash_bound(self):
        module, args, _ = self.fixture()
        for name in (RETAINED_GENERATOR, str(Path(RETAINED_GENERATOR).with_name(TEMPLATE.name)),
                     *module.HELPERS, module.CONTRACT_HELPER):
            path = Path(args.source_root) / name
            original = path.read_bytes()
            path.write_bytes(original + b'\n# changed retained bytes\n')
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.generate(args)
            path.write_bytes(original)
        self.outputs_absent(args)

    def test_complete_retained_inventory_rejects_extra_files_and_changed_modes(self):
        module, args, _ = self.fixture()
        extra = write(Path(args.source_root), 'unlisted.txt', b'extra')
        with self.assertRaises(ValueError):
            module.generate(args)
        extra.unlink()
        Path(args.action_ack).chmod(0o755)
        with self.assertRaises(ValueError):
            module.generate(args)
        self.outputs_absent(args)

    def test_late_input_changes_prevent_all_output(self):
        module, args, _ = self.fixture()
        retained = module.load_manifest
        def wrapped(root, inputs):
            loaded = retained(root, inputs)
            verify = loaded.verify_inputs
            calls = 0
            def late(root):
                nonlocal calls
                calls += 1
                if calls == 2:
                    Path(args.action_ack).write_bytes(b'changed during generation')
                return verify(root)
            loaded.verify_inputs = late
            return loaded
        with mock.patch.object(module, 'load_manifest', side_effect=wrapped), self.assertRaises(ValueError):
            module.generate(args)
        self.outputs_absent(args)

    def test_idempotent_outputs_keep_inodes_and_still_reverify(self):
        module, args, _ = self.fixture()
        result = module.generate(args)
        before = {path: Path(path).stat().st_ino for path in (args.output_header, args.output_build)}
        self.assertEqual(module.generate(args), result)
        self.assertEqual(before, {path: Path(path).stat().st_ino for path in before})
        Path(args.action_ack).write_bytes(b'changed after successful source generation')
        with self.assertRaises(ValueError):
            module.generate(args)

    def test_existing_different_header_blocks_build_before_publication(self):
        module, args, _ = self.fixture()
        Path(args.output_header).write_bytes(b'foreign header')
        with self.assertRaisesRegex(ValueError, 'existing metadata output differs'):
            module.generate(args)
        self.assertEqual(Path(args.output_header).read_bytes(), b'foreign header')
        self.assertFalse(Path(args.output_build).exists())

    def test_output_paths_are_distinct_disjoint_and_inside_build_root(self):
        module, args, _ = self.fixture()
        for changed in ({'output_header': args.output_build}, {'output_build': str(self.base / 'outside.json')},
                        {'build_root': args.source_root}, {'build_root': str(Path(args.source_root) / 'source')}):
            with self.subTest(changed=changed), self.assertRaises((ValueError, OSError)):
                module.generate(types.SimpleNamespace(**{**vars(args), **changed}))
        self.outputs_absent(args)

    def test_noncanonical_symlink_and_hardlink_inputs_are_rejected(self):
        module, args, _ = self.fixture()
        for value in ('relative', args.action_ack + '/..', str(Path(args.source_root)) + '//recipe.json'):
            with self.subTest(value=value), self.assertRaises((ValueError, OSError)):
                module.ordinary(value, False)
        alias = self.base / 'alias.json'
        alias.symlink_to(args.action_ack)
        with self.assertRaises(ValueError):
            module.read_file(alias)
        alias.unlink()
        os.link(args.action_ack, alias)
        with self.assertRaises(ValueError):
            module.generate(args)
        self.outputs_absent(args)

    def test_output_symlink_and_simulated_physical_directory_alias_reject(self):
        module, args, _ = self.fixture()
        Path(args.output_header).symlink_to(args.action_ack)
        with self.assertRaises(ValueError):
            module.generate(args)
        Path(args.output_header).unlink()
        with self.assertRaisesRegex(ValueError, 'physically disjoint'):
            module.check_output_isolation(Path(args.output_header), Path(args.build_root),
                {module.identity(Path(args.build_root).stat())[:2]})
        self.outputs_absent(args)

    def test_output_link_never_replaces_competing_destination(self):
        output = self.base / 'destination'
        link = os.link
        def compete(source, destination):
            Path(destination).write_bytes(b'competitor')
            return link(source, destination)
        with mock.patch.object(adapter.os, 'link', side_effect=compete), self.assertRaises(FileExistsError):
            adapter.write_output(output, b'ours', None)
        self.assertEqual(output.read_bytes(), b'competitor')
        self.assertEqual(list(self.base.iterdir()), [output])

    def test_temporary_substitution_is_rejected_before_destination_publication(self):
        output = self.base / 'destination'
        snapshot = adapter.output_snapshot
        calls = 0
        def replace_temporary(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                temporary = next(self.base.glob('.destination.*'))
                replacement = self.base / 'replacement'
                replacement.write_bytes(b'substituted')
                replacement.replace(temporary)
            return snapshot(path)
        with mock.patch.object(adapter, 'output_snapshot', side_effect=replace_temporary), self.assertRaises(ValueError):
            adapter.write_output(output, b'ours', None)
        self.assertFalse(output.exists())
        self.assertEqual(len(list(self.base.glob('.destination.*'))), 1)

    def test_header_publication_failure_preserves_valid_build_and_reports_partial_save(self):
        module, args, _ = self.fixture()
        save = module.write_output
        def fail_header(path, raw, before):
            if path == Path(args.output_header):
                raise OSError('injected header save failure')
            return save(path, raw, before)
        with mock.patch.object(module, 'write_output', side_effect=fail_header), self.assertRaisesRegex(
                ValueError, 'provider-build output saved; header publication failed'):
            module.generate(args)
        self.assertTrue(Path(args.output_build).is_file())
        self.assertFalse(Path(args.output_header).exists())
        contract.require_fields(contract.strict_json(Path(args.output_build).read_bytes()), contract.BUILD_FIELDS, 'build')

    def test_json_rejects_duplicates_bom_unicode_nonfinite_and_oversize(self):
        for raw in (b'{"x":1,"x":2}', b'{"outer":{"a":1,"\\u0061":2}}', b'NaN', b'Infinity',
                    b'-Infinity', b'1e999', b'"\xff"', b'"\\ud800"', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                adapter.document(raw)
        with mock.patch.object(adapter, 'MAX_DOCUMENT', 1), self.assertRaises(ValueError):
            adapter.document(b'{}')

    def test_facts_4096_bytes_are_rejected_before_any_publication(self):
        module, args, _ = self.fixture()
        canonical = module.canonical
        with mock.patch.object(module, 'canonical', side_effect=lambda value: canonical(value).ljust(4096)), self.assertRaisesRegex(
                ValueError, '4095-byte host bound'):
            module.generate(args)
        self.outputs_absent(args)

    def test_fixed_plan_owns_limits_and_has_no_generated_identity(self):
        _, _, recipe = self.fixture()
        first = adapter.fixed_plan(recipe, 'pixel')
        adapter.reject_circular(first)
        first['limits']['maximum_command_bytes'] = 0
        self.assertEqual(adapter.fixed_plan(recipe, 'pixel')['limits']['maximum_command_bytes'], 6246)
        physical = adapter.fixed_plan(recipe, 'physical')
        self.assertEqual(physical['physical_catalog_path'], 'abi/engine/physical-input-catalog.json')
        self.assertEqual(physical['surface_capabilities'], '8225')
        self.assertEqual(physical['configuration']['document_profile'], contract.PROFILE_NAMES['physical'])
        adapter.reject_circular(physical)


if __name__ == '__main__':
    unittest.main()
