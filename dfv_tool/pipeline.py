"""
DFV Pipeline - Step 2: Watch for new CSV, then analyze and report.
This script runs after UIBot + VBA completes the SAP BW refresh.

Workflow:
  1. Watch output/ folder for READY.flag
  2. Read the exported CSV
  3. Classify issues and assign owners
  4. Generate report
  5. (Future) Send emails to owners
"""
import os
import sys
import time
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    OUTPUT_DIR, ERROR_TYPES, OWNER_MAPPING, DRP_LOCATIONS, CATEGORY,
)


def watch_for_ready(timeout=600, poll_interval=5):
    """Wait for READY.flag file to appear in output directory."""
    flag_path = os.path.join(OUTPUT_DIR, "READY.flag")
    print(f"Watching for: {flag_path}")
    print(f"Timeout: {timeout}s")

    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(flag_path):
            with open(flag_path, "r") as f:
                lines = f.read().strip().split("\n")
            csv_path = lines[0].strip()
            timestamp = lines[1].strip() if len(lines) > 1 else ""
            print(f"READY! CSV: {csv_path} (at {timestamp})")
            # Remove flag
            os.remove(flag_path)
            return csv_path
        time.sleep(poll_interval)

    print("TIMEOUT: No READY.flag detected")
    return None


def load_data(csv_path):
    """Load exported CSV data."""
    df = pd.read_csv(csv_path)

    # Map raw Excel headers to internal names
    header_map = {
        "File ID": "File_ID",
        "APO - Product": "APO_Product",
        "Col3": "Description",
        "Category": "Category",
        "Brand": "Brand",
        "APO - Location": "APO_Location",
        "SNP Planner": "SNP_Planner",
        "Error Message": "Error_Message",
        "Forecast": "IDP_Forecast",
        "DP Fcst (Simulated)": "APO_Forecast",
    }
    df.rename(columns={k: v for k, v in header_map.items() if k in df.columns}, inplace=True)

    df["IDP_Forecast"] = pd.to_numeric(df["IDP_Forecast"], errors="coerce").fillna(0)
    df["APO_Forecast"] = pd.to_numeric(df["APO_Forecast"], errors="coerce").fillna(0)
    print(f"Loaded {len(df)} rows from {os.path.basename(csv_path)}")

    # Apply business filters (in case SAP returned unfiltered data)
    before = len(df)
    if "Category" in df.columns:
        df = df[df["Category"] == CATEGORY]
    if "APO_Location" in df.columns:
        df = df[df["APO_Location"].isin(DRP_LOCATIONS)]
    if len(df) < before:
        print(f"  Filtered: {before} -> {len(df)} rows (Category={CATEGORY}, {len(DRP_LOCATIONS)} locations)")

    return df


def classify_issues(df):
    """Classify error rows and assign owners/actions."""
    errors = df[df["Error_Message"] != "Successful"].copy()

    if errors.empty:
        print("No errors found - all data flowing correctly!")
        return errors

    # Assign owner
    errors["Owner"] = errors["Error_Message"].map(OWNER_MAPPING).fillna("CSP Planner")

    # Generate unique key
    errors["Key"] = errors["APO_Product"].astype(str) + errors["APO_Location"].astype(str)

    # For Missing Mat/Loc: check if ALL locations have this error (= no code activation)
    # vs only some locations (= missing master data in APO-DRP)
    missing_ml = errors[errors["Error_Message"] == "Missing Mat/Loc"]
    all_loc_products = set()  # products where ALL their locations have Missing Mat/Loc
    if not missing_ml.empty:
        for prod, grp in missing_ml.groupby("APO_Product"):
            prod_locs = set(grp["APO_Location"])
            if prod_locs >= (set(DRP_LOCATIONS) - {"5740"}):
                all_loc_products.add(prod)

    # Classify reason and action
    def get_reason_action(row):
        msg = row["Error_Message"]
        loc = row["APO_Location"]
        prod = row["APO_Product"]
        if msg == "Missing Mat/Loc":
            if loc == "5740":
                return "HKTW location", "HKTW - No action needed"
            elif prod in all_loc_products:
                return "No code activation requested", "CSP to investigate with IOL/SIP planner"
            else:
                return "Missing master data in APO-DRP", "Check code activation / Apply T-lane"
        elif msg == "Matloc Deleted":
            return "Material/location deleted but still has forecast", "Contact DP to remove forecast"
        elif msg == "No SNP Assigned":
            if loc == "5740":
                return "HKTW location", "HKTW - No action needed"
            else:
                return "DRP master data incomplete - no SNP planner", "DRP to complete master data"
        elif msg == "SNP equals *99":
            return "Code turned off in APO but still has forecast", "DRP to reactivate or DP to remove forecast"
        elif msg == "Under Deletion":
            return "Material under deletion process", "Contact DP to remove forecast"
        return "Unknown", "Investigate"

    reason_action = errors.apply(get_reason_action, axis=1, result_type="expand")
    errors["Reason"] = reason_action[0]
    errors["Action"] = reason_action[1]

    # Flag HKTW items (location 5740 = Hong Kong/Taiwan, usually no action needed)
    errors["Is_HKTW"] = errors["APO_Location"] == "5740"

    print(f"\nIssue Classification:")
    print(f"  Total errors: {len(errors)}")
    print(f"  HKTW (no action): {errors['Is_HKTW'].sum()}")
    print(f"  Actionable: {(~errors['Is_HKTW']).sum()}")
    print(f"\n  By Error Type:")
    for etype, group in errors.groupby("Error_Message"):
        actionable = len(group[~group["Is_HKTW"]])
        print(f"    {etype}: {len(group)} total, {actionable} actionable, {group['IDP_Forecast'].sum():,.0f} MSU")

    return errors


