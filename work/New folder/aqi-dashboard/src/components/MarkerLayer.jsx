import { CircleMarker } from "react-leaflet";

const MarkerLayer = ({ data, fullData, selectedDate, getColor, setSelected }) => {
  return (
    <>
      {data.map((item, i) => (
        <CircleMarker
          key={i}
          center={[item.latitude, item.longitude]}
          radius={8}
          pathOptions={{
            color: "black",
            fillColor: getColor(item.avg_value),
            fillOpacity: 0.9,
          }}
          eventHandlers={{
            click: () => {
              const stationData = fullData.filter(
                d => 
                d.station === item.station &&
                (selectedDate === "All" || d.date === selectedDate)
            );
              if (stationData && stationData.length > 0) {
                setSelected(stationData);
              } else {
                setSelected(null);
              }
            },
          }}
        />
      ))}
    </>
  );
};

export default MarkerLayer;