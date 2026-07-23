"""Built-in chat UI — served at GET /chat on every Cognilance worker."""

from __future__ import annotations

import html
import json


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _esc_js(value: str) -> str:
    return json.dumps(value)


_CHAT_STYLES = r"""
  :root {
    --bg: #0e0918;
    --surface: #1a1624;
    --surface2: #15101f;
    --border: #2c2834;
    --text: #ffffff;
    --muted: #c9c5c5;
    --dim: #9d9797;
    --ember: #ff492c;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
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
  header img { height: 28px; width: 28px; object-fit: contain; flex-shrink: 0; }
  header .info { flex: 1; min-width: 0; }
  header .name {
    font-family: "Space Grotesk", system-ui, sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  header .sub {
    font-size: 12px;
    color: var(--muted);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  header .role {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  #skills-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 12px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }
  .skill {
    font-size: 11px;
    color: var(--text);
    border: 1px solid var(--border);
    padding: 3px 8px;
    border-radius: 2px;
    background: var(--surface2);
  }
  #messages {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    background: var(--bg);
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
  }
  .msg {
    max-width: min(78%, 640px);
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
  }
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
  #input:focus { outline: none; border-color: rgba(255, 73, 44, 0.45); }
  #input::placeholder { color: var(--dim); }
  #send {
    background: var(--ember);
    color: #ffffff;
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
    header { padding: 16px 20px; gap: 12px; }
    header img { height: 24px; }
    header .name { font-size: 14px; }
    header .sub { font-size: 11px; white-space: normal; }
    #skills-bar { padding: 10px 20px; }
    #messages { padding: 16px 20px; gap: 12px; }
    .msg { max-width: 88%; font-size: 13px; padding: 10px 14px; }
    .typing { padding: 0 20px 8px; }
    #composer { padding: 12px 20px 16px; }
  }

  @media (max-width: 480px) {
    header {
      padding: 14px 16px;
      flex-wrap: wrap;
      align-items: flex-start;
    }
    header .info { width: calc(100% - 44px); }
    header .role { margin-left: auto; }
    header .name { white-space: normal; }
    #skills-bar { padding: 10px 16px; }
    #messages { padding: 14px 16px; }
    .msg { max-width: 92%; }
    #composer {
      padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
      flex-direction: column;
      align-items: stretch;
    }
    #send { width: 100%; min-height: 44px; }
    #input { font-size: 16px; }
  }
"""


def agent_chat_html(
    *,
    name: str,
    description: str = "",
    skills: list[str] | None = None,
    role: str = "agent",
) -> str:
    """Chat UI for a running worker."""
    skill_list = skills or []
    desc = _esc(description or "Built-in Cognilance chat.")
    role_label = _esc(role)
    skills_html = "".join(f'<span class="skill">{_esc(s)}</span>' for s in skill_list)
    skills_bar = (
        f'<div id="skills-bar">{skills_html}</div>' if skills_html else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(name)} — Cognilance</title>
<link rel="icon" href="/icon.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_CHAT_STYLES}</style>
</head>
<body>
<header>
  <img src="/icon.png" alt="Cognilance">
  <div class="info">
    <div class="name">{_esc(name)}</div>
    <div class="sub">{desc}</div>
  </div>
  <span class="role">{role_label}</span>
</header>
{skills_bar}
<div id="messages"></div>
<div class="typing" id="typing" hidden>Thinking…</div>
<form id="composer" onsubmit="return sendMsg(event)">
  <textarea id="input" rows="1" placeholder="Message {_esc(name)}…" autofocus></textarea>
  <button type="submit" id="send">Send</button>
</form>
<script>
const AGENT = {_esc_js(name)};

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
      if (d.hired) meta += "hired: " + (Array.isArray(d.hired) ? d.hired.join(" → ") : d.hired);
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

addMsg("system", "Connected to " + AGENT);
document.getElementById("input").addEventListener("keydown", (e) => {{
  if (e.key === "Enter" && !e.shiftKey) {{ e.preventDefault(); document.getElementById("composer").requestSubmit(); }}
}});
</script>
</body>
</html>"""


def manager_chat_html(
    *,
    name: str,
    description: str = "",
) -> str:
    """Chat UI for a CognilanceManager — posts to POST /chat (no registry listing)."""
    desc = _esc(description or "Discover and hire agents from the marketplace.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(name)} — Cognilance</title>
<link rel="icon" href="/icon.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_CHAT_STYLES}</style>
</head>
<body>
<header>
  <img src="/icon.png" alt="Cognilance">
  <div class="info">
    <div class="name">{_esc(name)}</div>
    <div class="sub">{desc}</div>
  </div>
  <span class="role">manager</span>
</header>
<div id="messages"></div>
<div class="typing" id="typing" hidden>Working…</div>
<form id="composer" onsubmit="return sendMsg(event)">
  <textarea id="input" rows="1" placeholder="Describe what you need…" autofocus></textarea>
  <button type="submit" id="send">Send</button>
</form>
<script>
const MANAGER = {_esc_js(name)};

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
    const res = await fetch("/chat", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ text }}),
    }});
    const data = await res.json();
    if (!res.ok || data.error) {{
      addMsg("error", data.text || "Request failed");
    }} else {{
      addMsg("agent", data.text || "(empty response)", data.meta || null);
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

addMsg("system", "Connected to " + MANAGER + " — type agents to list marketplace workers");
document.getElementById("input").addEventListener("keydown", (e) => {{
  if (e.key === "Enter" && !e.shiftKey) {{ e.preventDefault(); document.getElementById("composer").requestSubmit(); }}
}});
</script>
</body>
</html>"""
