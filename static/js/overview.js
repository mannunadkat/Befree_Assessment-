/**
 * Overview View Component for AuraBank.
 * Features 3D tilt card, count-up animations, reconciliation banner, and financial KPIs.
 */
import { state } from './state.js';

export function initOverview() {
  state.subscribe('result', (result) => {
    if (result) renderOverview(result);
  });

  initCardParallax();
}

function renderOverview(result) {
  const account = result.account || {};
  const validation = result.validation || {};
  const analytics = result.analytics || {};
  const kpis = analytics.kpis || {};
  const txns = result.transactions || [];

  // 1. Reconciliation Banner
  renderReconciliationBanner(validation);

  // 2. Bank Card details
  const elBank = document.getElementById('acc-bank-name');
  const elHolder = document.getElementById('acc-holder');
  const elNum = document.getElementById('acc-number');
  const elIfsc = document.getElementById('acc-ifsc');
  const elOpen = document.getElementById('acc-open-bal');
  const elClose = document.getElementById('acc-close-bal');
  const elTypeChip = document.getElementById('acc-pdf-type-chip');

  if (elBank) elBank.textContent = account.bank_name || 'BANK STATEMENT';
  if (elHolder) elHolder.textContent = account.account_holder_name || 'Account Holder';
  if (elNum) elNum.textContent = account.masked_account_number || account.account_number || '•••• •••• •••• ••••';
  if (elIfsc) elIfsc.textContent = account.ifsc_code || '—';
  if (elOpen) elOpen.textContent = formatCurrency(account.opening_balance || 0);
  if (elClose) elClose.textContent = formatCurrency(account.closing_balance || 0);

  if (elTypeChip) {
    const pType = account.pdf_type || 'text';
    elTypeChip.textContent = pType === 'scanned' ? 'Scanned OCR' : (pType === 'hybrid' ? 'Hybrid PDF' : 'Digital Text');
  }

  // 3. KPI values with count-up animation
  animateCountUp('kpi-total-credits', kpis.total_credits || 0, true);
  animateCountUp('kpi-total-debits', kpis.total_debits || 0, true);
  animateCountUp('kpi-net-flow', kpis.net_flow || 0, true);
  animateCountUp('kpi-total-txns', kpis.total_transactions || txns.length, false);

  const creditsCount = txns.filter(t => t.credit && t.credit > 0).length;
  const debitsCount = txns.filter(t => t.debit && t.debit > 0).length;
  const elCredCount = document.getElementById('kpi-credits-count');
  const elDebCount = document.getElementById('kpi-debits-count');
  if (elCredCount) elCredCount.textContent = `${creditsCount} deposits`;
  if (elDebCount) elDebCount.textContent = `${debitsCount} withdrawals`;

  // Net flow coloring
  const elNetFlow = document.getElementById('kpi-net-flow');
  if (elNetFlow) {
    if ((kpis.net_flow || 0) >= 0) {
      elNetFlow.style.color = 'var(--color-credit)';
    } else {
      elNetFlow.style.color = 'var(--color-debit)';
    }
  }

  // 4. Automated Insights
  renderInsights(analytics.insights || []);

  // 5. Recent Transactions mini-table
  renderRecentTable(txns.slice(0, 5));
}

function renderReconciliationBanner(validation) {
  const container = document.getElementById('overview-reconciliation-container');
  if (!container) return;

  const isReconciled = validation.is_reconciled;
  const discrepancy = Math.abs(validation.discrepancy || 0);

  if (isReconciled || discrepancy < 0.05) {
    container.innerHTML = `
      <div class="recon-banner reconciled">
        <i data-lucide="check-circle-2"></i>
        <div>
          <strong>Statement Mathematically Reconciled:</strong> Opening balance plus total deposits minus withdrawals matches the closing balance with zero discrepancy.
        </div>
      </div>
    `;
  } else {
    container.innerHTML = `
      <div class="recon-banner mismatch">
        <i data-lucide="alert-triangle"></i>
        <div>
          <strong>Reconciliation Discrepancy Flagged:</strong> Final calculated balance differs by ₹${discrepancy.toLocaleString('en-IN', { minimumFractionDigits: 2 })}. Check the Validation tab for flagged or repaired rows.
        </div>
      </div>
    `;
  }
  if (window.lucide) window.lucide.createIcons();
}

