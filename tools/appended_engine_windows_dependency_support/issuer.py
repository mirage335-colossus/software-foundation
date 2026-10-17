"""Native Windows version collection and retained-original reconstruction.

Import is passive. Complete inventory provenance, independently parsed program
versions, fixed source/runtime subjects and actual closed owners precede every
production capability. Pure diagnostics cannot issue those capabilities.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import time
import types
import stat


HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parent.parent
A_SHA256 = '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0'
METHODS_SHA256 = '4b980a06167298130f7f8faaf2e2e3a88f25345a36b07de008db04b4c2ebb62d'
SELECTION_KIND = 'private-windows-tool-version-selection-v2'
DEFAULT_LIMITS = {'wall_milliseconds': 60000, 'maximum_processes': 4,
    'maximum_output_bytes': 4 * 1024**2, 'maximum_log_bytes': 65536, 'cleanup_seconds': 10}
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
INVENTORIES = ('llvm', 'msvc_stl', 'windows_sdk', 'host_generators')
PROGRAM_NAMES = {'compiler': 'clang-cl.exe', 'linker': 'lld-link.exe',
    'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
    'manifest_tool': 'llvm-mt.exe', 'cmake': 'cmake.exe', 'ninja': 'ninja.exe',
    'python': 'python.exe', 'perl': 'perl.exe', 'ruby': 'ruby.exe', 'gperf': 'gperf.exe',
    'nmake': 'nmake.exe', 'msbuild': 'MSBuild.exe'}
# The one maintained native-byte AST source used by native_inspection. The old
# ten-file whole-prototype import closure belongs to the historical V1 packet.
INSPECTOR_SOURCE_RELEASE = {
    'tools/appended_engine_windows_dependency_support/native_inspection_core.py': '75e816fdca8cc9ccf4d384d4e4f01e7be76f53879a6e5cfd7c6bdf9dc4e892f8',
    'tools/appended_engine_windows_dependency_proof.py': '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747'}

O_KIND = 'foundation-native-engine-windows-tool-version-observation-v2'
PARTIAL_KIND = 'foundation-native-engine-windows-tool-version-partial-batch-v2'
COMPLETE_KIND = 'foundation-native-engine-windows-tool-version-batch-v2'
_METHODS = None
_LIVE = set()
_CLOSED = {}
_ISSUED = {}
_FIXTURE_ISSUED = {}
_RETAINED = []
_DATA_MODULES = {}
_OBSERVED_ORIGINS = {}
_OBSERVED_ORIGINAL_REFS = {}
_PROGRAM_RUNTIME_CONTEXTS = {}
_PROGRAM_EVIDENCE = {}
_NMAKE_RUNTIME_FACTS = {}
_FRESH_OBSERVED = set()
_DATA_SOURCES = {'origin_loader': ('origin_loader.py', 4404, 'c8bd43b0dbf5ec9db9635fb4ef53e3412eb4ac69aca6483618013f8990a25d3a'), 'observation_runtime': ('observation_runtime.py', 6100, '061a0535dda535c31ecf340d645af773bdc52ccc9b8aa88fc9a190eddfc6e756'), 'runtime': ('runtime.py', 13990, '557801ca12c660cc81f78d79e77bfcfbfa41d84fae5284815636c8e45427c5ec'), 'observation_host': ('observation_tools.py', 9117, '1baaf6b7e9d4c5f88c1ae7dabe7adb1312789c7b49ebaaf508949fa6d9c1473c'), 'msbuild_method': ('host_methods.py', 4780, '017230b1026703e027d007f17a82ac00eb6df2729f0169f989343a224d092e3d'), 'inventory': ('inventory_contract.py', 10077, '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb'), 'native_inspection': ('native_inspection.py', 1914, '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6'), 'historical_publication': ('historical_publication.py', 13382, '966061803c511ffd6380621829e79f2108f89a6425530ef802f9112f8bec7cf1'), 'current_publication': ('current_publication.py', 13929, '1a4c46fb2fa5d7f82eec3d396c68ae2b20554e154c28584bcf273df1c377f522'), 'managed': ('managed_runtime.py', 64755, 'a4c7a366c927e655ccd4f331174c9310d1e0d0357a29bae0452a9e56a9ae99c2')}
_EXTRA_SOURCES = {'nmake_version.py': (22934, '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc'), 'nmake_version_emitter.py': (5294, '82ae5d7e673450505435af68bd1c1aa04718dac86fe454bde267b6547d35adb0')}
_RETAINED_SOURCE_RELEASE = ('retained_versions.py', 76586, 'a5afc146576f7ec3b36cbcbce53a1a4c8babae9bc6908fcc04d57984377e85da')
# Fixed maintained SOURCE policy; values never come from selected Q/O/H input.
_SOURCE_RELEASE = {'tests/diagnostics/windows_engine_publication.py': {'bytes': 10515,
                                                     'sha256': '2ad31fa883729c7b157f21744cfcc5272b0eaad5591bcc3fc568ff8321fe2f8e'},
 'tests/diagnostics/windows_engine_source_reader.py': {'bytes': 26675,
                                                       'sha256': 'ea0743e266178395b792ea58d996a42b8c063d06d1c729745ea83d5ea34400a6'},
 'tools/appended_engine_document_contract.py': {'bytes': 20492,
                                                'sha256': '2a1bb13756d605c0d2edbdcc62744110d68e88d4b2517753e0ef9a1c7a8c01fd'},
 'tools/appended_engine_editor_contract.py': {'bytes': 15584,
                                              'sha256': '198ca94d231f58fdd027cd8bd1142d6d3fcbdc1e1975d127930eb400e77238c3'},
 'tools/appended_engine_manifest.py': {'bytes': 21624,
                                       'sha256': '6807d4471349f0bb8972ea7dbc257c6b8c8b79530ee32f9dcbca84750680952a'},
 'tools/appended_engine_native_actions_contract.py': {'bytes': 16206,
                                                      'sha256': 'd2808ae5a424f98984478e1bf287ce628e13aa2a06dd9d73cf45660e6dc3a48e'},
 'tools/appended_engine_native_inputs.py': {'bytes': 236376,
                                            'sha256': '973fdddefa5a4cccc0190fdc4c4f6f1ba6afd693b17d70d928e428c4060eb706'},
 'tools/appended_engine_native_sdk.py': {'bytes': 67094,
                                         'sha256': 'ae915886d9a5a6cefe230c10445c977f9841ed98e1e5ff14cd9883a73688828a'},
 'tools/appended_engine_windows_contract.py': {'bytes': 18541,
                                               'sha256': 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8'},
 'tools/appended_engine_windows_dependency_proof.py': {'bytes': 35435,
                                                       'sha256': '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747'},
 'tools/appended_engine_windows_dependency_support/__init__.py': {'bytes': 0,
                                                                  'sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'},
 'tools/appended_engine_windows_dependency_support/admission.py': {'bytes': 8858,
                                                                   'sha256': 'b4ed8350ad0efb2cac897973a784f9a98b93b47e533ded96e2d80edb162c23e3'},
 'tools/appended_engine_windows_dependency_support/builtins/builtins_protocol.py': {'bytes': 5438,
                                                                                    'sha256': 'c334b013d3fcc024784182a461f3ee5837b006629da598788df4fe05fb251cc6'},
 'tools/appended_engine_windows_dependency_support/builtins/perl/emitter.pl': {'bytes': 806,
                                                                               'sha256': 'bd80d964e46d45891b644f9a1018f7bdc7569105021b186407aca093bfe4e137'},
 'tools/appended_engine_windows_dependency_support/builtins/perl/parser.py': {'bytes': 1892,
                                                                              'sha256': '05a3c978918b050b5695116675e9dd7d1dbf3748876892d14876aabd2f65ad75'},
 'tools/appended_engine_windows_dependency_support/builtins/protocol_contract.py': {'bytes': 1454,
                                                                                    'sha256': '478dfa28a66fd3023dbf24803e3b8ef48ec35c12baaf8f3f6947a1c2d0a49d31'},
 'tools/appended_engine_windows_dependency_support/builtins/python/emitter.py': {'bytes': 1799,
                                                                                 'sha256': '90067e97239cacb1c5cc0d45a53d00df4060207cfc6e17e2a626f95c530573ab'},
 'tools/appended_engine_windows_dependency_support/builtins/python/parser.py': {'bytes': 2400,
                                                                                'sha256': '014b378ed23c525dc42ac3719ef0e05db98ef22086b83f3bf375d7b0faaa8ba2'},
 'tools/appended_engine_windows_dependency_support/builtins/ruby/emitter.rb': {'bytes': 1285,
                                                                               'sha256': 'e8b4a1fea4b6de2fe2853d75706c1ff34aa3f0a384db4dff5e2c5230778c82ff'},
 'tools/appended_engine_windows_dependency_support/builtins/ruby/parser.py': {'bytes': 3014,
                                                                              'sha256': '45b43a5afcb97c177b0804c920f7c05fd5ade1447e3d75c799587af42d06ac1a'},
 'tools/appended_engine_windows_dependency_support/cmake_version.py': {'bytes': 11623,
                                                                       'sha256': '871c7fe6a8cda6d511aa52377ec024b7ccce5972a8fef3fe2247d9c672fd4d10'},
 'tools/appended_engine_windows_dependency_support/console_methods.py': {'bytes': 4997,
                                                                         'sha256': 'dbdfdc7eae58f761788a511e043a107a62f63254e35387148786e73080048c8a'},
 'tools/appended_engine_windows_dependency_support/current_publication.py': {'bytes': 13929,
                                                                             'sha256': '1a4c46fb2fa5d7f82eec3d396c68ae2b20554e154c28584bcf273df1c377f522'},
 'tools/appended_engine_windows_dependency_support/historical_publication.py': {'bytes': 13382,
                                                                                'sha256': '966061803c511ffd6380621829e79f2108f89a6425530ef802f9112f8bec7cf1'},
 'tools/appended_engine_windows_dependency_support/historical_sources.json': {'bytes': 4452,
                                                                              'sha256': 'e7f6622442457c07fb01beac06728250a1b18c6f1ca5dc127441db339fa3bd49'},
 'tools/appended_engine_windows_dependency_support/host_methods.py': {'bytes': 4780,
                                                                      'sha256': '017230b1026703e027d007f17a82ac00eb6df2729f0169f989343a224d092e3d'},
 'tools/appended_engine_windows_dependency_support/identity.py': {'bytes': 2989,
                                                                  'sha256': 'b2a66fe02ab1a2890fe53bfc82872421ed00ff53037389d7da9e0d26fb46f919'},
 'tools/appended_engine_windows_dependency_support/inventory.py': {'bytes': 1979,
                                                                   'sha256': 'b4480452a0a25821203f6ef9448eb9612d969bfd9d5540b92b26463e1a286d07'},
 'tools/appended_engine_windows_dependency_support/inventory_contract.py': {'bytes': 10077,
                                                                            'sha256': '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb'},
 'tools/appended_engine_windows_dependency_support/layout.py': {'bytes': 2063,
                                                                'sha256': '29856284e3a5359fc69a2605884fee51b755956b5b1a0814232b94dc89218c57'},
 'tools/appended_engine_windows_dependency_support/llvm_methods.py': {'bytes': 9764,
                                                                      'sha256': '62a0c91a43764dfd577f75ffccb75a56e0e181452a51ca37777e893736fca9a4'},
 'tools/appended_engine_windows_dependency_support/managed_runtime.py': {'bytes': 64755,
                                                                         'sha256': 'a4c7a366c927e655ccd4f331174c9310d1e0d0357a29bae0452a9e56a9ae99c2'},
 'tools/appended_engine_windows_dependency_support/methods.py': {'bytes': 9983,
                                                                 'sha256': 'ab6fad7a14c7d08e5980c8c4a61eda3a3e76a2e85d5ff7006a36fd296e54eefc'},
 'tools/appended_engine_windows_dependency_support/native_inspection.py': {'bytes': 1914,
                                                                           'sha256': '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6'},
 'tools/appended_engine_windows_dependency_support/native_inspection_core.py': {'bytes': 21266,
                                                                                'sha256': '75e816fdca8cc9ccf4d384d4e4f01e7be76f53879a6e5cfd7c6bdf9dc4e892f8'},
 'tools/appended_engine_windows_dependency_support/nmake_version.py': {'bytes': 22934,
                                                                       'sha256': '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc'},
 'tools/appended_engine_windows_dependency_support/nmake_version_emitter.py': {'bytes': 5294,
                                                                               'sha256': '82ae5d7e673450505435af68bd1c1aa04718dac86fe454bde267b6547d35adb0'},
 'tools/appended_engine_windows_dependency_support/observation_host.py': {'bytes': 10856,
                                                                          'sha256': '4609b6a50e0ecb73c17a8563f8b346a35a0c5ca32f471076bd7528c75558eaf0'},
 'tools/appended_engine_windows_dependency_support/observation_runtime.py': {'bytes': 6100,
                                                                             'sha256': '061a0535dda535c31ecf340d645af773bdc52ccc9b8aa88fc9a190eddfc6e756'},
 'tools/appended_engine_windows_dependency_support/observation_tools.py': {'bytes': 9117,
                                                                           'sha256': '1baaf6b7e9d4c5f88c1ae7dabe7adb1312789c7b49ebaaf508949fa6d9c1473c'},
 'tools/appended_engine_windows_dependency_support/observations.py': {'bytes': 10155,
                                                                      'sha256': '1015d81599bf7823ea5c9df7c5477b12fd325e4b878e5189975b90dca13881c8'},
 'tools/appended_engine_windows_dependency_support/origin.py': {'bytes': 53954,
                                                                'sha256': '79c64fa668fa75e14979b167027636c405d6564996fa6cc703e947dc15f0d65c'},
 'tools/appended_engine_windows_dependency_support/origin_loader.py': {'bytes': 4404,
                                                                       'sha256': 'c8bd43b0dbf5ec9db9635fb4ef53e3412eb4ac69aca6483618013f8990a25d3a'},
 'tools/appended_engine_windows_dependency_support/probe_core.py': {'bytes': 27776,
                                                                    'sha256': 'ba66eaa2d88912ab4ae5277cc56f0616384a9c38241f8c1ad374b38a40f0747f'},
 'tools/appended_engine_windows_dependency_support/probe_d3.py': {'bytes': 4213,
                                                                  'sha256': '647186156cfb0289da9e95fa13d9f99cc70264ac7a05e62410585b20c7246717'},
 'tools/appended_engine_windows_dependency_support/probe_w2.py': {'bytes': 12736,
                                                                  'sha256': 'e11c3734ea8ba7a1e9bc52fdf4c19822ecf06f2c46579d456b3ad568476d06b3'},
 'tools/appended_engine_windows_dependency_support/proof_d3.py': {'bytes': 9776,
                                                                  'sha256': 'a032b4f632e3770bd6b1daeef28a95759717483aabe8a549f27b8710ea21d55a'},
 'tools/appended_engine_windows_dependency_support/proof_h2.py': {'bytes': 19877,
                                                                  'sha256': 'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9'},
 'tools/appended_engine_windows_dependency_support/resource/llvm_version.py': {'bytes': 9374,
                                                                               'sha256': '3f9600b3309c6ec5848d2de6e97d79c0fea9b02c80e801ccf133d42fa7673d4f'},
 'tools/appended_engine_windows_dependency_support/resource/llvm_version_emitter.py': {'bytes': 6714,
                                                                                       'sha256': 'a2d069a2682090c2b44094530ca4e0f1563426711046f9298ddaa3a14e72c511'},
 'tools/appended_engine_windows_dependency_support/retained_versions.py': {'bytes': 76586,
                                                                           'sha256': 'a5afc146576f7ec3b36cbcbce53a1a4c8babae9bc6908fcc04d57984377e85da'},
 'tools/appended_engine_windows_dependency_support/runtime.py': {'bytes': 13990,
                                                                 'sha256': '557801ca12c660cc81f78d79e77bfcfbfa41d84fae5284815636c8e45427c5ec'},
 'tools/appended_engine_windows_dependency_support/runtime_base.py': {'bytes': 6249,
                                                                      'sha256': '911cd28fc1d23ae891b9730a4405c25cee661fca2fefd6d4d3db85f294b48194'},
 'tools/appended_engine_windows_dependency_support/supported_builtins.py': {'bytes': 4173,
                                                                            'sha256': '085b5cb185df615824b5596d56cb0ba1c99e7c17a3553642ec7666f395f6a04a'},
 'tools/appended_engine_windows_dependency_support/version_methods.py': {'bytes': 5431,
                                                                         'sha256': '4b980a06167298130f7f8faaf2e2e3a88f25345a36b07de008db04b4c2ebb62d'},
 'tools/appended_engine_windows_handoff.py': {'bytes': 41354,
                                              'sha256': '6bbf1209d1cb673b18f7f6ba5e6d8977d57df68c13287c1f592f0c4f64ac556b'},
 'tools/appended_engine_windows_prepare.py': {'bytes': 93525,
                                              'sha256': 'f602cc2ad4e61d55045352c42b04a9ac2633bd31eded575a9b3c19f1193bbe54'},
 'tools/appended_engine_windows_publication.py': {'bytes': 98362,
                                                  'sha256': '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0'},
 'tools/appended_engine_windows_source_replay.py': {'bytes': 127602,
                                                    'sha256': '2b0539c7769bb7fd906d9984faea536bccfbe51e85fc3dbc137f4a4c64c66788'},
 'tools/dependency_archive.py': {'bytes': 14550,
                                 'sha256': '28a2433591726aadcd35fc57e01d6e5c7307a2ed67b64846735b49f693b38d8a'},
 'tools/process_tree.py': {'bytes': 70487,
                           'sha256': '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'},
 'tools/sdk_environment.py': {'bytes': 951,
                              'sha256': 'f69fd947603ee6cb7ecd6633a9565aab8aa7336e3e96569ef219109763f26b9e'}}

CORE_MODULE_NAME = '_foundation_windows_h2_native_issuer_v1'


class IssuerError(ValueError):
    pass


class MissingInputs(IssuerError):
    def __init__(self, gaps):
        self.gaps = tuple(gaps)
        super().__init__('; '.join(self.gaps))


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise IssuerError('Exact closed ' + label + ' fields required')


def integer(value, label, low=1, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        raise IssuerError('Bounded exact integer required: ' + label)
    return value


def pin(value):
    if (type(value) is not str or len(value) != 64 or value == '0' * 64 or
            any(character not in '0123456789abcdef' for character in value)):
        raise IssuerError('Exact nonzero SHA256 required')
    return value


def path(value):
    if (type(value) is not str or not 3 <= len(value) <= 4096 or
            any(ord(c) < 32 or ord(c) > 126 for c in value) or '\\' in value or
            value[1:3] != ':/' or not 'A' <= value[0] <= 'Z' or
            any(part in ('', '.', '..') or part.endswith(('.', ' ')) or
                any(c in ':*?"<>|' for c in part) or '~' in part or
                part.split('.')[0].upper() in ('CON', 'PRN', 'AUX', 'NUL',
                    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9')
                for part in value[3:].split('/'))):
        raise IssuerError('Canonical explicit local Windows path required')
    return value


def ref(value, *, body=False):
    fields(value, ('path', 'sha256', 'bytes', 'mode') if body else ('path', 'sha256'), 'reference')
    path(value['path']); pin(value['sha256'])
    if body:
        integer(value['bytes'], 'input bytes', 0, 512 * 1024**2)
        if type(value['mode']) is not int or value['mode'] != 0o644:
            raise IssuerError('Input manifest logical mode0644 required')
    return copy.deepcopy(value)


def _methods():
    global _METHODS
    if _METHODS is None:
        source = HERE / 'version_methods.py'
        raw = source.read_bytes()
        if len(raw) != 5431 or sha(raw) != METHODS_SHA256:
            raise MissingInputs(['windows-tool-version-method-source-release'])
        spec = importlib.util.spec_from_file_location('_private_windows_version_methods', source)
        module = importlib.util.module_from_spec(spec)
        # Compile exactly the checked bytes, avoiding a second pathname read.
        exec(compile(raw, str(source), 'exec'), module.__dict__)
        _METHODS = module
    return _METHODS


def _data_module(name):
    """Fixed maintained source only; no caller module/path/loader is accepted."""
    if name == 'methods':
        return _methods()
    if name not in _DATA_MODULES:
        relative, size, expected = _DATA_SOURCES[name]
        source = HERE / relative
        before = source.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise MissingInputs(['SOURCE:windows-tool-version-' + name + '-source-release'])
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
                                row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if (identity(before) != identity(opened) or identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or len(raw) != size or sha(raw) != expected):
            raise MissingInputs(['SOURCE:windows-tool-version-' + name + '-source-release'])
        module = types.ModuleType('_foundation_h2_' + name)
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _DATA_MODULES[name] = module
    return _DATA_MODULES[name]


def originals_module():
    """The sole shared genuine Origin registry for all consumers of this issuer."""
    return _data_module('origin_loader').originals_module()


def _publication_checker(schema):
    if type(schema) is not int or schema not in (1, 2):
        raise IssuerError('Exact original collector source scope required')
    return _data_module('historical_publication' if schema == 1 else 'current_publication')


def _runtime_module():
    """The sole fixed source runtime reader, never a caller-selected adapter."""
    return _data_module('runtime')


def _retained_source_catalogue(schema):
    """Independent maintained catalogue, never expected pins copied from Q/O."""
    if type(schema) is not int or schema not in (1, 2):
        raise IssuerError('Exact original version-source catalogue schema required')
    if schema == 2:
        return _current_source_catalogue()
    source = HERE / 'historical_sources.json'
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != 4452:
        raise MissingInputs(['DATA:windows-tool-version-retained-v1-source-catalogue'])
    with source.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(4453)
        after = os.fstat(stream.fileno())
    identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
                            row.st_size, row.st_mtime_ns, row.st_ctime_ns)
    if (identity(before) != identity(opened) or identity(before) != identity(after) or
            identity(before) != identity(source.lstat()) or len(raw) != 4452 or
            sha(raw) != 'e7f6622442457c07fb01beac06728250a1b18c6f1ca5dc127441db339fa3bd49'):
        raise MissingInputs(['DATA:windows-tool-version-retained-v1-source-catalogue'])
    catalogue = json.loads(raw)
    fields(catalogue, ('issuer_relative', 'files'), 'known original source catalogue')
    helper = '53dd02b3789c6418e872b7aeaf7b0d58d47ef632ed4d9b87b3eb38049b7b9ce1'
    process = 'cb68d2449ce3c1aa18a24169466e6f5d425b710fac1c356d5e22deeac14b687d'
    # Maintained immutable A53 SOURCE-RELEASE.md, 6914B, SHA84ffe5c63afc6ff2...
    # These historical publication/input contracts disagree at one source path.
    # Callers must reject that closure conflict rather than drop either map.
    catalogue['publication_source_identity'] = {
        'tools/appended_engine_windows_publication.py': helper,
        'tests/diagnostics/windows_engine_publication.py': '2ad31fa883729c7b157f21744cfcc5272b0eaad5591bcc3fc568ff8321fe2f8e',
        'tools/process_tree.py': process,
        'tools/appended_engine_windows_contract.py': '726277627277fda79c2422e34760e3a088466d06f93de26057ab17e03817bbd7'}
    catalogue['input_source_identity'] = {
        'tools/appended_engine_windows_publication.py': helper,
        'tests/diagnostics/windows_engine_source_reader.py': 'be8c1fec3821635927c7039e93d18ea0fdf6b78de39d9d2783aef769b3a0b6a7',
        'tools/process_tree.py': process,
        'tools/appended_engine_windows_contract.py': 'ef87ff6618756ee1201729b32cd4438e73e349ae456f057c710d2d4643628d5a'}
    return copy.deepcopy(catalogue)


def _current_source_catalogue():
    """The actual maintained release closure, independent of selected originals.

    An external fixed-byte loader pins this issuer before execution. Its own
    body is read under stable physical identity here to close the acyclic source
    subject without embedding its digest into itself. All other values are
    literal maintained source policy, never copied from selected Q/O/H fields.
    """
    source = Path(__file__).resolve()
    before = source.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
            not 1 <= before.st_size <= 512 * 1024):
        raise IssuerError('Ordinary bounded maintained issuer source required')
    identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
                            row.st_size, row.st_mtime_ns, row.st_ctime_ns)
    with source.open('rb') as stream:
        opened = os.fstat(stream.fileno()); raw = stream.read(512 * 1024 + 1)
        after = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(before) != identity(after) or
            identity(before) != identity(source.lstat()) or len(raw) != before.st_size):
        raise IssuerError('Maintained issuer source changed while closing its subject')
    relative = 'tools/appended_engine_windows_dependency_support/issuer.py'
    if source != CHECKOUT / relative:
        raise IssuerError('Issuer must use its maintained logical filename')
    files = copy.deepcopy(_SOURCE_RELEASE)
    files[relative] = {'sha256': sha(raw), 'bytes': len(raw)}
    publication = {name: files[name]['sha256'] for name in (
        'tools/appended_engine_windows_publication.py',
        'tests/diagnostics/windows_engine_publication.py', 'tools/process_tree.py',
        'tools/appended_engine_windows_contract.py')}
    inputs = {name: files[name]['sha256'] for name in (
        'tools/appended_engine_windows_publication.py',
        'tests/diagnostics/windows_engine_source_reader.py', 'tools/process_tree.py',
        'tools/appended_engine_windows_contract.py')}
    return {'issuer_relative': relative, 'files': files,
        'publication_source_identity': publication, 'input_source_identity': inputs,
        'qualification_sources': {name: name for name in set(publication) | set(inputs)}}


def _admit_runtime_profiles(context):
    """Read through the factory's real owners and derive shared pure subjects.

    This function alone issues no capability. Both fresh/retained issuance also
    require their exact production context registry and original provenance checks.
    """
    if type(context) is _NativeContext:
        if context._state not in ('opening', 'open'):
            raise IssuerError('Live actual fresh runtime context required')
    else:
        _retained_module()._require_live_context(context)
    runtime = _data_module('runtime')
    host = context.selection['inventories']['host_generators']
    inventory_raw = context.read_input(host['reference'])
    inventory_value = json.loads(inventory_raw)
    provenance_ref = inventory_value['provenance']
    provenance_raw = context.read_input(provenance_ref)
    held_inventory = {'reference': {key: host['reference'][key] for key in ('path', 'sha256')},
        'raw': inventory_raw, 'provenance_reference': copy.deepcopy(provenance_ref),
        'provenance_raw': provenance_raw}
    result = {}
    context.runtime_profile_facts = {}
    for role in ('msbuild', 'nmake'):
        context.check_inputs()
        reference = context.selection['runtime_profiles'][role]
        raw = context.read_input(reference)
        selected = runtime.profile_references(role, reference, raw)
        system_refs = runtime.system_references(role, reference, raw)
        if not hasattr(context, '_system_runtime_refs'):
            context._system_runtime_refs = {}
        for item in system_refs:
            current_system = _current_system_identity(context)
            if (item['path'] != current_system['root'].rstrip('/') + '/System32/cmd.exe' or
                    not 1 <= item['bytes'] <= 64 * 1024**2):
                raise IssuerError('Only the current qualified native operating-system command processor is supported')
            context._system_runtime_refs[item['path']] = {**copy.deepcopy(item), 'mode': 0o644}
        system_names = {row['path'] for row in system_refs}
        held_bytes = {}
        for row in selected:
            body = {**row, 'mode': 0o644}
            held_bytes[row['path']] = (context.read_system_runtime_input(body) if row['path'] in system_names
                                      else context.read_runtime_input(body))
        facts = runtime.runtime_profile(role, reference, raw,
            held_inventory=held_inventory, held_bytes=held_bytes,
            system_identity=_current_system_identity(context),
            selected_program={key: context.selection['programs'][role][key]
                              for key in ('path', 'sha256', 'bytes')})
        context.runtime_profile_facts[role] = facts
        result[role] = facts['binding']
    context.check_inputs()
    _admit_program_runtime_facts(context, context.runtime_profile_facts)
    return _data_module('observation_runtime').runtime_bindings(result)


def require_runtime_profiles(value):
    facts = require_observed_versions(value)
    if 'runtime_profiles' not in facts:
        raise IssuerError('Original H1 versions have no H2 runtime-profile extension')
    return _data_module('observation_runtime').runtime_bindings(facts['runtime_profiles'])


def _current_system_identity(context):
    if type(context) is _NativeContext:
        runtime = context.runtime
    else:
        _retained_module()._require_live_context(context)
        runtime = context.actual_subject['runtime_identity']
    return {'root': path(runtime['system_root']),
            'windows_version': copy.deepcopy(runtime['windows_version'])}


def _admit_program_runtime_facts(context, profiles):
    """Derive fixed role runtime subjects inside an actual held-input context.

    The existing eleven roles use the complete owning inventory, an independently
    inspected exact same-directory native dependency closure and the qualified
    native OS-origin policy. Host generators have their explicit profile subjects.
    This function accepts no declared H version or caller runtime-subject hash.
    """
    if type(context) is _NativeContext:
        if context._state not in ('opening', 'open') or not context.readers:
            raise IssuerError('Actual live held native input context required')
    else:
        _retained_module()._require_live_context(context)
    inspector = _data_module('native_inspection')
    original_runtime = context.selection['publication']['runtime_identity']
    os_subject = {'policy': 'qualified-native-system-root-v1',
        'root': path(original_runtime['system_root']),
        'windows_version': copy.deepcopy(original_runtime['windows_version'])}
    subjects = {}
    for role, selected in context.selection['programs'].items():
        context.check_inputs()
        if role in ('nmake', 'msbuild'):
            subjects[role] = profiles[role]['binding']['subject_sha256']
            continue
        owner = 'llvm' if role in ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool') else 'host_generators'
        inventory = context.inventory_facts[owner]
        root = inventory['root'].rstrip('/')
        files, edges, pending, total = {}, {}, [selected['path']], 0
        while pending:
            name = pending.pop()
            if name in files:
                continue
            if len(files) >= 256 or not name.startswith(root + '/'):
                raise IssuerError('Finite original program native closure exceeded or escaped')
            relative = name[len(root) + 1:]
            declared = inventory['files'].get(relative)
            if declared is None or declared['bytes'] > 64 * 1024**2:
                raise IssuerError('Original program native runtime file is not in its complete held inventory')
            body = {'path': name, **declared, 'mode': 0o644}
            raw = context.read_runtime_input(body)
            total += len(raw)
            if total > 256 * 1024**2:
                raise IssuerError('Original program native runtime byte bound exceeded')
            inspected = inspector.inspect_tool_image(raw)
            if bool(inspected['dll']) != (name != selected['path']):
                raise IssuerError('Original program native runtime image role differs')
            files[name] = {key: body[key] for key in ('path', 'sha256', 'bytes')}
            reached = []
            directory = name.rsplit('/', 1)[0]
            for imported in inspected['needed']:
                if imported in inspector.SYSTEM_IMPORTS:
                    continue
                matches = [root + '/' + member for member in inventory['files']
                    if (root + '/' + member).rsplit('/', 1)[0] == directory and
                    member.rsplit('/', 1)[-1].casefold() == imported]
                if len(matches) != 1:
                    raise IssuerError('Original program runtime import lacks exact bundled same-directory resolution')
                reached.append(matches[0]); pending.append(matches[0])
            edges[name] = reached
        subject = {'schema_version': 1,
            'kind': 'foundation-windows-owned-program-runtime-subject-v1',
            'program': {key: selected[key] for key in ('path', 'sha256')},
            'inventory': {'role': owner, 'root': root, 'subject_sha256': inventory['subject_sha256']},
            'native_images': [files[name] for name in sorted(files)],
            'native_dependencies': edges, 'system': os_subject,
            'semantic_source': _DATA_SOURCES['native_inspection'][2]}
        subjects[role] = sha(encoded(subject))
    if set(subjects) != set(context.selection['programs']):
        raise IssuerError('Every original program runtime subject must be reconstructed')
    _PROGRAM_RUNTIME_CONTEXTS[context] = copy.deepcopy(subjects)
    return copy.deepcopy(subjects)


def _program_evidence_payload(context, result):
    subjects = _PROGRAM_RUNTIME_CONTEXTS.get(context)
    if type(subjects) is not dict or set(subjects) != set(result['programs']):
        raise IssuerError('Actual original runtime derivation is required before issuance')
    evidence = {}
    for role in result['programs']:
        owner = 'llvm' if role in ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool') else 'host_generators'
        evidence[role] = {'observation': copy.deepcopy(result['observations'][role]),
            'inventory_subject_sha256': result['inventory_subjects'][owner],
            'runtime_subject_sha256': subjects[role]}
    nmake = None
    profile_facts = (getattr(context, 'runtime_profile_facts', {}) if type(context) is _NativeContext
                     else _retained_module()._require_closed_runtime_facts(context))
    if 'nmake' in profile_facts:
        system = profile_facts['nmake']['consistency']['system']
        nmake = {
            'profile': copy.deepcopy(result['runtime_profiles']['nmake']['reference']),
            'subject_sha256': result['runtime_profiles']['nmake']['subject_sha256'],
            'system_root': system['root'], 'windows_version': copy.deepcopy(system['windows_version']),
            'command_processor': copy.deepcopy(system['command_processor'])}
    return copy.deepcopy(evidence), copy.deepcopy(nmake)


def require_original_program_evidence(token):
    """Return role-specific facts only for this actual issuer's complete token."""
    facts = require_observed_versions(token)
    evidence = _PROGRAM_EVIDENCE.get(token)
    if type(evidence) is not dict or set(evidence) != set(facts['programs']):
        raise IssuerError('Original per-program runtime evidence is not issued')
    return copy.deepcopy(evidence)


