import { CSSProperties } from "react";

type Props = { summary?: string; filename?: string; code?: string };

const card: CSSProperties = {
  width: "100%",
  maxWidth: 720,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  overflow: "hidden",
  fontFamily: "ui-sans-serif, system-ui, sans-serif",
  background: "#fff",
};

const header: CSSProperties = {
  background: "linear-gradient(90deg,#0f766e,#14b8a6)",
  color: "#fff",
  padding: "12px 16px",
  fontWeight: 600,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
};

const codeBlock: CSSProperties = {
  margin: 0,
  padding: "14px 16px",
  background: "#0f172a",
  color: "#e2e8f0",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  fontSize: 13,
  lineHeight: 1.55,
  overflowX: "auto",
  whiteSpace: "pre",
};

export default function PythonCode({ summary, filename, code }: Props) {
  return (
    <div style={card}>
      <div style={header}>
        <span>Python Code</span>
        {filename ? (
          <span style={{ fontSize: 12, fontWeight: 500, opacity: 0.9 }}>{filename}</span>
        ) : null}
      </div>
      {summary ? (
        <div style={{ padding: "12px 16px", color: "#374151", fontSize: 14, lineHeight: 1.5 }}>
          {summary}
        </div>
      ) : null}
      {code ? (
        <pre style={codeBlock}>{code}</pre>
      ) : (
        <div style={{ padding: "12px 16px", color: "#9ca3af", fontSize: 13 }}>
          No code returned.
        </div>
      )}
    </div>
  );
}
