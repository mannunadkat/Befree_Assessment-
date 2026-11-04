/**
 * Export Manager for AuraBank.
 * Handles Excel (.xlsx) and CSV (.csv) downloads.
 */
import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './toast.js';

export function initExport() {
  const btnXlsx = document.getElementById('btn-download-xlsx');
  const btnCsv = document.getElementById('btn-download-csv');
  const cardXlsx = document.getElementById('export-xlsx-card');
  const cardCsv = document.getElementById('export-csv-card');
  const summaryText = document.getElementById('export-summary-text');

  const downloadXlsx = () => {
    const jobId = state.get('currentJobId');
    if (!jobId) {
      showToast('No Data', 'Process a statement before exporting.', 'warning');
      return;
    }
    showToast('Preparing Excel', 'Generating multi-sheet workbook with charts...', 'info', 2000);
    window.location.href = api.getExportXlsxUrl(jobId);
  };

  const downloadCsv = () => {
    const jobId = state.get('currentJobId');
    if (!jobId) {
      showToast('No Data', 'Process a statement before exporting.', 'warning');
      return;
    }
    showToast('Downloading CSV', 'Generating formatted flat CSV file...', 'info', 2000);
    window.location.href = api.getExportCsvUrl(jobId);
  };

  if (btnXlsx) btnXlsx.addEventListener('click', (e) => { e.stopPropagation(); downloadXlsx(); });
  if (btnCsv) btnCsv.addEventListener('click', (e) => { e.stopPropagation(); downloadCsv(); });

  if (cardXlsx) cardXlsx.addEventListener('click', downloadXlsx);
  if (cardCsv) cardCsv.addEventListener('click', downloadCsv);

  state.subscribe('result', (result) => {
    if (result && summaryText) {
      const count = result.transactions ? result.transactions.length : 0;
      summaryText.textContent = `${count} transactions ready for export`;
    }
  });
}
