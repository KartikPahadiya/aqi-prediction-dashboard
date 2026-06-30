import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { memo, useMemo } from "react";

const TrendChart = memo(({ fullData, selected, pollutant }) => {
  if (!selected || selected.length === 0) return null;

  const station = selected[0].station;

  const trendData = useMemo(() => {
    return fullData
      .filter((d) => d.station === station && d.pollutant_id === pollutant)
      .sort((a, b) => new Date(a.date) - new Date(b.date));
  }, [fullData, station, pollutant]);

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={trendData}>
          <CartesianGrid stroke="#444" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#aaa", fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="#ccc"
            domain={["dataMin - 1", "dataMax + 1"]}
            tick={{ fill: "#aaa", fontSize: 10 }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "6px" }}
            labelStyle={{ color: "#00ffcc" }}
            formatter={(value) => [`${value}`, "Avg Value"]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Line
            type="monotone"
            dataKey="avg_value"
            stroke="#00ffcc"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
});

export default TrendChart;
