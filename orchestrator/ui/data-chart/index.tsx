import { CSSProperties } from "react";
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

type DataPoint = { label: string; value: number };
type Props = {
  title?: string;
  chartType?: "bar" | "line";
  series?: DataPoint[];
};

const card: CSSProperties = {
  width: "100%",
  maxWidth: 720,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  padding: 16,
  fontFamily: "ui-sans-serif, system-ui, sans-serif",
  background: "#fff",
};

export default function DataChart({
  title,
  chartType = "bar",
  series = [],
}: Props) {
  return (
    <div style={card}>
      {title ? (
        <div style={{ fontWeight: 600, color: "#111827", marginBottom: 12 }}>
          {title}
        </div>
      ) : null}
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          {chartType === "line" ? (
            <LineChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#eef2f7" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip />
              <Line
                dataKey="value"
                type="monotone"
                stroke="#4f46e5"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          ) : (
            <BarChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#eef2f7" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip />
              <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      {series.length === 0 ? (
        <div style={{ color: "#9ca3af", fontSize: 13, marginTop: 8 }}>
          No data returned.
        </div>
      ) : null}
    </div>
  );
}
