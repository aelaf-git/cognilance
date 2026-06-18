import { CSSProperties } from "react";

type Source = { title: string; url: string; snippet: string };
type Props = { summary?: string; sources?: Source[] };

const card: CSSProperties = {
  width: "100%",
  maxWidth: 640,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  overflow: "hidden",
  fontFamily: "ui-sans-serif, system-ui, sans-serif",
  background: "#fff",
};

const header: CSSProperties = {
  background: "linear-gradient(90deg,#4338ca,#6366f1)",
  color: "#fff",
  padding: "12px 16px",
  fontWeight: 600,
};

const item: CSSProperties = {
  padding: "12px 16px",
  borderTop: "1px solid #f1f5f9",
};

export default function ResearchSources({ summary, sources = [] }: Props) {
  return (
    <div style={card}>
      <div style={header}>Research</div>
      {summary ? (
        <div style={{ padding: "12px 16px", color: "#374151", fontSize: 14 }}>
          {summary}
        </div>
      ) : null}
      <div>
        {sources.map((s, i) => (
          <div key={i} style={item}>
            <a
              href={s.url}
              target="_blank"
              rel="noreferrer"
              style={{ color: "#4f46e5", fontWeight: 600, fontSize: 14 }}
            >
              {s.title}
            </a>
            <div style={{ color: "#6b7280", fontSize: 12, marginTop: 2 }}>
              {s.url}
            </div>
            <div style={{ color: "#374151", fontSize: 13, marginTop: 6 }}>
              {s.snippet}
            </div>
          </div>
        ))}
        {sources.length === 0 ? (
          <div style={{ padding: "12px 16px", color: "#9ca3af", fontSize: 13 }}>
            No sources returned.
          </div>
        ) : null}
      </div>
    </div>
  );
}
