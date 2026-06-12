"""Self-contained dev chat UI — served at GET /dev/chat on each worker/delegator."""

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


def _esc_js(value: str) -> str:
    return json.dumps(value)
