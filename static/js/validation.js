/**
 * Balance Validation & Mathematical Integrity Audit Log for AuraBank.
 */
import { state } from './state.js';

export function initValidation() {
  state.subscribe('result', (result) => {
    if (result && result.validation) {
      renderValidationReport(result.validation);
    }
  });
}

export function renderValidationReport(validation) {
  const badgeContainer = document.getElementById('validation-overall-badge');
  const elReportedOpen = document.getElementById('val-reported-open');
  const elReportedClose = document.getElementById('val-reported-close');
  const elCalculatedClose = document.getElementById('val-calculated-close');
  const elDiscrepancy = document.getElementById('val-discrepancy');
  const issuesList = document.getElementById('validation-issues-list');
  const issuesCountChip = document.getElementById('val-issues-count');

  if (elReportedOpen) elReportedOpen.textContent = formatCurrency(validation.opening_balance || 0);
  if (elReportedClose) elReportedClose.textContent = formatCurrency(validation.closing_balance || 0);
  if (elCalculatedClose) elCalculatedClose.textContent = formatCurrency(validation.calculated_closing_balance || 0);

  const delta = Math.abs(validation.discrepancy || 0);
  if (elDiscrepancy) {
    elDiscrepancy.textContent = formatCurrency(delta);
    elDiscrepancy.style.color = delta < 0.05 ? 'var(--color-credit)' : 'var(--color-warning)';
  }

  // Status Badge
  if (badgeContainer) {
    if (validation.is_reconciled || delta < 0.05) {
      badgeContainer.innerHTML = `<span class="chip chip-success" style="font-size:var(--text-sm);"><i data-lucide="check-circle"></i> 100% Balanced</span>`;
    } else {
      badgeContainer.innerHTML = `<span class="chip chip-warning" style="font-size:var(--text-sm);"><i data-lucide="alert-triangle"></i> Discrepancy Detected</span>`;
    }
  }

  const issues = validation.issues || [];
  if (issuesCountChip) {
    issuesCountChip.textContent = `${issues.length} audit entry${issues.length === 1 ? '' : 'ies'}`;
  }

  if (!issuesList) return;

  if (issues.length === 0) {
    issuesList.innerHTML = `
      <div class="empty-state" style="padding:var(--space-8);">
        <div class="empty-state-icon" style="background:var(--color-success-bg);">
          <i data-lucide="check" style="color:var(--color-success);"></i>
        </div>
        <h3>Zero Discrepancies Found</h3>
        <p>Every transaction row matches the running balance calculation perfectly. No OCR digit fixes or column inversions needed.</p>
      </div>
    `;
  } else {
    issuesList.innerHTML = issues.map((issue, idx) => {
      const isRepaired = issue.auto_repaired;
      const typeLabel = issue.issue_type === 'swapped_columns' ? 'Debit/Credit Swapped'
        : (issue.issue_type === 'digit_repair' ? 'OCR Digit Fixed' : 'Balance Discrepancy');

      const badgeClass = isRepaired ? 'chip-success' : 'chip-warning';

      return `
        <div class="card card-sm" style="background:var(--color-bg-hover); border-left: 3px solid ${isRepaired ? 'var(--color-success)' : 'var(--color-warning)'};">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:var(--space-1);">
            <div style="display:flex; align-items:center; gap:var(--space-2);">
              <span class="chip ${badgeClass}">${escapeHtml(typeLabel)}</span>
              <span style="font-size:var(--text-xs); color:var(--color-text-tertiary);">Row #${issue.row_index + 1} (Page ${issue.page})</span>
            </div>
            <span class="money" style="font-size:var(--text-xs); color:var(--color-text-tertiary);">
              Expected: ₹${issue.expected_balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })} • Actual: ₹${issue.actual_balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </span>
          </div>

          <div style="font-size:var(--text-sm); font-weight:var(--weight-medium); margin-top:2px;">
            ${escapeHtml(issue.description)}
          </div>

          ${issue.repair_details ? `
            <div style="font-size:var(--text-xs); color:var(--color-brand); margin-top:4px; font-family:var(--font-mono);">
              Auto-repair: ${escapeHtml(issue.repair_details)}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  if (window.lucide) window.lucide.createIcons();
}

function formatCurrency(val) {
  if (val === null || val === undefined) return '₹0.00';
  return `₹${Math.abs(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
