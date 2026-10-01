"""Real process-lifetime scenarios plus native launch ordering checks."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('process_tree', ROOT / 'tools/process_tree.py')
TREE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TREE)


@unittest.skipUnless(os.name in ('posix', 'nt'), 'requires a supplied native process supervisor')
class NativeProcessTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='process-owner-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stream = (self.root / 'console.log').open('wb')
        self.addCleanup(self.stream.close)

    def launch(self, body):
        owner = TREE.launch([sys.executable, '-B', '-c', body], self.root, self.stream)
        self.addCleanup(owner.close)
        return owner

    def test_complete_parent_and_joined_child_leave_stable_output(self):
        owner = self.launch("import subprocess,sys; subprocess.run([sys.executable,'-c','print(42)'],check=True);print('done')")
        self.assertEqual(owner.wait(timeout=10), 0)
        self.assertEqual(owner.finish(), 0)
        owner.close()
        self.assertIn(b'42', (self.root / 'console.log').read_bytes())

    def test_successful_parent_with_inherited_output_child_is_rejected_and_stopped(self):
        body = ("import subprocess,sys; subprocess.Popen([sys.executable,'-c',"
                "\"import time;time.sleep(0.5);print('late',flush=True);time.sleep(30)\"]);print('parent done')")
        owner = self.launch(body)
        self.assertEqual(owner.wait(timeout=10), 0)
        with self.assertRaisesRegex(TREE.ProcessTreeError, 'descendants outlived'):
            owner.finish()
        saved = (self.root / 'console.log').read_bytes()
        time.sleep(0.6)
        self.assertEqual((self.root / 'console.log').read_bytes(), saved)
        self.assertNotIn(b'late', saved)

    def test_termination_stops_parent_and_child_without_releasing_early(self):
        owner = self.launch("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);print('ready',flush=True);time.sleep(30)")
        deadline = time.monotonic() + 10
        while b'ready' not in (self.root / 'console.log').read_bytes():
            if time.monotonic() >= deadline:
                self.fail('command did not reach ready state')
            time.sleep(0.01)
        owner.terminate()
        self.assertIsNotNone(owner.poll())
        self.assertFalse(owner._live())
        owner.close()

    def test_finish_before_exit_is_not_completion(self):
        owner = self.launch('import time;time.sleep(30)')
        with self.assertRaisesRegex(TREE.ProcessTreeError, 'has not exited'):
            owner.finish()
        owner.terminate()

    @unittest.skipUnless(os.name == 'nt', 'native Job Object breakaway rejection is Windows-specific')
    def test_windows_child_cannot_break_out_of_its_job(self):
        owner = self.launch("import subprocess,sys\ntry:\n subprocess.Popen([sys.executable,'-c','pass'],creationflags=0x01000000)\nexcept OSError:\n print('breakaway denied')\nelse:\n raise SystemExit('breakaway incorrectly allowed')")
        self.assertEqual(owner.wait(timeout=10), 0)
        self.assertEqual(owner.finish(), 0)
        self.assertIn(b'breakaway denied', (self.root / 'console.log').read_bytes())


class WindowsLaunchOrdering(unittest.TestCase):
    def check_order(self, failure=None):
        events = []
        class Job:
            def __init__(self):events.append('job')
            def assign(self, process):
                events.append('assign')
                if failure == 'assign':raise TREE.ProcessTreeError('assignment rejected')
            def resume(self, process):
                events.append('resume')
                if failure in ('resume', 'cleanup'):raise TREE.ProcessTreeError('resume rejected')
            def terminate(self):
                events.append('terminate job')
                if failure == 'cleanup':raise TREE.ProcessTreeError('job termination rejected')
            def close(self):events.append('close job')
        process = mock.Mock()
        process.poll.return_value = None
        process.kill.side_effect = lambda: events.append('kill suspended child')
        process.wait.side_effect = lambda **kw: events.append('wait child')
        def create(*args, **kwargs):
            self.assertEqual(kwargs['creationflags'], 0x4)
            self.assertFalse(kwargs['start_new_session'])
            events.append('create suspended')
            return process
        with mock.patch.object(TREE.os, 'name', 'nt'), mock.patch.object(TREE, '_WindowsJob', Job), \
                mock.patch.object(TREE.subprocess, 'Popen', side_effect=create):
            if failure:
                with self.assertRaises(TREE.ProcessTreeError):
                    TREE.launch(['program'], '.', None)
            else:
                owner = TREE.launch(['program'], '.', None)
                self.assertIs(owner.process, process)
        return events

    def test_child_cannot_execute_before_job_assignment(self):
        self.assertEqual(self.check_order(), ['job', 'create suspended', 'assign', 'resume'])

    def test_assignment_failure_never_resumes_and_joins_suspended_process(self):
        events = self.check_order('assign')
        self.assertNotIn('resume', events)
        self.assertEqual(events[-3:], ['kill suspended child', 'wait child', 'close job'])

    def test_resume_failure_still_closes_job_and_joins_child(self):
        events = self.check_order('resume')
        self.assertEqual(events[-4:], ['terminate job', 'kill suspended child', 'wait child', 'close job'])

    def test_failed_cleanup_still_attempts_child_stop_join_and_job_close(self):
        events = self.check_order('cleanup')
        self.assertEqual(events[-3:], ['kill suspended child', 'wait child', 'close job'])


@unittest.skipUnless(sys.platform.startswith('linux'), 'requires private Linux child-subreaper')
class LinuxSubreaper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nested-owner-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / 'console.log'
        self.stream = self.log.open('wb')
        self.addCleanup(self.stream.close)

    def launch(self, body):
        owner = TREE.launch([sys.executable, '-B', '-c', body], self.root, self.stream)
        self.addCleanup(owner.close)
        return owner

    def wait_file(self, name):
        path = self.root / name
        until = time.monotonic() + 10
        while not path.exists() or not path.read_text():
            if time.monotonic() > until:
                self.fail('nested command did not become ready')
            time.sleep(0.01)
        return int(path.read_text())

    def assert_gone(self, *pids):
        for pid in pids:
            self.assertFalse(Path('/proc', str(pid)).exists(), 'descendant was not reaped: ' + str(pid))

    def test_parent_success_with_new_session_writer_is_rejected_and_reaped(self):
        writer = "import os,time;from pathlib import Path;Path('writer.pid').write_text(str(os.getpid()));time.sleep(1);print('late');time.sleep(30)"
        body = ("import subprocess,sys,time;from pathlib import Path;"
                "subprocess.Popen([sys.executable,'-B','-c'," + repr(writer) + "],start_new_session=True)\n"
                "while not Path('writer.pid').exists():time.sleep(0.01)\n")
        owner = self.launch(body)
        pid = self.wait_file('writer.pid')
        self.assertEqual(owner.wait(timeout=10), 0)
        with self.assertRaisesRegex(TREE.ProcessTreeError, 'descendants outlived'):
            owner.finish()
        self.assert_gone(pid)
        self.assertNotIn(b'late', self.log.read_bytes())

    def test_timeout_reaps_nested_supervisor_and_new_session_descendants(self):
        writer = "import os,time;from pathlib import Path;Path('writer.pid').write_text(str(os.getpid()));time.sleep(30)"
        inner = ("import os,subprocess,sys,time;from pathlib import Path;Path('inner.pid').write_text(str(os.getpid()));"
                 "subprocess.Popen([sys.executable,'-B','-c'," + repr(writer) + "],start_new_session=True);time.sleep(30)")
        body = ("import sys,time;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT/'tools')) + ");"
                "import process_tree;owner=process_tree.launch([sys.executable,'-B','-c'," + repr(inner) + "],'.',sys.stdout);"
                "Path('supervisor.pid').write_text(str(owner.process.pid));time.sleep(30)")
        owner = self.launch(body)
        pids = [self.wait_file(name) for name in ('writer.pid', 'inner.pid', 'supervisor.pid')]
        owner.terminate(timeout=10)
        self.assertIsNotNone(owner.finish())
        self.assert_gone(*pids)

    def test_actual_coverage_timeout_stops_detached_session_writer(self):
        spec = importlib.util.spec_from_file_location('supervisor_coverage', ROOT/'tools/coverage.py')
        coverage = importlib.util.module_from_spec(spec);spec.loader.exec_module(coverage)
        writer = "import os,time;from pathlib import Path;Path('writer.pid').write_text(str(os.getpid()));time.sleep(2);print('late');time.sleep(30)"
        body = ("import subprocess,sys,time;subprocess.Popen([sys.executable,'-B','-c'," + repr(writer) +
                "],start_new_session=True);time.sleep(30)")
        plan = coverage.freeze({'schema_version':1,'mode':'diagnostic',
            'subject':{key:'a'*64 for key in ('source_sha256','inventory_sha256','configuration_sha256')},
            'inputs':{},'checks':[{'id':'nested','scope':'fixture','target':'linux-x86_64','environment':'fixture',
                'backend':'core','required':True,'argv':['{python}','-B','-c',body],
                'timeout_seconds':0.6,'warning_seconds':0.3,'expected_tests':[]}]})
        result = coverage.run_case(plan,'nested',self.root,self.root/'evidence','nested-run',1)
        self.assertEqual(result['status'],'incomplete')
        self.assert_gone(self.wait_file('writer.pid'))
        saved = (self.root/'evidence/console.log').read_bytes()
        time.sleep(0.1)
        self.assertEqual((self.root/'evidence/console.log').read_bytes(),saved)
        self.assertNotIn(b'late',saved)

    def test_subreaper_setting_is_private_to_supervisor(self):
        import ctypes
        api = ctypes.CDLL(None)
        before, after = ctypes.c_int(), ctypes.c_int()
        self.assertEqual(api.prctl(37, ctypes.byref(before), 0, 0, 0), 0)
        owner = self.launch('pass');owner.wait(timeout=10);owner.finish()
        self.assertEqual(api.prctl(37, ctypes.byref(after), 0, 0, 0), 0)
        self.assertEqual(before.value, after.value)

    def test_caller_exit_requests_private_supervisor_cleanup(self):
        writer = "import os,time;from pathlib import Path;Path('writer.pid').write_text(str(os.getpid()));time.sleep(30)"
        caller = ("import os,sys,time;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT/'tools')) + ");"
                  "import process_tree;owner=process_tree.launch([sys.executable,'-B','-c'," + repr(writer) + "],'.',sys.stdout)\n"
                  "while not Path('writer.pid').exists():time.sleep(0.01)\n"
                  "Path('supervisor.pid').write_text(str(owner.process.pid));os._exit(0)")
        body = ("import subprocess,sys,time;from pathlib import Path;subprocess.run([sys.executable,'-B','-c'," + repr(caller) + "],check=True)\n"
                "deadline=time.monotonic()+5\n"
                "while any(Path('/proc',Path(name).read_text()).exists() for name in ('writer.pid','supervisor.pid')):\n"
                " if time.monotonic()>deadline:raise RuntimeError('caller exit left writer alive')\n"
                " time.sleep(0.01)\n")
        owner=self.launch(body)
        self.assertEqual(owner.wait(timeout=10),0)
        # The outer owner also reaps any already-exited adopted supervisor.
        owner.finish()
        self.assert_gone(self.wait_file('writer.pid'),self.wait_file('supervisor.pid'))

    def test_missing_command_is_a_failed_launch_with_confirmed_cleanup(self):
        owner = TREE.launch([str(self.root/'absent-program')], self.root, self.stream)
        self.addCleanup(owner.close)
        self.assertEqual(owner.wait(timeout=10),125)
        with self.assertRaisesRegex(TREE.ProcessTreeError,'supervisor launch failed'):
            owner.finish()
        self.assertFalse(owner._live())

    def test_large_launch_diagnostic_cannot_block_completion_pipe(self):
        owner = TREE.launch([str(self.root/('é'*2000))],self.root,self.stream)
        self.addCleanup(owner.close)
        self.assertEqual(owner.wait(timeout=10),125)
        with self.assertRaisesRegex(TREE.ProcessTreeError,'bounded diagnostic'):
            owner.finish()
        self.assertFalse(owner._live())


class SupervisorBoundary(unittest.TestCase):
    def test_other_posix_platforms_do_not_fall_back_to_escaping_groups(self):
        with mock.patch.object(TREE.os,'name','posix'), mock.patch.object(TREE.sys,'platform','darwin'), \
                mock.patch.object(TREE.subprocess,'Popen') as child:
            with self.assertRaisesRegex(TREE.ProcessTreeError,'no qualified process supervisor'):
                TREE.launch(['program'],'.',None)
            child.assert_not_called()

    def test_missing_completion_receipt_remains_uncertain_on_repeated_observation(self):
        incoming,outgoing=os.pipe();os.close(outgoing)
        process=mock.Mock(returncode=0);process.poll.return_value=0
        proxy=TREE._LinuxProcess(process,incoming,['program'])
        for _ in range(2):
            with self.assertRaisesRegex(TREE.ProcessTreeError,'completion uncertain'):
                proxy.poll()


if __name__ == '__main__':
    unittest.main()
