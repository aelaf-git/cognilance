import { CSSProperties } from "react";

type Props = { summary?: string; filename?: string; code?: string };

const card: CSSProperties = {
  width: "100%",
  maxWidth: 720,
  border: "1px solid #2c2834",
  borderRadius: 12,
  overflow: "hidden",
  fontFamily: '"IBM Plex Sans", system-ui, sans-serif',
  background: "#1a1624",
  color: "#e8e6e6",
};

const header: CSSProperties = {
  background: "linear-gradient(90deg,#fd8925,#ff492c)",
  color: "#fff",
  padding: "12px 16px",
  fontWeight: 600,
  fontFamily: '"Space Grotesk", system-ui, sans-serif',
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
};

const codeBlock: CSSProperties = {
  margin: 0,
  padding: "14px 16px",
  background: "#0e0918",
  color: "#e8e6e6",
  fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
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
        <div style={{ padding: "12px 16px", color: "#c9c5c5", fontSize: 14, lineHeight: 1.5 }}>
          {summary}
        </div>
      ) : null}
      {code ? (
        <pre style={codeBlock}>{code}</pre>
      ) : (
        <div style={{ padding: "12px 16px", color: "#9d9797", fontSize: 13 }}>
          No code returned.
        </div>
      )}
    </div>
  );
}
