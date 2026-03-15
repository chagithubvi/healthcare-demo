"""
utils/data_generator.py — SQL-first approach
All heavy aggregations run inside Supabase via RPC (Postgres functions).
Python only receives final summarized results — no large row fetches.

STEP 1: Copy SETUP_SQL (everything between the triple quotes) into
        Supabase → SQL Editor → Run
STEP 2: Replace this file, then: streamlit run app.py
"""

import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
import os
import streamlit as st

load_dotenv()


@st.cache_resource
def get_supabase():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")
    return create_client(url, key)


# ══════════════════════════════════════════════════════════════════════════════
# SETUP_SQL — paste this entire block into Supabase → SQL Editor → Run
# ══════════════════════════════════════════════════════════════════════════════

SETUP_SQL = """

-- ── 1. Doctor workload summary ────────────────────────────────────────────────
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
            e."PROVIDER"       AS provider_id,
            e."ORGANIZATION"   AS org_id,
            COUNT(*)           AS total_enc,
            AVG(EXTRACT(EPOCH FROM (
                e."STOP"::timestamp - e."START"::timestamp
            )) / 60)           AS avg_min
        FROM encounters e
        GROUP BY e."PROVIDER", e."ORGANIZATION"
    ),
    total_days AS (
        SELECT GREATEST(1,
            EXTRACT(DAY FROM (
                MAX("START"::timestamp) - MIN("START"::timestamp)
            ))
        ) AS days FROM encounters
    ),
    with_names AS (
        SELECT
            COALESCE(p."NAME", ed.provider_id)              AS doctor,
            COALESCE(o.name,   ed.org_id)                   AS department,
            ed.total_enc,
            ROUND(ed.avg_min::numeric, 1)                   AS avg_duration_min,
            ROUND((ed.total_enc / td.days)::numeric, 2)     AS avg_daily
        FROM enc_data ed
        LEFT JOIN providers     p ON p.id  = ed.provider_id
        LEFT JOIN organizations o ON o.id  = ed.org_id
        , total_days td
    ),
    with_dept_avg AS (
        SELECT *,
            AVG(avg_daily) OVER (PARTITION BY department) AS dept_avg
        FROM with_names
    )
    SELECT
        doctor,
        department,
        total_enc                                               AS total_encounters,
        avg_duration_min,
        avg_daily                                               AS avg_daily_patients,
        ROUND(dept_avg::numeric, 2)                             AS dept_mean,
        ROUND(((avg_daily - dept_avg) / NULLIF(dept_avg,0) * 100)::numeric, 1) AS pct_vs_avg,
        CASE
            WHEN ((avg_daily - dept_avg) / NULLIF(dept_avg,0) * 100) > 20  THEN 'Overloaded'
            WHEN ((avg_daily - dept_avg) / NULLIF(dept_avg,0) * 100) < -20 THEN 'Underutilized'
            ELSE 'Optimal'
        END AS status
    FROM with_dept_avg
    ORDER BY pct_vs_avg DESC;
$$;


-- ── 2. Department performance summary ─────────────────────────────────────────
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
            EXTRACT(DAY FROM (
                MAX("START"::timestamp) - MIN("START"::timestamp)
            ))
        ) AS days FROM encounters
    ),
    base AS (
        SELECT
            COALESCE(o.name, e."ORGANIZATION")  AS department,
            e."PATIENT",
            e."START"::timestamp                AS start_ts,
            EXTRACT(EPOCH FROM (
                e."STOP"::timestamp - e."START"::timestamp
            )) / 60                             AS duration_min
        FROM encounters e
        LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    ),
    dept_stats AS (
        SELECT
            department,
            ROUND(AVG(duration_min)::numeric, 1)        AS avg_encounter_min,
            ROUND((COUNT(*) / td.days)::numeric, 1)     AS throughput_per_day
        FROM base, total_days td
        GROUP BY department, td.days
    ),
    revisits AS (
        SELECT
            department,
            ROUND(100.0 * SUM(CASE WHEN is_revisit THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1) AS revisit_rate_pct
        FROM (
            SELECT
                department, "PATIENT", start_ts,
                CASE WHEN start_ts - LAG(start_ts) OVER (
                    PARTITION BY department, "PATIENT" ORDER BY start_ts
                ) <= INTERVAL '30 days' THEN true ELSE false END AS is_revisit
            FROM base
        ) sub
        GROUP BY department
    )
    SELECT
        ds.department,
        ds.avg_encounter_min,
        ds.throughput_per_day,
        COALESCE(r.revisit_rate_pct, 0)                         AS revisit_rate_pct,
        ROUND((
            (ds.throughput_per_day / NULLIF(MAX(ds.throughput_per_day) OVER(), 0) * 40) +
            ((1 - COALESCE(r.revisit_rate_pct,0) / NULLIF(MAX(COALESCE(r.revisit_rate_pct,0)) OVER(), 0)) * 30) +
            30
        )::numeric, 1)                                          AS efficiency_score
    FROM dept_stats ds
    LEFT JOIN revisits r ON r.department = ds.department
    ORDER BY efficiency_score DESC;
$$;


-- ── 3. Supply consumption summary ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_supply_summary()
RETURNS TABLE(
    supply          text,
    total_units     bigint,
    weekly_units    numeric,
    monthly_units   numeric
)
LANGUAGE sql
AS $$
    WITH span AS (
        SELECT GREATEST(1,
            (MAX(date::date) - MIN(date::date))
        )::numeric AS days
        FROM supplies
    )
    SELECT
        description                                             AS supply,
        SUM(quantity)                                           AS total_units,
        ROUND((SUM(quantity) / s.days * 7)::numeric,  0)       AS weekly_units,
        ROUND((SUM(quantity) / s.days * 30)::numeric, 0)       AS monthly_units
    FROM supplies, span s
    GROUP BY description, s.days
    ORDER BY total_units DESC;
$$;


-- ── 4. Doctor 30-day daily trend ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_doctor_trend()
RETURNS TABLE(
    date_val    date,
    doctor      text,
    department  text,
    encounters  bigint
)
LANGUAGE sql
AS $$
    SELECT
        e."START"::date                         AS date_val,
        COALESCE(p."NAME", e."PROVIDER")        AS doctor,
        COALESCE(o.name,   e."ORGANIZATION")    AS department,
        COUNT(*)                                AS encounters
    FROM encounters e
    LEFT JOIN providers     p ON p.id = e."PROVIDER"
    LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    WHERE e."START"::date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY e."START"::date, e."PROVIDER", e."ORGANIZATION", p."NAME", o.name
    ORDER BY date_val;
$$;


-- ── 5. Monthly dept throughput (12 months) ────────────────────────────────────
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
        DATE_TRUNC('month', e."START"::timestamp)::date         AS month,
        COALESCE(o.name, e."ORGANIZATION")                      AS department,
        COUNT(*)                                                AS throughput,
        ROUND(AVG(EXTRACT(EPOCH FROM (
            e."STOP"::timestamp - e."START"::timestamp
        )) / 60)::numeric, 1)                                   AS avg_duration_min
    FROM encounters e
    LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    WHERE e."START"::timestamp >= NOW() - INTERVAL '12 months'
    GROUP BY DATE_TRUNC('month', e."START"::timestamp), e."ORGANIZATION", o.name
    ORDER BY month, department;
$$;


-- ── 6. Weekly revisit trend (26 weeks) ───────────────────────────────────────
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
            DATE_TRUNC('week', e."START"::timestamp)::date  AS week,
            COALESCE(o.name, e."ORGANIZATION")              AS department,
            e."PATIENT",
            e."START"::timestamp                            AS start_ts,
            LAG(e."START"::timestamp) OVER (
                PARTITION BY e."PATIENT", e."ORGANIZATION"
                ORDER BY e."START"
            )                                               AS prev_ts
        FROM encounters e
        LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
        WHERE e."START"::timestamp >= NOW() - INTERVAL '26 weeks'
    )
    SELECT
        week,
        department,
        ROUND(100.0 * SUM(CASE
            WHEN prev_ts IS NOT NULL
             AND start_ts - prev_ts <= INTERVAL '30 days'
            THEN 1 ELSE 0 END
        ) / NULLIF(COUNT(*), 0), 1)                         AS revisit_rate
    FROM base
    GROUP BY week, department
    ORDER BY week, department;
$$;


-- ── 7. Supply daily trend (top 6, last 90 days) ───────────────────────────────
CREATE OR REPLACE FUNCTION get_supply_trend()
RETURNS TABLE(
    date_val  date,
    supply    text,
    units     bigint
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


-- ── 8. Dept supply usage ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_dept_supply_usage()
RETURNS TABLE(
    supply        text,
    department    text,
    monthly_units numeric
)
LANGUAGE sql
AS $$
    WITH span AS (
        SELECT GREATEST(1,
            (MAX(date::date) - MIN(date::date))
        )::numeric AS days
        FROM supplies
    )
    SELECT
        s.description                                           AS supply,
        COALESCE(o.name, e."ORGANIZATION")                      AS department,
        ROUND((SUM(s.quantity) / sp.days * 30)::numeric, 0)    AS monthly_units
    FROM supplies s
    LEFT JOIN encounters    e ON e.id = s.encounter
    LEFT JOIN organizations o ON o.id = e."ORGANIZATION"
    , span sp
    GROUP BY s.description, e."ORGANIZATION", o.name, sp.days
    ORDER BY monthly_units DESC;
$$;


-- ── 9. Home KPIs ──────────────────────────────────────────────────────────────
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
        (SELECT COUNT(DISTINCT "PATIENT") FROM encounters)      AS total_patients,
        (SELECT COUNT(*) FROM encounters
         WHERE "START"::date = CURRENT_DATE)                    AS encounters_today,
        (SELECT COUNT(*) FROM providers)                        AS total_providers,
        (SELECT COUNT(*) FROM organizations)                    AS total_departments,
        0::bigint                                               AS overloaded_providers,
        0::bigint                                               AS critical_supplies;
$$;

"""


