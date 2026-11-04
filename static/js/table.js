/**
 * Transactions Table Manager for AuraBank.
 * Features search, multi-column sorting, pagination, inline category override, and PDF crop inspection drawer.
 */
import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './toast.js';

const ALL_CATEGORIES = [
  'Salary/Income', 'Transfer In', 'Transfer Out (Person)', 'Food & Dining',
  'Groceries', 'Shopping', 'Travel & Transport', 'Fuel', 'Utilities & Bills',
  'Mobile/Internet/DTH Recharge', 'Rent', 'EMI/Loan', 'Insurance',
  'Investments/Mutual Funds/SIP', 'Stocks', 'Entertainment/Subscriptions',
  'Healthcare', 'Education', 'ATM Withdrawal', 'Cash Deposit', 'Bank Charges/Fees',
  'Interest Earned', 'Tax (GST/TDS/Income Tax)', 'Refund/Reversal', 'Cheque',
  'Credit Card Payment', 'Wallet Top-up', 'Donations/Charity', 'Uncategorized'
];

export function initTable() {
  populateCategoryDropdown();

  // Search input
  const searchInput = document.getElementById('txn-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const filters = state.get('tableFilters');
      filters.search = e.target.value.toLowerCase();
      filters.page = 1;
      state.set('tableFilters', filters);
      renderTable();
    });
  }

  // Filter dropdowns
  ['filter-category', 'filter-mode', 'filter-status'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', (e) => {
        const filters = state.get('tableFilters');
        if (id === 'filter-category') filters.category = e.target.value;
        if (id === 'filter-mode') filters.payment_mode = e.target.value;
        if (id === 'filter-status') filters.validation_status = e.target.value;
        filters.page = 1;
        state.set('tableFilters', filters);
        renderTable();
      });
    }
  });

  // Table header sorting
  const table = document.getElementById('transactions-table');
  if (table) {
    table.querySelectorAll('th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.getAttribute('data-sort');
        const filters = state.get('tableFilters');
        if (filters.sortBy === col) {
          filters.sortOrder = filters.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
          filters.sortBy = col;
          filters.sortOrder = 'asc';
        }
        state.set('tableFilters', filters);
        updateSortIcons(th, filters.sortOrder);
        renderTable();
      });
    });
  }

  // Density toggle
  const btnDensity = document.getElementById('btn-toggle-density');
  if (btnDensity) {
    btnDensity.addEventListener('click', () => {
      const filters = state.get('tableFilters');
      filters.density = filters.density === 'normal' ? 'compact' : 'normal';
      state.set('tableFilters', filters);

      const tWrap = document.getElementById('transactions-table');
      if (tWrap) {
        if (filters.density === 'compact') {
          tWrap.classList.add('compact');
        } else {
          tWrap.classList.remove('compact');
        }
      }
    });
  }

  // Retrain button
  const btnRetrain = document.getElementById('btn-retrain-model');
  if (btnRetrain) {
    btnRetrain.addEventListener('click', async () => {
      btnRetrain.disabled = true;
      btnRetrain.classList.add('btn-loading');
      try {
        const res = await api.retrainModel();
        showToast('ML Retrained', `Hold-out accuracy: ${(res.accuracy * 100).toFixed(1)}% with user overrides incorporated.`, 'success');
      } catch (err) {
        showToast('Retrain Error', err.message, 'error');
      } finally {
        btnRetrain.disabled = false;
        btnRetrain.classList.remove('btn-loading');
      }
    });
  }

  // Drawer close button & backdrop
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  const drawerBackdrop = document.getElementById('drawer-backdrop');
  const drawer = document.getElementById('detail-drawer');

  const closeDrawer = () => {
    if (drawer) drawer.classList.remove('open');
    if (drawerBackdrop) drawerBackdrop.classList.remove('open');
  };

  if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeDrawer);

  // Subscribe to result changes
  state.subscribe('result', () => renderTable());

  // If result already loaded in state, render immediately
  if (state.get('result')) {
    renderTable();
  }
}

function populateCategoryDropdown() {
  const catSelect = document.getElementById('filter-category');
  if (!catSelect) return;

  catSelect.innerHTML = `<option value="">All Categories</option>` +
    ALL_CATEGORIES.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
}