def require_nmake_runtime(token):
    facts = require_observed_versions(token)
    evidence = require_original_program_evidence(token)
    value = _NMAKE_RUNTIME_FACTS.get(token)
    if (type(value) is not dict or 'nmake' not in evidence or
            value['subject_sha256'] != evidence['nmake']['runtime_subject_sha256'] or
            value['profile'] != facts['runtime_profiles']['nmake']['reference']):
        raise IssuerError('Original supported NMake runtime is not issued')
    return copy.deepcopy(value)


def _retained_module():
    if _RETAINED_SOURCE_RELEASE is None:
        raise MissingInputs(['SOURCE:windows-tool-version-retained-reader-source-release'])
    _DATA_SOURCES['retained_versions'] = _RETAINED_SOURCE_RELEASE
    return _data_module('retained_versions')


def admit_retained_observed_versions(request_ref, *, deadline, limits):
    return _retained_module().admit_retained_observed_versions(
        request_ref, deadline=deadline, limits=limits)


def require_observed_origin(value, expected_request_ref):
    require_observed_versions(value)
    expected = ref(expected_request_ref)
    origin = _OBSERVED_ORIGINS.get(value)
    original = originals_module()
    if origin is None:
        raise IssuerError('These versions have no admitted retained original origin')
    summary = original.require_retained_originals(origin)
    if summary['request'] != expected:
        raise IssuerError('Observed-version origin request differs from the selected request')
    return origin


