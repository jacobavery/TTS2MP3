/**
 * Text editor with word count and file drag-and-drop upload.
 */
import { api } from '../api.js';
import { $ } from '../utils/dom.js';

const WPM_ESTIMATE = 150;

export function initEditor() {
  const textarea = $('#text-editor');
  const wordCount = $('#word-count');
  const fileInput = $('#file-input');
  const fileLabel = $('#file-label');
  const dropZone = $('#editor-area');
  const clearBtn = $('#clear-text-btn');
  const pasteBtn = $('#paste-text-btn');

  function updateWordCount() {
    const text = textarea.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    const chars = text.length;
    const estMins = Math.ceil(words / WPM_ESTIMATE);
    wordCount.textContent = `${words.toLocaleString()} words · ${chars.toLocaleString()} chars · ~${estMins} min audio`;
  }

  textarea.addEventListener('input', updateWordCount);

  // File upload
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    await uploadAndPopulate(file);
  });

  // Drag and drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) await uploadAndPopulate(file);
  });

  // Clear / Paste
  clearBtn.addEventListener('click', () => {
    textarea.value = '';
    fileLabel.textContent = '';
    updateWordCount();
  });

  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      textarea.value = text;
      updateWordCount();
    } catch {
      // Clipboard API blocked
    }
  });

  async function uploadAndPopulate(file) {
    fileLabel.textContent = `Loading ${file.name}...`;
    try {
      const result = await api.uploadFile(file);
      textarea.value = result.text;
      fileLabel.textContent = `${result.filename} — ${result.words.toLocaleString()} words`;
      updateWordCount();
    } catch (err) {
      fileLabel.textContent = `Error: ${err.message}`;
    }
  }

  updateWordCount();
}

export function getEditorText() {
  return $('#text-editor').value;
}
