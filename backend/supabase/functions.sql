-- ══════════════════════════════════════════════════════════════════════
-- PASTE THIS ENTIRE FILE INTO SUPABASE SQL EDITOR AND CLICK RUN
-- Fixes all timeout issues with indexes + optimized functions
-- ══════════════════════════════════════════════════════════════════════

-- ── Increase timeouts ─────────────────────────────────────────────────
ALTER ROLE authenticator SET statement_timeout = '120s';
ALTER ROLE anon SET statement_timeout = '120s';
ALTER ROLE authenticated SET statement_timeout = '120s';

-- ── Indexes (makes all GROUP BY and JOINs fast on 674K rows) ──────────
CREATE INDEX IF NOT EXISTS idx_enc_provider ON encounters("PROVIDER");
CREATE INDEX IF NOT EXISTS idx_enc_org      ON encounters("ORGANIZATION");
CREATE INDEX IF NOT EXISTS idx_enc_start    ON encounters("START");
CREATE INDEX IF NOT EXISTS idx_enc_patient  ON encounters("PATIENT");
CREATE INDEX IF NOT EXISTS idx_enc_stop     ON encounters("STOP");
CREATE INDEX IF NOT EXISTS idx_sup_date     ON supplies(date);
CREATE INDEX IF NOT EXISTS idx_sup_desc     ON supplies(description);
CREATE INDEX IF NOT EXISTS idx_sup_enc      ON supplies(encounter);


-- ── 1. Doctor workload ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_doctor_workload()
RETURNS TABLE(
    doctor              text,
    department          text,
    total_encounters    bigint,
    avg_duration_min    numeric,
    avg_daily_patients  numeric,
    dept_mean           numeric,
    pct_vs_avg          numeric,
    status              text
)
LANGUAGE sql
AS $$
    WITH enc_data AS (
        SELECT
            e."PROVIDER"     AS provider_id,
            e."ORGANIZATION" AS org_id,
            COUNT(*)         AS total_enc,
            AVG(EXTRACT(EPOCH FROM (
                e."STOP"::timestamp - e."START"::timestamp
            )) / 60)         AS avg_min
        FROM encounters e
        GROUP BY e."PROVIDER", e."ORGANIZATION"
    ),
    total_days AS (
        SELECT GREATEST(1,
            EXTRACT(DAY FROM (MAX("START"::timestamp) - MIN("START"::timestamp)))
        ) AS days FROM encounters
    ),
    with_names AS (
        SELECT
            COALESCE(p."NAME", ed.provider_id)          AS doctor,
            COALESCE(o.name,   ed.org_id)               AS department,
            ed.total_enc,
            ROUND(ed.avg_min::numeric, 1)               AS avg_duration_min,
            ROUND((ed.total_enc / td.days)::numeric, 2) AS avg_daily
        FROM enc_data ed
        LEFT JOIN providers     p ON p.id = ed.provider_id
        LEFT JOIN organizations o ON o.id = ed.org_id
        , total_days td
    ),
    with_dept_avg AS (
        SELECT *, AVG(avg_daily) OVER (PARTITION BY department) AS dept_avg
        FROM with_names
    )
    SELECT
        doctor, department,
        total_enc                                                               AS total_encounters,
        avg_duration_min,
        avg_daily                                                               AS avg_daily_patients,
        ROUND(dept_avg::numeric, 2)                                             AS dept_mean,
        ROUND(((avg_daily - dept_avg) / NULLIF(dept_avg,0) * 100)::numeric, 1) AS pct_vs_avg,
        CASE
            WHEN ((avg_daily - dept_avg) / NULLIF(dept_avg,0) * 100) > 20  THEN 'Overloaded'
            WHEN ((avg_daily - dept_avg) / NULLIF(dept_avg,0) * 100) < -20 THEN 'Underutilized'
            ELSE 'Optimal'
        END AS status
    FROM with_dept_avg
    ORDER BY pct_vs_avg DESC;
$$;


