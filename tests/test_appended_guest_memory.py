"""Exercise the real appended guest memory primitives with guarded native fixtures.

Run against the canonical SDK source by default. To check a private exact input,
set FOUNDATION_GUEST_MEMORY_SOURCE to that source's absolute path. This fixture
does not alter the retained guest compiler or its source pins.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'sdk/appended/guest.c'


def _source_path():
    value = os.environ.get('FOUNDATION_GUEST_MEMORY_SOURCE')
    path = Path(value).absolute() if value else DEFAULT_SOURCE
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('guest memory source must be a regular file: ' + str(path))
    return path


HARNESS = r'''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

/* The included SDK owns the functions under test; renaming keeps this native
   fixture from replacing libc functions used by the compiler/runtime. */
#define memcpy foundation_test_memcpy
#define memmove foundation_test_memmove
#define memset foundation_test_memset
#define memcmp foundation_test_memcmp
#define __builtin_wasm_memory_size(index) 1u
#include "__GUEST_SOURCE__"
#undef memcpy
#undef memmove
#undef memset
#undef memcmp
#undef __builtin_wasm_memory_size

void __wasm_call_ctors(void) {}
uint32_t foundation_kernel_call_v1(uint32_t request, uint32_t bytes,
                                   uint32_t reply, uint32_t capacity) {
    (void)request; (void)bytes; (void)reply; (void)capacity; return 0;
}

static unsigned char pattern(size_t i) {
    return (unsigned char)(i * 37u + i / 7u + 11u);
}
static int equal_bytes(const unsigned char *left, const unsigned char *right,
                       size_t bytes) {
    for (size_t i = 0; i < bytes; ++i) if (left[i] != right[i]) return 0;
    return 1;
}
static int fail(const char *operation, size_t bytes, int source_align,
                int destination_align) {
    fprintf(stderr, "%s mismatch: bytes=%zu source_align=%d destination_align=%d\n",
            operation, bytes, source_align, destination_align);
    return 1;
}

static int test_copy(void) {
    static const size_t extra[] = {255, 256, 257, 511, 512, 1023};
    unsigned char source[2048], actual[2048], expected[2048];
    for (size_t n = 0; n <= 128; ++n) {
        for (int sa = 0; sa != 8; ++sa) for (int da = 0; da != 8; ++da) {
            for (size_t i = 0; i != sizeof source; ++i) {
                source[i] = pattern(i); actual[i] = expected[i] = 0xa7;
            }
            size_t sp = 256u + (size_t)sa, dp = 256u + (size_t)da;
            for (size_t i = 0; i != n; ++i) expected[dp + i] = source[sp + i];
            if (foundation_test_memcpy(actual + dp, source + sp, n) != actual + dp ||
                !equal_bytes(actual, expected, sizeof actual)) return fail("memcpy", n, sa, da);
        }
    }
    for (size_t k = 0; k != sizeof extra / sizeof extra[0]; ++k) {
        size_t n = extra[k];
        for (int sa = 0; sa != 8; ++sa) for (int da = 0; da != 8; ++da) {
            for (size_t i = 0; i != sizeof source; ++i) {
                source[i] = pattern(i); actual[i] = expected[i] = 0xa7;
            }
            size_t sp = 256u + (size_t)sa, dp = 256u + (size_t)da;
            for (size_t i = 0; i != n; ++i) expected[dp + i] = source[sp + i];
            if (foundation_test_memcpy(actual + dp, source + sp, n) != actual + dp ||
                !equal_bytes(actual, expected, sizeof actual)) return fail("memcpy", n, sa, da);
        }
    }
    /* End exactly at the object boundary, including the zero-byte case. */
    for (size_t n = 0; n <= 128; ++n) {
        for (size_t i = 0; i != sizeof actual; ++i) {
            source[i] = pattern(i); actual[i] = expected[i] = 0x5c;
        }
        size_t dp = sizeof actual - n;
        for (size_t i = 0; i != n; ++i) expected[dp + i] = source[i];
        if (foundation_test_memcpy(actual + dp, source, n) != actual + dp ||
            !equal_bytes(actual, expected, sizeof actual)) return fail("memcpy-tail", n, 0, 0);
    }
    return 0;
}

static int test_move(void) {
    static const size_t extra[] = {255, 256, 511};
    unsigned char actual[2048], expected[2048], snapshot[512];
    for (size_t pass = 0; pass != 2; ++pass) {
        size_t count = pass ? sizeof extra / sizeof extra[0] : 129;
        for (size_t k = 0; k != count; ++k) {
            size_t n = pass ? extra[k] : k;
            for (int align = 0; align != 8; ++align) for (int delta = -16; delta <= 16; ++delta) {
                for (size_t i = 0; i != sizeof actual; ++i)
                    actual[i] = expected[i] = pattern(i);
                size_t sp = 512u + (size_t)align;
                size_t dp = (size_t)((int)sp + delta);
                for (size_t i = 0; i != n; ++i) snapshot[i] = actual[sp + i];
                for (size_t i = 0; i != n; ++i) expected[dp + i] = snapshot[i];
                if (foundation_test_memmove(actual + dp, actual + sp, n) != actual + dp ||
                    !equal_bytes(actual, expected, sizeof actual))
                    return fail("memmove", n, align, delta);
            }
        }
    }
    /* Exercise ranges touching both object boundaries and exact self-moves. */
    for (size_t n = 0; n <= 128; ++n) {
        for (size_t i = 0; i != sizeof actual; ++i)
            actual[i] = expected[i] = pattern(i);
        for (size_t i = 0; i != n; ++i) expected[sizeof expected - n + i] = expected[i];
        if (foundation_test_memmove(actual + sizeof actual - n, actual, n) != actual + sizeof actual - n ||
            !equal_bytes(actual, expected, sizeof actual)) return fail("memmove-tail", n, 0, 0);
        if (foundation_test_memmove(actual + 64, actual + 64, n) != actual + 64)
            return fail("memmove-self-return", n, 0, 0);
    }
    return 0;
}

static int test_set(void) {
    static const size_t extra[] = {255, 256, 257, 511, 1023};
    static const int values[] = {0, 1, 0x80, 0xff, -1, 0x100, 0x12345678, INT32_MIN, INT32_MAX};
    unsigned char actual[2048], expected[2048];
    for (size_t pass = 0; pass != 2; ++pass) {
        size_t count = pass ? sizeof extra / sizeof extra[0] : 129;
        for (size_t k = 0; k != count; ++k) {
            size_t n = pass ? extra[k] : k;
            for (int align = 0; align != 8; ++align) for (size_t v = 0; v != sizeof values / sizeof values[0]; ++v) {
                for (size_t i = 0; i != sizeof actual; ++i) actual[i] = expected[i] = 0xa3;
                size_t dp = 256u + (size_t)align;
                for (size_t i = 0; i != n; ++i) expected[dp + i] = (unsigned char)values[v];
                if (foundation_test_memset(actual + dp, values[v], n) != actual + dp ||
                    !equal_bytes(actual, expected, sizeof actual)) return fail("memset", n, values[v], align);
            }
        }
    }
    for (size_t n = 0; n <= 128; ++n) {
        for (size_t i = 0; i != sizeof actual; ++i) actual[i] = expected[i] = 0x39;
        size_t dp = sizeof actual - n;
        for (size_t i = 0; i != n; ++i) expected[dp + i] = 0x80;
        if (foundation_test_memset(actual + dp, 0x180, n) != actual + dp ||
            !equal_bytes(actual, expected, sizeof actual)) return fail("memset-tail", n, 0x180, 0);
    }
    return 0;
}

int main(void) {
    if (test_copy() || test_move() || test_set()) return 1;
    puts("guest memory primitives passed: exhaustive small lengths/alignments, overlap directions, guards, tails, return pointers, and fill truncation");
    return 0;
}
'''


class AppendedGuestMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('cc')
        if not compiler:
            raise unittest.SkipTest('native C compiler (cc) is unavailable')
        cls.source = _source_path()
        cls.source_sha256 = hashlib.sha256(cls.source.read_bytes()).hexdigest()
        cls.temporary = tempfile.TemporaryDirectory(prefix='foundation-guest-memory-')
        cls.addClassCleanup(cls.temporary.cleanup)
        work = Path(cls.temporary.name)
        harness = work / 'guest_memory_fixture.c'
        cls.binary = work / 'guest_memory_fixture'
        include_path = str(cls.source).replace('\\', '\\\\').replace('"', '\\"')
        harness.write_text(HARNESS.replace('__GUEST_SOURCE__', include_path), encoding='utf-8')
        command = [compiler, '-std=c11', '-O2', '-fno-builtin', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   '-I', str(ROOT / 'include'), '-idirafter', str(ROOT / 'sdk/appended/include'),
                   str(harness), '-o', str(cls.binary)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('native guest-memory fixture compile exceeded 30 seconds') from error
        if result.returncode:
            raise RuntimeError('native guest-memory fixture compile failed:\n' + result.stdout + result.stderr)
        if len(result.stdout) + len(result.stderr) > 1024 * 1024:
            raise RuntimeError('native guest-memory fixture compiler output exceeded 1 MiB')

    def test_real_guest_memory_functions(self):
        environment = os.environ.copy()
        environment['ASAN_OPTIONS'] = 'abort_on_error=1:detect_leaks=0'
        environment['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
        try:
            result = subprocess.run([str(self.binary)], capture_output=True, text=True,
                                    timeout=15, env=environment, check=False)
        except subprocess.TimeoutExpired as error:
            self.fail('native guest-memory fixture exceeded 15 seconds')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('guest memory primitives passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
