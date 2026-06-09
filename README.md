# HairCare DFV Tool

**Demand Flow Verification** — One-click SAP AO automation for weekly DFV process.

## What it does

Automates the full DFV workflow in ~90 seconds (vs 15-30 min manual):

1. Opens SAP Analysis for Office workbook
2. Waits for AO Add-In to load
3. Clicks Refresh All (triggers Prompts dialog)
4. Fills Region / Category / Calendar Week in Prompts
5. Waits for BW data to load
6. Exports data to CSV via COM bulk read
7. Runs pipeline: filter → classify errors → generate KPI → export Excel → update Dashboard

## Output

| File | Description |
|------|-------------|
| `DFV_actions_YYYYMMDD.xlsx` | Excel report (KPI summary + error details by Owner) |
| `DFV_Dashboard.html` | Interactive trend dashboard (open in browser) |
| `DFV_errors_YYYYMMDD.csv` | All errors including HKTW |
| `DFV_YYYYMMDD_HHMMSS.csv` | Raw SAP export data |

## KPI Targets

- **18 Months Volume Difference**: < 2%
- **13 Weeks SKU Difference**: 0 errors

## Prerequisites

- Windows 10/11
- SAP Analysis for Office (AO) installed with SSO
- Python 3.10+ (recommended 3.13)
- Display scale = 100%

## Quick Start

```bash
pip install -r requirements.txt
python dfv_tool/run.py
```

## One-Click Launch (Windows)

Double-click `start_dfv.bat` in the project root.

What it does:
- Validates/rebuilds `.venv` if needed
- Installs dependencies from `requirements.txt`
- Runs full DFV automation (`dfv_tool/run.py`)
- Falls back to `dfv_tool/pipeline.py` if AO prompt flow fails
- Opens `output/DFV_Dashboard.html` automatically

## Configuration

Edit `dfv_tool/config.py`:
- `REGION` — SAP Region MR (default: "XA")
- `CATEGORY` — Category M (default: "HAIRCARE")
- `DRP_LOCATIONS` — List of DC codes to filter
- `WORKBOOK_PATH` — Path to the AO .xlsm file

## Project Structure

```
dfv_tool/
  run.py        — Main entry point (7-step automation)
  config.py     — Configuration (filters, paths, column mapping)
  pipeline.py   — Data pipeline (classify, KPI, export, history)
  history.py    — SQLite storage for weekly results
  dashboard.py  — Dashboard HTML generator
```

## Documentation

Open `DFV_Manual.html` in a browser for the full user manual (Chinese + English).

## Important Notes

- **Do not move mouse** during execution (Steps 1-4 use physical clicks)
- **Never call SAP XLL functions** from Python COM — it breaks the AO ribbon permanently
- Prompts dialog uses coordinate-based input (WPF controls, no UIA access to input fields)
