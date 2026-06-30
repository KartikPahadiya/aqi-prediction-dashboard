import Papa from "papaparse";

export const loadCSV = async () => {
  const res = await fetch("/data/aqi_data.csv");
  const text = await res.text();

  return new Promise((resolve) => {
    Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      complete: (result) => {
        const data = result.data.map(d => ({
          ...d,
          latitude: parseFloat(d.latitude),
          longitude: parseFloat(d.longitude),
          avg_value: parseFloat(d.avg_value),
        }));
        resolve(data);
      }
    });
  });
};