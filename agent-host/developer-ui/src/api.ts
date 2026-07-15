import type { EnvRow, HostedAgent } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

function envRowsToObject(rows: EnvRow[]): Record<string, string> {
  const env: Record<string, string> = {};
  for (const row of rows) {
    const key = row.key.trim().toUpperCase();
    if (!key || !row.value) continue;
    env[key] = row.value;
  }
  return env;
}

export async function listAgents(): Promise<HostedAgent[]> {
  const data = await request<{ agents: HostedAgent[] }>("/api/agents");
  return data.agents;
}

export async function uploadAgent(file: File, envRows: EnvRow[]): Promise<HostedAgent> {
  const form = new FormData();
  form.append("file", file);
  form.append("env", JSON.stringify(envRowsToObject(envRows)));
  const data = await request<{ agent: HostedAgent }>("/api/agents/upload", {
    method: "POST",
    body: form,
  });
  return data.agent;
}

export async function updateAgentEnv(
  agentId: string,
  payload: { set: Record<string, string>; remove: string[] },
): Promise<string[]> {
  const data = await request<{ keys: string[] }>(`/api/agents/${agentId}/env`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data.keys;
}

export async function startAgent(id: string): Promise<HostedAgent> {
  const data = await request<{ agent: HostedAgent }>(`/api/agents/${id}/start`, {
    method: "POST",
  });
  return data.agent;
}

export async function stopAgent(id: string): Promise<HostedAgent> {
  const data = await request<{ agent: HostedAgent }>(`/api/agents/${id}/stop`, {
    method: "POST",
  });
  return data.agent;
}

export async function deleteAgent(id: string): Promise<void> {
  await request(`/api/agents/${id}`, { method: "DELETE" });
}

export async function fetchLogs(id: string, lines = 200): Promise<string> {
  const data = await request<{ logs: string }>(`/api/agents/${id}/logs?lines=${lines}`);
  return data.logs;
}

export type RegistryAgentEarnings = {
  id: string | null;
  name: string;
  online: boolean;
  skills: string[];
  url: string | null;
  price_usd_cents: number;
  hires: number;
  earned_base_units: number;
  earned_usd: number;
};

export type EarningsResponse = {
  payout_wallet: string;
  balance_base_units: number;
  balance_usd: number;
  total_hires: number;
  total_earned_usd: number;
  agents: RegistryAgentEarnings[];
  ledger: Array<{
    entry_type: string;
    amount: number;
    created_at: string;
    hire_id?: string | null;
  }>;
  note: string;
};

export async function fetchEarnings(wallet: string): Promise<EarningsResponse> {
  return request<EarningsResponse>(
    `/api/earnings?wallet=${encodeURIComponent(wallet)}`,
  );
}

