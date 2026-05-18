"""
DFV History - SQLite storage for weekly DFV results.
Stores KPI summary + all error details for each run.
"""
import sqlite3
import os
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dfv_history.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            week_label TEXT,
            total_rows INTEGER,
            total_idp REAL,
            total_apo REAL,
            diff_pct REAL,
            vol_status TEXT,
            total_errors INTEGER,
            actionable_errors INTEGER,
            hktw_errors INTEGER,
            sku_status TEXT,
            impact_volume REAL
        );

        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            file_id TEXT,
            apo_product TEXT,
            description TEXT,
            category TEXT,
            brand TEXT,
            apo_location TEXT,
            snp_planner TEXT,
            error_message TEXT,
            idp_forecast REAL,
            apo_forecast REAL,
            reason TEXT,
            action TEXT,
            owner TEXT,
            is_hktw INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );
    """)
    conn.commit()
    conn.close()


def save_run(summary, errors_df):
    """Save a DFV run to history. Returns run_id."""
    init_db()
    conn = _get_conn()

    # Week label: e.g. "W20/2026"
    today = datetime.now()
    iso = today.isocalendar()
    week_label = f"W{iso[1]:02d}/{iso[0]}"

    cur = conn.execute("""
        INSERT INTO runs (run_date, week_label, total_rows, total_idp, total_apo,
                          diff_pct, vol_status, total_errors, actionable_errors,
                          hktw_errors, sku_status, impact_volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        today.strftime("%Y-%m-%d %H:%M"),
        week_label,
        summary["total_rows"],
        summary["total_idp"],
        summary["total_apo"],
        summary["diff_pct"],
        summary["vol_status"],
        summary["total_errors"],
        summary["actionable_errors"],
        summary["hktw_errors"],
        summary["sku_status"],
        summary["impact_volume_3m"],
    ))
    run_id = cur.lastrowid

    # Save error details
    if not errors_df.empty:
        rows = []
        for _, r in errors_df.iterrows():
            rows.append((
                run_id,
                r.get("File_ID", ""),
                str(r.get("APO_Product", "")),
                r.get("Description", ""),
                r.get("Category", ""),
                r.get("Brand", ""),
                r.get("APO_Location", ""),
                r.get("SNP_Planner", ""),
                r.get("Error_Message", ""),
                float(r.get("IDP_Forecast", 0)),
                float(r.get("APO_Forecast", 0)),
                r.get("Reason", ""),
                r.get("Action", ""),
                r.get("Owner", ""),
                1 if r.get("Is_HKTW", False) else 0,
            ))
        conn.executemany("""
            INSERT INTO errors (run_id, file_id, apo_product, description, category,
                                brand, apo_location, snp_planner, error_message,
                                idp_forecast, apo_forecast, reason, action, owner, is_hktw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    conn.commit()
    conn.close()
    return run_id


def get_all_runs():
    """Get all run summaries, ordered by date."""
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM runs ORDER BY run_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_errors_for_run(run_id):
    """Get all errors for a specific run."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM errors WHERE run_id = ? ORDER BY owner, error_message",
                        (run_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_data():
    """Get all runs + their errors. For dashboard generation."""
    runs = get_all_runs()
    conn = _get_conn()
    for run in runs:
        rows = conn.execute(
            "SELECT * FROM errors WHERE run_id = ? AND is_hktw = 0 ORDER BY owner, error_message",
            (run["id"],)
        ).fetchall()
        run["errors"] = [dict(r) for r in rows]
    conn.close()
    return runs


def update_owners(mapping, run_id=None):
    """
    Batch update owners in the DB.

    Args:
        mapping: dict of {error_message: new_owner_name}
                 e.g. {"Missing Mat/Loc": "张三 / IOL", "Matloc Deleted": "李四"}
        run_id:  If None, update ALL runs. If specified, only that run.

    Example usage:
        from history import update_owners
        update_owners({"Missing Mat/Loc": "张三 / IOL", "No SNP Assigned": "王五"})
    """
    conn = _get_conn()
    for error_msg, new_owner in mapping.items():
        if run_id:
            conn.execute(
                "UPDATE errors SET owner = ? WHERE error_message = ? AND run_id = ?",
                (new_owner, error_msg, run_id)
            )
        else:
            conn.execute(
                "UPDATE errors SET owner = ? WHERE error_message = ?",
                (new_owner, error_msg)
            )
    conn.commit()
    affected = conn.execute("SELECT changes()").fetchone()[0]
    conn.close()
    print(f"Updated {affected} rows")
    return affected


def sync_owners_from_excel(excel_path, run_id=None):
    """
    Read Owner column from edited Excel, sync back to DB.
    Matches by APO_Product + APO_Location + Error_Message.

    Args:
        excel_path: Path to edited DFV_actions_YYYYMMDD.xlsx
        run_id: If None, update the latest run. If specified, that run.

    Usage:
        from history import sync_owners_from_excel
        sync_owners_from_excel("output/DFV_actions_20260518.xlsx")
    """
    # Read the date-named sheet (second sheet, skip Summary)
    xl = pd.ExcelFile(excel_path)
    # Find the detail sheet (named like 20260518)
    detail_sheet = None
    for name in xl.sheet_names:
        if name.isdigit() and len(name) == 8:
            detail_sheet = name
            break
    if detail_sheet is None:
        detail_sheet = xl.sheet_names[1] if len(xl.sheet_names) > 1 else xl.sheet_names[0]

    df = pd.read_excel(excel_path, sheet_name=detail_sheet)

    # Map Excel column names to DB columns
    col_map = {
        "APO - Product": "apo_product",
        "APO - Location": "apo_location",
        "Error Message": "error_message",
        "Owner": "owner",
    }
    # Check required columns exist
    missing = [c for c in col_map if c not in df.columns]
    if missing:
        raise ValueError(f"Excel missing columns: {missing}")

    # Determine run_id
    if run_id is None:
        conn = _get_conn()
        row = conn.execute("SELECT id FROM runs ORDER BY run_date DESC LIMIT 1").fetchone()
        if not row:
            raise ValueError("No runs in DB")
        run_id = row["id"]
        conn.close()

    # Update each row
    conn = _get_conn()
    updated = 0
    for _, row in df.iterrows():
        product = str(row["APO - Product"])
        location = str(row["APO - Location"])
        error_msg = str(row["Error Message"])
        owner = str(row["Owner"])

        cur = conn.execute("""
            UPDATE errors SET owner = ?
            WHERE run_id = ? AND apo_product = ? AND apo_location = ? AND error_message = ?
        """, (owner, run_id, product, location, error_msg))
        updated += cur.rowcount

    conn.commit()
    conn.close()
    print(f"Synced {updated} owners from Excel (run_id={run_id})")
    return updated
