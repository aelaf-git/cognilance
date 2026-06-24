"""Built-in orchestrator chat UI — registry-style dark theme with generative UI."""

from __future__ import annotations

import html


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def orchestrator_chat_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cognilance — Orchestrator</title>
<style>
  :root {
    --bg: #000000;
    --surface: #0a0a0a;
    --surface2: #111111;
    --border: #222222;
    --text: #ffffff;
    --muted: #888888;
    --dim: #555555;
    --accent: #ffffff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html {
    height: 100%;
    -webkit-text-size-adjust: 100%;
    overflow: hidden;
  }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    height: 100%;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
  }
  header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }
  header img { height: 28px; width: auto; max-width: 36vw; object-fit: contain; flex-shrink: 0; }
  header .title {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    flex-shrink: 0;
  }
  header .sub {
    margin-left: auto;
    font-size: 12px;
    color: var(--dim);
    flex-shrink: 0;
  }
  #messages {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: var(--bg);
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    scroll-behavior: auto;
  }
  .msg {
    max-width: min(88%, 760px);
    padding: 12px 16px;
    border-radius: 4px;
    line-height: 1.55;
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
    border: 1px solid var(--border);
  }
  .msg.user {
    align-self: flex-end;
    background: var(--surface2);
    color: var(--text);
  }
  .msg.agent {
    align-self: flex-start;
    background: var(--surface);
    color: var(--text);
  }
  .msg.system {
    align-self: center;
    color: var(--muted);
    font-size: 12px;
    background: transparent;
    border: none;
    padding: 4px;
  }
  .msg.error {
    align-self: flex-start;
    background: var(--surface);
    color: var(--muted);
    border-color: var(--dim);
  }
  .meta {
    margin-top: 8px;
    font-size: 11px;
    color: var(--muted);
    font-family: ui-monospace, monospace;
    white-space: pre-wrap;
  }
  .thinking-block {
    align-self: flex-start;
    width: min(100%, 760px);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    background: var(--surface);
  }
  .thinking-head {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--dim);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .thinking-head .pulse {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--muted);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.35; }
    50% { opacity: 1; }
  }
  .thinking-body {
    padding: 14px;
    font-size: 13px;
    color: var(--muted);
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
    min-height: 1.5em;
    max-height: min(40vh, 320px);
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
  }
  .thinking-steps {
    padding: 0 14px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .thinking-step {
    border-left: 2px solid var(--border);
    padding-left: 10px;
    font-size: 12px;
  }
  .thinking-step .step-title {
    color: var(--text);
    font-weight: 600;
    margin-bottom: 2px;
  }
  .thinking-step .step-detail { color: var(--dim); }
  .thinking-status {
    padding: 8px 14px 12px;
    font-size: 11px;
    color: var(--dim);
    font-family: ui-monospace, monospace;
    border-top: 1px solid var(--border);
  }
  .answer-stream {
    align-self: flex-start;
    max-width: min(88%, 760px);
    padding: 12px 16px;
    border-radius: 4px;
    line-height: 1.55;
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
  }
  .gen-ui {
    align-self: flex-start;
    width: min(100%, 760px);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    background: var(--surface);
  }
  .gen-ui .ui-head {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .gen-ui .ui-body { padding: 14px; }
  .gen-ui .summary { font-size: 14px; color: var(--text); margin-bottom: 12px; line-height: 1.5; }
  .source-item {
    padding: 10px 0;
    border-top: 1px solid var(--border);
  }
  .source-item a { color: var(--text); font-weight: 600; font-size: 14px; text-decoration: none; }
  .source-item a:hover { text-decoration: underline; }
  .source-item .url { color: var(--dim); font-size: 12px; margin-top: 2px; }
  .source-item .snippet { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .chart-title { font-weight: 600; margin-bottom: 12px; font-size: 14px; }
  .bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 13px; }
  .bar-label { width: 88px; color: var(--muted); flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar-track { flex: 1; height: 10px; background: var(--surface2); border-radius: 2px; overflow: hidden; }
  .bar-fill { height: 100%; background: var(--text); border-radius: 2px; }
  .bar-value { width: 48px; text-align: right; color: var(--muted); flex-shrink: 0; }
  .findings-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .findings-table th {
    text-align: left;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--dim);
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
  }
  .findings-table td {
    padding: 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  .badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--muted);
  }
  .text-card-title { font-weight: 600; margin-bottom: 8px; font-size: 14px; }
  .text-card-body { font-size: 14px; color: var(--muted); line-height: 1.55; white-space: pre-wrap; }
  .empty { color: var(--dim); font-size: 13px; }
  .typing {
    color: var(--muted);
    font-size: 12px;
    padding: 0 28px 8px;
    letter-spacing: 0.02em;
    flex-shrink: 0;
  }
  #composer {
    padding: 16px 28px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    display: flex;
    gap: 10px;
    flex-shrink: 0;
  }
  #input {
    flex: 1;
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 12px 14px;
    font-size: 14px;
    resize: none;
    min-height: 46px;
    max-height: 140px;
    font-family: inherit;
  }
  #input:focus { outline: none; border-color: var(--muted); }
  #input::placeholder { color: var(--dim); }
  #send {
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 4px;
    padding: 0 22px;
    min-height: 46px;
    min-width: 72px;
    font-weight: 600;
    cursor: pointer;
    font-size: 13px;
    letter-spacing: 0.02em;
    flex-shrink: 0;
  }
  #send:disabled { opacity: 0.4; cursor: not-allowed; }
  @media (max-width: 768px) {
    header { padding: 16px 20px; }
    #messages { padding: 16px 20px; }
    #composer { padding: 12px 20px 16px; }
  }
