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
                <CartesianGrid vertical={false} stroke="#2c2834" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#9d9797", fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "#9d9797", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#15101f", border: "1px solid #2c2834", borderRadius: 8 }}
                  labelStyle={{ color: "#fff" }}
                />
                <Line dataKey="value" type="monotone" stroke="#ff492c" strokeWidth={2} dot={false} />
              </LineChart>
            ) : (
              <BarChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} stroke="#2c2834" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#9d9797", fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "#9d9797", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#15101f", border: "1px solid #2c2834", borderRadius: 8 }}
                  labelStyle={{ color: "#fff" }}
                />
                <Bar dataKey="value" fill="#fd8925" radius={[4, 4, 0, 0]} />
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

function looksLikeHtml(body: string): boolean {
  const t = body.trim().toLowerCase();
  if (!t.includes("<")) return false;
  return (
    /<(p|br|div|span|h[1-3]|ul|ol|li|a|strong|em|b|i)\b/.test(t) ||
    t.includes("font-family") ||
    t.includes("style=")
  );
}

function sanitizeEmailHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, "")
    .replace(/\son\w+\s*=\s*(['"]).*?\1/gi, "")
    .replace(/\son\w+\s*=\s*[^\s>]+/gi, "")
    .replace(/javascript:/gi, "");
}

function EmailDraft({
  to,
  subject,
  body,
  tone,
  status,
  gmail_message_id,
  format_notes,
}: {
  to?: string;
  subject?: string;
  body?: string;
  tone?: string;
  status?: string;
  gmail_message_id?: string | null;
  format_notes?: string;
}) {
  const sent = status === "sent" || Boolean(gmail_message_id);
  const htmlBody = Boolean(body && looksLikeHtml(body));
  return (
    <div className="space-y-3">
      {to ? (
        <p className="text-sm text-white/90">
          <span className="text-muted">To:</span> {to}
        </p>
      ) : null}
      {subject ? (
        <p className="text-sm font-semibold text-white">{subject}</p>
      ) : null}
      {tone ? <p className="text-xs text-dim">Tone: {tone}</p> : null}
      {format_notes ? <p className="text-xs text-dim">Format: {format_notes}</p> : null}
      {body ? (
        htmlBody ? (
          <div
            className="email-draft-html max-h-80 overflow-auto rounded-md border border-border bg-background p-3 text-sm leading-relaxed text-white/90 scrollbar-thin [&_a]:text-registry [&_a]:underline"
            dangerouslySetInnerHTML={{ __html: sanitizeEmailHtml(body) }}
          />
        ) : (
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background p-3 font-sans text-sm leading-relaxed text-white/90 scrollbar-thin">
            {body}
          </pre>
        )
      ) : (
        <p className="text-sm text-muted">No body returned.</p>
      )}
      {sent ? (
        <p className="text-xs text-registry">
          {gmail_message_id ? `Sent — Gmail ID: ${gmail_message_id}` : "Sent"}
        </p>
      ) : (
        <p className="text-xs text-dim">Draft — reply to approve and send.</p>
      )}
    </div>
  );
}

export function GenUiRenderer({ item }: { item: UiItem }) {
  const { name, props } = item;
  if (name === "email-draft") {
    return (
      <EmailDraft
        to={props.to as string}
        subject={props.subject as string}
        body={props.body as string}
        tone={props.tone as string}
        status={props.status as string}
        gmail_message_id={props.gmail_message_id as string | null}
        format_notes={props.format_notes as string | undefined}
      />
    );
  }
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
