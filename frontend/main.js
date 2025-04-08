const API_BASE_URL = 'http://localhost:8000';

// DOM Elements
const fileInput = document.getElementById('fileInput');
const fileCount = document.getElementById('fileCount');
const uploadBtn = document.getElementById('uploadBtn');
const deleteAllBtn = document.getElementById('deleteAllBtn');
const loadingDiv = document.getElementById('loading');
const resultsDiv = document.getElementById('results');
const resultsBody = document.getElementById('resultsBody');
const errorDiv = document.getElementById('error');
const noResultsMsg = document.getElementById('noResultsMsg');
const modal = document.getElementById('modal');
const modalClose = document.querySelector('.close');
const fullText = document.getElementById('fullText');

fileInput.addEventListener('change', () => {
  fileCount.textContent = `${fileInput.files.length} file(s) selected`;
});

function showLoading() {
  loadingDiv.classList.remove('hidden');
}
function hideLoading() {
  loadingDiv.classList.add('hidden');
}
function showError(message) {
  errorDiv.classList.remove('hidden');
  errorDiv.querySelector('.error-message').textContent = message;
}
function hideError() {
  errorDiv.classList.add('hidden');
}
function disableUpload() {
  uploadBtn.disabled = true;
  fileInput.disabled = true;
}
function enableUpload() {
  uploadBtn.disabled = false;
  fileInput.disabled = false;
}

function connectWebSocket(jobId) {
  updateJobStatus(jobId, 'Processing...', 10);
  const pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/jobs/all`);
      if (response.ok) {
        const jobs = await response.json();
        const job = jobs.find(j => j.file_id === jobId);
        if (job) {
          if (job.status === 'completed') {
            updateJobStatus(jobId, 'Completed', 100);
            clearInterval(pollInterval);
          } else if (job.status === 'failed') {
            updateJobStatus(jobId, 'Failed', 0);
            clearInterval(pollInterval);
          } else {
            const progressBar = document.querySelector(`tr[data-job-id="${jobId}"] .progress-bar`);
            if (progressBar) {
              let current = parseInt(progressBar.style.width) || 10;
              if (current < 90) updateJobStatus(jobId, 'Processing...', current + 5);
            }
          }
        }
      }
    } catch (err) {
      console.error('Polling error:', err);
    }
  }, 1000);
}

function updateJobStatus(jobId, status, progress) {
  const row = document.querySelector(`tr[data-job-id="${jobId}"]`);
  if (!row) return;

  const statusCell = row.querySelector('.status-cell');
  const progressBar = row.querySelector('.progress-bar');
  const scoreCell = row.querySelector('.score-cell');

  if (statusCell) statusCell.textContent = status;
  if (progressBar) {
    progressBar.style.width = `${progress}%`;
    progressBar.textContent = `${progress}%`;
    progressBar.className = 'progress-bar';
    if (status === 'Failed') progressBar.classList.add('failed');
    else if (progress === 100) progressBar.classList.add('completed');
  }

  if (scoreCell && (status === 'Failed')) {
    scoreCell.textContent = 'Failed';
    scoreCell.className = 'score-cell failed-score';
  }
}

uploadBtn.addEventListener('click', async () => {
  const files = fileInput.files;
  if (!files.length) return showError('Please select at least one file');

  hideError();
  showLoading();
  disableUpload();
  resultsDiv.classList.remove('hidden');
  noResultsMsg.classList.add('hidden');

  const filesArray = Array.from(files).sort((a, b) => a.name.localeCompare(b.name));
  const tempJobIds = [];

  for (let i = 0; i < filesArray.length; i++) {
    const file = filesArray[i];
    const tempId = `temp-${Date.now()}-${i}`;
    tempJobIds.push(tempId);

    const row = document.createElement('tr');
    row.dataset.jobId = tempId;
    row.innerHTML = `
      <td>${file.name}</td>
      <td class="file-type-cell">${file.type.includes('pdf') ? 'PDF' : 'DOCX'}</td>
      <td class="status-cell">${i === 0 ? 'Uploading...' : 'Queued'}</td>
      <td class="progress-cell">
        <div class="progress-bar-container">
          <div class="progress-bar" style="width:${i === 0 ? '5%' : '0%'}">${i === 0 ? '5%' : '0%'}</div>
        </div>
      </td>
      <td class="score-cell">${i === 0 ? 'Processing...' : 'Waiting...'}</td>
      <td class="actions-cell"></td>
    `;
    resultsBody.appendChild(row); // Appending in order
  }

  for (let i = 0; i < filesArray.length; i++) {
    const file = filesArray[i];
    const tempId = tempJobIds[i];
    const tempRow = document.querySelector(`tr[data-job-id="${tempId}"]`);

    if (tempRow) {
      const statusCell = tempRow.querySelector('.status-cell');
      const progressBar = tempRow.querySelector('.progress-bar');
      if (statusCell) statusCell.textContent = 'Processing...';
      if (progressBar) {
        progressBar.style.width = '10%';
        progressBar.textContent = '10%';
      }
    }

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE_URL}/jobs/parse`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error(await response.text());

      const job = await response.json();
      tempRow.remove();
      displayResults([job]);
      connectWebSocket(job.file_id);
    } catch (error) {
      console.error(`Error uploading ${file.name}:`, error);
      updateJobStatus(tempId, 'Failed', 0);
    }
  }

  fileInput.value = '';
  fileCount.textContent = '';
  hideLoading();
  enableUpload();
});

