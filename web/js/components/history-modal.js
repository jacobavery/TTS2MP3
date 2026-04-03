/**
 * Conversion history modal.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { openModal, closeModal } from './modal.js';

export async function showHistoryModal() {
  const body = document.createElement('div');
  body.innerHTML = '<div class="history-empty">Loading...</div>';

  const footer = document.createElement('div');
  footer.style.display = 'contents';
  const clearBtn = document.createElement('button');
  clearBtn.className = 'modal-btn danger';
  clearBtn.textContent = 'Clear All';
  clearBtn.addEventListener('click', async () => {
    await api.clearHistory();
    renderHistory(body, []);
  });
  footer.appendChild(clearBtn);

  openModal({ title: 'Conversion History', body, footer });

  try {
    const { records } = await api.getHistory(50);
    renderHistory(body, records);
  } catch {
    body.innerHTML = '<div class="history-empty">Failed to load history.</div>';
  }
}

function renderHistory(container, history) {
  if (!history.length) {
    container.innerHTML = '<div class="history-empty">No conversion history yet.</div>';
    return;
  }

  const list = document.createElement('div');
  list.className = 'history-list';

  for (const item of history) {
    const row = document.createElement('div');
    row.className = 'history-item';

    const textSnippet = (item.text || '').slice(0, 80) + ((item.text || '').length > 80 ? '...' : '');
    const voice = item.voice || 'Unknown';
    const fmt = item.format || 'MP3';
    const date = item.timestamp ? new Date(item.timestamp * 1000).toLocaleString() : '';

    row.innerHTML = `
      <div class="history-info">
        <div class="history-text">${escapeHtml(textSnippet)}</div>
        <div class="history-meta">${escapeHtml(voice)} &middot; ${fmt} &middot; ${date}</div>
      </div>
      <div class="history-actions">
        <button class="history-reuse">Reuse</button>
      </div>
    `;

    row.querySelector('.history-reuse').addEventListener('click', () => {
      // Load this conversion's text into the editor
      const editor = document.querySelector('#text-editor');
      if (editor && item.text) {
        editor.value = item.text;
        editor.dispatchEvent(new Event('input'));
      }
      closeModal();
    });

    list.appendChild(row);
  }

  container.innerHTML = '';
  container.appendChild(list);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
