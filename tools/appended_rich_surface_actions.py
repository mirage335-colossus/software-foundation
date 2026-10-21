"""Validate and dispatch physical WebDriver actions to the observed rich surface."""
import math
import re
import time


PROTOCOL = 'foundation-rich-surface-observer-v1'
SURFACE_ID = 'engine.frame'
BITMAP_WIDTH = 800
BITMAP_HEIGHT = 600
MAX_TEXT_BYTES = 4096
MAX_CHORD_KEYS = 8
MAX_GEOMETRY = 1_000_000
MAX_WHEEL_DELTA = 1_000_000

# The page implementation exposes observation only. All changes go through
# WebDriver's physical input actions below.
READ_SURFACE = '''const observer=globalThis.foundationRichSurfaceObserver;
if(!observer||typeof observer.read!=='function')throw Error('Rich surface observer unavailable');
return observer.read();'''

_NAME = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')
_U64_DECIMAL = re.compile(r'[1-9][0-9]{0,19}\Z')
_SHA256_HEX = re.compile(r'[0-9a-f]{64}\Z')
_U64_MAX = (1 << 64) - 1
_SPECIAL_KEYS = {
    'Control': '\ue009', 'Shift': '\ue008', 'Alt': '\ue00a', 'Meta': '\ue03d',
    'Home': '\ue011', 'End': '\ue010', 'ArrowLeft': '\ue012',
    'ArrowUp': '\ue013', 'ArrowRight': '\ue014', 'ArrowDown': '\ue015',
    'Tab': '\ue004', 'Enter': '\ue007', 'Backspace': '\ue003',
    'Delete': '\ue017', 'Escape': '\ue00c', 'PageUp': '\ue00e',
    'PageDown': '\ue00f',
}


def _number(value, *, minimum=None, maximum=None, label='number'):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be a finite number')
    if minimum is not None and value < minimum:
        raise ValueError(label + ' is below its allowed range')
    if maximum is not None and value > maximum:
        raise ValueError(label + ' exceeds its allowed range')
    return value


