-- =============================================================================
-- FRED Economic Pipeline -- Sample Athena Queries
-- Table: fred_processed_db.fred_processed_nkohlway_2026
-- All queries use Parquet columnar format for efficient scanning
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Preview the data
--    Quick sanity check -- verify all 4 series landed correctly
-- -----------------------------------------------------------------------------
SELECT
    series_id,
    series_label,
    COUNT(*)        AS observation_count,
    MIN(date)       AS earliest_date,
    MAX(date)       AS latest_date
FROM fred_processed_db.fred_processed_nkohlway_2026
GROUP BY series_id, series_label
ORDER BY series_id;


-- -----------------------------------------------------------------------------
-- 2. Latest value for each series
--    Shows the most recent observation across all 4 economic indicators
-- -----------------------------------------------------------------------------
SELECT
    series_id,
    series_label,
    date,
    value
FROM fred_processed_db.fred_processed_nkohlway_2026
WHERE (series_id, date) IN (
    SELECT series_id, MAX(date)
    FROM fred_processed_db.fred_processed_nkohlway_2026
    GROUP BY series_id
)
ORDER BY series_id;


-- -----------------------------------------------------------------------------
-- 3. 30-year mortgage rate trend (last 5 years)
--    Useful for investment and acquisition timing analysis
-- -----------------------------------------------------------------------------
SELECT
    date,
    value AS mortgage_rate_pct
FROM fred_processed_db.fred_processed_nkohlway_2026
WHERE series_id = 'MORTGAGE30US'
  AND date >= DATE_FORMAT(DATE_ADD('year', -5, CURRENT_DATE), '%Y-%m-%d')
ORDER BY date;


-- -----------------------------------------------------------------------------
-- 4. CPI year-over-year change (inflation proxy)
--    Compares each month's CPI to the same month one year prior
-- -----------------------------------------------------------------------------
WITH cpi AS (
    SELECT
        date,
        value AS cpi_value
    FROM fred_processed_db.fred_processed_nkohlway_2026
    WHERE series_id = 'CPIAUCSL'
),
cpi_lagged AS (
    SELECT
        c.date,
        c.cpi_value,
        LAG(c.cpi_value, 12) OVER (ORDER BY c.date) AS cpi_prior_year
    FROM cpi c
)
SELECT
    date,
    cpi_value,
    cpi_prior_year,
    ROUND(((cpi_value - cpi_prior_year) / cpi_prior_year) * 100, 2) AS yoy_inflation_pct
FROM cpi_lagged
WHERE cpi_prior_year IS NOT NULL
ORDER BY date DESC
LIMIT 24;


-- -----------------------------------------------------------------------------
-- 5. Unemployment vs housing starts correlation view
--    Side-by-side monthly comparison to spot macro relationships
-- -----------------------------------------------------------------------------
SELECT
    u.date,
    u.value     AS unemployment_rate_pct,
    h.value     AS housing_starts_thousands
FROM fred_processed_db.fred_processed_nkohlway_2026 u
JOIN fred_processed_db.fred_processed_nkohlway_2026 h
  ON u.date = h.date
WHERE u.series_id = 'UNRATE'
  AND h.series_id = 'HOUST'
ORDER BY u.date DESC
LIMIT 60;


-- -----------------------------------------------------------------------------
-- 6. Mortgage rate vs housing starts (affordability pressure)
--    Rising rates typically suppress housing starts -- useful for acquisition
--    analysis in real estate markets
-- -----------------------------------------------------------------------------
SELECT
    m.date,
    m.value AS mortgage_rate_pct,
    h.value AS housing_starts_thousands
FROM fred_processed_db.fred_processed_nkohlway_2026 m
JOIN fred_processed_db.fred_processed_nkohlway_2026 h
  ON m.date = h.date
WHERE m.series_id = 'MORTGAGE30US'
  AND h.series_id = 'HOUST'
  AND m.value IS NOT NULL
  AND h.value IS NOT NULL
ORDER BY m.date DESC
LIMIT 60;


-- -----------------------------------------------------------------------------
-- 7. Pipeline audit -- verify ingestion completeness
--    Checks that all 4 series were written in the latest partition
-- -----------------------------------------------------------------------------
SELECT
    year,
    month,
    day,
    COUNT(DISTINCT series_id) AS series_count,
    SUM(COUNT(*)) OVER (PARTITION BY year, month, day) AS total_rows
FROM fred_processed_db.fred_processed_nkohlway_2026
GROUP BY year, month, day
ORDER BY year DESC, month DESC, day DESC
LIMIT 10;
