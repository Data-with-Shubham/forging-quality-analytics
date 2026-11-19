"""Compute KPIs from the warehouse and export CSVs for Power BI.
Includes process capability (Cp / Cpk) per part from raw measurements."""
import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL, REPORTS_DIR

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL)


def process_capability() -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT l.part_code, m.critical_dim_mm, p.dim_lsl_mm AS lsl, p.dim_usl_mm AS usl
        FROM fact_measurement m
        JOIN fact_lot_inspection l ON l.lot_id = m.lot_id
        JOIN dim_part p ON p.part_code = l.part_code""", engine)
    rows = []
    for part, g in df.groupby("part_code"):
        mu, sigma = g.critical_dim_mm.mean(), g.critical_dim_mm.std(ddof=1)
        lsl, usl = g.lsl.iloc[0], g.usl.iloc[0]
        cp = (usl - lsl) / (6 * sigma)
        cpk = min(usl - mu, mu - lsl) / (3 * sigma)
        rows.append({"part_code": part, "samples": len(g), "mean_mm": round(mu, 4),
                     "std_mm": round(sigma, 4), "Cp": round(cp, 2), "Cpk": round(cpk, 2),
                     "status": "Capable (>=1.33)" if cpk >= 1.33 else "Marginal (1.0-1.33)" if cpk >= 1.0 else "Not capable (<1.0)"})
    return pd.DataFrame(rows)


def main():
    q = lambda sql: pd.read_sql(sql, engine)

    kpi = {
        "kpi_monthly_rejection": q("""
            SELECT d.year, d.month, d.month_name, SUM(f.inspected_qty) AS inspected, SUM(f.rejected_qty) AS rejected,
                   ROUND(100.0*SUM(f.rejected_qty)/SUM(f.inspected_qty),2) AS rejection_pct
            FROM fact_lot_inspection f JOIN dim_date d ON d.date_key=f.date_key
            GROUP BY d.year, d.month, d.month_name ORDER BY d.year, d.month"""),
        "kpi_defect_pareto": q("""
            SELECT r.defect_type, t.defect_category, SUM(r.qty) AS qty
            FROM fact_rejection r JOIN dim_defect_type t ON t.defect_type=r.defect_type
            GROUP BY r.defect_type, t.defect_category ORDER BY qty DESC"""),
        "kpi_die_life": q("""
            SELECT f.die_id, dd.die_life_limit_strokes, MAX(f.die_strokes_at_lot) AS strokes_done,
                   ROUND(100.0*MAX(f.die_strokes_at_lot)/dd.die_life_limit_strokes,1) AS die_life_used_pct,
                   ROUND(100.0*SUM(f.rejected_qty)/SUM(f.inspected_qty),2) AS rejection_pct
            FROM fact_lot_inspection f JOIN dim_die dd ON dd.die_id=f.die_id
            GROUP BY f.die_id, dd.die_life_limit_strokes ORDER BY rejection_pct DESC"""),
        "kpi_machine_shift": q("""
            SELECT machine_id, shift, SUM(inspected_qty) AS inspected, SUM(rejected_qty) AS rejected,
                   ROUND(100.0*SUM(rejected_qty)/SUM(inspected_qty),2) AS rejection_pct
            FROM fact_lot_inspection GROUP BY machine_id, shift ORDER BY machine_id, shift"""),
        "kpi_process_capability": process_capability(),
    }
    for name, df in kpi.items():
        df.to_csv(REPORTS_DIR / f"{name}.csv", index=False)
        print(f"\n=== {name} ===\n{df.head(8).to_string(index=False)}")


if __name__ == "__main__":
    main()
