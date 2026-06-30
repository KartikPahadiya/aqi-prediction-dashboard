import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import time
import requests
import warnings
warnings.filterwarnings('ignore')

from config import (
    RAW_DATA_PATH, PROCESSED_DATA_PATH, MERGED_DATA_PATH,
    WEATHER_API, ALL_POLLUTANTS
)


def log(msg):
    print(f"  {msg}")


def preprocess_aqi(df_raw):
    """Clean and deduplicate AQI data, handle missing dates."""
    log(f"Raw data: {len(df_raw):,} rows")
    
    # Drop collection_time column if exists (internal tracking)
    if 'collection_time' in df_raw.columns:
        df_raw = df_raw.drop(columns=['collection_time'])
    
    # Parse last_update - handle both date-only and datetime formats
    df_raw['last_update'] = pd.to_datetime(df_raw['last_update'], format='mixed', errors='coerce', dayfirst=True)
    df_raw = df_raw.dropna(subset=['last_update'])
    
    # Create date-only column
    df_raw['date'] = df_raw['last_update'].dt.strftime('%d-%m-%Y')
    
    # Remove duplicate timestamps (keep first occurrence per station/pollutant/time)
    df_raw = df_raw.sort_values(['station', 'pollutant_id', 'last_update'])
    df_raw = df_raw.drop_duplicates(subset=['station', 'pollutant_id', 'last_update'], keep='first')
    
    # Deduplicate on date level (keep one row per station/pollutant/date with latest timestamp)
    df_raw = df_raw.sort_values(['station', 'pollutant_id', 'date', 'last_update'])
    df_raw = df_raw.drop_duplicates(subset=['station', 'pollutant_id', 'date'], keep='last')
    
    # Rename date to last_update for consistency
    df = df_raw.copy()
    df['last_update'] = df['date']
    df = df.drop(columns=['date'])
    
    # Convert numeric columns
    for col in ['min_value', 'max_value', 'avg_value', 'latitude', 'longitude']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    log(f"After dedup: {len(df):,} rows")
    
    # Generate synthetic data for missing dates
    df = fill_missing_dates(df)
    
    return df


def fill_missing_dates(df):
    """Fill missing dates by averaging adjacent days for each station/pollutant."""
    df['last_update'] = pd.to_datetime(df['last_update'], format='%d-%m-%Y', dayfirst=True)
    
    # Get all unique dates and stations
    all_dates = pd.date_range(df['last_update'].min(), df['last_update'].max(), freq='D')
    all_stations = df[['station', 'latitude', 'longitude', 'city', 'state', 'country']].drop_duplicates()
    all_pollutants = df['pollutant_id'].unique()
    
    # Create full grid
    full_grid = []
    for date in all_dates:
        date_str = date.strftime('%d-%m-%Y')
        for _, station in all_stations.iterrows():
            for poll in all_pollutants:
                full_grid.append({
                    'last_update': date_str,
                    'station': station['station'],
                    'city': station['city'],
                    'state': station['state'],
                    'country': station['country'],
                    'latitude': station['latitude'],
                    'longitude': station['longitude'],
                    'pollutant_id': poll
                })
    
    full_df = pd.DataFrame(full_grid)
    full_df['last_update'] = pd.to_datetime(full_df['last_update'], format='%d-%m-%Y', dayfirst=True)
    
    # Merge with actual data
    merged = full_df.merge(
        df[['last_update', 'station', 'pollutant_id', 'min_value', 'max_value', 'avg_value']],
        on=['last_update', 'station', 'pollutant_id'],
        how='left'
    )
    
    # Identify missing values
    missing_mask = merged['avg_value'].isna()
    missing_count = missing_mask.sum()
    log(f"Missing values to fill: {missing_count:,}")
    
    if missing_count > 0:
        # Fill by averaging previous and next day for same station/pollutant
        merged = merged.sort_values(['station', 'pollutant_id', 'last_update'])
        
        for col in ['min_value', 'max_value', 'avg_value']:
            merged[col] = merged.groupby(['station', 'pollutant_id'])[col].transform(
                lambda x: x.fillna((x.shift(1) + x.shift(-1)) / 2)
            )
        
        # If still missing (e.g., at start/end of series), forward/backward fill
        for col in ['min_value', 'max_value', 'avg_value']:
            merged[col] = merged.groupby(['station', 'pollutant_id'])[col].transform(
                lambda x: x.ffill().bfill()
            )
    
    # Convert last_update back to string format
    merged['last_update'] = merged['last_update'].dt.strftime('%d-%m-%Y')
    
    filled_count = merged['avg_value'].isna().sum()
    log(f"Remaining missing after fill: {filled_count:,}")
    
    return merged


