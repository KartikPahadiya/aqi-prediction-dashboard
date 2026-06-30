import os
import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

from config import RAW_DATA_PATH, API_KEY, API_URL


def fetch_all_data():
    """Fetch all AQI data from data.gov.in API."""
    headers = {"User-Agent": "Mozilla/5.0"}
    all_data = []

    for offset in range(0, 50000, 1000):
        params = {
            "api-key": API_KEY,
            "format": "json",
            "limit": 1000,
            "offset": offset
        }

        try:
            r = requests.get(API_URL, params=params, headers=headers, timeout=30)
            if r.status_code != 200:
                print(f"  Warning: status {r.status_code} at offset {offset}")
                time.sleep(5)
                continue

            records = r.json().get("records", [])
            if not records:
                break

            all_data.extend(records)
            print(f"  Fetched {len(records)} records (offset {offset})")
            time.sleep(1)

        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            time.sleep(5)
            continue

    return pd.DataFrame(all_data)


def run():
    print(f"\n{'='*60}")
    print(f"STEP 1: Fetching AQI Data")
    print(f"{'='*60}")

    new_df = fetch_all_data()

    if new_df.empty:
        print("  No data fetched. Exiting.")
        return False

    new_df["collection_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    today = datetime.now().strftime("%Y-%m-%d")

    if RAW_DATA_PATH.exists():
        old_df = pd.read_csv(RAW_DATA_PATH)

        # Check if already updated today
        if "collection_time" in old_df.columns:
            try:
                old_df["collection_time"] = pd.to_datetime(old_df["collection_time"], format='mixed', errors='coerce', dayfirst=True)
                if today in old_df["collection_time"].dt.strftime("%Y-%m-%d").values:
                    print(f"  Already updated today ({today}). Skipping fetch.")
                    return False
            except Exception:
                # If parsing fails, continue anyway (might be first run with mixed formats)
                pass

        final_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    # Deduplicate on save
    final_df = final_df.drop_duplicates()
    final_df.to_csv(RAW_DATA_PATH, index=False)

    print(f"  Saved: {RAW_DATA_PATH}")
    print(f"  Total rows: {len(final_df):,}")
    print(f"  New rows added: {len(new_df):,}")

    return True


if __name__ == "__main__":
    run()
