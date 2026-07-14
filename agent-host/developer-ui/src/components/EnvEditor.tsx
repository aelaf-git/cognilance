import { Plus, Trash2 } from "lucide-react";
import type { EnvRow } from "../types";

const SUGGESTED_KEYS = ["GROQ_API_KEY", "GROQ_MODEL"];

type EnvEditorProps = {
  rows: EnvRow[];
  onChange: (rows: EnvRow[]) => void;
  hint?: string;
  existingKeys?: string[];
};

export function EnvEditor({ rows, onChange, hint, existingKeys = [] }: EnvEditorProps) {
  const addRow = (key = "") => {
    onChange([...rows, { key, value: "" }]);
  };

  const updateRow = (index: number, patch: Partial<EnvRow>) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index));
  };

  const suggested = SUGGESTED_KEYS.filter(
    (key) => !rows.some((row) => row.key.trim().toUpperCase() === key),
  );

  return (
    <div className="rounded-xl border border-border bg-surface/40 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-white">Environment variables</p>
          <p className="mt-1 text-xs text-dim">
            {hint ??
              "Secrets are encrypted at rest and never returned by the API. Use UPPER_SNAKE_CASE keys."}
          </p>
        </div>
        <button
          type="button"
          onClick={() => addRow()}
          className="flex shrink-0 items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:text-white"
        >
          <Plus className="h-3 w-3" /> Add
        </button>
      </div>

      {rows.length === 0 ? (
        <p className="text-xs text-dim">No variables configured.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row, index) => {
            const isExisting = existingKeys.includes(row.key.trim().toUpperCase());
            return (
              <div key={`${row.key}-${index}`} className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <input
                  type="text"
                  value={row.key}
                  onChange={(e) => updateRow(index, { key: e.target.value.toUpperCase() })}
                  placeholder="GROQ_API_KEY"
                  className="w-full min-w-0 rounded-md border border-border bg-background px-3 py-2.5 font-mono text-xs text-white outline-none focus:border-registry/50 sm:min-w-[10rem] sm:flex-1 sm:py-2"
                  autoComplete="off"
                  spellCheck={false}
                />
                <input
                  type="password"
                  value={row.value}
                  onChange={(e) => updateRow(index, { value: e.target.value })}
                  placeholder={isExisting ? "Leave blank to keep existing" : "Secret value"}
                  className="w-full min-w-0 rounded-md border border-border bg-background px-3 py-2.5 font-mono text-xs text-white outline-none focus:border-registry/50 sm:min-w-[12rem] sm:flex-[2] sm:py-2"
                  autoComplete="new-password"
                  spellCheck={false}
                />
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  className="self-end rounded-md border border-border p-2 text-dim hover:text-red-400 sm:self-auto"
                  aria-label="Remove variable"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {suggested.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggested.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => addRow(key)}
              className="rounded-full border border-border px-2.5 py-1 font-mono text-[11px] text-dim hover:border-registry/40 hover:text-registry"
            >
              + {key}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function rowsFromKeys(keys: string[]): EnvRow[] {
  return keys.map((key) => ({ key, value: "" }));
}

export function buildEnvUpdate(rows: EnvRow[], existingKeys: string[]) {
  const set: Record<string, string> = {};
  const present = new Set<string>();

  for (const row of rows) {
    const key = row.key.trim().toUpperCase();
    if (!key) continue;
    present.add(key);
    if (row.value) {
      set[key] = row.value;
    }
  }

  const remove = existingKeys.filter((key) => !present.has(key));
  return { set, remove };
}
