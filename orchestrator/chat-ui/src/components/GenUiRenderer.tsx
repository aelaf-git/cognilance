import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { UiItem } from "@/types";

type Source = { title: string; url: string; snippet: string };
type DataPoint = { label: string; value: number };

function ResearchSources({ summary, sources = [] }: { summary?: string; sources?: Source[] }) {
  return (
    <div className="space-y-3">
      {summary ? <p className="text-sm leading-relaxed text-white/90">{summary}</p> : null}
      {sources.length === 0 ? (
        <p className="text-sm text-muted">No sources returned.</p>
      ) : (
        sources.map((s, i) => (
          <div key={i} className="border-t border-border pt-3 first:border-0 first:pt-0">
            <a
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-semibold text-white hover:underline"
            >
              {s.title}
            </a>
            <p className="mt-0.5 font-mono text-xs text-dim">{s.url}</p>
            {s.snippet ? <p className="mt-2 text-sm text-muted">{s.snippet}</p> : null}
          </div>
        ))
      )}
    </div>
  );
}

function DataChart({
  title,
  chartType = "bar",
  series = [],
}: {
  title?: string;
  chartType?: "bar" | "line";
  series?: DataPoint[];
}) {
  return (
    <div>
      {title ? <p className="mb-3 text-sm font-semibold">{title}</p> : null}
      {series.length === 0 ? (
        <p className="text-sm text-muted">No data returned.</p>
      ) : (
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === "line" ? (
              <LineChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} stroke="#2a2a2a" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#888", fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "#888", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", borderRadius: 8 }}
                  labelStyle={{ color: "#fff" }}
                />
                <Line dataKey="value" type="monotone" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            ) : (
              <BarChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} stroke="#2a2a2a" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#888", fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "#888", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", borderRadius: 8 }}
                  labelStyle={{ color: "#fff" }}
                />
                <Bar dataKey="value" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function PythonCode({
  summary,
  filename,
  code,
}: {
  summary?: string;
  filename?: string;
  code?: string;
}) {
  return (
    <div className="space-y-3">
      {summary ? <p className="text-sm leading-relaxed text-white/90">{summary}</p> : null}
      {filename ? (
        <p className="font-mono text-xs text-registry">{filename}</p>
      ) : null}
      {code ? (
        <pre className="max-h-80 overflow-auto rounded-md border border-border bg-background p-3 font-mono text-xs leading-relaxed text-white/90 scrollbar-thin">
          {code}
        </pre>
      ) : (
        <p className="text-sm text-muted">No code returned.</p>
      )}
    </div>
  );
}

export function GenUiRenderer({ item }: { item: UiItem }) {
  const { name, props } = item;
  if (name === "research-sources") {
    return <ResearchSources summary={props.summary as string} sources={props.sources as Source[]} />;
  }
  if (name === "data-chart") {
    return (
      <DataChart
        title={props.title as string}
        chartType={props.chartType as "bar" | "line"}
        series={props.series as DataPoint[]}
      />
    );
  }
  if (name === "python-code") {
    return (
      <PythonCode
        summary={props.summary as string}
        filename={props.filename as string}
        code={props.code as string}
      />
    );
  }
  return <p className="text-sm text-muted">Unknown component: {name}</p>;
}