</style>
</head>
<body>
<header>
  <img src="/logo.png" alt="Cognilance">
  <span class="title">Orchestrator</span>
  <span class="sub">planner · generative UI</span>
</header>
<div id="messages"></div>
<div class="typing" id="typing" hidden></div>
<form id="composer" onsubmit="return sendMsg(event)">
  <textarea id="input" rows="1" placeholder="Describe what you need…" autofocus></textarea>
  <button type="submit" id="send">Send</button>
</form>
<script>
const messagesEl = document.getElementById("messages");
let stickToBottom = true;

messagesEl.addEventListener("scroll", () => {
  const gap = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
  stickToBottom = gap < 96;
}, { passive: true });

function scrollToBottom(force) {
  if (!force && !stickToBottom) return;
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function addMsg(role, text, meta) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = esc(text) + (meta ? `<div class="meta">${esc(meta)}</div>` : "");
  messagesEl.appendChild(div);
  scrollToBottom(true);
  return div;
}

function createThinkingBlock() {
  const wrap = document.createElement("div");
  wrap.className = "thinking-block";
  wrap.innerHTML = `
    <div class="thinking-head"><span class="pulse"></span> Planning</div>
    <div class="thinking-body"></div>
    <div class="thinking-steps" hidden></div>
    <div class="thinking-status"></div>
  `;
  messagesEl.appendChild(wrap);
  scrollToBottom(true);
  return {
    root: wrap,
    body: wrap.querySelector(".thinking-body"),
    steps: wrap.querySelector(".thinking-steps"),
    status: wrap.querySelector(".thinking-status"),
    head: wrap.querySelector(".thinking-head"),
  };
}

function finishThinking(block) {
  if (!block) return;
  block.head.innerHTML = "Plan";
  const pulse = block.root.querySelector(".pulse");
  if (pulse) pulse.remove();
}

function renderPlanSteps(block, steps) {
  if (!block || !steps || !steps.length) return;
  block.steps.hidden = false;
  block.steps.innerHTML = steps.map((step, i) => `
    <div class="thinking-step">
      <div class="step-title">${i + 1}. ${esc(step.title)}</div>
      <div class="step-detail">${esc(step.detail)}</div>
    </div>
  `).join("");
  scrollToBottom();
}

function createAnswerStream() {
  const div = document.createElement("div");
  div.className = "answer-stream";
  messagesEl.appendChild(div);
  scrollToBottom(true);
  return div;
}

function renderUI(item) {
  const wrap = document.createElement("div");
  wrap.className = "gen-ui";
  const head = document.createElement("div");
  head.className = "ui-head";
  head.textContent = item.name.replace(/-/g, " ");
  wrap.appendChild(head);
  const body = document.createElement("div");
  body.className = "ui-body";
  body.innerHTML = renderComponent(item.name, item.props || {});
  wrap.appendChild(body);
  messagesEl.appendChild(wrap);
  scrollToBottom();
}

function renderComponent(name, props) {
  if (name === "research-sources") return renderResearch(props);
  if (name === "data-chart") return renderChart(props);
  if (name === "code-findings") return renderFindings(props);
  if (name === "text-card") return renderTextCard(props);
  return `<div class="empty">Unknown component: ${esc(name)}</div>`;
}

function renderResearch(p) {
  let html = "";
  if (p.summary) html += `<div class="summary">${esc(p.summary)}</div>`;
  const sources = p.sources || [];
  if (!sources.length) return html + `<div class="empty">No sources returned.</div>`;
  for (const s of sources) {
    html += `<div class="source-item">
      <a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.title)}</a>
      <div class="url">${esc(s.url)}</div>
      <div class="snippet">${esc(s.snippet || "")}</div>
    </div>`;
  }
  return html;
}

