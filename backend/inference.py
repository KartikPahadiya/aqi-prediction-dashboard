import pickle
import json
import warnings
import gc
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
DATA_PATH = BASE_DIR / "data" / "merged_aqi_weather_data.csv"

ALL_POLLUTANTS = ['PM2.5', 'PM10', 'NO2', 'SO2', 'OZONE', 'NH3', 'CO']
WEATHER = ['temperature', 'humidity', 'wind_speed', 'wind_direction']
AUX_POLLS = ALL_POLLUTANTS
P = 7

AQI_BREAKPOINTS = {
    'PM2.5':  [0, 30, 60, 90, 120, 250, 9999],
    'PM10':   [0, 50, 100, 250, 350, 430, 9999],
    'NO2':    [0, 40, 80, 180, 280, 400, 9999],
    'SO2':    [0, 40, 80, 380, 800, 1600, 9999],
    'OZONE':  [0, 50, 100, 168, 208, 748, 9999],
    'CO':     [0, 1, 2, 10, 17, 34, 9999],
    'NH3':    [0, 200, 400, 800, 1200, 1800, 9999],
}
AQI_LABELS = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
AQI_COLORS = ["#00e400", "#ffff00", "#ff7e00", "#ff0000", "#8f3f97", "#7e0023"]

def get_advice(pollutant, level):
    advice = {
        "Good": "Air quality is satisfactory. No health impacts expected.",
        "Satisfactory": "Air quality is acceptable. Sensitive individuals may experience minor breathing discomfort.",
        "Moderate": f"{pollutant} levels are moderate. Sensitive groups should reduce outdoor exertion.",
        "Poor": f"{pollutant} levels are poor. Everyone should reduce outdoor exertion. Sensitive groups should avoid prolonged exposure.",
        "Very Poor": f"{pollutant} levels are very poor. Avoid outdoor activities. Sensitive groups should remain indoors.",
        "Severe": f"{pollutant} levels are severe. Health alert: everyone may experience serious health effects. Remain indoors.",
    }
    return advice.get(level, "Take precautions based on local health guidelines.")

def get_health_status(pollutant, value):
    if pollutant not in AQI_BREAKPOINTS:
        return {"level": "Unknown", "color": "#ccc", "advice": "No data available."}
    breakpoints = AQI_BREAKPOINTS[pollutant]
    for i in range(len(breakpoints) - 1):
        if breakpoints[i] <= value < breakpoints[i + 1]:
            return {"level": AQI_LABELS[i], "color": AQI_COLORS[i], "advice": get_advice(pollutant, AQI_LABELS[i])}
    return {"level": AQI_LABELS[-1], "color": AQI_COLORS[-1], "advice": get_advice(pollutant, AQI_LABELS[-1])}


_meta = {}
_latest = {}
_station_to_city = {}
_models = {}
_scalers = {}
_pollutants = []
available_pollutants = []

def _load_models(pollutant):
    if pollutant in _models:
        return
    key = pollutant.lower().replace('.', '')
    _models[pollutant] = {}
    for h in range(1, 4):
        with open(MODEL_DIR / f'gb_delta_model_{key}_day{h}.pkl', 'rb') as f:
            _models[pollutant][f'day_{h}'] = pickle.load(f)
    with open(MODEL_DIR / f'scaler_X_{key}.pkl', 'rb') as f:
        _scalers[pollutant] = pickle.load(f)