-- ── 2. Department performance ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_dept_performance()
RETURNS TABLE(
    department          text,
    avg_encounter_min   numeric,
    throughput_per_day  numeric,
    revisit_rate_pct    numeric,
    efficiency_score    numeric
)
LANGUAGE sql
AS $$
    WITH total_days AS (
        SELECT GREATEST(1,
            EXTRACT(DAY FROM (MAX("START"::timestamp) - MIN("START"::timestamp)))
        ) AS days FROM encounters
    ),
    base AS (
        SELECT
            COALESCE(o.name, e."ORGANIZATION") AS department,
            e."PATIENT",
            e."START"::timestamp               AS start_ts,
            EXTRACT(EPOCH FROM (
                e."STOP"::timestamp - e."START"::timestamp
            )) / 60                            AS duration_min
        FROM encounters e
        LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    ),
    dept_stats AS (
        SELECT
            department,
            ROUND(AVG(duration_min)::numeric, 1)    AS avg_encounter_min,
            ROUND((COUNT(*) / td.days)::numeric, 1) AS throughput_per_day
        FROM base, total_days td
        GROUP BY department, td.days
    ),
    revisits AS (
        SELECT department,
            ROUND(100.0 * SUM(CASE WHEN is_revisit THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1) AS revisit_rate_pct
        FROM (
            SELECT department, "PATIENT", start_ts,
                CASE WHEN start_ts - LAG(start_ts) OVER (
                    PARTITION BY department, "PATIENT" ORDER BY start_ts
                ) <= INTERVAL '30 days' THEN true ELSE false END AS is_revisit
            FROM base
        ) sub
        GROUP BY department
    )
    SELECT
        ds.department, ds.avg_encounter_min, ds.throughput_per_day,
        COALESCE(r.revisit_rate_pct, 0) AS revisit_rate_pct,
        ROUND((
            (ds.throughput_per_day / NULLIF(MAX(ds.throughput_per_day) OVER(), 0) * 40) +
            ((1 - COALESCE(r.revisit_rate_pct,0) / NULLIF(MAX(COALESCE(r.revisit_rate_pct,0)) OVER(), 0)) * 30) +
            30
        )::numeric, 1) AS efficiency_score
    FROM dept_stats ds
    LEFT JOIN revisits r ON r.department = ds.department
    ORDER BY efficiency_score DESC;
$$;


-- ── 3. Supply summary ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_supply_summary()
RETURNS TABLE(
    supply        text,
    total_units   bigint,
    weekly_units  numeric,
    monthly_units numeric
)
LANGUAGE sql
AS $$
    WITH span AS (
        SELECT GREATEST(1, (MAX(date::date) - MIN(date::date)))::numeric AS days
        FROM supplies
    )
    SELECT
        description                                          AS supply,
        SUM(quantity)                                        AS total_units,
        ROUND((SUM(quantity) / s.days * 7)::numeric,  0)    AS weekly_units,
        ROUND((SUM(quantity) / s.days * 30)::numeric, 0)    AS monthly_units
    FROM supplies, span s
    GROUP BY description, s.days
    ORDER BY total_units DESC;
$$;


-- ── 4. Doctor 30-day trend ────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_doctor_trend()
RETURNS TABLE(
    date_val   date,
    doctor     text,
    department text,
    encounters bigint
)
LANGUAGE sql
AS $$
    SELECT
        e."START"::date                      AS date_val,
        COALESCE(p."NAME", e."PROVIDER")     AS doctor,
        COALESCE(o.name,   e."ORGANIZATION") AS department,
        COUNT(*)                             AS encounters
    FROM encounters e
    LEFT JOIN providers     p ON p.id = e."PROVIDER"
    LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    WHERE e."START"::date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY e."START"::date, e."PROVIDER", e."ORGANIZATION", p."NAME", o.name
    ORDER BY date_val;
$$;


-- ── 5. Monthly dept throughput ────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_dept_monthly_trend()
RETURNS TABLE(
    month            date,
    department       text,
    throughput       bigint,
    avg_duration_min numeric
)
LANGUAGE sql
AS $$
    SELECT
        DATE_TRUNC('month', e."START"::timestamp)::date    AS month,
        COALESCE(o.name, e."ORGANIZATION")                 AS department,
        COUNT(*)                                           AS throughput,
        ROUND(AVG(EXTRACT(EPOCH FROM (
            e."STOP"::timestamp - e."START"::timestamp
        )) / 60)::numeric, 1)                              AS avg_duration_min
    FROM encounters e
    LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    WHERE e."START"::timestamp >= NOW() - INTERVAL '12 months'
    GROUP BY DATE_TRUNC('month', e."START"::timestamp), e."ORGANIZATION", o.name
    ORDER BY month, department;
$$;


-- ── 6. Weekly revisit trend ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_revisit_trend()
RETURNS TABLE(
    week         date,
    department   text,
    revisit_rate numeric
)
LANGUAGE sql
AS $$
    WITH base AS (
        SELECT
            DATE_TRUNC('week', e."START"::timestamp)::date AS week,
            COALESCE(o.name, e."ORGANIZATION")             AS department,
            e."PATIENT",
            e."START"::timestamp                           AS start_ts,
            LAG(e."START"::timestamp) OVER (
                PARTITION BY e."PATIENT", e."ORGANIZATION"
                ORDER BY e."START"
            ) AS prev_ts
        FROM encounters e
        LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
        WHERE e."START"::timestamp >= NOW() - INTERVAL '26 weeks'
    )
    SELECT
        week, department,
        ROUND(100.0 * SUM(CASE
            WHEN prev_ts IS NOT NULL
             AND start_ts - prev_ts <= INTERVAL '30 days'
            THEN 1 ELSE 0 END
        ) / NULLIF(COUNT(*), 0), 1) AS revisit_rate
    FROM base
    GROUP BY week, department
    ORDER BY week, department;
$$;


-- ── 7. Supply trend (top 6, last 90 days) ────────────────────────────
CREATE OR REPLACE FUNCTION get_supply_trend()
RETURNS TABLE(
    date_val date,
    supply   text,
    units    bigint
)
LANGUAGE sql
AS $$
    WITH top6 AS (
        SELECT description FROM supplies
        GROUP BY description
        ORDER BY SUM(quantity) DESC
        LIMIT 6
    )
    SELECT
        s.date::date    AS date_val,
        s.description   AS supply,
        SUM(s.quantity) AS units
    FROM supplies s
    JOIN top6 ON top6.description = s.description
    WHERE s.date::date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY s.date::date, s.description
    ORDER BY date_val, supply;
$$;


-- ── 8. Dept supply usage ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_dept_supply_usage()
RETURNS TABLE(
    supply        text,
    department    text,
    monthly_units numeric
)
LANGUAGE sql
AS $$
    WITH span AS (
        SELECT GREATEST(1, (MAX(date::date) - MIN(date::date)))::numeric AS days
        FROM supplies
    )
    SELECT
        s.description                                        AS supply,
        COALESCE(o.name, e."ORGANIZATION")                   AS department,
        ROUND((SUM(s.quantity) / sp.days * 30)::numeric, 0) AS monthly_units
    FROM supplies s
    LEFT JOIN encounters    e ON e.id = s.encounter
    LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    , span sp
    GROUP BY s.description, e."ORGANIZATION", o.name, sp.days
    ORDER BY monthly_units DESC;
$$;


-- ── 9. Home KPIs ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_home_kpis()
RETURNS TABLE(
    total_patients       bigint,
    encounters_today     bigint,
    total_providers      bigint,
    total_departments    bigint,
    overloaded_providers bigint,
    critical_supplies    bigint
)
LANGUAGE sql
AS $$
    SELECT
        (SELECT COUNT(*) FROM patients)                     AS total_patients,
        (SELECT COUNT(*) FROM encounters
         WHERE "START"::date = CURRENT_DATE)                AS encounters_today,
        (SELECT COUNT(*) FROM providers)                    AS total_providers,
        (SELECT COUNT(*) FROM organizations)                AS total_departments,
        0::bigint                                           AS overloaded_providers,
        0::bigint                                           AS critical_supplies;
$$;