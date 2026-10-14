import { cardStyle, headerStyle, useBrandColors } from "../theme";

type Props = { summary?: string; filename?: string; code?: string };

export default function PythonCode({ summary, filename, code }: Props) {
  const colors = useBrandColors();
  return (
    <div style={cardStyle(colors)}>
      <div
        style={{
          ...headerStyle(colors),
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <span>Python Code</span>
        {filename ? (
          <span style={{ fontSize: 12, fontWeight: 500, opacity: 0.9 }}>{filename}</span>
        ) : null}
      </div>
      {summary ? (
        <div style={{ padding: "12px 16px", color: colors.muted, fontSize: 14, lineHeight: 1.5 }}>
          {summary}
        </div>
      ) : null}
      {code ? (
        <pre
          style={{
            margin: 0,
            padding: "14px 16px",
            background: colors.background,
            color: colors.foreground,
            fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
            fontSize: 13,
            lineHeight: 1.55,
            overflowX: "auto",
            whiteSpace: "pre",
          }}
        >
          {code}
        </pre>
      ) : (
        <div style={{ padding: "12px 16px", color: colors.dim, fontSize: 13 }}>No code returned.</div>
      )}
    </div>
  );
}