def _save_precomputed():
    if not DATA_PATH.exists():
        print("ERROR: Data file not found")
        return False

    df_raw = pd.read_csv(DATA_PATH)
    df_raw['last_update'] = pd.to_datetime(df_raw['last_update'], format='mixed', dayfirst=True, errors='coerce')
    df_raw['avg_value'] = pd.to_numeric(df_raw['avg_value'], errors='coerce')
    df_raw['date'] = df_raw['last_update']

    latest = df_raw.sort_values('last_update').groupby(['station', 'state']).last().reset_index()
    station_map = {}
    for _, r in latest.iterrows():
        s = str(r['station']).strip() if pd.notna(r['station']) else ""
        st = str(r['state']).strip() if pd.notna(r['state']) else ""
        c = str(r['city']).strip() if pd.notna(r['city']) else ""
        if s and c:
            station_map[(s, st)] = c
    with open(MODEL_DIR / 'station_to_city.json', 'w') as f:
        json.dump({f"{k[0]}|{k[1]}": v for k, v in station_map.items()}, f)
    print(f"Saved station_to_city.json ({len(station_map)} stations)")

    agg_rules = {'avg_value': 'mean', 'min_value': 'mean', 'max_value': 'mean',
                 'latitude': 'mean', 'longitude': 'mean'}
    for w in WEATHER:
        agg_rules[w] = 'mean'
    df_agg = df_raw.groupby(['city', 'state', 'date', 'pollutant_id']).agg(agg_rules).reset_index()
    del df_raw
    gc.collect()

    for poll in ALL_POLLUTANTS:
        key = poll.lower().replace('.', '')
        nodes_path = MODEL_DIR / f'nodes_{key}.json'
        if not nodes_path.exists():
            continue
        with open(nodes_path, 'r') as f:
            nodes = json.load(f)

        poll_df = df_agg[df_agg['pollutant_id'] == poll].dropna(subset=['avg_value'])
        poll_df = poll_df[poll_df['city'].isin(nodes)]
        if len(poll_df) == 0:
            continue

        pivot = poll_df.pivot_table(index='date', columns='city', values='avg_value')
        pivot = pivot.sort_index().interpolate(axis=0).ffill().bfill()

        meta = poll_df.groupby('city')[['latitude', 'longitude', 'state']].first().loc[nodes].reset_index()
        meta.rename(columns={'city': 'node'}, inplace=True)

        weather_pivots = {}
        for col in WEATHER:
            wp = poll_df.pivot_table(index='date', columns='city', values=col, aggfunc='mean')
            wp = wp.reindex(columns=nodes).interpolate(axis=0).ffill().bfill()
            weather_pivots[col] = wp

        aux_pivots = {}
        for ap in [p for p in AUX_POLLS if p != poll]:
            tmp = df_agg[df_agg['pollutant_id'] == ap]
            tmp = tmp[tmp['city'].isin(nodes)]
            if len(tmp) == 0:
                continue
            ap_pivot = tmp.pivot_table(index='date', columns='city', values='avg_value', aggfunc='mean')
            ap_pivot = ap_pivot.reindex(index=pivot.index, columns=nodes).interpolate(axis=0).ffill().bfill().fillna(0)
            aux_pivots[ap] = ap_pivot

        with open(MODEL_DIR / f'feature_cols_{key}.json', 'r') as f:
            feature_cols = json.load(f)
        with open(MODEL_DIR / f'scaler_X_{key}.pkl', 'rb') as f:
            scaler = pickle.load(f)

        all_rows = []
        for node_i, node in enumerate(nodes):
            ts = pd.DataFrame(index=pivot.index)
            ts['target_t'] = pivot[node].values
            poll_key = poll.lower().replace('.', '')
            for lag in range(1, P + 1):
                ts[f'{poll_key}_lag_{lag}'] = ts['target_t'].shift(lag)
            ts['target_roll_mean_3'] = ts['target_t'].shift(1).rolling(3).mean()
            ts['target_roll_std_3'] = ts['target_t'].shift(1).rolling(3).std()
            ts['target_roll_mean_7'] = ts['target_t'].shift(1).rolling(7).mean()
            for col in WEATHER:
                ts[f'w_{col}'] = weather_pivots[col][node].values
                for lag in [1, 2]:
                    ts[f'w_{col}_lag_{lag}'] = weather_pivots[col][node].shift(lag).values
            for ap_name, ap_pivot in aux_pivots.items():
                ts[f'aux_{ap_name.lower().replace(".", "")}'] = ap_pivot[node].values
            ts['month'] = [d.month for d in pivot.index]
            ts['dayofweek'] = [d.dayofweek for d in pivot.index]
            ts['dayofyear'] = [d.dayofyear for d in pivot.index]
            ts['is_weekend'] = [int(d.weekday() >= 5) for d in pivot.index]
            ts['node_id'] = node_i
            ts['lat'] = meta.loc[node_i, 'latitude']
            ts['lon'] = meta.loc[node_i, 'longitude']
            ts['node_name'] = node
            all_rows.append(ts.iloc[-1:])

        latest_df = pd.concat(all_rows, ignore_index=True)
        latest_df = latest_df.dropna(subset=feature_cols)
        X_latest = scaler.transform(latest_df[feature_cols])

        city_lookup = {}
        for idx, row in latest_df.iterrows():
            city_lookup[row['node_name']] = {
                'today_value': float(row['target_t']),
                'feature_idx': int(idx),
                'lat': float(row['lat']),
                'lon': float(row['lon']),
                'state': str(meta[meta['node'] == row['node_name']]['state'].values[0]) if row['node_name'] in meta['node'].values else 'Unknown',
                'date': pivot.index[-1].strftime('%Y-%m-%d')
            }

        with open(MODEL_DIR / f'latest_{key}.pkl', 'wb') as f:
            pickle.dump({'X': X_latest, 'lookup': city_lookup}, f)
        with open(MODEL_DIR / f'meta_{key}.json', 'w') as f:
            json.dump({'nodes': nodes, 'feature_cols': feature_cols, 'latest_date': pivot.index[-1].strftime('%Y-%m-%d')}, f)

        cities_list = [
            {"name": c, "today_value": round(info['today_value'], 2), "state": info['state'], "lat": info['lat'], "lon": info['lon']}
            for c, info in city_lookup.items()
        ]
        with open(MODEL_DIR / f'cities_{key}.json', 'w') as f:
            json.dump(cities_list, f)

        print(f"  {poll}: {len(city_lookup)} cities, saved precomputed files")
        del pivot, meta, weather_pivots, aux_pivots, latest_df, X_latest, ts, all_rows
        gc.collect()

    del df_agg
    gc.collect()
    print("Precomputation complete. Backend can now run without loading the full CSV.")
    return True


