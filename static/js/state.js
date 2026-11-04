/**
 * Central Reactive State Store for AuraBank Statement Processor.
 */

class AppState {
  constructor() {
    this.listeners = new Map();
    this.data = {
      currentView: 'upload',
      currentJobId: null,
      jobStatus: null,
      result: null, // Holds ProcessingResult { account, transactions, validation, analytics }
      selectedFiles: [],
      passwords: {}, // filename -> password
      settings: {
        ocr_dpi: 300,
        confidence_threshold: 0.55,
        dedupe: true,
        merge_files: true,
        mask_account_number: true,
      },
      tableFilters: {
        search: '',
        category: '',
        payment_mode: '',
        validation_status: '',
        sortBy: 'date',
        sortOrder: 'asc',
        page: 1,
        pageSize: 20,
        density: 'normal', // 'normal' | 'compact'
      },
      selectedAccount: 'all',
      theme: localStorage.getItem('aurabank_theme') || 'dark'
    };
  }

  get(key) {
    return this.data[key];
  }

  set(key, value) {
    const prev = this.data[key];
    this.data[key] = value;
    this.notify(key, value, prev);
  }

  update(key, partial) {
    if (typeof this.data[key] === 'object' && this.data[key] !== null) {
      this.data[key] = { ...this.data[key], ...partial };
      this.notify(key, this.data[key]);
    }
  }

  subscribe(key, callback) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key).add(callback);
    return () => this.listeners.get(key).delete(callback);
  }

  notify(key, newValue, prevValue) {
    if (this.listeners.has(key)) {
      for (const cb of this.listeners.get(key)) {
        try {
          cb(newValue, prevValue);
        } catch (err) {
          console.error(`Error in state listener for ${key}:`, err);
        }
      }
    }
  }
}

export const state = new AppState();
