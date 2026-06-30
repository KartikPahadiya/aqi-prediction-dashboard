import { MapContainer, TileLayer } from "react-leaflet";
import MarkerLayer from "./MarkerLayer";
import "leaflet/dist/leaflet.css";
import { useMap } from "react-leaflet";
import { useEffect } from "react";



function AutoZoom({ selected }) {
  const map = useMap();

  useEffect(() => {
    if (selected && selected.length > 0) {
      const { latitude, longitude } = selected[0];
      map.setView([latitude, longitude], 10);
    }
  }, [selected]);

  return null;
}
const getColor = (val) => {
  if (val == null) return "gray";

  if (val <= 50) return "green";      // safe
  if (val <= 100) return "yellow";    // moderate
  return "red";                       // dangerous
};
const MapView = ({ data, fullData, selectedPollutant, selected, selectedDate, setSelected }) => {

  console.log("MAP DATA:", data.length);
  console.log("SELECTED:", selected);
  const filteredPollutantData = data?.filter(
      d => d.pollutant_id === selectedPollutant
  );
  return (
    <div style={{ height: "100%", width: "100%",overflow: "hidden" }}>
      <MapContainer
        center={[22.5, 78.9]}
        zoom={5}
        // style={{ height: "100%", width: "100%" }}
        className="map-container"
      > 
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <MarkerLayer 
          data={filteredPollutantData}
          fullData={fullData}
          selectedDate={selectedDate} 
          getColor={getColor}
          setSelected={setSelected}
        />
        <AutoZoom selected={selected} />
      </MapContainer>
    </div>
  );
};

export default MapView;