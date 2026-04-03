/**
 * Conversion progress bar — SSE consumer.
 */
import { $ } from '../utils/dom.js';
import { connectSSE } from '../utils/sse.js';
import { api } from '../api.js';
import { store } from '../state.js';

export function initProgress() {
  // UI elements bound during startProgress
}

export function startProgress(jobId) {
  const progressEl = $('#progress-area');
  const progressBar = $('#progress-bar');
  const progressText = $('#progress-text');
  const convertBtn = $('#convert-btn');

  progressEl.classList.remove('hidden');
  progressBar.style.width = '0%';
  progressText.textContent = 'Starting...';
  convertBtn.disabled = true;

  const source = connectSSE(api.jobStreamUrl(jobId), {
    onProgress: (data) => {
      const pct = data.pct || 0;
      progressBar.style.width = `${pct}%`;
      progressText.textContent = `Converting... ${pct}%`;
    },
    onDone: (data) => {
      progressBar.style.width = '100%';
      progressText.textContent = 'Done!';
      convertBtn.disabled = false;
      if (data.download_url) {
        store.set('audioUrl', data.download_url);
      }
    },
    onError: (data) => {
      progressText.textContent = `Error: ${data.error || 'Unknown'}`;
      progressBar.style.width = '0%';
      convertBtn.disabled = false;
    },
  });

  store.set('currentJob', { id: jobId, source });
}
