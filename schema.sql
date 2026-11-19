-- Star schema for forging quality (works on SQLite and PostgreSQL)
DROP TABLE IF EXISTS fact_measurement;
DROP TABLE IF EXISTS fact_rejection;
DROP TABLE IF EXISTS fact_lot_inspection;
DROP TABLE IF EXISTS dim_defect_type;
DROP TABLE IF EXISTS dim_shift;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_die;
DROP TABLE IF EXISTS dim_machine;
DROP TABLE IF EXISTS dim_part;

CREATE TABLE dim_part (
    part_code VARCHAR(20) PRIMARY KEY,
    part_name VARCHAR(80),
    material VARCHAR(30),
    dim_nominal_mm NUMERIC(8,3),
    dim_lsl_mm NUMERIC(8,3),
    dim_usl_mm NUMERIC(8,3),
    hardness_min_hrc NUMERIC(5,1),
    hardness_max_hrc NUMERIC(5,1)
);

CREATE TABLE dim_machine (
    machine_id VARCHAR(20) PRIMARY KEY,
    machine_type VARCHAR(60)
);

CREATE TABLE dim_die (
    die_id VARCHAR(20) PRIMARY KEY,
    part_code VARCHAR(20) REFERENCES dim_part(part_code),
    die_life_limit_strokes INTEGER
);

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,   -- YYYYMMDD
    full_date DATE,
    year INTEGER,
    month INTEGER,
    month_name VARCHAR(12),
    week_of_year INTEGER
);

CREATE TABLE dim_shift (
    shift VARCHAR(2) PRIMARY KEY,
    shift_name VARCHAR(20)
);

CREATE TABLE dim_defect_type (
    defect_type VARCHAR(40) PRIMARY KEY,
    defect_category VARCHAR(30)     -- Process / Material / Tooling
);

CREATE TABLE fact_lot_inspection (
    lot_id VARCHAR(20) PRIMARY KEY,
    date_key INTEGER REFERENCES dim_date(date_key),
    shift VARCHAR(2) REFERENCES dim_shift(shift),
    machine_id VARCHAR(20) REFERENCES dim_machine(machine_id),
    part_code VARCHAR(20) REFERENCES dim_part(part_code),
    die_id VARCHAR(20) REFERENCES dim_die(die_id),
    die_strokes_at_lot INTEGER,
    produced_qty INTEGER,
    inspected_qty INTEGER,
    rejected_qty INTEGER,
    hardness_hrc NUMERIC(5,1)
);

CREATE TABLE fact_rejection (
    lot_id VARCHAR(20) REFERENCES fact_lot_inspection(lot_id),
    defect_type VARCHAR(40) REFERENCES dim_defect_type(defect_type),
    qty INTEGER
);

CREATE TABLE fact_measurement (
    lot_id VARCHAR(20) REFERENCES fact_lot_inspection(lot_id),
    sample_no INTEGER,
    critical_dim_mm NUMERIC(8,3)
);

CREATE INDEX idx_lot_date ON fact_lot_inspection(date_key);
CREATE INDEX idx_lot_die ON fact_lot_inspection(die_id);
CREATE INDEX idx_lot_machine ON fact_lot_inspection(machine_id);
CREATE INDEX idx_rej_lot ON fact_rejection(lot_id);
CREATE INDEX idx_meas_lot ON fact_measurement(lot_id);
