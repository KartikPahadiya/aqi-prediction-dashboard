import { useState } from "react";

const Filters = ({ data, setFiltered, setSelected, selectedDate, setSelectedDate }) => {
  const [state, setState] = useState("");
  const [station, setStation] = useState("");

  const states = [...new Set(data.map(d => d.state))];

  const stations = [
    ...new Set(
      data
        .filter(d => !state || d.state === state)
        .map(d => d.station)
    )
  ];

  const dates = [...new Set(data.map(d => d.date))];

  const applyFilter = (s, st, d) => {
    let filtered = data;

    if (s) filtered = filtered.filter(x => x.state === s);
    if (st) filtered = filtered.filter(x => x.station === st);
    if (d) filtered = filtered.filter(x => x.date === d);

    setFiltered(filtered);
    setSelected(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>

      {/* 🔍 SEARCH */}
      <input
        placeholder="Search station..."
        onChange={(e) => {
          const val = e.target.value.toLowerCase();
          setFiltered(
            data.filter(d =>
              d.station.toLowerCase().includes(val)
            )
          );
        }}
      />

      {/* STATE */}
      <select onChange={(e) => {
        const val = e.target.value;
        setState(val);
        setStation("");
        applyFilter(val, "", selectedDate);
      }}>
        <option value="">All States</option>
        {states.map((s, i) => <option key={i}>{s}</option>)}
      </select>

      {/* STATION */}
      <select onChange={(e) => {
        const val = e.target.value;
        setStation(val);
        applyFilter(state, val, selectedDate);
      }}>
        <option value="">All Stations</option>
        {stations.map((s, i) => <option key={i}>{s}</option>)}
      </select>

      {/* DATE */}
      <select onChange={(e) => {
        const val = e.target.value;
        setSelectedDate(val);
        applyFilter(state, station, val);
      }}>
        <option value="">All Dates</option>
        {dates.map((d, i) => <option key={i}>{d}</option>)}
      </select>

    </div>
  );
};

export default Filters;