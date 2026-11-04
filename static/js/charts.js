/**
 * Analytics & Chart.js Visualizations for AuraBank.
 * Doughnut chart, monthly cash flow combo, top merchants horizontal bar, and largest expenses breakdown.
 */
import { state } from './state.js';

let categoryChartInstance = null;
let monthlyChartInstance = null;
let merchantsChartInstance = null;

// Category colors matching tokens.css
const CATEGORY_PALETTE = [
  '#10b981', '#34d399', '#f59e0b', '#f97316', '#84cc16',
  '#ec4899', '#3b82f6', '#78716c', '#06b6d4', '#8b5cf6',
  '#ef4444', '#dc2626', '#0ea5e9', '#14b8a6', '#22d3ee',
  '#d946ef', '#f43f5e', '#6366f1', '#a855f7', '#16a34a',
  '#94a3b8', '#059669', '#b91c1c', '#4ade80', '#7c3aed',
  '#e11d48', '#a78bfa', '#64748b'
];

export function initCharts() {
  state.subscribe('result', (result) => {
    if (result && result.analytics) {
      renderAllCharts(result.analytics);
    }
  });

  state.subscribe('theme', () => {
    const res = state.get('result');
    if (res && res.analytics) {
      renderAllCharts(res.analytics);
    }
  });
}

export function renderAllCharts(analytics) {
  if (typeof window.Chart === 'undefined') {
    console.warn('Chart.js library is not loaded');
    return;
  }

  const isDark = (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark';
  const textColor = isDark ? '#a0a0bf' : '#555573';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

  renderCategoryDoughnut(analytics.category_spending || {}, textColor);
  renderMonthlyCombo(analytics.monthly_summary || {}, textColor, gridColor);
  renderMerchantsBar(analytics.top_merchants || [], textColor, gridColor);
  renderTopExpensesList(analytics.top_expenses || []);
}

function renderCategoryDoughnut(catSpend, textColor) {
  const ctx = document.getElementById('chart-category-doughnut');
  if (!ctx) return;

  if (categoryChartInstance) {
    categoryChartInstance.destroy();
  }

  const labels = Object.keys(catSpend);
  const values = Object.values(catSpend);

  if (labels.length === 0) {
    labels.push('No Expenses');
    values.push(1);
  }

  categoryChartInstance = new window.Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: CATEGORY_PALETTE.slice(0, labels.length),
        borderWidth: 2,
        borderColor: (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? '#161629' : '#ffffff',
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: textColor,
            font: { family: 'Inter', size: 11 },
            boxWidth: 12,
            padding: 8
          }
        },
        tooltip: {
          callbacks: {
            label: (item) => {
              if (item.label === 'No Expenses') return ' No expenses recorded';
              const raw = item.raw || 0;
              return ` ₹${raw.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            }
          }
        }
      },
      onClick: (e, elements) => {
        if (elements.length > 0) {
          const idx = elements[0].index;
          const clickedCategory = labels[idx];
          if (clickedCategory && clickedCategory !== 'No Expenses') {
            const filters = state.get('tableFilters');
            filters.category = clickedCategory;
            filters.page = 1;
            state.set('tableFilters', filters);
            window.location.hash = '#transactions';
          }
        }
      }
    }
  });
}

function renderMonthlyCombo(monthlyData, textColor, gridColor) {
  const ctx = document.getElementById('chart-monthly-bar');
  if (!ctx) return;

  if (monthlyChartInstance) {
    monthlyChartInstance.destroy();
  }

  const labels = monthlyData.labels && monthlyData.labels.length > 0 ? [...monthlyData.labels] : ['Current Period'];
  const income = monthlyData.income && monthlyData.income.length > 0 ? [...monthlyData.income] : [0];
  const expense = monthlyData.expense && monthlyData.expense.length > 0 ? [...monthlyData.expense] : [0];
  const net = monthlyData.net && monthlyData.net.length > 0 ? [...monthlyData.net] : [0];

  monthlyChartInstance = new window.Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          type: 'bar',
          label: 'Income (Credits)',
          data: income,
          backgroundColor: 'rgba(52, 211, 153, 0.75)',
          borderRadius: 6,
          order: 2
        },
        {
          type: 'bar',
          label: 'Expense (Debits)',
          data: expense,
          backgroundColor: 'rgba(251, 113, 133, 0.75)',
          borderRadius: 6,
          order: 3
        },
        {
          type: 'line',
          label: 'Net Savings',
          data: net,
          borderColor: '#818cf8',
          backgroundColor: 'rgba(129, 140, 248, 0.2)',
          borderWidth: 2,
          tension: 0.3,
          fill: false,
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { family: 'JetBrains Mono', size: 10 },
            callback: (v) => {
              const abs = Math.abs(v);
              if (abs >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
              if (abs >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
              if (abs >= 1000) return `₹${(v / 1000).toFixed(0)}k`;
              return `₹${v}`;
            }
          }
        }
      },
      plugins: {
        legend: {
          labels: { color: textColor, font: { family: 'Inter', size: 11 }, boxWidth: 12 }
        },
        tooltip: {
          callbacks: {
            label: (item) => ` ${item.dataset.label}: ₹${item.raw.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
          }
        }
      }
    }
  });
}