def require_observed_original_references(value):
    require_observed_versions(value)
    origin = _OBSERVED_ORIGINS.get(value)
    references = _OBSERVED_ORIGINAL_REFS.get(value)
    if references is None:
        raise IssuerError('Genuine retained versions and original-reference association required')
    if origin is None:
        if value not in _FRESH_OBSERVED:
            raise IssuerError('Genuine closed fresh or retained original association required')
    else:
        originals_module().require_original_membership(origin, references)
    return copy.deepcopy(references)


def _issue_retained_closed(context, facts, origin):
    """Only actual closed retained context + actual original authorities issue."""
    retained = _retained_module()
    facts = retained._require_closed_context(context, facts, origin)
    expected_roles = set(PROGRAM_NAMES)
    old_roles = expected_roles - {'nmake', 'msbuild'}
    if set(facts['programs']) not in (expected_roles, old_roles):
        raise IssuerError('Complete exact original role map required')
    names = ('batch', 'observations', 'programs', 'inventory_subjects', 'inventories',
             'inventory_release_evidence')
    if set(facts['programs']) == expected_roles:
        names += ('runtime_profiles',)
        _data_module('observation_runtime').runtime_bindings(facts['runtime_profiles'])
    fields(facts, names, 'complete retained original facts')
    provenance = _inventory_provenance(context)
    if any(provenance[name] != facts[name] for name in ('inventories', 'inventory_release_evidence')):
        raise IssuerError('Retained facts differ from held inventory/provenance declarations')
    originals_module().require_retained_originals(origin)
    original_refs = retained._require_closed_original_references(context, origin)
    originals_module().require_original_membership(origin, original_refs)
    payload = encoded(facts)
    saved_refs = copy.deepcopy(original_refs)
    evidence, nmake_runtime = _program_evidence_payload(context, facts)
    context.check_deadline()
    value = object.__new__(IssuedObservedVersions)
    _ISSUED[value] = payload
    _OBSERVED_ORIGINS[value] = origin
    _OBSERVED_ORIGINAL_REFS[value] = saved_refs
    _PROGRAM_EVIDENCE[value] = evidence
    if nmake_runtime is not None:
        _NMAKE_RUNTIME_FACTS[value] = nmake_runtime
    _PROGRAM_RUNTIME_CONTEXTS.pop(context, None)
    return value


