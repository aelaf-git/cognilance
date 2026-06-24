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
  html { -webkit-text-size-adjust: 100%; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    height: 100vh;
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
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: var(--bg);
    -webkit-overflow-scrolling: touch;
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
  }
  #composer {
    padding: 16px 28px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    display: flex;
    gap: 10px;
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
<div class="typing" id="typing" hidden>Planning and hiring…</div>
<form id="composer" onsubmit="return sendMsg(event)">
  <textarea id="input" rows="1" placeholder="Describe what you need…" autofocus></textarea>
  <button type="submit" id="send">Send</button>
</form>
<script>
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function addMsg(role, text, meta) {
  const el = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = esc(text) + (meta ? `<div class="meta">${esc(meta)}</div>` : "");
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

function renderUI(item) {
  const el = document.getElementById("messages");
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
  el.appendChild(wrap);
  el.scrollTop = el.scrollHeight;
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
  addMsg("user", text);
  btn.disabled = true;
  typing.hidden = false;
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      addMsg("error", data.text || "Request failed");
    } else {
      addMsg("agent", data.text || "(empty response)", data.meta || null);
      for (const item of data.ui || []) renderUI(item);
    }
  } catch (err) {
    addMsg("error", String(err));
  } finally {
    btn.disabled = false;
    typing.hidden = true;
    input.focus();
  }
  return false;
}

addMsg("system", "Orchestrator ready — planner will discover agents and hire specialists");
document.getElementById("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
});
</script>
</body>
</html>"""
