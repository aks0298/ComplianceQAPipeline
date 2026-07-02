const feed = document.getElementById("chat-feed");
const form = document.getElementById("audit-form");
const input = document.getElementById("video-url");
const submitBtn = document.getElementById("submit-btn");
const connectionPill = document.getElementById("connection-pill");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(date = new Date()) {
  return new Intl.DateTimeFormat([], {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusClass(status) {
  const normalized = String(status || "neutral").toLowerCase();
  if (["pass", "success", "ok"].includes(normalized)) return "success";
  if (["fail", "error", "critical"].includes(normalized)) return "error";
  if (["warning", "warn"].includes(normalized)) return "warning";
  return "info";
}

function createMessageShell(role, timestamp = formatTime()) {
  const message = document.createElement("article");
  message.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const meta = document.createElement("div");
  meta.className = "message-meta";

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "You" : "Assistant";

  const time = document.createElement("div");
  time.className = "message-time";
  time.textContent = timestamp;

  meta.append(roleLabel, time);
  bubble.appendChild(meta);
  message.appendChild(bubble);
  feed.appendChild(message);

  return { message, bubble };
}

function addWelcomeMessage() {
  const { bubble } = createMessageShell("assistant");
  const wrapper = document.createElement("div");
  wrapper.className = "welcome-card";
  wrapper.innerHTML = `
    <p>Send a YouTube URL and I will return the important workflow states in a clean audit view.</p>
    <div class="welcome-grid">
      <div class="welcome-stat"><span>Download</span><strong>Video indexing stage</strong></div>
      <div class="welcome-stat"><span>Analysis</span><strong>Transcript and rule review</strong></div>
      <div class="welcome-stat"><span>Result</span><strong>Findings and final status</strong></div>
    </div>
  `;
  bubble.appendChild(wrapper);
}

function addUserMessage(videoUrl) {
  const { bubble } = createMessageShell("user");
  const content = document.createElement("div");
  content.className = "message-content";
  const p = document.createElement("p");
  p.textContent = videoUrl;
  content.appendChild(p);
  bubble.appendChild(content);
}

function createLoadingMessage() {
  const { bubble } = createMessageShell("assistant");
  const content = document.createElement("div");
  content.className = "message-content loading-message";
  content.innerHTML = '<p class="loading-dots">Running the audit</p>';
  bubble.appendChild(content);
  return { bubble, content };
}

function renderChips(container, items) {
  const row = document.createElement("div");
  row.className = "chip-row";
  items.forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = item;
    row.appendChild(chip);
  });
  container.appendChild(row);
}

function renderTimeline(items) {
  const card = document.createElement("section");
  card.className = "section-card timeline-card";

  const title = document.createElement("h3");
  title.className = "section-title";
  title.textContent = "Useful states from the workflow";

  const copy = document.createElement("p");
  copy.className = "section-copy";
  copy.textContent = "Only the meaningful stages are shown here, not the noisy library logs.";

  const list = document.createElement("div");
  list.className = "timeline-list";

  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "timeline-item";

    const head = document.createElement("div");
    head.className = "timeline-head";

    const label = document.createElement("div");
    label.className = "timeline-title";
    label.textContent = `${index + 1}. ${item.title}`;

    const pill = document.createElement("span");
    pill.className = `status-pill ${statusClass(item.status)}`;
    pill.textContent = String(item.status || "info").toUpperCase();

    head.append(label, pill);

    const detail = document.createElement("div");
    detail.className = "timeline-detail";
    detail.textContent = item.detail || "";

    row.append(head, detail);
    list.appendChild(row);
  });

  card.append(title, copy, list);
  return card;
}

function renderFindings(findings) {
  const card = document.createElement("section");
  card.className = "section-card";

  const title = document.createElement("h3");
  title.className = "section-title";
  title.textContent = "Compliance findings";

  const list = document.createElement("div");
  list.className = "findings-list";

  if (!findings.length) {
    const empty = document.createElement("div");
    empty.className = "finding-card";
    empty.innerHTML = '<div class="finding-body">No findings were returned for this video.</div>';
    list.appendChild(empty);
  } else {
    findings.forEach((finding) => {
      const row = document.createElement("div");
      row.className = "finding-card";

      const head = document.createElement("div");
      head.className = "finding-head";

      const titleWrap = document.createElement("div");
      titleWrap.innerHTML = `
        <div class="finding-title">${escapeHtml(finding.category || "General")}</div>
        <div class="summary-copy">${escapeHtml(finding.description || "No description available.")}</div>
      `;

      const pill = document.createElement("span");
      pill.className = `status-pill ${statusClass(finding.severity)}`;
      pill.textContent = String(finding.severity || "info").toUpperCase();

      head.append(titleWrap, pill);
      row.appendChild(head);
      list.appendChild(row);
    });
  }

  card.append(title, list);
  return card;
}

