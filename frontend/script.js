const API_URL = "http://localhost:8000";

const state = {
    resultsPayload: null,
    testCases: [],
    progressTimer: null,
};

const SIMPLE_MARKERS = ["smoke", "basic", "sanity", "happy path", "quick check"];

function q(id) {
    return document.getElementById(id);
}

function escapeHtml(text) {
    return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function parseAcceptanceCriteria(rawText) {
    return rawText
        .split("\n")
        .map((line) => line.trim())
        .map((line) => line.replace(/^[-*]\s*/, ""))
        .map((line) => line.replace(/^\d+[.)]\s*/, ""))
        .filter(Boolean);
}

function normalizeSuite(tc) {
    const title = String(tc.title || "").toLowerCase();
    const hasCopyStyle = Boolean(tc.copy_paste_input || tc.expected_outcome);
    const stepCount = Array.isArray(tc.steps) ? tc.steps.length : 0;

    if (title.startsWith("[supplemental]")) return "supplemental";
    if (title.startsWith("[rigorous]")) return "rigorous";
    if (SIMPLE_MARKERS.some((marker) => title.includes(marker))) return "supplemental";
    if (!hasCopyStyle && stepCount <= 2) return "supplemental";
    return "rigorous";
}

function normalizeType(tc) {
    return String(tc.type || "functional").toLowerCase();
}

function readPayload() {
    const description = q("description").value.trim();
    const userStory = q("userStory").value.trim();
    const criteria = parseAcceptanceCriteria(q("acceptanceCriteria").value);

    if (!description) {
        showInputError("Requirement description is required.");
        return null;
    }
    if (criteria.length === 0) {
        showInputError("Add at least one acceptance criterion.");
        return null;
    }

    showInputError("");
    return {
        description,
        user_story: userStory,
        acceptance_criteria: criteria,
    };
}

function showInputError(message) {
    const el = q("inputError");
    if (!message) {
        el.classList.add("hidden");
        el.textContent = "";
        return;
    }
    el.textContent = message;
    el.classList.remove("hidden");
}

function setBusy(isBusy) {
    q("generateBtn").disabled = isBusy;
    q("evaluateBtn").disabled = isBusy;
}

function showState(name) {
    q("emptyState").classList.add("hidden");
    q("loadingState").classList.add("hidden");
    q("errorState").classList.add("hidden");
    q("resultsState").classList.add("hidden");

    if (name === "empty") q("emptyState").classList.remove("hidden");
    if (name === "loading") q("loadingState").classList.remove("hidden");
    if (name === "error") q("errorState").classList.remove("hidden");
    if (name === "results") q("resultsState").classList.remove("hidden");
}

function startProgress() {
    stopProgress();
    const fill = q("progressFill");
    fill.style.width = "0%";

    let progress = 0;
    state.progressTimer = setInterval(() => {
        progress += Math.random() * 4;
        if (progress > 90) progress = 90;
        fill.style.width = `${progress}%`;
    }, 450);
}

function stopProgress() {
    if (state.progressTimer) {
        clearInterval(state.progressTimer);
        state.progressTimer = null;
    }
    q("progressFill").style.width = "100%";
}

function renderMetrics(payload) {
    const hasMetrics = typeof payload.accov_at_05 === "number";
    q("metricsSection").classList.toggle("hidden", !hasMetrics);
    if (!hasMetrics) return;

    q("metricAccov05").textContent = `${Math.round(payload.accov_at_05 * 100)}%`;
    q("metricAccov065").textContent = `${Math.round(payload.accov_at_065 * 100)}%`;
    q("metricNegRatio").textContent = `${Math.round(payload.negative_ratio * 100)}%`;
    q("metricCount").textContent = String(payload.num_test_cases ?? payload.test_cases?.length ?? 0);
}

function computeSummary(cases) {
    const rigorous = cases.filter((tc) => normalizeSuite(tc) === "rigorous").length;
    const supplemental = cases.length - rigorous;
    const riskCount = cases.filter((tc) => {
        const type = normalizeType(tc);
        return type === "negative" || type === "boundary";
    }).length;
    return {
        total: cases.length,
        rigorous,
        supplemental,
        riskCount,
    };
}

function renderSummary(cases) {
    const summary = computeSummary(cases);
    q("totalCount").textContent = String(summary.total);
    q("rigorousCount").textContent = String(summary.rigorous);
    q("supplementalCount").textContent = String(summary.supplemental);
    q("riskCount").textContent = String(summary.riskCount);
}

function searchableParts(tc) {
    const preconditions = Array.isArray(tc.preconditions) ? tc.preconditions : [];
    const covered = Array.isArray(tc.ac_covered) ? tc.ac_covered : [];
    const legacy = Array.isArray(tc.steps)
        ? tc.steps.flatMap((step) => [step.action || "", step.expected || ""])
        : [];

    return [
        tc.title || "",
        tc.type || "",
        tc.copy_paste_input || "",
        tc.expected_outcome || "",
        ...preconditions,
        ...covered,
        ...legacy,
    ];
}

