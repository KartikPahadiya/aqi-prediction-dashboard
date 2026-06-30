import warnings
warnings.filterwarnings('ignore')

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

SEED = 42

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_PATH = r"C:\Users\kartik pahadiya\pollution prediction\work\New folder\merged_aqi_weather_data (1).csv"
OUTPUT_DIR = r"C:\Users\kartik pahadiya\pollution prediction\work\New folder\train"
AGG_MODE = 'city'        # 'city' or 'station'
TOP_N_STATIONS = 25
MIN_CITY_DAYS = 35
P = 7                    # lookback window
Q = 3                    # forecast horizon

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# 1. LOAD & AGGREGATE
# ═══════════════════════════════════════════════════════════════════════════

print('='*60)
print('STEP 1: Loading Data')
print('='*60)

df_raw = pd.read_csv(DATA_PATH)
df_raw['date'] = pd.to_datetime(df_raw['date'])
df_raw['avg_value'] = pd.to_numeric(df_raw['avg_value'], errors='coerce')

print(f'Loaded: {df_raw.shape[0]:,} rows')
print(f'Date range: {df_raw["date"].min()} to {df_raw["date"].max()}')
print(f'Unique dates: {df_raw["date"].nunique()}')

TARGET = 'PM2.5'
AUX_POLLS = ['PM10', 'NO2', 'SO2', 'OZONE', 'NH3', 'CO']
WEATHER = ['temperature', 'humidity', 'wind_speed', 'wind_direction']

df = df_raw.copy()

if AGG_MODE == 'city':
    agg_rules = {'avg_value': 'mean', 'min_value': 'mean', 'max_value': 'mean',
                 'latitude': 'mean', 'longitude': 'mean'}
    for w in WEATHER:
        agg_rules[w] = 'mean'
    df_agg = df.groupby(['city', 'state', 'date', 'pollutant_id']).agg(agg_rules).reset_index()
    pm25 = df_agg[df_agg['pollutant_id'] == TARGET].dropna(subset=['avg_value'])
    cnt = pm25.groupby('city')['date'].nunique()
    good = cnt[cnt >= MIN_CITY_DAYS].index.tolist()
    pm25 = pm25[pm25['city'].isin(good)]
    pivot = pm25.pivot_table(index='date', columns='city', values='avg_value')
    pivot = pivot.sort_index().interpolate(axis=0).ffill().bfill()
    nodes = pivot.columns.tolist()
    meta = pm25.groupby('city')[['latitude', 'longitude', 'state']].first().loc[nodes].reset_index()
    meta.rename(columns={'city': 'node'}, inplace=True)
    group_col = 'city'
else:
    pm25 = df[df['pollutant_id'] == TARGET].dropna(subset=['avg_value'])
    cnt = pm25.groupby('station')['date'].nunique().sort_values(ascending=False)
    good = cnt.head(TOP_N_STATIONS).index.tolist()
    pm25 = pm25[pm25['station'].isin(good)]
    pivot = pm25.pivot_table(index='date', columns='station', values='avg_value')
    pivot = pivot.sort_index().interpolate(axis=0).ffill().bfill()
    nodes = pivot.columns.tolist()
    meta = pm25[['station', 'latitude', 'longitude', 'city', 'state']].drop_duplicates('station')
    meta = meta.set_index('station').loc[nodes].reset_index()
    meta.rename(columns={'station': 'node'}, inplace=True)
    group_col = 'station'

T, N = pivot.shape
print(f'\n✅ {N} nodes, {T} days')

# Weather pivots
weather_pivots = {}
for col in WEATHER:
    if AGG_MODE == 'city':
        wp = pm25.pivot_table(index='date', columns='city', values=col, aggfunc='mean')
    else:
        wp = pm25.pivot_table(index='date', columns='station', values=col, aggfunc='mean')
    wp = wp.reindex(columns=nodes).interpolate(axis=0).ffill().bfill()
    weather_pivots[col] = wp

# Aux pollutant pivots
aux_pivots = {}
for poll in AUX_POLLS:
    tmp = df_agg if AGG_MODE == 'city' else df
    tmp = tmp[tmp['pollutant_id'] == poll]
    tmp = tmp[tmp[group_col].isin(nodes)]
    if len(tmp) == 0:
        continue
    ap = tmp.pivot_table(index='date', columns=group_col, values='avg_value', aggfunc='mean')
    ap = ap.reindex(index=pivot.index, columns=nodes).interpolate(axis=0).ffill().bfill().fillna(0)
    aux_pivots[poll] = ap

