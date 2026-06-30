import { useEffect, useState, useCallback, useMemo } from "react";
import { loadCSV } from "./utils/parseCSV";
import MapView from "./components/MapView";
import "./App.css";
import ChartView from "./components/ChartView";
import TrendChart from "./components/TrendChart";
import "leaflet/dist/leaflet.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:7860";

const POLLUTANT_ORDER = ["PM2.5", "PM10", "NO2", "NH3", "SO2", "CO", "OZONE"];

const HEALTH_COLORS = {
  Good: "#00e400",
  Satisfactory: "#ffff00",
  Moderate: "#ff7e00",
  Poor: "#ff0000",
  "Very Poor": "#8f3f97",
  Severe: "#7e0023",
};

function getHealthColor(level) {
  return HEALTH_COLORS[level] || "#ccc";
}

function formatValue(val) {
  if (val === null || val === undefined || isNaN(val)) return "N/A";
  return Number(val).toFixed(2);
}

function App() {
  const [data, setData] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [selected, setSelected] = useState(null);
  const [selectedPollutant, setSelectedPollutant] = useState("PM2.5");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedState, setSelectedState] = useState("");
  const [selectedStation, setSelectedStation] = useState("");
  const [tempState, setTempState] = useState("");
  const [tempStation, setTempStation] = useState("");
  const [tempDate, setTempDate] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [predLoading, setPredLoading] = useState(false);
  const [predError, setPredError] = useState(null);

  const sortedSelected = useMemo(() => {
    if (!selected) return [];
    return POLLUTANT_ORDER.map((p) =>
      selected.find((item) => item.pollutant_id === p)
    ).filter(Boolean);
  }, [selected]);

  const dates = useMemo(() => {
    return [
      ...new Set(
        data
          .filter(
            (d) =>
              (!tempState || d.state === tempState) &&
              (!tempStation || d.station === tempStation)
          )
          .map((d) => d.date)
      ),
    ].sort((a, b) => new Date(a) - new Date(b));
  }, [data, tempState, tempStation]);

  const stations = useMemo(() => {
    return [
      ...new Set(
        data
          .filter((d) => !tempState || d.state === tempState)
          .map((d) => d.station)
      ),
    ].sort();
  }, [data, tempState]);

  useEffect(() => {
    loadCSV().then((res) => {
      setData(res);
      setFiltered(res);
    });
  }, []);

  const fetchPrediction = useCallback(
    async (station, state, pollutant) => {
      setPredLoading(true);
      setPredError(null);
      setPrediction(null);

      const stationName = station ? station.trim() : "";
      const stateName = state ? state.trim() : "";

      try {
        const res = await fetch(`${API_BASE}/predict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            station_name: stationName,
            state: stateName,
            pollutant: pollutant,
          }),
        });

        if (!res.ok) {
          let errMsg = `Server error: ${res.status}`;
          try {
            const errData = await res.json();
            errMsg = errData.detail || errData.message || `HTTP ${res.status}`;
          } catch (parseErr) {
            errMsg = `Server returned ${res.status}. Station "${stationName}" may not have enough data for ${pollutant}.`;
          }
          throw new Error(errMsg);
        }

        const result = await res.json();
        setPrediction(result);
      } catch (err) {
        console.error("Prediction error:", err);
        if (
          err.message &&
          (err.message.includes("fetch") || err.message.includes("Failed to fetch"))
        ) {
          setPredError(`Cannot connect to backend at ${API_BASE}. Is it running?`);
        } else {
          setPredError(err.message || "Prediction failed");
        }
        setPrediction(null);
      } finally {
        setPredLoading(false);
      }
    },
    []
  );

  const handleMapClick = useCallback(
    (stationInfo) => {
      const { station, state } = stationInfo;

      setTempState(state);
      setTempStation(station);
      setSelectedState(state);
      setSelectedStation(station);

      const stationData = data.filter((d) => d.station === station);
      const stationDates = [...new Set(stationData.map((d) => d.date))].sort();
      const latestDate = stationDates[stationDates.length - 1] || "";
      setSelectedDate(latestDate);
      setTempDate(latestDate);

      const latestData = stationData.filter((d) => d.date === latestDate);
      setSelected(latestData);

      fetchPrediction(station, state, selectedPollutant);
    },
    [data, selectedPollutant, fetchPrediction]
  );

  const handleApply = useCallback(async () => {
    setSelectedState(tempState);
    setSelectedStation(tempStation);
    setSelectedDate(tempDate);

    const filteredData = data.filter(
      (d) =>
        (!tempState || d.state === tempState) &&
        (!tempStation || d.station === tempStation) &&
        (!tempDate || d.date === tempDate)
    );
    setFiltered(filteredData);

    if (tempStation) {
      const stationData = filteredData.filter((d) => d.station === tempStation);
      let targetDate = tempDate;
      if (!targetDate) {
        const ds = [...new Set(stationData.map((d) => d.date))].sort();
        targetDate = ds[ds.length - 1] || "";
        setSelectedDate(targetDate);
      }
      const selectedData = stationData.filter((d) => d.date === targetDate);
      setSelected(selectedData);
      await fetchPrediction(tempStation, tempState, selectedPollutant);
    } else {
      setSelected(null);
      setPrediction(null);
    }
  }, [data, tempState, tempStation, tempDate, selectedPollutant, fetchPrediction]);

  const handleReset = useCallback(() => {
    setTempState("");
    setTempStation("");
    setTempDate("");
    setSelectedState("");
    setSelectedStation("");
    setSelectedDate("");
    setFiltered(data);
    setSelected(null);
    setPrediction(null);
    setPredError(null);
  }, [data]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <div
        style={{
          padding: "10px",
          background: "#222",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "10px",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
          {POLLUTANT_ORDER.map((p) => (
            <button
              key={p}
              onClick={() => {
                setSelectedPollutant(p);
                if (selectedStation) {
                  fetchPrediction(selectedStation, selectedState, p);
                }
              }}
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                border: "none",
                cursor: "pointer",
                background: selectedPollutant === p ? "#00ffcc" : "#333",
                color: selectedPollutant === p ? "black" : "white",
              }}
            >
              {p}
            </button>
          ))}

          <select
            value={tempState}
            onChange={(e) => {
              setTempState(e.target.value);
              setTempStation("");
              setTempDate("");
            }}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: tempState ? "#00ffcc" : "#333",
              color: tempState ? "black" : "white",
              appearance: "none",
              outline: "none",
            }}
          >
            <option value="">All States</option>
            {[...new Set(data.map((d) => d.state))].map((s, i) => (
              <option key={i}>{s}</option>
            ))}
          </select>

          <select
            value={tempStation}
            onChange={(e) => setTempStation(e.target.value)}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: tempStation ? "#00ffcc" : "#333",
              color: tempStation ? "black" : "white",
              appearance: "none",
              outline: "none",
            }}
          >
            <option value="">All Stations</option>
            {stations.map((s, i) => (
              <option key={i}>{s}</option>
            ))}
          </select>

          <select
            value={tempDate}
            onChange={(e) => setTempDate(e.target.value)}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: tempDate ? "#00ffcc" : "#333",
              color: tempDate ? "black" : "white",
              appearance: "none",
              outline: "none",
            }}
          >
            <option value="">All Dates</option>
            {dates.map((d, i) => (
              <option key={i}>{d}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button onClick={handleApply}>
            {predLoading ? "Loading..." : "Apply"}
          </button>

          <button
            onClick={handleReset}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: "#444",
              color: "white",
            }}
          >
            Reset
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ width: "40%", padding: "10px", height: "100%" }}>
          <MapView
            data={filtered}
            selectedPollutant={selectedPollutant}
            selected={selected}
            selectedDate={selectedDate}
            setSelected={setSelected}
            onStationClick={handleMapClick}
          />
        </div>

        <div style={{ flex: 1, display: "flex" }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                height: "100%",
                overflowY: "auto",
                gap: "10px",
                padding: "0 10px",
              }}
            >
              <div style={{ flex: "0 0 auto" }}>
                <h3>Snapshot Chart</h3>
                <p style={{ color: "#888", fontSize: "12px", margin: "4px 0 8px 0" }}>
                  Pollutant readings for the selected station on the selected date
                </p>
                <div className="chart-container">
                  {selected ? <ChartView data={selected} /> : <div style={{color: "#888", display: "flex", alignItems: "center", justifyContent: "center", height: "100%"}}>Select a station</div>}
                </div>
              </div>

              <div style={{ flex: "0 0 auto" }}>
                <h3>Trend ({selectedPollutant})</h3>
                <p style={{ color: "#888", fontSize: "12px", margin: "4px 0 8px 0" }}>
                  Historical {selectedPollutant} trend for the selected station over all dates
                </p>
                <div className="chart-container">
                  {selected ? (
                    <TrendChart
                      fullData={data}
                      selected={selected}
                      pollutant={selectedPollutant}
                    />
                  ) : <div style={{color: "#888", display: "flex", alignItems: "center", justifyContent: "center", height: "100%"}}>Select a station</div>}
                </div>
              </div>

              <div
                style={{
                  padding: "10px",
                  background: "#0f3d2e",
                  borderRadius: "10px",
                  flex: "0 0 auto",
                }}
              >
                <h3 style={{ color: "#00ffcc", textAlign: "center" }}>
                  Pollutant Summary
                </h3>

                {sortedSelected.length > 0 && (
                  <table
                    style={{
                      width: "100%",
                      borderCollapse: "collapse",
                      textAlign: "center",
                      color: "white",
                    }}
                  >
                    <thead>
                      <tr style={{ background: "#00ffcc", color: "black" }}>
                        <th>Pollutant</th>
                        <th>Min</th>
                        <th>Max</th>
                        <th>Avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedSelected.map((item, i) => (
                        <tr key={i} style={{ borderBottom: "1px solid #333" }}>
                          <td style={{ padding: "8px", color: "#00ffcc" }}>
                            {item.pollutant_id}
                          </td>
                          <td>{formatValue(item.min_value)}</td>
                          <td>{formatValue(item.max_value)}</td>
                          <td>{formatValue(item.avg_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          <div
            style={{
              width: "35%",
              padding: "15px",
              background: "#181818",
              overflowY: "auto",
              borderLeft: "2px solid #333",
            }}
          >
            <h2 style={{ textAlign: "center" }}>Selected Info</h2>

            {selected && selected.length > 0 ? (
              <>
                <p>
                  <b>Station:</b> {selected?.[0]?.station}
                </p>
                <p>
                  <b>City:</b> {selected[0].city}
                </p>
                <p>
                  <b>State:</b> {selected[0].state}
                </p>
                <p>
                  <b>Date:</b> {selected[0].date}
                </p>

                <hr />

                <div
                  style={{
                    background: "#0f3d2e",
                    padding: "12px",
                    borderRadius: "10px",
                    marginBottom: "15px",
                    boxShadow: "0 0 8px rgba(0,255,150,0.3)",
                  }}
                >
                  <h3 style={{ color: "#00ffcc" }}>Weather</h3>
                  <p>Temperature: {formatValue(selected[0].temperature)} °C</p>
                  <p>Humidity: {formatValue(selected[0].humidity)} %</p>
                  <p>Wind Speed: {formatValue(selected[0].wind_speed)} m/s</p>
                  <p>Wind Direction: {formatValue(selected[0].wind_direction)} °</p>
                </div>

                {predError && (
                  <div
                    style={{
                      background: "#4a1a1a",
                      padding: "12px",
                      borderRadius: "10px",
                      marginBottom: "15px",
                      color: "#ff6b6b",
                    }}
                  >
                    <p>
                      <b>Prediction Error:</b> {predError}
                    </p>
                    <p style={{ fontSize: "12px" }}>
                      Make sure the backend is running on {API_BASE}
                    </p>
                  </div>
                )}

                {predLoading && !predError && (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "#aaa",
                    }}
                  >
                    Fetching forecast...
                  </div>
                )}

                {prediction && !predError && !predLoading && (
                  <div
                    style={{
                      background: "#1a2f4b",
                      padding: "12px",
                      borderRadius: "10px",
                      marginBottom: "15px",
                      boxShadow: "0 0 10px rgba(0,150,255,0.3)",
                    }}
                  >
                    <h3
                      style={{
                        color: "#00ccff",
                        textAlign: "center",
                      }}
                    >
                      {prediction?.pollutant || "PM2.5"} Forecast
                    </h3>
                    <p
                      style={{
                        textAlign: "center",
                        color: "#aaa",
                        fontSize: "12px",
                      }}
                    >
                      Based on {prediction?.date || "latest data"}
                    </p>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-around",
                        marginTop: "10px",
                      }}
                    >
                      {["day1", "day2", "day3"].map((day, i) => {
                        const val = prediction?.predictions?.[day];
                        const health = prediction?.health_status?.[day];
                        return (
                          <div key={day} style={{ textAlign: "center" }}>
                            <p>+{i + 1} Day</p>
                            <h4
                              style={{
                                color: health
                                  ? getHealthColor(health.level)
                                  : "white",
                                margin: "4px 0",
                              }}
                            >
                              {val ?? "-"}
                            </h4>
                            {health && (
                              <p
                                style={{
                                  fontSize: "10px",
                                  color: getHealthColor(health.level),
                                  fontWeight: "bold",
                                }}
                              >
                                {health.level}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {prediction?.today_value !== undefined && (
                      <p
                        style={{
                          textAlign: "center",
                          marginTop: "10px",
                          color: "#aaa",
                        }}
                      >
                        Today: <b>{prediction.today_value}</b>{" "}
                        {prediction?.pollutant === "CO" ? "mg/m³" : "µg/m³"}
                      </p>
                    )}

                    {prediction?.delta_predictions && (
                      <div
                        style={{
                          marginTop: "10px",
                          paddingTop: "10px",
                          borderTop: "1px solid #333",
                        }}
                      >
                        <p
                          style={{
                            color: "#aaa",
                            fontSize: "12px",
                            textAlign: "center",
                          }}
                        >
                          Predicted Change
                        </p>
                        <div style={{ display: "flex", justifyContent: "space-around" }}>
                          {["day1", "day2", "day3"].map((day, i) => {
                            const delta = prediction?.delta_predictions?.[day];
                            if (delta === undefined) return null;
                            const color =
                              delta > 0 ? "#ff6b6b" : delta < 0 ? "#51cf66" : "#aaa";
                            const sign = delta > 0 ? "+" : "";
                            return (
                              <p key={day} style={{ color, fontSize: "12px" }}>
                                +{i + 1}d: {sign}
                                {delta}
                              </p>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {prediction?.health_status?.day1?.advice && (
                      <div
                        style={{
                          background: "rgba(0,0,0,0.2)",
                          borderRadius: "8px",
                          padding: "10px",
                          marginTop: "10px",
                        }}
                      >
                        <h4 style={{ fontSize: "12px", color: "#00ffcc", margin: "0 0 6px 0" }}>
                          Health Advice
                        </h4>
                        <p style={{ fontSize: "12px", color: "#aaa", lineHeight: "1.5", margin: 0 }}>
                          {prediction.health_status.day1.advice}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p>
                Select a station (click on map or use dropdowns) to view details and
                forecast
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
