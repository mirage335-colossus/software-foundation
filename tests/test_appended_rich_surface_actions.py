"""Physical WebDriver adapter tests; no browser or page code is executed."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_rich_surface_actions as actions


def snapshot():
    return {
        'protocol': actions.PROTOCOL,
        'frontendGeneration': 'a' * 64,
        'closed': False,
        'presentation': {
            'snapshotRevision': '30',
            'renderedRevision': '30',
            'identity': {
                'owner': {'id': 'engine.frame', 'generation': '4'},
                'presentationRevision': '30', 'generation': '4', 'epoch': '9', 'context': '17',
            },
            'available': True,
            'bounds': {'x': 10, 'y': 20, 'width': 800, 'height': 600},
            'clip': {'x': 110, 'y': 70, 'width': 700, 'height': 550},
            'displayScale': 1,
            'bitmap': {'source': 'engine.frame', 'revision': '8', 'width': 800, 'height': 600},
            # Deliberately scaled in CSS: native coordinates must use this rect.
            'canvas': {'x': 100, 'y': 50, 'width': 1600, 'height': 1200},
        },
        'document': {'title': 'fixture'},
    }


class FakeBrowser:
    def __init__(self, observations=None):
        self.observations = list(observations or [snapshot(), snapshot()])
        self.reads = 0
        self.commands = []

    def evaluate(self, source, args=()):
        self.assert_read_only_source(source, args)
        index = min(self.reads, len(self.observations) - 1)
        self.reads += 1
        return copy.deepcopy(self.observations[index])

    @staticmethod
    def assert_read_only_source(source, args):
        if source != actions.READ_SURFACE or args != ():
            raise AssertionError('adapter must use only the pinned observer read API')

    def command(self, name, value):
        self.commands.append(('firefox', name, copy.deepcopy(value)))
        return {}

    def path(self, suffix):
        return '/session/example' + suffix

    def request(self, method, path, value):
        self.commands.append(('chromium', method, path, copy.deepcopy(value)))
        return {}


class ValidateSurfaceActionTests(unittest.TestCase):
    def test_returns_canonical_copy_and_accepts_bitmap_edge_fraction(self):
        source = {'id': 'click-1', 'action': 'surface-click', 'surface': {'id': 'engine.frame'},
                  'point': {'x': 799.5, 'y': 599.5}}
        result = actions.validate_surface_action(source)
        self.assertEqual(result, source)
        self.assertIsNot(result, source)
        self.assertIsNot(result['point'], source['point'])

    def test_unknown_fields_wrong_surface_and_bad_points_fail_closed(self):
        base = {'id': 'click-1', 'action': 'surface-click', 'surface': {'id': 'engine.frame'},
                'point': {'x': 1, 'y': 2}}
        cases = []
        cases.append(dict(base, extra=True))
        cases.append(dict(base, surface={'id': 'other.frame'}))
        cases.append(dict(base, point={'x': True, 'y': 2}))
        cases.append(dict(base, point={'x': 800, 'y': 2}))
        cases.append(dict(base, point={'x': 1, 'y': -1}))
        cases.append(dict(base, point={'x': float('inf'), 'y': 2}))
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                actions.validate_surface_action(value)

    def test_wheel_delta_and_symbolic_chord_are_bounded(self):
        wheel = {'id': 'wheel', 'action': 'surface-wheel', 'surface': {'id': 'engine.frame'},
                 'point': {'x': 100, 'y': 100}, 'delta': {'x': 0, 'y': -120}}
        self.assertEqual(actions.validate_surface_action(wheel)['delta']['y'], -120)
        for delta in ({'x': 0, 'y': 0}, {'x': 1_000_001, 'y': 0},
                      {'x': False, 'y': 0}, {'x': 0.5, 'y': 0}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                actions.validate_surface_action(dict(wheel, delta=delta))
        chord = {'id': 'keys', 'action': 'surface-keys', 'surface': {'id': 'engine.frame'},
                 'keys': ['Control', 'Shift', 'a']}
        self.assertEqual(actions.validate_surface_action(chord)['keys'], chord['keys'])
        for keys in ([], ['Control'] * 2, ['UnlistedKey'], ['a'] * 9):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                actions.validate_surface_action(dict(chord, keys=keys))

    def test_text_requires_nonempty_unicode_scalars_and_utf8_bound(self):
        base = {'id': 'text', 'action': 'surface-type', 'surface': {'id': 'engine.frame'}, 'text': 'Hello 🙂'}
        self.assertEqual(actions.validate_surface_action(base)['text'], 'Hello 🙂')
        for text in ('', 'a\x00b', '\ud800', 'é' * 2049):
            with self.subTest(text_length=len(text)), self.assertRaises(ValueError):
                actions.validate_surface_action(dict(base, text=text))


class DispatchSurfaceActionTests(unittest.TestCase):
    def click(self, **overrides):
        value = {'id': 'click', 'action': 'surface-click', 'surface': {'id': 'engine.frame'},
                 'point': {'x': 150, 'y': 100}}
        value.update(overrides)
        return value

    def test_click_uses_fresh_scaled_canvas_coordinates_and_webdriver(self):
        driver = FakeBrowser()
        with patch.object(actions.time, 'monotonic_ns', return_value=12345):
            started = actions.dispatch_surface_action(driver, 'firefox', self.click())
        self.assertEqual(started, 12345)
        self.assertEqual(driver.reads, 2)
        self.assertEqual(driver.commands, [('firefox', 'WebDriver:PerformActions', {
            'actions': [{'type': 'pointer', 'id': 'foundation-pointer',
                'parameters': {'pointerType': 'mouse'}, 'actions': [
                    {'type': 'pointerMove', 'duration': 0, 'x': 400, 'y': 250},
                    {'type': 'pointerDown', 'button': 0}, {'type': 'pointerUp', 'button': 0}]}]})])

    def test_clip_mismatch_closed_surface_and_generation_change_do_not_dispatch(self):
        outside = self.click(point={'x': 10, 'y': 10})
        driver = FakeBrowser()
        with self.assertRaisesRegex(ValueError, 'outside the visible clip'):
            actions.dispatch_surface_action(driver, 'firefox', outside)
        self.assertEqual(driver.commands, [])

        first, changed = snapshot(), snapshot()
        changed['frontendGeneration'] = 'b' * 64
        driver = FakeBrowser([first, changed])
        with self.assertRaisesRegex(ValueError, 'changed between observation'):
            actions.dispatch_surface_action(driver, 'firefox', self.click())
        self.assertEqual(driver.commands, [])

    def test_observer_rejects_noncanonical_identity_and_inconsistent_revisions(self):
        mutations = (
            lambda value: value.update(frontendGeneration='A' * 64),
            lambda value: value['presentation'].update(snapshotRevision='030'),
            lambda value: value['presentation']['identity'].update(presentationRevision='29'),
            lambda value: value['presentation'].update(renderedRevision='31'),
            lambda value: value['presentation']['identity']['owner'].update(generation='0'),
            lambda value: value['presentation']['bitmap'].update(revision=str(1 << 64)),
        )
        for mutate in mutations:
            first, second = snapshot(), snapshot()
            mutate(first)
            driver = FakeBrowser([first, second])
            with self.subTest(first=first), self.assertRaises(ValueError):
                actions.dispatch_surface_action(driver, 'firefox', self.click())
            self.assertEqual(driver.commands, [])

        unavailable = snapshot()
        unavailable['presentation']['available'] = False
        driver = FakeBrowser([unavailable])
        with self.assertRaisesRegex(ValueError, 'not currently available'):
            actions.dispatch_surface_action(driver, 'firefox', self.click())
        self.assertEqual(driver.commands, [])

    def test_wheel_uses_physical_wheel_source(self):
        driver = FakeBrowser()
        step = {'id': 'scroll', 'action': 'surface-wheel', 'surface': {'id': 'engine.frame'},
                'point': {'x': 150, 'y': 100}, 'delta': {'x': 0, 'y': -80}}
        actions.dispatch_surface_action(driver, 'chromium', step)
        self.assertEqual(driver.commands, [('chromium', 'POST', '/session/example/actions', {
            'actions': [{'type': 'wheel', 'id': 'foundation-wheel', 'actions': [
                {'type': 'scroll', 'x': 400, 'y': 250, 'deltaX': 0, 'deltaY': -80, 'duration': 0}]}]})])

    def test_chord_releases_keys_in_reverse_order_and_typing_has_no_script_events(self):
        driver = FakeBrowser()
        chord = {'id': 'chord', 'action': 'surface-keys', 'surface': {'id': 'engine.frame'},
                 'keys': ['Control', 'a']}
        actions.dispatch_surface_action(driver, 'firefox', chord)
        self.assertEqual(driver.commands[0][2]['actions'][0]['actions'], [
            {'type': 'keyDown', 'value': '\ue009'}, {'type': 'keyDown', 'value': 'a'},
            {'type': 'keyUp', 'value': 'a'}, {'type': 'keyUp', 'value': '\ue009'}])
        driver = FakeBrowser()
        text = {'id': 'type', 'action': 'surface-type', 'surface': {'id': 'engine.frame'}, 'text': 'x🙂'}
        actions.dispatch_surface_action(driver, 'firefox', text)
        self.assertEqual(driver.commands[0][2]['actions'][0]['actions'], [
            {'type': 'keyDown', 'value': 'x'}, {'type': 'keyUp', 'value': 'x'},
            {'type': 'keyDown', 'value': '🙂'}, {'type': 'keyUp', 'value': '🙂'}])

    def test_only_supported_engine_names_are_accepted(self):
        with self.assertRaisesRegex(ValueError, 'Firefox or Chromium'):
            actions.dispatch_surface_action(FakeBrowser(), 'safari', self.click())


if __name__ == '__main__':
    unittest.main()