def validate_limits(value):
    bounds = {'wall_milliseconds': 60000, 'maximum_processes': 64,
              'maximum_output_bytes': 16 * 1024**2, 'maximum_log_bytes': 65536,
              'cleanup_seconds': 60}
    fields(value, bounds, 'version collection limits')
    for name, maximum in bounds.items():
        integer(value[name], name, 1, maximum)
    return copy.deepcopy(value)


def missing_source():
    gaps = [gap for gap in _methods().final_method_gaps()
            if gap not in ('windows-tool-version-method:nmake', 'windows-tool-version-method:msbuild')]
    return gaps


class IssuedObservedVersions:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise IssuerError('Only the actual closed original collector may issue versions')

    def as_dict(self):
        return require_observed_versions(self)


class _FixtureResult:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise IssuerError('Private fixture result only')

    def as_dict(self):
        if type(self) is not _FixtureResult or self not in _FIXTURE_ISSUED:
            raise IssuerError('Unissued fixture result')
        return json.loads(_FIXTURE_ISSUED[self])


def require_observed_versions(value):
    if type(value) is not IssuedObservedVersions or value not in _ISSUED:
        raise IssuerError('Actual complete original observation authority required')
    return json.loads(_ISSUED[value])


def _inventory_provenance(context):
    """Derive descriptive inventory labels and existing original references.

    This pure join creates no capability. Production issuance separately requires
    its actual live/closed owner registry, complete current inventory trees and
    independently observed program versions. The legacy serialized evidence key
    names existing provenance originals; it is not a vendor-label authority.
    """
    fields(context.inventory_facts, INVENTORIES, 'four held inventory declarations')
    fields(context.inventory_subjects, INVENTORIES, 'four actual inventory subjects')
    result = {'inventories': {}, 'inventory_release_evidence': {}}
    for role in INVENTORIES:
        facts = context.inventory_facts[role]
        path(facts['root']); pin(facts['subject_sha256'])
        if facts['subject_sha256'] != context.inventory_subjects[role]:
            raise IssuerError('Inventory declaration differs from actual held subject')
        label = facts['version']
        if (type(label) is not str or not 1 <= len(label) <= 4096 or
                any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in label)):
            raise IssuerError('Bounded descriptive inventory label required')
        try:
            label.encode('utf-8')
        except UnicodeError as error:
            raise IssuerError('Inventory label must have valid UTF-8') from error
        references = facts['original_refs']
        if type(references) is not list or not 1 <= len(references) <= 769:
            raise IssuerError('Finite existing inventory provenance originals required')
        originals, seen = [], set()
        for item in references:
            item = ref(item)
            alias = item['path'].casefold()
            if alias in seen:
                raise IssuerError('Inventory provenance original references alias')
            seen.add(alias); originals.append(item)
        result['inventories'][role] = {key: facts[key]
            for key in ('root', 'version', 'subject_sha256')}
        result['inventory_release_evidence'][role] = originals
    return copy.deepcopy(result)