print(f'Weather features: {WEATHER}')
print(f'Aux pollutants: {list(aux_pivots.keys())}')

# ═══════════════════════════════════════════════════════════════════════════
# 2. BUILD FEATURES & DELTA TARGETS
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 2: Feature Engineering + DELTA Targets')
print('='*60)

all_node_data = []
for node_i, node in enumerate(nodes):
    ts = pd.DataFrame(index=pivot.index)
    ts['date'] = pivot.index
    ts['target_t'] = pivot[node].values  # today's PM2.5 (used for reconstruction)
    
    # Lag features for PM2.5 (t-1 to t-P)
    for lag in range(1, P + 1):
        ts[f'pm25_lag_{lag}'] = ts['target_t'].shift(lag)
    
    # Rolling statistics
    ts['pm25_roll_mean_3'] = ts['target_t'].shift(1).rolling(3).mean()
    ts['pm25_roll_std_3'] = ts['target_t'].shift(1).rolling(3).std()
    ts['pm25_roll_mean_7'] = ts['target_t'].shift(1).rolling(7).mean()
    
    # Weather features (current day)
    for col in WEATHER:
        ts[f'w_{col}'] = weather_pivots[col][node].values
    
    # Weather lag features
    for col in WEATHER:
        for lag in [1, 2]:
            ts[f'w_{col}_lag_{lag}'] = weather_pivots[col][node].shift(lag).values
    
    # Aux pollutants (current day)
    for poll, ap in aux_pivots.items():
        ts[f'aux_{poll}'] = ap[node].values
    
    # Temporal features
    ts['month'] = [d.month for d in pivot.index]
    ts['dayofweek'] = [d.dayofweek for d in pivot.index]
    ts['dayofyear'] = [d.dayofyear for d in pivot.index]
    ts['is_weekend'] = [int(d.weekday() >= 5) for d in pivot.index]
    
    ts['node_id'] = node_i
    ts['lat'] = meta.loc[node_i, 'latitude']
    ts['lon'] = meta.loc[node_i, 'longitude']
    ts['node_name'] = node
    
    # ═══════════════════════════════════════════════════════════════════════
    # DELTA TARGETS: predict CHANGE from today's value
    # delta(t+1) = PM2.5(t+1) - PM2.5(t)
    # At inference: prediction = PM2.5(t) + model_prediction
    # ═══════════════════════════════════════════════════════════════════════
    ts['target_1'] = ts['target_t'].shift(-1) - ts['target_t']  # delta for +1 day
    ts['target_2'] = ts['target_t'].shift(-2) - ts['target_t']  # delta for +2 day
    ts['target_3'] = ts['target_t'].shift(-3) - ts['target_t']  # delta for +3 day
    
    all_node_data.append(ts)

full_df = pd.concat(all_node_data, ignore_index=True)

# Drop rows with NaN targets (at boundaries)
full_df = full_df.dropna(subset=['target_1', 'target_2', 'target_3'])
# Drop rows with NaN in any feature column (lag features create NaN at series start)
full_df = full_df.dropna()

print(f'✅ Feature matrix: {full_df.shape}')

feature_cols = [c for c in full_df.columns if c.startswith(('pm25_', 'w_', 'aux_', 'month', 'dayof', 'is_', 'lat', 'lon', 'node_id'))]
print(f'Feature count: {len(feature_cols)}')
print(f'Features: {feature_cols[:10]}...')

# Check target distribution
print(f'\nTarget delta statistics (all horizons):')
print(f'  mean={full_df[["target_1","target_2","target_3"]].mean().mean():.2f}')
print(f'  std={full_df[["target_1","target_2","target_3"]].std().mean():.2f}')

# ═══════════════════════════════════════════════════════════════════════════
# 3. TIME-BASED TRAIN/VAL/TEST SPLIT
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 3: Time-Series Split (No Leakage)')
print('='*60)

unique_dates = sorted(full_df['date'].unique())
n_train = int(len(unique_dates) * 0.70)
n_val = int(len(unique_dates) * 0.15)
train_dates = unique_dates[:n_train]
val_dates = unique_dates[n_train:n_train + n_val]
test_dates = unique_dates[n_train + n_val:]

