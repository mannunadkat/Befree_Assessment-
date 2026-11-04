/**
 * Theme Manager for AuraBank.
 * Handles dark/light switching, localStorage persistence, and system preference changes.
 */
import { state } from './state.js';

export function initTheme() {
  const currentTheme = state.get('theme');
  applyTheme(currentTheme);

  const toggleBtn = document.getElementById('theme-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const active = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = active === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      state.set('theme', next);
    });
  }

  // Listen to OS theme changes if user hasn't explicitly set preference
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('aurabank_theme')) {
      const osTheme = e.matches ? 'dark' : 'light';
      applyTheme(osTheme);
      state.set('theme', osTheme);
    }
  });
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('aurabank_theme', theme);

  const iconEl = document.getElementById('theme-icon');
  if (iconEl && window.lucide) {
    if (theme === 'light') {
      iconEl.setAttribute('data-lucide', 'sun');
    } else {
      iconEl.setAttribute('data-lucide', 'moon');
    }
    window.lucide.createIcons();
  }
}
