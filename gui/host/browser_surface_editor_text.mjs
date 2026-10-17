import {surfaceScalarMap} from './browser_surface.mjs';

// Owned text observations only. These helpers neither establish event trust nor
// infer an input's cause, editor revision, composition outcome or native range.
const encoder = new TextEncoder();
const limit = value => {
  if (!Number.isSafeInteger(value) || value < 1 || value > 65536) throw Error('Invalid editor text limit');
  return value;
};

export function captureEditorText(observation, textBytes = 65536) {
  limit(textBytes);
  const {value, selectionStart, selectionEnd, selectionDirection} = observation;
  if (typeof value !== 'string' || value.length > textBytes ||
      !['forward', 'backward', 'none'].includes(selectionDirection)) throw Error('Invalid editor text observation');
  const map = surfaceScalarMap(value), byteLength = encoder.encode(value).length;
  if (byteLength > textBytes || !Number.isSafeInteger(selectionStart) ||
      !Number.isSafeInteger(selectionEnd) || selectionStart > selectionEnd) throw Error('Invalid editor text observation');
  const selection = Object.freeze([map.byteOffset(selectionStart), map.byteOffset(selectionEnd)]);
  return Object.freeze({value, selectionStart, selectionEnd, selectionDirection, selection, byteLength});
}

// The range is the captured BEFORE selection, never a longest-prefix/suffix
// guess. Changes outside its exact unchanged flanks are not representable.
export function proveEditorReplacement(before, after, {data, textBytes = 65536} = {}) {
  before = captureEditorText(before, textBytes);
  after = captureEditorText(after, textBytes);
  const prefix = before.value.slice(0, before.selectionStart), suffix = before.value.slice(before.selectionEnd);
  if (after.value.length < prefix.length + suffix.length || !after.value.startsWith(prefix) ||
      !after.value.endsWith(suffix)) return null;
  const text = after.value.slice(prefix.length, after.value.length - suffix.length);
  // A scalar boundary in the old text need not remain one after a malformed
  // observation. Revalidate the independently owned inserted passage too.
  surfaceScalarMap(text);
  if (data !== undefined) {
    // InputEvent.data is an independent native observation. Bound it before
    // the scalar map allocates; bounded before/after values do not bound data.
    captureEditorText({value: data, selectionStart: 0, selectionEnd: 0, selectionDirection: 'none'}, textBytes);
    if (data !== text) return null;
  }
  return Object.freeze({text, replacement: before.selection, selection: after.selection,
    backward: after.selectionDirection === 'backward'});
}

// Selection is relative to the observed preedit passage. This is not a commit
// or cancel decision: even empty compositionend data cannot establish that.
export function proveEditorCompositionPassage(before, after, options = {}) {
  const replacement = proveEditorReplacement(before, after, options);
  if (!replacement) return null;
  const first = replacement.replacement[0], last = first + encoder.encode(replacement.text).length;
  if (replacement.selection[0] < first || replacement.selection[1] > last) return null;
  return Object.freeze({...replacement, selection: Object.freeze([
    replacement.selection[0] - first, replacement.selection[1] - first])});
}
