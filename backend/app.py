from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware

from inference import predict_station, predict_city, get_all_cities, get_available_pollutants, load_all, available_pollutants

app = FastAPI(
    title="AQI Forecast API",
    description="Multi-pollutant air quality forecasting API with auto-reload",
    version="3.1.0"
)

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Force CORS headers on every response — more reliable than built-in middleware."""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data file path for serving
DATA_PATH = Path(__file__).parent / "data" / "merged_aqi_weather_data.csv"

class PredictionRequest(BaseModel):
    station_name: str
    state: str = ""
    pollutant: str = "PM2.5"

@app.get("/")
async def root():
    return {
        "message": "AQI Forecast API v3.1",
        "docs": "/docs",
        "health": "/health",
        "refresh": "/refresh",
        "pollutants": available_pollutants
    }

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": len(available_pollutants),
        "pollutants": available_pollutants,
        "model_type": "Gradient Boosting (Delta)",
        "cities": {p: len(get_all_cities(p).get("cities", [])) for p in available_pollutants}
    }

@app.get("/pollutants")
async def list_pollutants():
    return get_available_pollutants()

@app.get("/cities")
async def list_cities(pollutant: str = "PM2.5"):
    return get_all_cities(pollutant)

@app.post("/predict")
async def predict(request: PredictionRequest):
    if not request.station_name or not request.station_name.strip():
        raise HTTPException(status_code=400, detail="station_name is required")
    
    result = predict_station(
        request.station_name.strip(),
        request.state.strip() if request.state else "",
        request.pollutant.upper()
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

@app.get("/predict/{station_name}")
async def predict_get(station_name: str, state: str = "", pollutant: str = "PM2.5"):
    result = predict_station(station_name.strip(), state.strip(), pollutant.upper())
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

@app.get("/compare/{station_name}")
async def compare_prediction(station_name: str, state: str = "", pollutant: str = "PM2.5"):
    result = predict_station(station_name.strip(), state.strip(), pollutant.upper())
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    today = result["today_value"]
    
    return {
        "station": station_name,
        "state": state,
        "city": result.get("city", ""),
        "pollutant": pollutant,
        "today_value": today,
        "model_predictions": result["predictions"],
        "naive_baseline": {
            "day1": today,
            "day2": today,
            "day3": today
        },
        "model_deltas": result["delta_predictions"],
        "health_status": result.get("health_status", {})
    }

@app.post("/refresh")
async def refresh_models():
    """Reload models and data from disk. Call after pipeline retraining."""
    try:
        summary = load_all()
        if "error" in summary:
            raise HTTPException(status_code=500, detail=summary["error"])
        return {"status": "reloaded", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")

@app.get("/data/csv")
async def get_csv():
    """Serve the full merged AQI + weather dataset as CSV."""
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Data file not found. Run the pipeline first.")
    return FileResponse(
        path=DATA_PATH,
        media_type="text/csv",
        filename="aqi_data.csv"
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
