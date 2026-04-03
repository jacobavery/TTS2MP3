/**
 * Pronunciation dictionary editor modal.
 */
import { api } from '../api.js';
import { openModal } from './modal.js';

export async function showPronunciationModal() {
  const body = document.createElement('div');
  body.innerHTML = '<div class="pron-empty">Loading...</div>';

  openModal({ title: 'Pronunciation Dictionary', body });

  try {
    const { entries: pronunciations } = await api.getPronunciations();
    renderTable(body, pronunciations);
  } catch {
    body.innerHTML = '<div class="pron-empty">Failed to load pronunciations.</div>';
  }
}

function renderTable(container, pronunciations) {
  container.innerHTML = '';

  const table = document.createElement('table');
  table.className = 'pron-table';

  // Header
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Find</th><th>Replace With</th><th></th></tr>';
  table.appendChild(thead);

  const tbody = document.createElement('tbody');

  // Existing entries
  pronunciations.forEach((p, i) => {
    const tr = makeRow(p.find, p.replace, i, tbody, container);
    tbody.appendChild(tr);
  });

  // Add-new row
  const addRow = document.createElement('tr');
  addRow.className = 'pron-add-row';
  addRow.innerHTML = `
    <td><input class="pron-input" id="pron-new-find" placeholder="e.g. TTS"></td>
    <td><input class="pron-input" id="pron-new-replace" placeholder="e.g. T T S"></td>
    <td><button class="modal-btn primary" id="pron-add-btn">Add</button></td>
  `;
  tbody.appendChild(addRow);
  table.appendChild(tbody);
  container.appendChild(table);

  // Add handler
  container.querySelector('#pron-add-btn').addEventListener('click', async () => {
    const findInput = container.querySelector('#pron-new-find');
    const replaceInput = container.querySelector('#pron-new-replace');
    const find = findInput.value.trim();
    const replace = replaceInput.value.trim();
    if (!find) { findInput.focus(); return; }

    try {
      const { entries: updated } = await api.addPronunciation({ find, replace });
      renderTable(container, updated);
    } catch (e) {
      alert('Failed to add: ' + e.message);
    }
  });

  // Enter key on inputs
  ['pron-new-find', 'pron-new-replace'].forEach(id => {
    container.querySelector(`#${id}`).addEventListener('keydown', (e) => {
      if (e.key === 'Enter') container.querySelector('#pron-add-btn').click();
    });
  });

  if (!pronunciations.length) {
    const hint = document.createElement('p');
    hint.className = 'pron-empty';
    hint.style.paddingBottom = '0';
    hint.textContent = 'No entries yet. Add find/replace rules below.';
    container.insertBefore(hint, table);
  }
}

function makeRow(find, replace, index, tbody, container) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${escapeHtml(find)}</td>
    <td>${escapeHtml(replace)}</td>
    <td><button class="pron-delete" title="Delete">&times;</button></td>
  `;

  tr.querySelector('.pron-delete').addEventListener('click', async () => {
    try {
      const { entries: updated } = await api.deletePronunciation(index);
      renderTable(container, updated);
    } catch (e) {
      alert('Failed to delete: ' + e.message);
    }
  });

  return tr;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
