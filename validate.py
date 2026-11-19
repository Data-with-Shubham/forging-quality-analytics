"""Data validation layer. Each rule returns a boolean 'bad' mask plus a reason.
Bad rows go to quarantine (data/processed/quarantine_*.csv) instead of the warehouse."""
import pandas as pd


def validate_lots(lots: pd.DataFrame, parts: pd.DataFrame, dies: pd.DataFrame, machines: pd.DataFrame):
    lots = lots.copy()
    lots["reject_reason"] = ""

    def flag(mask, reason):
        lots.loc[mask, "reject_reason"] = lots.loc[mask, "reject_reason"].where(
            lots.loc[mask, "reject_reason"] == "", lots.loc[mask, "reject_reason"] + "; "
        ) + reason

    # 1. duplicates (keep first)
    flag(lots.duplicated("lot_id", keep="first"), "duplicate lot_id")
    # 2. mandatory fields
    for col in ["lot_id", "production_date", "shift", "machine_id", "part_code", "die_id"]:
        flag(lots[col].isna(), f"missing {col}")
    # 3. quantities
    for col in ["produced_qty", "inspected_qty", "rejected_qty"]:
        flag(lots[col].isna() | (lots[col] < 0), f"invalid {col}")
    flag(lots["inspected_qty"] > lots["produced_qty"], "inspected > produced")
    flag(lots["rejected_qty"] > lots["inspected_qty"], "rejected > inspected")
    # 4. referential integrity against master data
    flag(~lots["part_code"].isin(parts["part_code"]) & lots["part_code"].notna(), "unknown part_code")
    flag(~lots["die_id"].isin(dies["die_id"]) & lots["die_id"].notna(), "unknown die_id")
    flag(~lots["machine_id"].isin(machines["machine_id"]) & lots["machine_id"].notna(), "unknown machine_id")
    # 5. hardness within a physically sensible window (0-70 HRC)
    flag(lots["hardness_hrc"].notna() & ~lots["hardness_hrc"].between(0, 70), "hardness out of range")
    # 6. dates parse
    flag(pd.to_datetime(lots["production_date"], errors="coerce").isna(), "bad production_date")

    bad = lots["reject_reason"] != ""
    return lots[~bad].drop(columns="reject_reason"), lots[bad]


def validate_measurements(meas: pd.DataFrame, valid_lot_ids):
    meas = meas.copy()
    bad = meas["critical_dim_mm"].isna() | ~meas["lot_id"].isin(valid_lot_ids)
    meas["reject_reason"] = ""
    meas.loc[meas["critical_dim_mm"].isna(), "reject_reason"] = "missing measurement"
    meas.loc[~meas["lot_id"].isin(valid_lot_ids), "reject_reason"] = "lot not in clean lots"
    return meas[~bad].drop(columns="reject_reason"), meas[bad]


def validate_rejections(rej: pd.DataFrame, valid_lot_ids):
    ok = rej["lot_id"].isin(valid_lot_ids) & (rej["qty"] > 0)
    return rej[ok], rej[~ok]
