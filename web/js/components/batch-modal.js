/**
 * Batch conversion modal — upload multiple files, convert all with shared settings.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { openModal, closeModal } from './modal.js';
import { getControlValues } from './controls.js';

let pollTimer = null;

export function showBatchModal() {
  const voice = store.get('chosenVoice');
  if (!voice) {
    alert('Please select a voice first.');
    return;
  }

  const body = document.createElement('div');
  body.innerHTML = `
    <div class="batch-upload-zone" id="batch-drop">
      <div class="batch-upload-icon">&#128194;</div>
      <p>Drag &amp; drop files here, or</p>
      <label class="modal-btn primary batch-browse-btn">
        Browse Files
        <input type="file" id="batch-file-input" multiple accept=".txt,.rtf,.epub,.pdf,.md" hidden>
      </label>
      <p class="batch-hint">Supports TXT, RTF, EPUB, PDF, Markdown &middot; Max 20 files</p>
    </div>
    <div id="batch-queue" class="batch-queue hidden"></div>
  `;

  const footer = document.createElement('div');
  footer.style.display = 'contents';
  footer.innerHTML = `
    <span id="batch-summary" class="batch-summary"></span>
    <button class="modal-btn" id="batch-cancel-btn">Close</button>
    <button class="modal-btn primary" id="batch-start-btn" disabled>Convert All</button>
  `;

  openModal({ title: 'Batch Conversion', body, footer });

  const files = [];
  const dropZone = body.querySelector('#batch-drop');
  const fileInput = body.querySelector('#batch-file-input');
  const queue = body.querySelector('#batch-queue');
  const startBtn = footer.querySelector('#batch-start-btn');
  const cancelBtn = footer.querySelector('#batch-cancel-btn');
  const summary = footer.querySelector('#batch-summary');

  // Drag and drop
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });

  fileInput.addEventListener('change', () => {
    addFiles(fileInput.files);
    fileInput.value = '';
  });

  cancelBtn.addEventListener('click', () => {
    if (pollTimer) clearInterval(pollTimer);
    closeModal();
  });

  startBtn.addEventListener('click', () => startBatch());

  function addFiles(fileList) {
    for (const f of fileList) {
      if (files.length >= 20) break;
      if (files.some(x => x.file.name === f.name)) continue;
      files.push({ file: f, text: null, status: 'pending', progress: 0, jobId: null, error: null });
    }
    renderQueue();
    uploadAll();
  }

  async function uploadAll() {
    for (const item of files) {
      if (item.text !== null) continue;
      item.status = 'uploading';
      renderQueue();
      try {
        const result = await api.uploadFile(item.file);
        item.text = result.text;
        item.words = result.words;
        item.status = 'ready';
      } catch (e) {
        item.status = 'error';
        item.error = `Upload failed: ${e.message}`;
      }
      renderQueue();
    }
  }

  function renderQueue() {
    if (!files.length) {
      queue.classList.add('hidden');
      dropZone.classList.remove('hidden');
      startBtn.disabled = true;
      summary.textContent = '';
      return;
    }

    dropZone.classList.add('hidden');
    queue.classList.remove('hidden');
    startBtn.disabled = !files.some(f => f.status === 'ready');

    const ready = files.filter(f => f.status === 'ready').length;
    const done = files.filter(f => f.status === 'done').length;
    const total = files.length;
    summary.textContent = done > 0 ? `${done}/${total} complete` : `${ready}/${total} ready`;

    queue.innerHTML = files.map((item, i) => `
      <div class="batch-item" data-idx="${i}">
        <div class="batch-item-info">
          <span class="batch-filename">${escapeHtml(item.file.name)}</span>
          <span class="batch-meta">${item.words ? item.words + ' words' : ''}</span>
        </div>
        <div class="batch-item-progress">
          <div class="batch-item-bar">
            <div class="batch-item-fill" style="width:${item.progress}%"></div>
          </div>
        </div>
        <div class="batch-item-status ${item.status}">
          ${statusLabel(item)}
        </div>
        ${item.status === 'done' ? `<a href="${item.downloadUrl}" class="batch-dl" download>&#8681;</a>` : ''}
        ${['pending','ready','uploading'].includes(item.status) ? `<button class="pron-delete batch-remove" data-idx="${i}">&times;</button>` : ''}
      </div>
    `).join('');

    // Remove buttons
    queue.querySelectorAll('.batch-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        files.splice(parseInt(btn.dataset.idx), 1);
        renderQueue();
      });
    });
  }

  function statusLabel(item) {
    switch (item.status) {
      case 'pending': return 'Pending';
      case 'uploading': return 'Reading...';
      case 'ready': return 'Ready';
      case 'converting': return `${item.progress}%`;
      case 'done': return '&#10003; Done';
      case 'error': return `&#10007; ${escapeHtml(item.error || 'Error')}`;
      default: return item.status;
    }
  }

  async function startBatch() {
    const controls = getControlValues();
    const readyItems = files.filter(f => f.status === 'ready');
    if (!readyItems.length) return;

    startBtn.disabled = true;
    readyItems.forEach(f => { f.status = 'converting'; f.progress = 0; });
    renderQueue();

    try {
      const { job_ids } = await api.startBatch({
        items: readyItems.map(f => ({ filename: f.file.name, text: f.text })),
        voice: voice.ShortName,
        ...controls,
      });

      // Map job IDs back to items
      readyItems.forEach((f, i) => { f.jobId = job_ids[i]; });

      // Poll for progress
      pollTimer = setInterval(async () => {
        const active = files.filter(f => f.jobId && f.status === 'converting');
        if (!active.length) {
          clearInterval(pollTimer);
          pollTimer = null;
          return;
        }
        try {
          const { jobs } = await api.getBatchStatus(active.map(f => f.jobId));
          for (const j of jobs) {
            const item = files.find(f => f.jobId === j.job_id);
            if (!item) continue;
            item.progress = j.progress;
            if (j.status === 'done') {
              item.status = 'done';
              item.progress = 100;
              item.downloadUrl = j.download_url;
            } else if (j.status === 'error') {
              item.status = 'error';
              item.error = j.error || 'Conversion failed';
            }
          }
          renderQueue();
        } catch { /* ignore poll errors */ }
      }, 1000);

    } catch (e) {
      readyItems.forEach(f => { f.status = 'error'; f.error = e.message; });
      renderQueue();
    }
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