def generate_summary(df, errors):
    """Generate summary statistics with two KPIs:
    1. 18 Months volume difference (target < 2%)
    2. 13 weeks SKU difference (target = 0 SKU)
    """
    total_idp = df["IDP_Forecast"].sum()
    total_apo = df["APO_Forecast"].sum()
    diff = abs(total_idp - total_apo)
    diff_pct = diff / total_idp * 100 if total_idp > 0 else 0

    actionable = errors[~errors["Is_HKTW"]] if "Is_HKTW" in errors.columns else errors
    total_error_skus = len(errors)

    vol_status = "on-track" if diff_pct < 2.0 else "off-track"
    sku_status = "on-track" if total_error_skus == 0 else "off-track"

    summary = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_rows": len(df),
        "total_idp": total_idp,
        "total_apo": total_apo,
        "diff_volume": diff,
        "diff_pct": diff_pct,
        "vol_status": vol_status,
        "total_errors": total_error_skus,
        "actionable_errors": len(actionable),
        "hktw_errors": len(errors) - len(actionable),
        "sku_status": sku_status,
        "impact_volume_3m": actionable["IDP_Forecast"].sum() if len(actionable) > 0 else 0,
    }

    # KPI table output
    print(f"\n{'='*90}")
    print(f"DFV SUMMARY - {summary['date']}")
    print(f"{'='*90}")
    print(f"{'Criteria':<30} {'Status':<12} {'TOTAL Demand HUB':>18} {'TOTAL APO-DRP':>15} {'% DIFF':>10} {'Target':>10}")
    print(f"{'-'*90}")
    print(f"{'18 Months volume difference':<30} {vol_status:<12} {total_idp:>18,.0f} {total_apo:>15,.0f} {diff_pct:>9.2f}% {'2%':>10}")
    print(f"{'13 weeks sku difference':<30} {sku_status:<12} {'':>18} {'':>15} {total_error_skus:>10} {'0 SKU':>10}")
    print(f"{'='*90}")
    print(f"  Actionable errors: {len(actionable)}  |  HKTW (no action): {len(errors) - len(actionable)}  |  Impact Volume: {summary['impact_volume_3m']:,.0f} MSU")
    print(f"{'='*90}")

    return summary


def generate_owner_report(errors):
    """Group errors by owner for distribution."""
    if errors.empty:
        return {}

    actionable = errors[~errors["Is_HKTW"]]
    reports = {}

    for owner, group in actionable.groupby("Owner"):
        report = {
            "owner": owner,
            "count": len(group),
            "volume": group["IDP_Forecast"].sum(),
            "items": group[["APO_Product", "Description", "APO_Location",
                           "Error_Message", "IDP_Forecast", "Action"]].to_dict("records"),
        }
        reports[owner] = report
        print(f"\n  {owner}: {report['count']} items, {report['volume']:,.0f} MSU")
        for item in report["items"][:5]:
            print(f"    {item['APO_Product']} @ {item['APO_Location']}: "
                  f"{item['Error_Message']} ({item['IDP_Forecast']:,.0f}) -> {item['Action']}")
        if len(report["items"]) > 5:
            print(f"    ... and {len(report['items']) - 5} more")

    return reports


