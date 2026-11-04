/**
 * API Client & SSE Stream Manager for AuraBank.
 */

export const api = {
  /**
   * Health check and OCR availability.
   */
  async checkHealth() {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },

  /**
   * Upload one or more PDF statement files with optional settings.
   */
  async uploadFiles(files, settings = {}, passwords = {}) {
    const formData = new FormData();
    for (const f of files) {
      formData.append('files', f);
    }
    const mergedSettings = { ...settings, passwords };
    formData.append('settings', JSON.stringify(mergedSettings));

    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Upload failed' }));
      throw new Error(err.message || 'Upload failed');
    }
    return res.json(); // { job_id, status }
  },

  /**
   * Run the instant demo statement.
   */
  async loadDemo() {
    const res = await fetch('/api/demo', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Failed to trigger demo' }));
      throw new Error(err.message || 'Demo failed');
    }
    return res.json();
  },

  /**
   * Get single job status.
   */
  async getJobStatus(jobId) {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) throw new Error('Job status fetch failed');
    return res.json();
  },

  /**
   * Get final processed result.
   */
  async getJobResult(jobId) {
    const res = await fetch(`/api/jobs/${jobId}/result`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Failed to fetch results' }));
      throw new Error(err.message || 'Result fetch failed');
    }
    return res.json();
  },

  /**
   * Connect to Server-Sent Events (SSE) stream for real-time progress.
   */
  connectJobEvents(jobId, onEvent, onError) {
    const eventSource = new EventSource(`/api/jobs/${jobId}/events`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
        if (data.status === 'completed' || data.status === 'error' || data.status === 'password_required') {
          eventSource.close();
        }
      } catch (err) {
        console.error('Failed to parse SSE payload:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE stream closed or encountered error:', err);
      eventSource.close();
      if (onError) onError(err);
    };

    return eventSource;
  },

  /**
   * Manual category override for a transaction.
   */
  async overrideCategory(jobId, txnId, category) {
    const res = await fetch('/api/override', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, txn_id: txnId, category }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Override failed' }));
      throw new Error(err.message || 'Override failed');
    }
    return res.json();
  },

  /**
   * Retrain ML model with current seeds and overrides.
   */
  async retrainModel() {
    const res = await fetch('/api/retrain', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Retrain failed' }));
      throw new Error(err.message || 'Retrain failed');
    }
    return res.json();
  },

  /**
   * Build URL for PDF page image crop/preview with optional highlight.
   */
  getPageImageUrl(jobId, filename, pageNum, bbox = null) {
    let url = `/api/page-image/${encodeURIComponent(jobId)}/${encodeURIComponent(filename)}/${pageNum}`;
    if (bbox && bbox.length === 4) {
      url += `?highlight=${bbox.join(',')}`;
    }
    return url;
  },

  /**
   * Trigger download for CSV.
   */
  getExportCsvUrl(jobId) {
    return `/api/export/csv?job_id=${encodeURIComponent(jobId)}`;
  },

  /**
   * Trigger download for Excel.
   */
  getExportXlsxUrl(jobId) {
    return `/api/export/xlsx?job_id=${encodeURIComponent(jobId)}`;
  }
};
