# Pollution Prediction — AQI Forecast Dashboard

Production-grade end-to-end air quality forecasting with automated daily data collection, preprocessing, and model retraining.

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  data.gov.in    │────▶│  Data Pipeline  │────▶│  FastAPI Backend│
│  (Daily Fetch)  │     │  (Clean/Weather)│     │  (7 Pollutants) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │ Daily Cron           │  /predict
                              │ 6:07 AM IST          │  /refresh
                              ▼                      ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  21 GB Models   │     │  React Frontend │
                        │  (Auto-retrain) │     │  (Vercel)       │
                        └─────────────────┘     └─────────────────┘
```

## 📁 Project Structure

```
pollution-prediction/
├── backend/                    # FastAPI → Hugging Face Spaces
│   ├── app.py                  # API server with /refresh endpoint
│   ├── inference.py            # Model loading & prediction (hot-reloadable)
│   ├── requirements.txt
│   ├── Dockerfile              # HF Spaces (port 7860)
│   ├── data/
│   │   ├── aqi_history.csv         # Raw daily API data
│   │   ├── aqi_data_processed.csv  # Cleaned + deduplicated
│   │   └── merged_aqi_weather_data.csv  # Final training data
│   └── models/
│       ├── gb_delta_model_pm25_day1.pkl  # 21 models total
│       ├── gb_delta_model_pm10_day1.pkl
│       ├── ... (7 pollutants × 3 horizons)
│       ├── scaler_X_*.pkl
│       ├── feature_cols_*.json
│       ├── nodes_*.json
│       └── training_summary.json
│
├── frontend/                   # React + Vite → Vercel
│   ├── src/App.jsx             # Multi-pollutant dashboard + map click
│   ├── public/data/
│   ├── package.json
│   ├── Dockerfile / vercel.json
│   └── .env.example
│
├── data_pipeline/              # Automated daily pipeline
│   ├── config.py               # Shared paths & API keys
│   ├── fetch_aqi.py            # data.gov.in API fetcher
│   ├── preprocess.py           # Clean, dedup, synthetic fill, weather
│   ├── train_models.py         # Multi-pollutant model training
│   ├── pipeline.py             # Orchestrator with logging
│   └── README.md
│
├── train/                      # Reference scripts & results
│   ├── gb_aqi_delta_train.py
│   └── gb_delta_results.png
│
├── preprocessing/              # Original notebook (reference)
│   └── preprocessing_and_weather.ipynb
│
└── README.md
```

## 🚀 Deployment

### Backend → Hugging Face Spaces

```bash
cd backend
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/aqi-backend.git
git push -u origin main
```

Then create a Space at [huggingface.co/spaces](https://huggingface.co/spaces) with **Docker** SDK, connect to `aqi-backend` repo.

### Frontend → Vercel

```bash
cd frontend
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/aqi-frontend.git
git push -u origin main
```

Import to [Vercel](https://vercel.com), set `VITE_API_URL=https://YOUR_USERNAME-aqi-forecast-backend.hf.space`.

## 🔄 Daily Pipeline (Automated)

**Runs every day at 6:07 AM IST** via cron job.

| Step | What Happens | File |
|---|---|---|
| 1. Fetch | Download new AQI data from data.gov.in API | `fetch_aqi.py` |
| 2. Clean | Deduplicate, remove bad timestamps, fill missing dates with synthetic data | `preprocess.py` |
| 3. Weather | Fetch historical weather from Open-Meteo for each station | `preprocess.py` |
| 4. Merge | Combine AQI + weather into training dataset | `preprocess.py` |
| 5. Train | Retrain all 21 models (7 pollutants × 3-day horizons) | `train_models.py` |
| 6. Reload | Backend auto-reloads models via `/refresh` endpoint | `app.py` |

### Manual Pipeline Run

```bash
cd data_pipeline
python pipeline.py           # Full pipeline
python pipeline.py --fetch-only   # Only fetch
python pipeline.py --train-only   # Only train
```

### View Pipeline Logs

```bash
type data_pipeline\pipeline.log   # Windows
cat data_pipeline/pipeline.log      # Linux/Mac
```

## 🧠 Model

- **Algorithm**: Gradient Boosting (Delta prediction)
- **Pollutants**: PM2.5, PM10, NO2, SO2, OZONE, NH3, CO
- **Approach**: Predicts the *change* from today's value, then reconstructs absolute forecast
- **Features**: Lag values, rolling statistics, weather (temp/humidity/wind), auxiliary pollutants, temporal features
- **Data**: 259 Indian cities, 7 pollutants, 44+ days (grows daily)

## 🔧 Backend API

| Endpoint | Description |
|---|---|
| `GET /health` | Status, loaded models, city counts |
| `GET /pollutants` | List available pollutants |
| `GET /cities?pollutant=PM2.5` | Cities with data for a pollutant |
| `POST /predict` | `{city_name, pollutant}` → 3-day forecast + health status |
| `GET /predict/{city}` | GET version for testing |
| `POST /refresh` | Hot-reload models after retraining |

## 🎨 Frontend Features

- **Interactive map** — click any marker to auto-select + fetch forecast
- **7 pollutant buttons** — click to switch forecast type
- **3-day forecast** with India CPCB health status colors
- **Predicted change** (delta) from today's value
- **Weather card** — temperature, humidity, wind speed, direction
- **Trend charts** — historical time series
- **Responsive** loading states and error handling

## 📝 Environment Variables

### Backend (HF Spaces)
None needed — Docker handles everything.

### Frontend (Vercel)
| Variable | Local | Production |
|---|---|---|
| `VITE_API_URL` | `http://localhost:7860` | `https://your-backend.hf.space` |

## 📊 Performance

| Pollutant | +1 Day MAE | +2 Day MAE | +3 Day MAE |
|---|---|---|---|
| PM2.5 | ~17 µg/m³ | ~21 µg/m³ | ~22 µg/m³ |
| PM10 | ~25 µg/m³ | ~30 µg/m³ | ~35 µg/m³ |
| (Others vary by data availability) | | | |

## 🛠️ Local Development

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python app.py

# Terminal 2: Frontend
cd frontend
npm install
npm run dev

# Terminal 3: Run pipeline once
cd data_pipeline
python pipeline.py
```

## 📜 Data Sources

- **AQI**: [data.gov.in](https://data.gov.in) — CPCB India real-time air quality
- **Weather**: [Open-Meteo](https://open-meteo.com) — Free historical weather API

## 📧 Contact

Built for portfolio and resume demonstration. Auto-retraining pipeline makes it production-grade.
