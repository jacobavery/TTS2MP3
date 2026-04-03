/**
 * Voice comparison modal — synthesize same text with multiple voices side by side.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { openModal, closeModal } from './modal.js';

const MAX_VOICES = 6;

export function showCompareModal() {
  const voices = store.get('allVoices') || [];
  if (!voices.length) {
    alert('Voices not loaded yet.');
    return;
  }

  const body = document.createElement('div');
  body.innerHTML = `
    <div class="cmp-text-row">
      <label class="cmp-label">Sample text</label>
      <textarea id="cmp-text" class="cmp-textarea" rows="3" placeholder="Enter text to compare...">The quick brown fox jumps over the lazy dog. This is a voice comparison test.</textarea>
    </div>
    <div class="cmp-voices-section">
      <label class="cmp-label">Select voices to compare (2–6)</label>
      <div class="cmp-voice-picker">
        <input type="text" id="cmp-voice-search" class="pron-input" placeholder="Search voices...">
        <div id="cmp-voice-list" class="cmp-voice-list"></div>
      </div>
      <div id="cmp-selected" class="cmp-selected-tags"></div>
    </div>
    <div id="cmp-results" class="cmp-results hidden"></div>
  `;

  const footer = document.createElement('div');
  footer.style.display = 'contents';
  footer.innerHTML = `
    <span id="cmp-summary" class="batch-summary"></span>
    <button class="modal-btn" id="cmp-cancel">Close</button>
    <button class="modal-btn primary" id="cmp-start" disabled>Compare</button>
  `;

  openModal({ title: 'Voice Comparison', body, footer });

  const selected = new Set();
  const textArea = body.querySelector('#cmp-text');
  const searchInput = body.querySelector('#cmp-voice-search');
  const voiceList = body.querySelector('#cmp-voice-list');
  const selectedDiv = body.querySelector('#cmp-selected');
  const resultsDiv = body.querySelector('#cmp-results');
  const summaryEl = footer.querySelector('#cmp-summary');
  const startBtn = footer.querySelector('#cmp-start');
  const cancelBtn = footer.querySelector('#cmp-cancel');

  cancelBtn.addEventListener('click', closeModal);
  startBtn.addEventListener('click', startCompare);

  function renderVoiceList(filter = '') {
    const q = filter.toLowerCase();
    const filtered = voices.filter(v =>
      v.ShortName.toLowerCase().includes(q) ||
      (v.Locale || '').toLowerCase().includes(q)
    ).slice(0, 50);

    voiceList.innerHTML = filtered.map(v => `
      <div class="cmp-voice-option ${selected.has(v.ShortName) ? 'selected' : ''}" data-name="${v.ShortName}">
        <span>${escapeHtml(v.ShortName)}</span>
        <span class="ab-ch-words">${v.Gender} · ${v.Locale}</span>
      </div>
    `).join('');

    voiceList.querySelectorAll('.cmp-voice-option').forEach(el => {
      el.addEventListener('click', () => {
        const name = el.dataset.name;
        if (selected.has(name)) {
          selected.delete(name);
        } else if (selected.size < MAX_VOICES) {
          selected.add(name);
        }
        renderVoiceList(searchInput.value);
        renderSelected();
      });
    });
  }

  function renderSelected() {
    selectedDiv.innerHTML = [...selected].map(name => `
      <span class="cmp-tag">${escapeHtml(name)} <button class="cmp-tag-remove" data-name="${name}">&times;</button></span>
    `).join('');
    selectedDiv.querySelectorAll('.cmp-tag-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        selected.delete(btn.dataset.name);
        renderVoiceList(searchInput.value);
        renderSelected();
      });
    });
    summaryEl.textContent = `${selected.size} voice${selected.size !== 1 ? 's' : ''} selected`;
    startBtn.disabled = selected.size < 2;
  }

  searchInput.addEventListener('input', () => renderVoiceList(searchInput.value));
  renderVoiceList();
  renderSelected();

  async function startCompare() {
    const text = textArea.value.trim();
    if (!text) { alert('Enter some text.'); return; }

    startBtn.disabled = true;
    resultsDiv.classList.remove('hidden');
    resultsDiv.innerHTML = '<p style="color:var(--text-muted)">Generating samples...</p>';

    try {
      const { jobs } = await api.compareVoices({
        text,
        voices: [...selected],
      });

      // Poll all jobs
      resultsDiv.innerHTML = jobs.map(j => `
        <div class="cmp-result-item" data-job="${j.job_id}">
          <span class="cmp-result-voice">${escapeHtml(j.voice)}</span>
          <span class="cmp-result-status">Generating...</span>
          <audio class="cmp-audio hidden" controls preload="none"></audio>
        </div>
      `).join('');

      const poll = setInterval(async () => {
        let allDone = true;
        for (const j of jobs) {
          const el = resultsDiv.querySelector(`[data-job="${j.job_id}"]`);
          if (!el) continue;
          try {
            const status = await api.getJobStatus(j.job_id);
            const statusEl = el.querySelector('.cmp-result-status');
            const audioEl = el.querySelector('.cmp-audio');
            if (status.status === 'done') {
              statusEl.textContent = '';
              audioEl.src = status.download_url;
              audioEl.classList.remove('hidden');
            } else if (status.status === 'error') {
              statusEl.textContent = 'Failed';
              statusEl.style.color = 'var(--red)';
            } else {
              allDone = false;
            }
          } catch {
            allDone = false;
          }
        }
        if (allDone) clearInterval(poll);
      }, 1000);
    } catch (e) {
      resultsDiv.innerHTML = `<p style="color:var(--red)">Error: ${escapeHtml(e.message)}</p>`;
    }
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
