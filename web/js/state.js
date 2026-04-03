/**
 * Simple observable state store using CustomEvent.
 */
class Store {
  constructor() {
    this._state = {
      voices: [],
      filteredVoices: [],
      chosenVoice: null,
      favorites: new Set(),
      settings: {},
      currentJob: null,
      allVoices: [],
      audioUrl: null,
      systemStatus: null,
    };
    this._target = new EventTarget();
  }

  get(key) {
    return this._state[key];
  }

  set(key, value) {
    this._state[key] = value;
    this._target.dispatchEvent(new CustomEvent('change', { detail: { key, value } }));
  }

  on(key, callback) {
    this._target.addEventListener('change', (e) => {
      if (e.detail.key === key) callback(e.detail.value);
    });
  }

  onAny(callback) {
    this._target.addEventListener('change', (e) => callback(e.detail.key, e.detail.value));
  }
}

export const store = new Store();