def export_results(errors, summary, output_dir):
    """Export analysis results."""
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")

    # Export actionable errors
    if not errors.empty:
        actionable = errors[~errors["Is_HKTW"]]
        if not actionable.empty:
            out_path = os.path.join(output_dir, f"DFV_actions_{date_str}.xlsx")
            with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
                # KPI Summary sheet
                kpi_data = pd.DataFrame([
                    {
                        "Criteria": "18 Months volume difference",
                        "Status": summary["vol_status"],
                        "TOTAL Demand HUB": summary["total_idp"],
                        "TOTAL APO-DRP": summary["total_apo"],
                        "% DIFF": f"{summary['diff_pct']:.2f}%",
                        "Target": "2%",
                    },
                    {
                        "Criteria": "13 weeks sku difference",
                        "Status": summary["sku_status"],
                        "TOTAL Demand HUB": "",
                        "TOTAL APO-DRP": "",
                        "% DIFF": summary["total_errors"],
                        "Target": "0 SKU",
                    },
                ])
                kpi_data.to_excel(writer, sheet_name="Summary", index=False)

                # Date-named detail sheet with exact columns
                detail_cols = {
                    "File_ID": "File ID",
                    "APO_Product": "APO - Product",
                    "Category": "Category",
                    "Brand": "Brand",
                    "APO_Location": "APO - Location",
                    "SNP_Planner": "SNP Planner",
                    "Error_Message": "Error Message",
                    "IDP_Forecast": "Forecast",
                    "APO_Forecast": "DP Fcst (Simulated)",
                    "Reason": "Reason",
                    "Action": "Action",
                    "Owner": "Owner",
                }
                detail = actionable[[c for c in detail_cols if c in actionable.columns]].copy()
                detail.rename(columns=detail_cols, inplace=True)
                detail.to_excel(writer, sheet_name=date_str, index=False)

                # By owner
                for owner, group in actionable.groupby("Owner"):
                    sheet_name = owner[:31].replace("/", "_")
                    group.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"\nExported: {out_path}")

    # Export full error list as CSV
    csv_out = os.path.join(output_dir, f"DFV_errors_{date_str}.csv")
    errors.to_csv(csv_out, index=False)
    print(f"Exported: {csv_out}")


def run_pipeline(csv_path=None):
    """Run the full analysis pipeline."""
    # If no CSV provided, use latest in output
    if csv_path is None:
        csvs = sorted(Path(OUTPUT_DIR).glob("DFV_2*.csv"), reverse=True)
        if csvs:
            csv_path = str(csvs[0])
            print(f"Using latest CSV: {csv_path}")
        else:
            print("No CSV found in output/. Run SAP refresh first.")
            return

    # Load
    df = load_data(csv_path)

    # Classify
    errors = classify_issues(df)

    # Summary
    summary = generate_summary(df, errors)

    # Owner reports
    reports = generate_owner_report(errors)

    # Export
    export_results(errors, summary, OUTPUT_DIR)

    # Save to history DB + generate dashboard
    try:
        from history import save_run
        from dashboard import generate_dashboard
        run_id = save_run(summary, errors)
        generate_dashboard()
    except Exception as e:
        print(f"Warning: dashboard generation failed: {e}")

    return df, errors, summary, reports


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DFV Analysis Pipeline")
    parser.add_argument("--csv", help="Path to CSV file (otherwise uses latest)")
    parser.add_argument("--watch", action="store_true", help="Watch for READY.flag")
    args = parser.parse_args()

    if args.watch:
        csv_path = watch_for_ready()
        if csv_path:
            run_pipeline(csv_path)
    elif args.csv:
        run_pipeline(args.csv)
    else:
        # Use baseline data for testing
        baseline = os.path.join(os.path.dirname(OUTPUT_DIR), "baseline_main_data.csv")
        if os.path.exists(baseline):
            run_pipeline(baseline)
        else:
            run_pipeline()
