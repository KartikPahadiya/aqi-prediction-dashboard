#!/usr/bin/env python3
"""
Production Pipeline Orchestrator
================================
Runs the full daily pipeline:
1. Fetch new AQI data from API
2. Preprocess (clean, dedup, fill missing dates, fetch weather, merge)
3. Retrain all models
4. Report results

Usage:
    python pipeline.py           # Run full pipeline
    python pipeline.py --fetch   # Only fetch
    python pipeline.py --train   # Only train (assumes data exists)
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_PATH


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    
    # Also append to log file
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')


def run_pipeline(skip_fetch=False, skip_train=False):
    log("="*60)
    log("AQI FORECAST PIPELINE STARTED")
    log("="*60)
    
    success = True
    
    # Step 1: Fetch
    if not skip_fetch:
        from fetch_aqi import run as fetch_run
        try:
            fetched = fetch_run()
            if not fetched:
                log("No new data fetched. Will still retrain on existing data.")
        except Exception as e:
            log(f"FETCH FAILED: {e}")
            success = False
    
    # Step 2: Preprocess
    from preprocess import run as preprocess_run
    try:
        preprocessed = preprocess_run()
        if not preprocessed:
            log("PREPROCESS FAILED")
            success = False
    except Exception as e:
        log(f"PREPROCESS FAILED: {e}")
        success = False
    
    # Step 3: Train
    if not skip_train and success:
        from train_models import run as train_run
        try:
            trained = train_run()
            if not trained:
                log("TRAINING FAILED")
                success = False
            else:
                log("TRAINING COMPLETE")
        except Exception as e:
            log(f"TRAINING FAILED: {e}")
            success = False
    
    log("="*60)
    if success:
        log("PIPELINE COMPLETED SUCCESSFULLY")
    else:
        log("PIPELINE COMPLETED WITH ERRORS")
    log("="*60)
    
    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AQI Forecast Pipeline")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch data")
    parser.add_argument("--train-only", action="store_true", help="Only train models")
    args = parser.parse_args()
    
    if args.fetch_only:
        from fetch_aqi import run as fetch_run
        fetch_run()
    elif args.train_only:
        from train_models import run as train_run
        train_run()
    else:
        run_pipeline()
