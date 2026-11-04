/**
 * Upload & File Selection Manager for AuraBank.
 */
import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './toast.js';
import { startPipelineWatcher } from './pipeline.js';

let pendingPasswordFile = null;

export function initUpload() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const btnBrowse = document.getElementById('btn-browse-files');
  const btnUploadDemo = document.getElementById('btn-upload-demo');
  const btnLoadDemoTop = document.getElementById('btn-load-demo');
  const btnClearQueue = document.getElementById('btn-clear-queue');
  const btnProcessQueue = document.getElementById('btn-process-queue');
  const queueCard = document.getElementById('queue-card');
  const queueList = document.getElementById('queue-list');
  const queueMeta = document.getElementById('queue-meta');

  // Drag and drop event listeners
  if (dropZone) {
    ['dragenter', 'dragover'].forEach(name => {
      dropZone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropZone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      const allowed = ['.pdf', '.csv', '.json'];
      const files = Array.from(e.dataTransfer.files).filter(f => allowed.some(ext => f.name.toLowerCase().endsWith(ext)));
      if (files.length === 0) {
        showToast('Invalid File', 'Please drop PDF, CSV, or JSON statement files.', 'warning');
        return;
      }
      addFilesToQueue(files);
    });

    dropZone.addEventListener('click', (e) => {
      if (e.target.closest('#btn-browse-files') || e.target.closest('#btn-upload-demo')) return;
      fileInput.click();
    });
  }

  if (btnBrowse && fileInput) {
    btnBrowse.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      const allowed = ['.pdf', '.csv', '.json'];
      const files = Array.from(e.target.files).filter(f => allowed.some(ext => f.name.toLowerCase().endsWith(ext)));
      addFilesToQueue(files);
      fileInput.value = '';
    });
  }

  if (btnClearQueue) {
    btnClearQueue.addEventListener('click', () => {
      state.set('selectedFiles', []);
      renderQueue();
    });
  }

  // Load demo statements
  const runDemo = async () => {
    try {
      showToast('Loading Demo', 'Synthesizing statement and running pipeline...', 'info');
      const res = await api.loadDemo();
      state.set('currentJobId', res.job_id);
      startPipelineWatcher(res.job_id);
    } catch (err) {
      showToast('Demo Failed', err.message, 'error');
    }
  };

  if (btnUploadDemo) btnUploadDemo.addEventListener('click', runDemo);
  if (btnLoadDemoTop) btnLoadDemoTop.addEventListener('click', runDemo);

  // Process queue button
  if (btnProcessQueue) {
    btnProcessQueue.addEventListener('click', async () => {
      const files = state.get('selectedFiles');
      if (!files || files.length === 0) {
        showToast('No Files', 'Please select at least one PDF statement to process.', 'warning');
        return;
      }

      btnProcessQueue.disabled = true;
      btnProcessQueue.classList.add('btn-loading');

      try {
        const settings = state.get('settings');
        const passwords = state.get('passwords');
        const res = await api.uploadFiles(files, settings, passwords);
        state.set('currentJobId', res.job_id);
        startPipelineWatcher(res.job_id);
      } catch (err) {
        showToast('Processing Error', err.message, 'error');
      } finally {
        btnProcessQueue.disabled = false;
        btnProcessQueue.classList.remove('btn-loading');
      }
    });
  }

  // Password Modal
  initPasswordModal();

  // Settings Modal
  initSettingsModal();

  // Subscribe to file queue changes
  state.subscribe('selectedFiles', () => renderQueue());
}

function addFilesToQueue(newFiles) {
  const current = state.get('selectedFiles') || [];
  const existingNames = new Set(current.map(f => f.name));
  const merged = [...current];

  for (const f of newFiles) {
    if (!existingNames.has(f.name)) {
      merged.push(f);
      existingNames.add(f.name);
    }
  }

  state.set('selectedFiles', merged);
  showToast('Files Added', `${newFiles.length} file(s) staged for processing.`, 'info');
}

function renderQueue() {
  const queueCard = document.getElementById('queue-card');
  const queueList = document.getElementById('queue-list');
  const queueMeta = document.getElementById('queue-meta');
  const files = state.get('selectedFiles') || [];

  if (!queueCard || !queueList) return;

  if (files.length === 0) {
    queueCard.style.display = 'none';
    return;
  }

  queueCard.style.display = 'block';
  const totalSize = files.reduce((acc, f) => acc + f.size, 0);
  queueMeta.textContent = `${files.length} statement(s) staged • ${(totalSize / (1024 * 1024)).toFixed(2)} MB total`;

  queueList.innerHTML = files.map((f, idx) => {
    const ext = f.name.toLowerCase().split('.').pop();
    const iconName = ext === 'csv' ? 'table-2' : (ext === 'json' ? 'file-code-2' : 'file-text');
    return `
    <div class="file-card">
      <div class="file-card-icon">
        <i data-lucide="${iconName}"></i>
      </div>
      <div class="file-card-info">
        <div class="file-card-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
        <div class="file-card-meta">${(f.size / 1024).toFixed(1)} KB • Ready for extraction</div>
      </div>
      <button class="file-card-remove" data-index="${idx}" title="Remove file">
        <i data-lucide="x" style="width:16px;height:16px;"></i>
      </button>
    </div>
  `}).join('');

  if (window.lucide) window.lucide.createIcons();

  // Attach removal events
  queueList.querySelectorAll('.file-card-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.currentTarget.getAttribute('data-index'), 10);
      const updated = [...files];
      updated.splice(idx, 1);
      state.set('selectedFiles', updated);
    });
  });
}

