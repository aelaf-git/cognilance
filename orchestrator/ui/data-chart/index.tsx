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
  border: "1px solid #2c2834",
  borderRadius: 12,
  padding: 16,
  fontFamily: '"IBM Plex Sans", system-ui, sans-serif',
  background: "#1a1624",
  color: "#e8e6e6",
};

const tick = { fill: "#9d9797", fontSize: 11 };
const tooltipStyle = {
  background: "#15101f",
  border: "1px solid #2c2834",
  borderRadius: 8,
};

export default function DataChart({
  title,
  chartType = "bar",
  series = [],
}: Props) {
  return (
    <div style={card}>
      {title ? (
        <div
          style={{
            fontWeight: 600,
            color: "#ffffff",
            marginBottom: 12,
            fontFamily: '"Space Grotesk", system-ui, sans-serif',
          }}
        >
          {title}
        </div>
      ) : null}
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          {chartType === "line" ? (
            <LineChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#2c2834" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={tick} />
              <YAxis tickLine={false} axisLine={false} tick={tick} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#fff" }} />
              <Line
                dataKey="value"
                type="monotone"
                stroke="#ff492c"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          ) : (
            <BarChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#2c2834" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={tick} />
              <YAxis tickLine={false} axisLine={false} tick={tick} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#fff" }} />
              <Bar dataKey="value" fill="#fd8925" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      {series.length === 0 ? (
        <div style={{ color: "#9d9797", fontSize: 13, marginTop: 8 }}>
          No data returned.
        </div>
      ) : null}
    </div>
  );
}
