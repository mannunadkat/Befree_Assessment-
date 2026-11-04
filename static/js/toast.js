/**
 * Toast Notification System for AuraBank.
 */

const TOAST_ICONS = {
  success: 'check-circle-2',
  error: 'alert-circle',
  warning: 'alert-triangle',
  info: 'info'
};

export function showToast(title, message = '', type = 'info', durationMs = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');

  const iconName = TOAST_ICONS[type] || 'info';

  toast.innerHTML = `
    <div class="toast-icon">
      <i data-lucide="${iconName}"></i>
    </div>
    <div class="toast-body">
      <div class="toast-title">${escapeHtml(title)}</div>
      ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
    </div>
    <div class="toast-close" title="Dismiss">
      <i data-lucide="x" style="width:14px;height:14px;"></i>
    </div>
  `;

  container.appendChild(toast);
  if (window.lucide) window.lucide.createIcons();

  const removeToast = () => {
    toast.classList.add('removing');
    setTimeout(() => {
      if (toast.parentElement) toast.parentElement.removeChild(toast);
    }, 250);
  };

  const closeBtn = toast.querySelector('.toast-close');
  if (closeBtn) closeBtn.addEventListener('click', removeToast);

  if (durationMs > 0) {
    setTimeout(removeToast, durationMs);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
