import warnings
warnings.filterwarnings('ignore')

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

SEED = 42

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_PATH = r"C:\Users\kartik pahadiya\pollution prediction\backend\data\merged_aqi_weather_data.csv"
OUTPUT_DIR = r"C:\Users\kartik pahadiya\pollution prediction\backend\models"
AGG_MODE = 'city'
MIN_CITY_DAYS = 35
P = 7                    # lookback window
Q = 3                    # forecast horizon

ALL_POLLUTANTS = ['PM2.5', 'PM10', 'NO2', 'SO2', 'OZONE', 'NH3', 'CO']
WEATHER = ['temperature', 'humidity', 'wind_speed', 'wind_direction']

os.makedirs(OUTPUT_DIR, exist_ok=True)

print('='*60)
print('Multi-Pollutant Delta Model Training')
print('='*60)

# ═══════════════════════════════════════════════════════════════════════════
# 1. LOAD & AGGREGATE DATA (once)
# ═══════════════════════════════════════════════════════════════════════════

df_raw = pd.read_csv(DATA_PATH)
df_raw['date'] = pd.to_datetime(df_raw['date'])
df_raw['avg_value'] = pd.to_numeric(df_raw['avg_value'], errors='coerce')

print(f'Loaded: {df_raw.shape[0]:,} rows | {df_raw["date"].nunique()} unique dates')

agg_rules = {'avg_value': 'mean', 'min_value': 'mean', 'max_value': 'mean',
             'latitude': 'mean', 'longitude': 'mean'}
for w in WEATHER:
    agg_rules[w] = 'mean'

df_agg = df_raw.groupby(['city', 'state', 'date', 'pollutant_id']).agg(agg_rules).reset_index()

# Precompute all pollutant pivots for feature building
all_pivots = {}
all_meta = {}
all_weather = {}
all_aux = {}

for target_poll in ALL_POLLUTANTS:
    print(f'\n--- Preparing data for {target_poll} ---')
    
    poll_df = df_agg[df_agg['pollutant_id'] == target_poll].dropna(subset=['avg_value'])
    cnt = poll_df.groupby('city')['date'].nunique()
    good = cnt[cnt >= MIN_CITY_DAYS].index.tolist()
    poll_df = poll_df[poll_df['city'].isin(good)]
    
    if len(poll_df) == 0:
        print(f'  ❌ No data for {target_poll}, skipping')
        continue
    
    pivot = poll_df.pivot_table(index='date', columns='city', values='avg_value')
    pivot = pivot.sort_index().interpolate(axis=0).ffill().bfill()
    nodes = pivot.columns.tolist()
    N = len(nodes)
    T = len(pivot)
    
    if N == 0 or T < P + Q + 10:
        print(f'  ❌ Not enough data ({N} cities, {T} days), skipping')
        continue
    
    meta = poll_df.groupby('city')[['latitude', 'longitude', 'state']].first().loc[nodes].reset_index()
    meta.rename(columns={'city': 'node'}, inplace=True)
    
    # Weather (from the target pollutant's dataframe - all cities have same weather)
    weather_pivots = {}
    for col in WEATHER:
        wp = poll_df.pivot_table(index='date', columns='city', values=col, aggfunc='mean')
        wp = wp.reindex(columns=nodes).interpolate(axis=0).ffill().bfill()
        weather_pivots[col] = wp
    
    # Aux pollutants (all except target)
    aux_polls = [p for p in ALL_POLLUTANTS if p != target_poll]
    aux_pivots = {}
    for ap in aux_polls:
        tmp = df_agg[df_agg['pollutant_id'] == ap]
        tmp = tmp[tmp['city'].isin(nodes)]
        if len(tmp) == 0:
            continue
        ap_pivot = tmp.pivot_table(index='date', columns='city', values='avg_value', aggfunc='mean')
        ap_pivot = ap_pivot.reindex(index=pivot.index, columns=nodes).interpolate(axis=0).ffill().bfill().fillna(0)
        aux_pivots[ap] = ap_pivot
    
    all_pivots[target_poll] = pivot
    all_meta[target_poll] = meta
    all_weather[target_poll] = weather_pivots
    all_aux[target_poll] = aux_pivots
    
    print(f'  ✅ {N} cities, {T} days')

# ═══════════════════════════════════════════════════════════════════════════
# 2. TRAIN MODELS PER POLLUTANT
# ═══════════════════════════════════════════════════════════════════════════