function getFilteredCases() {
    const suiteFilter = q("suiteFilter").value;
    const typeFilter = q("typeFilter").value;
    const query = q("searchInput").value.trim().toLowerCase();

    return state.testCases.filter((tc) => {
        const suite = normalizeSuite(tc);
        const type = normalizeType(tc);

        if (suiteFilter !== "all" && suite !== suiteFilter) return false;
        if (typeFilter !== "all" && type !== typeFilter) return false;

        if (!query) return true;
        return searchableParts(tc).join(" ").toLowerCase().includes(query);
    });
}

function typeClass(type) {
    const t = normalizeType({ type });
    if (t === "negative") return "badge-negative";
    if (t === "boundary") return "badge-boundary";
    if (t === "integration") return "badge-integration";
    if (t === "performance") return "badge-performance";
    if (t === "security") return "badge-security";
    return "badge-functional";
}

function priorityClass(priority) {
    const p = String(priority || "").toLowerCase();
    if (p === "high") return "badge-high";
    if (p === "low") return "badge-low";
    return "badge-medium";
}

function suiteClass(tc) {
    return normalizeSuite(tc) === "rigorous" ? "suite-rigorous" : "suite-supplemental";
}

function renderLegacyStepRows(steps) {
    if (!Array.isArray(steps) || steps.length === 0) return "";

    const rows = steps
        .map((step, idx) => {
            const stepNo = escapeHtml(step.step ?? idx + 1);
            const action = escapeHtml(step.action || "");
            const expected = escapeHtml(step.expected || "-");
            return `
                <div class="step-row">
                    <span>${stepNo}</span>
                    <span>${action}</span>
                    <span>${expected}</span>
                </div>
            `;
        })
        .join("");

    return `
        <div class="step-table">
            <div class="step-head">
                <span>#</span>
                <span>Action</span>
                <span>Expected</span>
            </div>
            ${rows}
        </div>
    `;
}

function renderPreconditions(preconditions) {
    if (!Array.isArray(preconditions) || preconditions.length === 0) return "";
    const items = preconditions
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
    return `
        <section class="case-block">
            <p class="case-block-label">Preconditions</p>
            <ul class="precondition-list">${items}</ul>
        </section>
    `;
}

function renderCoveredCriteria(criteria) {
    if (!Array.isArray(criteria) || criteria.length === 0) return "";
    const chips = criteria
        .map((item) => `<span class="criteria-chip">${escapeHtml(item)}</span>`)
        .join("");
    return `
        <section class="case-block">
            <p class="case-block-label">Acceptance Criteria Covered</p>
            <div class="criteria-wrap">${chips}</div>
        </section>
    `;
}

function formatCaseForClipboard(tc) {
    const preconditions = Array.isArray(tc.preconditions) ? tc.preconditions : [];
    const criteria = Array.isArray(tc.ac_covered) ? tc.ac_covered : [];
    const lines = [
        `Title: ${tc.title || "Untitled"}`,
        `Type: ${tc.type || "Functional"}`,
        `Priority: ${tc.priority || "Medium"}`,
        "",
        "Preconditions:",
        preconditions.length > 0 ? preconditions.map((item) => `- ${item}`).join("\n") : "- None",
        "",
        "Copy-Paste Input:",
        tc.copy_paste_input || "(not provided)",
        "",
        "Expected Outcome:",
        tc.expected_outcome || "(not provided)",
        "",
        "Acceptance Criteria Covered:",
        criteria.length > 0 ? criteria.map((item) => `- ${item}`).join("\n") : "- Not specified",
    ];
    return lines.join("\n");
}

function buildCaseCard(tc, index) {
    const suite = normalizeSuite(tc);
    const suiteLabel = suite === "rigorous" ? "RIGOROUS" : "SUPPLEMENTAL";
    const title = escapeHtml(tc.title || "Untitled");
    const type = escapeHtml(tc.type || "Functional");
    const priority = escapeHtml(tc.priority || "Medium");
    const copyInput = escapeHtml(tc.copy_paste_input || "");
    const expected = escapeHtml(tc.expected_outcome || "");
    const preconditionsHtml = renderPreconditions(tc.preconditions);
    const criteriaHtml = renderCoveredCriteria(tc.ac_covered);
    const legacyStepsHtml =
        tc.copy_paste_input || tc.expected_outcome ? "" : renderLegacyStepRows(tc.steps);

    return `
        <article class="case-card ${suiteClass(tc)}">
            <header class="case-header">
                <div>
                    <p class="suite-tag">${suiteLabel}</p>
                    <h4>${title}</h4>
                </div>
                <div class="case-meta">
                    <span class="badge ${typeClass(tc.type)}">${type}</span>
                    <span class="badge ${priorityClass(tc.priority)}">${priority}</span>
                    <button class="mini-btn" onclick="copyInput(${index})" type="button">Copy Input</button>
                    <button class="mini-btn" onclick="copyCase(${index})" type="button">Copy Case</button>
                </div>
            </header>

            ${preconditionsHtml}

            <section class="case-block">
                <p class="case-block-label">Copy-Paste Input</p>
                <pre class="payload-box">${copyInput || "No explicit input provided."}</pre>
            </section>

            <section class="case-block">
                <p class="case-block-label">Expected Outcome</p>
                <p class="expected-text">${expected || "No expected outcome provided."}</p>
            </section>

            ${criteriaHtml}
            ${legacyStepsHtml}
        </article>
    `;
}