def _selection(value):
    fields(value, ('schema_version', 'kind', 'target', 'programs', 'inventories',
        'source_root', 'sources', 'publication', 'input', 'runtime_profiles'), 'native version selection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 2 or
            value['kind'] != SELECTION_KIND or value['target'] != TARGET):
        raise IssuerError('Unsupported native version selection')
    fields(value['programs'], _methods().ROLE_ORDER, 'thirteen no-version program selections')
    for role, record in value['programs'].items():
        ref(record, body=True)
        if record['path'].rsplit('/', 1)[-1] != PROGRAM_NAMES[role]:
            raise IssuerError('Selected program basename differs from exact role')
    fields(value['inventories'], INVENTORIES, 'four original inventories')
    for record in value['inventories'].values():
        fields(record, ('reference', 'root', 'subject_sha256'), 'inventory selection')
        ref(record['reference'], body=True); path(record['root']); pin(record['subject_sha256'])
    fields(value['runtime_profiles'], ('nmake', 'msbuild'), 'two original runtime profile selections')
    runtime_aliases = set()
    for record in value['runtime_profiles'].values():
        ref(record, body=True)
        integer(record['bytes'], 'original runtime profile bytes', 1, 2 * 1024**2)
        if record['path'].casefold() in runtime_aliases:
            raise IssuerError('Original runtime profile paths repeat or alias')
        runtime_aliases.add(record['path'].casefold())
    path(value['source_root'])
    if type(value['sources']) is not list or not 1 <= len(value['sources']) <= 128:
        raise IssuerError('Finite complete collector source closure required')
    seen = set()
    for record in value['sources']:
        ref(record, body=True)
        if record['path'].casefold() in seen:
            raise IssuerError('Collector source paths alias')
        seen.add(record['path'].casefold())
        if not record['path'].startswith(value['source_root'] + '/'):
            raise IssuerError('Collector source escapes its selected root')
    for name in ('publication', 'input'):
        subject = value[name]
        fields(subject, ('qualification', 'source_identity', 'runtime_identity'), name + ' source/runtime selection')
        ref(subject['qualification'])
        if type(subject['source_identity']) is not dict or not subject['source_identity']:
            raise IssuerError('Complete independently pinned A source identity required')
        for digest in subject['source_identity'].values(): pin(digest)
        if type(subject['runtime_identity']) is not dict:
            raise IssuerError('Typed actual A runtime identity required')
    return copy.deepcopy(value)


def _observe_tool_versions(selection, *, output, limits):
    """Complete production entrypoint. Missing source is checked before any native operation."""
    selection = _selection(selection); path(output); limits = validate_limits(limits)
    gaps = missing_source()
    if gaps:
        raise MissingInputs(gaps)
    context = _NativeContext.open(selection, output, limits)
    return _collect(context, _methods().ROLE_ORDER, complete=True)


