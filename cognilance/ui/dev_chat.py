"""Self-contained dev chat UIs — served at GET /dev/chat (agents + registry)."""

from __future__ import annotations

import html
import json


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


_SHARED_STYLES = r"""
  :root {
    --bg: #0b0e14;
    --panel: #11151f;
    --panel2: #161b28;
    --border: #232a3b;
    --text: #d7dce6;
    --muted: #7d8699;
    --accent: #5b8cff;
    --user: #2a3550;
    --agent: #1a2233;
    --green: #3ecf8e;
    --red: #ff6b6b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Inter", system-ui, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  header h1 { font-size: 16px; font-weight: 600; }
  header h1 span { color: var(--accent); }
  header .sub { color: var(--muted); font-size: 12px; }
  header .links { margin-left: auto; display: flex; gap: 12px; font-size: 12px; }
  header a { color: var(--accent); text-decoration: none; }
  header a:hover { text-decoration: underline; }
  #toolbar {
    padding: 10px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
  }
  #toolbar label { font-size: 12px; color: var(--muted); }
  #toolbar select {
    flex: 1;
    min-width: 200px;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
  }
  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .msg {
    max-width: 85%;
    padding: 12px 14px;
    border-radius: 12px;
    line-height: 1.5;
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .msg.user { align-self: flex-end; background: var(--user); border: 1px solid var(--border); }
  .msg.agent { align-self: flex-start; background: var(--agent); border: 1px solid var(--border); }
  .msg.system { align-self: center; color: var(--muted); font-size: 12px; background: transparent; padding: 4px; }
  .msg.error { align-self: flex-start; background: rgba(255,107,107,0.12); border-color: var(--red); color: #ffb4b4; }
  .meta { margin-top: 8px; font-size: 11px; color: var(--muted); font-family: ui-monospace, monospace; }
  #composer {
    padding: 16px 20px;
    background: var(--panel);
    border-top: 1px solid var(--border);
    display: flex;
    gap: 10px;
  }
  #input {
    flex: 1;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 14px;
    resize: none;
    min-height: 44px;
    max-height: 120px;
    font-family: inherit;
  }
  #input:focus { outline: none; border-color: var(--accent); }
  #send {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 0 20px;
    font-weight: 600;
    cursor: pointer;
    font-size: 14px;
  }
  #send:disabled { opacity: 0.5; cursor: not-allowed; }
  .typing { color: var(--muted); font-size: 12px; padding: 0 20px 8px; }
"""


def agent_chat_html(*, name: str, description: str = "", skills: list[str] | None = None) -> str:
    """Chat UI for a single running worker/delegator (same-origin A2A)."""
    skill_text = ", ".join(skills or [])
    desc = _esc(description or "Test your agent handler in the browser.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(name)} — Dev Chat</title>
<style>{_SHARED_STYLES}</style>
</head>
<body>
<header>
  <div>
    <h1><span>{_esc(name)}</span> — Dev Chat</h1>
    <div class="sub">{desc}</div>
  </div>
  <div class="links">
    <a href="/a2a" target="_blank">Agent card</a>
    <a href="/health" target="_blank">Health</a>
  </div>
</header>
<div id="toolbar" style="display:none"></div>
<div id="messages"></div>
<div class="typing" id="typing" hidden>Agent is thinking…</div>
<form id="composer" onsubmit="return sendMsg(event)">
  <textarea id="input" rows="1" placeholder="Message {_esc(name)}…" autofocus></textarea>
  <button type="submit" id="send">Send</button>
</form>
<script>
const AGENT = {_esc_js(name)};
const SKILLS = {_esc_js(skill_text)};

function esc(s) {{
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
}}

function addMsg(role, text, meta) {{
  const el = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = esc(text) + (meta ? `<div class="meta">${{esc(meta)}}</div>` : "");
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}}

async function sendMsg(e) {{
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
  try {{
    const res = await fetch("/a2a/tasks", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ input: {{ text }} }}),
    }});
    const data = await res.json();
    if (!res.ok || data.status?.state === "failed") {{
      addMsg("error", data.status?.message || "Request failed");
    }} else {{
      const out = data.output?.text || "(empty response)";
      let meta = "";
      const d = data.output?.data || {{}};
      if (d.hired) meta += "hired: " + d.hired;
      if (d.routed_skill) meta += (meta ? " · " : "") + "skill: " + d.routed_skill;
      if (d.mode) meta += (meta ? " · " : "") + "mode: " + d.mode;
      addMsg("agent", out, meta || null);
    }}
  }} catch (err) {{
    addMsg("error", String(err));
  }} finally {{
    btn.disabled = false;
    typing.hidden = true;
    input.focus();
  }}
  return false;
}}

