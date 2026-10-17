import assert from 'node:assert/strict';
import {captureEditorText, proveEditorReplacement, proveEditorCompositionPassage} from '../host/browser_surface_editor_text.mjs';

let checks = 0;
const equal = (actual, expected) => { assert.deepEqual(actual, expected); ++checks; };
const rejects = callback => { assert.throws(callback); ++checks; };
const text = (value, first = value.length, last = first, direction = 'none') =>
  ({value, selectionStart: first, selectionEnd: last, selectionDirection: direction});

// Byte ranges preserve Unicode scalars, including distinct normalizations and
// multi-scalar graphemes; no grapheme deletion or rich editing is inferred.
equal(captureEditorText(text('aé😀e\u0301', 1, 4, 'backward')).selection, [1, 7]);
equal(captureEditorText(text('👩‍👩‍👧‍👦')).byteLength, 25);
equal(captureEditorText(text('é')).byteLength, 2);
equal(captureEditorText(text('e\u0301')).byteLength, 3);
equal(captureEditorText(text('')).selection, [0, 0]);
for (const bad of ['\0', '\ud800', '\udfff', 'a\ud800z']) rejects(() => captureEditorText(text(bad)));
for (const bad of [text('😀', 1), text('a', -1), text('a', 0, 2), text('a', 1, 0),
  text('a', 0.5), text('a', Number.MAX_SAFE_INTEGER + 1), text('a', 0, 0, 'invalid')])
  rejects(() => captureEditorText(bad));
for (const bad of [0, -1, 65537, 1.5, Infinity]) rejects(() => captureEditorText(text(''), bad));
equal(captureEditorText(text('a'.repeat(65536))).byteLength, 65536);
rejects(() => captureEditorText(text('a'.repeat(65537))));
equal(captureEditorText(text('😀'.repeat(16384))).byteLength, 65536);
rejects(() => captureEditorText(text('😀'.repeat(16385))));
rejects(() => captureEditorText(text('é'), 1));

const before = text('Aé😀Z', 1, 4, 'backward');
equal(proveEditorReplacement(before, text('AxZ', 2), {data: 'x'}),
  {text: 'x', replacement: [1, 7], selection: [2, 2], backward: false});
equal(proveEditorReplacement(text('abc', 1), text('a😀bc', 3)),
  {text: '😀', replacement: [1, 1], selection: [5, 5], backward: false});
equal(proveEditorReplacement(text('abc', 1, 2), text('ac', 1)),
  {text: '', replacement: [1, 2], selection: [1, 1], backward: false});
equal(proveEditorReplacement(text('aaaa', 1, 2), text('aaaa', 2)).replacement, [1, 2]);
equal(proveEditorReplacement(before, text('BxZ', 2)), null);
equal(proveEditorReplacement(before, text('AxY', 2)), null);
equal(proveEditorReplacement(text('abc', 1), text('ac', 1)), null);
equal(proveEditorReplacement(before, text('AxZ', 2), {data: 'y'}), null);
equal(proveEditorReplacement(before, text('AxZ', 2), {data: ''}), null);
rejects(() => proveEditorReplacement(before, text('AxZ', 2), {data: '\ud800'}));
rejects(() => proveEditorReplacement(before, text('AxZ', 2), {data: 'x'.repeat(65537)}));
rejects(() => proveEditorReplacement(text('a', 0), text('xa', 1), {data: '😀', textBytes: 2}));
rejects(() => proveEditorReplacement(before, text('A😀Z', 2)));

equal(proveEditorCompositionPassage(text('aZ', 1), text('aé😀Z', 2, 4, 'backward')),
  {text: 'é😀', replacement: [1, 1], selection: [2, 6], backward: true});
equal(proveEditorCompositionPassage(text('abc', 1, 2), text('ac', 1)),
  {text: '', replacement: [1, 2], selection: [0, 0], backward: false});
equal(proveEditorCompositionPassage(text('aZ', 1), text('aéZ', 0)), null);
equal(proveEditorCompositionPassage(text('aZ', 1), text('aéZ', 3)), null);
equal(proveEditorCompositionPassage(text('aZ', 1), text('béZ', 2)), null);

// Results retain owned values when the caller later reuses its observation.
const observation = text('é😀', 1, 3, 'forward'), captured = captureEditorText(observation);
observation.value = 'changed'; observation.selectionStart = 0;
equal(captured.value, 'é😀'); equal(captured.selection, [2, 6]);
equal(Object.isFrozen(captured), true); equal(Object.isFrozen(captured.selection), true);
const proof = proveEditorReplacement(text('x', 0, 1), text('é', 1));
equal(Object.isFrozen(proof), true); equal(Object.isFrozen(proof.replacement), true);
equal(Object.isFrozen(proof.selection), true);
console.log(`browser surface editor text: ${checks} checks passed`);
