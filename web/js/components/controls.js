/**
 * Conversion controls: format, quality, speed, pitch, volume, options.
 */
import { $ } from '../utils/dom.js';

const QUALITY_PRESETS = {
  MP3:  ['Standard (128k)', 'High (192k)', 'Maximum (320k)'],
  WAV:  [],
  FLAC: [],
  AAC:  ['Standard (128k)', 'High (192k)'],
  M4B:  ['Standard (96k)', 'High (128k)'],
  OGG:  ['Standard (q4)', 'High (q7)'],
  OPUS: ['Standard (96k)', 'High (128k)', 'Maximum (192k)'],
};

export function initControls() {
  const formatSelect = $('#format-select');
  const qualitySelect = $('#quality-select');
  const speedSlider = $('#speed-slider');
  const pitchSlider = $('#pitch-slider');
  const volumeSlider = $('#volume-slider');
  const speedVal = $('#speed-val');
  const pitchVal = $('#pitch-val');
  const volumeVal = $('#volume-val');

  // Populate quality when format changes
  formatSelect.addEventListener('change', () => {
    updateQualityOptions(formatSelect.value);
  });

  function updateQualityOptions(fmt) {
    const presets = QUALITY_PRESETS[fmt] || [];
    qualitySelect.innerHTML = '';
    if (presets.length === 0) {
      qualitySelect.innerHTML = '<option value="">Default</option>';
      qualitySelect.disabled = true;
    } else {
      qualitySelect.disabled = false;
      for (const p of presets) {
        qualitySelect.innerHTML += `<option value="${p}">${p}</option>`;
      }
      // Default to second option (High) if available
      if (presets.length >= 2) qualitySelect.selectedIndex = 1;
    }
  }

  // Slider labels
  speedSlider.addEventListener('input', () => {
    const v = parseInt(speedSlider.value);
    speedVal.textContent = `${v >= 0 ? '+' : ''}${v}%`;
  });
  pitchSlider.addEventListener('input', () => {
    const v = parseInt(pitchSlider.value);
    pitchVal.textContent = `${v >= 0 ? '+' : ''}${v}Hz`;
  });
  volumeSlider.addEventListener('input', () => {
    const v = parseInt(volumeSlider.value);
    volumeVal.textContent = `${v >= 0 ? '+' : ''}${v}%`;
  });

  // Initialize
  updateQualityOptions(formatSelect.value);
}

export function getControlValues() {
  return {
    format: $('#format-select').value,
    quality: $('#quality-select').value,
    rate: `${parseInt($('#speed-slider').value) >= 0 ? '+' : ''}${$('#speed-slider').value}%`,
    pitch: `${parseInt($('#pitch-slider').value) >= 0 ? '+' : ''}${$('#pitch-slider').value}Hz`,
    volume: `${parseInt($('#volume-slider').value) >= 0 ? '+' : ''}${$('#volume-slider').value}%`,
    normalize_text: $('#normalize-text').checked,
    normalize_audio: $('#normalize-audio').checked,
    para_pause: parseFloat($('#para-pause').value),
  };
}
