import { CSSProperties } from "react";

type Severity = "high" | "medium" | "low" | "info";
type Finding = {
  severity: Severity;
  title: string;
  detail: string;
  line?: number | null;
};
type Props = { summary?: string; findings?: Finding[] };

const card: CSSProperties = {
  width: "100%",
  maxWidth: 720,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  overflow: "hidden",
  fontFamily: "ui-sans-serif, system-ui, sans-serif",
  background: "#fff",
};

const SEVERITY_COLORS: Record<Severity, { bg: string; fg: string }> = {
  high: { bg: "#fee2e2", fg: "#b91c1c" },
  medium: { bg: "#ffedd5", fg: "#c2410c" },
  low: { bg: "#fef9c3", fg: "#a16207" },
  info: { bg: "#e0e7ff", fg: "#4338ca" },
};

function Badge({ severity }: { severity: Severity }) {
  const c = SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.info;
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
        padding: "2px 8px",
        borderRadius: 999,
      }}
    >
      {severity}
    </span>
  );
}

export default function CodeFindings({ summary, findings = [] }: Props) {
  return (
    <div style={card}>
      <div
        style={{
          background: "linear-gradient(90deg,#111827,#374151)",
          color: "#fff",
          padding: "12px 16px",
          fontWeight: 600,
        }}
      >
        Code Review {findings.length ? `· ${findings.length} finding(s)` : ""}
      </div>
      {summary ? (
        <div style={{ padding: "12px 16px", color: "#374151", fontSize: 14 }}>
          {summary}
        </div>
      ) : null}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#f9fafb", textAlign: "left" }}>
            <th style={th}>Severity</th>
            <th style={th}>Finding</th>
            <th style={{ ...th, width: 64, textAlign: "right" }}>Line</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, i) => (
            <tr key={i} style={{ borderTop: "1px solid #f1f5f9" }}>
              <td style={{ ...td, whiteSpace: "nowrap", verticalAlign: "top" }}>
                <Badge severity={f.severity} />
              </td>
              <td style={td}>
                <div style={{ fontWeight: 600, color: "#111827", fontSize: 14 }}>
                  {f.title}
                </div>
                <div style={{ color: "#4b5563", fontSize: 13, marginTop: 4 }}>
                  {f.detail}
                </div>
              </td>
              <td
                style={{
                  ...td,
                  textAlign: "right",
                  color: "#6b7280",
                  verticalAlign: "top",
                }}
              >
                {f.line ?? "—"}
              </td>
            </tr>
          ))}
          {findings.length === 0 ? (
            <tr>
              <td style={{ ...td, color: "#9ca3af" }} colSpan={3}>
                No findings.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

const th: CSSProperties = {
  padding: "8px 16px",
  fontSize: 11,
  fontWeight: 600,
  color: "#6b7280",
  textTransform: "uppercase",
};

const td: CSSProperties = {
  padding: "12px 16px",
  fontSize: 14,
};
