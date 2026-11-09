"""Helper: generates powerbi/powerbi_export_query.dax from the slice lists in 01_reconcile_measures.py,
so the Power BI export and the pandas side always cover exactly the same 91 rows."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rec", HERE / "01_reconcile_measures.py")
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)


def val(m):
    if m in rec.TEXT:
        return f"[{m}]"
    # FORMAT strips the measure's display format so the value is copied unrounded
    return f'VAR v = [{m}] RETURN IF ( ISBLANK ( v ), BLANK (), FORMAT ( v, "0.0000000000" ) )'


parts = []
for m in rec.TOTAL_MEASURES:
    parts.append(f'    ROW ( "measure", "{m}", "slice", "Total", "value", {val(m)} )')
for m in rec.YEAR_MEASURES:
    parts.append(
        f'    SELECTCOLUMNS ( VALUES ( dim_date[year] ), "measure", "{m}", '
        f'"slice", "Year=" & dim_date[year], "value", {val(m)} )')
for m in rec.TIER_MEASURES:
    parts.append(
        f'    CALCULATETABLE ( SELECTCOLUMNS ( VALUES ( dim_client[client_tier] ), "measure", "{m}", '
        f'"slice", "Tier=" & dim_client[client_tier] & "|2024", "value", {val(m)} ), dim_date[year] = 2024 )')
for m in rec.MONTH_MEASURES:
    parts.append(
        f'    CALCULATETABLE ( ROW ( "measure", "{m}", "slice", "Month=2024-12", "value", {val(m)} ), '
        f'dim_date[year] = 2024, dim_date[month] = 12 )')

query = (
    "// HW6 - export every reconciliation value in one go (DAX query view -> paste -> Run)\n"
    "// Then: Copy the result grid (with headers) and paste it into reports/powerbi_values.csv\n"
    "EVALUATE\nUNION (\n" + ",\n".join(parts) + "\n)\nORDER BY [slice], [measure]\n"
)
target = HERE.parent / "powerbi" / "powerbi_export_query.dax"
target.parent.mkdir(exist_ok=True)
target.write_text(query, encoding="utf-8")
print(f"{len(parts)} blocks -> {target}")
