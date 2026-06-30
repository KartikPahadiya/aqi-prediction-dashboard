import Papa from "papaparse";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:7860";

/**
 * Parse DD-MM-YYYY date string to ISO YYYY-MM-DD format.
 * The merged CSV uses DD-MM-YYYY (e.g., "01-04-2026" = April 1, 2026).
 * JavaScript's Date() constructor incorrectly interprets this as MM-DD-YYYY.
 */
function parseDDMMYYYY(dateStr) {
  if (!dateStr) return null;
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    const day = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1; // 0-indexed
    const year = parseInt(parts[2], 10);
    return new Date(year, month, day).toLocaleDateString("en-CA");
  }
  // Fallback for ISO format
  return new Date(dateStr).toLocaleDateString("en-CA");
}

export const loadCSV = async () => {
  // Fetch from backend API so deployed frontend always gets latest data
  const res = await fetch(`${API_BASE}/data/csv`);
  if (!res.ok) {
    throw new Error(`Failed to fetch data: ${res.status}`);
  }
  const text = await res.text();

  return new Promise((resolve, reject) => {
    Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      complete: (result) => {
        const data = result.data
          .filter(row => row.station && row.station.trim() !== "")
          .map(row => ({
            station: row.station?.trim(),
            city: row.city?.trim(),
            state: row.state?.trim(),
            country: row.country?.trim(),
            latitude: parseFloat(row.latitude),
            longitude: parseFloat(row.longitude),
            last_update: row.last_update,
            date: parseDDMMYYYY(row.last_update),
            pollutant_id: row.pollutant_id,
            min_value: row.min_value !== "" && row.min_value !== undefined ? parseFloat(row.min_value) : null,
            max_value: row.max_value !== "" && row.max_value !== undefined ? parseFloat(row.max_value) : null,
            avg_value: row.avg_value !== "" && row.avg_value !== undefined ? parseFloat(row.avg_value) : null,
            temperature: row.temperature !== "" && row.temperature !== undefined ? parseFloat(row.temperature) : null,
            humidity: row.humidity !== "" && row.humidity !== undefined ? parseFloat(row.humidity) : null,
            wind_speed: row.wind_speed !== "" && row.wind_speed !== undefined ? parseFloat(row.wind_speed) : null,
            wind_direction: row.wind_direction !== "" && row.wind_direction !== undefined ? parseFloat(row.wind_direction) : null,
          }));
        
        console.log(`Loaded ${data.length} rows from backend API`);
        console.log("Date range:", data[0]?.date, "to", data[data.length - 1]?.date);
        resolve(data);
      },
      error: (err) => reject(err)
    });
  });
};