class _NativeContext:
    """Factory-owned actual A objects, never accepted as a caller capability."""

    def __init__(self, *args, **kwargs):
        raise IssuerError('Use the fixed original collector factory')

    @classmethod
    def open(cls, selection, output, limits):
        if os.name != 'nt':
            raise MissingInputs(['windows-tool-version-native-windows-host'])
        # Source is fixed; a caller cannot select or inject a publication module.
        if INSPECTOR_SOURCE_RELEASE is None:
            raise MissingInputs(['windows-tool-version-generic-inspector-source-release'])
        publication, input_q, actual_subject = originals_module()._admit_input_subject(selection['input'])
        if not hasattr(publication.AnchoredInputs, 'capture_tree'):
            raise MissingInputs(['SOURCE:windows-tool-version-complete-tree-input-api-binding'])
        actual = actual_subject['runtime_identity']
        if actual != selection['publication']['runtime_identity'] or actual != selection['input']['runtime_identity']:
            raise IssuerError('Actual native collector runtime differs from original qualification subjects')
        output_q = publication.admit_qualification(selection['publication']['qualification'],
            source_identity=selection['publication']['source_identity'], runtime_identity=actual)
        self = object.__new__(cls)
        self.publication, self.runtime, self.selection = publication, actual, selection
        self.actual_subject = copy.deepcopy(actual_subject)
        self.limits, self.output, self.readers = limits, output, []
        self.workspace = None
        self._consumed_refs = {}
        self._state, self.captures = 'opening', []
        self._input_q, self._readers_by_root = input_q, {}
        self.clock, self.pause = time.monotonic, time.sleep
        self.deadline = self.clock() + limits['wall_milliseconds'] / 1000
        try:
            self._check_source_set()
            # Pure shared declarations/byte checks over real held captures.
            # No whole prototype import or engine R/S/B/handoff admission occurs.
            inventory_contract = _data_module('inventory')
            inspector = _data_module('native_inspection')
            self.inventory_facts = {}
            self.inventory_subjects = {}
            for role, record in selection['inventories'].items():
                if record['reference']['bytes'] > 4 * 1024**2:
                    raise IssuerError('Original inventory metadata exceeds finite document bound')
                raw = self.read_input(record['reference'])
                metadata = json.loads(raw)
                provenance = ref(metadata['provenance'])
                provenance_raw = self.read_input(provenance)
                facts = inventory_contract.inventory_declaration(raw, record['reference']['sha256'], role,
                    provenance_raw=provenance_raw, provenance_pin=provenance['sha256'])
                if facts['root'] != record['root'] or facts['subject_sha256'] != record['subject_sha256']:
                    raise IssuerError('Selected native inventory root differs')
                for original in facts['original_refs']:
                    self.read_input(original)
                facts['protected_paths'] = [record['reference']['path'], facts['root']]
                facts['protected_paths'] += [row['path'] for row in facts['original_refs']]
                self.inventory_facts[role] = facts
                self.inventory_subjects[role] = facts['subject_sha256']
            # Hold every selected tool/runtime inventory file against mutation
            # throughout original execution; pre/post scans alone cannot rule
            # out a transient runtime-file replacement. No tree is copied.
            for role in INVENTORIES:
                self._hold_runtime_inventory(self.inventory_facts[role])
            for role, record in selection['programs'].items():
                owner = 'llvm' if role in ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool') else 'host_generators'
                inventory = self.inventory_facts[owner]
                root = inventory['root'].rstrip('/')
                if not record['path'].startswith(root + '/'):
                    raise IssuerError('Selected program escapes its complete owning inventory')
                relative = record['path'][len(root) + 1:]
                expected = {key: record[key] for key in ('sha256', 'bytes')}
                if inventory['files'].get(relative) != expected:
                    raise IssuerError('Selected program does not join its complete owning inventory')
                program_raw = self.read_input(record)
                if role == 'msbuild':
                    _data_module('managed').inspect_managed_image(program_raw,
                        {key: record[key] for key in ('path', 'sha256', 'bytes')})
                elif inspector.inspect_tool_image(program_raw)['dll']:
                    raise IssuerError('Selected program image/role differs')
            python = selection['programs']['python']
            if actual['python_path'] != python['path'] or actual['python_sha256'] != python['sha256']:
                raise IssuerError('Actual collector Python image is not the selected admitted image')
            self.programs = {role: {key: row[key] for key in ('path', 'sha256')} for role, row in selection['programs'].items()}
            self.collector = {'program': self.programs['python'],
                'runtime_subject_sha256': self.inventory_subjects['host_generators'],
                'sources': [{key: row[key] for key in ('path', 'sha256')} for row in selection['sources']],
                'qualification': copy.deepcopy(selection['publication']['qualification'])}
            self.runtime_profiles = _admit_runtime_profiles(self)
            for capability in (output_q, input_q):
                for original in capability.as_dict()['originals'].values():
                    self.read_input(original)
            for name in ('publication', 'input'):
                self.read_input(selection[name]['qualification'])
            protected = [row['path'] for row in selection['sources']] + [row['root'] for row in selection['inventories'].values()]
            protected += [row['path'] for row in selection['runtime_profiles'].values()]
            protected += [item for facts in self.inventory_facts.values() for item in facts['protected_paths']]
            protected += [selection[name]['qualification']['path'] for name in ('publication', 'input')]
            self.workspace = publication.Workspace.create_new(output, protected_paths=protected,
                limits={'maximum_output_bytes': limits['maximum_output_bytes'],
                        'maximum_log_bytes': limits['maximum_log_bytes'], 'maximum_entries': 512,
                        'maximum_file_bytes': 16 * 1024**2, 'io_seconds': 60}, qualification=output_q)
            if type(self.workspace) is not publication.Workspace or self.workspace.diagnostic:
                raise IssuerError('Actual qualified production Workspace required')
            self._state = 'open'; _LIVE.add(self)
            self.check_inputs()
            return self
        except BaseException:
            self._abort_open()
            raise

    def _check_source_set(self):
        catalogue = _current_source_catalogue()
        if Path(self.selection['source_root']).resolve() != CHECKOUT:
            raise IssuerError('Fresh collector must use the actual maintained checkout')
        for name, subject in (('publication', 'publication_source_identity'),
                              ('input', 'input_source_identity')):
            if self.selection[name]['source_identity'] != catalogue[subject]:
                raise IssuerError('Selected A source identity differs from maintained source policy')
        required = {str(CHECKOUT / relative): row for relative, row in catalogue['files'].items()}
        declared = {str(Path(row['path'])): row for row in self.selection['sources']}
        if set(declared) != set(required):
            raise IssuerError('Exact issuer/method/A collector source closure differs')
        for name, expected in required.items():
            if any(declared[name][key] != value for key, value in expected.items()):
                raise IssuerError('Fixed source-owned collector byte pin or bound differs')
            self.read_input(declared[name])

    def _reader(self, root):
        if root not in self._readers_by_root:
            limits = {'seconds': 60, 'maximum_archive_bytes': 8 * 1024**3,
                'maximum_expanded_bytes': 32 * 1024**3, 'maximum_members': 65536,
                'maximum_member_bytes': 256 * 1024**2, 'maximum_patch_bytes': 32 * 1024**2}
            reader = self.publication.AnchoredInputs.open_existing(root,
                qualification=self._input_q, limits=limits, deadline=self.deadline)
            if type(reader) is not self.publication.AnchoredInputs:
                raise IssuerError('Actual qualified selected-file capture required')
            self.readers.append(reader); self._readers_by_root[root] = reader
        return self._readers_by_root[root]

    def _hold_runtime_inventory(self, inventory):
        reader = self._reader(inventory['root'])
        if len(inventory['files']) > 65536 or sum(row['bytes'] for row in inventory['files'].values()) > 32 * 1024**3:
            raise IssuerError('Complete tool/runtime capture exceeds conservative finite bounds')
        tree = reader.capture_tree('', files={name: {**row, 'mode': 0o644}
            for name, row in inventory['files'].items()}, directories=inventory['directories'])
        for name, row in inventory['files'].items():
            self.check_deadline()
            view = tree.open_file(name)
            digest, count = hashlib.sha256(), 0
            try:
                while True:
                    self.check_deadline()
                    raw = view.read(1024 * 1024)
                    if not raw: break
                    digest.update(raw); count += len(raw)
                if count != row['bytes'] or digest.hexdigest() != row['sha256']:
                    raise IssuerError('Held tool/runtime file differs from complete original inventory')
            finally:
                # Closing the borrowed view retains its owner's input handle.
                view.close()

    def read_input(self, record):
        selected = PureWindowsPath(record['path'])
        reader = self._reader(selected.parent.as_posix())
        if set(record) == {'path', 'sha256'}:
            ref(record)
            raw = reader.read(selected.name, expected={'sha256': record['sha256'], 'mode': 0o644},
                              maximum=64 * 1024**2)
        else:
            ref(record, body=True)
            raw = reader.read(selected.name, expected={key: record[key] for key in ('sha256', 'bytes', 'mode')},
                              maximum=max(1, record['bytes']))
        item = {key: record[key] for key in ('path', 'sha256')}
        previous = self._consumed_refs.get(record['path'].casefold())
        if previous is not None and previous != item:
            raise IssuerError('Consumed original input path spelling or byte pin changed')
        self._consumed_refs[record['path'].casefold()] = item
        if len(self._consumed_refs) > 16000:
            raise IssuerError('Consumed original input reference bound exceeded')
        return raw

    def read_runtime_input(self, record):
        ref(record, body=True)
        matches = []
        for inventory in self.inventory_facts.values():
            root = inventory['root'].rstrip('/') + '/'
            if record['path'].startswith(root):
                row = inventory['files'].get(record['path'][len(root):])
                if row == {key: record[key] for key in ('sha256', 'bytes')}:
                    matches.append(inventory)
        if len(matches) != 1:
            raise IssuerError('Runtime file must join exactly one complete held inventory')
        return self.read_input(record)

    def read_system_runtime_input(self, record):
        ref(record, body=True)
        expected = getattr(self, '_system_runtime_refs', {}).get(record['path'])
        if (expected != record or record['path'] !=
                self.runtime['system_root'].rstrip('/') + '/System32/cmd.exe'):
            raise IssuerError('Only the independently selected current native OS shell may bypass a bundle inventory')
        # This is current qualified native OS data. It is not represented as a
        # CI member or silently admitted as a generic bundled runtime file.
        return self.read_input(record)

    def emitter(self, role):
        rows = [row for row in _methods().source_refs(role) if row['path'].endswith(('emitter.py', 'emitter.pl', 'emitter.rb'))]
        if len(rows) != 1:
            raise IssuerError('One exact pinned emitter source required')
        selected = (HERE / rows[0]['path']).resolve()
        match = [row for row in self.selection['sources'] if Path(row['path']) == selected and row['sha256'] == rows[0]['sha256']]
        if len(match) != 1:
            raise IssuerError('Emitter source/byte pin differs from fixed method')
        self.read_input(match[0])
        return selected.as_posix()

    def check_inputs(self):
        if self._state not in ('opening', 'open', 'closing'):
            raise IssuerError('Original input context is not live')
        self.check_deadline()
        for reader in self.readers: reader.check()
        if self.publication._Native().runtime_identity() != self.runtime:
            raise IssuerError('Actual native collector runtime changed')

    def check_deadline(self):
        if self.clock() >= self.deadline:
            raise IssuerError('Absolute original-collection deadline expired')

    def environment(self):
        dirs = sorted({row['path'].rsplit('/', 1)[0] for row in self.programs.values()}, key=str.casefold)
        return {'SystemRoot': self.runtime['system_root'], 'PATH': ';'.join(dirs),
                'TEMP': self.output + '/temp', 'TMP': self.output + '/temp'}

    def read_log(self, log, row):
        reader = self._reader(self.output)
        raw = reader.read(log.path, expected={'sha256': row['sha256'], 'bytes': row['bytes'], 'mode': 0o644},
                          maximum=self.limits['maximum_log_bytes'])
        # The maintained current A source retains this exact physical identity
        # association between its actual OwnedLog and anchored input capture.
        held = reader._files[log.path]
        if held['identity'] != log.identity:
            raise IssuerError('Whole-log physical identity differs from the original OwnedLog')
        return raw

    def joined(self, log, joined):
        p = self.publication
        if (type(log) is not p.OwnedLog or log._workspace is not self.workspace or
                not any(log is item for item in self.workspace.logs) or
                type(joined) is not p.JoinedStage or not any(joined is item for item in self.workspace.joined)):
            raise IssuerError('Original log and actual JoinedStage association required')
        return joined.as_dict()

    def close(self):
        self._state = 'closing'
        self.check_inputs()
        first = None
        for reader in reversed(self.readers):
            try: reader.close()
            except BaseException as error: first = first or error
        if first is not None:
            self.retain(None, None, 'input close failed; original completion revoked')
            raise first
        self.workspace.close_joined()
        if not self.workspace.closed or any(not reader.closed for reader in self.readers):
            raise IssuerError('Original collector resources did not close')
        self._state = 'closed'; _LIVE.remove(self)
        _CLOSED[self] = tuple(self.captures)

    def _abort_open(self):
        _PROGRAM_RUNTIME_CONTEXTS.pop(self, None)
        if self.workspace is not None:
            self.retain(None, None, 'original native context opening failed after output creation')
            return
        first = None
        for reader in reversed(self.readers):
            try: reader.close()
            except BaseException as error: first = first or error
        if first is not None:
            _RETAINED.append(self)

    def retain(self, owner, log, reason):
        _PROGRAM_RUNTIME_CONTEXTS.pop(self, None)
        self._state = 'uncertain'; _LIVE.discard(self); _CLOSED.pop(self, None)
        self.workspace.retain_uncertain(owner, log, reason)
        _RETAINED.append(self)


