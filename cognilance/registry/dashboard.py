"""Registry dashboard — black/white UI with agent tabs and live hire chains."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cognilance — Registry</title>
<style>
  :root {
    --bg: #000000;
    --surface: #0a0a0a;
    --surface2: #111111;
    --border: #222222;
    --text: #ffffff;
    --muted: #888888;
    --dim: #555555;
    --green: #ffffff;
    --amber: #cccccc;
    --red: #999999;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
  }
  header img { height: 28px; width: auto; }
  header .title {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
  }
  #conn {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--muted);
  }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--dim); }
  .dot.live { background: var(--text); animation: pulse 2s infinite; }
  @keyframes pulse { 50% { opacity: 0.35; } }

  .tabs {
    display: flex;
    gap: 0;
    padding: 0 28px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
  }
  .tab {
    padding: 14px 20px;
    font-size: 13px;
    font-weight: 500;
    color: var(--muted);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
    letter-spacing: 0.02em;
  }
  .tab:hover { color: var(--text); }
  .tab.active {
    color: var(--text);
    border-bottom-color: var(--text);
  }
  .tab .count {
    margin-left: 6px;
    font-size: 11px;
    color: var(--dim);
    font-weight: 400;
  }
  .tab.active .count { color: var(--muted); }

  #agents-panel {
    flex: 1;
    padding: 24px 28px;
    overflow-y: auto;
    min-height: 280px;
  }
  .empty-state {
    color: var(--muted);
    font-size: 14px;
    padding: 48px 0;
    text-align: center;
    line-height: 1.6;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 18px 20px;
    transition: border-color 0.2s;
  }
  .card:hover { border-color: #444; }
  .card.active { border-color: var(--text); }
  .card-head {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 10px;
  }
  .card-head .status {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--dim);
    margin-top: 5px;
    flex-shrink: 0;
  }
  .card-head .status.online { background: var(--text); }
  .card-head .name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
    flex: 1;
  }
  .card-head .role {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: 2px;
  }
  .card .desc {
    font-size: 13px;
    color: var(--muted);
    line-height: 1.5;
    margin-bottom: 12px;
  }
  .card .skills {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
  }
  .skill {
    font-size: 11px;
    color: var(--text);
    border: 1px solid var(--border);
    padding: 3px 8px;
    border-radius: 2px;
    background: var(--surface2);
  }
  .card .meta {
    font-size: 11px;
    color: var(--dim);
    font-family: ui-monospace, monospace;
    word-break: break-all;
  }
  .card .meta a { color: var(--muted); text-decoration: none; }
  .card .meta a:hover { color: var(--text); text-decoration: underline; }

  .manager-note {
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 20px;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--surface);
    line-height: 1.5;
  }

  #traces-section {
    border-top: 1px solid var(--border);
    background: var(--surface);
    display: flex;
    flex-direction: column;
    min-height: 320px;
    max-height: 42vh;
  }
  #traces-section h2 {
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted);
    padding: 14px 28px 10px;
  }
  .traces-body { display: flex; flex: 1; overflow: hidden; }

  #sidebar {
    width: 300px;
    min-width: 300px;
    border-right: 1px solid var(--border);
    overflow-y: auto;
    background: var(--bg);
  }
  .trace-item {
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
  }
  .trace-item:hover { background: var(--surface2); }
  .trace-item.selected { background: var(--surface2); border-left: 2px solid var(--text); }
  .trace-item .root {
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .trace-item .meta {
    display: flex;
    gap: 8px;
    margin-top: 5px;
    font-size: 10px;
    color: var(--muted);
  }
  .badge {
    padding: 1px 6px;
    border-radius: 2px;
    font-size: 10px;
    border: 1px solid var(--border);
    color: var(--muted);
  }
  .badge.working { color: var(--text); border-color: var(--muted); }
  .badge.completed { color: var(--text); }
  .badge.failed { color: var(--dim); }

  #detail { flex: 1; overflow-y: auto; padding: 16px 24px; background: var(--bg); }
  #detail .placeholder { color: var(--muted); padding: 32px; text-align: center; font-size: 13px; }

  .node {
    border: 1px solid var(--border);
    border-radius: 4px;
    margin-bottom: 12px;
    background: var(--surface);
  }
  .node-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }
  .node-head .name { font-weight: 600; font-size: 13px; }
  .node-head .dur { margin-left: auto; color: var(--muted); font-size: 11px; }
  .node-body { padding: 10px 14px; }
  .ev {
    display: flex;
    gap: 8px;
    padding: 3px 0;
    font-size: 12px;
    color: var(--muted);
    align-items: baseline;
  }
  .ev .txt { color: var(--text); white-space: pre-wrap; word-break: break-word; }
  .ev.think .txt { color: var(--muted); font-style: italic; }
  .ev .t { font-size: 10px; color: var(--dim); min-width: 56px; flex-shrink: 0; }
  .children { margin-left: 28px; border-left: 1px solid var(--border); padding-left: 16px; }
</style>
</head>
<body>
<header>
  <img src="/logo.png" alt="Cognilance">
  <span class="title">Registry</span>
  <div id="conn"><div class="dot" id="conn-dot"></div><span id="conn-text">connecting</span></div>
</header>

<nav class="tabs">
  <button class="tab active" data-tab="worker">Workers<span class="count" id="count-worker">0</span></button>
  <button class="tab" data-tab="delegator">Delegators<span class="count" id="count-delegator">0</span></button>
  <button class="tab" data-tab="manager">Managers<span class="count" id="count-manager">0</span></button>
</nav>

<section id="agents-panel">
  <div class="grid" id="agent-grid"></div>
</section>

<section id="traces-section">
  <h2>Live hire chains</h2>
  <div class="traces-body">
    <div id="sidebar"><div id="trace-list"></div></div>
    <div id="detail"><div class="placeholder">Hire chains appear here when managers and delegators run tasks.</div></div>
  </div>
</section>

<script>
const ICONS = {
  task_received: "→", think: "…", discover: "◎",
  hire_started: "⇢", hire_completed: "✓", hire_failed: "✗",
  task_completed: "✓", task_failed: "✗",
};

let allAgents = [];
let activeTab = "worker";
let traces = {};
let traceOrder = [];
let selected = null;
let agentActivity = {};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function agentRole(a) {
  const tags = (a.tags || []).map(t => t.toLowerCase());
  if (tags.includes("delegator")) return "delegator";
  if (tags.includes("worker")) return "worker";
  if (tags.includes("manager")) return "manager";
  const skills = (a.skills || []).map(s => (s.name || s).toLowerCase());
  if (skills.some(s => ["routing", "orchestration", "pipeline", "product-launch"].includes(s)))
    return "delegator";
  return "worker";
}

function activeManagers() {
  const registered = new Set(allAgents.map(a => a.name));
  const managers = {};
  for (const tid of traceOrder) {
    for (const e of traces[tid] || []) {
      if (!["discover", "hire_started"].includes(e.type) || e.depth !== 0) continue;
      const name = e.agent_name || "Manager";
      if (registered.has(name) && agentRole(allAgents.find(a => a.name === name) || {}) !== "manager")
        continue;
      if (!managers[name]) managers[name] = { name, last: e.timestamp, actions: 0, type: "session" };
      managers[name].actions++;
      if (new Date(e.timestamp) > new Date(managers[name].last)) managers[name].last = e.timestamp;
    }
  }
  for (const a of allAgents) {
    if (agentRole(a) === "manager") {
      managers[a.name] = { name: a.name, last: a.last_heartbeat, actions: 0, type: "registered", agent: a };
    }
  }
  return Object.values(managers).sort((a, b) => new Date(b.last) - new Date(a.last));
}

function agentsForTab(tab) {
  if (tab === "manager") return activeManagers();
  return allAgents.filter(a => agentRole(a) === tab);
}

function renderAgentCard(a) {
  if (a.type === "session") {
    return `
      <div class="card" data-name="${esc(a.name)}">
        <div class="card-head">
          <div class="status online"></div>
          <div class="name">${esc(a.name)}</div>
          <span class="role">active</span>
        </div>
        <div class="desc">CognilanceManager client — hiring via trace events, not registered on the marketplace.</div>
        <div class="meta">${a.actions} action(s) · last seen ${fmtTime(a.last)}</div>
      </div>`;
  }
  if (a.type === "registered" && a.agent) return renderRegisteredCard(a.agent);
  return renderRegisteredCard(a);
}

function renderRegisteredCard(a) {
  const skills = (a.skills || []).map(s => `<span class="skill">${esc(s.name || s)}</span>`).join("");
  const role = agentRole(a);
  return `
    <div class="card" data-name="${esc(a.name)}">
      <div class="card-head">
        <div class="status ${a.online ? "online" : ""}"></div>
        <div class="name">${esc(a.name)}</div>
        <span class="role">${esc(role)}</span>
      </div>
      <div class="desc">${esc(a.description || "No description.")}</div>
      <div class="skills">${skills || '<span class="skill">—</span>'}</div>
      <div class="meta">
        <a href="${esc(a.url)}/chat" target="_blank">${esc(a.url)}</a>
        ${a.id ? " · " + esc(a.id.slice(0, 8)) : ""}
      </div>
    </div>`;
}

function renderAgents() {
  const grid = document.getElementById("agent-grid");
  const items = agentsForTab(activeTab);

  document.getElementById("count-worker").textContent = allAgents.filter(a => agentRole(a) === "worker").length;
  document.getElementById("count-delegator").textContent = allAgents.filter(a => agentRole(a) === "delegator").length;
  document.getElementById("count-manager").textContent = activeManagers().length;

  if (!items.length) {
    const hints = {
      worker: "No workers registered.",
      delegator: "No delegators registered.",
      manager: "No active managers.",
    };
    grid.innerHTML = `<div class="empty-state">${hints[activeTab]}</div>`;
    return;
  }

  let html = "";
  if (activeTab === "manager") {
    html += `<div class="manager-note" style="grid-column:1/-1">Managers use <strong>CognilanceManager</strong> — they discover and hire without an A2A server. Active sessions appear below when they run.</div>`;
  }
  html += items.map(renderAgentCard).join("");
  grid.innerHTML = html;
  grid.className = activeTab === "manager" && items.length ? "grid" : "grid";
}

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    renderAgents();
  });
});

function fmtTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour12: false });
}

function traceStatus(events) {
  if (events.some(e => e.type === "task_failed" || e.type === "hire_failed")) return "failed";
  if (events.some(e => e.type === "task_completed" || e.type === "hire_completed")) return "completed";
  return "working";
}

function rootText(events) {
  const r = events.find(e => e.type === "task_received" || e.type === "hire_started");
  return (r && r.text) || "(no input)";
}

function renderTraceList() {
  const el = document.getElementById("trace-list");
  el.innerHTML = "";
  if (!traceOrder.length) {
    el.innerHTML = '<div class="empty-state" style="padding:24px;font-size:12px">No hire chains yet.</div>';
    return;
  }
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

function buildTree(events) {
  const nodes = {};
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
    if (n.parent && nodes[n.parent]) (nodes[n.parent].children ??= []).push(n);
    else roots.push(n);
  }
  return roots.sort((a, b) => new Date(a.start) - new Date(b.start));
}

function labelFor(e) {
  switch (e.type) {
    case "task_received": return `received: "${truncate(e.text, 180)}"`;
    case "task_completed": return e.text ? truncate(e.text, 180) : "completed";
    case "task_failed": return `failed: ${e.text}`;
    default: return truncate(e.text, 180);
  }
}
function truncate(s, n) { return s && s.length > n ? s.slice(0, n) + "…" : (s || ""); }

function renderNode(n) {
  const dur = (new Date(n.end) - new Date(n.start)) / 1000;
  const evs = n.events.map(e => `
    <div class="ev ${e.type}">
      <span class="t">${fmtTime(e.timestamp)}</span>
      <span class="txt">${esc(labelFor(e))}</span>
    </div>`).join("");
  const kids = (n.children || []).sort((a, b) => new Date(a.start) - new Date(b.start)).map(renderNode).join("");
  return `
    <div class="node">
      <div class="node-head">
        <span class="badge ${n.state}">${n.state}</span>
        <span class="name">${esc(n.agent)}</span>
        <span class="dur">${dur.toFixed(1)}s</span>
      </div>
      <div class="node-body">${evs}</div>
    </div>
    ${kids ? `<div class="children">${kids}</div>` : ""}`;
}

function renderDetail() {
  const el = document.getElementById("detail");
  if (!selected || !traces[selected]) {
    el.innerHTML = '<div class="placeholder">Select a hire chain to inspect the flow.</div>';
    return;
  }
  el.innerHTML = buildTree(traces[selected]).map(renderNode).join("");
}

function flashAgent(name) {
  document.querySelectorAll(".card").forEach(card => {
    if (card.dataset.name === name) {
      card.classList.add("active");
      clearTimeout(agentActivity[name]);
      agentActivity[name] = setTimeout(() => card.classList.remove("active"), 2000);
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
  if (activeTab === "manager") renderAgents();
  renderTraceList();
  if (e.trace_id === selected) renderDetail();
}

async function loadAgents() {
  try {
    const res = await fetch("/v1/agents/discover?limit=100");
    const data = await res.json();
    allAgents = data.agents || [];
    renderAgents();
  } catch (err) { /* registry starting */ }
}

async function loadTraces() {
  try {
    const res = await fetch("/v1/traces");
    const data = await res.json();
    for (const summary of (data.traces || []).reverse()) {
      const detail = await fetch(`/v1/traces/${summary.trace_id}`).then(r => r.json());
      traces[summary.trace_id] = detail.events;
      if (!traceOrder.includes(summary.trace_id)) traceOrder.unshift(summary.trace_id);
    }
    if (!selected && traceOrder.length) selected = traceOrder[0];
    renderAgents();
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
    document.getElementById("conn-text").textContent = "reconnecting";
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
