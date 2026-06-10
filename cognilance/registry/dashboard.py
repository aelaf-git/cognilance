"""Self-contained HTML for the live trace dashboard (served at GET /dashboard)."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cognilance — Live Dashboard</title>
<style>
  :root {
    --bg: #0b0e14;
    --panel: #11151f;
    --panel2: #161b28;
    --border: #232a3b;
    --text: #d7dce6;
    --muted: #7d8699;
    --accent: #5b8cff;
    --green: #3ecf8e;
    --red: #ff6b6b;
    --amber: #ffc145;
    --think: #b48cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "JetBrains Mono", "Fira Code", ui-monospace, monospace;
    font-size: 13px;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  header h1 { font-size: 15px; font-weight: 600; letter-spacing: 0.4px; }
  header h1 span { color: var(--accent); }
  #conn {
    margin-left: auto;
    font-size: 11px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--red); }
  .dot.live { background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 50% { opacity: 0.4; } }

  #agents-bar {
    display: flex;
    gap: 8px;
    padding: 10px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
    min-height: 46px;
    align-items: center;
  }
  .agent-chip {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 5px 12px;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 16px;
    white-space: nowrap;
    font-size: 12px;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .agent-chip.active {
    border-color: var(--accent);
    box-shadow: 0 0 10px rgba(91, 140, 255, 0.35);
  }
  .agent-chip .skills { color: var(--muted); font-size: 10px; }
  #agents-bar .empty { color: var(--muted); font-size: 12px; }

  main { display: flex; flex: 1; overflow: hidden; }

  #sidebar {
    width: 300px;
    min-width: 300px;
    background: var(--panel);
    border-right: 1px solid var(--border);
    overflow-y: auto;
  }
  #sidebar h2, #detail-header h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    padding: 12px 16px 8px;
  }
  .trace-item {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
  }
  .trace-item:hover { background: var(--panel2); }
  .trace-item.selected { background: var(--panel2); border-left: 3px solid var(--accent); }
  .trace-item .root { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .trace-item .meta { display: flex; gap: 8px; margin-top: 4px; font-size: 10px; color: var(--muted); }
  .badge { padding: 1px 7px; border-radius: 8px; font-size: 10px; }
  .badge.working { background: rgba(255,193,69,0.15); color: var(--amber); }
  .badge.completed { background: rgba(62,207,142,0.15); color: var(--green); }
  .badge.failed { background: rgba(255,107,107,0.15); color: var(--red); }

  #detail { flex: 1; overflow-y: auto; padding: 16px 24px; }
  #detail .placeholder { color: var(--muted); padding: 40px; text-align: center; }

  .node {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 14px;
    overflow: hidden;
  }
  .node.working { border-color: rgba(255,193,69,0.5); }
  .node.failed { border-color: rgba(255,107,107,0.5); }
  .node-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
  }
  .node-head .name { font-weight: 600; font-size: 13px; }
  .node-head .dur { margin-left: auto; color: var(--muted); font-size: 11px; }
  .node-body { padding: 10px 14px; }
  .ev { display: flex; gap: 8px; padding: 4px 0; font-size: 12px; align-items: baseline; }
  .ev .ico { width: 18px; text-align: center; flex-shrink: 0; }
  .ev .txt { white-space: pre-wrap; word-break: break-word; }
  .ev.think .txt { color: var(--think); font-style: italic; }
  .ev.discover .txt { color: var(--accent); }
  .ev.hire_started .txt { color: var(--amber); }
  .ev.hire_completed .txt { color: var(--green); }
  .ev.hire_failed .txt, .ev.task_failed .txt { color: var(--red); }
  .ev.task_received .txt { color: var(--text); }
  .ev.task_completed .txt { color: var(--green); }
  .ev .t { color: var(--muted); font-size: 10px; flex-shrink: 0; min-width: 60px; }
  .children { margin-left: 34px; border-left: 2px dashed var(--border); padding-left: 18px; }
</style>
</head>
<body>
<header>
  <h1><span>Cognilance</span> — Live Dashboard</h1>
  <div id="conn"><div class="dot" id="conn-dot"></div><span id="conn-text">connecting…</span></div>
</header>
<div id="agents-bar"><span class="empty">No agents registered yet.</span></div>
<main>
  <div id="sidebar">
    <h2>Hire chains</h2>
    <div id="trace-list"></div>
  </div>
  <div id="detail"><div class="placeholder">Select a hire chain on the left,<br>or run a task to see it appear live.</div></div>
</main>
<script>
const ICONS = {
  task_received: "📥", think: "💭", discover: "🔍",
  hire_started: "🤝", hire_completed: "✅", hire_failed: "❌",
  task_completed: "✔", task_failed: "✖",
};

let traces = {};        // trace_id -> [events]
let traceOrder = [];    // newest first
let selected = null;
let agentActivity = {}; // agent_name -> timeout handle

function fmtTime(ts) {
  return new Date(ts).toLocaleTimeString([], {hour12: false}) ;
}

function traceStatus(events) {
  if (events.some(e => e.type === "task_failed" || e.type === "hire_failed")) return "failed";
  const roots = events.filter(e => e.depth === 0);
  if (roots.some(e => e.type === "task_completed" || e.type === "hire_completed")) return "completed";
  return "working";
}

function rootText(events) {
  const r = events.find(e => e.type === "task_received" || e.type === "hire_started");
  return (r && r.text) || "(no input)";
}

function renderTraceList() {
  const el = document.getElementById("trace-list");
  el.innerHTML = "";
  for (const tid of traceOrder) {
    const events = traces[tid];
    if (!events || !events.length) continue;
    const status = traceStatus(events);
    const agents = [...new Set(events.map(e => e.agent_name).filter(Boolean))];
    const div = document.createElement("div");
    div.className = "trace-item" + (tid === selected ? " selected" : "");
    div.onclick = () => { selected = tid; renderTraceList(); renderDetail(); };
    div.innerHTML = `
      <div class="root">${esc(rootText(events))}</div>
      <div class="meta">
        <span class="badge ${status}">${status}</span>
        <span>${agents.join(" → ") || "—"}</span>
        <span>${fmtTime(events[0].timestamp)}</span>
      </div>`;
    el.appendChild(div);
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// Build a tree of task nodes from flat events.
function buildTree(events) {
  const nodes = {};   // task_id -> node
  for (const e of events) {
    if (!nodes[e.task_id]) {
      nodes[e.task_id] = {
        id: e.task_id, parent: e.parent_task_id, depth: e.depth,
        agent: e.agent_name || "Manager", events: [], state: "working",
        start: e.timestamp, end: e.timestamp,
      };
    }
    const n = nodes[e.task_id];
    n.events.push(e);
    n.end = e.timestamp;
    if (e.agent_name) n.agent = e.agent_name;
    if (e.type === "task_completed") n.state = "completed";
    if (e.type === "task_failed") n.state = "failed";
  }
  const roots = [];
  for (const n of Object.values(nodes)) {
    if (n.parent && nodes[n.parent]) {
      (nodes[n.parent].children ??= []).push(n);
    } else {
      roots.push(n);
    }
  }
  return roots.sort((a, b) => new Date(a.start) - new Date(b.start));
}

function renderNode(n) {
  const dur = (new Date(n.end) - new Date(n.start)) / 1000;
  const evs = n.events.map(e => `
    <div class="ev ${e.type}">
      <span class="t">${fmtTime(e.timestamp)}</span>
      <span class="ico">${ICONS[e.type] || "•"}</span>
      <span class="txt">${esc(labelFor(e))}</span>
    </div>`).join("");
  const kids = (n.children || [])
    .sort((a, b) => new Date(a.start) - new Date(b.start))
    .map(renderNode).join("");
  return `
    <div class="node ${n.state}">
      <div class="node-head">
        <span class="badge ${n.state}">${n.state}</span>
        <span class="name">${esc(n.agent)}</span>
        <span class="dur">${dur.toFixed(1)}s</span>
      </div>
      <div class="node-body">${evs}</div>
    </div>
    ${kids ? `<div class="children">${kids}</div>` : ""}`;
}

function labelFor(e) {
  switch (e.type) {
    case "task_received": return `received: "${e.text}"`;
    case "task_completed": return e.text ? `done: "${truncate(e.text, 220)}"` : "done";
    case "task_failed": return `failed: ${e.text}`;
    default: return truncate(e.text, 220);
  }
}
function truncate(s, n) { return s && s.length > n ? s.slice(0, n) + "…" : s; }

function renderDetail() {
  const el = document.getElementById("detail");
  if (!selected || !traces[selected]) {
    el.innerHTML = '<div class="placeholder">Select a hire chain on the left,<br>or run a task to see it appear live.</div>';
    return;
  }
  const roots = buildTree(traces[selected]);
  el.innerHTML = roots.map(renderNode).join("");
}

function flashAgent(name) {
  document.querySelectorAll(".agent-chip").forEach(chip => {
    if (chip.dataset.name === name) {
      chip.classList.add("active");
      clearTimeout(agentActivity[name]);
      agentActivity[name] = setTimeout(() => chip.classList.remove("active"), 2500);
    }
  });
}

function addEvent(e) {
  if (!traces[e.trace_id]) {
    traces[e.trace_id] = [];
    traceOrder.unshift(e.trace_id);
    if (!selected) selected = e.trace_id;
  }
  traces[e.trace_id].push(e);
  if (e.agent_name) flashAgent(e.agent_name);
  renderTraceList();
  if (e.trace_id === selected) renderDetail();
}

async function loadAgents() {
  try {
    const res = await fetch("/v1/agents/discover?limit=100");
    const data = await res.json();
    const bar = document.getElementById("agents-bar");
    if (!data.agents.length) {
      bar.innerHTML = '<span class="empty">No agents registered yet.</span>';
      return;
    }
    bar.innerHTML = data.agents.map(a => `
      <div class="agent-chip" data-name="${esc(a.name)}">
        <div class="dot ${a.online ? "live" : ""}"></div>
        <span>${esc(a.name)}</span>
        <span class="skills">${a.skills.map(s => esc(s.name)).join(", ")}</span>
      </div>`).join("");
  } catch (err) { /* registry not ready yet */ }
}

async function loadTraces() {
  try {
    const res = await fetch("/v1/traces");
    const data = await res.json();
    for (const summary of data.traces.reverse()) {
      const detail = await fetch(`/v1/traces/${summary.trace_id}`).then(r => r.json());
      traces[summary.trace_id] = detail.events;
      if (!traceOrder.includes(summary.trace_id)) traceOrder.unshift(summary.trace_id);
    }
    if (!selected && traceOrder.length) selected = traceOrder[0];
    renderTraceList();
    renderDetail();
  } catch (err) { /* ignore */ }
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/v1/traces/ws`);
  ws.onopen = () => {
    document.getElementById("conn-dot").classList.add("live");
    document.getElementById("conn-text").textContent = "live";
  };
  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.kind === "event") addEvent(data.event);
  };
  ws.onclose = () => {
    document.getElementById("conn-dot").classList.remove("live");
    document.getElementById("conn-text").textContent = "reconnecting…";
    setTimeout(connectWS, 2000);
  };
}

loadAgents();
loadTraces();
connectWS();
setInterval(loadAgents, 5000);
</script>
</body>
</html>
"""
