import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const TrendChart = ({ fullData, selected, pollutant }) => {
  if (!selected || selected.length === 0) return null;

  const station = selected[0].station;

  const trendData = fullData
    .filter(d => d.station === station && d.pollutant_id === pollutant)
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  return (
    <div>
      <LineChart width={400} height={250} data={trendData}>
        <CartesianGrid stroke="#444" />

        {/* ✅ SHOW limited dates properly */}
        <XAxis 
          dataKey="date"
          tick={{ fill: "#aaa", fontSize: 10 }}
          interval="preserveStartEnd"   // only first & last shown
        />

        {/* ✅ FIX graph overflow */}
        <YAxis 
          stroke="#ccc"
          domain={["dataMin - 1", "dataMax + 1"]}   // padding
        />

        {/* ✅ CLEAN tooltip */}
        <Tooltip 
          contentStyle={{ backgroundColor: "#222", border: "none" }}
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

      {/* Bottom label */}
      <div style={{ textAlign: "center", marginTop: "10px", color: "#aaa" }}>
       
      </div>
    </div>
  );
};

export default TrendChart;