for target_poll in ALL_POLLUTANTS:
    if target_poll not in all_pivots:
        continue
    
    print(f'\n{"="*60}')
    print(f'TRAINING: {target_poll}')
    print('='*60)
    
    pivot = all_pivots[target_poll]
    meta = all_meta[target_poll]
    weather_pivots = all_weather[target_poll]
    aux_pivots = all_aux[target_poll]
    nodes = pivot.columns.tolist()
    N = len(nodes)
    T = len(pivot)
    
    # Build features with pollutant-specific lags
    all_node_data = []
    for node_i, node in enumerate(nodes):
        ts = pd.DataFrame(index=pivot.index)
        ts['date'] = pivot.index
        ts['target_t'] = pivot[node].values
        
        # Lag features for TARGET pollutant
        for lag in range(1, P + 1):
            ts[f'{target_poll.lower().replace(".", "")}_lag_{lag}'] = ts['target_t'].shift(lag)
        
        # Rolling stats on target
        ts['target_roll_mean_3'] = ts['target_t'].shift(1).rolling(3).mean()
        ts['target_roll_std_3'] = ts['target_t'].shift(1).rolling(3).std()
        ts['target_roll_mean_7'] = ts['target_t'].shift(1).rolling(7).mean()
        
        # Weather
        for col in WEATHER:
            ts[f'w_{col}'] = weather_pivots[col][node].values
        for col in WEATHER:
            for lag in [1, 2]:
                ts[f'w_{col}_lag_{lag}'] = weather_pivots[col][node].shift(lag).values
        
        # Aux pollutants (all other pollutants as current-day features)
        for ap_name, ap_pivot in aux_pivots.items():
            ts[f'aux_{ap_name.lower().replace(".", "")}'] = ap_pivot[node].values
        
        # Temporal
        ts['month'] = [d.month for d in pivot.index]
        ts['dayofweek'] = [d.dayofweek for d in pivot.index]
        ts['dayofyear'] = [d.dayofyear for d in pivot.index]
        ts['is_weekend'] = [int(d.weekday() >= 5) for d in pivot.index]
        
        ts['node_id'] = node_i
        ts['lat'] = meta.loc[node_i, 'latitude']
        ts['lon'] = meta.loc[node_i, 'longitude']
        ts['node_name'] = node
        
        # Delta targets
        ts['target_1'] = ts['target_t'].shift(-1) - ts['target_t']
        ts['target_2'] = ts['target_t'].shift(-2) - ts['target_t']
        ts['target_3'] = ts['target_t'].shift(-3) - ts['target_t']
        
        all_node_data.append(ts)
    
    full_df = pd.concat(all_node_data, ignore_index=True)
    full_df = full_df.dropna(subset=['target_1', 'target_2', 'target_3'])
    full_df = full_df.dropna()
    
    feature_cols = [c for c in full_df.columns if c.startswith((f'{target_poll.lower().replace(".", "")}_', 'target_roll', 'w_', 'aux_', 'month', 'dayof', 'is_', 'lat', 'lon', 'node_id'))]
    
    print(f'  Feature matrix: {full_df.shape} | Features: {len(feature_cols)}')
    
    # Time split
    unique_dates = sorted(full_df['date'].unique())
    n_train = int(len(unique_dates) * 0.70)
    n_val = int(len(unique_dates) * 0.15)
    train_dates = unique_dates[:n_train]
    val_dates = unique_dates[n_train:n_train + n_val]
    test_dates = unique_dates[n_train + n_val:]
    
    train_df = full_df[full_df['date'].isin(train_dates)].copy().dropna()
    val_df = full_df[full_df['date'].isin(val_dates)].copy().dropna()
    test_df = full_df[full_df['date'].isin(test_dates)].copy().dropna()
    
    print(f'  Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}')
    
    if len(train_df) < 100 or len(test_df) < 50:
        print(f'  ❌ Not enough samples, skipping')
        continue
    
    # Normalize
    scaler_X = RobustScaler()
    scaler_X.fit(train_df[feature_cols])
    
    X_train = scaler_X.transform(train_df[feature_cols])
    X_val = scaler_X.transform(val_df[feature_cols])
    X_test = scaler_X.transform(test_df[feature_cols])
    
    y_train = train_df[['target_1', 'target_2', 'target_3']].values
    y_val = val_df[['target_1', 'target_2', 'target_3']].values
    y_test = test_df[['target_1', 'target_2', 'target_3']].values
    
    # Train 3 models (one per horizon)
    models = {}
    for h in range(1, Q + 1):
        print(f'    Training +{h} day model...')
        model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=SEED + h,
            validation_fraction=0.1,
            n_iter_no_change=10,
            tol=1e-4
        )
        model.fit(X_train, y_train[:, h-1])
        
        # Save
        model_path = os.path.join(OUTPUT_DIR, f'gb_delta_model_{target_poll.lower().replace(".", "")}_day{h}.pkl')
        import pickle
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        models[f'day_{h}'] = model
    
    # Save scaler and metadata
    scaler_path = os.path.join(OUTPUT_DIR, f'scaler_X_{target_poll.lower().replace(".", "")}.pkl')
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler_X, f)
    
    feature_path = os.path.join(OUTPUT_DIR, f'feature_cols_{target_poll.lower().replace(".", "")}.json')
    with open(feature_path, 'w') as f:
        json.dump(feature_cols, f)
    
    nodes_path = os.path.join(OUTPUT_DIR, f'nodes_{target_poll.lower().replace(".", "")}.json')
    with open(nodes_path, 'w') as f:
        json.dump(nodes, f)
    
    # Evaluate on test
    test_maes = []
    for h in range(1, Q + 1):
        delta_pred = models[f'day_{h}'].predict(X_test)
        abs_pred = test_df['target_t'].values + delta_pred
        abs_true = test_df['target_t'].values + y_test[:, h-1]
        mae = mean_absolute_error(abs_true, abs_pred)
        test_maes.append(mae)
    
    print(f'  ✅ Saved! Test MAE: +1d={test_maes[0]:.2f}, +2d={test_maes[1]:.2f}, +3d={test_maes[2]:.2f}')

print(f'\n{"="*60}')
print('ALL MODELS TRAINED')
print('='*60)
