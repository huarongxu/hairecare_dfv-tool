"""
DFV Tool Configuration
SAP BW connection parameters and filter criteria
"""
import os
from datetime import datetime, timedelta

# ============================================================
# SAP System Configuration (from KHP AO workbook)
# ============================================================
SAP_SYSTEM = {
    "system_id": "KHP",
    "system_name": "KHP APO-DRP Production -SSO",
    "message_server": "KHP.na.pg.com",
    "message_server_service": "03600",
    "server_group": "KHPGROUP",
    "client": "001",
    "language": "EN",
    "snc_partner": "p/secude:CN=KHP, O=PG, C=US",
    "snc_qop": "9",
}

# BW Query
BW_QUERY = "ZCMFCSTERRCHECK"  # Forecast Flow Validation Report
DATA_PROVIDER = "DP_4"

# ============================================================
# Filter Criteria
# ============================================================
REGION = "XA"
CATEGORY = "HAIRCARE"

# DRP Locations (DCs)
DRP_LOCATIONS = [
    "A672", "A716", "A715", "A673", "A680",
    "C810", "C816", "A668", "D352", "C719",
    "C819", "D774", "C563", "C731", "C937",
    "D191", "D767", "D901", "E295", "E496",
    "E467", "E474", "5740", "E230", "D594",
]

# Calendar Week: current week + 18 months (~78 weeks)
CALENDAR_WEEK_LOOKAHEAD_MONTHS = 18


def get_calendar_week_range():
    """Calculate calendar week range: current week to +18 months"""
    today = datetime.now()
    cal = today.isocalendar()
    start_week = f"{cal[1]:02d}/{cal[0]}"

    end_date = today + timedelta(days=CALENDAR_WEEK_LOOKAHEAD_MONTHS * 30)
    end_cal = end_date.isocalendar()
    end_week = f"{end_cal[1]:02d}/{end_cal[0]}"

    return start_week, end_week


# ============================================================
# BW Query Variable Mapping
# ============================================================
# Variable technical name -> filter value
QUERY_VARIABLES = {
    "ZCREGNMR": REGION,           # Region - MR
    "ZCCAT_M": CATEGORY,          # Category - M
    "ZCLOCNOM": DRP_LOCATIONS,    # DRP Location - M (multiple values)
    # ZCUR78 is set dynamically via get_calendar_week_range()
}

# ============================================================
# AO Workbook Path
# ============================================================
WORKBOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "DRP Forecast Flow Validation AO (20251021) - KHP.xlsm"
)

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# ============================================================
# Column Mapping (Main sheet, row 21 = headers, row 22+ = data)
# ============================================================
COLUMNS = {
    "File_ID": 0,        # A: File ID (XADRPDSO, XARTFAPO, XAGDFAPO)
    "APO_Product": 1,    # B: APO Product (material number)
    "Description": 2,    # C: Material description
    "Category": 3,       # D: Category
    "Brand": 4,          # E: Brand
    "APO_Location": 5,   # F: APO Location (DC code)
    "SNP_Planner": 6,    # G: SNP Planner
    "Error_Message": 7,  # H: Error Message
    "IDP_Forecast": 8,   # I: IDP Forecast (BW Demand Hub)
    "APO_Forecast": 9,   # J: DP Fcst (Simulated) (APO-DRP)
}

# Error types
ERROR_TYPES = {
    "Successful": "OK",
    "Missing Mat/Loc": "Master data or code activation missing",
    "Matloc Deleted": "Material/location deleted but still has forecast",
    "No SNP Assigned": "DRP master data incomplete - no SNP planner",
    "SNP equals *99": "Code turned off in APO but still has forecast",
    "Under Deletion": "Material under deletion process",
}

# ============================================================
# Owner Mapping
# ============================================================
# Default owner by error type (used during pipeline run)
OWNER_MAPPING = {
    "Missing Mat/Loc": "DRP Planner / IOL",
    "Matloc Deleted": "DP Planner",
    "No SNP Assigned": "DRP Planner",
    "SNP equals *99": "DRP Planner",
    "Under Deletion": "DP Planner",
}

# Fixed owners - override by error type with specific names
# Applied AFTER OWNER_MAPPING during classify_issues
FIXED_OWNERS = {
    "No SNP Assigned": "GC DRP",
    "SNP equals *99": "GC DRP",
}

# Location-based owner overrides (applied after error-type mapping)
# These override the owner for specific DC locations
LOCATION_OWNERS = {
    "C937": "Wu Wen hao",
    "D594": "Wu Wen hao",
    "D767": "Wu Wen hao",
}

# IOL Owner assignment (for "Missing Mat/Loc" items only)
# Priority: Description contains "+" → Lucy, then by Brand
IOL_BRAND_OWNERS = {
    "HAIRRECIPE": "Guimin",
    "REJOICE": "Rebecca",
    "PANTENE": "Xueying",
    "HD&SHLDRS": "Becky",
}
IOL_PLUS_OWNER = "Lucy"  # Description contains "+"

# Additional HKTW locations (not in scope, owner = blank)
# 5740 is always HKTW; add more here
HKTW_LOCATIONS = {"5740", "E230"}
