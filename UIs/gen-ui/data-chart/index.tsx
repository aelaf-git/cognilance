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
import { cardStyle, useBrandColors } from "../theme";

type DataPoint = { label: string; value: number };
type Props = {
  title?: string;
  chartType?: "bar" | "line";
  series?: DataPoint[];
};

export default function DataChart({ title, chartType = "bar", series = [] }: Props) {
  const colors = useBrandColors();
  const tick = { fill: colors.dim, fontSize: 11 };
  const tooltipStyle = {
    background: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: 8,
  };
  return (
    <div style={{ ...cardStyle(colors), padding: 16, overflow: "visible" }}>
      {title ? (
        <div
          style={{
            fontWeight: 600,
            color: colors.foreground,
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
              <CartesianGrid vertical={false} stroke={colors.border} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={tick} />
              <YAxis tickLine={false} axisLine={false} tick={tick} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: colors.foreground }} />
              <Line
                dataKey="value"
                type="monotone"
                stroke={colors.ember}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          ) : (
            <BarChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} stroke={colors.border} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={tick} />
              <YAxis tickLine={false} axisLine={false} tick={tick} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: colors.foreground }} />
              <Bar dataKey="value" fill={colors.planner} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      {series.length === 0 ? (
        <div style={{ color: colors.dim, fontSize: 13, marginTop: 8 }}>No data returned.</div>
      ) : null}
    </div>
  );
}
