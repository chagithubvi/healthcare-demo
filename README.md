# HealthIntel — AI-Powered Healthcare Intelligence Dashboard

A production-ready Streamlit dashboard for hospital operational intelligence,
built on Synthea 10K patient data with Supabase backend support.

---

## 📐 Architecture

```
healthintel/
├── app.py                        ← Main entry point + global CSS + sidebar routing
├── requirements.txt
├── .env                          ← Supabase credentials (create this)
├── pages/
│   ├── home.py                   ← Command center overview
│   ├── doctor_utilization.py     ← Provider workload intelligence
│   ├── department_performance.py ← Dept efficiency & benchmarking
│   └── supply_intelligence.py   ← Supply consumption & forecasting
└── utils/
    ├── data_generator.py         ← Synthea-compatible data layer (swap for Supabase)
    └── charts.py                 ← Shared Plotly theme + chart helpers
```

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Supabase (optional — works with synthetic data out of the box)
Create a `.env` file:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### 3. Run the dashboard
```bash
streamlit run app.py
```

---

## 🗄️ Supabase Schema

The dashboard expects these tables (mirrors Synthea output format):

### `encounters`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| patient_id | uuid | FK to patients |
| provider_id | uuid | FK to providers |
| organization_id | uuid | FK to organizations (department) |
| start | timestamp | Encounter start time |
| stop | timestamp | Encounter end time |
| encounter_class | text | ambulatory / emergency / inpatient |
| reason_description | text | Primary reason |

### `providers`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| name | text | Doctor full name |
| specialty | text | Medical specialty |
| organization | text | Department/hospital |

### `organizations`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| name | text | Department name |
| city | text | Location |

### `supplies` (custom table)
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| name | text | Supply item name |
| date | date | Consumption date |
| department_id | uuid | FK to organizations |
| units_used | integer | Quantity used |
| unit_cost | numeric | Cost per unit |
| stock_on_hand | integer | Current inventory |

---

## 🔌 Connecting Supabase (Replace synthetic data)

In `utils/data_generator.py`, replace the `get_*()` functions with Supabase queries:

```python
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_doctor_encounters():
    response = supabase.table("encounters") \
        .select("*, providers(name, specialty), organizations(name)") \
        .execute()
    df = pd.DataFrame(response.data)
    # ... transform to match expected schema
    return df
```

---

## 🤖 How Training Works (New Data Handling)

### Current Approach (Statistical Baselines)
- Baselines computed from 90-day rolling windows
- Alerts triggered when values exceed 1.5σ from rolling mean
- Forecasts use exponential smoothing + seasonal decomposition

### For ML Integration (Recommended path before March 19)
```python
# In utils/models.py (create this)
from sklearn.ensemble import IsolationForest  # anomaly detection
from sklearn.linear_model import LinearRegression  # trend forecasting

def train_supply_model(historical_df):
    """Train on last 90 days, re-train weekly on new data."""
    X = historical_df[["day_of_week", "month", "lag_7", "lag_14"]]
    y = historical_df["units"]
    model = LinearRegression().fit(X, y)
    return model

def detect_anomalies(df, contamination=0.05):
    """Flag consumption spikes using Isolation Forest."""
    clf = IsolationForest(contamination=contamination)
    df["is_anomaly"] = clf.fit_predict(df[["units"]]) == -1
    return df
```

### New Data Flow
```
Synthea Export → Supabase (nightly ETL) → Dashboard queries live
                                         → Weekly model retrain
                                         → Alerts recalibrate
```

---

## 📊 Use Cases Delivered

| Module | Problem Solved | Business Value |
|---|---|---|
| Doctor Utilization | Uneven workload distribution | Reduce burnout, optimize allocation |
| Dept Performance | No visibility into efficiency | Data-driven improvements |
| Supply Intelligence | Overstocking / shortages | Cut waste, prevent disruptions |

---

## 🎨 Design System

- **Primary font**: DM Sans (body) + Space Grotesk (headings/numbers)
- **Background**: `#050D1A` (deep navy)
- **Accent**: `#00D4FF` (cyan) for highlights, `#00E5A0` (green) for positive, `#FF4D6A` (red) for alerts
- **Charts**: Plotly with custom dark theme — all axis labels present

---

## 📅 Submission Checklist (before March 19)

- [ ] Connect Supabase tables to real Synthea export
- [ ] Verify all 3 use cases render with live data
- [ ] Add `.env` with production Supabase credentials  
- [ ] Test on hospital stakeholder machine (non-technical user review)
- [ ] Optional: Add ML model training pipeline in `utils/models.py`