function initPasswordModal() {
  const modal = document.getElementById('password-modal');
  const pwdInput = document.getElementById('pdf-password-input');
  const btnSubmit = document.getElementById('btn-submit-password');
  const btnCancel = document.getElementById('btn-cancel-password');
  const btnClose = document.getElementById('btn-close-pwd-modal');

  const closeModal = () => {
    if (modal) modal.classList.remove('open');
    pendingPasswordFile = null;
  };

  if (btnCancel) btnCancel.addEventListener('click', closeModal);
  if (btnClose) btnClose.addEventListener('click', closeModal);

  if (pwdInput && btnSubmit) {
    pwdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        btnSubmit.click();
      }
    });
  }

  if (btnSubmit) {
    btnSubmit.addEventListener('click', () => {
      const pwd = pwdInput.value.trim();
      if (!pwd) {
        showToast('Password Empty', 'Please provide statement decryption password.', 'warning');
        return;
      }

      const passwords = state.get('passwords') || {};
      if (pendingPasswordFile) {
        passwords[pendingPasswordFile] = pwd;
      }
      passwords['default'] = pwd;
      passwords['Statement'] = pwd;
      const files = state.get('selectedFiles') || [];
      for (const f of files) {
        passwords[f.name] = pwd;
      }
      state.set('passwords', passwords);
      closeModal();

      showToast('Password Set', 'Retrying processing with supplied credentials...', 'info');
      const btnProcess = document.getElementById('btn-process-queue');
      if (btnProcess) btnProcess.click();
    });
  }
}

export function promptForPassword(filename) {
  const files = state.get('selectedFiles') || [];
  if ((!filename || filename === 'Statement') && files.length > 0) {
    filename = files[0].name;
  }
  pendingPasswordFile = filename || (files.length > 0 ? files[0].name : 'Statement');
  const modal = document.getElementById('password-modal');
  const desc = document.getElementById('pwd-modal-desc');
  const pwdInput = document.getElementById('pdf-password-input');

  if (desc) {
    desc.textContent = `The statement "${pendingPasswordFile}" is encrypted with a password. Please enter the decryption key below.`;
  }
  if (pwdInput) {
    pwdInput.value = '';
    setTimeout(() => pwdInput.focus(), 50);
  }
  if (modal) modal.classList.add('open');
}

function initSettingsModal() {
  const btnSettings = document.getElementById('btn-settings');
  const modal = document.getElementById('settings-modal');
  const btnClose = document.getElementById('btn-close-settings');
  const btnSave = document.getElementById('btn-save-settings');

  const dpiSelect = document.getElementById('setting-ocr-dpi');
  const thresholdInput = document.getElementById('setting-threshold');
  const thresholdVal = document.getElementById('threshold-val');
  const toggleDedupe = document.getElementById('toggle-dedupe');
  const toggleMask = document.getElementById('toggle-mask');

  if (btnSettings && modal) {
    btnSettings.addEventListener('click', () => modal.classList.add('open'));
  }
  if (btnClose && modal) {
    btnClose.addEventListener('click', () => modal.classList.remove('open'));
  }

  if (thresholdInput && thresholdVal) {
    thresholdInput.addEventListener('input', (e) => {
      thresholdVal.textContent = parseFloat(e.target.value).toFixed(2);
    });
  }

  [toggleDedupe, toggleMask].forEach(t => {
    if (t) {
      t.addEventListener('click', () => t.classList.toggle('active'));
    }
  });

  if (btnSave && modal) {
    btnSave.addEventListener('click', () => {
      const newSettings = {
        ocr_dpi: parseInt(dpiSelect.value, 10),
        confidence_threshold: parseFloat(thresholdInput.value),
        dedupe: toggleDedupe.classList.contains('active'),
        merge_files: true,
        mask_account_number: toggleMask.classList.contains('active'),
      };
      state.set('settings', newSettings);
      modal.classList.remove('open');
      showToast('Settings Saved', 'Processing parameters updated.', 'success');
    });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