def _absolute(context, row):
    return {'path': context.output + '/' + row['path'], 'sha256': row['sha256']}


def _held_emitter(context, role):
    if role == 'nmake':
        relative = 'nmake_version_emitter.py'
        size, digest = _EXTRA_SOURCES[relative]
    else:
        candidates = [row for row in _methods().source_refs(role)
                      if row['path'].endswith(('emitter.py', 'emitter.pl', 'emitter.rb'))]
        if len(candidates) != 1:
            raise IssuerError('One fixed original emitter source required')
        relative, digest = candidates[0]['path'], candidates[0]['sha256']
        size = None
    selected = ((HERE / relative).resolve().as_posix() if type(context) is _NativeContext
                else context.emitter(role))
    matches = [row for row in context.selection['sources']
               if row['path'] == selected and row['sha256'] == digest]
    if len(matches) != 1:
        raise IssuerError('Original emitter does not join the fixed independent source catalogue')
    record = matches[0]
    raw = context.read_input(record)
    if sha(raw) != digest or size is not None and len(raw) != size:
        raise IssuerError('Whole original emitter source bytes differ')
    return copy.deepcopy(record), raw


def _retained_method_plan(context, role):
    """One fixed literal plan from a genuine live capture/reconstruction owner.

    No O, log, runner, callback or expected version is accepted. The plan is an
    ordinary owned declaration; only actual owner closure and this issuer's
    production registries may later issue observed-version facts.
    """
    if type(context) is _NativeContext:
        if context._state not in ('opening', 'open') or not context.readers:
            raise IssuerError('Actual live native version context required')
    else:
        _retained_module()._require_live_context(context)
    selected = context.selection['programs'][role]
    subject = {key: selected[key] for key in ('path', 'sha256')}
    if role in ('archiver', 'resource_compiler', 'manifest_tool'):
        emitter, raw = _held_emitter(context, role)
        runner = {key: context.selection['programs']['python'][key] for key in ('path', 'sha256')}
        program = {key: selected[key] for key in ('path', 'sha256', 'bytes')}
        return {'runner': runner,
                'argv': _methods().resource_argv(role, runner['path'], emitter['path'], program),
                'method_inputs': {'program': program, 'runner': runner,
                    'emitter': emitter, 'emitter_raw': raw}}
    if role == 'msbuild':
        facts = context.runtime_profile_facts['msbuild']
        inputs = copy.deepcopy(facts['method_inputs'])
        actual = context.read_runtime_input(inputs['project'])
        _data_module('msbuild_method').verify_project(actual)
        if actual != inputs['project_raw']:
            raise IssuerError('Held MSBuild project changed before launch')
        return {'runner': subject,
                'argv': _data_module('msbuild_method').msbuild_argv(subject['path'], inputs['project']['path']),
                'method_inputs': inputs}
    if role == 'nmake':
        emitter, raw = _held_emitter(context, role)
        runner = {key: context.selection['programs']['python'][key] for key in ('path', 'sha256')}
        program = {key: selected[key] for key in ('path', 'sha256', 'bytes')}
        body = context.read_runtime_input({**program, 'mode': 0o644})
        if len(body) != program['bytes'] or sha(body) != program['sha256']:
            raise IssuerError('Original NMake subject changed before collection')
        inputs = {'runtime_profile': copy.deepcopy(context.runtime_profiles['nmake']),
            'program': program, 'runner': runner, 'emitter': emitter, 'emitter_raw': raw}
        return {'runner': runner,
            'argv': [runner['path'], '-I', '-S', emitter['path'], '--program',
                     subject['path'], '--sha256', subject['sha256'], '--bytes', str(program['bytes'])],
            'method_inputs': inputs}
    emitter = None if role == 'cmake' else _held_emitter(context, role)[0]['path']
    return {'runner': subject, 'argv': _methods().argv(role, subject['path'], emitter),
            'method_inputs': None}


