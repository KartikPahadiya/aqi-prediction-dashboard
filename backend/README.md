# AQI Forecast Backend

FastAPI backend for multi-pollutant air quality forecasting using Gradient Boosting delta models. Predicts PM2.5, PM10, NO2, SO2, OZONE, NH3, and CO for 259 Indian cities.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

API will be available at `http://localhost:7860`.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | API info & available pollutants |
| `/health` | GET | Health check |
| `/pollutants` | GET | List all available pollutants |
| `/cities` | GET | List cities for a pollutant (`?pollutant=PM2.5`) |
| `/predict` | POST | Predict 3-day forecast (`{city_name, pollutant}`) |
| `/predict/{city}` | GET | GET version for testing (`?pollutant=PM2.5`) |
| `/compare/{city}` | GET | Compare model vs naive baseline |

## Deploy to Hugging Face Spaces

### Step 1: Create a GitHub Repository for Backend

```bash
cd backend
git init
git add .
git commit -m "Initial backend commit"
# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/aqi-backend.git
git push -u origin main
```

### Step 2: Create Hugging Face Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click **Create New Space**
3. **Space name**: `aqi-forecast-backend` (or your choice)
4. **SDK**: Select **Docker**
5. **License**: MIT (or your choice)
6. Click **Create Space**

### Step 3: Connect GitHub to HF Space

In your Space settings:
- Go to **Settings → Repository**
- Select **GitHub** as repository provider
- Connect your GitHub account
- Select the `aqi-backend` repository
- HF will auto-build on every push

**OR manually upload:**
```bash
# Install huggingface-cli: pip install huggingface-hub
huggingface-cli login

# Upload all files in backend/ folder
huggingface-cli upload YOUR_USERNAME/aqi-forecast-backend . --repo-type=space
```

### Step 4: Wait for Build

Hugging Face Spaces will:
1. Build the Docker image from your `Dockerfile`
2. Run the container on port `7860`
3. Expose your API at `https://YOUR_USERNAME-aqi-forecast-backend.hf.space`

### Step 5: Test the Deployed API

```bash
curl https://YOUR_USERNAME-aqi-forecast-backend.hf.space/health
```

Should return: `{"status":"ok","models_loaded":7,...}`

## Model Details

- **Type**: Gradient Boosting (Delta prediction)
- **Pollutants**: PM2.5, PM10, NO2, SO2, OZONE, NH3, CO
- **Input**: 35+ features per pollutant (lags, weather, auxiliary pollutants, temporal)
- **Output**: 3-day absolute forecast with pollutant-specific AQI health status
- **Performance**: ~17 µg/m³ MAE at +1 day for PM2.5

## Files

- `app.py` — FastAPI server
- `inference.py` — Model loading, preprocessing, prediction logic
- `models/` — 21 trained sklearn models (7 pollutants × 3 horizons) + scalers
- `data/` — Merged AQI + weather dataset
- `Dockerfile` — HF Spaces deployment (Python 3.11, port 7860)
- `requirements.txt` — Python dependencies (no PyTorch!)
