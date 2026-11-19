"""Extract -> Validate -> Transform -> Load (full refresh, idempotent)."""
import logging
import pandas as pd
from sqlalchemy import create_engine, text

from config import RAW_DIR, PROCESSED_DIR, SQL_DIR, DATABASE_URL
from validate import validate_lots, validate_measurements, validate_rejections

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("forging_etl")

DEFECT_CATEGORY = {
    "Lap": "Process", "Crack": "Material", "Underfill": "Process",
    "Dimensional": "Tooling", "Scale Pit": "Process", "Die Wear Mark": "Tooling",
}
SHIFT_NAME = {"A": "Morning", "B": "Afternoon", "C": "Night"}


def extract():
    r = lambda f: pd.read_csv(RAW_DIR / f)
    return (r("lot_inspection.csv"), r("rejection_details.csv"), r("dimension_measurements.csv"),
            r("master_parts.csv"), r("master_dies.csv"), r("master_machines.csv"))


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    d = pd.to_datetime(dates).drop_duplicates().sort_values()
    return pd.DataFrame({
        "date_key": d.dt.strftime("%Y%m%d").astype(int),
        "full_date": d.dt.date,
        "year": d.dt.year, "month": d.dt.month, "month_name": d.dt.strftime("%b"),
        "week_of_year": d.dt.isocalendar().week.astype(int),
    })


def run_schema(engine):
    ddl = (SQL_DIR / "schema.sql").read_text()
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    lots, rej, meas, parts, dies, machines = extract()
    log.info("Extracted: lots=%d rejections=%d measurements=%d", len(lots), len(rej), len(meas))

    # ---- validate ----
    lots_ok, lots_bad = validate_lots(lots, parts, dies, machines)
    meas_ok, meas_bad = validate_measurements(meas, set(lots_ok.lot_id))
    rej_ok, rej_bad = validate_rejections(rej, set(lots_ok.lot_id))
    for name, bad in [("lots", lots_bad), ("measurements", meas_bad), ("rejections", rej_bad)]:
        bad.to_csv(PROCESSED_DIR / f"quarantine_{name}.csv", index=False)
    log.info("Quarantined: lots=%d measurements=%d rejections=%d", len(lots_bad), len(meas_bad), len(rej_bad))
    log.info("Quarantine reasons (lots):\n%s", lots_bad["reject_reason"].value_counts().to_string())

    # ---- transform ----
    lots_ok = lots_ok.copy()
    lots_ok["date_key"] = pd.to_datetime(lots_ok["production_date"]).dt.strftime("%Y%m%d").astype(int)
    fact_lot = lots_ok[["lot_id", "date_key", "shift", "machine_id", "part_code", "die_id",
                        "die_strokes_at_lot", "produced_qty", "inspected_qty", "rejected_qty", "hardness_hrc"]]
    dim_date = build_dim_date(lots_ok["production_date"])
    dim_shift = pd.DataFrame({"shift": list(SHIFT_NAME), "shift_name": list(SHIFT_NAME.values())})
    dim_defect = pd.DataFrame({"defect_type": list(DEFECT_CATEGORY), "defect_category": list(DEFECT_CATEGORY.values())})

    # ---- load ----
    engine = create_engine(DATABASE_URL)
    run_schema(engine)
    load = lambda df, t: df.to_sql(t, engine, if_exists="append", index=False, chunksize=500)
    load(parts, "dim_part"); load(machines, "dim_machine"); load(dies, "dim_die")
    load(dim_date, "dim_date"); load(dim_shift, "dim_shift"); load(dim_defect, "dim_defect_type")
    load(fact_lot, "fact_lot_inspection"); load(rej_ok, "fact_rejection"); load(meas_ok, "fact_measurement")
    log.info("Loaded %d lots, %d rejection rows, %d measurements into %s",
             len(fact_lot), len(rej_ok), len(meas_ok), engine.url.render_as_string(hide_password=True))

    # ---- data quality summary ----
    summary = pd.DataFrame([{
        "run_ts": pd.Timestamp.now().isoformat(timespec="seconds"),
        "lots_received": len(lots), "lots_loaded": len(fact_lot), "lots_quarantined": len(lots_bad),
        "pass_rate_pct": round(100 * len(fact_lot) / len(lots), 2),
    }])
    summary.to_csv(PROCESSED_DIR / "dq_summary.csv", index=False)
    log.info("DQ summary: %s", summary.iloc[0].to_dict())


if __name__ == "__main__":
    main()
