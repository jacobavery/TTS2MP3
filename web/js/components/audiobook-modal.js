/**
 * Audiobook builder modal — upload EPUB, select chapters, convert to M4B.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { openModal, closeModal } from './modal.js';

export function showAudiobookModal() {
  const voice = store.get('chosenVoice');
  if (!voice) {
    alert('Please select a voice first.');
    return;
  }

  const body = document.createElement('div');
  body.innerHTML = `
    <div class="ab-upload-zone" id="ab-drop">
      <div class="batch-upload-icon">&#128214;</div>
      <p>Drop an EPUB file here, or</p>
      <label class="modal-btn primary batch-browse-btn">
        Browse
        <input type="file" id="ab-file-input" accept=".epub" hidden>
      </label>
    </div>
    <div id="ab-chapters" class="ab-chapters hidden"></div>
    <div id="ab-progress" class="ab-progress hidden">
      <div class="batch-item-bar"><div id="ab-fill" class="batch-item-fill" style="width:0%"></div></div>
      <span id="ab-status" class="ab-status-text">Converting...</span>
    </div>
  `;

  const footer = document.createElement('div');
  footer.style.display = 'contents';
  footer.innerHTML = `
    <span id="ab-summary" class="batch-summary"></span>
    <button class="modal-btn" id="ab-cancel">Close</button>
    <button class="modal-btn primary" id="ab-convert" disabled>Convert to M4B</button>
  `;

  openModal({ title: 'Audiobook Builder', body, footer });

  const dropZone = body.querySelector('#ab-drop');
  const fileInput = body.querySelector('#ab-file-input');
  const chaptersDiv = body.querySelector('#ab-chapters');
  const progressDiv = body.querySelector('#ab-progress');
  const fill = body.querySelector('#ab-fill');
  const statusText = body.querySelector('#ab-status');
  const summaryEl = footer.querySelector('#ab-summary');
  const convertBtn = footer.querySelector('#ab-convert');
  const cancelBtn = footer.querySelector('#ab-cancel');

  let epubPath = null;
  let chapters = [];

  // Drag and drop
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) uploadEpub(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) uploadEpub(fileInput.files[0]);
  });
  cancelBtn.addEventListener('click', closeModal);
  convertBtn.addEventListener('click', startConvert);

  async function uploadEpub(file) {
    if (!file.name.toLowerCase().endsWith('.epub')) {
      alert('Please select an EPUB file.');
      return;
    }
    dropZone.innerHTML = '<p style="color:var(--text-muted)">Reading chapters...</p>';

    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/api/audiobook/chapters', { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      epubPath = data.epub_path;
      chapters = data.chapters;
      renderChapters(data.metadata);
    } catch (e) {
      dropZone.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
    }
  }

  function renderChapters(metadata) {
    dropZone.classList.add('hidden');
    chaptersDiv.classList.remove('hidden');

    const metaHtml = metadata?.title
      ? `<div class="ab-meta"><strong>${escapeHtml(metadata.title)}</strong>${metadata.author ? ` by ${escapeHtml(metadata.author)}` : ''}</div>`
      : '';

    chaptersDiv.innerHTML = `
      ${metaHtml}
      <div class="ab-actions-row">
        <button class="modal-btn" id="ab-select-all">Select All</button>
        <button class="modal-btn" id="ab-select-none">Select None</button>
      </div>
      <div class="ab-chapter-list">
        ${chapters.map((ch, i) => `
          <label class="ab-chapter-item">
            <input type="checkbox" checked data-idx="${i}">
            <span class="ab-ch-title">${escapeHtml(ch.title)}</span>
            <span class="ab-ch-words">${ch.words} words</span>
          </label>
        `).join('')}
      </div>
    `;

    chaptersDiv.querySelector('#ab-select-all').addEventListener('click', () => {
      chaptersDiv.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = true);
      updateSummary();
    });
    chaptersDiv.querySelector('#ab-select-none').addEventListener('click', () => {
      chaptersDiv.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = false);
      updateSummary();
    });
    chaptersDiv.querySelectorAll('input[type=checkbox]').forEach(cb => {
      cb.addEventListener('change', updateSummary);
    });

    convertBtn.disabled = false;
    updateSummary();
  }

  function updateSummary() {
    const selected = chaptersDiv.querySelectorAll('input[type=checkbox]:checked').length;
    summaryEl.textContent = `${selected}/${chapters.length} chapters selected`;
    convertBtn.disabled = selected === 0;
  }

  async function startConvert() {
    const selected = [...chaptersDiv.querySelectorAll('input[type=checkbox]:checked')]
      .map(cb => parseInt(cb.dataset.idx));
    if (!selected.length) return;

    convertBtn.disabled = true;
    chaptersDiv.classList.add('hidden');
    progressDiv.classList.remove('hidden');
    statusText.textContent = 'Converting chapters...';

    try {
      const res = await fetch('/api/audiobook/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          epub_path: epubPath,
          selected_chapters: selected,
          voice: voice.ShortName,
          rate: '+0%',
          pitch: '+0Hz',
          volume: '+0%',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const { job_id } = await res.json();

      // Poll for progress
      const poll = setInterval(async () => {
        try {
          const status = await api.getJobStatus(job_id);
          fill.style.width = `${status.progress}%`;
          statusText.textContent = `Converting... ${status.progress}%`;

          if (status.status === 'done') {
            clearInterval(poll);
            fill.style.width = '100%';
            statusText.innerHTML = `Done! <a href="${status.download_url}" download class="batch-dl">Download M4B</a>`;
          } else if (status.status === 'error') {
            clearInterval(poll);
            statusText.textContent = `Error: ${status.error}`;
            statusText.style.color = 'var(--red)';
          }
        } catch { /* ignore */ }
      }, 1000);
    } catch (e) {
      statusText.textContent = `Error: ${e.message}`;
      statusText.style.color = 'var(--red)';
    }
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
