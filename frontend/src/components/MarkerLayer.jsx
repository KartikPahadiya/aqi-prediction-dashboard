import { CircleMarker } from "react-leaflet";
import { memo } from "react";

const MarkerLayer = memo(({ data, selectedDate, getColor, onStationClick }) => {
  // Only render markers for the latest date to avoid 30K+ markers
  const displayData = selectedDate
    ? data.filter(d => d.date === selectedDate)
    : data;

  // Deduplicate by station — keep only one marker per station
  const seen = new Set();
  const uniqueData = [];
  for (const item of displayData) {
    if (!seen.has(item.station)) {
      seen.add(item.station);
      uniqueData.push(item);
    }
  }

  return (
    <>
      {uniqueData.map((item) => (
        <CircleMarker
          key={item.station}          // stable key = no full re-render
          center={[item.latitude, item.longitude]}
          radius={8}
          pathOptions={{
            color: "black",
            fillColor: getColor(item.avg_value),
            fillOpacity: 0.9,
          }}
          eventHandlers={{
            click: () => {
              if (onStationClick) {
                onStationClick({
                  station: item.station,
                  state: item.state,
                  city: item.city
                });
              }
            },
          }}
        />
      ))}
    </>
  );
});

export default MarkerLayer;
