import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, RefreshCw, Play, Square, Trash2, ChevronDown, ChevronUp, KeyRound, MessageSquare } from "lucide-react";
import {
  deleteAgent,
  fetchLogs,
  listAgents,
  startAgent,
  stopAgent,
  updateAgentEnv,
  uploadAgent,
} from "./api";
import { EnvEditor, buildEnvUpdate, rowsFromKeys } from "./components/EnvEditor";
import type { EnvRow, HostedAgent } from "./types";

const REGISTRY_URL = "http://127.0.0.1:8088/dashboard";
const ORCHESTRATOR_URL = "http://127.0.0.1:8200/chat";

const STATUS_STYLES: Record<string, string> = {
  uploaded: "text-muted",
  starting: "text-yellow-400",
  running: "text-registry",
  stopped: "text-dim",
  error: "text-red-400",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs font-medium capitalize ${STATUS_STYLES[status] ?? "text-muted"}`}>
      {status}
    </span>
  );
}

function RegistryDot({ online }: { online: boolean | null }) {
  if (online === null) return <span className="text-xs text-dim">—</span>;
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span
        className={`h-2 w-2 rounded-full ${online ? "bg-registry" : "bg-red-500/80"}`}
        title={online ? "Online in registry" : "Not in registry"}
      />
      {online ? "online" : "offline"}
    </span>
  );
}

export default function App() {
  const [agents, setAgents] = useState<HostedAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expandedLogs, setExpandedLogs] = useState<string | null>(null);
  const [editingEnvId, setEditingEnvId] = useState<string | null>(null);
  const [logs, setLogs] = useState<Record<string, string>>({});
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploadEnvRows, setUploadEnvRows] = useState<EnvRow[]>([
    { key: "GROQ_API_KEY", value: "" },
  ]);
  const [editEnvRows, setEditEnvRows] = useState<EnvRow[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listAgents();
      setAgents(data);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const selectFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError("Please upload a .zip file");
      return;
    }
    setPendingFile(file);
    setError(null);
  };

  const handleUpload = async () => {
    if (!pendingFile) return;
    setUploading(true);
    setError(null);
    try {
      await uploadAgent(pendingFile, uploadEnvRows);
      setPendingFile(null);
      setUploadEnvRows([
        { key: "GROQ_API_KEY", value: "" },
      ]);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) selectFile(file);
  };

  const runAction = async (id: string, action: "start" | "stop" | "delete") => {
    setBusyId(id);
    setError(null);
    try {
      if (action === "start") await startAgent(id);
      else if (action === "stop") await stopAgent(id);
      else {
        await deleteAgent(id);
        if (editingEnvId === id) setEditingEnvId(null);
      }
      if (action === "delete" && expandedLogs === id) setExpandedLogs(null);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  };

  const toggleLogs = async (id: string) => {
    if (expandedLogs === id) {
      setExpandedLogs(null);
      return;
    }
    setExpandedLogs(id);
    try {
      const text = await fetchLogs(id);
      setLogs((prev) => ({ ...prev, [id]: text }));
    } catch (exc) {
      setLogs((prev) => ({
        ...prev,
        [id]: exc instanceof Error ? exc.message : "Failed to load logs",
      }));
    }
  };

  const openEnvEditor = (agent: HostedAgent) => {
    setEditingEnvId(agent.id);
    setEditEnvRows(rowsFromKeys(agent.env_keys));
    setExpandedLogs(null);
  };

  const saveEnv = async (agent: HostedAgent) => {
    setBusyId(agent.id);
    setError(null);
    try {
      const payload = buildEnvUpdate(editEnvRows, agent.env_keys);
      await updateAgentEnv(agent.id, payload);
      setEditingEnvId(null);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to save environment");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="flex h-full min-h-screen flex-col bg-background">
      <header className="flex shrink-0 flex-wrap items-center gap-3 border-b border-border px-4 py-3 sm:gap-4 sm:px-6 sm:py-4">
        <img src="/icon.png" alt="Cognilance" className="h-6 w-6 object-contain sm:h-7 sm:w-7" />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Developer Portal
          </p>
          <p className="text-sm text-dim">Upload and host Cognilance agents locally</p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 sm:ml-auto sm:w-auto sm:gap-4">
          <a href={REGISTRY_URL} target="_blank" rel="noreferrer" className="text-xs text-registry hover:underline">
            Registry
          </a>
          <a href={ORCHESTRATOR_URL} target="_blank" rel="noreferrer" className="text-xs text-registry hover:underline">
            Orchestrator
          </a>
          <button type="button" onClick={() => void refresh()} className="text-xs text-dim hover:text-white">
            <RefreshCw className="inline h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 scrollbar-thin sm:p-6">
        {error ? (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        ) : null}

        <div
          className={`mb-6 rounded-xl border border-dashed px-4 py-6 transition-colors sm:px-6 sm:py-8 ${
            dragOver ? "border-registry bg-registry/5" : "border-border bg-surface/30"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <div className="flex flex-col items-center text-center">
            <Upload className="mb-3 h-8 w-8 text-muted" />
            <p className="text-sm text-muted">
              {pendingFile ? pendingFile.name : "Drag and drop an agent ZIP, or choose a file"}
            </p>
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              className="mt-2 rounded-md border border-border px-4 py-2 text-sm text-muted hover:text-white disabled:opacity-50"
            >
              Choose file
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) selectFile(file);
                e.target.value = "";
              }}
            />
          </div>

          {pendingFile ? (
            <div className="mt-6 space-y-4">
              <EnvEditor
                rows={uploadEnvRows}
                onChange={setUploadEnvRows}
                hint="Configure secrets before upload. Values are encrypted at rest and never shown again."
              />
              <div className="flex flex-wrap items-center justify-end gap-2">
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => {
                    setPendingFile(null);
      setUploadEnvRows([
        { key: "GROQ_API_KEY", value: "" },
      ]);
                  }}
                  className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => void handleUpload()}
                  className="rounded-md bg-registry/20 px-4 py-2 text-sm font-medium text-registry hover:bg-registry/30 disabled:opacity-50"
                >
                  {uploading ? "Uploading…" : "Upload agent"}
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-center text-xs text-dim">
              ZIP must include a .py file with a CognilanceWorker. You will configure environment
              variables before upload. Max 15 MB. Local-only — executes arbitrary code.
            </p>
          )}
        </div>

        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-white">Hosted agents</h2>
          {loading ? <span className="text-xs text-dim">Loading…</span> : null}
        </div>

        {agents.length === 0 && !loading ? (
          <p className="text-sm text-dim">No agents uploaded yet.</p>
        ) : (
          <div className="space-y-3">
            {agents.map((agent) => {
              const busy = busyId === agent.id;
              const logsOpen = expandedLogs === agent.id;
              const envOpen = editingEnvId === agent.id;
              const canEditEnv = agent.status !== "running" && agent.status !== "starting";
              return (
                <div key={agent.id} className="rounded-xl border border-border bg-surface/40 p-4">
                  <div className="flex flex-wrap items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
                        <StatusBadge status={agent.status} />
                        {agent.port ? (
                          <span className="font-mono text-xs text-dim">:{agent.port}</span>
                        ) : null}
                      </div>
                      <p className="mt-1 font-mono text-xs text-dim">{agent.entry_file}</p>
                      {agent.env_keys.length > 0 ? (
                        <p className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-dim">
                          <KeyRound className="h-3 w-3" />
                          {agent.env_keys.map((key) => (
                            <span
                              key={key}
                              className="rounded-full border border-border px-2 py-0.5 font-mono text-[11px]"
                            >
                              {key}
                            </span>
                          ))}
                        </p>
                      ) : (
                        <p className="mt-2 text-xs text-dim">No environment variables configured</p>
                      )}
                      {agent.error_message ? (
                        <p className="mt-1 text-xs text-red-400">{agent.error_message}</p>
                      ) : null}
                    </div>
                    <RegistryDot online={agent.registry_online} />
                    <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                      {agent.status !== "running" ? (
                        <button
                          type="button"
                          disabled={busy || agent.status === "starting"}
                          onClick={() => void runAction(agent.id, "start")}
                          className="flex min-h-[36px] flex-1 items-center justify-center gap-1 rounded-md bg-registry/20 px-2.5 py-1.5 text-xs text-registry hover:bg-registry/30 disabled:opacity-50 sm:flex-none"
                        >
                          <Play className="h-3 w-3" /> Start
                        </button>
                      ) : (
                        <>
                          {agent.port ? (
                            <a
                              href={`http://127.0.0.1:${agent.port}/chat`}
                              target="_blank"
                              rel="noreferrer"
                              className="flex min-h-[36px] flex-1 items-center justify-center gap-1 rounded-md border border-registry/40 bg-registry/15 px-2.5 py-1.5 text-xs text-registry hover:bg-registry/25 sm:flex-none"
                            >
                              <MessageSquare className="h-3 w-3" /> Chat
                            </a>
                          ) : null}
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void runAction(agent.id, "stop")}
                            className="flex min-h-[36px] items-center justify-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:text-white disabled:opacity-50"
                          >
                            <Square className="h-3 w-3" /> Stop
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        disabled={busy || !canEditEnv}
                        onClick={() => (envOpen ? setEditingEnvId(null) : openEnvEditor(agent))}
                        className="flex min-h-[36px] items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-dim hover:text-white disabled:opacity-50"
                        title={canEditEnv ? "Edit secrets" : "Stop the agent to edit secrets"}
                      >
                        <KeyRound className="h-3 w-3" /> Secrets
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void toggleLogs(agent.id)}
                        className="flex min-h-[36px] items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-dim hover:text-white"
                      >
                        {logsOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                        Logs
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(agent.id, "delete")}
                        className="flex min-h-[36px] items-center gap-1 rounded-md border border-red-500/30 px-2.5 py-1.5 text-xs text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                      >
                        <Trash2 className="h-3 w-3" /> Delete
                      </button>
                    </div>
                  </div>

                  {envOpen ? (
                    <div className="mt-4 space-y-3">
                      <EnvEditor
                        rows={editEnvRows}
                        onChange={setEditEnvRows}
                        existingKeys={agent.env_keys}
                        hint="Stored values are never shown. Re-enter a value to update, or remove the row to delete a key."
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setEditingEnvId(null)}
                          className="rounded-md border border-border px-3 py-1.5 text-xs text-muted hover:text-white"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void saveEnv(agent)}
                          className="rounded-md bg-registry/20 px-3 py-1.5 text-xs font-medium text-registry hover:bg-registry/30 disabled:opacity-50"
                        >
                          Save secrets
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {logsOpen ? (
                    <pre className="mt-3 max-h-64 overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-xs text-muted scrollbar-thin">
                      {logs[agent.id] ?? "Loading logs…"}
                    </pre>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
