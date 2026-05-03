/* ── State ──────────────────────────────────────── */
let sessionId = null;
let needsRebuild = false;
let reindexPollTimer = null;

/* ── marked.js config ───────────────────────────── */
marked.setOptions({ breaks: true, gfm: true });

/* ── Init ───────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  loadFiles();
  setupUploadZone();
  document.getElementById('questionInput').focus();
});

/* ── Sidebar ────────────────────────────────────── */
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('open');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
}

/* ── File list ──────────────────────────────────── */
async function loadFiles() {
  try {
    const res = await fetch('/files');
    const data = await res.json();
    renderFileList(data.files || []);
  } catch (_) { /* sidebar just stays empty */ }
}

function renderFileList(files) {
  const list  = document.getElementById('fileList');
  const badge = document.getElementById('fileBadge');
  const empty = document.getElementById('fileEmpty');
  badge.textContent = files.length;

  // Remove old file items (keep empty placeholder)
  list.querySelectorAll('.file-item').forEach(el => el.remove());

  if (files.length === 0) {
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';

  files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = `
      <div class="file-type-icon file-type-${f.type}">${f.type.toUpperCase()}</div>
      <div class="file-info">
        <div class="file-name" title="${escHtml(f.name)}">${escHtml(f.name)}</div>
        <div class="file-size">${fmtSize(f.size)}</div>
      </div>
      <button class="file-del" onclick="deleteFile('${escHtml(f.name)}')" title="Delete">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
      </button>`;
    list.appendChild(item);
  });
}

