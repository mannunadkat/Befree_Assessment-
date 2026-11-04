/**
 * Main Application Orchestrator & Router for AuraBank.
 */
import { state } from './state.js';
import { api } from './api.js';
import { initTheme } from './theme.js';
import { initUpload } from './upload.js';
import { initOverview } from './overview.js';
import { initTable, renderTable } from './table.js';
import { initCharts } from './charts.js';
import { initValidation } from './validation.js';
import { initExport } from './export.js';
import { showToast } from './toast.js';

const VIEW_TITLES = {
  upload: 'Upload & Ingest',
  overview: 'Account Overview',
  transactions: 'Transaction Ledger',
  analytics: 'Financial Analytics',
  validation: 'Balance Integrity',
  export: 'Export Intelligence'
};

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Initialize Submodules
  initTheme();
  initUpload();
  initOverview();
  initTable();
  initCharts();
  initValidation();
  initExport();

  // 2. Setup Router
  initRouter();

  // 3. Setup Sidebar Collapse
  initSidebar();

  // 4. Setup Command Palette
  initCommandPalette();

  // 5. Global Keyboard Shortcuts
  initKeyboardShortcuts();

  // 6. Check OCR Health
  checkOcrHealth();

  // 7. Render Lucide Icons
  if (window.lucide) {
    window.lucide.createIcons();
  }
});

function initRouter() {
  const switchView = (hash) => {
    const viewName = (hash || '#upload').replace('#', '').toLowerCase();
    const validViews = ['upload', 'overview', 'transactions', 'analytics', 'validation', 'export'];
    const activeView = validViews.includes(viewName) ? viewName : 'upload';

    // Update active nav link
    document.querySelectorAll('.nav-item[data-view]').forEach(item => {
      if (item.getAttribute('data-view') === activeView) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Update view sections
    document.querySelectorAll('.view').forEach(v => {
      v.classList.remove('active');
    });

    const targetEl = document.getElementById(`view-${activeView}`);
    if (targetEl) {
      targetEl.classList.add('active');
      if (window.gsap) {
        window.gsap.fromTo(targetEl, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.3, ease: 'power2.out' });
      }
    }

    // Update topbar title
    const titleEl = document.getElementById('topbar-title');
    if (titleEl) {
      titleEl.textContent = VIEW_TITLES[activeView] || 'Statement Intelligence';
    }

    if (activeView === 'transactions') {
      renderTable();
    }

    state.set('currentView', activeView);
  };

  window.addEventListener('hashchange', () => {
    switchView(window.location.hash);
  });

  // Initial route
  switchView(window.location.hash);
}

function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const toggleBtn = document.getElementById('sidebar-toggle');

  if (sidebar && toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      const isCollapsed = sidebar.classList.contains('collapsed');
      toggleBtn.querySelector('.nav-label').textContent = isCollapsed ? 'Expand' : 'Collapse';
    });
  }
}

function initCommandPalette() {
  const modal = document.getElementById('cmd-palette-modal');
  const btnTrigger = document.getElementById('btn-cmd-palette');
  const searchInput = document.getElementById('cmd-search-input');
  const resultsContainer = document.getElementById('cmd-results');

  const openPalette = () => {
    if (modal) {
      modal.classList.add('open');
      if (searchInput) {
        searchInput.value = '';
        searchInput.focus();
      }
    }
  };

  const closePalette = () => {
    if (modal) modal.classList.remove('open');
  };

  if (btnTrigger) btnTrigger.addEventListener('click', openPalette);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closePalette();
    });
  }

  // Filter commands
  if (searchInput && resultsContainer) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      resultsContainer.querySelectorAll('.nav-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
      });
    });
  }

  // Execute command
  if (resultsContainer) {
    resultsContainer.querySelectorAll('.nav-item[data-action]').forEach(item => {
      item.addEventListener('click', () => {
        const action = item.getAttribute('data-action');
        closePalette();
        handleCommandAction(action);
      });
    });
  }
}

function handleCommandAction(action) {
  if (action.startsWith('nav:')) {
    const view = action.split(':')[1];
    window.location.hash = `#${view}`;
  } else if (action === 'action:demo') {
    const btn = document.getElementById('btn-load-demo');
    if (btn) btn.click();
  } else if (action === 'action:theme') {
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.click();
  } else if (action === 'action:retrain') {
    const btn = document.getElementById('btn-retrain-model');
    if (btn) btn.click();
  }
}

let keySeq = '';
function initKeyboardShortcuts() {
  window.addEventListener('keydown', (e) => {
    // Ignore when typing in inputs/textareas
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      if (e.key === 'Escape') {
        document.activeElement.blur();
        closeAllModals();
      }
      return;
    }

    // Cmd+K or Ctrl+K -> Command Palette
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const modal = document.getElementById('cmd-palette-modal');
      if (modal) {
        if (modal.classList.contains('open')) {
          modal.classList.remove('open');
        } else {
          modal.classList.add('open');
          const input = document.getElementById('cmd-search-input');
          if (input) { input.value = ''; input.focus(); }
        }
      }
      return;
    }

    // Slash "/" -> Focus table search
    if (e.key === '/') {
      e.preventDefault();
      window.location.hash = '#transactions';
      setTimeout(() => {
        const searchInput = document.getElementById('txn-search-input');
        if (searchInput) searchInput.focus();
      }, 100);
      return;
    }

    // Escape -> Close modals / drawers
    if (e.key === 'Escape') {
      closeAllModals();
      return;
    }

    // Navigation hotkeys: "g then t" -> transactions, "g then o" -> overview, etc.
    keySeq += e.key.toLowerCase();
    if (keySeq.length > 2) keySeq = keySeq.slice(-2);

    if (keySeq === 'gt') { window.location.hash = '#transactions'; keySeq = ''; }
    if (keySeq === 'go') { window.location.hash = '#overview'; keySeq = ''; }
    if (keySeq === 'ga') { window.location.hash = '#analytics'; keySeq = ''; }
    if (keySeq === 'gu') { window.location.hash = '#upload'; keySeq = ''; }
    if (keySeq === 'gv') { window.location.hash = '#validation'; keySeq = ''; }
    if (keySeq === 'ge') { window.location.hash = '#export'; keySeq = ''; }
  });
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  const drawer = document.getElementById('detail-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
}

async function checkOcrHealth() {
  try {
    const health = await api.checkHealth();
    const pill = document.getElementById('ocr-status-pill');
    const text = document.getElementById('ocr-status-text');

    if (pill && text) {
      pill.style.display = 'inline-flex';
      if (health.tesseract_installed) {
        pill.className = 'chip chip-success';
        text.textContent = 'Tesseract OCR Ready';
      } else {
        pill.className = 'chip chip-warning';
        text.textContent = 'OCR Binary Missing';
        pill.title = 'Install Tesseract OCR to support scanned image PDFs (brew install tesseract / apt-get install tesseract-ocr)';
      }
      if (window.lucide) window.lucide.createIcons();
    }
  } catch (err) {
    console.warn('Could not query OCR health:', err);
  }
}
