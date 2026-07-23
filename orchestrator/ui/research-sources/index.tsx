import { CSSProperties } from "react";

type Source = { title: string; url: string; snippet: string };
type Props = { summary?: string; sources?: Source[] };

const card: CSSProperties = {
  width: "100%",
  maxWidth: 640,
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
};

const item: CSSProperties = {
  padding: "12px 16px",
  borderTop: "1px solid #2c2834",
};

export default function ResearchSources({ summary, sources = [] }: Props) {
  return (
    <div style={card}>
      <div style={header}>Research</div>
      {summary ? (
        <div style={{ padding: "12px 16px", color: "#c9c5c5", fontSize: 14 }}>
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
              style={{ color: "#ff492c", fontWeight: 600, fontSize: 14 }}
            >
              {s.title}
            </a>
            <div style={{ color: "#9d9797", fontSize: 12, marginTop: 2 }}>
              {s.url}
            </div>
            <div style={{ color: "#e8e6e6", fontSize: 13, marginTop: 6 }}>
              {s.snippet}
            </div>
          </div>
        ))}
        {sources.length === 0 ? (
          <div style={{ padding: "12px 16px", color: "#9d9797", fontSize: 13 }}>
            No sources returned.
          </div>
        ) : null}
      </div>
    </div>
  );
}