function renderInsights(insights) {
  const container = document.getElementById('overview-insights-grid');
  if (!container) return;

  if (insights.length === 0) {
    container.innerHTML = `<p style="color:var(--color-text-tertiary); font-size:var(--text-xs);">No insights generated yet.</p>`;
    return;
  }

  container.innerHTML = insights.map(item => `
    <div class="card card-sm insight-card">
      <div class="insight-icon">
        <i data-lucide="${item.icon || 'activity'}"></i>
      </div>
      <div>
        <div class="insight-title">${escapeHtml(item.title)}</div>
        <div class="insight-value">${escapeHtml(item.value)}</div>
        <div class="insight-subtext">${escapeHtml(item.subtext)}</div>
      </div>
    </div>
  `).join('');

  if (window.lucide) window.lucide.createIcons();
}

function renderRecentTable(recentTxns) {
  const wrap = document.getElementById('overview-recent-table-wrap');
  if (!wrap) return;

  if (recentTxns.length === 0) {
    wrap.innerHTML = `<div class="empty-state"><p>No transactions parsed yet.</p></div>`;
    return;
  }

  wrap.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Narration</th>
          <th>Mode</th>
          <th>Category</th>
          <th style="text-align:right;">Amount</th>
          <th style="text-align:right;">Balance</th>
        </tr>
      </thead>
      <tbody>
        ${recentTxns.map(t => {
          const isDebit = t.debit !== null && t.debit !== undefined && t.debit > 0;
          const isCredit = t.credit !== null && t.credit !== undefined && t.credit > 0;
          let amtStr = '—';
          if (isDebit) amtStr = `- ${formatCurrency(t.debit)}`;
          else if (isCredit) amtStr = `+ ${formatCurrency(t.credit)}`;
          const amtClass = isDebit ? 'amount-debit' : 'amount-credit';
          const balStr = (t.balance !== null && t.balance !== undefined) ? formatCurrency(t.balance) : '—';
          return `
            <tr>
              <td class="money">${escapeHtml(t.date)}</td>
              <td style="max-width:280px;" class="truncate" title="${escapeHtml(t.description)}">${escapeHtml(t.description)}</td>
              <td><span class="chip">${escapeHtml(t.payment_mode || 'Other')}</span></td>
              <td><span class="chip chip-info">${escapeHtml(t.category || 'Uncategorized')}</span></td>
              <td style="text-align:right;" class="${amtClass}">${amtStr}</td>
              <td style="text-align:right;" class="amount-balance">${balStr}</td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

function initCardParallax() {
  const card = document.getElementById('account-card-widget');
  if (!card) return;

  card.addEventListener('mousemove', (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const rotateX = (-y / rect.height) * 12;
    const rotateY = (x / rect.width) * 12;

    card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
    card.style.transition = 'transform 0.1s ease-out';
  });

  card.addEventListener('mouseleave', () => {
    card.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
    card.style.transition = 'transform 0.5s ease-out';
  });
}

function animateCountUp(elementId, targetVal, isCurrency = false) {
  const el = document.getElementById(elementId);
  if (!el) return;

  if (window.gsap) {
    const obj = { val: 0 };
    window.gsap.to(obj, {
      val: targetVal,
      duration: 1.2,
      ease: 'power2.out',
      onUpdate: () => {
        el.textContent = isCurrency ? formatCurrency(obj.val) : Math.round(obj.val).toLocaleString();
      }
    });
  } else {
    el.textContent = isCurrency ? formatCurrency(targetVal) : targetVal.toLocaleString();
  }
}

function formatCurrency(val) {
  if (val === null || val === undefined || isNaN(val)) return '₹0.00';
  const num = Number(val);
  if (!isFinite(num)) return '₹0.00';
  const abs = Math.abs(num);
  const sign = num < 0 ? '- ' : '';
  try {
    return `${sign}₹${abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  } catch (e) {
    return `${sign}₹${abs.toFixed(2)}`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