function updateSortIcons(activeTh, order) {
  document.querySelectorAll('#transactions-table th').forEach(th => {
    th.classList.remove('sorted');
    const icon = th.querySelector('.sort-icon');
    if (icon) icon.textContent = '↕';
  });

  activeTh.classList.add('sorted');
  const icon = activeTh.querySelector('.sort-icon');
  if (icon) icon.textContent = order === 'asc' ? '↑' : '↓';
}

export function renderTable() {
  const tbody = document.getElementById('txn-table-body');
  const paginationInfo = document.getElementById('pagination-info');
  const paginationBtns = document.getElementById('pagination-buttons');
  const result = state.get('result');

  if (!tbody || !result) return;

  const rawTxns = result.transactions || [];
  const filters = state.get('tableFilters');

  // Filter
  let filtered = rawTxns.filter(t => {
    if (filters.search) {
      const q = filters.search;
      const matchDesc = (t.description || '').toLowerCase().includes(q);
      const matchParty = (t.counterparty || '').toLowerCase().includes(q);
      const matchRef = (t.ref_no || '').toLowerCase().includes(q);
      const matchCat = (t.category || '').toLowerCase().includes(q);
      const matchDate = (t.date || '').includes(q);
      if (!matchDesc && !matchParty && !matchRef && !matchCat && !matchDate) return false;
    }
    if (filters.category && t.category !== filters.category) return false;
    if (filters.payment_mode && t.payment_mode !== filters.payment_mode) return false;
    if (filters.validation_status && t.validation_status !== filters.validation_status) return false;
    return true;
  });

  // Sort
  filtered.sort((a, b) => {
    let valA = a[filters.sortBy];
    let valB = b[filters.sortBy];

    if (valA === null || valA === undefined) valA = '';
    if (valB === null || valB === undefined) valB = '';

    if (typeof valA === 'number' && typeof valB === 'number') {
      return filters.sortOrder === 'asc' ? valA - valB : valB - valA;
    }
    return filters.sortOrder === 'asc'
      ? String(valA).localeCompare(String(valB))
      : String(valB).localeCompare(String(valA));
  });

  // Pagination
  const total = filtered.length;
  const totalPages = Math.ceil(total / filters.pageSize) || 1;
  const curPage = Math.min(filters.page, totalPages);
  const start = (curPage - 1) * filters.pageSize;
  const pagedTxns = filtered.slice(start, start + filters.pageSize);

  if (paginationInfo) {
    paginationInfo.textContent = `Showing ${Math.min(start + 1, total)} - ${Math.min(start + filters.pageSize, total)} of ${total} transactions`;
  }

  renderPaginationControls(paginationBtns, curPage, totalPages);

  if (pagedTxns.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align:center; padding:var(--space-8); color:var(--color-text-tertiary);">
          No transactions match current filters.
        </td>
      </tr>
    `;
    return;
  }

  const formatINR = (val) => {
    if (val === null || val === undefined || isNaN(val)) return '—';
    const num = Number(val);
    if (!isFinite(num)) return '—';
    try {
      return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch (e) {
      return '₹' + num.toFixed(2);
    }
  };

  tbody.innerHTML = pagedTxns.map(t => {
    const isDebit = t.debit !== null && t.debit !== undefined && t.debit > 0;
    const isCredit = t.credit !== null && t.credit !== undefined && t.credit > 0;
    const debitStr = isDebit ? formatINR(t.debit) : '—';
    const creditStr = isCredit ? formatINR(t.credit) : '—';
    const balanceStr = (t.balance !== null && t.balance !== undefined) ? formatINR(t.balance) : '—';

    // Status chip
    let statusChip = `<span class="chip chip-success">OK</span>`;
    if (t.validation_status === 'Repaired') {
      statusChip = `<span class="chip chip-warning" title="${escapeHtml(t.validation_note || 'Auto-repaired')}">Repaired</span>`;
    } else if (t.validation_status === 'Mismatch') {
      statusChip = `<span class="chip chip-error" title="${escapeHtml(t.validation_note || 'Mismatch')}">Mismatch</span>`;
    }

    // Category options
    const categoryOptions = ALL_CATEGORIES.map(c => `
      <option value="${escapeHtml(c)}" ${t.category === c ? 'selected' : ''}>${escapeHtml(c)}</option>
    `).join('');

    return `
      <tr data-txn-id="${t.id}">
        <td class="money">${escapeHtml(t.date)}</td>
        <td>
          <div style="font-weight:var(--weight-medium);">${escapeHtml(t.description)}</div>
          <div style="font-size:var(--text-xs); color:var(--color-text-tertiary); margin-top:2px; display:flex; gap:var(--space-2);">
            ${t.counterparty ? `<span>Entity: <strong>${escapeHtml(t.counterparty)}</strong></span>` : ''}
            ${t.ref_no ? `<span>Ref: ${escapeHtml(t.ref_no)}</span>` : ''}
            ${t.is_recurring ? `<span class="chip chip-info" style="font-size:10px;"><i data-lucide="repeat" style="width:10px;height:10px;"></i> Recurring</span>` : ''}
          </div>
        </td>
        <td><span class="chip">${escapeHtml(t.payment_mode || 'Other')}</span></td>
        <td>
          <select class="category-select" data-txn-id="${t.id}">
            ${categoryOptions}
          </select>
        </td>
        <td style="text-align:right;" class="amount-debit">${debitStr}</td>
        <td style="text-align:right;" class="amount-credit">${creditStr}</td>
        <td style="text-align:right;" class="amount-balance">${balanceStr}</td>
        <td style="text-align:center;">${statusChip}</td>
        <td style="text-align:center;">
          <button class="btn btn-ghost btn-sm btn-inspect" data-txn-id="${t.id}" title="Inspect transaction details and PDF crop">
            <i data-lucide="eye" style="width:14px;height:14px;"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  if (window.lucide) window.lucide.createIcons();

  // Attach inline category change listener
  tbody.querySelectorAll('.category-select').forEach(sel => {
    sel.addEventListener('change', async (e) => {
      const txnId = e.target.getAttribute('data-txn-id');
      const newCat = e.target.value;
      const jobId = state.get('currentJobId');

      if (!jobId || !txnId) return;

      try {
        await api.overrideCategory(jobId, txnId, newCat);
        // Update local object
        const target = rawTxns.find(x => x.id === txnId);
        if (target) {
          target.category = newCat;
          target.classification_source = 'manual';
          target.category_confidence = 1.0;
        }
        showToast('Category Updated', `Set to "${newCat}" and saved for ML learning.`, 'success');
      } catch (err) {
        showToast('Override Error', err.message, 'error');
      }
    });
  });

  // Attach inspect click listener
  tbody.querySelectorAll('.btn-inspect').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const txnId = e.currentTarget.getAttribute('data-txn-id');
      const txn = rawTxns.find(x => x.id === txnId);
      if (txn) openDetailDrawer(txn);
    });
  });
}

