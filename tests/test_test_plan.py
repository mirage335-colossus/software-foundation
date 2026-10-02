import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("test_plan", Path(__file__).resolve().parents[1] / "tools/test_plan.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


class CoverageTests(unittest.TestCase):
    def test_partition_and_complete_merge(self):
        recipe = plan.make_plan(["c", "a", "b"], 2, "source")
        reports = [{"plan": recipe["id"], "shard": index, "exit_code": 0,
                    "results": {name: "passed" for name in shard}}
                   for index, shard in enumerate(recipe["shards"])]
        self.assertEqual(plan.merge(recipe, reports)["tests"], 3)
        for broken in (reports[:1], reports + reports[:1]):
            with self.assertRaises(ValueError):
                plan.merge(recipe, broken)
        reports[0]["results"]["a"] = "skipped"
        with self.assertRaises(ValueError):
            plan.merge(recipe, reports)

    def test_junit_requires_every_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.xml"
            path.write_text('<testsuite><testcase name="a" status="run"/><testcase name="b"><skipped/></testcase></testsuite>')
            self.assertEqual(plan.junit_results(path, ["a", "b"])["b"], "failed_or_incomplete")
            with self.assertRaises(ValueError):
                plan.junit_results(path, ["a", "b", "c"])

    def test_location_normalization_precedes_windows_json_escaping(self):
        from unittest.mock import patch
        value={'path':r'C:\work\source\main.cpp','command':['C:/work/source/test.py',r'C:\external\compiler.exe']}
        with patch.object(plan,'ROOT',r'C:\work\source'):
            normalized=plan.normalize_locations(value,Path.cwd()/'build')
        self.assertEqual(normalized,{'path':r'<SOURCE>\main.cpp','command':['<SOURCE>/test.py',r'C:\external\compiler.exe']})

    def test_tampered_and_empty_inventory_rejected(self):
        with self.assertRaises(ValueError):
            plan.make_plan([], 1, "source")
        recipe = plan.make_plan(["a", "b"], 2, "source")
        recipe["tests"].append("c")
        with self.assertRaises(ValueError):
            plan.validate_plan(recipe)

class ReceiptTests(unittest.TestCase):
    def test_failed_attempt_removes_stale_receipt(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "plan.json"
            invalid.write_text(json.dumps({"schema_version": 0}))
            for operation in ("run", "merge"):
                output = root / "previous.json"
                output.write_text('{"status":"passed"}')
                command = [sys.executable, str(Path(plan.__file__)), operation,
                           "--plan", str(invalid), "--output", str(output)]
                if operation == "run":
                    command += ["--build", str(root / "missing-build"), "--shard", "0"]
                else:
                    command += [str(root / "missing-report")]
                result = subprocess.run(command, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

class InputIdentityTests(unittest.TestCase):
    def setUp(self):
        import json
        from unittest.mock import patch
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'application'; self.source.mkdir()
        (self.source / 'main.cpp').write_text('int main() { return 0; }\n')
        self.build = self.root / 'build'; self.build.mkdir()
        self.compiler = self.root / 'compiler'; self.compiler.write_bytes(b'first compiler')
        self.cache = {'CMAKE_CXX_COMPILER': str(self.compiler), 'FOUNDATION_BUILD_GUI': 'OFF',
                      'FOUNDATION_DEPENDENCY_RECIPES': ''}
        (self.build / 'build-info.txt').write_text('fixture build\n')
        self.root_patch = patch.object(plan, 'ROOT', self.source); self.root_patch.start()
        self.definitions_patch = patch.object(plan, 'test_definitions', return_value=[{'name': 'core.store', 'command': ['inert']}])
        self.definitions_patch.start(); self.write_cache()

    def tearDown(self):
        self.definitions_patch.stop(); self.root_patch.stop(); self.temporary.cleanup()

    def write_cache(self):
        (self.build / 'CMakeCache.txt').write_text(''.join(name + ':STRING=' + value + '\n' for name, value in self.cache.items()))

    def freeze(self):
        return plan.make_plan(['core.store'], 1, plan.source_id(self.build), plan.configuration_id(self.build))

    def wrapper(self, **extra):
        import json
        value = {'sdk': None, 'gui': None, 'dependencies': [], 'windows_dependencies': None}
        value.update(extra)
        (self.build / 'wrapper-identity.json').write_text(json.dumps(value))
        (self.build / 'configured-identity.json').write_text(json.dumps(plan.builder.cache_identity(self.build)))
        return value

    def test_unchanged_native_tree_retains_valid_plan(self):
        frozen = self.freeze()
        plan.require_current(self.build, frozen)
        self.assertEqual(self.freeze(), frozen)

    def test_compiler_bytes_change_with_unchanged_path_size_and_time(self):
        import os
        frozen = self.freeze(); stat = self.compiler.stat()
        self.compiler.write_bytes(b'other compiler')
        os.utime(self.compiler, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'compiler'):
            plan.require_current(self.build, frozen)

    def test_wrapper_configured_compiler_receipt_is_reverified(self):
        self.wrapper(); self.freeze()
        self.compiler.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'configured compiler'):
            plan.build_inputs(self.build)

    def test_prepared_sdk_target_header_mutation_rejected_before_compile(self):
        import json, sys
        from unittest.mock import patch
        from test_sdk import fixture
        recipe, sdk, _, _ = fixture(self.root / 'dependency')
        self.cache.update(FOUNDATION_SDK_ROOT=str(sdk), CMAKE_CXX_COMPILER=str(sdk / 'bin/c++'))
        self.write_cache()
        # Direct CMake appends its SDK recipe outside the cache; verify that
        # ordinary SDK configurations remain supported without a wrapper stamp.
        frozen = self.freeze()
        (self.root / 'plan.json').write_text(json.dumps(frozen))
        (sdk / 'sysroot/usr/include/example.h').write_bytes(b'changed target input')
        with patch.object(sys, 'argv', ['test_plan.py', 'run', '--build', str(self.build), '--plan', str(self.root / 'plan.json'), '--shard', '0', '--output', str(self.root / 'report.json')]), patch.object(plan.windows_compiler, 'run') as run:
            with self.assertRaises(ValueError): plan.main()
            run.assert_not_called()
        self.assertFalse((self.root / 'report.json').exists())

    def test_external_gui_bytes_change_source_identity(self):
        gui = self.root / 'gui-source'; gui.mkdir(); (gui / 'view.hpp').write_text('first input')
        self.cache.update(FOUNDATION_BUILD_GUI='ON', FOUNDATION_GUI_SOURCE=str(gui)); self.write_cache()
        frozen = self.freeze()
        (gui / 'view.hpp').write_text('other input')
        with self.assertRaisesRegex(ValueError, 'source'):
            plan.require_current(self.build, frozen)

    def test_retained_dependency_archive_mutation_is_reverified(self):
        from test_sdk import fixture
        from dependency_store import names, verify_group
        recipe, _, _, group = fixture(self.root / 'dependency')
        self.cache['FOUNDATION_DEPENDENCY_RECIPES'] = recipe; self.write_cache()
        # Match the wrapper's canonical location, including Windows short-name aliases.
        self.wrapper(dependencies=[{'root': str(group.resolve(strict=True)), 'recipe': recipe, 'files': verify_group(group, recipe)}])
        self.freeze()
        (group / names(recipe)[1]).write_bytes(b'changed source archive')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            plan.build_inputs(self.build)

    def test_native_search_environment_change_invalidates_plan(self):
        import os
        from unittest.mock import patch
        frozen = self.freeze()
        with patch.dict(os.environ, {'CPATH': str(self.root / 'other-headers')}):
            with self.assertRaisesRegex(ValueError, 'configuration'):
                plan.require_current(self.build, frozen)

    def test_native_dependency_prefix_is_reverified_in_direct_and_wrapper_trees(self):
        from unittest.mock import patch
        root = self.root / 'inputs'; root.mkdir(); prefix = root / 'usr'; prefix.mkdir()
        self.cache['FOUNDATION_DEPENDENCY_PREFIX'] = str(root); self.write_cache()
        first = {'sha256':'a'*64, 'prefix':str(prefix.resolve())}
        with patch('prepare_dependencies.verify', return_value=first) as verify:
            frozen = self.freeze(); verify.assert_called()
            self.wrapper(dependency_prefix={'root':str(root.resolve()), **first})
            wrapped = self.freeze()
            with patch('prepare_dependencies.verify', return_value={**first, 'sha256':'b'*64}):
                with self.assertRaisesRegex(ValueError,'dependency prefix'): self.freeze()
            self.assertNotEqual(frozen['configuration'], wrapped['configuration'])
        (self.build / 'wrapper-identity.json').unlink(); (self.build / 'configured-identity.json').unlink()
        self.cache['FOUNDATION_SDK_ROOT'] = str(root); self.write_cache()
        with self.assertRaisesRegex(ValueError,'cannot mix'): self.freeze()

    def test_primary_recipe_without_retained_inputs_is_rejected(self):
        self.cache['FOUNDATION_DEPENDENCY_RECIPE'] = 'b' * 64; self.write_cache()
        with self.assertRaisesRegex(ValueError, 'complete verified'):
            self.freeze()

    def test_prepared_recipe_without_group_location_is_rejected(self):
        self.cache['FOUNDATION_DEPENDENCY_RECIPES'] = 'a' * 64; self.write_cache()
        with self.assertRaisesRegex(ValueError, 'complete verified'):
            self.freeze()

    def test_gui_group_is_verified_on_every_configuration_capture(self):
        from unittest.mock import patch
        group = self.root / 'gui-group'; group.mkdir()
        self.wrapper(gui_input_group={'root': str(group.resolve(strict=True)), 'sha256': 'a' * 64})
        with patch.object(plan, 'verify_gui_group', side_effect=['a' * 64, 'b' * 64]) as verify:
            self.freeze()
            verify.assert_called_once_with(str(group.resolve(strict=True)))
            with self.assertRaisesRegex(ValueError, 'GUI input group'):
                self.freeze()
            self.assertEqual(verify.call_count, 2)

    def test_compiler_mutation_during_prerequisite_build_leaves_no_plan(self):
        import sys
        from unittest.mock import patch
        output = self.root / 'plan.json'
        def changed(*args, **kwargs): self.compiler.write_bytes(b'changed during build')
        with patch.object(sys, 'argv', ['test_plan.py', 'plan', '--build', str(self.build), '--shards', '1', '--output', str(output)]), patch.object(plan.windows_compiler, 'run', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'compiling test prerequisites'):
                plan.main()
        self.assertFalse(output.exists())

    def test_mutation_during_test_execution_leaves_no_receipt(self):
        import json,sys,subprocess
        from unittest.mock import patch
        frozen = self.freeze(); path=self.root / 'plan.json';path.write_text(json.dumps(frozen))
        output=self.root / 'report.json';output.write_text('previous receipt')
        def runner(argv, **kwargs):
            if '--output-junit' in argv:
                Path(argv[argv.index('--output-junit')+1]).write_text('<testsuite><testcase name="core.store" status="run"/></testsuite>')
                self.compiler.write_bytes(b'changed during test')
            return subprocess.CompletedProcess(argv,0)
        with patch.object(sys, 'argv', ['test_plan.py','run','--build',str(self.build),'--plan',str(path),'--shard','0','--output',str(output)]), patch.object(plan.windows_compiler,'run',side_effect=runner):
            with self.assertRaisesRegex(ValueError,'compiler'):
                plan.main()
        self.assertFalse(output.exists())

    def owned_route(self, route, output):
        import json, sys
        from unittest.mock import patch
        if route == 'candidate':
            (self.build / 'CTestTestfile.cmake').write_text('# declaration fixture\n')
            (self.build / 'test-platform.json').write_text(json.dumps({'schema_version': 1, 'excluded_suites': {}}))
            definitions = [{'name': 'core.store', 'command': ['inert']},
                {'name': 'tools.fixture', 'properties': [{'name': 'LABELS', 'value': ['tools']}]},
                {'name': 'integration.fixture', 'properties': [{'name': 'LABELS', 'value': ['integration']}]}]
            with patch.object(plan, 'test_definitions', return_value=definitions):
                return plan.candidate_run(self.build, 'core', output, jobs=3, build_jobs=2)
        argv = ['test_plan.py', route, '--build', str(self.build), '--output', str(output), '--jobs', '2']
        if route == 'run':
            recipe = self.root / 'frozen-plan.json'; recipe.write_text(json.dumps(self.freeze()))
            argv += ['--plan', str(recipe), '--shard', '0']
        else:
            argv += ['--shards', '1']
        with patch.object(sys, 'argv', argv):
            return plan.main()

    def test_owned_ctest_nonzero_preserves_failed_receipts_and_junit(self):
        import json, subprocess
        from unittest.mock import patch
        programs = {'cmake': 'owned-cmake', 'ctest': 'owned-ctest'}
        environment = {'PATH': 'selected-toolkit'}
        for route in ('candidate', 'run'):
            with self.subTest(route=route):
                output = self.root / (route + '-failed.json')
                calls = []
                def owned(argv, **options):
                    calls.append(argv); self.assertEqual(options, {'env': environment})
                    if argv[0] == programs['ctest']:
                        junit = Path(argv[argv.index('--output-junit') + 1])
                        junit.write_text('<testsuite><testcase name="core.store"><failure/></testcase></testsuite>')
                        raise subprocess.CalledProcessError(8, argv)
                    self.assertEqual(argv[0], programs['cmake'])
                    self.assertIn('foundation-tests', argv)
                    return subprocess.CompletedProcess(argv, 0)
                with patch.object(plan, 'execution_context', return_value=(programs, environment)), \
                        patch.object(plan.windows_compiler, 'run', side_effect=owned), \
                        patch.object(plan.subprocess, 'run', side_effect=AssertionError('unowned test launch')):
                    if route == 'candidate':
                        with self.assertRaisesRegex(ValueError, 'candidate scope failed'):
                            self.owned_route(route, output)
                    else:
                        self.assertEqual(self.owned_route(route, output), 1)
                receipt = json.loads(output.read_text())
                self.assertEqual(receipt['exit_code'], 8)
                self.assertEqual(receipt['results'], {'core.store': 'failed_or_incomplete'})
                self.assertEqual([argv[0] for argv in calls], ['owned-cmake', 'owned-ctest'])
                self.assertTrue(Path(calls[-1][calls[-1].index('--output-junit') + 1]).is_file())
                self.assertEqual(environment, {'PATH': 'selected-toolkit'})

    def test_owner_and_timeout_failures_never_read_junit_or_emit_receipts(self):
        import subprocess
        from unittest.mock import patch
        import process_tree
        programs = {'cmake': 'owned-cmake', 'ctest': 'owned-ctest'}
        for route in ('candidate', 'run', 'plan'):
            for phase in ('compile', 'test') if route != 'plan' else ('compile',):
                for failure in (process_tree.ProcessTreeError('descendant join unknown'),
                                subprocess.TimeoutExpired('owned-command', 1)):
                    with self.subTest(route=route, phase=phase, failure=type(failure).__name__):
                        output = self.root / (route + '-' + phase + '-' + type(failure).__name__ + '.json')
                        def owned(argv, **options):
                            if (argv[0] == programs['cmake']) == (phase == 'compile'):
                                raise failure
                            return subprocess.CompletedProcess(argv, 0)
                        with patch.object(plan, 'execution_context', return_value=(programs, {})), \
                                patch.object(plan.windows_compiler, 'run', side_effect=owned) as run, \
                                patch.object(plan.subprocess, 'run', side_effect=AssertionError('unowned test launch')), \
                                patch.object(plan, 'junit_results', side_effect=AssertionError('unsafe JUnit read')) as read:
                            with self.assertRaises(type(failure)) as caught:
                                self.owned_route(route, output)
                        self.assertIs(caught.exception, failure)
                        self.assertEqual(run.call_count, 1 if phase == 'compile' else 2)
                        read.assert_not_called()
                        self.assertFalse(output.exists())

class NativeExecutionTests(unittest.TestCase):
    def test_actual_cmake_plan_run_and_merge(self):
        import json, subprocess, sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; source.mkdir(); build = root / 'build'
            (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.24)\nproject(PlanProbe LANGUAGES CXX)\nenable_testing()\nadd_executable(probe main.cpp)\nadd_custom_target(foundation-tests DEPENDS probe)\nadd_test(NAME core.probe COMMAND probe)\nfile(WRITE "${CMAKE_BINARY_DIR}/build-info.txt" "fixture\\n")\n')
            (source / 'main.cpp').write_text('int main() { return 0; }\n')
            subprocess.run(['cmake','-S',str(source),'-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release'],check=True,capture_output=True)
            recipe = root / 'plan.json'; result = root / 'shard.json'; merged = root / 'merged.json'
            with patch.object(plan, 'ROOT', source):
                for argv in (['plan','--build',str(build),'--shards','1','--output',str(recipe)],
                             ['run','--build',str(build),'--plan',str(recipe),'--shard','0','--output',str(result)],
                             ['merge','--plan',str(recipe),'--output',str(merged),str(result)]):
                    with patch.object(sys,'argv',['test_plan.py',*argv]): self.assertEqual(plan.main(),0)
            self.assertEqual(json.loads(merged.read_text())['status'],'passed')
            self.assertEqual(json.loads(merged.read_text())['tests'],1)


class CandidateInventoryTests(unittest.TestCase):
    def test_actual_unlabelled_test_runs_and_every_scope_is_required(self):
        import json,subprocess,sys,copy
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';source.mkdir();build=root/'build'
            script=source/'fixture.py'
            script.write_text("import json,sys\nfrom pathlib import Path\np=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'schema_version':1,'system':'fixture','status':'passed','inventory':['one'],'excluded':{},'results':{'one':{'status':'passed'}}}))\n")
            (source/'main.cpp').write_text('#include <fstream>\nint main(int argc, char** argv) { if (argc != 2) return 1; std::ofstream out(argv[1]); out << \"ran\"; return out ? 0 : 1; }\n')
            cmake='cmake_minimum_required(VERSION 3.24)\nproject(CandidateProbe LANGUAGES CXX)\nenable_testing()\nadd_executable(probe EXCLUDE_FROM_ALL main.cpp)\nadd_custom_target(foundation-tests DEPENDS probe)\n'
            cmake+='add_test(NAME newly_unlabelled COMMAND probe "${CMAKE_BINARY_DIR}/unlabelled-ran")\n'
            cmake+='add_test(NAME tools.fixture COMMAND "'+sys.executable.replace('\\','/')+'" "${CMAKE_SOURCE_DIR}/fixture.py" "${CMAKE_BINARY_DIR}/test-reports/fixture.json")\nset_tests_properties(tools.fixture PROPERTIES LABELS tools)\n'
            cmake+='add_test(NAME integration.fixture COMMAND "${CMAKE_COMMAND}" -E true)\nset_tests_properties(integration.fixture PROPERTIES LABELS integration)\n'
            cmake+='file(WRITE "${CMAKE_BINARY_DIR}/build-info.txt" "fixture")\n'
            (source/'CMakeLists.txt').write_text(cmake)
            subprocess.run(['cmake','-S',str(source),'-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release'],check=True,capture_output=True)
            (build/'test-platform.json').write_text(json.dumps({'schema_version':1,'excluded_suites':{'tools.unavailable':'explicit fixture platform exclusion'}}))
            paths=[]
            with patch.object(plan,'ROOT',source):
                unresolved=next(row for row in plan.test_definitions(build) if row['name']=='newly_unlabelled')
                self.assertNotIn('command',unresolved)
                frozen=plan.candidate_plan(build)
                self.assertEqual(frozen['scopes']['core'],['newly_unlabelled'])
                for scope in plan.CANDIDATE_SCOPES:
                    output=root/(scope+'.json');plan.candidate_run(build,scope,output);paths.append(output)
                self.assertTrue((build/'unlabelled-ran').is_file())
                merged=plan.candidate_merge(paths)
                self.assertEqual(merged['mode'],'candidate');self.assertEqual(merged['plan']['platform_exclusions'],frozen['platform_exclusions'])
                for changed in (paths[:2],paths+paths[:1]):
                    with self.assertRaises(ValueError):plan.candidate_merge(changed)
                self.assertEqual(plan.candidate_merge(paths[:1],diagnostic=True)['omitted_scopes'],['integration','tools'])
                # Exercise the actual CLI with the relative receipt path used in CI.
                command=[sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'tools/test_plan.py'),
                         'candidate-run','--build',str(build),'--scope','core','--output','relative.json']
                result=subprocess.run(command,cwd=root,capture_output=True,text=True)
                self.assertEqual(0,result.returncode,result.stdout+result.stderr)
                self.assertTrue((root/'relative.junit.xml').is_file())
                self.assertFalse((build/'relative.junit.xml').exists())
                row=json.loads(paths[1].read_text());row['tool_reports']['tools.fixture']['results']['one']['status']='incomplete';paths[1].write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError,'inner'):plan.candidate_merge(paths)
                original_run=plan.windows_compiler.run
                def mutate_declaration(argv, **kwargs):
                    result=original_run(argv,**kwargs)
                    if '--build' in argv:
                        declaration=build/'CTestTestfile.cmake'
                        declaration.write_text(declaration.read_text()+'# changed during prerequisite build\n')
                    return result
                with patch.object(plan.windows_compiler,'run',side_effect=mutate_declaration):
                    with self.assertRaisesRegex(ValueError,'prerequisite compilation'):
                        plan.candidate_run(build,'core',root/'changed.json')
                self.assertFalse((root/'changed.json').exists())
