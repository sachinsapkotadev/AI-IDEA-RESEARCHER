"""Live log viewer — captures logs and streams them via SSE."""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

router = APIRouter(tags=["logs"])

# ── In-memory ring buffer + subscriber list ──────────────────────────────
MAX_LOGS = 500
_log_buffer: deque[dict] = deque(maxlen=MAX_LOGS)
_subscribers: list[asyncio.Queue] = []


class LiveLogHandler(logging.Handler):
    """Logging handler that pushes records to the SSE broadcast system."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "time": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "level": record.levelname,
                "name": record.name,
                "message": self.format(record),
            }
        except Exception:
            return

        _log_buffer.append(entry)

        # Fan out to all subscribers (non-blocking)
        for q in _subscribers:
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                pass  # drop if subscriber is too slow


def install_handler(level: int = logging.DEBUG) -> LiveLogHandler:
    """Attach the live handler to the root logger."""
    handler = LiveLogHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.root.addHandler(handler)
    return handler


# ── SSE endpoint ─────────────────────────────────────────────────────────
async def _event_generator(queue: asyncio.Queue):
    """Yield SSE frames from a queue."""
    try:
        while True:
            entry = await queue.get()
            yield f"data: {json.dumps(entry)}\n\n"
    except asyncio.CancelledError:
        return


@router.get("/stream")
async def log_stream(request: Request):
    """SSE endpoint — streams new log lines in real-time."""
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    _subscribers.append(q)

    async def cleanup():
        await request.is_disconnected()
        if q in _subscribers:
            _subscribers.remove(q)

    # Start cleanup task
    asyncio.create_task(cleanup())

    return StreamingResponse(
        _event_generator(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── History endpoint ─────────────────────────────────────────────────────
@router.get("/history")
async def log_history():
    """Return buffered log lines (last MAX_LOGS)."""
    return {"logs": list(_log_buffer), "count": len(_log_buffer)}


# ── HTML dashboard ───────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def log_viewer_page():
    return LOG_HTML


LOG_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backend Logs — Live</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #c9d1d9; --text-dim: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --yellow: #d29922; --red: #f85149; --purple: #bc8cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; }

  /* ── Toolbar ── */
  .toolbar {
    display: flex; align-items: center; gap: 12px; padding: 10px 16px;
    background: var(--surface); border-bottom: 1px solid var(--border); flex-wrap: wrap;
  }
  .toolbar h1 { font-size: 14px; font-weight: 600; color: var(--accent); white-space: nowrap; }
  .status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-dim); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--red); }
  .dot.connected { background: var(--green); }
  .filters { display: flex; gap: 4px; }
  .filters button {
    padding: 3px 10px; border-radius: 12px; border: 1px solid var(--border);
    background: transparent; color: var(--text-dim); cursor: pointer; font-size: 11px;
    font-family: inherit; transition: all .15s;
  }
  .filters button.active { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,.08); }
  .filters button:hover { border-color: var(--accent); }
  .search-box {
    flex: 1; min-width: 160px; padding: 4px 10px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--bg); color: var(--text);
    font-family: inherit; font-size: 12px; outline: none;
  }
  .search-box:focus { border-color: var(--accent); }
  .actions { display: flex; gap: 6px; }
  .actions button {
    padding: 4px 12px; border-radius: 6px; border: 1px solid var(--border);
    background: transparent; color: var(--text-dim); cursor: pointer; font-size: 12px;
    font-family: inherit; transition: all .15s;
  }
  .actions button:hover { border-color: var(--accent); color: var(--text); }
  .actions button.pause { border-color: var(--yellow); color: var(--yellow); }
  .counter { font-size: 11px; color: var(--text-dim); white-space: nowrap; }

  /* ── Log area ── */
  #log-container {
    flex: 1; overflow-y: auto; padding: 8px 0; scroll-behavior: smooth;
  }
  .log-line {
    padding: 2px 16px; font-size: 12px; line-height: 1.7; white-space: pre-wrap;
    word-break: break-all; border-left: 3px solid transparent; transition: background .1s;
  }
  .log-line:hover { background: rgba(255,255,255,.03); }
  .log-line.ERROR, .log-line.CRITICAL { border-left-color: var(--red); background: rgba(248,81,73,.06); }
  .log-line.WARNING { border-left-color: var(--yellow); background: rgba(210,153,34,.05); }
  .log-line.INFO { border-left-color: var(--green); }
  .log-line.DEBUG { border-left-color: var(--purple); opacity: .7; }
  .ts { color: var(--text-dim); margin-right: 8px; }
  .lvl { font-weight: 600; min-width: 64px; display: inline-block; }
  .lvl.ERROR, .lvl.CRITICAL { color: var(--red); }
  .lvl.WARNING { color: var(--yellow); }
  .lvl.INFO { color: var(--green); }
  .lvl.DEBUG { color: var(--purple); }
  .name { color: var(--accent); margin-right: 8px; }
  mark { background: rgba(210,153,34,.35); color: inherit; border-radius: 2px; }

  /* ── Scrollbar ── */
  #log-container::-webkit-scrollbar { width: 6px; }
  #log-container::-webkit-scrollbar-track { background: transparent; }
  #log-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>

<div class="toolbar">
  <h1>📡 Backend Logs</h1>
  <div class="status">
    <div class="dot" id="statusDot"></div>
    <span id="statusText">Connecting…</span>
  </div>

  <div class="filters">
    <button data-level="ALL" class="active">ALL</button>
    <button data-level="ERROR">ERR</button>
    <button data-level="WARNING">WARN</button>
    <button data-level="INFO">INFO</button>
    <button data-level="DEBUG">DBG</button>
  </div>

  <input class="search-box" id="searchBox" placeholder="Filter text…" />
  <span class="counter" id="counter">0 lines</span>

  <div class="actions">
    <button id="pauseBtn" onclick="togglePause()">⏸ Pause</button>
    <button onclick="clearLogs()">🗑 Clear</button>
    <button onclick="exportLogs()">⬇ Export</button>
  </div>
</div>

<div id="log-container"></div>

<script>
const container = document.getElementById('log-container');
const counter   = document.getElementById('counter');
const pauseBtn  = document.getElementById('pauseBtn');
const searchBox = document.getElementById('searchBox');
const dot       = document.getElementById('statusDot');
const statusTxt = document.getElementById('statusText');

let paused = false;
let filter = 'ALL';
let searchText = '';
let allLogs = [];
let autoScroll = true;

// ── Scroll detection ──
container.addEventListener('scroll', () => {
  const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
  autoScroll = atBottom;
});

// ── SSE connect ──
let evtSource;
function connect() {
  evtSource = new EventSource('/logs/stream');

  evtSource.onopen = () => {
    dot.classList.add('connected');
    statusTxt.textContent = 'Connected';
  };

  evtSource.onmessage = (e) => {
    const entry = JSON.parse(e.data);
    allLogs.push(entry);
    if (allLogs.length > 2000) allLogs = allLogs.slice(-1500);
    if (!paused) renderEntry(entry);
  };

  evtSource.onerror = () => {
    dot.classList.remove('connected');
    statusTxt.textContent = 'Reconnecting…';
    evtSource.close();
    setTimeout(connect, 2000);
  };
}

// ── Render ──
function renderEntry(e) {
  if (filter !== 'ALL' && e.level !== filter) return;
  if (searchText && !e.message.toLowerCase().includes(searchText)) return;

  const div = document.createElement('div');
  div.className = 'log-line ' + e.level;

  let msg = escapeHtml(e.message);
  if (searchText) {
    const re = new RegExp('(' + escapeRegex(searchText) + ')', 'gi');
    msg = msg.replace(re, '<mark>$1</mark>');
  }

  div.innerHTML =
    '<span class="ts">' + e.time + '</span>' +
    '<span class="lvl">' + pad(e.level, 8) + '</span>' +
    '<span class="name">' + escapeHtml(e.name) + '</span>' +
    msg;

  container.appendChild(div);

  // limit DOM nodes
  while (container.children.length > 1500) container.removeChild(container.firstChild);

  counter.textContent = container.children.length + ' lines';
  if (autoScroll) container.scrollTop = container.scrollHeight;
}

function renderAll() {
  container.innerHTML = '';
  counter.textContent = '0 lines';
  allLogs.forEach(renderEntry);
}

// ── Controls ──
function togglePause() {
  paused = !paused;
  pauseBtn.textContent = paused ? '▶ Resume' : '⏸ Pause';
  pauseBtn.classList.toggle('pause', paused);
}

function clearLogs() {
  container.innerHTML = '';
  allLogs = [];
  counter.textContent = '0 lines';
}

function exportLogs() {
  const blob = new Blob([allLogs.map(e => e.time + ' ' + pad(e.level,8) + ' ' + e.name + ' ' + e.message).join('\\n')], {type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'backend-logs-' + new Date().toISOString().slice(0,10) + '.txt';
  a.click();
}

// ── Filter buttons ──
document.querySelectorAll('.filters button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelector('.filters .active').classList.remove('active');
    btn.classList.add('active');
    filter = btn.dataset.level;
    renderAll();
  });
});

// ── Search ──
searchBox.addEventListener('input', () => {
  searchText = searchBox.value.toLowerCase();
  renderAll();
});

// ── Helpers ──
function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\\\$&'); }
function pad(s, n) { return s.length >= n ? s : s + ' '.repeat(n - s.length); }

// ── Load history then connect SSE ──
fetch('/logs/history').then(r => r.json()).then(data => {
  data.logs.forEach(e => { allLogs.push(e); renderEntry(e); });
  connect();
}).catch(connect);
</script>
</body>
</html>"""