function renderPaginationControls(container, currentPage, totalPages) {
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn prev-btn" ${currentPage === 1 ? 'disabled style="opacity:0.4;"' : ''}>
      <i data-lucide="chevron-left" style="width:14px;height:14px;"></i>
    </button>
  `;

  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
      html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
    } else if (i === currentPage - 2 || i === currentPage + 2) {
      html += `<span style="padding:0 4px; color:var(--color-text-tertiary);">...</span>`;
    }
  }

  html += `
    <button class="page-btn next-btn" ${currentPage === totalPages ? 'disabled style="opacity:0.4;"' : ''}>
      <i data-lucide="chevron-right" style="width:14px;height:14px;"></i>
    </button>
  `;

  container.innerHTML = html;
  if (window.lucide) window.lucide.createIcons();

  container.querySelectorAll('.page-btn[data-page]').forEach(b => {
    b.addEventListener('click', (e) => {
      const p = parseInt(e.currentTarget.getAttribute('data-page'), 10);
      const filters = state.get('tableFilters');
      filters.page = p;
      state.set('tableFilters', filters);
      renderTable();
    });
  });

  const prevBtn = container.querySelector('.prev-btn');
  const nextBtn = container.querySelector('.next-btn');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentPage > 1) {
        const filters = state.get('tableFilters');
        filters.page = currentPage - 1;
        state.set('tableFilters', filters);
        renderTable();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (currentPage < totalPages) {
        const filters = state.get('tableFilters');
        filters.page = currentPage + 1;
        state.set('tableFilters', filters);
        renderTable();
      }
    });
  }
}

function openDetailDrawer(txn) {
  const drawer = document.getElementById('detail-drawer');
  const drawerBackdrop = document.getElementById('drawer-backdrop');
  const content = document.getElementById('drawer-content');
  const jobId = state.get('currentJobId');

  if (!drawer || !content) return;

  const imageUrl = jobId && txn.source_file
    ? api.getPageImageUrl(jobId, txn.source_file, txn.page || 1, txn.bbox)
    : null;

  content.innerHTML = `
    <div class="card card-sm" style="background:var(--color-bg);">
      <div style="font-size:var(--text-xs); color:var(--color-text-tertiary); text-transform:uppercase;">Narration</div>
      <div style="font-size:var(--text-md); font-weight:var(--weight-semibold); margin-top:2px;">${escapeHtml(txn.description)}</div>
    </div>

    <div class="grid-cols-2">
      <div class="card card-sm" style="background:var(--color-bg);">
        <div style="font-size:var(--text-xs); color:var(--color-text-tertiary);">Transaction Date</div>
        <div class="money" style="font-weight:var(--weight-medium); margin-top:2px;">${escapeHtml(txn.date)}</div>
      </div>
      <div class="card card-sm" style="background:var(--color-bg);">
        <div style="font-size:var(--text-xs); color:var(--color-text-tertiary);">Payment Mode</div>
        <div style="font-weight:var(--weight-medium); margin-top:2px;">${escapeHtml(txn.payment_mode || 'Other')}</div>
      </div>
    </div>

    <div class="grid-cols-2">
      <div class="card card-sm" style="background:var(--color-bg);">
        <div style="font-size:var(--text-xs); color:var(--color-text-tertiary);">Classification Engine</div>
        <div style="font-weight:var(--weight-medium); margin-top:2px; display:flex; align-items:center; gap:var(--space-2);">
          <span class="chip chip-info">${escapeHtml(txn.classification_source || 'rule')}</span>
          <span style="font-size:var(--text-xs);">${Math.round((txn.category_confidence || 1) * 100)}% conf</span>
        </div>
      </div>
      <div class="card card-sm" style="background:var(--color-bg);">
        <div style="font-size:var(--text-xs); color:var(--color-text-tertiary);">Validation Status</div>
        <div style="font-weight:var(--weight-medium); margin-top:2px;">${escapeHtml(txn.validation_status)}</div>
      </div>
    </div>

    ${txn.validation_note ? `
      <div class="card card-sm" style="background:var(--color-warning-bg); border-color:rgba(251,191,36,0.3);">
        <div style="font-size:var(--text-xs); color:var(--color-warning); font-weight:var(--weight-semibold);">Validation Note</div>
        <div style="font-size:var(--text-xs); color:var(--color-text-primary); margin-top:2px;">${escapeHtml(txn.validation_note)}</div>
      </div>
    ` : ''}

    <!-- PDF Page Crop Overlay Preview -->
    <div class="card card-sm" style="background:var(--color-bg);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-2);">
        <div style="font-size:var(--text-xs); color:var(--color-text-tertiary); text-transform:uppercase;">Source Page Highlight</div>
        <span class="chip">${escapeHtml(txn.source_file || 'Document')} • P.${txn.page || 1}</span>
      </div>
      ${imageUrl ? `
        <div style="max-height:280px; overflow:auto; border-radius:var(--radius-md); border:1px solid var(--color-border); background:#fff;">
          <img src="${imageUrl}" alt="PDF Source Page Highlight" style="width:100%; object-fit:contain;" loading="lazy">
        </div>
      ` : `<p style="font-size:var(--text-xs); color:var(--color-text-tertiary);">Preview not available for this record.</p>`}
    </div>
  `;

  if (drawer) drawer.classList.add('open');
  if (drawerBackdrop) drawerBackdrop.classList.add('open');
  if (window.lucide) window.lucide.createIcons();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
