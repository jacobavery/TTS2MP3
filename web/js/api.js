/**
 * API client — thin wrapper around fetch() for all backend endpoints.
 */
const API_BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Voices
  getVoices: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/voices${qs ? '?' + qs : ''}`);
  },
  getStaffPicks: () => request('/voices/staff-picks'),
  getLanguages: () => request('/voices/languages'),
  previewUrl: (name) => `${API_BASE}/voices/preview/${encodeURIComponent(name)}`,

  // Conversion
  startConversion: (body) => request('/convert', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  getJobStatus: (id) => request(`/jobs/${id}`),
  jobStreamUrl: (id) => `${API_BASE}/jobs/${id}/stream`,
  jobDownloadUrl: (id) => `${API_BASE}/jobs/${id}/download`,

  // Upload
  uploadFile: async (file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // Settings
  getSettings: () => request('/settings'),
  updateSettings: (settings) => request('/settings', {
    method: 'PUT',
    body: JSON.stringify({ settings }),
  }),

  // Favorites
  getFavorites: () => request('/favorites'),
  toggleFavorite: (voice) => request('/favorites/toggle', {
    method: 'POST',
    body: JSON.stringify({ voice }),
  }),

  // Pronunciations
  getPronunciations: () => request('/pronunciations'),
  addPronunciation: (entry) => request('/pronunciations', {
    method: 'POST',
    body: JSON.stringify(entry),
  }),
  updatePronunciation: (index, entry) => request(`/pronunciations/${index}`, {
    method: 'PUT',
    body: JSON.stringify(entry),
  }),
  deletePronunciation: (index) => request(`/pronunciations/${index}`, {
    method: 'DELETE',
  }),

  // History
  getHistory: (limit = 50) => request(`/history?limit=${limit}`),
  clearHistory: () => request('/history', { method: 'DELETE' }),

  // Batch
  startBatch: (body) => request('/batch/convert', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  getBatchStatus: (jobIds) => request(`/batch/status?job_ids=${jobIds.join(',')}`),

  // Compare
  compareVoices: (body) => request('/voices/compare', {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  // Characters
  detectCharacters: (body) => request('/characters/detect', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  convertCharacters: (body) => request('/characters/convert', {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  // Projects
  getProjects: () => request('/projects'),
  deleteProject: (filename) => request(`/projects/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  }),
  saveProject: (body) => request('/projects/save', {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  // System
  getSystemStatus: () => request('/system/status'),
  clearCache: () => request('/cache/clear', { method: 'POST' }),
};