print(f'Train dates: {len(train_dates)}  |  Val dates: {len(val_dates)}  |  Test dates: {len(test_dates)}')

train_df = full_df[full_df['date'].isin(train_dates)].copy()
val_df = full_df[full_df['date'].isin(val_dates)].copy()
test_df = full_df[full_df['date'].isin(test_dates)].copy()

print(f'Train samples: {len(train_df)}  |  Val: {len(val_df)}  |  Test: {len(test_df)}')

# ═══════════════════════════════════════════════════════════════════════════
# 4. NORMALIZATION — FIT ON TRAIN ONLY
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 4: Normalization (Fit on Train Only)')
print('='*60)

scaler_X = RobustScaler()
scaler_X.fit(train_df[feature_cols])

X_train = scaler_X.transform(train_df[feature_cols])
X_val = scaler_X.transform(val_df[feature_cols])
X_test = scaler_X.transform(test_df[feature_cols])

# Targets are deltas (can be negative), we train directly on them
y_train = train_df[['target_1', 'target_2', 'target_3']].values
y_val = val_df[['target_1', 'target_2', 'target_3']].values
y_test = test_df[['target_1', 'target_2', 'target_3']].values

print(f'✅ Features normalized: {len(feature_cols)} features')
print(f'   Training on delta (change) targets, not absolute values')

# ═══════════════════════════════════════════════════════════════════════════
# 5. TRAIN MODELS — One per horizon (t+1, t+2, t+3)
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 5: Training Delta Models')
print('='*60)

models = {}
val_maes = []
val_rmses = []

for h in range(1, Q + 1):
    print(f'\nTraining delta model for +{h} day...')
    
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
    
    val_pred = model.predict(X_val)
    val_mae = mean_absolute_error(y_val[:, h-1], val_pred)
    val_rmse = np.sqrt(mean_squared_error(y_val[:, h-1], val_pred))
    val_maes.append(val_mae)
    val_rmses.append(val_rmse)
    
    models[f'day_{h}'] = model
    print(f'  Delta Val MAE: {val_mae:.2f}  |  Delta Val RMSE: {val_rmse:.2f}')
    
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print(f'  Top 5 features: {importances.head(5).to_dict()}')

print(f'\nOverall Delta Val MAE: {np.mean(val_maes):.2f}  |  Val RMSE: {np.mean(val_rmses):.2f}')

# ═══════════════════════════════════════════════════════════════════════════
# 6. TEST EVALUATION — Reconstruct absolute values
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 6: Test Evaluation (Absolute Reconstruction)')
print('='*60)

# Absolute reconstruction: prediction = today's_value + delta_prediction
# This forces the model to learn weather-driven DEVIATIONS from persistence

results = {'Model': [], 'Horizon': [], 'MAE': [], 'RMSE': []}
per_node_test = {node: {'MAE': [], 'RMSE': []} for node in nodes}

for h in range(1, Q + 1):
    model = models[f'day_{h}']
    
    # Predict delta
    delta_pred = model.predict(X_test)
    
    # Reconstruct absolute: PM2.5(t+h) = PM2.5(t) + delta_pred
    # For +h day, we need to match the correct "today" value from test_df
    # test_df['target_t'] is PM2.5(t) for each row
    abs_pred = test_df['target_t'].values + delta_pred
    abs_true = test_df['target_t'].values + y_test[:, h-1]  # target_t + delta = actual future value
    
    test_mae = mean_absolute_error(abs_true, abs_pred)
    test_rmse = np.sqrt(mean_squared_error(abs_true, abs_pred))
    
    results['Model'].append('GradientBoosting (Delta)')
    results['Horizon'].append(f'+{h} day')
    results['MAE'].append(round(test_mae, 2))
    results['RMSE'].append(round(test_rmse, 2))
    
    print(f'  +{h} day  Abs MAE: {test_mae:.2f}  |  Abs RMSE: {test_rmse:.2f}')
    
    # Per-node breakdown
    test_df[f'abs_pred_{h}'] = abs_pred
    test_df[f'abs_true_{h}'] = abs_true
    for node in nodes:
        mask = test_df['node_name'] == node
        if mask.sum() > 0:
            node_mae = mean_absolute_error(
                test_df.loc[mask, f'abs_true_{h}'], 
                test_df.loc[mask, f'abs_pred_{h}']
            )
            node_rmse = np.sqrt(mean_squared_error(
                test_df.loc[mask, f'abs_true_{h}'], 
                test_df.loc[mask, f'abs_pred_{h}']
            ))
            per_node_test[node]['MAE'].append(node_mae)
            per_node_test[node]['RMSE'].append(node_rmse)