function renderMerchantsBar(merchants, textColor, gridColor) {
  const ctx = document.getElementById('chart-merchants-bar');
  if (!ctx) return;

  if (merchantsChartInstance) {
    merchantsChartInstance.destroy();
  }

  const cleanMerchant = (name) => {
    if (!name) return 'Unknown';
    const s = String(name).trim();
    const map = {
      'yntra': 'Myntra', 'viggy': 'Swiggy', 'omato': 'Zomato', 'linkit': 'Blinkit', 'ber': 'Uber'
    };
    if (map[s.toLowerCase()]) return map[s.toLowerCase()];
    return s.charAt(0).toUpperCase() + s.slice(1);
  };

  const labels = merchants && merchants.length > 0 ? merchants.map(m => cleanMerchant(m.merchant)) : ['No Outflow Records'];
  const values = merchants && merchants.length > 0 ? merchants.map(m => m.amount) : [0];

  merchantsChartInstance = new window.Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Spent Amount',
        data: values,
        backgroundColor: 'rgba(139, 92, 246, 0.7)',
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { left: 4, right: 12, top: 4, bottom: 4 }
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { family: 'JetBrains Mono', size: 10 },
            callback: (v) => {
              const abs = Math.abs(v);
              if (abs >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
              if (abs >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
              if (abs >= 1000) return `₹${(v / 1000).toFixed(0)}k`;
              return `₹${v}`;
            }
          }
        },
        y: {
          grid: { display: false },
          ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => ` Total: ₹${item.raw.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
          }
        }
      }
    }
  });
}

function renderTopExpensesList(topExpenses) {
  const container = document.getElementById('top-expenses-list');
  if (!container) return;

  if (topExpenses.length === 0) {
    container.innerHTML = `<div style="font-size:var(--text-xs); color:var(--color-text-tertiary); padding:var(--space-4);">No debit expenses detected.</div>`;
    return;
  }

  container.innerHTML = topExpenses.map((exp, idx) => `
    <div style="display:flex; justify-content:space-between; align-items:center; padding:var(--space-2) var(--space-3); border-radius:var(--radius-md); background:var(--color-bg-hover); min-width:0; overflow:hidden;">
      <div style="display:flex; align-items:center; gap:var(--space-3); min-width:0; flex:1 1 auto; overflow:hidden;">
        <span style="font-size:var(--text-xs); font-weight:var(--weight-bold); color:var(--color-text-tertiary); width:18px; flex-shrink:0;">#${idx + 1}</span>
        <div style="min-width:0; flex:1 1 auto; overflow:hidden;">
          <div style="font-size:var(--text-sm); font-weight:var(--weight-medium); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(exp.description)}">${escapeHtml(exp.description)}</div>
          <div style="font-size:var(--text-xs); color:var(--color-text-tertiary); margin-top:1px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(exp.date)} • <span class="chip chip-info" style="font-size:10px;">${escapeHtml(exp.category)}</span></div>
        </div>
      </div>
      <div class="money amount-debit" style="font-weight:var(--weight-semibold); font-size:var(--text-sm); flex-shrink:0; margin-left:var(--space-3);">
        - ₹${(Number.isFinite(exp.amount) ? exp.amount : 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
    </div>
  `).join('');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
