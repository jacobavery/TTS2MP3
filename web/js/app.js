/**
 * App initialization — wire up all components.
 */
import { api } from './api.js';
import { store } from './state.js';
import { $ } from './utils/dom.js';
import { initVoicePanel } from './components/voice-panel.js';
import { initEditor, getEditorText } from './components/editor.js';
import { initControls, getControlValues } from './components/controls.js';
import { initPlayer } from './components/player.js';
import { initProgress, startProgress } from './components/progress.js';
import { showHistoryModal } from './components/history-modal.js';
import { showPronunciationModal } from './components/pronunciation-modal.js';
import { showBatchModal } from './components/batch-modal.js';
import { showAudiobookModal } from './components/audiobook-modal.js';
import { showCompareModal } from './components/compare-modal.js';
import { showCharactersModal } from './components/characters-modal.js';

async function init() {
  // Load initial data
  const [{ favorites }, status, { voices: allVoices }] = await Promise.all([
    api.getFavorites(),
    api.getSystemStatus(),
    api.getVoices({}),
  ]);
  store.set('favorites', new Set(favorites));
  store.set('systemStatus', status);
  store.set('allVoices', allVoices);

  // Update status bar
  $('#status-voices').textContent = `${status.voice_count} voices`;
  $('#status-cache').textContent = `Cache: ${status.cache_size_mb} MB`;
  $('#status-ffmpeg').textContent = status.ffmpeg ? 'ffmpeg ✓' : 'ffmpeg ✗';

  // Initialize components
  initVoicePanel();
  initEditor();
  initControls();
  initPlayer();
  initProgress();

  // Convert button
  $('#convert-btn').addEventListener('click', handleConvert);

  // Nav buttons
  $('#btn-batch').addEventListener('click', showBatchModal);
  $('#btn-audiobook').addEventListener('click', showAudiobookModal);
  $('#btn-compare').addEventListener('click', showCompareModal);
  $('#btn-characters').addEventListener('click', showCharactersModal);
  $('#btn-history').addEventListener('click', showHistoryModal);
  $('#btn-pronunciation').addEventListener('click', showPronunciationModal);

  // Chosen voice display
  store.on('chosenVoice', (v) => {
    if (v) {
      const name = v.ShortName.split('-').length >= 3
        ? v.ShortName.split('-')[2].replace('Neural', '').replace('Multilingual', '')
        : v.ShortName;
      $('#chosen-voice-label').textContent = `${name} (${v.Locale})`;
    }
  });
}

async function handleConvert() {
  const voice = store.get('chosenVoice');
  if (!voice) {
    alert('Please select a voice first.');
    return;
  }

  const text = getEditorText();
  if (!text.trim()) {
    alert('Please enter or upload some text.');
    return;
  }

  const controls = getControlValues();

  try {
    store.set('audioUrl', null);
    const { job_id } = await api.startConversion({
      text,
      voice: voice.ShortName,
      ...controls,
    });
    startProgress(job_id);
  } catch (err) {
    alert(`Conversion failed: ${err.message}`);
  }
}

// Boot
document.addEventListener('DOMContentLoaded', init);