def load_all():
    global _meta, _latest, _station_to_city, _pollutants, available_pollutants
    _meta = {}
    _latest = {}
    _station_to_city = {}
    _pollutants = []
    available_pollutants = []
    _models.clear()
    _scalers.clear()

    stc_path = MODEL_DIR / 'station_to_city.json'
    if stc_path.exists():
        with open(stc_path, 'r') as f:
            raw = json.load(f)
            _station_to_city = {tuple(k.split('|', 1)): v for k, v in raw.items()}
    else:
        print("WARNING: station_to_city.json not found. Run _save_precomputed() once.")

    for poll in ALL_POLLUTANTS:
        key = poll.lower().replace('.', '')
        meta_path = MODEL_DIR / f'meta_{key}.json'
        latest_path = MODEL_DIR / f'latest_{key}.pkl'
        if not meta_path.exists() or not latest_path.exists():
            print(f"  Missing precomputed files for {poll}, skipping")
            continue

        with open(meta_path, 'r') as f:
            _meta[poll] = json.load(f)
        with open(latest_path, 'rb') as f:
            _latest[poll] = pickle.load(f)

        _pollutants.append(poll)
        print(f"  {poll}: {len(_latest[poll]['lookup'])} cities")

    available_pollutants = _pollutants
    print(f"\nAvailable pollutants: {_pollutants}")
    mem = sum(_latest[p]['X'].nbytes for p in _pollutants) / 1024 / 1024
    print(f"Memory usage: ~{mem:.1f} MB for precomputed features")
    return {"pollutants": _pollutants, "cities": {p: len(_latest[p]['lookup']) for p in _pollutants}}


def _resolve_city(station_name, state):
    station_name = station_name.strip() if station_name else ""
    state = state.strip() if state else ""
    key = (station_name, state)
    if key in _station_to_city:
        return _station_to_city[key]
    for (s, st), c in _station_to_city.items():
        if s.lower() == station_name.lower() and st.lower() == state.lower():
            return c
    for (s, st), c in _station_to_city.items():
        if s.lower() == station_name.lower():
            return c
    import re
    match = re.search(r',\s*([^-,]+)\s*-', station_name)
    if match:
        extracted = match.group(1).strip()
        for p in _pollutants:
            if extracted in _latest[p]['lookup']:
                return extracted
    parts = re.split(r'\s+-\s+|,\s*', station_name)
    for part in parts:
        part = part.strip()
        for p in _pollutants:
            if part in _latest[p]['lookup']:
                return part
    return None


def predict_station(station_name, state, pollutant='PM2.5'):
    station_name = station_name.strip() if station_name else ""
    state = state.strip() if state else ""

    if pollutant not in _pollutants:
        return {"error": f"Pollutant '{pollutant}' not available. Available: {_pollutants}"}
    if pollutant not in _latest:
        return {"error": f"No precomputed features for '{pollutant}'"}

    _load_models(pollutant)

    city = _resolve_city(station_name, state)
    if not city:
        for p in _pollutants:
            if station_name in _latest[p]['lookup']:
                city = station_name
                break
    if not city:
        available = list(_latest[pollutant]['lookup'].keys())[:20]
        return {"error": f"Could not map station '{station_name}' to a known city. Available (first 20): {available}. Total: {len(_latest[pollutant]['lookup'])}."}

    lookup = _latest[pollutant]['lookup']
    X_latest = _latest[pollutant]['X']
    if city not in lookup:
        available = list(lookup.keys())[:20]
        return {"error": f"City '{city}' not found. Available (first 20): {available}."}

    info = lookup[city]
    today_value = info['today_value']
    idx = info['feature_idx']
    X = X_latest[idx].reshape(1, -1)

    predictions = {}
    delta_predictions = {}
    for h in range(1, 4):
        delta = _models[pollutant][f'day_{h}'].predict(X)[0]
        abs_pred = today_value + delta
        predictions[f'day{h}'] = round(float(abs_pred), 2)
        delta_predictions[f'day{h}'] = round(float(delta), 2)

    return {
        "station": station_name, "state": state, "city": city,
        "pollutant": pollutant, "today_value": round(today_value, 2),
        "date": info['date'], "predictions": predictions,
        "delta_predictions": delta_predictions,
        "health_status": {f"day{h}": get_health_status(pollutant, predictions[f'day{h}']) for h in range(1, 4)}
    }


def predict_city(city_name, pollutant='PM2.5'):
    return predict_station(city_name, "", pollutant)


def get_all_cities(pollutant='PM2.5'):
    if pollutant not in _pollutants:
        return {"cities": [], "pollutant": pollutant, "error": "Not available"}
    key = pollutant.lower().replace('.', '')
    cache_path = MODEL_DIR / f'cities_{key}.json'
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            cities = json.load(f)
        return {"pollutant": pollutant, "cities": cities}
    lookup = _latest[pollutant]['lookup']
    return {"pollutant": pollutant, "cities": [
        {"name": c, "today_value": round(info['today_value'], 2), "state": info['state'], "lat": info['lat'], "lon": info['lon']}
        for c, info in lookup.items()
    ]}


def get_available_pollutants():
    return {"pollutants": _pollutants, "count": len(_pollutants)}


if __name__ != "__main__":
    load_all()