function displayResults(jobs) {
  for (const job of jobs) {
    if (!job.file_id) continue;

    const row = document.createElement('tr');
    row.dataset.jobId = job.file_id;

    const scoreClass = job.status === 'completed'
      ? (job.parse_score >= 80 ? 'high-score' : job.parse_score >= 60 ? 'medium-score' : 'low-score')
      : 'failed-score';

    row.innerHTML = `
      <td>${job.filename}</td>
      <td class="file-type-cell">${job.file_type.includes('pdf') ? 'PDF' : 'DOCX'}</td>
      <td class="status-cell ${job.status === 'failed' ? 'error-status' : ''}">
        ${job.status === 'completed' ? 'Completed' : job.status === 'failed' ? 'Failed' : 'Processing...'}
      </td>
      <td class="progress-cell">
        <div class="progress-bar-container">
          <div class="progress-bar ${job.status === 'completed' ? 'completed' : job.status === 'failed' ? 'failed' : ''}" 
               style="width:${job.status === 'completed' ? '100%' : '0%'}">
            ${job.status === 'completed' ? '100%' : '0%'}
          </div>
        </div>
      </td>
      <td class="score-cell ${scoreClass}">
        ${job.status === 'completed' ? job.parse_score : 'Failed'}
      </td>
      <td class="actions-cell">
        ${job.status === 'completed' ? `
          <button onclick="viewFullText('${job.file_id}')">📄</button>
          ${job.has_converted_pdf ? `<button onclick="downloadPdf('${job.file_id}')">⬇️PDF</button>` : ''}
          <button onclick="downloadOriginal('${job.file_id}')">⬇️Original</button>
        ` : ''}
        <button onclick="deleteJob('${job.file_id}')">🗑️</button>
      </td>
    `;

    resultsBody.appendChild(row);
    if (job.status === 'processing') connectWebSocket(job.file_id);
  }
}

async function loadExistingJobs() {
  try {
    const res = await fetch(`${API_BASE_URL}/jobs/all`);
    const jobs = await res.json();
    resultsBody.innerHTML = '';

    if (!jobs.length) {
      noResultsMsg.classList.remove('hidden');
    } else {
      noResultsMsg.classList.add('hidden');
      resultsDiv.classList.remove('hidden');
      displayResults(jobs);
    }
  } catch (err) {
    showError('Could not fetch job data');
  }
}

async function viewFullText(fileId) {
  try {
    const res = await fetch(`${API_BASE_URL}/jobs/${fileId}/text`);
    const data = await res.json();
    fullText.textContent = data.text;
    modal.classList.remove('hidden');
  } catch {
    showError('Failed to load full text');
  }
}

async function downloadPdf(fileId) {
  const res = await fetch(`${API_BASE_URL}/jobs/${fileId}/pdf`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'converted.pdf';
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadOriginal(fileId) {
  const res = await fetch(`${API_BASE_URL}/jobs/${fileId}/original`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'original';
  a.click();
  URL.revokeObjectURL(url);
}

async function deleteJob(fileId) {
  await fetch(`${API_BASE_URL}/jobs/${fileId}`, { method: 'DELETE' });
  await loadExistingJobs();
}

deleteAllBtn.addEventListener('click', async () => {
  if (!confirm('Are you sure? This will remove all jobs.')) return;
  const res = await fetch(`${API_BASE_URL}/jobs/all`);
  const jobs = await res.json();
  for (const job of jobs) {
    await fetch(`${API_BASE_URL}/jobs/${job.file_id}`, { method: 'DELETE' });
  }
  await loadExistingJobs();
  showError('All jobs deleted.');
  setTimeout(hideError, 3000);
});

modalClose.onclick = () => modal.classList.add('hidden');
window.onclick = (e) => {
  if (e.target === modal) modal.classList.add('hidden');
};

loadExistingJobs();
