import { connectQuoteProvider, UINT32_MAX } from './quote-pad-protocol.mjs';

const byId = id => document.getElementById(id);
const quoteTab = byId('quote-tab');
const notesTab = byId('notes-tab');
const quotePane = byId('quote-page');
const notesPane = byId('notes-page');
const editor = byId('quote-editor');
const boldButton = byId('bold-text');
const undoButton = byId('undo-text');
const calculateButton = byId('calculate-total');
const leftInput = byId('left-amount');
const rightInput = byId('right-amount');
const totalOutput = byId('quote-total');
const detailOutput = byId('total-detail');
const statusOutput = byId('provider-status');
let calculate;

function selectTab(tab) {
  const quoteSelected = tab === 'quote';
  quoteTab.setAttribute('aria-selected', String(quoteSelected));
  notesTab.setAttribute('aria-selected', String(!quoteSelected));
  quoteTab.tabIndex = quoteSelected ? 0 : -1;
  notesTab.tabIndex = quoteSelected ? -1 : 0;
  quotePane.hidden = !quoteSelected;
  notesPane.hidden = quoteSelected;
  (quoteSelected ? quoteTab : notesTab).focus();
}
quoteTab.addEventListener('click', () => selectTab('quote'));
notesTab.addEventListener('click', () => selectTab('notes'));
for (const tab of [quoteTab, notesTab]) tab.addEventListener('keydown', event => {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    selectTab(tab === quoteTab ? 'notes' : 'quote');
  }
});

for (const button of [boldButton, undoButton]) button.addEventListener('mousedown', event => event.preventDefault());
boldButton.addEventListener('click', () => {
  editor.focus();
  document.execCommand('bold');
  boldButton.setAttribute('aria-pressed', String(document.queryCommandState('bold')));
});
undoButton.addEventListener('click', () => {
  editor.focus();
  document.execCommand('undo');
  boldButton.setAttribute('aria-pressed', String(document.queryCommandState('bold')));
});
document.addEventListener('selectionchange', () => {
  if (document.activeElement === editor || editor.contains(document.activeElement))
    boldButton.setAttribute('aria-pressed', String(document.queryCommandState('bold')));
});

function amount(input) {
  const value = input.value.trim();
  if (!/^(0|[1-9][0-9]*)$/.test(value)) throw new RangeError('Enter a whole unsigned amount.');
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number > UINT32_MAX)
    throw new RangeError('Amount is outside the supported 32-bit range.');
  return number;
}
calculateButton.addEventListener('click', async () => {
  calculateButton.disabled = true;
  try {
    const result = await calculate(amount(leftInput), amount(rightInput));
    if (result.overflow) {
      totalOutput.textContent = 'Total: overflow';
      detailOutput.textContent = `Checked provider call ${result.calls} could not be represented.`;
    } else {
      totalOutput.textContent = `Total: ${result.total}`;
      detailOutput.textContent = `Portable provider call ${result.calls}`;
    }
    statusOutput.textContent = 'Portable module provider connected';
  } catch (error) {
    totalOutput.textContent = '—';
    detailOutput.textContent = error instanceof Error ? error.message : 'Calculation failed.';
  } finally {
    calculateButton.disabled = false;
  }
});

try {
  calculate = await connectQuoteProvider();
  statusOutput.textContent = 'Portable module provider connected';
  calculateButton.disabled = false;
} catch (error) {
  statusOutput.textContent = error instanceof Error ? error.message : 'Provider unavailable';
  calculateButton.disabled = true;
}
