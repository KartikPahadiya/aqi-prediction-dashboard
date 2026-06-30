import os
import sys
from pathlib import Path


# Add parent to path so we can import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Project root
ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Data paths
RAW_DATA_PATH = ROOT / "backend" / "data" / "aqi_history.csv"
PROCESSED_DATA_PATH = ROOT / "backend" / "data" / "aqi_data_processed.csv"
MERGED_DATA_PATH = ROOT / "backend" / "data" / "merged_aqi_weather_data.csv"

# Models path
MODELS_DIR = ROOT / "backend" / "models"

# API config
API_KEY = "579b464db66ec23bdd000001defb204ced3c478d5e7628fbd2525939"
API_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"

# Weather config (Open-Meteo)
WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"

# Pollutants we track
ALL_POLLUTANTS = ['PM2.5', 'PM10', 'NO2', 'SO2', 'OZONE', 'NH3', 'CO']

# Training config
P = 7   # lookback window
Q = 3   # forecast horizon
MIN_CITY_DAYS = 35
AGG_MODE = 'city'

# Log file
LOG_PATH = ROOT / "data_pipeline" / "pipeline.log"
