/**
 * HTML5 audio player with custom controls.
 */
import { $, formatTime } from '../utils/dom.js';
import { store } from '../state.js';

let audio = null;

export function initPlayer() {
  const playerEl = $('#audio-player');
  const playBtn = $('#player-play');
  const seekBar = $('#player-seek');
  const timeDisplay = $('#player-time');
  const downloadBtn = $('#player-download');

  playBtn.addEventListener('click', () => {
    if (!audio) return;
    if (audio.paused) {
      audio.play();
      playBtn.textContent = '⏸';
    } else {
      audio.pause();
      playBtn.textContent = '▶';
    }
  });

  seekBar.addEventListener('input', () => {
    if (audio) audio.currentTime = parseFloat(seekBar.value);
  });

  store.on('audioUrl', (url) => {
    if (!url) {
      playerEl.classList.add('hidden');
      return;
    }

    playerEl.classList.remove('hidden');

    if (audio) audio.pause();
    audio = new Audio(url);
    playBtn.textContent = '▶';

    audio.addEventListener('loadedmetadata', () => {
      seekBar.max = audio.duration;
      timeDisplay.textContent = `0:00 / ${formatTime(audio.duration)}`;
    });

    audio.addEventListener('timeupdate', () => {
      seekBar.value = audio.currentTime;
      timeDisplay.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration || 0)}`;
    });

    audio.addEventListener('ended', () => {
      playBtn.textContent = '▶';
    });

    downloadBtn.href = url;
    downloadBtn.download = 'output.mp3';
  });
}
