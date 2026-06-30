# AQI Forecast Dashboard

End-to-end air quality prediction dashboard with a Gradient Boosting backend and React frontend.

## Quick Start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Backend runs on `http://localhost:8000`

### 2. Frontend (new terminal)

```bash
# From the aqi-dashboard folder
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/cities` | GET | List all available cities |
| `/predict` | POST | Predict PM2.5 for 3 days (body: `{city_name: "Delhi"}`) |
| `/predict/{city}` | GET | GET version for browser testing |
| `/compare/{city}` | GET | Compare model vs naive baseline |

## Model

- **Type**: Gradient Boosting (Delta prediction)
- **Input**: 35 features (PM2.5 lags, weather, aux pollutants, temporal features)
- **Output**: PM2.5 change (delta) from today's value, reconstructed to absolute forecast
- **Performance**: ~17 µg/m³ MAE at +1 day (beats naive baseline)

## Project Structure

```
aqi-dashboard/
├── backend/
│   ├── app.py              # FastAPI server
│   ├── inference.py        # Model loading & prediction logic
│   ├── requirements.txt    # Python dependencies
│   └── models/             # Saved model files (or references train/)
├── src/
│   ├── App.jsx             # Main dashboard
│   └── utils/parseCSV.js   # CSV data loader
├── .env                    # Frontend API URL config
└── package.json
```

## Environment Variables

Backend (optional):
- `PORT` — server port (default: 8000)
- `ALLOWED_ORIGINS` — CORS origins (default: `http://localhost:5173`)

Frontend:
- `VITE_API_URL` — backend URL (default: `http://localhost:8000`)