def _capture_one(context, role):
    methods = _methods()
    method = (_data_module('msbuild_method').METHOD if role == 'msbuild' else
              'nmake-pe-version-resource-v1' if role == 'nmake' else methods.method_for(role))
    plan = _retained_method_plan(context, role)
    subject = copy.deepcopy(context.programs[role])
    command = {'program': copy.deepcopy(plan['runner']), 'argv': plan['argv'],
        'cwd': context.output, 'environment': context.environment()}
    workspace, limits = context.workspace, context.limits
    context.check_inputs(); workspace.check_anchors()
    log = workspace.open_log_new('logs/' + role + '.log')
    workspace.mark_running(log)
    owner = joined = None
    join_started = seal_started = sealed = False
    peak_processes, peak_bytes = 1, 0
    started = context.clock()

    def sample():
        nonlocal peak_processes, peak_bytes
        context.check_deadline()
        usage = workspace.usage(log=log)
        peak_bytes = max(peak_bytes, integer(usage['bytes'], 'observed output bytes', 0, 2**63 - 1))
        if peak_bytes > limits['maximum_output_bytes'] or usage['log_bytes'] > limits['maximum_log_bytes']:
            raise IssuerError('Original version output/log limit exceeded')
        if owner is not None:
            count = integer(owner.job.active(), 'sampled active Job processes', 0, 65536)
            peak_processes = max(peak_processes, count)
            if count > limits['maximum_processes']:
                raise IssuerError('Original version sampled-process threshold exceeded')

    try:
        sample()
        owner = workspace.launch(log, command['argv'], command['cwd'], env=command['environment'],
            maximum_active_processes=limits['maximum_processes'])
        if owner.job is None:
            raise IssuerError('Actual Windows Job owner required')
        while owner.poll() is None:
            sample(); context.pause(0.05)
        sample()  # Mandatory even when the first poll observes immediate exit.
        join_started = True
        joined = workspace.mark_joined(log, {'phase': 'probe', 'role': role,
            'method': method, 'argv': command['argv'], 'cwd': command['cwd'],
            'launch_intent_sha256': sha(encoded(command))})
        fact = context.joined(log, joined)
        seal_started = True; row = workspace.seal_log(log); sealed = True
        if (fact.get('returncode') != 0 or fact.get('process_tree_closed') is not True or
                fact.get('closure') != 'actual-bound-job-finish-and-close'):
            raise IssuerError('Original version command did not close successfully')
        if getattr(log, '_state', None) != 'sealed':
            raise IssuerError('Original OwnedLog is not sealed')
        inventory = workspace.inspect_outputs()
        peak_bytes = max(peak_bytes, integer(inventory['bytes'], 'final output bytes', 0, 2**63 - 1))
        if peak_bytes > limits['maximum_output_bytes']:
            raise IssuerError('Original final output exceeds limit')
        raw = context.read_log(log, row)
        if type(raw) is not bytes or len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise IssuerError('Complete original log readback differs')
        context.check_inputs(); context.check_deadline()
        elapsed = int((context.clock() - started) * 1000)
        if elapsed >= limits['wall_milliseconds']:
            raise IssuerError('Original version wall observation reached deadline')
        observation = {'schema_version': 2, 'kind': O_KIND, 'target': TARGET,
            'role': role, 'method': method, 'program': subject,
            'inventory_subject_sha256': context.inventory_subjects['llvm' if role in
                ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool') else 'host_generators'],
            'collector': copy.deepcopy(context.collector), 'command': command,
            'runtime_profiles': copy.deepcopy(context.runtime_profiles),
            'log': {**_absolute(context, row), 'bytes': row['bytes'], 'mode': 0o644},
            'job': {'owner': 'windows-job-v1', 'launch_intent_sha256': sha(encoded(command)),
                'image': command['program'], 'launch_suspended': True, 'assigned_before_resume': True,
                'breakaway_allowed': False, 'kill_on_close': True, 'exit_code': fact['returncode'],
                'elapsed_milliseconds': elapsed, 'wall_limit_milliseconds': limits['wall_milliseconds'],
                # Monitoring thresholds only until the separate pre-resume cap is released.
                'process_count': peak_processes, 'process_limit': limits['maximum_processes'],
                'peak_output_bytes': peak_bytes, 'output_limit_bytes': limits['maximum_output_bytes'],
                'active_processes_at_join': 0, 'streams_closed': True,
                'join_completed': True, 'owner_closed': True},
            'output_subject_sha256': sha(encoded(inventory))}
        observation_raw = encoded(observation)
        checked = _data_module('observation_host').observation(observation_raw, sha(observation_raw),
            role=role, program=subject,
            inventory_subject_sha256=observation['inventory_subject_sha256'],
            collector=context.collector, command=command, log_raw=raw,
            log_reference=observation['log'], runtime_profiles=context.runtime_profiles,
            method_inputs=plan['method_inputs'])
        version = checked['version']
        reference = _absolute(context, workspace.publish_bytes_new('observations/' + role + '.json', observation_raw))
        context.captures.append({'role': role, 'method': method, 'version': version,
                                 'reference': reference, 'log_reference': copy.deepcopy(observation['log']),
                                 'log': log, 'joined': joined})
        return reference
    except BaseException as error:
        if (join_started and joined is None) or (seal_started and not sealed):
            context.retain(owner, log, str(error)); raise
        try:
            if joined is None and owner is not None:
                owner.terminate(timeout=limits['cleanup_seconds'])
                join_started = True
                joined = workspace.mark_joined(log, {'phase': 'probe', 'role': role, 'method': method,
                    'argv': command['argv'], 'cwd': command['cwd']})
            if joined is not None:
                workspace.mark_failed_joined(joined, str(error))
                if not sealed:
                    seal_started = True; workspace.seal_log(log)
            else:
                context.retain(owner, log, 'launch outcome lacks its returned actual owner')
        except BaseException as cleanup:
            context.retain(owner, log, str(error) + '; cleanup: ' + str(cleanup))
        raise


def _collect(context, roles, *, complete):
    """Private flow shared with inert fixtures; this function alone mints nothing."""
    try:
        return _collect_impl(context, roles, complete=complete)
    except BaseException as error:
        _CLOSED.pop(context, None)
        _PROGRAM_RUNTIME_CONTEXTS.pop(context, None)
        workspace = context.workspace
        if getattr(context, '_state', None) not in ('closed', 'uncertain'):
            if not workspace.uncertain and all(log._state == 'sealed' for log in workspace.logs):
                try:
                    context.close()
                    _CLOSED.pop(context, None)
                except BaseException as cleanup:
                    context.retain(None, None, str(error) + '; final cleanup: ' + str(cleanup))
            else:
                context.retain(None, None, str(error))
        raise


def _collect_impl(context, roles, *, complete):
    roles = tuple(roles)
    if not roles or len(set(roles)) != len(roles) or any(role not in _methods().ROLE_ORDER for role in roles):
        raise IssuerError('Finite unique selected roles required')
    workspace = context.workspace
    for name in ('logs', 'observations', 'temp'): workspace.mkdir_new(name)
    references = {role: _capture_one(context, role) for role in roles}
    context.check_inputs()
    batch = {'schema_version': 2, 'kind': COMPLETE_KIND if complete else PARTIAL_KIND,
        'target': TARGET, 'collector': copy.deepcopy(context.collector),
        'inventory_subjects': copy.deepcopy(context.inventory_subjects),
        'runtime_profiles': copy.deepcopy(context.runtime_profiles),
        'observations': references}
    if complete:
        released = _require_complete(context, references)
        batch.update(released)
    batch_ref = _absolute(context, workspace.publish_bytes_new('observation-batch.json', encoded(batch)))
    context.check_inputs(); workspace.inspect_outputs()
    context.close()  # Includes a final live-input postflight and real A close.
    result = {'batch': batch_ref, 'observations': references,
        'programs': {row['role']: {**context.programs[row['role']], 'version': row['version']} for row in context.captures},
        'runtime_profiles': copy.deepcopy(context.runtime_profiles),
        'inventory_subjects': copy.deepcopy(context.inventory_subjects)}
    if complete:
        result.update(released)
        return _issue_closed(context, result)
    _PROGRAM_RUNTIME_CONTEXTS.pop(context, None)
    _CLOSED.pop(context, None)
    return result


def _require_complete(context, references):
    if type(context) is not _NativeContext or context not in _LIVE:
        raise IssuerError('Actual native original collector context required')
    if set(references) != set(_methods().ROLE_ORDER):
        raise IssuerError('All thirteen final original role observations required')
    provenance = _inventory_provenance(context)
    for evidence in provenance['inventory_release_evidence'].values():
        if any(item['path'].casefold() == context.output.casefold() or
               item['path'].casefold().startswith(context.output.casefold() + '/') for item in evidence):
            raise IssuerError('Existing inventory provenance cannot refer to later collector outputs')
    return provenance


def _issue_closed(context, result):
    if type(context) is not _NativeContext or context not in _CLOSED or context._state != 'closed':
        raise IssuerError('Actual collector and all resource owners must close before issuance')
    if set(result['programs']) != set(_methods().ROLE_ORDER):
        raise IssuerError('Partial versions cannot issue H facts')
    if _data_module('observation_runtime').runtime_bindings(result['runtime_profiles']) != context.runtime_profiles:
        raise IssuerError('Runtime profile facts differ from actual held original derivation')
    # Reconstruct the same descriptive declarations from the held originals;
    # inventory labels do not replace any independently captured role version.
    provenance = _inventory_provenance(context)
    if any(provenance[name] != result[name]
           for name in ('inventories', 'inventory_release_evidence')):
        raise IssuerError('Complete facts differ from held inventory/provenance declarations')
    captured = _CLOSED[context]
    if (len(captured) != len(_methods().ROLE_ORDER) or
            {row['role'] for row in captured} != set(_methods().ROLE_ORDER) or
            any(row['log']._state != 'sealed' or
                not any(row['joined'] is item for item in context.workspace.joined) or
                not any(row['log'] is item for item in context.workspace.logs)
                for row in captured)):
        raise IssuerError('Complete actual original role captures required at issuance')
    actual_observations = {row['role']: row['reference'] for row in captured}
    actual_programs = {row['role']: {**context.programs[row['role']], 'version': row['version']}
                       for row in captured}
    if (encoded(result['observations']) != encoded(actual_observations) or
            encoded(result['programs']) != encoded(actual_programs)):
        raise IssuerError('Issued versions must equal actual closed original role captures')
    value = object.__new__(IssuedObservedVersions)
    payload = encoded(result)
    evidence, nmake_runtime = _program_evidence_payload(context, result)
    originals = copy.deepcopy(context._consumed_refs)
    for reference in (result['batch'], *result['observations'].values()):
        item = {key: reference[key] for key in ('path', 'sha256')}
        previous = originals.get(item['path'].casefold())
        if previous is not None and previous != item:
            raise IssuerError('Original closed output path aliases an input')
        originals[item['path'].casefold()] = item
    for row in context.captures:
        # The exact original log ref was verified by the shared O checker before
        # publication. Retain that source-owned row, not arbitrary Workspace data.
        item = copy.deepcopy(row['log_reference'])
        originals[item['path'].casefold()] = {key: item[key] for key in ('path', 'sha256')}
    original_refs = [originals[key] for key in sorted(originals)]
    context.check_deadline()
    _ISSUED[value] = payload
    _PROGRAM_EVIDENCE[value] = evidence
    _OBSERVED_ORIGINAL_REFS[value] = original_refs
    _FRESH_OBSERVED.add(value)
    if nmake_runtime is not None:
        _NMAKE_RUNTIME_FACTS[value] = nmake_runtime
    _PROGRAM_RUNTIME_CONTEXTS.pop(context, None)
    del _CLOSED[context]
    return value


def _fixture_result(result):
    """A distinct diagnostic registry; production require() always rejects it."""
    value = object.__new__(_FixtureResult)
    _FIXTURE_ISSUED[value] = encoded(result)
    return value


def _admit_retained_original(*args, **kwargs):
    return admit_retained_observed_versions(*args, **kwargs)


def _admit_retained_observed_versions(request_ref, *, deadline, limits):
    return admit_retained_observed_versions(request_ref, deadline=deadline, limits=limits)
