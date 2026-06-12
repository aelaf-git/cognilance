"""Registry dashboard — agent list (SDK-compatible)."""

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
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
  }
  header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 28px;
    border-bottom: 1px solid var(--border);
  }
  header img { height: 28px; width: auto; max-width: 40vw; object-fit: contain; flex-shrink: 0; }
  header .title {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    flex-shrink: 0;
  }
  #status {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--muted);
    flex-shrink: 0;
  }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--dim); }
  .dot.live { background: var(--text); }

  .tabs {
    display: flex;
    gap: 0;
    padding: 0 28px;
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar { display: none; }
  .tab {
    padding: 14px 20px;
    font-size: 13px;
    font-weight: 500;
    color: var(--muted);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    letter-spacing: 0.02em;
    white-space: nowrap;
    flex-shrink: 0;
    min-height: 44px;
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--text); border-bottom-color: var(--text); }
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
  }
  .empty-state {
    color: var(--muted);
    font-size: 14px;
    padding: 48px 0;
    text-align: center;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr));
    gap: 16px;
    width: 100%;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 18px 20px;
  }
  .card:hover { border-color: #444; }
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
    flex: 1;
    min-width: 0;
    word-break: break-word;
  }
  .card-head .role {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: 2px;
    flex-shrink: 0;
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

  @media (max-width: 768px) {
    header { padding: 16px 20px; gap: 12px; flex-wrap: wrap; }
    header img { height: 24px; }
    header .title { font-size: 12px; }
    .tabs { padding: 0 20px; }
    .tab { padding: 12px 16px; font-size: 12px; }
    #agents-panel { padding: 20px; }
    .grid { grid-template-columns: 1fr; gap: 12px; }
    .card { padding: 16px; }
    .card-head .name { font-size: 15px; }
  }

  @media (max-width: 480px) {
    header { padding: 14px 16px; }
    #status { width: 100%; margin-left: 0; margin-top: 4px; justify-content: flex-end; }
    .tabs { padding: 0 16px; }
    #agents-panel { padding: 16px; }
    .card-head { flex-wrap: wrap; }
    .card-head .role { margin-left: 18px; }
    .empty-state { padding: 32px 16px; font-size: 13px; }
  }
</style>
</head>
<body>
<header>
  <img src="/logo.png" alt="Cognilance">
  <span class="title">Registry</span>
  <div id="status"><div class="dot" id="status-dot"></div><span id="status-text">loading</span></div>
</header>

<nav class="tabs">
  <button class="tab active" data-tab="worker">Workers<span class="count" id="count-worker">0</span></button>
  <button class="tab" data-tab="delegator">Delegators<span class="count" id="count-delegator">0</span></button>
</nav>

<section id="agents-panel">
  <div class="grid" id="agent-grid"></div>
</section>

<script>
let allAgents = [];
let activeTab = "worker";

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function agentRole(a) {
  const tags = (a.tags || []).map(t => t.toLowerCase());
  if (tags.includes("delegator")) return "delegator";
  if (tags.includes("worker")) return "worker";
  const skills = (a.skills || []).map(s => (s.name || s).toLowerCase());
  if (skills.some(s => ["routing", "orchestration", "pipeline", "product-launch"].includes(s)))
    return "delegator";
  return "worker";
}

function renderCard(a) {
  const skills = (a.skills || []).map(s => `<span class="skill">${esc(s.name || s)}</span>`).join("");
  return `
    <div class="card">
      <div class="card-head">
        <div class="status ${a.online ? "online" : ""}"></div>
        <div class="name">${esc(a.name)}</div>
        <span class="role">${esc(agentRole(a))}</span>
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
  const workers = allAgents.filter(a => agentRole(a) === "worker");
  const delegators = allAgents.filter(a => agentRole(a) === "delegator");
  const items = activeTab === "worker" ? workers : delegators;

  document.getElementById("count-worker").textContent = workers.length;
  document.getElementById("count-delegator").textContent = delegators.length;

  if (!items.length) {
    const hint = activeTab === "worker" ? "No workers registered." : "No delegators registered.";
    grid.innerHTML = `<div class="empty-state">${hint}</div>`;
    return;
  }
  grid.innerHTML = items.map(renderCard).join("");
}

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    renderAgents();
  });
});

async function loadAgents() {
  const dot = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  try {
    const res = await fetch("/v1/agents/discover?limit=100");
    const data = await res.json();
    allAgents = data.agents || [];
    renderAgents();
    dot.classList.add("live");
    text.textContent = `${allAgents.length} agent${allAgents.length === 1 ? "" : "s"}`;
  } catch (err) {
    dot.classList.remove("live");
    text.textContent = "unavailable";
    document.getElementById("agent-grid").innerHTML =
      '<div class="empty-state">Could not load agents.</div>';
  }
}

loadAgents();
setInterval(loadAgents, 5000);
</script>
</body>
</html>
"""
