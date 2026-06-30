"""One-time precomputation script to generate lightweight cache files.
Run this once after training models to create the cache files the backend needs.
"""
from inference import _save_precomputed

if __name__ == "__main__":
    print("Starting precomputation...")
    success = _save_precomputed()
    if success:
        print("\nDone! Now you can run: python app.py")
    else:
        print("\nFailed. Check errors above.")
