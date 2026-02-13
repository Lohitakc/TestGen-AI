const API_URL = "http://localhost:8000";
let lastResults = null;

// ----------------------------
// Server Health Check
// ----------------------------
async function checkServer() {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    try {
        const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5000) });
        const data = await res.json();

        statusDot.classList.add('online');
        statusDot.classList.remove('offline');
        statusText.textContent = `Online • ${data.chroma_collection_count} docs`;
    } catch {
        statusDot.classList.add('offline');
        statusDot.classList.remove('online');
        statusText.textContent = 'Server Offline';
    }
}

checkServer();
setInterval(checkServer, 30000);

// ----------------------------
// Parse Acceptance Criteria
// ----------------------------
function parseAcceptanceCriteria(text) {
    return text
        .split('\n')
        .map(line => line.trim())
        .map(line => line.replace(/^[-*•]\s*/, ''))
        .map(line => line.replace(/^\d+[.)]\s*/, ''))
        .filter(line => line.length > 0);
}

// ----------------------------
// UI State Management
// ----------------------------
function showLoading() {
    document.getElementById('emptyState').classList.add('hidden');
    document.getElementById('loadingState').classList.remove('hidden');
    document.getElementById('resultsContainer').classList.add('hidden');
    document.getElementById('metricsSection').classList.add('hidden');
    document.getElementById('downloadSection').classList.add('hidden');
    document.getElementById('errorState').classList.add('hidden');

    document.getElementById('generateBtn').disabled = true;
    document.getElementById('evaluateBtn').disabled = true;

    startProgress();
}

function showResults() {
    document.getElementById('emptyState').classList.add('hidden');
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('resultsContainer').classList.remove('hidden');
    document.getElementById('downloadSection').classList.remove('hidden');
    document.getElementById('errorState').classList.add('hidden');

    document.getElementById('generateBtn').disabled = false;
    document.getElementById('evaluateBtn').disabled = false;
}

function showError(message) {
    document.getElementById('emptyState').classList.add('hidden');
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('resultsContainer').classList.add('hidden');
    document.getElementById('metricsSection').classList.add('hidden');
    document.getElementById('downloadSection').classList.add('hidden');
    document.getElementById('errorState').classList.remove('hidden');
    document.getElementById('errorMessage').textContent = message;

    document.getElementById('generateBtn').disabled = false;
    document.getElementById('evaluateBtn').disabled = false;
}

function resetUI() {
    document.getElementById('emptyState').classList.remove('hidden');
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('resultsContainer').classList.add('hidden');
    document.getElementById('metricsSection').classList.add('hidden');
    document.getElementById('downloadSection').classList.add('hidden');
    document.getElementById('errorState').classList.add('hidden');

    document.getElementById('generateBtn').disabled = false;
    document.getElementById('evaluateBtn').disabled = false;
}

// ----------------------------
// Progress Bar
// ----------------------------
let progressInterval = null;

function startProgress() {
    const fill = document.getElementById('progressFill');
    fill.style.width = '0%';
    let progress = 0;

    progressInterval = setInterval(() => {
        progress += Math.random() * 3;
        if (progress > 90) progress = 90;
        fill.style.width = progress + '%';
    }, 500);
}

function stopProgress() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    document.getElementById('progressFill').style.width = '100%';
}

// ----------------------------
// Validation
// ----------------------------
function validateInputs() {
    const desc = document.getElementById('description').value.trim();
    const ac = document.getElementById('acceptanceCriteria').value.trim();

    if (!desc) {
        alert('Please enter a requirement description.');
        document.getElementById('description').focus();
        return false;
    }

    if (!ac) {
        alert('Please enter at least one acceptance criterion.');
        document.getElementById('acceptanceCriteria').focus();
        return false;
    }

    return true;
}

// ----------------------------
// Build Payload
// ----------------------------
function buildPayload() {
    return {
        description: document.getElementById('description').value.trim(),
        user_story: document.getElementById('userStory').value.trim(),
        acceptance_criteria: parseAcceptanceCriteria(
            document.getElementById('acceptanceCriteria').value
        )
    };
}

// ----------------------------
// Render Test Cases
// ----------------------------
function getCardClass(type) {
    const t = type.toLowerCase();
    if (t === 'negative') return 'tc-card tc-card-negative';
    if (t === 'boundary') return 'tc-card tc-card-boundary';
    return 'tc-card tc-card-functional';
}

function getBadgeClass(type) {
    const t = type.toLowerCase();
    if (t === 'negative') return 'badge badge-negative';
    if (t === 'boundary') return 'badge badge-boundary';
    return 'badge badge-functional';
}

function getPriorityClass(priority) {
    const p = priority.toLowerCase();
    if (p === 'high') return 'badge badge-high';
    if (p === 'low') return 'badge badge-low';
    return 'badge badge-medium';
}

function renderTestCases(testCases) {
    const container = document.getElementById('resultsContainer');
    container.innerHTML = '';

    testCases.forEach((tc, index) => {
        const stepsHTML = tc.steps.map(step => `
            <div class="step-row">
                <div class="step-num">${step.step}</div>
                <div class="step-action">${step.action}</div>
                <div class="step-expected">${step.expected || '—'}</div>
            </div>
        `).join('');

        const card = document.createElement('div');
        card.className = getCardClass(tc.type);
        card.style.animationDelay = `${index * 0.05}s`;
        card.innerHTML = `
            <div class="tc-header">
                <div class="tc-title">${tc.title}</div>
                <div class="tc-badges">
                    <span class="${getBadgeClass(tc.type)}">${tc.type}</span>
                    <span class="${getPriorityClass(tc.priority)}">${tc.priority}</span>
                </div>
            </div>
            <div class="tc-steps">
                <div class="steps-header">
                    <span>#</span>
                    <span>Action</span>
                    <span>Expected Result</span>
                </div>
                ${stepsHTML}
            </div>
        `;

        container.appendChild(card);
    });
}

// ----------------------------
// Render Metrics
// ----------------------------
function renderMetrics(data) {
    document.getElementById('metricsSection').classList.remove('hidden');
    document.getElementById('metricAccov05').textContent = Math.round(data.accov_at_05 * 100) + '%';
    document.getElementById('metricAccov065').textContent = Math.round(data.accov_at_065 * 100) + '%';
    document.getElementById('metricNegRatio').textContent = Math.round(data.negative_ratio * 100) + '%';
    document.getElementById('metricCount').textContent = data.num_test_cases;
}

// ----------------------------
// Generate Handler
// ----------------------------
async function handleGenerate() {
    if (!validateInputs()) return;

    showLoading();

    try {
        const res = await fetch(`${API_URL}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildPayload())
        });

        stopProgress();

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Server error');
        }

        const data = await res.json();
        lastResults = data;

        renderTestCases(data.test_cases);
        showResults();

    } catch (err) {
        stopProgress();
        showError(err.message || 'Failed to connect to server');
    }
}

// ----------------------------
// Evaluate Handler
// ----------------------------
async function handleEvaluate() {
    if (!validateInputs()) return;

    showLoading();

    try {
        const res = await fetch(`${API_URL}/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildPayload())
        });

        stopProgress();

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Server error');
        }

        const data = await res.json();
        lastResults = data;

        renderMetrics(data);
        renderTestCases(data.test_cases);
        showResults();

    } catch (err) {
        stopProgress();
        showError(err.message || 'Failed to connect to server');
    }
}

// ----------------------------
// Download
// ----------------------------
function downloadResults() {
    if (!lastResults) return;

    const blob = new Blob([JSON.stringify(lastResults, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'testgen_results.json';
    a.click();
    URL.revokeObjectURL(url);
}