import { cardStyle, headerStyle, useBrandColors } from "../theme";

type Source = { title: string; url: string; snippet: string };
type Props = { summary?: string; sources?: Source[] };

export default function ResearchSources({ summary, sources = [] }: Props) {
  const colors = useBrandColors();
  return (
    <div style={{ ...cardStyle(colors), maxWidth: 640 }}>
      <div style={headerStyle(colors)}>Research</div>
      {summary ? (
        <div style={{ padding: "12px 16px", color: colors.muted, fontSize: 14 }}>{summary}</div>
      ) : null}
      <div>
        {sources.map((s, i) => (
          <div
            key={i}
            style={{ padding: "12px 16px", borderTop: `1px solid ${colors.border}` }}
          >
            <a
              href={s.url}
              target="_blank"
              rel="noreferrer"
              style={{ color: colors.ember, fontWeight: 600, fontSize: 14 }}
            >
              {s.title}
            </a>
            <div style={{ color: colors.dim, fontSize: 12, marginTop: 2 }}>{s.url}</div>
            <div style={{ color: colors.foreground, fontSize: 13, marginTop: 6 }}>{s.snippet}</div>
          </div>
        ))}
        {sources.length === 0 ? (
          <div style={{ padding: "12px 16px", color: colors.dim, fontSize: 13 }}>
            No sources returned.
          </div>
        ) : null}
      </div>
    </div>
  );
}
