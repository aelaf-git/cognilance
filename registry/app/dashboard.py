"""Registry dashboard — agent list (SDK-compatible)."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cognilance — Registry</title>
<link rel="icon" href="/icon.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0e0918;
    --surface: #1a1624;
    --surface2: #15101f;
    --border: #2c2834;
    --text: #ffffff;
    --muted: #c9c5c5;
    --dim: #9d9797;
    --ember: #ff492c;
    --ember-soft: #fd8925;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
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
    background: rgba(14, 9, 24, 0.92);
  }
  header img { height: 28px; width: 28px; object-fit: contain; flex-shrink: 0; }
  header .title {
    font-family: "Space Grotesk", system-ui, sans-serif;
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
  .tab.active { color: var(--text); border-bottom-color: var(--ember); }
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
    border-radius: 8px;
    padding: 18px 20px;
  }
  .card:hover { border-color: rgba(255, 73, 44, 0.35); }
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
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    margin-top: 4px;
    font-size: 11px;
    color: var(--dim);
    font-family: ui-monospace, monospace;
    word-break: break-all;
  }
  .card .meta a { color: var(--muted); text-decoration: none; }
  .card .meta a:hover { color: var(--text); text-decoration: underline; }
  .card .meta a.chat-btn {
    display: inline-flex;
    align-items: center;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 73, 44, 0.35);
    background: rgba(255, 73, 44, 0.12);
    color: var(--ember);
    font-weight: 600;
    font-family: inherit;
    text-decoration: none;
    white-space: nowrap;
  }
  .card .meta a.chat-btn:hover {
    background: rgba(255, 73, 44, 0.22);
    color: var(--ember-soft);
    text-decoration: none;
  }

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
    .card .meta a.chat-btn {
      width: 100%;
      justify-content: center;
      min-height: 44px;
      padding: 10px 12px;
    }
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
  <img src="/icon.png" alt="Cognilance">
  <span class="title">Registry</span>
  <div id="status"><div class="dot" id="status-dot"></div><span id="status-text">loading</span></div>
</header>

<section id="agents-panel">
  <div class="grid" id="agent-grid"></div>
</section>

<script>
let allAgents = [];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function renderCard(a) {
  const skills = (a.skills || []).map(s => `<span class="skill">${esc(s.name || s)}</span>`).join("");
  return `
    <div class="card">
      <div class="card-head">
        <div class="status ${a.online ? "online" : ""}"></div>
        <div class="name">${esc(a.name)}</div>
        <span class="role">worker</span>
      </div>
      <div class="desc">${esc(a.description || "No description.")}</div>
      <div class="skills">${skills || '<span class="skill">—</span>'}</div>
      <div class="meta">
        <a class="chat-btn" href="${esc(a.url)}/chat" target="_blank" rel="noreferrer">Chat with agent</a>
        <span>${esc(a.url)}${a.id ? " · " + esc(a.id.slice(0, 8)) : ""}</span>
      </div>
    </div>`;
}

function renderAgents() {
  const grid = document.getElementById("agent-grid");

  if (!allAgents.length) {
    grid.innerHTML = `<div class="empty-state">No workers registered.</div>`;
    return;
  }
  grid.innerHTML = allAgents.map(renderCard).join("");
}

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
