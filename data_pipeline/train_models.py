import os
import sys
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings('ignore')

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MERGED_DATA_PATH, MODELS_DIR, ALL_POLLUTANTS, P, Q, MIN_CITY_DAYS, AGG_MODE

SEED = 42
WEATHER = ['temperature', 'humidity', 'wind_speed', 'wind_direction']
AUX_POLLS = ALL_POLLUTANTS.copy()  # All can be auxiliary for each other


def log(msg):
    print(f"  {msg}")


def train_pollutant(target_poll, df_raw, output_dir):
    """Train models for one pollutant."""
    log(f"\nTraining: {target_poll}")
    
    # Filter to target pollutant
    poll_df = df_raw[df_raw['pollutant_id'] == target_poll].dropna(subset=['avg_value'])
    
    # Aggregate to city level
    agg_rules = {'avg_value': 'mean', 'min_value': 'mean', 'max_value': 'mean',
                 'latitude': 'mean', 'longitude': 'mean'}
    for w in WEATHER:
        agg_rules[w] = 'mean'
    
    df_agg = poll_df.groupby(['city', 'state', 'last_update', 'pollutant_id']).agg(agg_rules).reset_index()
    
    # Keep cities with enough data
    cnt = df_agg.groupby('city')['last_update'].nunique()
    good = cnt[cnt >= MIN_CITY_DAYS].index.tolist()
    if len(good) == 0:
        log(f"  Not enough cities for {target_poll}, skipping")
        return None
    
    df_agg = df_agg[df_agg['city'].isin(good)]
    
    # Build pivot
    pivot = df_agg.pivot_table(index='last_update', columns='city', values='avg_value')
    pivot = pivot.sort_index().interpolate(axis=0).ffill().bfill()
    nodes = pivot.columns.tolist()
    N = len(nodes)
    T = len(pivot)
    
    if N == 0 or T < P + Q + 10:
        log(f"  Not enough data ({N} cities, {T} days), skipping")
        return None
    
    log(f"  {N} cities, {T} days")
    
    # Weather pivots
    weather_pivots = {}
    for col in WEATHER:
        wp = df_agg.pivot_table(index='last_update', columns='city', values=col, aggfunc='mean')
        wp = wp.reindex(columns=nodes).interpolate(axis=0).ffill().bfill()
        weather_pivots[col] = wp
    
    # Aux pollutants (from full raw data, aggregated)
    aux_pivots = {}
    aux_polls = [p for p in AUX_POLLS if p != target_poll]
    for ap in aux_polls:
        tmp = df_raw[df_raw['pollutant_id'] == ap]
        tmp = tmp[tmp['city'].isin(nodes)]
        if len(tmp) == 0:
            continue
        ap_pivot = tmp.pivot_table(index='last_update', columns='city', values='avg_value', aggfunc='mean')
        ap_pivot = ap_pivot.reindex(index=pivot.index, columns=nodes).interpolate(axis=0).ffill().bfill().fillna(0)
        aux_pivots[ap] = ap_pivot
    
    # Build features
    all_node_data = []
    for node_i, node in enumerate(nodes):
        ts = pd.DataFrame(index=pivot.index)
        ts['date'] = pivot.index
        ts['target_t'] = pivot[node].values
        
        poll_key = target_poll.lower().replace('.', '')
        for lag in range(1, P + 1):
            ts[f'{poll_key}_lag_{lag}'] = ts['target_t'].shift(lag)
        
        ts['target_roll_mean_3'] = ts['target_t'].shift(1).rolling(3).mean()
        ts['target_roll_std_3'] = ts['target_t'].shift(1).rolling(3).std()
        ts['target_roll_mean_7'] = ts['target_t'].shift(1).rolling(7).mean()
        
        for col in WEATHER:
            ts[f'w_{col}'] = weather_pivots[col][node].values
        for col in WEATHER:
            for lag in [1, 2]:
                ts[f'w_{col}_lag_{lag}'] = weather_pivots[col][node].shift(lag).values
        
        for ap_name, ap_pivot in aux_pivots.items():
            ts[f'aux_{ap_name.lower().replace(".", "")}'] = ap_pivot[node].values
        
        ts['month'] = [pd.to_datetime(d).month for d in pivot.index]
        ts['dayofweek'] = [pd.to_datetime(d).dayofweek for d in pivot.index]
        ts['dayofyear'] = [pd.to_datetime(d).dayofyear for d in pivot.index]
        ts['is_weekend'] = [int(pd.to_datetime(d).weekday() >= 5) for d in pivot.index]
        
        ts['node_id'] = node_i
        ts['lat'] = df_agg.groupby('city')['latitude'].first()[node]
        ts['lon'] = df_agg.groupby('city')['longitude'].first()[node]
        ts['node_name'] = node
        
        ts['target_1'] = ts['target_t'].shift(-1) - ts['target_t']
        ts['target_2'] = ts['target_t'].shift(-2) - ts['target_t']
        ts['target_3'] = ts['target_t'].shift(-3) - ts['target_t']
        
        all_node_data.append(ts)
    
    full_df = pd.concat(all_node_data, ignore_index=True)
    full_df = full_df.dropna(subset=['target_1', 'target_2', 'target_3'])
    full_df = full_df.dropna()
    
    feature_cols = [c for c in full_df.columns if c.startswith((
        f'{poll_key}_', 'target_roll', 'w_', 'aux_', 'month', 'dayof', 'is_', 'lat', 'lon', 'node_id'
    ))]
    
    log(f"  Feature matrix: {full_df.shape} | {len(feature_cols)} features")
    
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
    
    if len(train_df) < 100 or len(test_df) < 50:
        log(f"  Not enough samples, skipping")
        return None
    
    # Normalize
    scaler_X = RobustScaler()
    scaler_X.fit(train_df[feature_cols])
    
    X_train = scaler_X.transform(train_df[feature_cols])
    X_test = scaler_X.transform(test_df[feature_cols])
    
    y_train = train_df[['target_1', 'target_2', 'target_3']].values
    y_test = test_df[['target_1', 'target_2', 'target_3']].values
    
    # Train 3 models
    models = {}
    test_maes = []
    for h in range(1, Q + 1):
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
        models[f'day_{h}'] = model
        
        # Quick test eval
        delta_pred = model.predict(X_test)
        abs_pred = test_df['target_t'].values + delta_pred
        abs_true = test_df['target_t'].values + y_test[:, h-1]
        mae = mean_absolute_error(abs_true, abs_pred)
        test_maes.append(mae)
    
    log(f"  Test MAE: +1d={test_maes[0]:.2f}, +2d={test_maes[1]:.2f}, +3d={test_maes[2]:.2f}")
    
    # Save all
    key = target_poll.lower().replace('.', '')
    for h in range(1, Q + 1):
        with open(output_dir / f'gb_delta_model_{key}_day{h}.pkl', 'wb') as f:
            pickle.dump(models[f'day_{h}'], f)
    
    with open(output_dir / f'scaler_X_{key}.pkl', 'wb') as f:
        pickle.dump(scaler_X, f)
    with open(output_dir / f'feature_cols_{key}.json', 'w') as f:
        json.dump(feature_cols, f)
    with open(output_dir / f'nodes_{key}.json', 'w') as f:
        json.dump(nodes, f)
    
    return {
        'pollutant': target_poll,
        'cities': N,
        'days': T,
        'test_mae': test_maes,
        'features': len(feature_cols)
    }


def run():
    print(f"\n{'='*60}")
    print(f"STEP 3: Training Models")
    print(f"{'='*60}")
    
    if not MERGED_DATA_PATH.exists():
        log(f"ERROR: Merged data not found at {MERGED_DATA_PATH}")
        return False
    
    df_raw = pd.read_csv(MERGED_DATA_PATH)
    df_raw['last_update'] = pd.to_datetime(df_raw['last_update'], format='%d-%m-%Y', dayfirst=True)
    log(f"Loaded merged data: {df_raw.shape}")
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    results = []
    for poll in ALL_POLLUTANTS:
        result = train_pollutant(poll, df_raw, MODELS_DIR)
        if result:
            results.append(result)
    
    # Save summary
    summary = {
        'trained_at': pd.Timestamp.now().isoformat(),
        'pollutants': results,
        'total_models': len(results) * Q
    }
    with open(MODELS_DIR / 'training_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    log(f"\nTrained {len(results)} pollutants ({len(results) * Q} models total)")
    log(f"Models saved to: {MODELS_DIR}")
    
    return True


if __name__ == "__main__":
    run()