function renderChart(p) {
  let html = "";
  if (p.title) html += `<div class="chart-title">${esc(p.title)}</div>`;
  const series = p.series || [];
  if (!series.length) return html + `<div class="empty">No data returned.</div>`;
  const max = Math.max(...series.map(s => Number(s.value) || 0), 1);
  for (const point of series) {
    const value = Number(point.value) || 0;
    const pct = Math.round((value / max) * 100);
    html += `<div class="bar-row">
      <div class="bar-label" title="${esc(point.label)}">${esc(point.label)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-value">${esc(String(value))}</div>
    </div>`;
  }
  return html;
}

function renderFindings(p) {
  let html = "";
  if (p.summary) html += `<div class="summary">${esc(p.summary)}</div>`;
  const findings = p.findings || [];
  if (!findings.length) return html + `<div class="empty">No findings.</div>`;
  html += `<table class="findings-table"><thead><tr>
    <th>Severity</th><th>Finding</th><th style="text-align:right">Line</th>
  </tr></thead><tbody>`;
  for (const f of findings) {
    html += `<tr>
      <td><span class="badge">${esc(f.severity || "info")}</span></td>
      <td><div style="font-weight:600;color:var(--text)">${esc(f.title)}</div>
          <div style="color:var(--muted);margin-top:4px">${esc(f.detail || "")}</div></td>
      <td style="text-align:right;color:var(--dim)">${esc(f.line != null ? String(f.line) : "—")}</td>
    </tr>`;
  }
  return html + "</tbody></table>";
}

function renderTextCard(p) {
  return `<div class="text-card-title">${esc(p.title || "Response")}</div>
    <div class="text-card-body">${esc(p.body || "")}</div>`;
}

async function sendMsg(e) {
  e.preventDefault();
  const input = document.getElementById("input");
  const btn = document.getElementById("send");
  const typing = document.getElementById("typing");
  const text = input.value.trim();
  if (!text) return false;
  input.value = "";
  stickToBottom = true;
  addMsg("user", text);
  btn.disabled = true;
  typing.hidden = false;
  typing.textContent = "Starting planner…";

  let thinking = createThinkingBlock();
  let answerEl = null;
  let answerMeta = null;
  const uiItems = [];

  try {
    const res = await fetch("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok || !res.body) {
      addMsg("error", "Stream request failed");
      return false;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        let data;
        try { data = JSON.parse(line.slice(6)); } catch { continue; }

        if (data.event === "thinking" && data.delta) {
          thinking.body.textContent += data.delta;
          thinking.body.scrollTop = thinking.body.scrollHeight;
          scrollToBottom();
        } else if (data.event === "thinking_done") {
          finishThinking(thinking);
        } else if (data.event === "status" && data.message) {
          typing.textContent = data.message;
          thinking.status.textContent = data.message;
          scrollToBottom();
        } else if (data.event === "plan" && data.data) {
          renderPlanSteps(thinking, data.data.steps || []);
          if (data.data.reasoning) {
            thinking.status.textContent = data.data.reasoning;
          }
          scrollToBottom();
        } else if (data.event === "answer" && data.delta) {
          if (!answerEl) answerEl = createAnswerStream();
          answerEl.textContent += data.delta;
          scrollToBottom();
        } else if (data.event === "ui") {
          uiItems.push({ name: data.name, props: data.props || {} });
        } else if (data.event === "final") {
          answerMeta = data.meta || null;
          if (!answerEl && data.text) {
            answerEl = createAnswerStream();
            answerEl.textContent = data.text;
          }
          if (data.ui && data.ui.length) {
            for (const item of data.ui) uiItems.push(item);
          }
        } else if (data.event === "error") {
          addMsg("error", data.message || "Request failed");
        }
      }
    }

    if (answerEl && answerMeta) {
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = answerMeta;
      answerEl.appendChild(meta);
    }

    const seen = new Set();
    for (const item of uiItems) {
      const key = item.name + JSON.stringify(item.props || {});
      if (seen.has(key)) continue;
      seen.add(key);
      renderUI(item);
    }
    scrollToBottom(true);
  } catch (err) {
    addMsg("error", String(err));
  } finally {
    btn.disabled = false;
    typing.hidden = true;
    input.focus();
  }
  return false;
}

addMsg("system", "Orchestrator ready — planner thinks first, then hires specialists and streams the answer");
document.getElementById("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
});
</script>
</body>
</html>"""
