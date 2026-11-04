/**
 * Pipeline Progress Watcher & SSE Stream Listener for AuraBank.
 */
import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './toast.js';
import { promptForPassword } from './upload.js';

let activeEventSource = null;

export function startPipelineWatcher(jobId) {
  const pipelineCard = document.getElementById('pipeline-card');
  const pipelineMsg = document.getElementById('pipeline-message');
  const pipelinePct = document.getElementById('pipeline-percentage');
  const pipelineProg = document.getElementById('pipeline-progress');
  const pipelineCounter = document.getElementById('pipeline-txn-counter');
  const pipelineSub = document.getElementById('pipeline-subtext');

  if (pipelineCard) pipelineCard.style.display = 'block';

  resetStepper();

  if (activeEventSource) {
    activeEventSource.close();
  }

  activeEventSource = api.connectJobEvents(jobId, (event) => {
    // Update progress elements
    if (event.progress !== undefined && pipelineProg && pipelinePct) {
      pipelineProg.style.width = `${event.progress}%`;
      pipelinePct.textContent = `${Math.round(event.progress)}%`;
    }

    if (event.message && pipelineMsg) {
      pipelineMsg.textContent = event.message;
    }

    if (event.transactions_found !== undefined && pipelineCounter) {
      pipelineCounter.textContent = event.transactions_found;
    }

    // Step state activation
    updateStepperStage(event.stage);

    if (event.status === 'password_required') {
      showToast('Password Required', event.message, 'warning');
      promptForPassword(event.file || 'Statement');
      return;
    }

    if (event.status === 'error') {
      showToast('Processing Error', event.message || 'Pipeline halted unexpectedly', 'error');
      if (pipelineCard) pipelineCard.style.display = 'none';
      return;
    }

    if (event.status === 'completed') {
      onPipelineComplete(jobId);
    }
  }, (err) => {
    console.warn('SSE event stream error:', err);
  });
}

function updateStepperStage(stage) {
  const stages = ['detect', 'extract', 'parse', 'validate', 'classify'];
  const stageMap = {
    initializing: 0,
    detecting: 0,
    detect: 0,
    extracting: 1,
    extract: 1,
    ocr: 1,
    parsing: 2,
    parse: 2,
    validating: 3,
    validate: 3,
    classifying: 4,
    classify: 4,
    completed: 5,
  };

  const currentIdx = stageMap[stage] !== undefined ? stageMap[stage] : 0;

  stages.forEach((name, idx) => {
    const el = document.getElementById(`step-${name}`);
    const conn = document.getElementById(`conn-${idx}`);

    if (el) {
      el.classList.remove('active', 'done');
      if (idx < currentIdx) {
        el.classList.add('done');
      } else if (idx === currentIdx) {
        el.classList.add('active');
      }
    }

    if (conn) {
      conn.classList.remove('done');
      if (idx < currentIdx) {
        conn.classList.add('done');
      }
    }
  });
}

function resetStepper() {
  ['detect', 'extract', 'parse', 'validate', 'classify'].forEach((name, idx) => {
    const el = document.getElementById(`step-${name}`);
    const conn = document.getElementById(`conn-${idx}`);
    if (el) el.classList.remove('active', 'done');
    if (conn) conn.classList.remove('done');
  });
  const first = document.getElementById('step-detect');
  if (first) first.classList.add('active');
}

async function onPipelineComplete(jobId) {
  try {
    const result = await api.getJobResult(jobId);
    state.set('result', result);

    triggerConfetti();
    showToast('Processing Complete', `Extracted ${result.transactions.length} transactions with high confidence.`, 'success');

    // Auto-navigate to Overview after 600ms
    setTimeout(() => {
      window.location.hash = '#overview';
    }, 600);
  } catch (err) {
    showToast('Result Fetch Error', err.message, 'error');
  }
}

function triggerConfetti() {
  if (typeof window.confetti === 'function') {
    window.confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 }
    });
  }
}