overall_test_mae = np.mean([r for r in results['MAE']])
overall_test_rmse = np.mean([r for r in results['RMSE']])
print(f'\nOverall Test MAE: {overall_test_mae:.2f}  |  Test RMSE: {overall_test_rmse:.2f}')

# ═══════════════════════════════════════════════════════════════════════════
# 7. BASELINE COMPARISON (Absolute scale)
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 7: Baseline Comparison')
print('='*60)

comparison = {'Model': [], 'MAE': [], 'RMSE': []}

# --- Naive: predict today's value (delta = 0) ---
naive_maes = []
naive_rmses = []
for h in range(1, Q + 1):
    # Naive delta = 0, so abs_pred = target_t
    abs_pred = test_df['target_t'].values
    abs_true = test_df['target_t'].values + y_test[:, h-1]
    mae = mean_absolute_error(abs_true, abs_pred)
    rmse = np.sqrt(mean_squared_error(abs_true, abs_pred))
    naive_maes.append(mae)
    naive_rmses.append(rmse)
comparison['Model'].append('Naive (Last Value)')
comparison['MAE'].append(round(np.mean(naive_maes), 2))
comparison['RMSE'].append(round(np.mean(naive_rmses), 2))
print(f'Naive (Last Value)  MAE={np.mean(naive_maes):.2f}  RMSE={np.mean(naive_rmses):.2f}')

# --- Linear Regression (Delta) ---
lr_maes = []
lr_rmses = []
for h in range(1, Q + 1):
    lr = Ridge(alpha=1.0)
    lr.fit(X_train, y_train[:, h-1])
    delta_pred = lr.predict(X_test)
    abs_pred = test_df['target_t'].values + delta_pred
    abs_true = test_df['target_t'].values + y_test[:, h-1]
    lr_maes.append(mean_absolute_error(abs_true, abs_pred))
    lr_rmses.append(np.sqrt(mean_squared_error(abs_true, abs_pred)))
comparison['Model'].append('Ridge Regression (Delta)')
comparison['MAE'].append(round(np.mean(lr_maes), 2))
comparison['RMSE'].append(round(np.mean(lr_rmses), 2))
print(f'Ridge Regression      MAE={np.mean(lr_maes):.2f}  RMSE={np.mean(lr_rmses):.2f}')

# --- Random Forest (Delta) ---
rf_maes = []
rf_rmses = []
for h in range(1, Q + 1):
    rf = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=SEED+h, n_jobs=-1)
    rf.fit(X_train, y_train[:, h-1])
    delta_pred = rf.predict(X_test)
    abs_pred = test_df['target_t'].values + delta_pred
    abs_true = test_df['target_t'].values + y_test[:, h-1]
    rf_maes.append(mean_absolute_error(abs_true, abs_pred))
    rf_rmses.append(np.sqrt(mean_squared_error(abs_true, abs_pred)))
comparison['Model'].append('Random Forest (Delta)')
comparison['MAE'].append(round(np.mean(rf_maes), 2))
comparison['RMSE'].append(round(np.mean(rf_rmses), 2))
print(f'Random Forest         MAE={np.mean(rf_maes):.2f}  RMSE={np.mean(rf_rmses):.2f}')

# --- Gradient Boosting (Delta, ours) ---
comparison['Model'].append('Gradient Boosting (Delta)')
comparison['MAE'].append(round(overall_test_mae, 2))
comparison['RMSE'].append(round(overall_test_rmse, 2))
print(f'Gradient Boosting     MAE={overall_test_mae:.2f}  RMSE={overall_test_rmse:.2f}')

print('\n' + '='*40)
comp_df = pd.DataFrame(comparison)
print(comp_df.to_string(index=False))
print('='*40)

# ═══════════════════════════════════════════════════════════════════════════
# 8. SAVE RESULTS
# ═══════════════════════════════════════════════════════════════════════════

print('\n' + '='*60)
print('STEP 8: Saving Results')
print('='*60)

