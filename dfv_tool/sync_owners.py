"""
Sync Owner column from edited Excel back to DB, then regenerate dashboard.
Usage: python dfv_tool/sync_owners.py
"""
import sys
import os
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from history import sync_owners_from_excel
from dashboard import generate_dashboard

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def find_latest_excel():
    """Find the most recent DFV_actions_*.xlsx in output/."""
    pattern = os.path.join(OUTPUT_DIR, "DFV_actions_*.xlsx")
    files = glob.glob(pattern)
    if not files:
        print("No DFV_actions_*.xlsx found in output/")
        return None
    return max(files, key=os.path.getmtime)


if __name__ == "__main__":
    xlsx = find_latest_excel()
    if xlsx is None:
        sys.exit(1)
    print(f"Syncing from: {xlsx}")
    sync_owners_from_excel(xlsx)
    generate_dashboard()
    print("Done! Dashboard refreshed.")
