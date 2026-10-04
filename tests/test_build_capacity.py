import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_capacity as c
import build as b


class Capacity(unittest.TestCase):
    def candidate_capacity_scripts(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/candidate.yml').read_text()
        self.assertNotIn('CMAKE_BUILD_PARALLEL_LEVEL: ${{ inputs.build_jobs }}', workflow)
        scripts = {}
        for job, following, first_child in (
                ('source', 'package', '    - if: runner.os'),
                ('sanitizer', 'distribution', '    - name: Explicit pinned Rust host preparation')):
            block = workflow.split('  ' + job + ':\n', 1)[1].split('  ' + following + ':\n', 1)[0]
            self.assertIn('      BUILD_JOBS: ${{ inputs.build_jobs }}', block)
            marker = '    - name: Resolve compile capacity\n'
            self.assertEqual(block.count(marker), 1)
            self.assertLess(block.index(marker), block.index(first_child))
            step = block.split(marker, 1)[1].split('    - ', 1)[0]
            self.assertIn('      shell: python\n', step)
            scripts[job] = textwrap.dedent(step.split('      run: |\n', 1)[1])
        return scripts

    def test_candidate_exports_resolved_auto_and_explicit_capacity_to_later_steps(self):
        for job, script in self.candidate_capacity_scripts().items():
            for selector, expected in (('auto', '3'), ('4', '4')):
                with self.subTest(job=job, selector=selector), tempfile.TemporaryDirectory() as temporary:
                    environment_file = Path(temporary) / 'environment'
                    environment_file.write_text('EXISTING=value\n', encoding='utf-8')
                    with patch.dict(os.environ, {'BUILD_JOBS': selector, 'GITHUB_ENV': str(environment_file)}), \
                            patch.object(c, 'default_jobs', return_value=3) as automatic, \
                            patch.object(sys, 'path', list(sys.path)):
                        exec(compile(script, 'candidate-' + job, 'exec'), {})
                    self.assertEqual(environment_file.read_text(encoding='utf-8'),
                                     'EXISTING=value\nCMAKE_BUILD_PARALLEL_LEVEL=' + expected + '\n')
                    self.assertEqual(automatic.call_count, 1 if selector == 'auto' else 0)

    def test_candidate_rejects_invalid_capacity_before_export(self):
        for job, script in self.candidate_capacity_scripts().items():
            for selector in ('0', '-1', '1.5', 'many'):
                with self.subTest(job=job, selector=selector), tempfile.TemporaryDirectory() as temporary:
                    environment_file = Path(temporary) / 'environment'
                    environment_file.write_text('EXISTING=value\n', encoding='utf-8')
                    with patch.dict(os.environ, {'BUILD_JOBS': selector, 'GITHUB_ENV': str(environment_file)}), \
                            patch.object(sys, 'path', list(sys.path)), \
                            self.assertRaisesRegex(ValueError, 'compile jobs must be auto or a positive integer'):
                        exec(compile(script, 'candidate-' + job, 'exec'), {})
                    self.assertEqual(environment_file.read_text(encoding='utf-8'), 'EXISTING=value\n')

    def test_candidate_descendant_cmake_build_uses_numeric_capacity(self):
        scripts = self.candidate_capacity_scripts()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; source.mkdir(); build = root / 'build'
            (source / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.21)\nproject(capacity NONE)\n'
                'add_custom_target(probe ALL COMMAND ${CMAKE_COMMAND} -E touch "${CMAKE_BINARY_DIR}/built")\n')
            environment = dict(os.environ, CMAKE_BUILD_PARALLEL_LEVEL='1')
            subprocess.run(['cmake', '-G', 'Ninja', '-S', str(source), '-B', str(build)],
                           env=environment, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            rejected = subprocess.run(['cmake', '--build', str(build)],
                                      env=dict(environment, CMAKE_BUILD_PARALLEL_LEVEL='auto'),
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('CMAKE_BUILD_PARALLEL_LEVEL', rejected.stdout)
            self.assertIn("'auto'", rejected.stdout)
            self.assertFalse((build / 'built').exists())
            for job, script in scripts.items():
                for selector in ('auto', '4'):
                    with self.subTest(job=job, selector=selector):
                        environment_file = root / 'environment'
                        environment_file.write_text('', encoding='utf-8')
                        with patch.dict(os.environ, {'BUILD_JOBS': selector, 'GITHUB_ENV': str(environment_file)}), \
                                patch.object(c, 'default_jobs', return_value=3), \
                                patch.object(sys, 'path', list(sys.path)):
                            exec(compile(script, 'candidate-' + job, 'exec'), {})
                        key, value = environment_file.read_text(encoding='utf-8').strip().split('=', 1)
                        subprocess.run(['cmake', '--build', str(build)], env=dict(environment, **{key: value}),
                                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        self.assertTrue((build / 'built').is_file())
                        (build / 'built').unlink()

    def test_auto_and_explicit_compile_limits(self):
        with patch.object(c, 'default_jobs', return_value=7) as automatic:
            for value in (None, '', 'auto'):
                self.assertEqual(c.compile_jobs(value), 7)
            for value in (1, '2', 9):
                self.assertEqual(c.compile_jobs(value), int(value))
            self.assertEqual(automatic.call_count, 3)
        for value in (0, '0', '-1', '1.5', 'many', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.compile_jobs(value)

    def test_memory_reserve_and_cpu_headroom_are_independent(self):
        self.assertEqual(c.select_jobs(16, c.MEMORY_PER_JOB * 3), 2)
        self.assertEqual(c.select_jobs(2, 32 * 1024**3), 1)
        self.assertEqual(c.select_jobs(64, None), 2)
        self.assertEqual(c.select_jobs(32, 0), 1)

    def test_default_uses_tightest_container_limits(self):
        with patch.object(c.sys, 'platform', 'linux'), patch.object(c, 'usable_cpus', return_value=32), \
             patch.object(c, 'available_memory', return_value=64*1024**3), \
             patch.object(c, 'linux_limits', return_value=([4,2],[c.MEMORY_PER_JOB*2])):
            self.assertEqual(c.default_jobs(),1)
        with patch.object(c, 'usable_cpus', side_effect=ValueError('unavailable')):
            self.assertEqual(c.default_jobs(),1)

    def test_automatic_test_workers_observe_resources_and_four_worker_cap(self):
        for cpus, memory, expected in [(16, 32 * 1024**3, 4),
                                      (3, 32 * 1024**3, 2),
                                      (16, c.MEMORY_PER_JOB * 3, 2),
                                      (16, None, 2), (1, 0, 1)]:
            with self.subTest(cpus=cpus, memory=memory), \
                    patch.object(c.sys, 'platform', 'linux'), \
                    patch.object(c, 'usable_cpus', return_value=cpus), \
                    patch.object(c, 'available_memory', return_value=memory), \
                    patch.object(c, 'linux_limits', return_value=([], [])):
                self.assertEqual(c.default_test_jobs(), expected)
        with patch.object(c, 'usable_cpus', side_effect=OSError('unavailable')):
            self.assertEqual(c.default_test_jobs(), 1)

    def test_parent_cgroup_memory_and_quota_are_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';(proc/'self').mkdir(parents=True)
            group=root/'group';leaf=group/'child';leaf.mkdir(parents=True)
            (proc/'self/cgroup').write_text('0::/child\n')
            (proc/'self/mountinfo').write_text('1 2 0:1 / '+str(group)+' rw - cgroup2 cgroup rw\n')
            for directory,cpu,memory,current in ((group,'200000 100000','1000','800'),(leaf,'max 100000','max','0')):
                (directory/'cpu.max').write_text(cpu);(directory/'memory.max').write_text(memory);(directory/'memory.current').write_text(current)
            cpus,memory=c.linux_limits(proc)
            self.assertEqual(cpus,[2]);self.assertEqual(memory,[200])
            (group/'memory.current').unlink()
            with self.assertRaises(ValueError):c.linux_limits(proc)

    def test_explicit_scope_flags_then_shared_then_environment_then_defaults(self):
        args=argparse.Namespace(build_jobs=None,test_jobs=None,jobs=None)
        with patch.dict(b.os.environ,{},clear=True),patch.object(b,'default_jobs',return_value=7), \
                patch.object(c,'default_test_jobs',return_value=4) as automatic_tests:
            self.assertEqual(b.job_limits(args),(7,4))
            with patch.dict(b.os.environ,{'CMAKE_BUILD_PARALLEL_LEVEL':'5','CTEST_PARALLEL_LEVEL':'3'}):
                self.assertEqual(b.job_limits(args),(5,3))
                with patch.dict(b.os.environ,{'CMAKE_BUILD_PARALLEL_LEVEL':'auto'}), patch.object(c,'default_jobs',return_value=9):
                    self.assertEqual(b.job_limits(args),(9,3))
                args.jobs=4;self.assertEqual(b.job_limits(args),(4,4))
                args.build_jobs=8;args.test_jobs=1;self.assertEqual(b.job_limits(args),(8,1))
                self.assertEqual(automatic_tests.call_count,1)
            args.jobs=None;args.test_jobs=None
            self.assertEqual(b.job_limits(args),(8,4))


if __name__=='__main__':unittest.main()
