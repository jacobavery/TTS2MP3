/**
 * Voice panel: search, filter, list, preview, favorites.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { $, debounce, el } from '../utils/dom.js';

let previewAudio = null;

export function initVoicePanel() {
  const searchInput = $('#voice-search');
  const langSelect = $('#voice-lang');
  const genderBtns = $$('#voice-filters .filter-pill');
  const favBtn = $('#voice-fav-only');
  const voiceList = $('#voice-list');

  let currentGender = 'All';
  let favOnly = false;

  // Load languages
  api.getLanguages().then(({ languages }) => {
    langSelect.innerHTML = '<option value="All">All Languages</option>';
    for (const { locale, name } of languages) {
      langSelect.innerHTML += `<option value="${locale}">${name} (${locale})</option>`;
    }
  });

  // Filter logic
  const applyFilter = debounce(async () => {
    const { voices } = await api.getVoices({
      search: searchInput.value,
      language: langSelect.value,
      gender: currentGender,
      favorites_only: favOnly,
    });
    store.set('filteredVoices', voices);
    renderVoices(voices);
  }, 200);

  searchInput.addEventListener('input', applyFilter);
  langSelect.addEventListener('change', applyFilter);

  // Gender pills
  document.querySelectorAll('#voice-filters .filter-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#voice-filters .filter-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentGender = btn.dataset.gender;
      applyFilter();
    });
  });

  // Favorites only
  favBtn.addEventListener('click', () => {
    favOnly = !favOnly;
    favBtn.classList.toggle('active', favOnly);
    applyFilter();
  });

  // Render voice list
  function renderVoices(voices) {
    voiceList.innerHTML = '';
    const favorites = store.get('favorites');
    const chosen = store.get('chosenVoice');

    for (const v of voices) {
      const isChosen = chosen && chosen.ShortName === v.ShortName;
      const isFav = favorites.has(v.ShortName);
      const displayName = v.ShortName.split('-').length >= 3
        ? v.ShortName.split('-')[2].replace('Neural', '').replace('Multilingual', '')
        : v.ShortName;
      const backendIcon = v.Backend === 'macos' ? '⊕' : '☁';
      const backendClass = v.Backend === 'macos' ? 'offline' : 'cloud';

      const row = el('div', { class: `voice-row${isChosen ? ' selected' : ''}` }, [
        el('span', { class: `voice-badge ${backendClass}`, text: backendIcon }),
        el('div', { class: 'voice-info' }, [
          el('div', { class: 'voice-name', text: displayName }),
          el('div', { class: 'voice-meta', text: `${v.Locale} · ${v.Gender}` }),
        ]),
        el('button', {
          class: `voice-fav-btn${isFav ? ' active' : ''}`,
          text: '★',
          onclick: async (e) => {
            e.stopPropagation();
            const result = await api.toggleFavorite(v.ShortName);
            store.set('favorites', new Set(result.favorites));
            applyFilter();
          },
        }),
        el('button', {
          class: 'voice-preview-btn',
          text: '▶',
          onclick: (e) => {
            e.stopPropagation();
            playPreview(v.ShortName);
          },
        }),
      ]);

      row.addEventListener('click', () => {
        store.set('chosenVoice', v);
        renderVoices(voices);
      });

      voiceList.appendChild(row);
    }
  }

  // Preview
  function playPreview(name) {
    if (previewAudio) {
      previewAudio.pause();
      previewAudio = null;
    }
    previewAudio = new Audio(api.previewUrl(name));
    previewAudio.play().catch(() => {});
  }

  // Listen for state changes
  store.on('chosenVoice', () => {
    const voices = store.get('filteredVoices');
    if (voices.length) renderVoices(voices);
  });

  store.on('favorites', () => {
    const voices = store.get('filteredVoices');
    if (voices.length) renderVoices(voices);
  });

  // Initial load
  applyFilter();
}

function $$(...args) {
  return [...document.querySelectorAll(...args)];
}
