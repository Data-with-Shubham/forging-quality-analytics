-- 1. Overall rejection % (monthly trend)
SELECT d.year, d.month, d.month_name,
       SUM(f.inspected_qty) AS inspected,
       SUM(f.rejected_qty)  AS rejected,
       ROUND(100.0 * SUM(f.rejected_qty) / SUM(f.inspected_qty), 2) AS rejection_pct
FROM fact_lot_inspection f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- 2. Defect Pareto (count + cumulative %)
WITH defect AS (
    SELECT defect_type, SUM(qty) AS qty FROM fact_rejection GROUP BY defect_type
)
SELECT defect_type, qty,
       ROUND(100.0 * qty / SUM(qty) OVER (), 2) AS pct,
       ROUND(100.0 * SUM(qty) OVER (ORDER BY qty DESC) / SUM(qty) OVER (), 2) AS cumulative_pct
FROM defect
ORDER BY qty DESC;

-- 3. Rejection % by die, with die-life consumed (die-wear RCA)
SELECT f.die_id, dd.die_life_limit_strokes,
       MAX(f.die_strokes_at_lot) AS strokes_done,
       ROUND(100.0 * MAX(f.die_strokes_at_lot) / dd.die_life_limit_strokes, 1) AS die_life_used_pct,
       ROUND(100.0 * SUM(f.rejected_qty) / SUM(f.inspected_qty), 2) AS rejection_pct
FROM fact_lot_inspection f
JOIN dim_die dd ON dd.die_id = f.die_id
GROUP BY f.die_id, dd.die_life_limit_strokes
ORDER BY rejection_pct DESC;

-- 4. Rejection % by die-life band (does rejection rise as the die ages?)
SELECT CASE
         WHEN 100.0 * f.die_strokes_at_lot / dd.die_life_limit_strokes < 25 THEN '0-25%'
         WHEN 100.0 * f.die_strokes_at_lot / dd.die_life_limit_strokes < 50 THEN '25-50%'
         WHEN 100.0 * f.die_strokes_at_lot / dd.die_life_limit_strokes < 75 THEN '50-75%'
         ELSE '75%+' END AS die_life_band,
       ROUND(100.0 * SUM(f.rejected_qty) / SUM(f.inspected_qty), 2) AS rejection_pct,
       COUNT(*) AS lots
FROM fact_lot_inspection f
JOIN dim_die dd ON dd.die_id = f.die_id
GROUP BY 1
ORDER BY 1;

-- 5. Shift x machine rejection matrix
SELECT f.machine_id, f.shift,
       ROUND(100.0 * SUM(f.rejected_qty) / SUM(f.inspected_qty), 2) AS rejection_pct
FROM fact_lot_inspection f
GROUP BY f.machine_id, f.shift
ORDER BY f.machine_id, f.shift;

-- 6. First-pass yield by part
SELECT p.part_code, p.part_name,
       ROUND(100.0 * (1 - 1.0 * SUM(f.rejected_qty) / SUM(f.inspected_qty)), 2) AS first_pass_yield_pct
FROM fact_lot_inspection f
JOIN dim_part p ON p.part_code = f.part_code
GROUP BY p.part_code, p.part_name
ORDER BY first_pass_yield_pct;

-- 7. Lots with hardness outside spec
SELECT f.lot_id, f.part_code, f.hardness_hrc, p.hardness_min_hrc, p.hardness_max_hrc
FROM fact_lot_inspection f
JOIN dim_part p ON p.part_code = f.part_code
WHERE f.hardness_hrc < p.hardness_min_hrc OR f.hardness_hrc > p.hardness_max_hrc
ORDER BY f.lot_id;