addMsg("system", "Connected to " + AGENT + (SKILLS ? " [" + SKILLS + "]" : "") + ". Same handler as the terminal.");
document.getElementById("input").addEventListener("keydown", (e) => {{
  if (e.key === "Enter" && !e.shiftKey) {{ e.preventDefault(); document.getElementById("composer").requestSubmit(); }}
}});
</script>
</body>
</html>"""


def registry_chat_html(*, registry_url: str = "http://127.0.0.1:8080") -> str:
    """Chat UI on the registry — pick any registered agent to test."""
    base = _esc(registry_url.rstrip("/"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cognilance — Dev Chat</title>
<style>{_SHARED_STYLES}</style>
</head>
<body>
<header>
  <div>
    <h1><span>Cognilance</span> — Dev Chat</h1>
    <div class="sub">Test any agent registered on the local marketplace</div>
  </div>
  <div class="links">
    <a href="/dashboard">Dashboard</a>
    <a href="/v1/agents/discover?limit=50" target="_blank">Registry API</a>
  </div>
</header>
<div id="toolbar">
  <label for="agent-select">Agent</label>
  <select id="agent-select"><option value="">Loading agents…</option></select>
  <button type="button" id="refresh" style="background:var(--panel2);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 12px;cursor:pointer;">Refresh</button>
</div>
<div id="messages"></div>
<div class="typing" id="typing" hidden>Agent is thinking…</div>
<form id="composer" onsubmit="return sendMsg(event)">
  <textarea id="input" rows="1" placeholder="Select an agent and send a test message…"></textarea>
  <button type="submit" id="send">Send</button>
</form>
<script>
const REGISTRY = "{base}";

function esc(s) {{
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
}}

function addMsg(role, text, meta) {{
  const el = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = esc(text) + (meta ? `<div class="meta">${{esc(meta)}}</div>` : "");
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}}

let agents = [];

async function loadAgents() {{
  const sel = document.getElementById("agent-select");
  try {{
    const res = await fetch("/v1/agents/discover?limit=100");
    const data = await res.json();
    agents = data.agents || [];
    sel.innerHTML = "";
    if (!agents.length) {{
      sel.innerHTML = '<option value="">No agents registered</option>';
      return;
    }}
    for (const a of agents) {{
      const skills = (a.skills || []).map(s => s.name).join(", ");
      const opt = document.createElement("option");
      opt.value = a.url;
      opt.textContent = `${{a.name}} [${{skills}}]${{a.online ? "" : " (offline)"}}`;
      sel.appendChild(opt);
    }}
    addMsg("system", `Loaded ${{agents.length}} agent(s) from registry.`);
  }} catch (err) {{
    sel.innerHTML = '<option value="">Failed to load</option>';
    addMsg("error", "Could not load agents: " + err);
  }}
}}

async function sendMsg(e) {{
  e.preventDefault();
  const sel = document.getElementById("agent-select");
  const url = sel.value;
  if (!url) {{ addMsg("error", "Select an agent first."); return false; }}
  const input = document.getElementById("input");
  const btn = document.getElementById("send");
  const typing = document.getElementById("typing");
  const text = input.value.trim();
  if (!text) return false;
  const name = sel.options[sel.selectedIndex].textContent.split(" [")[0];
  input.value = "";
  addMsg("user", text);
  btn.disabled = true;
  typing.hidden = false;
  try {{
    const res = await fetch("/v1/dev/chat", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ agent_url: url, text }}),
    }});
    const data = await res.json();
    if (!res.ok || data.status?.state === "failed") {{
      addMsg("error", data.status?.message || data.detail || "Request failed");
    }} else {{
      const out = data.output?.text || "(empty response)";
      let meta = "via " + name;
      const d = data.output?.data || {{}};
      if (d.hired) meta += " · hired: " + (Array.isArray(d.hired) ? d.hired.join(" → ") : d.hired);
      addMsg("agent", out, meta);
    }}
  }} catch (err) {{
    addMsg("error", String(err));
  }} finally {{
    btn.disabled = false;
    typing.hidden = true;
  }}
  return false;
}}

document.getElementById("refresh").onclick = loadAgents;
document.getElementById("input").addEventListener("keydown", (e) => {{
  if (e.key === "Enter" && !e.shiftKey) {{ e.preventDefault(); document.getElementById("composer").requestSubmit(); }}
}});
loadAgents();
addMsg("system", "Hire chains appear on the dashboard in real time.");
</script>
</body>
</html>"""


def _esc_js(value: str) -> str:
    return json.dumps(value)