import pickle
for h in range(1, Q + 1):
    with open(os.path.join(OUTPUT_DIR, f'gb_delta_model_day{h}.pkl'), 'wb') as f:
        pickle.dump(models[f'day_{h}'], f)
with open(os.path.join(OUTPUT_DIR, 'scaler_X_delta.pkl'), 'wb') as f:
    pickle.dump(scaler_X, f)
with open(os.path.join(OUTPUT_DIR, 'feature_cols_delta.json'), 'w') as f:
    json.dump(feature_cols, f)
with open(os.path.join(OUTPUT_DIR, 'nodes_delta.json'), 'w') as f:
    json.dump(nodes, f)

with open(os.path.join(OUTPUT_DIR, 'gb_delta_comparison.json'), 'w') as f:
    json.dump(comparison, f, indent=2)
with open(os.path.join(OUTPUT_DIR, 'gb_delta_results.json'), 'w') as f:
    json.dump(results, f, indent=2)

per_node_df = pd.DataFrame({
    'node': nodes,
    'MAE': [np.mean(per_node_test[n]['MAE']) for n in nodes],
    'RMSE': [np.mean(per_node_test[n]['RMSE']) for n in nodes]
})
per_node_df.to_json(os.path.join(OUTPUT_DIR, 'gb_delta_per_node.json'), orient='records', indent=2)

print(f'✅ Saved models and metrics to {OUTPUT_DIR}')

# ═══════════════════════════════════════════════════════════════════════════
# 9. PLOTS
# ═══════════════════════════════════════════════════════════════════════════

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Gradient Boosting (Delta) — AQI Prediction', fontsize=14, fontweight='bold')

# Comparison bar chart
ax = axes[0, 0]
x_pos = np.arange(len(comparison['Model']))
width = 0.35
bars1 = ax.bar(x_pos - width/2, comparison['MAE'], width, label='MAE', color='steelblue')
bars2 = ax.bar(x_pos + width/2, comparison['RMSE'], width, label='RMSE', color='coral')
ax.set_xticks(x_pos)
ax.set_xticklabels(comparison['Model'], rotation=15, ha='right')
ax.set_title('Model Comparison (Absolute MAE)')
ax.set_ylabel('Error (µg/m³)')
ax.legend()
ax.grid(True, alpha=0.3, axis='y')
for b in bars1:
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f'{b.get_height():.1f}', 
            ha='center', va='bottom', fontsize=8)
for b in bars2:
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f'{b.get_height():.1f}', 
            ha='center', va='bottom', fontsize=8)

# Per-node MAE
ax = axes[0, 1]
ax.barh(nodes, per_node_df['MAE'], color='steelblue')
ax.set_title('Per-Node Test MAE')
ax.set_xlabel('MAE (µg/m³)')
ax.grid(True, alpha=0.3, axis='x')

# Actual vs Predicted (day+1)
ax = axes[1, 0]
h = 1
mask = test_df['node_name'] == nodes[0]
ax.scatter(test_df.loc[mask, f'abs_true_{h}'], test_df.loc[mask, f'abs_pred_{h}'], alpha=0.6, s=30, color='steelblue')
mn = min(test_df.loc[mask, f'abs_true_{h}'].min(), test_df.loc[mask, f'abs_pred_{h}'].min())
mx = max(test_df.loc[mask, f'abs_true_{h}'].max(), test_df.loc[mask, f'abs_pred_{h}'].max())
ax.plot([mn, mx], [mn, mx], 'r--', lw=1)
ax.set_title(f'Actual vs Predicted — {nodes[0]} (+{h} day)')
ax.set_xlabel('Actual µg/m³')
ax.set_ylabel('Predicted µg/m³')
ax.grid(True, alpha=0.3)

# Feature importance (day+1)
ax = axes[1, 1]
imp = pd.Series(models['day_1'].feature_importances_, index=feature_cols).sort_values(ascending=True).tail(15)
ax.barh(imp.index, imp.values, color='steelblue')
ax.set_title('Top 15 Feature Importances (+1 day, Delta)')
ax.set_xlabel('Importance')
ax.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'gb_delta_results.png'), dpi=150, bbox_inches='tight')
plt.show()
print(f'\n📊 Plot saved: {os.path.join(OUTPUT_DIR, "gb_delta_results.png")}')

print('\n' + '='*60)
print('DONE')
print('='*60)
