"""Initial-view and immutable gallery failure checks without a graphical service."""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import screenshots as S
from test_github_release import FakeGitHub


def png(width, height):
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    pixels = b''.join(b'\0' + bytes([row % 256, 50, 100]) * width for row in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def gallery(path):
    path.mkdir()
    value = {'schema_version': 1, 'kind': 'initial-view-gallery', 'source_commit': 'a' * 40,
             'state': 'fresh initial application', 'logical_viewport': [640, 480],
             'display_dpi': 96, 'display_scale': 1, 'images': {}, 'source_sha256': 'a' * 64,
             'run_id': '123', 'attempt': 1, 'terminal': 'fixture cells', 'host': {'target': 'linux-x86_64'},
             'distribution': {'ID': 'fixture'}, 'recipes': {'native': 'b' * 64, 'wasm': 'c' * 64},
             'origins': {name: {'origin': 'local', 'recipe': recipe} for name, recipe in
                         [('native', 'b' * 64), ('wasm', 'c' * 64)]},
             'dependencies': {name: {p: 'a' * 64 for p in S.delivery.store.names(recipe)}
                              for name, recipe in [('native', 'b' * 64), ('wasm', 'c' * 64)]},
             'gui_group': {'revision': 'a' * 40, 'source_tree': 'b' * 40, 'upstream': 'fixture',
                           'license': 'fixture', 'redistributable': False, 'archive_sha256': 'a' * 64,
                           'manifest_sha256': 'b' * 64},
             'binaries': {name: 'd' * 64 for name in {*(f'native/gui/foundation-gui-{n}' for n in S.TARGETS),
                          'wasm/gui/gui_web_wasm.js', 'wasm/gui/gui_web_wasm.wasm'}},
             'captures': {'browser': {'browserName': 'fixture', 'browserVersion': '1'}},
             'tools': {name: 'fixture version 1' for name in ('cmake', 'chromium', 'chromedriver', 'xterm')}}
    for name in S.BACKENDS:
        dimensions = [644, 500] if name == 'terminal' else [640, 480]
        p = path / (name + '.png'); p.write_bytes(png(*dimensions))
        value['images'][p.name] = {'sha256': S.archive.digest(p), 'size': p.stat().st_size, 'dimensions': dimensions}
        value['captures'][name] = {'width': dimensions[0], 'height': dimensions[1], 'colors': 20,
            'surface': 'browser-viewport' if name in ('hosted-web', 'wasm') else
                       'application-framebuffer' if name == 'framebuffer' else 'native-window'}
    for name, mode in [('hosted-web', 'hosted'), ('wasm', 'wasm')]:
        value['captures'][name].update(mode=mode, geometry=[{'key': 'generic', 'box': [0, 0, 20, 20]}])
    (path / 'screenshots.json').write_bytes(S.archive.encoded(value))
    (path / 'BUILD.txt').write_text('Fixture provenance\n', encoding='utf-8')
    seal(path)
    return value


def seal(path):
    (path / 'SHA256SUMS').write_text(''.join(S.archive.digest(path / name) + '  ' + name + '\n'
        for name in sorted(S.PUBLIC - {'SHA256SUMS'})), encoding='ascii')


class Clock:
    value = 0
    def monotonic(self): return self.value
    def sleep(self, amount): self.value += amount


@contextmanager
def running(*args, **kwargs):
    child = mock.Mock(); child.poll.return_value = None
    yield child


class ScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.directory = self.root / 'gallery'

    def test_all_seven_distinct_inventory_entries_and_source_are_required(self):
        expected = gallery(self.directory)
        self.assertEqual(S.verify_gallery(self.directory), expected)
        for name in S.BACKENDS:
            file = self.directory / (name + '.png'); data = file.read_bytes(); file.unlink()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'complete exact'):
                S.verify_gallery(self.directory)
            file.write_bytes(data)
        expected['source_commit'] = 'main'
        (self.directory / 'screenshots.json').write_bytes(S.archive.encoded(expected)); seal(self.directory)
        with self.assertRaisesRegex(ValueError, 'complete source commit'):
            S.verify_gallery(self.directory)

    def test_changed_image_and_unexpected_binary_block_publication(self):
        gallery(self.directory)
        (self.directory / 'fltk.png').write_bytes(png(640, 480) + b'changed')
        with self.assertRaisesRegex(ValueError, 'image bytes'):
            S.verify_gallery(self.directory)
        (self.directory / 'application.exe').write_bytes(b'not publishable here')
        with self.assertRaisesRegex(ValueError, 'complete exact'):
            S.verify_gallery(self.directory)

    def test_png_dimensions_and_metadata_reject_resized_viewports(self):
        value = gallery(self.directory)
        p = self.directory / 'sdl.png'; p.write_bytes(png(320, 240))
        value['images'][p.name] = {'sha256': S.archive.digest(p), 'size': p.stat().st_size, 'dimensions': [320, 240]}
        (self.directory / 'screenshots.json').write_bytes(S.archive.encoded(value)); seal(self.directory)
        with self.assertRaisesRegex(ValueError, 'viewport'):
            S.verify_gallery(self.directory)

    def test_missing_actual_capture_and_dependency_provenance_is_rejected(self):
        value = gallery(self.directory)
        for field in ('binaries', 'captures', 'dependencies', 'gui_group'):
            changed = copy.deepcopy(value); changed[field] = {}
            (self.directory / 'screenshots.json').write_bytes(S.archive.encoded(changed)); seal(self.directory)
            with self.subTest(field=field), self.assertRaises(ValueError):
                S.verify_gallery(self.directory)

    def test_capture_crash_is_not_an_image(self):
        child = mock.Mock(); child.poll.return_value = 7
        @contextmanager
        def dead(*args, **kwargs): yield child
        with mock.patch.object(S, 'windows', return_value=set()), mock.patch.object(S, 'process', dead):
            with self.assertRaisesRegex(RuntimeError, 'exited before'):
                S.capture_window(['unused'], 'fltk', self.root)
        self.assertFalse((self.root / 'fltk.png').exists())

    def test_blank_stable_window_does_not_pass(self):
        clock = Clock()
        def capture(*args, **kwargs): (self.root / 'fltk.png').write_bytes(b'blank')
        with mock.patch.object(S, 'windows', side_effect=lambda: {'old', 'new'} if clock.value else {'old'}), \
             mock.patch.object(S, 'process', running), mock.patch.object(S, 'command', side_effect=capture), \
             mock.patch.object(S, 'image_info', return_value=(640, 480, 1)), \
             mock.patch.object(S.time, 'monotonic', clock.monotonic), mock.patch.object(S.time, 'sleep', clock.sleep):
            with self.assertRaisesRegex(RuntimeError, 'stable painted'):
                S.capture_window(['unused'], 'fltk', self.root)
        self.assertGreaterEqual(clock.value, 30)

    def test_discovery_ignores_preexisting_and_ambiguous_windows(self):
        clock = Clock(); sightings = iter(({'old'}, {'old', 'one', 'two'})); commands = []
        def capture(argv, **kwargs):
            commands.append(argv); (self.root / 'sdl.png').write_bytes(b'actual capture')
        with mock.patch.object(S, 'windows', side_effect=lambda: next(sightings, {'old', 'new'})), \
             mock.patch.object(S, 'process', running), mock.patch.object(S, 'command', side_effect=capture), \
             mock.patch.object(S, 'image_info', return_value=(640, 480, 20)), \
             mock.patch.object(S.time, 'monotonic', clock.monotonic), mock.patch.object(S.time, 'sleep', clock.sleep):
            receipt = S.capture_window(['unused'], 'sdl', self.root)
        self.assertEqual(receipt['surface'], 'native-window')
        self.assertTrue(commands)
        self.assertEqual({argv[argv.index('-window') + 1] for argv in commands}, {'new'})

    def test_display_inspection_error_is_not_empty_display(self):
        result = mock.Mock(returncode=2, stdout='', stderr='private diagnostic')
        with mock.patch.object(S.subprocess, 'run', return_value=result), self.assertRaisesRegex(RuntimeError, 'native display'):
            S.windows()

    def test_owned_process_is_stopped_even_when_capture_raises(self):
        child = mock.Mock()
        with mock.patch.object(S.process_tree, 'launch', return_value=child):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                with S.process(['command'], self.root / 'log'):
                    raise RuntimeError('injected')
        child.terminate.assert_called_once(); child.close.assert_called_once()

    def test_plan_is_network_free_and_source_bound(self):
        gallery(self.directory); remote = FakeGitHub()
        result = S.publish('example/project', 'screenshots-1', self.directory, 'a' * 40, transport=remote)
        self.assertFalse(result['execute']); self.assertEqual(remote.calls, [])
        with self.assertRaisesRegex(ValueError, 'source differs'):
            S.publish('example/project', 'screenshots-1', self.directory, 'b' * 40, transport=remote)
        with self.assertRaisesRegex(ValueError, 'separate tag namespace'):
            S.publish('example/project', 'v1', self.directory, 'a' * 40, transport=remote)

    def test_publication_verifies_complete_bytes_and_never_latest(self):
        gallery(self.directory); remote = FakeGitHub()
        result = S.publish('example/project', 'screenshots-1', self.directory, 'a' * 40, execute=True, transport=remote)
        self.assertTrue(result['execute']); self.assertIsNone(remote.latest)
        release = remote.releases[0]
        self.assertFalse(release['draft']); self.assertTrue(release['prerelease'])
        self.assertEqual({x['name'] for x in release['assets']}, S.PUBLIC)
        self.assertEqual(len([x for x in remote.calls if x[0] == 'download']), len(S.PUBLIC))
        before = copy.deepcopy(remote.mutations)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            S.publish('example/project', 'screenshots-1', self.directory, 'a' * 40, execute=True, transport=remote)
        self.assertEqual(remote.mutations, before)

    def test_incomplete_upload_is_uncertain_and_never_finalizes(self):
        gallery(self.directory); remote = FakeGitHub(); remote.fail_upload = 'fltk.png'
        with self.assertRaises(S.delivery.DeliveryError) as caught:
            S.publish('example/project', 'screenshots-1', self.directory, 'a' * 40, execute=True, transport=remote)
        self.assertTrue(caught.exception.uncertain)
        self.assertTrue(remote.releases[0]['draft']); self.assertIsNone(remote.latest)

    def test_same_byte_asset_replacement_during_verification_fails(self):
        gallery(self.directory); remote = FakeGitHub()
        remote.change_download = lambda: remote.replace_asset('fltk.png')
        with self.assertRaises(S.delivery.DeliveryError) as caught:
            S.publish('example/project', 'screenshots-1', self.directory, 'a' * 40, execute=True, transport=remote)
        self.assertTrue(caught.exception.uncertain); self.assertTrue(remote.releases[0]['draft'])

    def test_hosted_capture_uses_unprivileged_debian_and_explicit_runtime_only(self):
        with mock.patch.dict(os.environ, {'GH_TOKEN': 'do-not-copy', 'GITHUB_RUN_ID': '4'}):
            argv = S.hosted_command('a' * 64, 'b' * 64, 2, uid=1001, gid=1001)
        self.assertIn('debian:bookworm', argv)
        self.assertNotIn('GH_TOKEN', argv); self.assertNotIn('do-not-copy', ' '.join(argv))
        script = argv[argv.index('-euc') + 1]
        self.assertIn('runuser -u gallery', script); self.assertIn('96', script)
        self.assertIn('SDL_VIDEODRIVER=x11', script)
        self.assertNotIn('emscripten', script)
        with self.assertRaisesRegex(ValueError, 'non-root'):
            S.hosted_command('a' * 64, 'b' * 64, 2, uid=0, gid=1001)

    def test_retained_mode_requires_both_exact_requests_without_base_fallback(self):
        requests = {name: {'schema_version': 2, 'repository': 'example/project', 'target': target,
            'profile': 'all-gui', 'recipe_id': recipe, 'workflow': 'sdk-import.yml', 'run_id': 123,
            'attempt': 1, 'job_id': 456, 'source_commit': 'a' * 40,
            'group': {'manifest_id': 11, 'manifest_sha256': 'b' * 64},
            'proof': {'manifest_id': 12, 'manifest_sha256': 'c' * 64}}
            for name, target, recipe in [('native', 'linux-x86_64', 'b' * 64), ('wasm', 'browser-wasm32', 'c' * 64)]}
        self.assertEqual(S.input_selection('example/project', 'b' * 64, 'c' * 64, 'retained', requests),
                         {'native': 'b' * 64, 'wasm': 'c' * 64})
        for selected in (None, {}, {'native': requests['native']}, {**requests, 'unexpected': {}},
                         {**requests, 'wasm': {**requests['wasm'], 'recipe_id': 'd' * 64}}):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                S.input_selection('example/project', 'b' * 64, 'c' * 64, 'retained', selected)
        with self.assertRaisesRegex(ValueError, 'must not contain'):
            S.input_selection('example/project', 'b' * 64, 'c' * 64, 'base', requests)
        with mock.patch.object(S.ci, 'retained_sdk', side_effect=ValueError('missing retained input')), \
             mock.patch.object(S.delivery, 'fetch_base') as base:
            with self.assertRaisesRegex(ValueError, 'missing retained input'):
                S.prepare_inputs('example/project', 'b' * 64, 'c' * 64, self.root / 'inputs', 'retained', requests)
        base.assert_not_called()

    def test_container_timeout_stops_only_the_verified_owned_container(self):
        unique = mock.Mock(hex='a' * 32)
        inspected = mock.Mock(returncode=0, stdout='b' * 64 + ' ' + 'a' * 32)
        with mock.patch.object(S.uuid, 'uuid4', return_value=unique), \
             mock.patch.object(S, 'command', side_effect=[TimeoutError('client timeout'), None]) as run, \
             mock.patch.object(S.subprocess, 'run', return_value=inspected):
            with self.assertRaisesRegex(TimeoutError, 'client timeout'):
                S.run_hosted(['docker', 'run', '--rm', 'image'])
        self.assertIn('foundation-gallery-' + 'a' * 32, run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0], ['docker', 'rm', '--force', 'b' * 64])

    def test_foreign_or_unknown_container_is_preserved_after_client_failure(self):
        for row in (mock.Mock(returncode=0, stdout='b' * 64 + ' foreign'), mock.Mock(returncode=1, stdout='')):
            with self.subTest(row=row), mock.patch.object(S, 'command', side_effect=TimeoutError('original')) as run, \
                 mock.patch.object(S.subprocess, 'run', return_value=row):
                with self.assertRaisesRegex(RuntimeError, 'cleanup could not') as caught:
                    S.run_hosted(['docker', 'run', '--rm', 'image'])
            self.assertIsInstance(caught.exception.__cause__, TimeoutError)
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__': unittest.main()
