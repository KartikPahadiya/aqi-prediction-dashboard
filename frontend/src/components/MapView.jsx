import { MapContainer, TileLayer } from "react-leaflet";
import MarkerLayer from "./MarkerLayer";
import "leaflet/dist/leaflet.css";
import { useMap } from "react-leaflet";
import { useEffect, useMemo } from "react";

function AutoZoom({ selected }) {
  const map = useMap();

  useEffect(() => {
    if (selected && selected.length > 0) {
      const { latitude, longitude } = selected[0];
      map.setView([latitude, longitude], 10);
    }
  }, [selected, map]);

  return null;
}

const getColor = (val) => {
  if (val == null) return "gray";
  if (val <= 50) return "green";      // safe
  if (val <= 100) return "yellow";    // moderate
  return "red";                       // dangerous
};

const MapView = ({ data, selectedPollutant, selected, selectedDate, setSelected, onStationClick }) => {
  const filteredPollutantData = useMemo(() => {
    return data?.filter((d) => d.pollutant_id === selectedPollutant) || [];
  }, [data, selectedPollutant]);

  return (
    <div style={{ height: "100%", width: "100%", overflow: "hidden" }}>
      <MapContainer
        center={[22.5, 78.9]}
        zoom={5}
        className="map-container"
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <MarkerLayer
          data={filteredPollutantData}
          selectedDate={selectedDate}
          getColor={getColor}
          onStationClick={onStationClick}
        />
        <AutoZoom selected={selected} />
      </MapContainer>
    </div>
  );
};

export default MapView;
