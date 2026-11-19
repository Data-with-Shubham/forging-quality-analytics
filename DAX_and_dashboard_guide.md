# Power BI Guide

## 1. Connect
Get Data -> Text/CSV (or PostgreSQL) and load either:
- the warehouse tables: `fact_lot_inspection`, `fact_rejection`, `fact_measurement`, `dim_*`
- or the ready-made CSVs in `/reports` (`kpi_*.csv`) for a quick start.

## 2. Model (star schema)
Create these relationships (many-to-one, single direction):
- `fact_lot_inspection[date_key]` -> `dim_date[date_key]`
- `fact_lot_inspection[part_code]` -> `dim_part[part_code]`
- `fact_lot_inspection[die_id]` -> `dim_die[die_id]`
- `fact_lot_inspection[machine_id]` -> `dim_machine[machine_id]`
- `fact_lot_inspection[shift]` -> `dim_shift[shift]`
- `fact_rejection[lot_id]` -> `fact_lot_inspection[lot_id]`
- `fact_rejection[defect_type]` -> `dim_defect_type[defect_type]`

## 3. DAX measures
```DAX
Inspected Qty = SUM ( fact_lot_inspection[inspected_qty] )
Rejected Qty  = SUM ( fact_lot_inspection[rejected_qty] )

Rejection % =
DIVIDE ( [Rejected Qty], [Inspected Qty], 0 )

First Pass Yield % =
1 - [Rejection %]

Rejection % Target = 0.03

Variance vs Target =
[Rejection %] - [Rejection % Target]

Rejection % MoM =
VAR _prev = CALCULATE ( [Rejection %], DATEADD ( dim_date[full_date], -1, MONTH ) )
RETURN [Rejection %] - _prev

Defect Qty = SUM ( fact_rejection[qty] )

-- Pareto cumulative % (put dim_defect_type[defect_type] on the axis)
Cumulative Defect % =
VAR _cur = [Defect Qty]
VAR _tbl = ALL ( dim_defect_type[defect_type] )
VAR _run =
    SUMX (
        FILTER ( _tbl, [Defect Qty] >= _cur ),
        [Defect Qty]
    )
RETURN DIVIDE ( _run, CALCULATE ( [Defect Qty], ALL ( dim_defect_type ) ) )

Die Life Used % =
DIVIDE (
    MAX ( fact_lot_inspection[die_strokes_at_lot] ),
    MAX ( dim_die[die_life_limit_strokes] )
)

Lots Out of Hardness Spec =
COUNTROWS (
    FILTER (
        fact_lot_inspection,
        VAR _p = RELATED ( dim_part[hardness_min_hrc] )
        VAR _x = RELATED ( dim_part[hardness_max_hrc] )
        RETURN fact_lot_inspection[hardness_hrc] < _p || fact_lot_inspection[hardness_hrc] > _x
    )
)
```

## 4. Suggested pages
**Page 1 - Executive KPIs:** cards (Rejection %, First Pass Yield %, Inspected Qty, Lots Out of Hardness Spec), monthly rejection trend line with target line, rejection % by part (bar).

**Page 2 - Defect RCA:** Pareto (bars = Defect Qty, line = Cumulative Defect %), defect by machine x shift matrix with conditional formatting, drill-through to lot level.

**Page 3 - Die & Process:** scatter of Die Life Used % vs Rejection % (the key RCA insight), Cp/Cpk table from `kpi_process_capability.csv` with red/amber/green rules (Cpk < 1.0 red, 1.0-1.33 amber, >= 1.33 green).

## 5. Power Query tips
- Set `production_date` to Date type; `shift`, `machine_id`, `die_id` to Text.
- Remove nothing manually: bad records are already quarantined by the Python pipeline.
