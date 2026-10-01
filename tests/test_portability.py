from pathlib import Path
import shutil
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import verify_abi
import stage_runtime


@unittest.skipUnless(platform.system() == 'Linux' and shutil.which('cc') and shutil.which('readelf'), 'native Linux ELF toolchain required')
class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.processor = {'arm64': 'aarch64', 'AMD64': 'x86_64'}.get(platform.machine(), platform.machine())
        (self.root / 'main.c').write_text('int main(void) { return 0; }\n')
        subprocess.run(['cc', str(self.root / 'main.c'), '-o', str(self.root / 'application')], check=True)

    def tearDown(self): self.temp.cleanup()

    def test_real_native_elf_inspection(self):
        report = verify_abi.audit(self.root / 'application', processor=self.processor)
        self.assertEqual(report['status'], 'passed')
        self.assertIn('application', report['files'])

    def test_above_runtime_floor_rejected(self):
        with self.assertRaisesRegex(ValueError, 'above ceiling'):
            verify_abi.audit(self.root / 'application', processor=self.processor, ceilings={'GLIBC': '2.2.5'})

    def test_architecture_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'architecture'):
            verify_abi.audit(self.root / 'application', processor='aarch64' if self.processor == 'x86_64' else 'x86_64')

    def test_absolute_runtime_search_path_rejected(self):
        subprocess.run(['cc', str(self.root / 'main.c'), '-Wl,-rpath,/temporary/library', '-o', str(self.root / 'absolute')], check=True)
        with self.assertRaisesRegex(ValueError, 'relative'):
            verify_abi.audit(self.root / 'absolute', processor=self.processor)

    def test_non_elf_is_not_passing_coverage(self):
        with self.assertRaisesRegex(ValueError, 'no ELF'):
            verify_abi.audit(self.root / 'main.c')

    def test_missing_runtime_dependency_fails(self):
        info = verify_abi.inspect(self.root / 'application')
        info['needed'].append('libmissing.so.1')
        with patch('verify_abi.inspect', return_value=info):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                verify_abi.audit(self.root / 'application', processor=self.processor)

    def test_recursive_runtime_staging(self):
        libs = self.root / 'supplier'
        libs.mkdir()
        (libs / 'tiny.c').write_text('int value(void) { return 42; }\n')
        subprocess.run(['cc', '-shared', '-fPIC', str(libs / 'tiny.c'), '-Wl,-soname,libtiny.so.1', '-o', str(libs / 'libtiny.so.1')], check=True)
        (self.root / 'use.c').write_text('extern int value(void); int main(void) { return value()!=42; }\n')
        subprocess.run(['cc', str(self.root / 'use.c'), str(libs / 'libtiny.so.1'), '-o', str(self.root / 'use')], check=True)
        result = stage_runtime.stage([self.root / 'use'], [libs], self.root / 'private', processor=self.processor)
        self.assertEqual(set(result['files']), {'libtiny.so.1'})
        with self.assertRaisesRegex(ValueError, 'missing'):
            stage_runtime.stage([self.root / 'use'], [], self.root / 'missing', processor=self.processor)

    def linked_package(self, inherited=True, middle_path=False):
        package = self.root / 'package'
        binary, libraries = package / 'bin', package / 'lib' / 'runtime'
        binary.mkdir(parents=True)
        libraries.mkdir(parents=True)
        (self.root / 'leaf.c').write_text('int leaf(void) { return 42; }\n')
        (self.root / 'middle.c').write_text('extern int leaf(void); int middle(void) { return leaf(); }\n')
        (self.root / 'entry.c').write_text('extern int middle(void); int main(void) { return middle()!=42; }\n')
        subprocess.run(['cc', '-shared', '-fPIC', str(self.root / 'leaf.c'),
                        '-Wl,-soname,libleaf.so.1', '-o', str(libraries / 'libleaf.so.1')], check=True)
        args = ['cc', '-shared', '-fPIC', str(self.root / 'middle.c'), str(libraries / 'libleaf.so.1'),
                '-Wl,-soname,libmiddle.so.1', '-o', str(libraries / 'libmiddle.so.1')]
        if middle_path: args += ['-Wl,-rpath,$ORIGIN']
        subprocess.run(args, check=True)
        subprocess.run(['cc', str(self.root / 'entry.c'), str(libraries / 'libmiddle.so.1'),
                        '-Wl,-rpath-link,' + str(libraries), '-Wl,-rpath,$ORIGIN/../lib/runtime',
                        '-Wl,--disable-new-dtags' if inherited else '-Wl,--enable-new-dtags',
                        '-o', str(binary / 'application')], check=True)
        return package, binary, libraries

    def test_inherited_rpath_resolves_indirect_private_library(self):
        package, binary, libraries = self.linked_package()
        report = verify_abi.audit(package, processor=self.processor)
        self.assertEqual(len(report['resolution']), 2)
        self.assertEqual(report['runtime_resolution'], 'passed')
        subprocess.run([str(binary / 'application')], check=True,
                       env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, cwd=self.root)

    def test_runpath_is_not_inherited(self):
        package, _, _ = self.linked_package(inherited=False)
        with self.assertRaisesRegex(ValueError, 'loader cannot resolve libleaf'):
            verify_abi.audit(package, processor=self.processor)

    def test_each_library_own_runpath_can_resolve_closure(self):
        package, binary, _ = self.linked_package(inherited=False, middle_path=True)
        self.assertEqual(verify_abi.audit(package, processor=self.processor)['runtime_resolution'], 'passed')
        subprocess.run([str(binary / 'application')], check=True,
                       env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, cwd=self.root)

    def test_provider_in_unsearched_directory_rejected(self):
        package, _, libraries = self.linked_package()
        wrong = package / 'wrong'
        wrong.mkdir()
        (libraries / 'libleaf.so.1').rename(wrong / 'libleaf.so.1')
        with self.assertRaisesRegex(ValueError, 'loader cannot resolve libleaf'):
            verify_abi.audit(package, processor=self.processor)

    def test_multiple_searched_providers_rejected(self):
        package, binary, libraries = self.linked_package()
        other = package / 'other'
        other.mkdir()
        shutil.copyfile(libraries / 'libmiddle.so.1', other / 'libmiddle.so.1')
        subprocess.run(['cc', str(self.root / 'entry.c'), str(libraries / 'libmiddle.so.1'),
                        '-Wl,-rpath-link,' + str(libraries),
                        '-Wl,-rpath,$ORIGIN/../lib/runtime:$ORIGIN/../other',
                        '-Wl,--disable-new-dtags', '-o', str(binary / 'application')], check=True)
        with self.assertRaisesRegex(ValueError, 'ambiguous runtime loader'):
            verify_abi.audit(package, processor=self.processor)

    def test_native_staging_records_newer_floor_without_claiming_bookworm(self):
        libraries = self.root / 'supplier'
        libraries.mkdir()
        (self.root / 'leaf.c').write_text('int late(void) { return 42; }\n')
        (self.root / 'middle.c').write_text('extern int late(void); int value(void) { return late(); }\n')
        (self.root / 'versions.map').write_text('GLIBC_2.37 { global: late; local: *; };\n')
        subprocess.run(['cc', '-shared', '-fPIC', str(self.root / 'leaf.c'),
                        '-Wl,--version-script=' + str(self.root / 'versions.map'),
                        '-Wl,-soname,libleaf.so.1', '-o', str(libraries / 'libleaf.so.1')], check=True)
        subprocess.run(['cc', '-shared', '-fPIC', str(self.root / 'middle.c'),
                        str(libraries / 'libleaf.so.1'), '-Wl,-soname,libmiddle.so.1',
                        '-o', str(libraries / 'libmiddle.so.1')], check=True)
        self.assertEqual(verify_abi.inspect(libraries / 'libmiddle.so.1')['requirements']['GLIBC'], '2.37')
        # Include the dependent object itself in the copied closure, so staging
        # audits its real imported requirement rather than only its provider.
        (self.root / 'use.c').write_text('extern int value(void); int main(void) { return value()!=42; }\n')
        subprocess.run(['cc', str(self.root / 'use.c'), str(libraries / 'libmiddle.so.1'),
                        '-Wl,-rpath-link,' + str(libraries), '-o', str(self.root / 'use')], check=True)
        with self.assertRaisesRegex(ValueError, 'above ceiling'):
            stage_runtime.stage([self.root / 'use'], [libraries], self.root / 'fixed-package',
                                processor=self.processor)
        self.assertFalse((self.root / 'fixed-package').exists())
        report = stage_runtime.stage([self.root / 'use'], [libraries], self.root / 'native',
                                     processor=self.processor, audit_baseline=False)
        self.assertEqual(report['abi']['ceilings']['GLIBC'], '2.37')
        self.assertEqual(report['baseline_qualification'], 'native-observed-requirements-only')
        self.assertEqual(report['runtime_resolution'], 'requires_final_package_audit')



class WindowsInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def sample(self, name='application.exe', dependency='kernel32.dll', machine=0x8664, delayed=False):
        import struct
        data = bytearray(1024)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 60, 128)
        data[128:132] = b'PE\0\0'
        struct.pack_into('<HH', data, 132, machine, 1)
        struct.pack_into('<H', data, 148, 240)
        optional = 152
        struct.pack_into('<H', data, optional, 0x20b)
        struct.pack_into('<HH', data, optional + 40, 6, 0)
        struct.pack_into('<I', data, optional + 60, 512)
        struct.pack_into('<I', data, optional + 108, 16)
        index = 13 if delayed else 1
        width = 32 if delayed else 20
        struct.pack_into('<II', data, optional + 112 + index * 8, 4096, width * 2)
        section = optional + 240
        struct.pack_into('<IIII', data, section + 8, 512, 4096, 512, 512)
        if delayed: struct.pack_into('<II', data, 512, 1, 4224)
        else: struct.pack_into('<I', data, 524, 4224)
        encoded = dependency.encode() + b'\0'
        data[640:640 + len(encoded)] = encoded
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_pe_system_import(self):
        import verify_pe
        self.sample()
        self.assertEqual(verify_pe.audit(self.root)['status'], 'passed')

    def test_shared_runtime_not_assumed_os_library(self):
        import verify_pe
        self.sample(dependency='VCRUNTIME140.dll')
        with self.assertRaisesRegex(ValueError, 'static CRT'):
            verify_pe.audit(self.root)

    def test_delayed_missing_library_rejected(self):
        import verify_pe
        self.sample(dependency='optional-provider.dll', delayed=True)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            verify_pe.audit(self.root)

    def test_pe_wrong_architecture_rejected(self):
        import verify_pe
        self.sample(machine=0xaa64)
        with self.assertRaisesRegex(ValueError, 'architecture'):
            verify_pe.audit(self.root)

    def test_truncated_pe_rejected(self):
        import verify_pe
        path = self.sample()
        path.write_bytes(path.read_bytes()[:200])
        with self.assertRaisesRegex(ValueError, 'truncated'):
            verify_pe.audit(self.root)

if __name__ == '__main__': unittest.main()