async function deleteFile(filename) {
  if (!confirm(`Delete "${filename}"?`)) return;
  try {
    const res = await fetch(`/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    if (res.ok) {
      markNeedsRebuild(true);
      loadFiles();
    } else {
      const d = await res.json();
      alert(d.detail || 'Delete failed');
    }
  } catch (e) { alert('Delete failed: ' + e.message); }
}

/* ── Upload ─────────────────────────────────────── */
function setupUploadZone() {
  const zone  = document.getElementById('uploadZone');
  const input = document.getElementById('fileInput');

  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files.length) uploadFiles([...input.files]);
    input.value = '';
  });

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = [...e.dataTransfer.files].filter(f => /\.(pdf|docx|txt|md)$/i.test(f.name));
    if (files.length) uploadFiles(files);
  });
}

async function uploadFiles(files) {
  const prog   = document.getElementById('uploadProgress');
  const fill   = document.getElementById('progressFill');
  const status = document.getElementById('uploadStatus');
  prog.style.display = 'block';

  for (let i = 0; i < files.length; i++) {
    const pct = Math.round((i / files.length) * 100);
    fill.style.width = pct + '%';
    status.textContent = `Uploading ${files[i].name}…`;

    const form = new FormData();
    form.append('file', files[i]);
    try {
      const res = await fetch('/upload', { method: 'POST', body: form });
      if (!res.ok) {
        const d = await res.json();
        alert(`Failed to upload ${files[i].name}: ${d.detail}`);
      }
    } catch (e) { alert(`Upload error: ${e.message}`); }
  }

  fill.style.width = '100%';
  status.textContent = `${files.length} file(s) uploaded`;
  setTimeout(() => { prog.style.display = 'none'; fill.style.width = '0%'; }, 2000);

  markNeedsRebuild(true);
  loadFiles();
}

/* ── Rebuild ─────────────────────────────────────── */
function markNeedsRebuild(state) {
  needsRebuild = state;
  document.getElementById('rebuildNotice').style.display = state ? 'flex' : 'none';
}

async function rebuildKB() {
  const btn = document.getElementById('rebuildBtn');
  btn.disabled = true;
  setStatus('running', 'Rebuilding…');

  try {
    const res = await fetch('/reindex', { method: 'POST' });
    if (!res.ok && res.status !== 409) {
      const d = await res.json();
      setStatus('error', d.detail || 'Reindex failed');
      btn.disabled = false;
      return;
    }
    pollReindex();
  } catch (e) {
    setStatus('error', e.message);
    btn.disabled = false;
  }
}

function pollReindex() {
  clearInterval(reindexPollTimer);
  reindexPollTimer = setInterval(async () => {
    try {
      const res = await fetch('/reindex/status');
      const data = await res.json();
      if (data.status === 'running') {
        setStatus('running', 'Rebuilding…');
      } else if (data.status === 'done') {
        clearInterval(reindexPollTimer);
        setStatus('ready', 'Ready');
        markNeedsRebuild(false);
        document.getElementById('rebuildBtn').disabled = false;
      } else if (data.status === 'error') {
        clearInterval(reindexPollTimer);
        setStatus('error', 'Rebuild failed');
        document.getElementById('rebuildBtn').disabled = false;
        alert('Rebuild error: ' + data.message);
      }
    } catch (_) { clearInterval(reindexPollTimer); }
  }, 2000);
}

function setStatus(state, text) {
  const dot = document.getElementById('statusDot');
  const lbl = document.getElementById('statusText');
  dot.className = 'status-dot ' + state;
  lbl.textContent = text;
}

/* ── Chat submit ─────────────────────────────────── */
function handleSubmit(e) {
  e.preventDefault();
  const input = document.getElementById('questionInput');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  autoResize(input);
  sendQuestion(q);
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    document.getElementById('chatForm').dispatchEvent(new Event('submit'));
  }
}

async function sendQuestion(question) {
  hideWelcome();
  addUserBubble(question);

  const loadingId = addLoadingBubble();
  const btn = document.getElementById('sendButton');
  const input = document.getElementById('questionInput');
  btn.disabled = true;
  input.disabled = true;

  // Show hint after 5s
  const hintTimer = setTimeout(() => {
    const el = document.getElementById(loadingId);
    if (el) {
      const hint = document.createElement('div');
      hint.className = 'thinking-hint';
      hint.textContent = 'AI is thinking… this may take up to 20 seconds.';
      el.querySelector('.bubble').appendChild(hint);
    }
  }, 5000);

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionId })
    });
    clearTimeout(hintTimer);
    removeLoading(loadingId);

    const data = await res.json();
    if (res.ok) {
      sessionId = data.session_id;
      addBotBubble(data.answer, data.sources || [], data.confidence || 0);
    } else {
      addErrorBubble(data.detail || 'Failed to get answer.');
    }
  } catch (err) {
    clearTimeout(hintTimer);
    removeLoading(loadingId);
    addErrorBubble('Connection error: ' + err.message);
  } finally {
    btn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

/* ── Message rendering ───────────────────────────── */
function hideWelcome() {
  const w = document.getElementById('welcomeScreen');
  if (w) w.style.display = 'none';
}

function addUserBubble(text) {
  const row = document.createElement('div');
  row.className = 'msg-row user';
  row.innerHTML = `
    <div class="bubble">${escHtml(text)}</div>
    <div class="avatar avatar-user">You</div>`;
  appendMsg(row);
}

function addBotBubble(answer, sources, confidence) {
  const confClass = confidence >= 0.8 ? 'conf-high' : confidence >= 0.5 ? 'conf-mid' : 'conf-low';
  const confPct   = Math.round(confidence * 100);

  let sourcesHtml = '';
  if (sources.length) {
    const items = sources.map((s, i) => `
      <div class="source-card">
        <strong>Source ${i + 1}</strong>
        ${escHtml(s.content_preview || '')}
      </div>`).join('');
    sourcesHtml = `
      <div class="sources-list" id="sl-${Date.now()}">${items}</div>`;
  }

  const metaId = 'meta-' + Date.now();
  const row = document.createElement('div');
  row.className = 'msg-row bot';
  row.innerHTML = `
    <div class="avatar avatar-bot">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    </div>
    <div class="bubble">
      <div class="md-content">${marked.parse(answer)}</div>
      <div class="bubble-meta" id="${metaId}">
        <span class="conf-badge ${confClass}">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          ${confPct}% confidence
        </span>
        ${sources.length ? `
        <button class="sources-toggle" onclick="toggleSources(this)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
          ${sources.length} source${sources.length > 1 ? 's' : ''}
        </button>` : ''}
      </div>
      ${sourcesHtml}
    </div>`;
  appendMsg(row);
}

function addErrorBubble(msg) {
  const row = document.createElement('div');
  row.className = 'msg-row bot';
  row.innerHTML = `
    <div class="avatar avatar-bot">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    </div>
    <div class="bubble error-bubble">${escHtml(msg)}</div>`;
  appendMsg(row);
}

function addLoadingBubble() {
  const id = 'loading-' + Date.now();
  const row = document.createElement('div');
  row.id = id;
  row.className = 'msg-row bot';
  row.innerHTML = `
    <div class="avatar avatar-bot">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    </div>
    <div class="bubble">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>`;
  appendMsg(row);
  return id;
}

function removeLoading(id) {
  document.getElementById(id)?.remove();
}

function toggleSources(btn) {
  btn.classList.toggle('open');
  const bubble = btn.closest('.bubble');
  bubble.querySelector('.sources-list')?.classList.toggle('open');
}

function appendMsg(el) {
  const body = document.getElementById('chatMessages');
  body.appendChild(el);
  body.scrollTop = body.scrollHeight;
}

/* ── Chip shortcuts ──────────────────────────────── */
function useChip(btn) {
  document.getElementById('questionInput').value = btn.textContent;
  document.getElementById('chatForm').dispatchEvent(new Event('submit'));
}

/* ── New chat ────────────────────────────────────── */
function newChat() {
  sessionId = null;
  const body = document.getElementById('chatMessages');
  body.innerHTML = '';
  const welcome = document.createElement('div');
  welcome.className = 'welcome';
  welcome.id = 'welcomeScreen';
  welcome.innerHTML = `
    <div class="welcome-icon">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#7c8cf8" stroke-width="1.5">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    </div>
    <h2>How can I help you?</h2>
    <p>Ask me anything — I answer exclusively from the uploaded knowledge base documents.</p>
    <div class="welcome-chips">
      <button class="chip" onclick="useChip(this)">What is this document about?</button>
      <button class="chip" onclick="useChip(this)">Summarize the key points</button>
      <button class="chip" onclick="useChip(this)">What are the main provisions?</button>
    </div>`;
  body.appendChild(welcome);
  document.getElementById('questionInput').focus();
}

/* ── Textarea auto-resize ────────────────────────── */
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

/* ── Helpers ─────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtSize(bytes) {
  if (bytes < 1024)        return bytes + ' B';
  if (bytes < 1048576)     return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}
