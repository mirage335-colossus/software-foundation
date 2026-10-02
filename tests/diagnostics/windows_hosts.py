"""Opt-in installed Windows host probes; never ordinary unit-test discovery."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import process_tree
import windows_graphics
import windows_toolchain


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def executable_identity(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('installed host executable is not a file')
    return {'path': str(path), 'sha256': digest(path)}


def probe_identity(path):
    windows_toolchain.pe_identity(path)
    return dict(executable_identity(path), format='PE32+', machine='x86_64')


def compiler_identity(compiler):
    compiler = Path(compiler).resolve(strict=True)
    linker = compiler.with_name('link.exe').resolve(strict=True)
    selected = shutil.which('link.exe')
    if selected is None or Path(selected).resolve(strict=True) != linker:
        raise ValueError('selected linker differs from the compiler directory; host input is ambiguous')
    return {'compiler': executable_identity(compiler), 'linker': executable_identity(linker)}


@contextmanager
def workspace(cleanup_error):
    # A cleanup error must not let TemporaryDirectory erase an uncertain writer.
    directory = Path(tempfile.mkdtemp(prefix='windows-host-probe-')).resolve()
    safe = True
    try:
        yield directory
    except cleanup_error:
        safe = False
        print(json.dumps({'retained_workspace': str(directory), 'writers_stopped': False}), flush=True)
        raise
    except BaseException:
        # Ordinary command/startup failures have already joined their owner. Keep
        # only bounded named excerpts in the outer, retained diagnostic console.
        for name in ('compile.log', 'firefox.log'):
            path = directory / name
            if not path.exists():
                continue
            try:
                with path.open('rb') as stream:
                    raw = stream.read(16385)
                print(json.dumps({'diagnostic_log': name, 'text': raw[:16384].decode('utf-8', errors='replace'),
                                  'truncated': len(raw) > 16384}), flush=True)
            except OSError as error:
                print(json.dumps({'diagnostic_log': name, 'read_error': error.errno}), flush=True)
        raise
    finally:
        if safe:
            shutil.rmtree(directory)


class WindowsHosts(unittest.TestCase):
    def setUp(self):
        if platform.system() != 'Windows':
            raise RuntimeError('windows_hosts requires its native Windows host')

    def test_compiler_probe_completes_with_all_descendants_joined(self):
        compiler = shutil.which('cl.exe')
        self.assertIsNotNone(compiler, 'selected installed MSVC cl.exe is required')
        identity = compiler_identity(compiler)
        strict = os.environ.get('FOUNDATION_MSVC_STRICT_COMPLETION', '0')
        if strict not in ('0', '1'):
            raise ValueError('FOUNDATION_MSVC_STRICT_COMPLETION must be 0 or 1')
        print(json.dumps(dict(identity, source_sha256=digest(ROOT / 'tools/windows_gl_probe.cpp'),
                              strict_completion=strict == '1')), flush=True)
        with workspace(process_tree.ProcessTreeError) as directory:
            executable, receipt = windows_graphics.compile_probe(directory, directory / 'compile.log',
                                                                 environment=dict(os.environ), strict_completion=strict == '1')
            output_identity = probe_identity(executable)
            self.assertEqual(receipt['source_sha256'], digest(ROOT / 'tools/windows_gl_probe.cpp'))
            self.assertEqual(identity, compiler_identity(compiler), 'compiler/linker changed during the native probe')
            print(json.dumps({'compile': receipt, 'output': output_identity}), flush=True)
            # No driver download or WGL execution is needed to reproduce the compiler lifetime.

    def test_firefox_session_close_releases_profile_immediately(self):
        executable = Path('C:/Program Files/Mozilla Firefox/firefox.exe')
        identity = executable_identity(executable)  # Same installed path as native certification.
        print(json.dumps({'firefox': identity}), flush=True)
        spec = importlib.util.spec_from_file_location('diagnostic_browser', ROOT / 'gui/tests/browser_test.py')
        browser_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(browser_module)
        with workspace(browser_module.BrowserCleanupError) as directory:
            browser = browser_module.Browser(str(executable), directory)
            try:
                self.assertEqual(browser.capabilities['browserName'].lower(), 'firefox')
                self.assertTrue(browser.capabilities['browserVersion'])
                print(json.dumps({'browser_name': browser.capabilities['browserName'],
                                  'browser_version': browser.capabilities['browserVersion']}), flush=True)
                browser.command('WebDriver:Navigate', {'url': 'about:blank'})
                self.assertEqual(browser.script('return document.location.href;'), 'about:blank')
                self.assertEqual(browser.script('document.body.textContent="native host probe"; return document.body.textContent;'),
                                 'native host probe')
            finally:
                browser.close()
            self.assertEqual(identity, executable_identity(executable), 'Firefox changed during the native probe')
            released = directory / 'released-profile'
            browser.profile.rename(released)
            shutil.rmtree(released)
            self.assertFalse(browser.profile.exists())
            self.assertFalse(released.exists())
            # Whole workspace removal additionally exercises the now-closed browser log.
