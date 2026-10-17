// SPDX-License-Identifier: CC0-1.0
// Evaluated ONLY by the internal WebCore/JSC session. Prototype protocol v1.
#pragma once
static constexpr const char* bibPrototypeSemanticScript = R"FNDJS(
(function (epoch, request, editorState) {
  "use strict";
  const slot = Symbol.for("foundation.prototype.semantic.v1");
  let state = globalThis[slot];
  if (!state || state.document !== document || state.epoch !== epoch) {
    state = { document, epoch, ids: new WeakMap(), visible: new Map(), next: 1, revision: 0 };
    state.observer = new MutationObserver(() => { ++state.revision; });
    state.observer.observe(document, { subtree: true, childList: true, characterData: true, attributes: true });
    Object.defineProperty(globalThis, slot, { value: state, configurable: true });
  }
  const fail = code => ({ requestId: request?.id, ok: false, code, epoch });
  if (!request || !Number.isSafeInteger(request.id) || request.id < 1)
    return fail("invalid-request");
  const idOf = node => {
    if (!node) return null;
    if (!state.ids.has(node)) state.ids.set(node, state.next++);
    return state.ids.get(node);
  };
  const isBoundary = (text, offset) => Number.isSafeInteger(offset) && offset >= 0 && offset <= text.length &&
    !(offset > 0 && offset < text.length && text.charCodeAt(offset - 1) >= 0xd800 &&
      text.charCodeAt(offset - 1) <= 0xdbff && text.charCodeAt(offset) >= 0xdc00 && text.charCodeAt(offset) <= 0xdfff);
  const inScope = node => {
    if (!node || !node.isConnected || node.ownerDocument !== document) return false;
    for (let parent = node.nodeType === 1 ? node : node.parentElement; parent; parent = parent.parentElement) {
      if (parent.getAttribute("data-foundation-tui") === "omit") return false;
      const style = getComputedStyle(parent);
      if (style.display === "none") return false;
    }
    return true;
  };
  const visible = node => {
    const element = node.nodeType === 1 ? node : node.parentElement;
    return element && !["hidden", "collapse"].includes(getComputedStyle(element).visibility);
  };
  const available = node => inScope(node) && visible(node);
  const selectionStamp = () => {
    const selected = getSelection();
    return selected ? [idOf(selected.anchorNode), selected.anchorOffset, idOf(selected.focusNode), selected.focusOffset].join(":") : "";
  };
  const nativeBefore = editorState();
  if (state.observer.takeRecords().length || state.editorRevision !== nativeBefore.revision ||
      state.selectionStamp !== selectionStamp() || state.activeElement !== document.activeElement)
    ++state.revision;
  if (request.operation !== "snapshot") {
    if (request.epoch !== epoch || request.revision !== state.revision)
      return fail("stale-view");
    if (request.operation === "select") {
      const anchor = state.visible.get(request.anchorNode), focus = state.visible.get(request.focusNode);
      if (!available(anchor) || !available(focus) || anchor.nodeType !== 3 || focus.nodeType !== 3 ||
          !isBoundary(anchor.data, request.anchorOffset) || !isBoundary(focus.data, request.focusOffset))
        return fail("invalid-selection");
      getSelection().setBaseAndExtent(anchor, request.anchorOffset, focus, request.focusOffset);
    } else {
      const node = state.visible.get(request.node);
      if (!available(node) || node.nodeType !== 1 || node.disabled) return fail("unavailable-node");
      if (request.operation === "focus") node.focus();
      else if (request.operation === "activate" && /^(A|BUTTON|INPUT)$/.test(node.tagName)) node.click();
      else return fail("unsupported-action");
    }
  }
  const nodes = [], presented = new Map(), stack = [[document.documentElement, null]];
  let remainingText = 65536, truncated = false, visited = 0;
  const bounded = value => {
    const text = String(value ?? "");
    let end = Math.min(text.length, remainingText, 2048);
    if (!isBoundary(text, end)) --end;
    const kept = text.slice(0, end);
    remainingText -= kept.length;
    if (kept.length !== text.length) truncated = true;
    return kept;
  };
  while (stack.length) {
    if (++visited > 4096) { truncated = true; break; }
    const [node, parent] = stack.pop();
    if (!node || !inScope(node) || ![1, 3].includes(node.nodeType)) continue;
    if (nodes.length === 2048) { truncated = true; break; }
    if (node.nodeType === 1 && /^(SCRIPT|STYLE|TEMPLATE|NOSCRIPT)$/.test(node.tagName)) continue;
    const shown = visible(node), id = shown ? idOf(node) : parent;
    if (shown) presented.set(id, node);
    if (node.nodeType === 3) {
      if (shown) nodes.push({ id, parent, type: "text", text: bounded(node.data) });
    } else {
      const style = getComputedStyle(node), masked = node.tagName === "INPUT" && node.type === "password";
      if (shown) nodes.push({ id, parent, type: "element", tag: node.tagName.toLowerCase(),
        role: bounded(node.getAttribute("role")), name: bounded(node.getAttribute("aria-label")),
        display: bounded(style.display), whiteSpace: bounded(style.whiteSpace),
        editable: !!node.isContentEditable, disabled: !!node.disabled,
        readonly: !!node.readOnly, masked,
        value: masked ? "" : bounded(/^(INPUT|TEXTAREA|SELECT)$/.test(node.tagName) ? node.value : ""),
        checked: !!node.checked, href: bounded(node.tagName === "A" ? node.getAttribute("href") : "") });
      const keep = Math.min(node.childNodes.length, Math.max(0, 2048 - nodes.length - stack.length));
      if (keep < node.childNodes.length) truncated = true;
      for (let index = keep - 1; index >= 0; --index)
        stack.push([node.childNodes[index], id]);
    }
  }
  state.visible = presented;
  const selection = getSelection();
  let selected = null;
  if (selection && state.visible.has(idOf(selection.anchorNode)) && state.visible.has(idOf(selection.focusNode))) {
    selected = { anchorNode: idOf(selection.anchorNode), anchorOffset: selection.anchorOffset,
      focusNode: idOf(selection.focusNode), focusOffset: selection.focusOffset };
    const range = document.createRange();
    range.setStart(selection.focusNode, selection.focusOffset);
    range.collapse(true);
    const rect = range.getBoundingClientRect();
    selected.focusRect = { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  }
  const currentEditorState = editorState();
  state.editorRevision = currentEditorState.revision;
  state.selectionStamp = selectionStamp(); state.activeElement = document.activeElement;
  state.observer.takeRecords(); // This response already includes this action's mutations.
  return { requestId: request.id, ok: true, epoch, revision: ++state.revision,
    editorState: currentEditorState, truncated, activeNode: idOf(document.activeElement), selection: selected, nodes };
})
)FNDJS";
