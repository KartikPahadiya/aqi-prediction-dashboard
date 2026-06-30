import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer
} from "recharts";

const ChartView = ({ data }) => {
  if (!data) return null;

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid stroke="#333" />
          <XAxis
            dataKey="pollutant_id"
            angle={-45}
            textAnchor="end"
            interval={0}
            tick={{ fill: "white", fontSize: 10 }}
          />
          <YAxis tick={{ fill: "white" }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="avg_value"
            stroke="#00ffcc"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ChartView;