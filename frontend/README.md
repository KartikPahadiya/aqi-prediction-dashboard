# AQI Forecast Dashboard

Interactive air quality dashboard built with React 19 + Vite + Leaflet + Recharts. Supports 7 pollutant forecasts with map click-to-select.

## Run Locally

```bash
npm install
npm run dev
```

App will be available at `http://localhost:5173`.

**Note:** Make sure the backend is running at `http://localhost:7860` (or update `.env`).

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend API URL. Local: `http://localhost:7860`. Production: `https://your-backend.hf.space` |

## Deploy to Vercel

### Step 1: Create a GitHub Repository for Frontend

```bash
cd frontend
git init
git add .
git commit -m "Initial frontend commit"
# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/aqi-frontend.git
git push -u origin main
```

### Step 2: Connect to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click **Add New... → Project**
3. Import your `aqi-frontend` GitHub repository
4. Vercel will auto-detect Vite framework

### Step 3: Set Environment Variable

Before deploying, add this in Vercel dashboard:

- Go to **Settings → Environment Variables**
- Add: `VITE_API_URL` = `https://YOUR_USERNAME-aqi-forecast-backend.hf.space`
- **Target**: Production (and Preview if you want)

### Step 4: Deploy

Click **Deploy**. Vercel will:
1. Build the React app (`npm run build`)
2. Serve static files from `dist/`
3. Give you a URL like `https://aqi-frontend.vercel.app`

### Step 5: Update CORS (if needed)

If your frontend gets CORS errors, update the backend `app.py`:

```python
allow_origins=["https://aqi-frontend.vercel.app", "https://*.vercel.app"]
```

Or keep `["*"]` for demo/portfolio use.

## Features

- **Interactive Leaflet map** of 259 Indian cities with AQI-colored markers
- **Click-to-select** — click any map marker to auto-select station + fetch forecast
- **7 pollutant forecasts** — PM2.5, PM10, NO2, SO2, OZONE, NH3, CO
- **Pollutant-specific AQI** — health status colors match India CPCB breakpoints
- **3-day forecast** with predicted change (delta) from today's value
- **Time-series charts** — snapshot and trend views
- **Weather data** — temperature, humidity, wind speed, wind direction
- **Responsive design** with loading states and error handling

## Tech Stack

- React 19 + Vite
- Leaflet + React-Leaflet (maps)
- Recharts (charts)
- PapaParse (CSV parsing)
