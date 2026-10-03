import argparse
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_capacity as c
import build as b


class Capacity(unittest.TestCase):
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
        with patch.dict(b.os.environ,{},clear=True),patch.object(b,'default_jobs',return_value=7):
            self.assertEqual(b.job_limits(args),(7,2))
            with patch.dict(b.os.environ,{'CMAKE_BUILD_PARALLEL_LEVEL':'5','CTEST_PARALLEL_LEVEL':'3'}):
                self.assertEqual(b.job_limits(args),(5,3))
                with patch.dict(b.os.environ,{'CMAKE_BUILD_PARALLEL_LEVEL':'auto'}), patch.object(c,'default_jobs',return_value=9):
                    self.assertEqual(b.job_limits(args),(9,3))
                args.jobs=4;self.assertEqual(b.job_limits(args),(4,4))
                args.build_jobs=8;args.test_jobs=1;self.assertEqual(b.job_limits(args),(8,1))


if __name__=='__main__':unittest.main()