function renderGroupedResults(cases) {
    const container = q("resultsContainer");
    if (cases.length === 0) {
        container.innerHTML = `<p class="empty-filter">No test cases match the current filters.</p>`;
        return;
    }

    const rigorous = [];
    const supplemental = [];
    cases.forEach((tc, index) => {
        if (normalizeSuite(tc) === "rigorous") rigorous.push({ tc, index });
        else supplemental.push({ tc, index });
    });

    let html = "";
    if (rigorous.length > 0) {
        html += `<section class="group-block"><h3>Rigorous Coverage (${rigorous.length})</h3>`;
        html += rigorous.map(({ tc, index }) => buildCaseCard(tc, index)).join("");
        html += `</section>`;
    }
    if (supplemental.length > 0) {
        html += `<section class="group-block"><h3>Supplemental Checks (${supplemental.length})</h3>`;
        html += supplemental.map(({ tc, index }) => buildCaseCard(tc, index)).join("");
        html += `</section>`;
    }

    container.innerHTML = html;
}

function renderResults(payload) {
    state.resultsPayload = payload;
    state.testCases = Array.isArray(payload.test_cases) ? payload.test_cases : [];

    renderSummary(state.testCases);
    renderMetrics(payload);
    renderGroupedResults(getFilteredCases());

    q("downloadBtn").classList.remove("hidden");
    showState("results");
}

async function callApi(path, payload) {
    const response = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        let message = "Server error";
        try {
            const data = await response.json();
            message = data.detail || message;
        } catch (err) {
            void err;
        }
        throw new Error(message);
    }
    return response.json();
}

async function runRequest(path) {
    const payload = readPayload();
    if (!payload) return;

    setBusy(true);
    showState("loading");
    startProgress();

    try {
        const data = await callApi(path, payload);
        stopProgress();
        renderResults(data);
    } catch (err) {
        stopProgress();
        q("errorMessage").textContent = err.message || "Unable to connect to backend";
        showState("error");
        q("downloadBtn").classList.add("hidden");
    } finally {
        setBusy(false);
    }
}

async function checkServer() {
    const statusDot = document.querySelector(".status-dot");
    const statusText = document.querySelector(".status-text");

    try {
        const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5000) });
        const data = await response.json();
        statusDot.classList.add("online");
        statusDot.classList.remove("offline");
        statusText.textContent = `Online - ${data.chroma_collection_count} indexed requirements`;
    } catch (err) {
        statusDot.classList.add("offline");
        statusDot.classList.remove("online");
        statusText.textContent = "Backend offline";
    }
}

function loadSample() {
    q("description").value = "Users should be able to login with email and password and access a protected dashboard.";
    q("userStory").value = "As a registered user, I want secure login so I can access my account safely.";
    q("acceptanceCriteria").value = [
        "Valid credentials allow user login",
        "Invalid credentials show clear error",
        "Password input remains masked",
        "Unauthenticated users cannot access dashboard route",
    ].join("\n");
    showInputError("");
}

function downloadResults() {
    if (!state.resultsPayload) return;
    const blob = new Blob([JSON.stringify(state.resultsPayload, null, 2)], {
        type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "testgen_suite.json";
    a.click();
    URL.revokeObjectURL(url);
}

window.copyCase = async function copyCase(index) {
    const tc = state.testCases[index];
    if (!tc) return;
    const text = formatCaseForClipboard(tc);
    await navigator.clipboard.writeText(text);
};

window.copyInput = async function copyInput(index) {
    const tc = state.testCases[index];
    if (!tc) return;

    let text = String(tc.copy_paste_input || "").trim();
    if (!text && Array.isArray(tc.steps)) {
        text = tc.steps.map((step) => step.action || "").filter(Boolean).join("\n");
    }
    await navigator.clipboard.writeText(text || "No copy-paste input provided.");
};

function bindEvents() {
    q("generateBtn").addEventListener("click", () => runRequest("/generate"));
    q("evaluateBtn").addEventListener("click", () => runRequest("/evaluate"));
    q("downloadBtn").addEventListener("click", downloadResults);
    q("loadSampleBtn").addEventListener("click", loadSample);

    ["suiteFilter", "typeFilter", "searchInput"].forEach((id) => {
        q(id).addEventListener("input", () => {
            if (!state.resultsPayload) return;
            renderGroupedResults(getFilteredCases());
        });
    });
}

function init() {
    bindEvents();
    checkServer();
    setInterval(checkServer, 30000);
}

init();
