# Data Pipeline

Production-grade automated pipeline for AQI data collection, preprocessing, and model retraining.

## Architecture

```
Daily Cron (6:00 AM)
    ↓
fetch_aqi.py          → Fetch from data.gov.in API
    ↓
preprocess.py         → Clean, dedup, fill missing dates, fetch weather
    ↓
train_models.py       → Retrain all 21 models (7 pollutants × 3 horizons)
    ↓
backend /refresh      → Hot-reload models without restarting server
```

## Files

| File | Purpose |
|---|---|
| `config.py` | Shared paths, API keys, pollutant list |
| `fetch_aqi.py` | Fetch daily AQI data from data.gov.in |
| `preprocess.py` | Clean, deduplicate, synthetic missing dates, Open-Meteo weather |
| `train_models.py` | Train all pollutant models on latest data |
| `pipeline.py` | Orchestrator — runs all steps with logging |

## Run Manually

```bash
# Full pipeline
python pipeline.py

# Only fetch new data
python pipeline.py --fetch-only

# Only retrain (assumes data exists)
python pipeline.py --train-only
```

## Automated Daily Run (Cron)

The pipeline is scheduled to run daily at 6:00 AM. It will:
1. Check if today's data already exists (skip if yes)
2. Fetch new AQI records from API
3. Preprocess (clean, dedup, fill missing dates, add weather)
4. Retrain all models
5. Log results to `pipeline.log`

After the pipeline completes, the backend auto-reloads models on its next `/refresh` call, or you can manually POST to `/refresh`.

## Data Flow

| Stage | Input | Output | Location |
|---|---|---|---|
| Raw fetch | data.gov.in API | `aqi_history.csv` | `backend/data/` |
| Preprocess | `aqi_history.csv` | `aqi_data_processed.csv` + `merged_aqi_weather_data.csv` | `backend/data/` |
| Train | `merged_aqi_weather_data.csv` | 21 model `.pkl` files + scalers + metadata | `backend/models/` |

## Weather API

Uses [Open-Meteo](https://open-meteo.com) (free, no API key required) to fetch historical weather for each station's latitude/longitude.

## Missing Data Handling

When a date is missing for a station/pollutant combination:
1. Try averaging the previous and next day's values
2. If still missing (edge dates), forward/backward fill
3. This ensures every station has a complete daily time series for model training
