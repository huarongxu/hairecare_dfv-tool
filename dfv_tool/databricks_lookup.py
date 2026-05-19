"""
Databricks SKU description lookup.
Enriches error rows that have code-like descriptions (Description == APO_Product)
by querying ps_psc_sku_master in Databricks.
"""
import os
from dotenv import load_dotenv

# Load .env from same directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

_QUERY = """
SELECT material_num, product_name_en
FROM cdl_ps_hana_prd.sl.ps_psc_sku_master
WHERE material_num IN ({placeholders})
"""


def fetch_descriptions(material_nums):
    """
    Query Databricks for product descriptions.

    Args:
        material_nums: list of material number strings (e.g. ["83930677", "83930678"])

    Returns:
        dict of {material_num: product_name_en}
    """
    if not material_nums:
        return {}

    if not all([DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN]):
        print("WARNING: Databricks credentials not configured in .env, skipping description lookup")
        return {}

    from databricks import sql as dbsql

    placeholders = ", ".join(["?" for _ in material_nums])
    query = _QUERY.format(placeholders=placeholders)

    try:
        with dbsql.connect(
            server_hostname=DATABRICKS_HOST,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_TOKEN,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, material_nums)
                rows = cursor.fetchall()
                result = {}
                for row in rows:
                    mat_num = str(row[0]).strip()
                    desc = str(row[1]).strip() if row[1] else ""
                    if desc:
                        result[mat_num] = desc
                print(f"  Databricks: fetched {len(result)} descriptions for {len(material_nums)} SKUs")
                return result
    except Exception as e:
        print(f"WARNING: Databricks query failed: {e}")
        return {}


def enrich_descriptions(errors_df):
    """
    For error rows where Description == APO_Product (code-like),
    look up real descriptions from Databricks and update in-place.

    Args:
        errors_df: DataFrame with APO_Product and Description columns

    Returns:
        errors_df (modified in-place), dict of {material_num: description} fetched
    """
    if errors_df.empty:
        return errors_df, {}

    # Find rows where description is just the material number
    code_mask = errors_df["Description"].astype(str).str.strip() == errors_df["APO_Product"].astype(str).str.strip()
    code_skus = errors_df.loc[code_mask, "APO_Product"].astype(str).unique().tolist()

    if not code_skus:
        return errors_df, {}

    print(f"\n  {len(code_skus)} SKUs with code-like descriptions, querying Databricks...")
    desc_map = fetch_descriptions(code_skus)

    if desc_map:
        for mat_num, desc in desc_map.items():
            mask = errors_df["APO_Product"].astype(str) == mat_num
            errors_df.loc[mask, "Description"] = desc

    # Report any still-missing
    still_missing = [s for s in code_skus if s not in desc_map]
    if still_missing:
        print(f"  WARNING: {len(still_missing)} SKUs not found in Databricks: {still_missing[:5]}...")

    return errors_df, desc_map
