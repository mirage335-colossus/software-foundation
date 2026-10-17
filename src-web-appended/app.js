/* Local application behavior for the bundled Signal notebook document. */
var FoundationAppendedFixture = (function () {
  'use strict';

  const MAX_ROWS = 100;
  const MAX_CELL_LENGTH = 512;
  const NUMBER = /^(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

  function calculationError(code, message) {
    const error = new Error(message || code);
    error.code = code;
    return error;
  }

  function factor(kind) {
    if (kind !== 'amplitude' && kind !== 'power') {
      throw new Error('Choose an amplitude or power ratio.');
    }
    return kind === 'amplitude' ? 20 : 10;
  }

  function ratioToDecibels(ratio, kind) {
    const scale = factor(kind);
    if (!Number.isFinite(ratio) || ratio <= 0) {
      throw new Error('Enter a finite ratio greater than zero.');
    }
    return scale * Math.log10(ratio);
  }

  function decibelsToRatio(decibels, kind) {
    const scale = factor(kind);
    if (!Number.isFinite(decibels)) {
      throw new Error('Enter a finite decibel value.');
    }
    const ratio = Math.pow(10, decibels / scale);
    if (!Number.isFinite(ratio) || ratio === 0) {
      throw new Error('The ratio is outside the supported numeric range.');
    }
    return ratio;
  }

  function numberText(value) {
    return Number(value.toPrecision(10)).toString();
  }

  function numericCell(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim() === '') return 0;
    if (typeof value === 'string' && /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())) {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) return parsed;
    }
    throw calculationError('#VALUE!', 'A referenced cell is not a finite number.');
  }

  function cellAddress(name) {
    const match = /^([A-D])([1-9]\d*)$/.exec(name);
    if (!match || Number(match[2]) > MAX_ROWS) {
      throw calculationError('#REF!', 'The cell reference is outside this sheet.');
    }
    return {column: match[1].charCodeAt(0) - 65, row: Number(match[2]) - 1};
  }

  function evaluateFormula(source, readCell) {
    if (typeof source !== 'string' || source.length > MAX_CELL_LENGTH || source[0] !== '=') {
      throw calculationError('#FORMULA!', 'A formula must begin with = and stay within 512 characters.');
    }
    const tokens = [];
    let position = 1;
    while (position < source.length) {
      const remaining = source.slice(position);
      const space = /^\s+/.exec(remaining);
      if (space) { position += space[0].length; continue; }
      const match = /^(?:(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z]+[0-9]*|[+\-*/(),:])/.exec(remaining);
      if (!match) throw calculationError('#FORMULA!', 'This formula contains an unsupported character.');
      tokens.push(match[0].toUpperCase());
      position += match[0].length;
    }
    let index = 0;
    let depth = 0;

    function expect(token) {
      if (tokens[index++] !== token) throw calculationError('#FORMULA!', 'Check the formula syntax.');
    }

    function finite(value) {
      if (!Number.isFinite(value)) throw calculationError('#VALUE!', 'The calculated number is out of range.');
      return value;
    }

    function reference(name) {
      cellAddress(name);
      return numericCell(readCell(name));
    }

    function sumArgument() {
      if (/^[A-D][1-9]\d*$/.test(tokens[index] || '') && tokens[index + 1] === ':') {
        const first = cellAddress(tokens[index]);
        const last = cellAddress(tokens[index + 2]);
        index += 3;
        let total = 0;
        for (let row = Math.min(first.row, last.row); row <= Math.max(first.row, last.row); row += 1) {
          for (let column = Math.min(first.column, last.column); column <= Math.max(first.column, last.column); column += 1) {
            total = finite(total + reference(String.fromCharCode(65 + column) + String(row + 1)));
          }
        }
        return total;
      }
      return expression();
    }

    function primary() {
      depth += 1;
      if (depth > 64) throw calculationError('#FORMULA!', 'This formula is nested too deeply.');
      const token = tokens[index++];
      let value;
      if (token === '+' || token === '-') {
        value = primary() * (token === '-' ? -1 : 1);
      } else if (token === '(') {
        value = expression();
        expect(')');
      } else if (token === 'SUM') {
        expect('(');
        value = 0;
        if (tokens[index] !== ')') {
          value = sumArgument();
          while (tokens[index] === ',') { index += 1; value = finite(value + sumArgument()); }
        }
        expect(')');
      } else if (token && NUMBER.test(token)) {
        value = Number(token);
      } else if (token && /^[A-D][1-9]\d*$/.test(token)) {
        value = reference(token);
      } else {
        throw calculationError('#FORMULA!', 'Use numbers, A1:D100 references, arithmetic, or SUM.');
      }
      depth -= 1;
      return finite(value);
    }

    function product() {
      let value = primary();
      while (tokens[index] === '*' || tokens[index] === '/') {
        const operation = tokens[index++];
        const right = primary();
        if (operation === '/' && right === 0) throw calculationError('#DIV/0!', 'A formula divides by zero.');
        value = finite(operation === '*' ? value * right : value / right);
      }
      return value;
    }

    function expression() {
      let value = product();
      while (tokens[index] === '+' || tokens[index] === '-') {
        const operation = tokens[index++];
        const right = product();
        value = finite(operation === '+' ? value + right : value - right);
      }
      return value;
    }

    const result = expression();
    if (index !== tokens.length) throw calculationError('#FORMULA!', 'Check the formula syntax.');
    return result;
  }

  function mount(document) {
    function element(id) { return document.getElementById(id); }

    const calculatorResult = element('calculator-result');
    const ratioInput = element('ratio-input');
    const dbInput = element('db-input');
    const ratioKind = element('ratio-kind');

    function convert(direction) {
      try {
        const input = direction === 'decibels' ? ratioInput : dbInput;
        if (input.value.trim() === '') throw new Error('Enter a number to convert.');
        const value = Number(input.value);
        if (direction === 'decibels') {
          const decibels = ratioToDecibels(value, ratioKind.value);
          dbInput.value = numberText(decibels);
          calculatorResult.textContent = (ratioKind.value === 'amplitude' ? 'Amplitude' : 'Power') +
            ' ratio ' + numberText(value) + ' = ' + numberText(decibels) + ' dB.';
        } else {
          const ratio = decibelsToRatio(value, ratioKind.value);
          ratioInput.value = numberText(ratio);
          calculatorResult.textContent = numberText(value) + ' dB = ' + ratioKind.value +
            ' ratio ' + numberText(ratio) + '.';
        }
        calculatorResult.classList.remove('error');
      } catch (error) {
        calculatorResult.textContent = error.message;
        calculatorResult.classList.add('error');
      }
    }

    element('decibel-form').addEventListener('submit', function (event) {
      event.preventDefault(); convert('decibels');
    });
    element('to-ratio').addEventListener('click', function () { convert('ratio'); });
    dbInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); convert('ratio'); }
    });
    ratioKind.addEventListener('change', function () { convert('decibels'); });
    convert('decibels');

    function newSheet(id, name, values) {
      return {id: id, name: name, rows: values.map(function (cells, index) {
        return {id: String(index + 1), cells: cells};
      }), nextRow: values.length + 1, selected: {rowId: '1', column: 1},
      revision: 0, request: 0, status: 'Select a cell to inspect or edit its value.'};
    }

    const sheets = {
      measurements: newSheet('measurements', 'Measurements', [
        ['Reference', '1', '0', 'Reference level'],
        ['Double', '2', '6.0206', 'Amplitude ratio ×2'],
        ['Half', '0.5', '-6.0206', 'Amplitude ratio ÷2'],
        ['Totals', '=SUM(B1:B3)', '=C2+C3', 'Edit a number or a formula']
      ]),
      notes: newSheet('notes', 'Notes', [
        ['Task', 'State', 'Owner', 'Next step'],
        ['Inspect levels', 'Ready', 'You', 'Select a cell'],
        ['Review note', 'Draft', 'You', 'Try the rich editor'],
        ['Keep offline', 'Local', 'You', 'All resources are bundled']
      ])
    };
    let activeId = 'measurements';
    const body = element('sheet-body');
    const formulaInput = element('formula-input');
    const sheetStatus = element('sheet-status');
    let formulaBaseline = '';

    function activeSheet() { return sheets[activeId]; }
    function rowIndex(sheet, rowId) { return sheet.rows.findIndex(function (row) { return row.id === rowId; }); }
    function selectedAddress(sheet) {
      return String.fromCharCode(65 + sheet.selected.column) + String(rowIndex(sheet, sheet.selected.rowId) + 1);
    }
    function selectedRow(sheet) { return sheet.rows[rowIndex(sheet, sheet.selected.rowId)]; }

    function evaluator(sheet) {
      const visiting = new Set();
      const cache = new Map();
      function read(name) {
        const address = cellAddress(name);
        if (address.row >= sheet.rows.length) throw calculationError('#REF!', 'This row does not exist.');
        if (cache.has(name)) return cache.get(name);
        if (visiting.has(name)) throw calculationError('#CYCLE!', 'The formula refers back to itself.');
        visiting.add(name);
        try {
          const raw = sheet.rows[address.row].cells[address.column];
          const value = raw.startsWith('=') ? evaluateFormula(raw, read) : raw;
          cache.set(name, value);
          return value;
        } finally { visiting.delete(name); }
      }
      return read;
    }

    function displayValue(sheet, row, column, read) {
      const raw = sheet.rows[row].cells[column];
      if (!raw.startsWith('=')) return {text: raw, error: false};
      try {
        return {text: numberText(numericCell(read(String.fromCharCode(65 + column) + String(row + 1)))), error: false};
      } catch (error) { return {text: error.code || '#FORMULA!', error: true}; }
    }

    function refreshDisplays() {
      const sheet = activeSheet();
      const read = evaluator(sheet);
      body.querySelectorAll('input.cell-editor').forEach(function (input) {
        const row = rowIndex(sheet, input.dataset.rowId);
        const value = displayValue(sheet, row, Number(input.dataset.column), read);
        if (input.readOnly) input.value = value.text;
        input.closest('td').classList.toggle('cell-error', value.error);
        input.setAttribute('aria-invalid', String(value.error));
      });
    }

    function refreshSelection() {
      const sheet = activeSheet();
      const address = selectedAddress(sheet);
      element('selection-label').textContent = address;
      element('selection-label').title = sheet.name + ' · ' + address;
      element('selection-label').setAttribute('aria-label', 'Selected cell: ' + sheet.name + ' ' + address);
      if (document.activeElement !== formulaInput) formulaInput.value = selectedRow(sheet).cells[sheet.selected.column];
      body.querySelectorAll('td[data-cell]').forEach(function (cell) {
        const selected = cell.dataset.rowId === sheet.selected.rowId && Number(cell.dataset.column) === sheet.selected.column;
        cell.classList.toggle('selected', selected);
        cell.setAttribute('aria-selected', String(selected));
      });
      element('remove-row').disabled = sheet.rows.length <= 1;
      element('add-row').disabled = sheet.rows.length >= MAX_ROWS;
      sheetStatus.textContent = sheet.status;
    }

    function changed(sheet, raw, rowId, column) {
      const row = sheet.rows[rowIndex(sheet, rowId)];
      if (raw.length > MAX_CELL_LENGTH) raw = raw.slice(0, MAX_CELL_LENGTH);
      if (row.cells[column] !== raw) {
        row.cells[column] = raw;
        sheet.revision += 1;
        sheet.request += 1;
      }
      sheet.status = 'Editing ' + selectedAddress(sheet) + '. Changes stay in this document.';
      refreshDisplays();
      refreshSelection();
    }

    function focusCell(row, column) {
      const sheet = activeSheet();
      row = Math.max(0, Math.min(sheet.rows.length - 1, row));
      column = Math.max(0, Math.min(3, column));
      const input = body.querySelector('input[data-row-id="' + sheet.rows[row].id + '"][data-column="' + column + '"]');
      input.focus();
      input.select();
    }

    function renderSheet(focusSelection) {
      const sheet = activeSheet();
      const fragment = document.createDocumentFragment();
      sheet.rows.forEach(function (row, rowNumber) {
        const tr = document.createElement('tr');
        const heading = document.createElement('th');
        heading.scope = 'row';
        heading.textContent = String(rowNumber + 1);
        tr.appendChild(heading);
        row.cells.forEach(function (raw, column) {
          const td = document.createElement('td');
          td.dataset.cell = String.fromCharCode(65 + column) + String(rowNumber + 1);
          td.dataset.rowId = row.id;
          td.dataset.column = String(column);
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'cell-editor';
          input.dataset.rowId = row.id;
          input.dataset.column = String(column);
          input.maxLength = MAX_CELL_LENGTH;
          input.readOnly = true;
          input.setAttribute('aria-label', sheet.name + ' ' + td.dataset.cell);
          let baseline = raw;

          function beginEdit() {
            if (!input.readOnly) return;
            baseline = row.cells[column];
            input.readOnly = false;
            input.value = baseline;
            input.select();
            sheet.status = 'Editing ' + td.dataset.cell + '. Enter commits; Escape restores the previous value.';
            refreshSelection();
          }

          function finishEdit(cancel) {
            if (cancel) changed(sheet, baseline, row.id, column);
            input.readOnly = true;
            sheet.status = td.dataset.cell + (cancel ? ' restored.' : ' selected. Press Enter to edit.');
            refreshDisplays();
            refreshSelection();
          }

          input.addEventListener('focus', function () {
            sheet.selected = {rowId: row.id, column: column};
            sheet.status = td.dataset.cell + ' selected. Press Enter to edit.';
            refreshSelection();
          });
          input.addEventListener('dblclick', beginEdit);
          input.addEventListener('paste', beginEdit);
          input.addEventListener('input', function () {
            changed(sheet, input.value, row.id, column);
            formulaInput.value = row.cells[column];
          });
          input.addEventListener('blur', function () { if (!input.readOnly) finishEdit(false); });
          input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === 'F2') {
              event.preventDefault();
              if (input.readOnly) beginEdit();
              else { finishEdit(false); focusCell(rowIndex(sheet, row.id) + 1, column); }
            } else if (event.key === 'Escape' && !input.readOnly) {
              event.preventDefault(); finishEdit(true);
            } else if (input.readOnly && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
              event.preventDefault();
              focusCell(rowIndex(sheet, row.id) + (event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0),
                        column + (event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0));
            } else if (input.readOnly && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
              event.preventDefault(); beginEdit(); input.value = event.key;
              changed(sheet, input.value, row.id, column); formulaInput.value = input.value;
            } else if (input.readOnly && (event.key === 'Backspace' || event.key === 'Delete')) {
              event.preventDefault(); beginEdit(); input.value = '';
              changed(sheet, '', row.id, column); formulaInput.value = '';
            }
          });
          td.appendChild(input);
          tr.appendChild(td);
        });
        fragment.appendChild(tr);
      });
      body.replaceChildren(fragment);
      element('sheet-caption').textContent = sheet.name + ' worksheet';
      element('sheet-panel').setAttribute('aria-labelledby', 'sheet-tab-' + sheet.id);
      document.querySelectorAll('[data-sheet]').forEach(function (tab) {
        const active = tab.dataset.sheet === sheet.id;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      refreshDisplays();
      refreshSelection();
      if (focusSelection) focusCell(rowIndex(sheet, sheet.selected.rowId), sheet.selected.column);
    }

    document.querySelectorAll('[data-sheet]').forEach(function (tab) {
      tab.addEventListener('click', function () { activeId = tab.dataset.sheet; renderSheet(false); });
      tab.addEventListener('keydown', function (event) {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 'measurements' : event.key === 'End' ? 'notes' :
          (activeId === 'measurements' ? 'notes' : 'measurements');
        activeId = next; renderSheet(false); element('sheet-tab-' + next).focus();
      });
    });
    formulaInput.maxLength = MAX_CELL_LENGTH;
    formulaInput.addEventListener('focus', function () {
      const sheet = activeSheet(); formulaBaseline = selectedRow(sheet).cells[sheet.selected.column];
    });
    formulaInput.addEventListener('input', function () {
      const sheet = activeSheet(); changed(sheet, formulaInput.value, sheet.selected.rowId, sheet.selected.column);
    });
    formulaInput.addEventListener('keydown', function (event) {
      const sheet = activeSheet();
      if (event.key === 'Enter') {
        event.preventDefault(); focusCell(rowIndex(sheet, sheet.selected.rowId), sheet.selected.column);
      } else if (event.key === 'Escape') {
        event.preventDefault(); changed(sheet, formulaBaseline, sheet.selected.rowId, sheet.selected.column);
        formulaInput.value = formulaBaseline;
        focusCell(rowIndex(sheet, sheet.selected.rowId), sheet.selected.column);
      }
    });
    element('add-row').addEventListener('click', function () {
      const sheet = activeSheet();
      if (sheet.rows.length >= MAX_ROWS) return;
      const row = {id: String(sheet.nextRow++), cells: ['', '', '', '']};
      sheet.rows.push(row); sheet.selected.rowId = row.id;
      sheet.revision += 1; sheet.request += 1;
      sheet.status = 'Added row ' + sheet.rows.length + '.';
      renderSheet(true);
    });
    element('remove-row').addEventListener('click', function () {
      const sheet = activeSheet();
      if (sheet.rows.length <= 1) return;
      const index = rowIndex(sheet, sheet.selected.rowId);
      sheet.rows.splice(index, 1);
      sheet.selected.rowId = sheet.rows[Math.min(index, sheet.rows.length - 1)].id;
      sheet.revision += 1; sheet.request += 1;
      sheet.status = 'Removed row ' + (index + 1) + '; references use current row positions.';
      renderSheet(true);
    });
    element('recalculate').addEventListener('click', function () {
      const sheet = activeSheet();
      const request = ++sheet.request;
      const revision = sheet.revision;
      sheet.status = 'Recalculating this worksheet locally…'; refreshSelection();
      setTimeout(function () {
        if (sheet.request !== request || sheet.revision !== revision) return;
        const read = evaluator(sheet);
        let errors = 0;
        sheet.rows.forEach(function (row, index) {
          row.cells.forEach(function (_, column) { if (displayValue(sheet, index, column, read).error) errors += 1; });
        });
        sheet.status = 'Local recalculation complete: ' + (sheet.rows.length * 4) + ' cells, ' + errors + ' formula errors.';
        if (activeId === sheet.id) { refreshDisplays(); refreshSelection(); }
      }, 150);
    });
    renderSheet(false);

    function mountServices() {
      const heading = element('service-heading');
      const description = element('service-description');
      const indicator = element('service-indicator');
      const features = [
        {name: 'demo.echo', schema: Uint8Array.from({length: 32}, function (_, index) { return index + 1; }),
          maxReplyBytes: 1024, button: element('service-read'), status: element('service-status'),
          readyText: 'Ready to read the selected cell.', unavailableText: 'Read service unavailable.'},
        {name: 'org.example.increment', schema: Uint8Array.from([
          0x3f,0xe7,0xab,0x0d,0x3f,0x8f,0x76,0x49,0x9f,0x05,0x4c,0xa6,0xf2,0x9f,0x68,0xde,
          0xee,0x28,0x62,0x76,0x81,0xf7,0x92,0x31,0xaf,0x3b,0x09,0x5b,0x06,0x35,0xb2,0x46]),
          maxReplyBytes: 8, button: element('service-increment'), status: element('provider-status'),
          readyText: 'Select a whole number from 0 to 4294967295.', unavailableText: 'Counter service unavailable.'}
      ];
      let alive = true, epoch = 0;

      function current(token) { return alive && token === epoch; }
      function buttons() {
        features.forEach(function (feature) {
          feature.button.disabled = !alive || !feature.ready || feature.busy;
          feature.button.setAttribute('aria-busy', String(Boolean(feature.busy)));
        });
      }
      function status(feature, message, error) {
        feature.status.textContent = message;
        feature.status.classList.toggle('error', Boolean(error));
      }
      function availability() {
        const connected = features.some(function (feature) { return feature.ready; });
        heading.textContent = connected ? 'Application services ready' : 'Application services unavailable';
        description.textContent = features[0].ready && features[1].ready ? 'Read a selected cell, or increment a selected whole number.' :
          features[0].ready ? 'Read a selected cell. The counter service is unavailable.' :
          features[1].ready ? 'Increment a selected whole number. The read service is unavailable.' :
          'Neither notebook service is available in this session.';
        indicator.textContent = connected ? '✓' : '○';
        indicator.dataset.connected = String(connected);
      }
      function failure(error) {
        if (error && error.code === '#SERVICE!') return error.message;
        if (error && error.status === 14) return 'The outcome is unknown. Reload before making another request.';
        if (error && error.status === 10) return 'This service connection has closed.';
        if (error && error.status === 8) return 'The service cannot accept this request right now.';
        return 'The service request could not be completed.';
      }
      function selectedValue() {
        const sheet = activeSheet();
        const value = displayValue(sheet, rowIndex(sheet, sheet.selected.rowId), sheet.selected.column, evaluator(sheet));
        if (value.error) throw calculationError('#SERVICE!', 'Fix the selected cell formula before sending it.');
        return {sheet: sheet, revision: sheet.revision, rowId: sheet.selected.rowId,
          column: sheet.selected.column, address: selectedAddress(sheet), text: value.text};
      }
      function stillSelected(selection) {
        return activeSheet() === selection.sheet && selection.sheet.revision === selection.revision &&
          selection.sheet.selected.rowId === selection.rowId && selection.sheet.selected.column === selection.column;
      }
      async function connect() {
        const token = ++epoch;
        features.forEach(function (feature) {
          feature.ready = false; feature.busy = false; feature.service = null;
          status(feature, feature.unavailableText, false);
        });
        heading.textContent = 'Kernel services unavailable';
        description.textContent = 'No service connection is available in this session.';
        indicator.textContent = '○'; indicator.dataset.connected = 'false';
        buttons();
        let discover;
        try {
          const host = globalThis.foundation;
          if (host && typeof host.discover === 'function') discover = host.discover.bind(host);
        } catch (_) { discover = null; }
        if (!discover) return;
        heading.textContent = 'Connecting application services';
        description.textContent = 'Checking which services are available in this session.';
        await Promise.all(features.map(async function (feature) {
          status(feature, 'Looking for this service…', false);
          try {
            const service = await discover(feature.name, {major: 1, minMinor: 0, maxMinor: 0, schema: feature.schema});
            if (!current(token)) return;
            const contract = service && service.descriptor;
            const schema = contract && contract.schema;
            if (!contract || typeof service.call !== 'function' || contract.name !== feature.name ||
                contract.major !== 1 || contract.minor !== 0 || contract.maxReplyBytes !== feature.maxReplyBytes ||
                !(schema instanceof Uint8Array) || schema.length !== 32 ||
                !feature.schema.every(function (byte, index) { return byte === schema[index]; })) {
              throw calculationError('#SERVICE!', 'The service contract does not match this notebook.');
            }
            feature.service = service; feature.ready = true;
            status(feature, feature.readyText, false);
          } catch (_) {
            if (current(token)) status(feature, feature.unavailableText, false);
          } finally { if (current(token)) buttons(); }
        }));
        if (!current(token)) return;
        availability();
      }
      features.forEach(function (feature, index) {
        feature.button.addEventListener('click', async function () {
          if (!alive || !feature.ready || feature.busy) return;
          const token = epoch;
          feature.busy = true; buttons();
          try {
            const selection = selectedValue();
            let payload, operand;
            if (index === 0) {
              payload = new TextEncoder().encode(selection.text);
              if (payload.length > 1024) throw calculationError('#SERVICE!', 'Select a value that fits within 1024 UTF-8 bytes.');
            } else {
              if (selection.text.trim() === '') throw calculationError('#SERVICE!', feature.readyText);
              try { operand = numericCell(selection.text); }
              catch (_) { throw calculationError('#SERVICE!', feature.readyText); }
              if (!Number.isInteger(operand) || operand < 0 || operand > 4294967295) {
                throw calculationError('#SERVICE!', feature.readyText);
              }
              payload = new Uint8Array(4); new DataView(payload.buffer).setUint32(0, operand, true);
            }
            status(feature, 'Sending ' + selection.sheet.name + ' ' + selection.address + '…', false);
            const response = await feature.service.call(1, payload);
            if (!current(token)) return;
            if (!(response instanceof Uint8Array) || response.length !== (index === 0 ? payload.length : 8) ||
                (index === 0 && !payload.every(function (byte, offset) { return response[offset] === byte; }))) {
              feature.ready = false;
              throw calculationError('#SERVICE!', 'The service returned an unexpected response. Reload before another request.');
            }
            const bytes = new Uint8Array(response);
            let result;
            if (index === 0) result = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(bytes);
            else {
              const values = new DataView(bytes.buffer);
              if (values.getUint32(0, true) !== ((operand + 1) >>> 0)) {
                feature.ready = false;
                throw calculationError('#SERVICE!', 'The counter returned an unexpected value. Reload before another request.');
              }
              result = values.getUint32(0, true) + '; completed increments: ' + values.getUint32(4, true);
            }
            if (!stillSelected(selection)) {
              status(feature, index === 0 ? 'Selection changed. Read the selected cell again.' :
                'Selection changed. The previous increment completed.', false);
            } else status(feature, selection.sheet.name + ' ' + selection.address + ': ' + result, false);
          } catch (error) {
            if (current(token)) {
              if (error && [7, 10, 13, 14].includes(error.status)) feature.ready = false;
              status(feature, failure(error), true);
            }
          } finally {
            if (current(token)) { feature.busy = false; buttons(); availability(); }
          }
        });
      });
      const page = document.defaultView;
      if (page) {
        page.addEventListener('pagehide', function () { alive = false; ++epoch; buttons(); });
        page.addEventListener('pageshow', function (event) {
          if (event.persisted) { alive = true; connect(); }
        });
      }
      connect();
    }
    mountServices();

    const editor = element('rich-editor');
    const editorStatus = element('editor-status');
    let savedRange = null;

    function rememberSelection() {
      const selection = document.getSelection();
      if (selection && selection.rangeCount && editor.contains(selection.anchorNode) && editor.contains(selection.focusNode)) {
        savedRange = selection.getRangeAt(0).cloneRange();
        editorStatus.textContent = selection.isCollapsed ? 'Caret ready. Type to edit your note.' :
          selection.toString().length + ' characters selected.';
      }
    }

    function edit(command, value) {
      editor.focus();
      const selection = document.getSelection();
      if (savedRange && editor.contains(savedRange.commonAncestorContainer) && selection) {
        selection.removeAllRanges(); selection.addRange(savedRange);
      }
      if (typeof document.execCommand !== 'function') {
        editorStatus.textContent = 'This document host does not provide this formatting command.';
        return;
      }
      try {
        const changed = document.execCommand(command, false, value || null);
        rememberSelection();
        editorStatus.textContent = changed ? 'Applied ' + command + '.' : 'No change from ' + command + '.';
      } catch (error) {
        editorStatus.textContent = 'Formatting command unavailable: ' + error.message;
      }
    }

    document.addEventListener('selectionchange', rememberSelection);
    document.querySelectorAll('[data-edit-command]').forEach(function (button) {
      button.addEventListener('mousedown', function (event) { event.preventDefault(); });
      button.addEventListener('click', function () { edit(button.dataset.editCommand); });
    });
    element('editor-block').addEventListener('change', function (event) {
      edit('formatBlock', event.target.value);
    });
    editor.addEventListener('input', function () {
      rememberSelection();
      editorStatus.textContent = 'Note edited · ' + editor.textContent.length + ' characters. Changes stay in this document.';
    });
  }

  return Object.freeze({ratioToDecibels: ratioToDecibels, decibelsToRatio: decibelsToRatio,
                        evaluateFormula: evaluateFormula, mount: mount});
}());

if (typeof document !== 'undefined') FoundationAppendedFixture.mount(document);
