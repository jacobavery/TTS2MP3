// ===== Nav scroll effect =====
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
});

// ===== Mobile nav toggle =====
const navToggle = document.getElementById('nav-toggle');
const navMobile = document.getElementById('nav-mobile');
navToggle.addEventListener('click', () => {
  navMobile.classList.toggle('open');
});
navMobile.querySelectorAll('a').forEach(a => {
  a.addEventListener('click', () => navMobile.classList.remove('open'));
});

// ===== Stat counter animation =====
function animateCounters() {
  document.querySelectorAll('.stat-num').forEach(el => {
    const target = parseInt(el.dataset.target);
    if (!target || el.dataset.done) return;

    const rect = el.getBoundingClientRect();
    if (rect.top > window.innerHeight) return;

    el.dataset.done = '1';
    const duration = 1500;
    const start = performance.now();

    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(target * eased);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}
window.addEventListener('scroll', animateCounters);
animateCounters();

// ===== Scroll-triggered animations =====
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 80);
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.15 }
);
document.querySelectorAll('[data-aos]').forEach(el => observer.observe(el));

// ===== Waveform bars =====
const waveContainer = document.querySelector('.wave-bars');
if (waveContainer) {
  for (let i = 0; i < 40; i++) {
    const bar = document.createElement('span');
    bar.style.animationDelay = `${i * 0.05}s`;
    bar.style.animationDuration = `${0.8 + Math.random() * 0.8}s`;
    waveContainer.appendChild(bar);
  }
}

// ===== Copy button =====
const copyBtn = document.getElementById('copy-btn');
const installCode = document.getElementById('install-code');
if (copyBtn && installCode) {
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(installCode.textContent).then(() => {
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
    });
  });
}

// ===== Smooth scroll for anchor links =====
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', (e) => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});