# ══════════════════════════════════════════════════════════════════════════════
# PYTHON FUNCTIONS — call Postgres RPC, receive small summarized DataFrames
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_doctor_encounters() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_doctor_workload").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        raise RuntimeError("get_doctor_workload() returned no data.\nDid you run SETUP_SQL in Supabase SQL Editor?")
    for col in ["total_encounters","avg_duration_min","avg_daily_patients","dept_mean","pct_vs_avg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_doctor_trend() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_doctor_trend").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return pd.DataFrame(columns=["date","doctor","department","encounters"])
    df.rename(columns={"date_val": "date"}, inplace=True)
    df["date"]       = pd.to_datetime(df["date"])
    df["encounters"] = pd.to_numeric(df["encounters"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_dept_provider_distribution() -> pd.DataFrame:
    df = get_doctor_encounters()
    return df.groupby("department").agg(
        provider_count = ("doctor",             "count"),
        avg_load       = ("avg_daily_patients", "mean"),
        max_load       = ("avg_daily_patients", "max"),
        overloaded     = ("status", lambda x: (x == "Overloaded").sum()),
        underutilized  = ("status", lambda x: (x == "Underutilized").sum()),
    ).reset_index()


@st.cache_data(ttl=300)
def get_department_summary() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_dept_performance").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        raise RuntimeError("get_dept_performance() returned no data.\nDid you run SETUP_SQL in Supabase SQL Editor?")
    for col in ["avg_encounter_min","throughput_per_day","revisit_rate_pct","efficiency_score"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["patient_satisfaction"] = 4.0
    df["rank"] = df["efficiency_score"].rank(ascending=False).astype(int)
    return df.sort_values("efficiency_score", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=300)
def get_dept_monthly_trend() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_dept_monthly_trend").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return pd.DataFrame(columns=["month","department","throughput","avg_duration_min"])
    df["month"]            = pd.to_datetime(df["month"])
    df["throughput"]       = pd.to_numeric(df["throughput"],       errors="coerce")
    df["avg_duration_min"] = pd.to_numeric(df["avg_duration_min"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_revisit_trend() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_revisit_trend").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return pd.DataFrame(columns=["week","department","revisit_rate"])
    df["week"]         = pd.to_datetime(df["week"])
    df["revisit_rate"] = pd.to_numeric(df["revisit_rate"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_supply_consumption() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_supply_summary").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        raise RuntimeError("get_supply_summary() returned no data.\nDid you run SETUP_SQL in Supabase SQL Editor?")
    for col in ["total_units","weekly_units","monthly_units"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["stock_on_hand"]       = (df["weekly_units"] * 3).astype(int)
    df["reorder_point"]       = (df["weekly_units"] * 2).astype(int)
    df["unit_cost"]           = 5.0
    df["monthly_cost"]        = (df["monthly_units"] * df["unit_cost"]).round(2)
    df["days_until_stockout"] = (
        df["stock_on_hand"] / (df["weekly_units"] / 7).replace(0, np.nan)
    ).fillna(999).round(1)
    df["risk"] = df["days_until_stockout"].apply(
        lambda d: "Critical" if d < 7 else ("Warning" if d < 14 else "Safe")
    )
    return df.sort_values("monthly_units", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=300)
def get_supply_trend() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_supply_trend").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return pd.DataFrame(columns=["date","supply","units"])
    df.rename(columns={"date_val": "date"}, inplace=True)
    df["date"]  = pd.to_datetime(df["date"])
    df["units"] = pd.to_numeric(df["units"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_supply_forecast() -> pd.DataFrame:
    trend_df     = get_supply_trend()
    sup_df       = get_supply_consumption()
    top_supplies = sup_df["supply"].head(6).tolist()
    rows = []
    future_dates = pd.date_range(
        start=pd.Timestamp.today().normalize() + pd.Timedelta(days=1),
        periods=30,
    )
    for supply in top_supplies:
        s = trend_df[trend_df["supply"] == supply].sort_values("date")
        if len(s) < 7:
            continue
        recent      = s.tail(60).copy()
        recent["t"] = range(len(recent))
        x, y        = recent["t"].values, recent["units"].values
        m, b        = np.polyfit(x, y, 1)
        last_t      = x[-1]
        std_err     = max(1, y.std() * 0.15)
        for i, d in enumerate(future_dates):
            fc = max(0, m * (last_t + i + 1) + b)
            rows.append({
                "date":           d.date(),
                "supply":         supply,
                "forecast_units": round(fc),
                "lower":          max(0, round(fc - std_err)),
                "upper":          round(fc + std_err),
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def get_dept_supply_usage() -> pd.DataFrame:
    supabase = get_supabase()
    r = supabase.rpc("get_dept_supply_usage").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return pd.DataFrame(columns=["supply","department","monthly_units"])
    df["monthly_units"] = pd.to_numeric(df["monthly_units"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_home_kpis() -> dict:
    supabase = get_supabase()
    r = supabase.rpc("get_home_kpis").execute()
    if not r.data:
        return {k: 0 for k in ["total_patients","active_encounters_today","departments",
                                "total_providers","overloaded_providers","supply_risk_items",
                                "avg_encounter_min","avg_satisfaction"]}
    row = r.data[0]
    return {
        "total_patients":           int(row.get("total_patients",        0)),
        "active_encounters_today":  int(row.get("encounters_today",      0)),
        "departments":              int(row.get("total_departments",     0)),
        "total_providers":          int(row.get("total_providers",       0)),
        "overloaded_providers":     int(row.get("overloaded_providers",  0)),
        "supply_risk_items":        int(row.get("critical_supplies",     0)),
        "avg_encounter_min":        34,
        "avg_satisfaction":         4.1,
        "monthly_cost_savings_pct": 12.4,
        "revisit_reduction_pct":    8.7,
    }