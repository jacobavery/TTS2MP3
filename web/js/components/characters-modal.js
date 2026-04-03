/**
 * Character voices modal — detect characters, assign voices, multi-voice convert.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { openModal, closeModal } from './modal.js';
import { getEditorText } from './editor.js';
import { startProgress } from './progress.js';

export function showCharactersModal() {
  const text = getEditorText();
  if (!text.trim()) {
    alert('Enter some text in the editor first (use CHARACTER: Name format).');
    return;
  }
  const defaultVoice = store.get('chosenVoice');
  if (!defaultVoice) {
    alert('Please select a default voice first.');
    return;
  }

  const body = document.createElement('div');
  body.innerHTML = `
    <p class="cmp-label">Detecting characters in text (looking for NAME: patterns)...</p>
    <div id="char-list" class="char-list"></div>
  `;

  const footer = document.createElement('div');
  footer.style.display = 'contents';
  footer.innerHTML = `
    <span class="batch-summary" id="char-summary"></span>
    <button class="modal-btn" id="char-cancel">Close</button>
    <button class="modal-btn primary" id="char-convert" disabled>Convert</button>
  `;

  openModal({ title: 'Character Voices', body, footer });

  const charListDiv = body.querySelector('#char-list');
  const summaryEl = footer.querySelector('#char-summary');
  const convertBtn = footer.querySelector('#char-convert');
  const cancelBtn = footer.querySelector('#char-cancel');

  cancelBtn.addEventListener('click', closeModal);

  const voices = store.get('allVoices') || [];
  const assignments = {};

  // Detect characters
  detectCharacters(text);

  async function detectCharacters(text) {
    try {
      const { characters } = await api.detectCharacters({ text });
      if (!characters.length) {
        charListDiv.innerHTML = `
          <div class="pron-empty">
            No characters detected.<br>
            <small>Use the format <code>CHARACTER NAME: dialogue text</code> in your text.</small>
          </div>
        `;
        return;
      }

      charListDiv.innerHTML = `
        <p style="margin-bottom:10px;font-size:0.82rem;color:var(--text-muted)">
          Assign a voice to each character. Default voice: <strong>${escapeHtml(defaultVoice.ShortName)}</strong>
        </p>
        ${characters.map(name => `
          <div class="char-row">
            <span class="char-name">${escapeHtml(name)}</span>
            <select class="select-input char-voice-select" data-char="${escapeHtml(name)}">
              <option value="">(Default voice)</option>
              ${voices.map(v => `<option value="${v.ShortName}">${v.ShortName}</option>`).join('')}
            </select>
          </div>
        `).join('')}
      `;

      charListDiv.querySelectorAll('.char-voice-select').forEach(sel => {
        sel.addEventListener('change', () => {
          const char = sel.dataset.char;
          if (sel.value) {
            assignments[char] = sel.value;
          } else {
            delete assignments[char];
          }
        });
      });

      summaryEl.textContent = `${characters.length} characters found`;
      convertBtn.disabled = false;
      convertBtn.addEventListener('click', () => startCharConvert(characters));
    } catch (e) {
      charListDiv.innerHTML = `<p style="color:var(--red)">Error: ${escapeHtml(e.message)}</p>`;
    }
  }

  async function startCharConvert(characters) {
    // Build final assignments — fill in default voice for unassigned
    const finalAssignments = {};
    for (const name of characters) {
      finalAssignments[name] = assignments[name] || defaultVoice.ShortName;
    }

    convertBtn.disabled = true;

    try {
      const { job_id } = await api.convertCharacters({
        text,
        assignments: finalAssignments,
        default_voice: defaultVoice.ShortName,
      });
      closeModal();
      startProgress(job_id);
    } catch (e) {
      alert(`Conversion failed: ${e.message}`);
      convertBtn.disabled = false;
    }
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
