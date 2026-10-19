"""Source/data fixtures only: no SDK, native program, archive or engine executes."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_contract as contract


def reference(path):
    return {'path': path, 'sha256': hashlib.sha256(path.encode()).hexdigest()}


def inputs(woff2='OFF'):
    prefix = 'C:/retained/native-dependencies'
    targets = contract.LIBRARIES | (frozenset(('WOFF2::dec', 'WOFF2::common'))
                                    if woff2 == 'ON' else frozenset())
    return {'schema_version': 1, 'kind': 'foundation-native-engine-windows-inputs',
        'target': 'windows-x86_64', 'build_type': 'Release', 'crt': 'static-mt',
        'cpu_baseline': 'x86_64-sse2', 'os_floor_declaration': 'windows-10-1809-unqualified',
        'engine_cxx_standard': 23, 'dependency_prefix': prefix,
        'toolchain': {'compiler': reference('C:/retained/llvm/bin/clang-cl.exe'),
            'linker': reference('C:/retained/llvm/bin/lld-link.exe'),
            'builtins': reference('C:/retained/llvm/lib/clang_rt.builtins-x86_64.lib'),
            'compiler_version': '19.1.7',
            'msvc_stl': {'root': 'C:/retained/msvc',
                         'inventory': reference('C:/records/msvc-stl.json')},
            'windows_sdk': {'root': 'C:/retained/windows-sdk',
                            'inventory': reference('C:/records/windows-sdk.json')}},
        'dependency_inventory': reference('C:/records/native-dependencies.json'),
        'woff2': woff2,
        'libraries': {target: {**reference(prefix + '/lib/' + target.replace('::', '_') + '.lib'),
            'includes': [prefix + '/include'], 'definitions': ['STATIC_BUILD=1'],
            'links': ['WebP::sharpyuv'] if target == 'WebP::libwebp' else ['ws2_32']}
            for target in sorted(targets)}}


class WindowsContractTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / contract.PROFILE_PATH).read_text())
        self.value = inputs()

    def reject(self, value=None, pattern=None):
        with self.assertRaisesRegex(ValueError, pattern or '.'):
            contract.validate_inputs(self.value if value is None else value)

    def test_checked_profile_names_exact_shared_source_and_no_execution(self):
        checked = contract.validate_profile(self.profile)
        for role, reference_value in contract.catalogue_for_profile(checked).items():
            self.assertEqual(checked[role], reference_value)
            self.assertEqual(hashlib.sha256((ROOT / reference_value['path']).read_bytes()).hexdigest(),
                             reference_value['sha256'])
        for name in contract.FALSE_FACTS:
            self.assertIs(checked[name], False)

    def test_showpicker_profile_has_separate_catalogue_and_rejects_old_kind(self):
        historical = copy.deepcopy(self.profile)
        historical.update(kind=contract.NATIVE_SHOWPICKER_PROFILE_KIND,
                          **contract.NATIVE_SHOWPICKER_CATALOGUE)
        checked = contract.validate_profile(historical)
        catalogue = contract.NATIVE_SHOWPICKER_CATALOGUE
        self.assertEqual(checked['kind'], contract.NATIVE_SHOWPICKER_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked), catalogue)
        self.assertEqual(contract.catalogue_for_map_digest(checked['source_map']['sha256']), catalogue)
        self.assertEqual(contract.catalogue_for_reference(catalogue), catalogue)
        self.assertEqual(contract.catalogue_for_recipe_inputs({'map': checked['source_map']}), catalogue)
        for field in ('kind', 'source_map', 'build'):
            changed = copy.deepcopy(checked)
            if field == 'kind': changed[field] = contract.NATIVE_CONTROL_INCLUDES_PROFILE_KIND
            elif field == 'source_map': changed[field] = contract.NATIVE_CONTROL_KEYPRESS_CATALOGUE[field]
            else: changed[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                contract.validate_profile(changed)

    def test_native_select_events_profile_has_separate_exact_catalogue(self):
        historical = copy.deepcopy(self.profile)
        historical.update(kind=contract.NATIVE_SELECT_EVENTS_PROFILE_KIND, **contract.NATIVE_SELECT_EVENTS_CATALOGUE)
        checked = contract.validate_profile(historical)
        catalogue = contract.NATIVE_SELECT_EVENTS_CATALOGUE
        self.assertEqual(checked['kind'], contract.NATIVE_SELECT_EVENTS_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked), catalogue)
        self.assertEqual(contract.catalogue_for_map_digest(checked['source_map']['sha256']), catalogue)
        self.assertEqual(contract.catalogue_for_reference(catalogue), catalogue)
        self.assertEqual(contract.catalogue_for_recipe_inputs({'map': checked['source_map']}), catalogue)
        for mutation in ('old-kind', 'old-map', 'runtime-claim'):
            value = copy.deepcopy(checked)
            if mutation == 'old-kind': value['kind'] = contract.NATIVE_SHOWPICKER_PROFILE_KIND
            elif mutation == 'old-map': value['source_map'] = contract.NATIVE_SHOWPICKER_CATALOGUE['source_map']
            else: value['production_eligible'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate_profile(value)

    def test_input_method_profile_has_its_own_exact_catalogue(self):
        historical = copy.deepcopy(self.profile)
        historical.update(kind=contract.NATIVE_INPUT_METHOD_PROFILE_KIND, **contract.NATIVE_INPUT_METHOD_CATALOGUE)
        checked = contract.validate_profile(historical)
        catalogue = contract.NATIVE_INPUT_METHOD_CATALOGUE
        self.assertEqual(checked['kind'], contract.NATIVE_INPUT_METHOD_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked), catalogue)
        self.assertEqual(contract.catalogue_for_map_digest(checked['source_map']['sha256']), catalogue)
        self.assertEqual(contract.catalogue_for_reference(catalogue), catalogue)
        self.assertEqual(contract.catalogue_for_recipe_inputs({'map': checked['source_map']}), catalogue)
        for mutation in ('old-kind', 'old-map', 'old-provenance', 'runtime-claim'):
            changed = copy.deepcopy(checked)
            if mutation == 'old-kind': changed['kind'] = contract.NATIVE_SELECT_EVENTS_PROFILE_KIND
            elif mutation == 'old-map': changed['source_map'] = contract.NATIVE_SELECT_EVENTS_CATALOGUE['source_map']
            elif mutation == 'old-provenance': changed['provenance'] = contract.NATIVE_SELECT_EVENTS_CATALOGUE['provenance']
            else: changed['production_eligible'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate_profile(changed)

    def test_form_preflight_profile_has_distinct_exact_catalogue(self):
        checked = contract.validate_profile(self.profile)
        catalogue = contract.NATIVE_FORM_PREFLIGHT_CATALOGUE
        self.assertEqual(checked['kind'], contract.NATIVE_FORM_PREFLIGHT_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked), catalogue)
        self.assertEqual(contract.catalogue_for_map_digest(checked['source_map']['sha256']), catalogue)
        self.assertEqual(contract.catalogue_for_reference(catalogue), catalogue)
        self.assertEqual(contract.catalogue_for_recipe_inputs({'map': checked['source_map']}), catalogue)
        for mutation in ('kind', 'source_map', 'provenance', 'production_eligible'):
            changed = copy.deepcopy(checked)
            if mutation == 'kind': changed[mutation] = contract.NATIVE_INPUT_METHOD_PROFILE_KIND
            elif mutation == 'production_eligible': changed[mutation] = True
            else: changed[mutation] = contract.NATIVE_INPUT_METHOD_CATALOGUE[mutation]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate_profile(changed)

    def test_historical_control_includes_profile_keeps_its_own_catalogue(self):
        historical = copy.deepcopy(self.profile)
        historical.update(kind=contract.NATIVE_CONTROL_INCLUDES_PROFILE_KIND,
                          **contract.NATIVE_CONTROL_INCLUDES_CATALOGUE)
        checked = contract.validate_profile(historical)
        self.assertEqual(checked['kind'], contract.NATIVE_CONTROL_INCLUDES_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked), contract.NATIVE_CONTROL_INCLUDES_CATALOGUE)

    def test_native_control_keypress_profile_uses_distinct_exact_catalogue(self):
        historical = copy.deepcopy(self.profile)
        historical.update(kind=contract.NATIVE_CONTROL_KEYPRESS_PROFILE_KIND, **contract.NATIVE_CONTROL_KEYPRESS_CATALOGUE)
        checked = contract.validate_profile(historical)
        catalogue = contract.NATIVE_CONTROL_KEYPRESS_CATALOGUE
        self.assertEqual(checked['kind'], contract.NATIVE_CONTROL_KEYPRESS_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked), catalogue)
        self.assertEqual(contract.catalogue_for_map_digest(checked['source_map']['sha256']), catalogue)
        self.assertEqual(contract.catalogue_for_reference(catalogue), catalogue)
        self.assertEqual(contract.catalogue_for_recipe_inputs({'map': checked['source_map']}), catalogue)
        for mutation in ('old-kind', 'old-map', 'runtime-claim'):
            value = copy.deepcopy(checked)
            if mutation == 'old-kind': value['kind'] = contract.NATIVE_POPUP_PROFILE_KIND
            elif mutation == 'old-map': value['source_map'] = contract.NATIVE_POPUP_CATALOGUE['source_map']
            else: value['build'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate_profile(value)

    def test_native_popup_profile_uses_distinct_exact_catalogue(self):
        historical=copy.deepcopy(self.profile)
        historical.update(kind=contract.NATIVE_POPUP_PROFILE_KIND, **contract.NATIVE_POPUP_CATALOGUE)
        checked=contract.validate_profile(historical)
        self.assertEqual(checked['kind'],contract.NATIVE_POPUP_PROFILE_KIND)
        self.assertEqual(contract.catalogue_for_profile(checked),contract.NATIVE_POPUP_CATALOGUE)
        self.assertEqual(contract.catalogue_for_map_digest(checked['source_map']['sha256']),contract.NATIVE_POPUP_CATALOGUE)
        self.assertEqual(contract.catalogue_for_reference(contract.NATIVE_POPUP_CATALOGUE),contract.NATIVE_POPUP_CATALOGUE)
        for mutation in ('old-kind','old-map','runtime-claim'):
            value=copy.deepcopy(checked)
            if mutation=='old-kind':value['kind']=contract.COMPOSITION_PROFILE_KIND
            elif mutation=='old-map':value['source_map']=contract.COMPOSITION_CATALOGUE['source_map']
            else:value['build']=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):contract.validate_profile(value)

    def test_composition_profile_is_separate_from_exact_legacy_catalogue(self):
        legacy = copy.deepcopy(self.profile)
        legacy.update(kind='foundation-native-engine-windows-producer-profile-v1', source_files=157, **contract.CATALOGUE)
        self.assertEqual(contract.validate_profile(legacy), legacy)
        successor = copy.deepcopy(legacy)
        successor.update(kind=contract.COMPOSITION_PROFILE_KIND, source_files=158)
        catalogue = copy.deepcopy(contract.CATALOGUE)
        catalogue['source_map']['sha256'] = '1' * 64
        catalogue['provenance']['sha256'] = '2' * 64
        successor.update(catalogue)
        with mock.patch.object(contract, 'COMPOSITION_CATALOGUE', None):
            with self.assertRaisesRegex(ValueError, 'unbound'):
                contract.validate_profile(successor)
        with mock.patch.object(contract, 'COMPOSITION_CATALOGUE', catalogue):
            self.assertEqual(contract.validate_profile(successor), successor)
            self.assertEqual(contract.validate_profile(legacy), legacy)
            for key in contract.FALSE_FACTS:
                changed = copy.deepcopy(successor); changed[key] = True
                with self.subTest(key=key), self.assertRaises(ValueError):
                    contract.validate_profile(changed)

    def test_source_profile_cannot_promote_or_retarget_itself(self):
        for name, replacement in (('build', True), ('production_eligible', True),
                ('source_files', self.profile['source_files'] + 1), ('publication_policy', 'qualified')):
            value = copy.deepcopy(self.profile); value[name] = replacement
            with self.subTest(name=name), self.assertRaises(ValueError):
                contract.validate_profile(value)
        value = copy.deepcopy(self.profile); value['target']['system'] = 'Linux'
        with self.assertRaises(ValueError):
            contract.validate_profile(value)

    def test_woff2_off_and_on_have_independent_closed_library_sets(self):
        for selection in ('OFF', 'ON'):
            value = inputs(selection)
            self.assertEqual(contract.validate_inputs(value), value)
        self.value['woff2'] = 'ON'; self.reject(pattern='library map')
        self.value = inputs('ON'); self.value['woff2'] = 'OFF'; self.reject(pattern='library map')

    def test_windows_policy_rejects_other_runtime_targets_and_bool_numbers(self):
        changes = {'schema_version': True, 'engine_cxx_standard': True,
            'target': 'linux-x86_64', 'build_type': 'Debug', 'crt': 'dynamic-md',
            'cpu_baseline': 'avx2', 'os_floor_declaration': 'windows-10-1809-qualified'}
        for name, replacement in changes.items():
            value = copy.deepcopy(self.value); value[name] = replacement
            with self.subTest(name=name): self.reject(value, 'target/C\\+\\+23')

    def test_unknown_and_omitted_fields_fail_before_reference_inspection(self):
        for parent in ((), ('toolchain',), ('toolchain', 'msvc_stl'),
                       ('dependency_inventory',), ('libraries', 'ICU::data')):
            value = copy.deepcopy(self.value); item = value
            for key in parent: item = item[key]
            item['unexpected'] = True
            with self.subTest(parent=parent): self.reject(value, 'fields')
        del self.value['toolchain']['windows_sdk']; self.reject(pattern='fields')

    def test_paths_refuse_devices_ads_unc_aliases_and_cmake_syntax(self):
        paths = ('relative/file', '/retained/lib', 'c:/retained/lib', 'C:relative',
            'C:/', 'C:/retained/../lib', 'C:/retained/./lib', 'C://retained/lib',
            'C:/retained/lib/', 'C:\\retained\\lib', '//server/share/lib',
            'C:/retained/NUL.lib', 'C:/retained/CON/test.lib', 'C:/retained/COM¹.lib',
            'C:/retained/LPT²/test.lib', 'C:/retained/a:stream',
            'C:/retained/trailing.', 'C:/retained/trailing ', 'C:/retained/a;b',
            'C:/retained/$<CONFIG>', 'C:/retained/@TOKEN@', 'C:/retained/a\nb')
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                contract.windows_path(path, 'fixture')
        self.assertEqual(contract.windows_path('C:/retained/München/lib', 'fixture'),
                         'C:/retained/München/lib')

    def test_reference_pins_are_independent_nonzero_and_exact(self):
        for replacement in ('0' * 64, 'A' * 64, 'a' * 63, 2):
            value = copy.deepcopy(self.value); value['toolchain']['compiler']['sha256'] = replacement
            with self.subTest(replacement=replacement): self.reject(value, 'SHA256')

    def test_compiler_linker_and_builtins_roles_are_explicit(self):
        for role, path in (('compiler', 'C:/tools/cl.exe'), ('linker', 'C:/tools/ld.exe'),
                           ('builtins', 'C:/tools/builtins.a')):
            value = copy.deepcopy(self.value); value['toolchain'][role] = reference(path)
            with self.subTest(role=role): self.reject(value, 'tool role')
        self.value['toolchain']['linker'] = reference('C:/retained/msvc/bin/link.exe')
        self.assertEqual(contract.validate_inputs(self.value), self.value)

    def test_compiler_version_is_declared_not_an_executed_version_probe(self):
        for version in ('unknown', '19', '19.1', '19.1.7-dev', True):
            value = copy.deepcopy(self.value); value['toolchain']['compiler_version'] = version
            with self.subTest(version=version): self.reject(value, 'compiler version')

    def test_archive_and_include_escape_and_dll_dependencies_are_rejected(self):
        for path in ('C:/retained/native-dependencies-sibling/lib/icu.lib',
                     'D:/retained/native-dependencies/lib/icu.lib',
                     'C:/retained/native-dependencies/lib/icu.dll'):
            value = copy.deepcopy(self.value); value['libraries']['ICU::data'].update(reference(path))
            with self.subTest(path=path): self.reject(value, 'static dependency archive')
        self.value['libraries']['ICU::data']['includes'] = ['C:/ambient/include']
        self.reject(pattern='include escapes')

    def test_casefold_path_alias_or_conflicting_pin_is_rejected(self):
        first = self.value['libraries']['ICU::data']
        second = self.value['libraries']['ICU::uc']
        second.update(reference(first['path'].replace('/lib/', '/LIB/')))
        self.reject(pattern='Conflicting Windows path')
        second.update(reference(first['path'])); second['sha256'] = '1' * 64
        self.reject(pattern='Conflicting Windows path')

    def test_implicit_parent_case_and_file_directory_aliases_are_rejected(self):
        self.value['libraries']['ICU::data']['path'] = self.value['libraries']['ICU::data']['path'].replace(
            '/retained/', '/Retained/')
        self.reject(pattern='Conflicting Windows path')
        self.value = inputs()
        self.value['toolchain']['windows_sdk']['root'] = self.value['toolchain']['compiler']['path']
        self.reject(pattern='Conflicting Windows path')

    def test_definitions_links_and_duplicate_properties_cannot_smuggle_code(self):
        replacements = {'definitions': ['X=$<CONFIG>'], 'links': ['C:/ambient/tool.lib'],
                        'includes': ['C:/retained/native-dependencies/include'] * 2}
        for name, replacement in replacements.items():
            value = copy.deepcopy(self.value); value['libraries']['ICU::data'][name] = replacement
            with self.subTest(name=name): self.reject(value)
        self.value['libraries']['ICU::data']['links'] = ['Fontconfig::Fontconfig']
        self.reject(pattern='closed native/system')

    def test_static_link_order_is_preserved(self):
        selected = self.value['libraries']['ICU::data']
        selected['links'] = ['ICU::uc', 'ICU::i18n', 'ws2_32']
        checked = contract.validate_inputs(self.value)
        self.assertEqual(checked['libraries']['ICU::data']['links'], selected['links'])

    def test_webp_requires_explicit_same_source_sharpyuv_link_and_target(self):
        self.value['libraries']['WebP::libwebp']['links'] = ['ws2_32']
        self.reject(pattern='same-source sharpyuv')
        self.value = inputs(); del self.value['libraries']['WebP::sharpyuv']
        self.reject(pattern='library map')

    def test_accepted_data_is_owned_and_result_never_claims_retained_bytes(self):
        checked = contract.validate_inputs(self.value)
        result = contract.assess(self.profile, checked)
        self.value['libraries']['ICU::data']['links'].clear()
        self.assertEqual(checked['libraries']['ICU::data']['links'], ['ws2_32'])
        self.assertIs(result['manifest_contract_valid'], True)
        self.assertGreater(len(result['missing_admission']), 8)
        for name in contract.FALSE_FACTS: self.assertIs(result[name], False)

    def test_absent_real_admission_remains_named_missing_inputs(self):
        rows = contract.required_admission(self.value)
        self.assertEqual(len({item['role'] for item in rows}), len(rows))
        self.assertIn('metadata-publication-join', {item['role'] for item in rows})
        self.assertIn('native-build-adapter', {item['role'] for item in rows})
        report = contract.MissingInputs(rows).as_dict()
        for name in contract.FALSE_FACTS: self.assertIs(report[name], False)
        rows[0]['path'] = 'mutated'
        self.assertNotEqual(report['missing'][0]['path'], 'mutated')

    def test_json_duplicate_nonfinite_unicode_and_oversize_rejection(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":"\\ud800"}', b'\xff', b' ' * (contract.MAX_DOCUMENT + 1)):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                contract.parse_document(raw)

    def test_cli_reads_only_two_selected_metadata_files_and_plan_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            profile, source = directory / 'profile.json', directory / 'inputs.json'
            profile.write_bytes(contract.encoded(self.profile)); source.write_bytes(contract.encoded(self.value))
            arguments = ['--profile', str(profile), '--profile-sha256', hashlib.sha256(profile.read_bytes()).hexdigest(),
                '--inputs', str(source), '--inputs-sha256', hashlib.sha256(source.read_bytes()).hexdigest()]
            with mock.patch.object(contract, 'read_metadata', wraps=contract.read_metadata) as read, \
                    redirect_stdout(io.StringIO()) as output:
                self.assertEqual(contract.cli(['check', *arguments]), 0)
            self.assertEqual(read.call_count, 2)
            self.assertIs(json.loads(output.getvalue())['executable_plan'], False)
            with redirect_stderr(io.StringIO()) as errors, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(contract.cli(['plan', *arguments]), 2)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(json.loads(errors.getvalue())['kind'],
                             'foundation-native-engine-windows-missing-inputs-v1')

    def test_metadata_missing_and_tampered_are_distinct_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve(); path = directory / 'metadata.json'
            with self.assertRaises(contract.MissingInputs):
                contract.read_metadata(path, '1' * 64, 'fixture')
            path.write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                contract.read_metadata(path, '1' * 64, 'fixture')

    @unittest.skipIf(os.name == 'nt', 'actual symlink fixture requires POSIX; native Windows reparse qualification is separate')
    def test_metadata_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve(); path = directory / 'metadata.json'
            path.write_bytes(b'{}\n')
            symbolic = directory / 'symbolic.json'; symbolic.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'ordinary'):
                contract.read_metadata(symbolic, '1' * 64, 'fixture')

    def test_metadata_hardlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve(); path = directory / 'metadata.json'
            path.write_bytes(b'{}\n')
            os.link(path, directory / 'hard.json')
            with self.assertRaisesRegex(ValueError, 'ordinary'):
                contract.read_metadata(path, '1' * 64, 'fixture')

    def test_cmake_importer_declares_the_same_closed_dependency_set(self):
        source = (ROOT / contract.RECIPE / 'source/engine/Source/cmake/FoundationWindowsInputs.cmake').read_text()
        match = re.search(r'set\(_required\s+(.*?)\)', source, re.S)
        self.assertIsNotNone(match)
        self.assertEqual(set(match.group(1).split()), contract.LIBRARIES)

    def cmake_importer(self, change=None, woff2='OFF'):
        """Inert importer only: no CMake project, compiler, real SDK or targets."""
        cmake = shutil.which('cmake')
        if cmake is None:
            self.skipTest('inert Windows importer fixture needs installed CMake')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            prefix = root / 'prefix'; (prefix / 'lib').mkdir(parents=True)
            (prefix / 'include').mkdir()
            selected = inputs(woff2)
            selected['dependency_prefix'] = str(prefix)
            for role in ('compiler', 'linker', 'builtins'):
                path = root / (role + '.fixture'); path.write_bytes(role.encode())
                selected['toolchain'][role] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for role in ('msvc_stl', 'windows_sdk'):
                directory = root / role; directory.mkdir()
                inventory = root / (role + '.json'); inventory.write_bytes(b'{}\n')
                selected['toolchain'][role] = {'root': str(directory), 'inventory': {
                    'path': str(inventory), 'sha256': hashlib.sha256(inventory.read_bytes()).hexdigest()}}
            inventory = root / 'dependencies.json'; inventory.write_bytes(b'{}\n')
            selected['dependency_inventory'] = {'path': str(inventory),
                                                'sha256': hashlib.sha256(inventory.read_bytes()).hexdigest()}
            for target, item in selected['libraries'].items():
                path = prefix / 'lib' / (target.replace('::', '_') + '.lib')
                path.write_bytes(('inert-fixture-' + target).encode())
                item.update(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            includes=[str(prefix / 'include')])
                if target == 'WebP::libwebp': item['links'] = ['WebP::sharpyuv']
            if change is not None: change(selected)
            manifest = root / 'inputs.json'; manifest.write_bytes(contract.encoded(selected))
            importer = ROOT / contract.RECIPE / 'source/engine/Source/cmake/FoundationWindowsInputs.cmake'
            script = root / 'fixture.cmake'
            script.write_text('''cmake_minimum_required(VERSION 3.24)
# These host/compiler variables are synthetic policy inputs, never probes.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_HOST_SYSTEM_NAME Windows)
set(MSVC TRUE)
set(COMPILER_IS_CLANG_CL TRUE)
set(CMAKE_CXX_COMPILER_FRONTEND_VARIANT MSVC)
set(WTF_CPU_X86_64 TRUE)
set(CMAKE_SIZEOF_VOID_P 8)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
set(CMAKE_CXX_COMPILER_VERSION 19.1.7)
function(add_library target)
  set_property(GLOBAL APPEND PROPERTY fixture_targets "${target}")
endfunction()
function(set_target_properties target)
  set_property(GLOBAL PROPERTY "fixture_${target}_${ARGV2}" "${ARGV3}")
endfunction()
''' + '\n'.join('set(' + name + ' "' + value.replace('\\', '/') + '")' for name, value in {
                'CMAKE_C_COMPILER': selected['toolchain']['compiler']['path'],
                'CMAKE_CXX_COMPILER': selected['toolchain']['compiler']['path'],
                'CMAKE_LINKER': selected['toolchain']['linker']['path'],
                'FOUNDATION_NATIVE_WINDOWS_INPUTS': str(manifest),
                'FOUNDATION_NATIVE_WINDOWS_INPUTS_SHA256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                'FOUNDATION_NATIVE_DEPENDENCY_PREFIX': str(prefix),
                'FOUNDATION_NATIVE_DEPENDENCY_TARGET': 'windows-x86_64'}.items()) + '\n' +
                'include("' + str(importer).replace('\\', '/') + '")\n' +
                'foundation_import_windows_inputs()\n' +
                'get_property(_links GLOBAL PROPERTY "fixture_WebP::libwebp_INTERFACE_LINK_LIBRARIES")\n' +
                'if(NOT "WebP::sharpyuv" IN_LIST _links)\n  message(FATAL_ERROR "fixture lost raw sharpyuv edge")\nendif()\n')
            environment = {name: value for name, value in os.environ.items()
                           if name.upper() not in ('CL', '_CL_', 'LINK', '_LINK_')}
            return subprocess.run([cmake, '-P', str(script)], cwd=root, env=environment,
                                  capture_output=True, text=True, timeout=5, check=False)

    def test_inert_cmake_imports_explicit_sharpyuv_for_woff2_on_and_off(self):
        for selection in ('OFF', 'ON'):
            with self.subTest(woff2=selection):
                result = self.cmake_importer(woff2=selection)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_inert_cmake_rejects_missing_sharpyuv_edge_archive_and_old19map(self):
        changes = (
            (lambda value: value['libraries']['WebP::libwebp'].update(links=[]), 'same-source sharpyuv'),
            (lambda value: value['libraries'].pop('WebP::sharpyuv'), 'closed target set'),
            (lambda value: value['libraries']['WebP::sharpyuv'].update(sha256='1' * 64), 'independent SHA256'))
        for change, diagnostic in changes:
            with self.subTest(diagnostic=diagnostic):
                result = self.cmake_importer(change)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(diagnostic, ' '.join((result.stdout + result.stderr).split()))


if __name__ == '__main__':
    unittest.main()