function renderSummary(data) {
  const summary = data.summary || {};
  const card = document.createElement("section");
  card.className = "summary-card";

  const head = document.createElement("div");
  head.className = "summary-head";

  const left = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "summary-title";
  title.textContent = summary.final_status === "PASS" ? "Audit completed successfully" : "Audit completed with findings";

  const copy = document.createElement("p");
  copy.className = "summary-copy";
  copy.textContent = summary.final_report || "No report was returned.";

  left.append(title, copy);

  const status = document.createElement("span");
  status.className = `status-pill ${statusClass(summary.final_status)}`;
  status.textContent = String(summary.final_status || "UNKNOWN").toUpperCase();

  head.append(left, status);
  card.appendChild(head);

  renderChips(card, [
    `Video ID: ${summary.video_id || "n/a"}`,
    `Findings: ${summary.finding_count ?? 0}`,
    `Transcript words: ${summary.transcript_words ?? 0}`,
    `Platform: ${summary.platform || "youtube"}`,
  ]);

  return card;
}

function renderTranscript(data) {
  const section = document.createElement("section");
  section.className = "section-card";

  const title = document.createElement("h3");
  title.className = "section-title";
  title.textContent = "Transcript preview";

  const transcript = document.createElement("div");
  transcript.className = "transcript-box";
  transcript.textContent = data.transcript_preview || "No transcript preview is available.";

  section.append(title, transcript);
  return section;
}

function renderDebug(data) {
  const card = document.createElement("section");
  card.className = "debug-card";

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Raw workflow state";

  const pre = document.createElement("pre");
  pre.className = "debug-pre";
  pre.textContent = JSON.stringify(data.raw_state || data, null, 2);

  details.append(summary, pre);
  card.appendChild(details);
  return card;
}

function renderAssistantResponse(data) {
  const { bubble } = createMessageShell("assistant");
  const content = document.createElement("div");
  content.className = "response-grid";

  content.append(
    renderSummary(data),
    renderTimeline(data.timeline || []),
    renderFindings(data.findings || []),
    renderTranscript(data),
    renderDebug(data),
  );

  bubble.appendChild(content);
}

function updateConnectionPill(text, mode) {
  connectionPill.textContent = text;
  connectionPill.className = `status-pill ${mode}`;
}

async function runAudit(videoUrl) {
  const response = await fetch("/api/audit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ video_url: videoUrl }),
  });

  const payload = await response.json();

  if (!response.ok) {
    const detail = payload?.detail || "Audit failed.";
    throw new Error(detail);
  }

  return payload;
}

addWelcomeMessage();
feed.scrollTop = feed.scrollHeight;

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const videoUrl = input.value.trim();
  if (!videoUrl) {
    updateConnectionPill("Please add a URL", "warning");
    return;
  }

  addUserMessage(videoUrl);
  const loading = createLoadingMessage();
  feed.scrollTop = feed.scrollHeight;

  submitBtn.disabled = true;
  input.disabled = true;
  updateConnectionPill("Analyzing...", "info");

  try {
    const data = await runAudit(videoUrl);
    loading.bubble.parentElement.remove();
    renderAssistantResponse(data);
    updateConnectionPill(data.summary?.final_status || "Done", statusClass(data.summary?.final_status));
    input.value = "";
  } catch (error) {
    loading.bubble.parentElement.remove();

    const { bubble } = createMessageShell("assistant");
    const content = document.createElement("div");
    content.className = "response-grid";

    const card = document.createElement("section");
    card.className = "summary-card";
    card.innerHTML = `
      <div class="summary-head">
        <div>
          <h2 class="summary-title">The audit could not run</h2>
          <p class="summary-copy">${escapeHtml(error.message || "Unexpected error.")}</p>
        </div>
        <span class="status-pill error">ERROR</span>
      </div>
    `;

    content.appendChild(card);
    bubble.appendChild(content);
    updateConnectionPill("Error", "error");
  } finally {
    submitBtn.disabled = false;
    input.disabled = false;
    input.focus();
    feed.scrollTop = feed.scrollHeight;
  }
});