def _exact_fields(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(label + ' has an invalid shape')


def validate_surface_action(step):
    """Return a canonical copy of one bounded engine-frame action."""
    if type(step) is not dict or type(step.get('id')) is not str or not _NAME.fullmatch(step['id']):
        raise ValueError('surface action id must be a bounded name')
    action = step.get('action')
    fields = {
        'surface-click': {'id', 'action', 'surface', 'point'},
        'surface-wheel': {'id', 'action', 'surface', 'point', 'delta'},
        'surface-keys': {'id', 'action', 'surface', 'keys'},
        'surface-type': {'id', 'action', 'surface', 'text'},
    }.get(action)
    if fields is None or set(step) != fields:
        raise ValueError('surface action has an unsupported action or fields')
    _exact_fields(step['surface'], {'id'}, 'surface')
    if step['surface']['id'] != SURFACE_ID:
        raise ValueError('surface action must target engine.frame')
    result = {'id': step['id'], 'action': action, 'surface': {'id': SURFACE_ID}}
    if action in ('surface-click', 'surface-wheel'):
        _exact_fields(step['point'], {'x', 'y'}, 'point')
        point = {axis: _number(step['point'][axis], minimum=0, maximum=(BITMAP_WIDTH if axis == 'x' else BITMAP_HEIGHT), label='point.' + axis)
                 for axis in ('x', 'y')}
        if point['x'] >= BITMAP_WIDTH or point['y'] >= BITMAP_HEIGHT:
            raise ValueError('surface point must remain inside the bitmap')
        result['point'] = point
    if action == 'surface-wheel':
        _exact_fields(step['delta'], {'x', 'y'}, 'wheel delta')
        delta = {}
        for axis in ('x', 'y'):
            value = step['delta'][axis]
            if type(value) is not int or abs(value) > MAX_WHEEL_DELTA:
                raise ValueError('wheel deltas must be bounded integers')
            delta[axis] = value
        if delta['x'] == 0 and delta['y'] == 0:
            raise ValueError('wheel delta must be nonzero')
        result['delta'] = delta
    elif action == 'surface-keys':
        keys = step['keys']
        if type(keys) is not list or not 1 <= len(keys) <= MAX_CHORD_KEYS:
            raise ValueError('key chord must contain between one and eight keys')
        for key in keys:
            if type(key) is not str or not (key in _SPECIAL_KEYS or (len(key) == 1 and 0x20 <= ord(key) <= 0x7e)):
                raise ValueError('key chord contains an unsupported symbolic key')
        if len(set(keys)) != len(keys):
            raise ValueError('key chord cannot contain duplicate keys')
        result['keys'] = list(keys)
    elif action == 'surface-type':
        text = step['text']
        if type(text) is not str or not text:
            raise ValueError('surface text must be nonempty text')
        if '\x00' in text or any(0xd800 <= ord(char) <= 0xdfff for char in text):
            raise ValueError('surface text must contain Unicode scalar values')
        try:
            encoded = text.encode('utf-8', 'strict')
        except UnicodeEncodeError as error:
            raise ValueError('surface text must contain Unicode scalar values') from error
        if len(encoded) > MAX_TEXT_BYTES:
            raise ValueError('surface text exceeds 4096 UTF-8 bytes')
        result['text'] = text
    return result


def _rect(value, label, *, positive=True):
    _exact_fields(value, {'x', 'y', 'width', 'height'}, label)
    result = {key: _number(value[key], minimum=-MAX_GEOMETRY, maximum=MAX_GEOMETRY,
                           label=label + '.' + key)
              for key in ('x', 'y', 'width', 'height')}
    if positive and (result['width'] <= 0 or result['height'] <= 0):
        raise ValueError(label + ' dimensions must be positive')
    if not positive and (result['width'] < 0 or result['height'] < 0):
        raise ValueError(label + ' dimensions cannot be negative')
    return result


def _read_presentation(browser):
    observed = browser.evaluate(READ_SURFACE)
    _exact_fields(observed, {'protocol', 'frontendGeneration', 'closed', 'presentation', 'document'}, 'observer result')
    if (observed['protocol'] != PROTOCOL or type(observed['frontendGeneration']) is not str or
            not _SHA256_HEX.fullmatch(observed['frontendGeneration'])):
        raise ValueError('surface observer protocol or frontend generation is invalid')
    if type(observed['closed']) is not bool or observed['closed']:
        raise ValueError('surface observer is closed')
    presentation = observed['presentation']
    _exact_fields(presentation, {'snapshotRevision', 'renderedRevision', 'identity', 'available', 'bounds', 'clip',
                                 'displayScale', 'bitmap', 'canvas'}, 'presentation')
    if type(presentation['available']) is not bool or not presentation['available']:
        raise ValueError('engine surface is not currently available')
    identity = presentation['identity']
    _exact_fields(identity, {'owner', 'presentationRevision', 'generation', 'epoch', 'context'}, 'surface identity')
    _exact_fields(identity['owner'], {'id', 'generation'}, 'surface owner')
    owner_generation = identity['owner']['generation']
    if identity['owner']['id'] != SURFACE_ID:
        raise ValueError('observer identity does not name a live engine.frame generation')
    snapshot_revision = presentation['snapshotRevision']
    rendered_revision = presentation['renderedRevision']
    identity_values = {
        'snapshotRevision': snapshot_revision,
        'renderedRevision': rendered_revision,
        'presentationRevision': identity['presentationRevision'],
        'generation': identity['generation'],
        'epoch': identity['epoch'],
        'context': identity['context'],
        'owner generation': owner_generation,
    }
    parsed_values = {}
    for key, value in identity_values.items():
        if type(value) is not str or not _U64_DECIMAL.fullmatch(value) or int(value) > _U64_MAX:
            raise ValueError('surface observer ' + key + ' must be canonical nonzero u64 decimal')
        parsed_values[key] = int(value)
    if (identity_values['presentationRevision'] != snapshot_revision or
            parsed_values['renderedRevision'] > parsed_values['snapshotRevision']):
        raise ValueError('surface observer presentation revisions are inconsistent')
    bounds = _rect(presentation['bounds'], 'bounds')
    clip = _rect(presentation['clip'], 'clip', positive=False)
    canvas = _rect(presentation['canvas'], 'canvas')
    scale = _number(presentation['displayScale'], minimum=0, maximum=4, label='displayScale')
    if scale != 1:
        raise ValueError('public surface actions require displayScale 1')
    bitmap = presentation['bitmap']
    _exact_fields(bitmap, {'source', 'revision', 'width', 'height'}, 'bitmap')
    if (type(bitmap['source']) is not str or not bitmap['source'] or type(bitmap['revision']) is not str or
            not _U64_DECIMAL.fullmatch(bitmap['revision']) or
            int(bitmap['revision']) > _U64_MAX or
            type(bitmap['width']) is not int or type(bitmap['height']) is not int or
            bitmap['width'] != BITMAP_WIDTH or bitmap['height'] != BITMAP_HEIGHT):
        raise ValueError('surface bitmap dimensions or identity are invalid')
    if bounds['width'] != BITMAP_WIDTH or bounds['height'] != BITMAP_HEIGHT:
        raise ValueError('surface logical bounds do not match its bitmap')
    intersection = {
        'left': max(bounds['x'], clip['x']), 'top': max(bounds['y'], clip['y']),
        'right': min(bounds['x'] + bounds['width'], clip['x'] + clip['width']),
        'bottom': min(bounds['y'] + bounds['height'], clip['y'] + clip['height']),
    }
    if intersection['right'] <= intersection['left'] or intersection['bottom'] <= intersection['top']:
        raise ValueError('surface clip does not intersect the engine bounds')
    return {
        'frontendGeneration': observed['frontendGeneration'],
        'identity': identity,
        'bounds': bounds,
        'clip': clip,
        'displayScale': scale,
        'bitmap': bitmap,
        'canvas': canvas,
        'intersection': intersection,
    }


def _same_target(first, second):
    return all(first[key] == second[key] for key in
               ('frontendGeneration', 'identity', 'bounds', 'clip', 'bitmap', 'canvas', 'displayScale'))


def _target_point(snapshot, point):
    bounds, canvas, clip = snapshot['bounds'], snapshot['canvas'], snapshot['intersection']
    logical_x = bounds['x'] + point['x'] / snapshot['displayScale']
    logical_y = bounds['y'] + point['y'] / snapshot['displayScale']
    if not (clip['left'] <= logical_x < clip['right'] and clip['top'] <= logical_y < clip['bottom']):
        raise ValueError('surface point is outside the visible clip')
    x = canvas['x'] + (logical_x - bounds['x']) * canvas['width'] / bounds['width']
    y = canvas['y'] + (logical_y - bounds['y']) * canvas['height'] / bounds['height']
    x, y = round(x), round(y)
    # A fractional edge can round into the clipped-away region. Fail closed
    # instead of silently moving the requested point.
    visible_left = canvas['x'] + (clip['left'] - bounds['x']) * canvas['width'] / bounds['width']
    visible_top = canvas['y'] + (clip['top'] - bounds['y']) * canvas['height'] / bounds['height']
    visible_right = canvas['x'] + (clip['right'] - bounds['x']) * canvas['width'] / bounds['width']
    visible_bottom = canvas['y'] + (clip['bottom'] - bounds['y']) * canvas['height'] / bounds['height']
    if not (visible_left <= x < visible_right and visible_top <= y < visible_bottom):
        raise ValueError('rounded physical point is outside the visible clip')
    return x, y


def _key_value(key):
    return _SPECIAL_KEYS.get(key, key)


def _dispatch(browser, engine, actions):
    request = {'actions': actions}
    if engine == 'chromium':
        browser.request('POST', browser.path('/actions'), request)
    else:
        browser.command('WebDriver:PerformActions', request)


def dispatch_surface_action(browser, engine, step):
    """Send one action to the fresh, stable engine.frame through WebDriver."""
    if engine not in ('firefox', 'chromium'):
        raise ValueError('surface actions require Firefox or Chromium WebDriver')
    action = validate_surface_action(step)
    first = _read_presentation(browser)
    second = _read_presentation(browser)
    if not _same_target(first, second):
        raise ValueError('engine surface changed between observation and physical dispatch')
    started = time.monotonic_ns()
    kind = action['action']
    if kind == 'surface-click':
        x, y = _target_point(second, action['point'])
        _dispatch(browser, engine, [{'type': 'pointer', 'id': 'foundation-pointer',
            'parameters': {'pointerType': 'mouse'}, 'actions': [
                {'type': 'pointerMove', 'duration': 0, 'x': x, 'y': y},
                {'type': 'pointerDown', 'button': 0}, {'type': 'pointerUp', 'button': 0}]}])
    elif kind == 'surface-wheel':
        x, y = _target_point(second, action['point'])
        _dispatch(browser, engine, [{'type': 'wheel', 'id': 'foundation-wheel', 'actions': [
            {'type': 'scroll', 'x': x, 'y': y, 'deltaX': action['delta']['x'],
             'deltaY': action['delta']['y'], 'duration': 0}]}])
    elif kind == 'surface-keys':
        values = [_key_value(key) for key in action['keys']]
        actions = [{'type': 'keyDown', 'value': value} for value in values]
        actions.extend({'type': 'keyUp', 'value': value} for value in reversed(values))
        _dispatch(browser, engine, [{'type': 'key', 'id': 'foundation-keyboard', 'actions': actions}])
    else:
        actions = []
        for char in action['text']:
            actions.extend(({'type': 'keyDown', 'value': char}, {'type': 'keyUp', 'value': char}))
        _dispatch(browser, engine, [{'type': 'key', 'id': 'foundation-keyboard', 'actions': actions}])
    return started
