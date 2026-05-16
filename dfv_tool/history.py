"""
DFV History - SQLite storage for weekly DFV results.
Stores KPI summary + all error details for each run.
"""
import sqlite3
import os
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