def fetch_weather(stations_df, start_date, end_date):
    """Fetch historical weather from Open-Meteo for each station."""
    log(f"Fetching weather for {len(stations_df)} stations...")
    
    weather_data = []
    
    for idx, row in stations_df.iterrows():
        lat = row['latitude']
        lon = row['longitude']
        station = row['station']
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_date,
            'end_date': end_date,
            'daily': 'temperature_2m_mean,relative_humidity_2m_mean,wind_speed_10m_max,wind_direction_10m_dominant',
            'timezone': 'auto'
        }
        
        try:
            r = requests.get(WEATHER_API, params=params, timeout=30)
            if r.status_code != 200:
                log(f"  Weather API error for {station}: {r.status_code}")
                continue
            
            data = r.json()
            daily = data.get('daily', {})
            
            if not daily or 'time' not in daily:
                log(f"  No weather data for {station}")
                continue
            
            dates = daily['time']
            temps = daily.get('temperature_2m_mean', [])
            humidity = daily.get('relative_humidity_2m_mean', [])
            wind_speed = daily.get('wind_speed_10m_max', [])
            wind_dir = daily.get('wind_direction_10m_dominant', [])
            
            for i, d in enumerate(dates):
                weather_data.append({
                    'station': station,
                    'date': d,
                    'temperature': temps[i] if i < len(temps) else None,
                    'humidity': humidity[i] if i < len(humidity) else None,
                    'wind_speed': wind_speed[i] if i < len(wind_speed) else None,
                    'wind_direction': wind_dir[i] if i < len(wind_dir) else None
                })
            
            time.sleep(0.5)  # Rate limit
            
        except Exception as e:
            log(f"  Error fetching weather for {station}: {e}")
            continue
    
    weather_df = pd.DataFrame(weather_data)
    log(f"Fetched weather: {len(weather_df):,} rows")
    return weather_df


def merge_with_weather(aqi_df, weather_df):
    """Merge AQI data with weather data."""
    aqi_df['date'] = pd.to_datetime(aqi_df['last_update'], format='%d-%m-%Y', dayfirst=True).dt.strftime('%Y-%m-%d')
    weather_df['date'] = pd.to_datetime(weather_df['date']).dt.strftime('%Y-%m-%d')
    
    merged = aqi_df.merge(weather_df, on=['station', 'date'], how='left')
    
    # Interpolate missing weather values
    numeric_cols = ['temperature', 'humidity', 'wind_speed', 'wind_direction']
    for col in numeric_cols:
        if col in merged.columns:
            merged[col] = merged.groupby('station')[col].transform(
                lambda x: x.interpolate().ffill().bfill()
            )
    
    # Drop temp date column, keep last_update as primary
    merged = merged.drop(columns=['date'])
    
    return merged


def run():
    print(f"\n{'='*60}")
    print(f"STEP 2: Preprocessing AQI Data")
    print(f"{'='*60}")
    
    if not RAW_DATA_PATH.exists():
        log(f"ERROR: Raw data not found at {RAW_DATA_PATH}")
        return False
    
    df_raw = pd.read_csv(RAW_DATA_PATH)
    log(f"Loaded raw data: {len(df_raw):,} rows")
    
    # Preprocess AQI
    df_processed = preprocess_aqi(df_raw)
    df_processed.to_csv(PROCESSED_DATA_PATH, index=False)
    log(f"Saved processed: {PROCESSED_DATA_PATH}")
    
    # Get stations and date range for weather
    stations_df = df_processed[['station', 'latitude', 'longitude']].drop_duplicates()
    df_processed['last_update_dt'] = pd.to_datetime(df_processed['last_update'], format='%d-%m-%Y', dayfirst=True)
    start_date = df_processed['last_update_dt'].min().strftime('%Y-%m-%d')
    end_date = df_processed['last_update_dt'].max().strftime('%Y-%m-%d')
    
    # Fetch weather
    weather_df = fetch_weather(stations_df, start_date, end_date)
    
    # Merge
    merged_df = merge_with_weather(df_processed, weather_df)
    merged_df = merged_df.drop(columns=['last_update_dt'], errors='ignore')
    
    # Save
    merged_df.to_csv(MERGED_DATA_PATH, index=False)
    log(f"Saved merged data: {MERGED_DATA_PATH}")
    log(f"Final shape: {merged_df.shape}")
    
    # Print summary
    log(f"Date range: {merged_df['last_update'].min()} to {merged_df['last_update'].max()}")
    log(f"Stations: {merged_df['station'].nunique()}")
    log(f"Cities: {merged_df['city'].nunique()}")
    log(f"Pollutants: {merged_df['pollutant_id'].nunique()}")
    
    return True


if __name__ == "__main__":
    run()
