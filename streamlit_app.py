# ================================================================
#  TN LOAD FORECASTING — STREAMLIT WEB APP (FIXED FINAL)
#
#  HOW DATA FLOWS:
#  ─────────────────────────────────────────────────────────────
#  BEFORE Colab runs  → NO charts, NO data, only placeholder
#                       messages telling user to run Colab.
#
#  AFTER Colab runs   → Colab pushes CSV files to GitHub.
#                       Web app reads them from GitHub.
#                       All charts appear automatically.
#
#  NO DATA IS HARDCODED IN THIS FILE.
#  All historical (2020–2025) and forecast (2026) data
#  comes exclusively from the CSV files produced by Colab.
#
#  BUGS FIXED:
#  ✓ 2026 avg bar was missing in 5-year chart → fixed
#  ✓ Growth table year-string parse crash → fixed
#  ✓ No embedded/hardcoded historical data → fixed
#  ✓ fillcolor crash (hex→rgba) → fixed
#  ✓ Safe None-guards everywhere → fixed
#
#  TABS:
#  1. 📅 Monthly Forecast  — bar+line, month-by-month, day picker
#  2. 📊 5-Year Comparison — line + bar + growth table
#  3. 📈 Daily Forecast    — today hourly + tomorrow hourly
#  4. 🎯 Accuracy          — MAPE / RMSE trends
#  5. 📋 All Results       — full table + download
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, requests, calendar
from datetime import datetime
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide"
)

# ── GitHub config ──────────────────────────────────────────────
GITHUB_USER  = "sanjay-engineer"
GITHUB_REPO  = "TN-LOAD-FORECAST"
GITHUB_RAW   = (f"https://raw.githubusercontent.com/"
                f"{GITHUB_USER}/{GITHUB_REPO}/main/results")

USERS_FILE   = "users.json"
SHARED_DIR   = "shared_results"
os.makedirs(SHARED_DIR, exist_ok=True)

MONTH_NAMES  = {4: "April",   5: "May",     6: "June"}
MONTH_COLORS = {4: "#2563eb", 5: "#16a34a", 6: "#ea580c"}
MONTH_FILL   = {
    4: "rgba(37,99,235,0.10)",
    5: "rgba(22,163,74,0.10)",
    6: "rgba(234,88,12,0.10)"
}
YEAR_COLORS  = {
    2020: "#94a3b8", 2021: "#64748b", 2022: "#f59e0b",
    2023: "#8b5cf6", 2024: "#ec4899", 2025: "#6366f1",
    2026: "#dc2626"
}

# ── Plotly base layout (no background) ────────────────────────
BL = dict(
    plot_bgcolor  = "rgba(0,0,0,0)",
    paper_bgcolor = "rgba(0,0,0,0)",
    hovermode     = "x unified",
    yaxis         = dict(tickformat=","),
    legend        = dict(orientation="h", yanchor="bottom", y=1.02)
)

# ── Safe helpers ───────────────────────────────────────────────
def sf(v):
    try:
        x = float(v)
        return None if (np.isnan(x) or np.isinf(x)) else x
    except Exception:
        return None

def g24(row, pfx):
    return [sf(row.get(f"{pfx}_h{h:02d}")) for h in range(24)]

def safe_mean(lst):
    vals = [v for v in lst if v is not None and not np.isnan(v)]
    return float(np.mean(vals)) if vals else None

def safe_max(lst):
    vals = [v for v in lst if v is not None and not np.isnan(v)]
    return float(max(vals)) if vals else None


# ══════════════════════════════════════════════════════════════
#  USER SYSTEM
# ══════════════════════════════════════════════════════════════
def _hp(p):
    return hashlib.sha256(p.encode()).hexdigest()

def _lu():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def _su(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def register(un, pw):
    if len(un) < 3:  return False, "Min 3 chars"
    if len(un) > 20: return False, "Max 20 chars"
    if not un.replace("_", "").isalnum():
        return False, "Letters/numbers/underscore only"
    if len(pw) < 6:  return False, "Password min 6 chars"
    u = _lu()
    if un.lower() in [k.lower() for k in u]:
        return False, "Username already taken"
    u[un] = {
        "password": _hp(pw), "role": "viewer",
        "created": str(datetime.now().date()), "last_login": None
    }
    _su(u)
    return True, "Account created — login now"

def login(un, pw):
    u = _lu()
    m = next((k for k in u if k.lower() == un.lower()), None)
    if not m:                          return False, "Username not found", None
    if u[m]["password"] != _hp(pw):   return False, "Wrong password", None
    u[m]["last_login"] = str(datetime.now())
    _su(u)
    return True, m, u[m].get("role", "viewer")

def set_admin(un, secret):
    if secret != "TN2025Admin":
        return False, "Wrong secret key"
    u = _lu()
    m = next((k for k in u if k.lower() == un.lower()), None)
    if not m: return False, f"User '{un}' not found"
    u[m]["role"] = "admin"
    _su(u)
    return True, f"'{m}' is now Admin"


# ══════════════════════════════════════════════════════════════
#  DATA LOADING  — GitHub first, local fallback
#  NO hardcoded data anywhere in this file.
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def gh_fetch(fn):
    try:
        r = requests.get(f"{GITHUB_RAW}/{fn}", timeout=10)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None

@st.cache_data(ttl=30)
def gh_ok():
    try:
        r = requests.head(f"{GITHUB_RAW}/rolling_results.csv",
                          timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def read_csv(fn):
    """Try GitHub → local upload folder → return None."""
    raw = gh_fetch(fn)
    if raw:
        try:
            df = pd.read_csv(StringIO(raw))
            if len(df) > 0:
                return df
        except Exception:
            pass
    loc = os.path.join(SHARED_DIR, fn)
    if os.path.exists(loc):
        try:
            df = pd.read_csv(loc)
            if len(df) > 0:
                return df
        except Exception:
            pass
    return None   # ← nothing available yet

def load_rolling():
    return read_csv("rolling_results.csv")

def load_mo(mo):
    return read_csv(f"{MONTH_NAMES[mo].lower()}_2026_results.csv")

def load_history():
    """
    Load the combined history CSV (2020-2025) pushed by Colab.
    File name: history_summary.csv
    Columns: year, month, avg_load, peak_load
    (Colab must push this file — see Colab code Cell 9.)
    """
    return read_csv("history_summary.csv")

def load_daily_history():
    """
    Load daily history CSV pushed by Colab.
    File name: history_daily.csv
    Columns: year, month, day, avg_load
    """
    return read_csv("history_daily.csv")

def save_local(uf, fn):
    df = pd.read_csv(uf)
    df.to_csv(os.path.join(SHARED_DIR, fn), index=False)
    return len(df)


# ══════════════════════════════════════════════════════════════
#  NO-DATA PLACEHOLDER
# ══════════════════════════════════════════════════════════════
def no_data_card(msg="Run the Colab notebook first."):
    st.markdown(
        f"""
        <div style='background:#f8fafc;border:2px dashed #cbd5e1;
        border-radius:12px;padding:40px 24px;text-align:center;
        margin:20px 0'>
          <div style='font-size:40px;margin-bottom:12px'>⏳</div>
          <h3 style='color:#475569;margin:0 0 8px'>
            No Forecast Data Yet</h3>
          <p style='color:#94a3b8;margin:0;font-size:14px'>
            {msg}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════════════
def show_login():
    st.markdown(
        "<div style='text-align:center;padding:30px 0 10px'>"
        "<div style='font-size:52px'>⚡</div>"
        "<h2 style='color:#2563eb;margin:8px 0'>TN Intelligent Load Forecasting</h2>"
        "<p style='color:#64748b;font-size:13px'>"
        "Tamil Nadu Power Grid — LSTM Forecast System</p></div>",
        unsafe_allow_html=True
    )
    st.divider()

    t1, t2, t3 = st.tabs(["🔑 Login", "📝 Register", "🔧 Admin Setup"])

    with t1:
        with st.form("lf"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            s = st.form_submit_button("Login",
                use_container_width=True, type="primary")
        if s:
            if not u or not p:
                st.error("Enter both username and password")
            else:
                ok, res, role = login(u, p)
                if ok:
                    st.session_state.update(
                        logged_in=True, username=res, role=role)
                    st.rerun()
                else:
                    st.error(f"❌ {res}")

    with t2:
        with st.form("rf"):
            nu  = st.text_input("Username", placeholder="3–20 chars")
            np_ = st.text_input("Password", type="password")
            cp  = st.text_input("Confirm Password", type="password")
            rb  = st.form_submit_button("Create Account",
                use_container_width=True, type="primary")
        if rb:
            if not nu or not np_ or not cp:
                st.error("Fill all fields")
            elif np_ != cp:
                st.error("Passwords don't match")
            else:
                ok, msg = register(nu, np_)
                (st.success if ok else st.error)(msg)

    with t3:
        st.info("Register first, then enter the secret key below.")
        st.info("Secret key: **TN2025Admin**")
        with st.form("af"):
            au = st.text_input("Your Username")
            ak = st.text_input("Admin Key", type="password")
            if st.form_submit_button("Make Admin",
                    use_container_width=True):
                ok, msg = set_admin(au, ak)
                (st.success if ok else st.error)(msg)

    st.divider()
    if gh_ok():
        st.success("✅ GitHub connected — data will load automatically after Colab runs")
    else:
        st.warning("⚠ GitHub offline — use sidebar Manual Upload after login")


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
def show_sidebar(un, role):
    with st.sidebar:
        bg = "#7c3aed" if role == "admin" else "#2563eb"
        st.markdown(
            f"<div style='background:{bg};color:white;"
            f"padding:10px 14px;border-radius:8px;margin-bottom:8px'>"
            f"<b>👤 {un}</b><br>"
            f"<span style='font-size:12px;opacity:.85'>"
            f"{'Admin ✓' if role=='admin' else 'Viewer'}"
            f"</span></div>",
            unsafe_allow_html=True
        )
        st.divider()

        # ── Data source status ─────────────────────────────────
        st.subheader("🔗 Data Source")
        if gh_ok():
            st.success("✅ GitHub — Auto sync")
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("⚠ GitHub offline")

        # ── How data flows (info box) ──────────────────────────
        with st.expander("ℹ️ How data gets here"):
            st.markdown(
                """
**Step 1:** Run `TN_FORECAST_COLAB.py` in Google Colab  
**Step 2:** Colab trains LSTM & makes predictions  
**Step 3:** Colab pushes CSV files to GitHub  
**Step 4:** This app reads them — charts appear  

No Colab run = No charts. That is by design.
                """
            )

        # ── Admin manual upload ────────────────────────────────
        if role == "admin":
            st.divider()
            with st.expander("📂 Manual Upload (Admin)"):
                st.caption(
                    "Use this only if GitHub push failed. "
                    "Upload the CSVs that Colab generated."
                )
                upload_map = [
                    ("rolling_results.csv",         "ru"),
                    ("april_2026_results.csv",       "a26"),
                    ("may_2026_results.csv",         "m26"),
                    ("june_2026_results.csv",        "j26"),
                    ("history_summary.csv",          "hs"),
                    ("history_daily.csv",            "hd"),
                ]
                for fn, key in upload_map:
                    uf = st.file_uploader(fn, type=["csv"], key=key)
                    if uf:
                        n = save_local(uf, fn)
                        st.cache_data.clear()
                        st.success(f"✓ {fn} saved ({n} rows)")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.update(
                logged_in=False, username=None, role=None)
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
def show_dashboard(un, role):
    st.markdown(
        f"<h2 style='color:#2563eb'>⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>"
        f"Tamil Nadu Power Grid · LSTM Rolling Forecast · "
        f"Welcome <b>{un}</b></p>",
        unsafe_allow_html=True
    )
    st.divider()

    # ── Load all data ──────────────────────────────────────────
    df_roll   = load_rolling()
    df_hist   = load_history()       # monthly summary 2020-2025
    df_hist_d = load_daily_history() # daily history 2020-2025
    hlbl      = [f"{h:02d}:00" for h in range(24)]

    # ── Derived frame slices ───────────────────────────────────
    if df_roll is not None and len(df_roll) > 0:
        df_roll["ha"] = df_roll.get("actual_h00", pd.Series(
            dtype=object)).apply(
            lambda x: pd.notna(x) and str(x).strip()
            not in ["", "nan", "None"])
        df_past   = df_roll[df_roll["ha"]].copy()
        df_future = df_roll[~df_roll["ha"]].copy()
        df_m      = (df_past[df_past["mape"].notna()].copy()
                     if "mape" in df_past.columns
                     else pd.DataFrame())
    else:
        df_past = df_future = df_m = pd.DataFrame()

    # ── KPI strip ──────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)

    if df_roll is not None and len(df_roll) > 0:
        k1.metric("📅 Forecast Days", len(df_roll))
    else:
        k1.metric("📅 Forecast Days", "—  Run Colab")

    if len(df_m) > 0:
        k2.metric("🎯 Avg MAPE",  f"{df_m['mape'].mean():.2f}%")
        k3.metric("📊 Avg RMSE",  f"{df_m['rmse'].mean():.0f} MW")
    else:
        k2.metric("🎯 Avg MAPE",  "—")
        k3.metric("📊 Avg RMSE",  "—")

    if df_hist is not None and len(df_hist) > 0:
        k4.metric("📂 History Years",
                  f"{int(df_hist['year'].min())}–"
                  f"{int(df_hist['year'].max())}")
    else:
        k4.metric("📂 History", "—  Run Colab")

    k5.metric("🔮 Target", "Apr · May · Jun 2026")

    # ── Top-level status banner ────────────────────────────────
    if df_roll is None and df_hist is None:
        st.warning(
            "⚠️  **No data found.** "
            "Run `TN_FORECAST_COLAB.py` in Google Colab first. "
            "Colab will train the LSTM model, generate forecasts, "
            "and push all CSVs to GitHub. "
            "Once pushed, this dashboard will auto-populate."
        )
    elif df_roll is not None:
        st.success(
            f"✅  Forecast data loaded — "
            f"{len(df_roll)} predicted days across "
            f"April · May · June 2026"
        )

    st.divider()

    # ── TABS ───────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Monthly Forecast",
        "📊 5-Year Comparison",
        "📈 Daily Forecast",
        "🎯 Accuracy",
        "📋 All Results",
    ])

    # ══════════════════════════════════════════════════════════
    # TAB 1 — MONTHLY FORECAST
    # Data source: april/may/june_2026_results.csv from Colab
    # ══════════════════════════════════════════════════════════
    with tab1:
        st.subheader("📅 Monthly Forecast — April · May · June 2026")

        # Load all 3 months
        mo_data = {}
        for mo in [4, 5, 6]:
            df_mo = load_mo(mo)
            if df_mo is not None and len(df_mo) > 0:
                df_mo["day"] = pd.to_numeric(
                    df_mo["day"], errors="coerce")
                df_mo = (df_mo.dropna(subset=["day"])
                               .sort_values("day"))
                df_mo["day"] = df_mo["day"].astype(int)
                mo_data[mo]  = df_mo

        if not mo_data:
            no_data_card(
                "Monthly forecast charts will appear here after "
                "you run TN_FORECAST_COLAB.py in Google Colab."
            )
        else:
            # ── COMBINED VIEW ──────────────────────────────────
            st.markdown("### 📊 Combined 3-Month View")
            cb, cl = st.columns(2)

            with cb:
                fc = go.Figure()
                xoff = 0
                for mo, df_mo in mo_data.items():
                    xs   = [xoff + d for d in df_mo["day"]]
                    avgs = pd.to_numeric(
                        df_mo["predicted_avg"],
                        errors="coerce").tolist()
                    fc.add_trace(go.Bar(
                        x=xs, y=avgs,
                        name=MONTH_NAMES[mo],
                        marker_color=MONTH_COLORS[mo],
                        opacity=0.85, width=0.8))
                    if xoff > 0:
                        fc.add_vline(
                            x=xoff + 0.5,
                            line_dash="dash",
                            line_color="gray", opacity=0.4)
                    xoff += calendar.monthrange(2026, mo)[1]
                fc.update_layout(
                    title="Apr+May+Jun 2026 — Daily Avg Load (Bar)",
                    xaxis_title="Consecutive Day",
                    yaxis_title="Avg Load (MW)",
                    height=360, **BL)
                st.plotly_chart(fc, use_container_width=True)

            with cl:
                fl = go.Figure()
                xoff = 0
                for mo, df_mo in mo_data.items():
                    xs   = [xoff + d for d in df_mo["day"]]
                    avgs = pd.to_numeric(
                        df_mo["predicted_avg"],
                        errors="coerce").tolist()
                    fl.add_trace(go.Scatter(
                        x=xs, y=avgs,
                        name=MONTH_NAMES[mo],
                        line=dict(color=MONTH_COLORS[mo],
                                  width=2.5),
                        mode="lines+markers",
                        marker=dict(size=4),
                        fill="tozeroy",
                        fillcolor=MONTH_FILL[mo]))
                    if xoff > 0:
                        fl.add_vline(
                            x=xoff + 0.5,
                            line_dash="dash",
                            line_color="gray", opacity=0.4)
                    xoff += calendar.monthrange(2026, mo)[1]
                fl.update_layout(
                    title="Apr+May+Jun 2026 — Daily Trend (Line)",
                    xaxis_title="Consecutive Day",
                    yaxis_title="Avg Load (MW)",
                    height=360, **BL)
                st.plotly_chart(fl, use_container_width=True)

            st.divider()

            # ── EACH MONTH SEPARATELY ──────────────────────────
            for mo in [4, 5, 6]:
                if mo not in mo_data:
                    continue

                mn    = MONTH_NAMES[mo]
                color = MONTH_COLORS[mo]
                fill  = MONTH_FILL[mo]
                df_mo = mo_data[mo]
                ndays = int(df_mo["day"].max())

                days   = df_mo["day"].tolist()
                avgs   = pd.to_numeric(
                    df_mo["predicted_avg"],
                    errors="coerce").tolist()
                peaks  = pd.to_numeric(
                    df_mo["predicted_peak"],
                    errors="coerce").tolist()

                # Previous year daily data (from history_daily.csv)
                prev_avgs = [None] * len(days)
                if df_hist_d is not None and len(df_hist_d) > 0:
                    hd_cols = df_hist_d.columns.str.lower().tolist()
                    # Normalise column names
                    df_hist_d.columns = hd_cols
                    sub25 = df_hist_d[
                        (pd.to_numeric(df_hist_d["year"],
                                       errors="coerce") == 2025) &
                        (pd.to_numeric(df_hist_d["month"],
                                       errors="coerce") == mo)
                    ]
                    day_map = dict(zip(
                        pd.to_numeric(sub25["day"], errors="coerce"),
                        pd.to_numeric(sub25["avg_load"],
                                      errors="coerce")
                    ))
                    prev_avgs = [day_map.get(d) for d in days]

                # Month header banner
                avg_v  = safe_mean(avgs)  or 0
                peak_v = safe_max(peaks) or 0
                st.markdown(
                    f"<div style='background:{color};color:white;"
                    f"padding:10px 18px;border-radius:8px;"
                    f"margin:18px 0 10px'>"
                    f"<b>📅 {mn} 2026</b> — {ndays} days"
                    f"&nbsp;|&nbsp; Avg: {avg_v:,.0f} MW"
                    f"&nbsp;|&nbsp; Peak: {peak_v:,.0f} MW"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # KPIs
                m1, m2, m3 = st.columns(3)
                m1.metric("Monthly Avg",  f"{avg_v:,.0f} MW")
                m2.metric("Monthly Peak", f"{peak_v:,.0f} MW")
                valid_peaks = [(v, d) for v, d in
                               zip(peaks, days) if v is not None]
                if valid_peaks:
                    pk_day = max(valid_peaks, key=lambda x: x[0])[1]
                    m3.metric("Peak Day", f"{mn} {pk_day}")

                # ── BAR CHART ─────────────────────────────────
                bc, lc = st.columns(2)
                with bc:
                    fb = go.Figure()
                    # 2026 forecast bars
                    fb.add_trace(go.Bar(
                        x=days, y=avgs,
                        name=f"{mn} 2026 Forecast",
                        marker_color=color, opacity=0.88,
                        offsetgroup=0))
                    # 2025 actual bars (if available)
                    if any(v is not None for v in prev_avgs):
                        fb.add_trace(go.Bar(
                            x=days, y=prev_avgs,
                            name=f"{mn} 2025 Actual",
                            marker_color=YEAR_COLORS[2025],
                            opacity=0.55,
                            offsetgroup=1))
                    # Peak line overlay
                    fb.add_trace(go.Scatter(
                        x=days, y=peaks,
                        name="2026 Peak",
                        mode="lines+markers",
                        line=dict(color="#dc2626",
                                  width=2, dash="dot"),
                        marker=dict(size=5, color="#dc2626")))
                    fb.update_layout(
                        title=f"{mn} 2026 vs 2025 (Bar)",
                        xaxis_title="Day",
                        yaxis_title="Load (MW)",
                        xaxis=dict(tickmode="linear",
                                   tick0=1, dtick=1),
                        barmode="group",
                        height=370, **BL)
                    st.plotly_chart(fb, use_container_width=True)

                # ── LINE CHART ────────────────────────────────
                with lc:
                    fl2 = go.Figure()
                    fl2.add_trace(go.Scatter(
                        x=days, y=avgs,
                        name=f"{mn} 2026 Forecast",
                        line=dict(color=color, width=2.5),
                        mode="lines+markers",
                        marker=dict(size=5),
                        fill="tozeroy",
                        fillcolor=fill))
                    if any(v is not None for v in prev_avgs):
                        fl2.add_trace(go.Scatter(
                            x=days, y=prev_avgs,
                            name=f"{mn} 2025 Actual",
                            line=dict(
                                color=YEAR_COLORS[2025],
                                width=1.8, dash="dash"),
                            mode="lines+markers",
                            marker=dict(size=4)))
                    fl2.add_trace(go.Scatter(
                        x=days, y=peaks,
                        name="2026 Peak",
                        line=dict(color="#dc2626",
                                  width=1.5, dash="dot"),
                        mode="lines"))
                    fl2.update_layout(
                        title=f"{mn} 2026 vs 2025 (Line)",
                        xaxis_title="Day",
                        yaxis_title="Load (MW)",
                        xaxis=dict(tickmode="linear",
                                   tick0=1, dtick=1),
                        height=370, **BL)
                    st.plotly_chart(fl2, use_container_width=True)

                # ── DAY PICKER ────────────────────────────────
                st.markdown(
                    f"**🔍 View a specific day in {mn} 2026**")
                sel = st.slider(
                    f"Select day — {mn}",
                    min_value=1, max_value=ndays, value=1,
                    key=f"sl_{mo}")

                drow = df_mo[df_mo["day"] == sel]
                if len(drow) > 0:
                    dr   = drow.iloc[0]
                    dp   = g24(dr, "pred")
                    dp   = [v if v is not None else 0 for v in dp]
                    vdp  = [v for v in dp if v > 0]

                    # Day KPIs
                    d1, d2, d3 = st.columns(3)
                    if vdp:
                        d1.metric("Avg Load",
                                  f"{np.mean(vdp):,.0f} MW")
                        d2.metric("Peak Load",
                                  f"{max(vdp):,.0f} MW")
                        d3.metric("Peak Hour",
                                  f"{dp.index(max(vdp)):02d}:00")

                    # Day bar + line side by side
                    db2, dl2 = st.columns(2)
                    with db2:
                        fdb = go.Figure()
                        fdb.add_trace(go.Bar(
                            x=hlbl, y=dp,
                            name="Hourly Load",
                            marker_color=color, opacity=0.85))
                        fdb.update_layout(
                            title=f"{mn} {sel}, 2026 — Hourly (Bar)",
                            xaxis_title="Hour",
                            yaxis_title="Load (MW)",
                            height=290, **BL)
                        st.plotly_chart(fdb,
                            use_container_width=True)
                    with dl2:
                        fdl = go.Figure()
                        fdl.add_trace(go.Scatter(
                            x=hlbl, y=dp,
                            name="Hourly Load",
                            line=dict(color=color, width=2.5),
                            mode="lines+markers",
                            marker=dict(size=7,
                                        symbol="diamond"),
                            fill="tozeroy",
                            fillcolor=fill))
                        if vdp:
                            ph = dp.index(max(vdp))
                            fdl.add_annotation(
                                x=hlbl[ph], y=max(vdp),
                                text=f"Peak: {max(vdp):,.0f}",
                                showarrow=True, arrowhead=2,
                                font=dict(color=color, size=10),
                                bgcolor="white",
                                bordercolor=color,
                                borderwidth=1, ay=-35)
                        fdl.update_layout(
                            title=f"{mn} {sel}, 2026 — Hourly (Line)",
                            xaxis_title="Hour",
                            yaxis_title="Load (MW)",
                            height=290, **BL)
                        st.plotly_chart(fdl,
                            use_container_width=True)

                st.divider()

    # ══════════════════════════════════════════════════════════
    # TAB 2 — 5-YEAR COMPARISON
    # Data source: history_summary.csv + history_daily.csv
    #              + monthly forecast CSVs (all from Colab)
    # ══════════════════════════════════════════════════════════
    with tab2:
        st.subheader("📊 5-Year Comparison — 2020 to 2026")

        if df_hist is None:
            no_data_card(
                "5-year comparison data will appear here after "
                "running TN_FORECAST_COLAB.py. "
                "Colab pushes history_summary.csv and "
                "history_daily.csv to GitHub automatically."
            )
        else:
            # Normalise columns
            df_hist.columns = df_hist.columns.str.lower()

            sel_mn = st.selectbox(
                "Select Month",
                ["April", "May", "June"],
                key="s5y")
            sel_mo = next(
                k for k, v in MONTH_NAMES.items()
                if v == sel_mn)
            color  = MONTH_COLORS[sel_mo]
            ndays  = calendar.monthrange(2026, sel_mo)[1]
            df_mo26 = load_mo(sel_mo)

            # ── Chart 1: Daily line per year ───────────────────
            st.markdown(
                f"**Daily Avg Load — {sel_mn} "
                f"(each year as a line)**")
            fig1 = go.Figure()

            # Historical years from history_daily.csv
            if df_hist_d is not None and len(df_hist_d) > 0:
                df_hist_d_norm = df_hist_d.copy()
                df_hist_d_norm.columns = (
                    df_hist_d_norm.columns.str.lower())
                years_avail = sorted(
                    pd.to_numeric(
                        df_hist_d_norm["year"],
                        errors="coerce").dropna().unique()
                )
                for yr in years_avail:
                    yr_int = int(yr)
                    sub = df_hist_d_norm[
                        (pd.to_numeric(
                            df_hist_d_norm["year"],
                            errors="coerce") == yr_int) &
                        (pd.to_numeric(
                            df_hist_d_norm["month"],
                            errors="coerce") == sel_mo)
                    ]
                    if len(sub) == 0:
                        continue
                    sub = sub.sort_values("day")
                    ds  = pd.to_numeric(
                        sub["day"], errors="coerce").tolist()
                    av  = pd.to_numeric(
                        sub["avg_load"],
                        errors="coerce").tolist()
                    fig1.add_trace(go.Scatter(
                        x=ds, y=av,
                        name=str(yr_int),
                        line=dict(
                            color=YEAR_COLORS.get(yr_int, "#888"),
                            width=1.8,
                            dash="dot" if yr_int < 2023
                            else "solid"),
                        mode="lines+markers",
                        marker=dict(size=4),
                        opacity=0.85))

            # 2026 forecast line
            if df_mo26 is not None and len(df_mo26) > 0:
                df_s = df_mo26.sort_values("day")
                fig1.add_trace(go.Scatter(
                    x=df_s["day"].tolist(),
                    y=pd.to_numeric(
                        df_s["predicted_avg"],
                        errors="coerce").tolist(),
                    name="2026 Forecast",
                    line=dict(
                        color=YEAR_COLORS[2026], width=3),
                    mode="lines+markers",
                    marker=dict(size=7, symbol="diamond"),
                    fill="tozeroy",
                    fillcolor="rgba(220,38,38,0.07)"))
            else:
                fig1.add_annotation(
                    x=ndays // 2, y=0.5, yref="paper",
                    text="<b>2026 forecast — run Colab to see</b>",
                    showarrow=False,
                    font=dict(size=12, color="#dc2626"),
                    bgcolor="rgba(255,255,255,0.9)",
                    bordercolor="#dc2626", borderwidth=1)

            fig1.update_layout(
                title=f"{sel_mn} — Daily Avg Load 2020–2026",
                xaxis_title=f"Day of {sel_mn}",
                yaxis_title="Avg Load (MW)",
                xaxis=dict(tickmode="linear", tick0=1,
                           dtick=1, range=[0, ndays + 1]),
                height=430, **BL)
            st.plotly_chart(fig1, use_container_width=True)

            # ── Chart 2: Monthly avg bar per year ──────────────
            # KEY FIX: 2026 bar always included if data exists
            st.markdown(
                f"**Monthly Avg & Peak — {sel_mn} "
                f"(bar per year)**")

            yr_labels, yr_avgs, yr_peaks, yr_cols = [], [], [], []

            # Historical years from history_summary.csv
            for _, row in df_hist.iterrows():
                try:
                    yr  = int(float(row["year"]))
                    mo_ = int(float(row["month"]))
                except Exception:
                    continue
                if mo_ != sel_mo:
                    continue
                avg_v  = sf(row.get("avg_load"))
                peak_v = sf(row.get("peak_load"))
                if avg_v is None:
                    continue
                yr_labels.append(str(yr))
                yr_avgs.append(avg_v)
                yr_peaks.append(peak_v)
                yr_cols.append(YEAR_COLORS.get(yr, "#888"))

            # 2026 forecast — ALWAYS add if available
            if df_mo26 is not None and len(df_mo26) > 0:
                avg26 = sf(pd.to_numeric(
                    df_mo26["predicted_avg"],
                    errors="coerce").mean())
                pk26  = sf(pd.to_numeric(
                    df_mo26["predicted_peak"],
                    errors="coerce").max())
                if avg26 is not None:
                    yr_labels.append("2026\n(Forecast)")
                    yr_avgs.append(avg26)
                    yr_peaks.append(pk26)
                    yr_cols.append(YEAR_COLORS[2026])
            else:
                # Show placeholder bar so axis is consistent
                yr_labels.append("2026\n(Pending)")
                yr_avgs.append(None)
                yr_peaks.append(None)
                yr_cols.append("#e5e7eb")

            fig2 = go.Figure()
            # Bar: monthly avg
            fig2.add_trace(go.Bar(
                x=yr_labels, y=yr_avgs,
                name="Monthly Avg Load",
                marker_color=yr_cols,
                opacity=0.88,
                text=[
                    f"{v:,.0f}" if v is not None
                    else "Run Colab"
                    for v in yr_avgs
                ],
                textposition="outside"))
            # Line: monthly peak
            fig2.add_trace(go.Scatter(
                x=yr_labels, y=yr_peaks,
                name="Monthly Peak",
                mode="lines+markers",
                line=dict(color="#dc2626", width=2, dash="dot"),
                marker=dict(
                    size=9, symbol="triangle-up",
                    color="#dc2626")))
            fig2.update_layout(
                title=(f"{sel_mn} — Monthly Avg & Peak "
                       f"by Year (Bar)"),
                xaxis_title="Year",
                yaxis_title="Load (MW)",
                height=400, **BL)
            st.plotly_chart(fig2, use_container_width=True)

            # ── Chart 3: Avg hourly profile by year ────────────
            st.markdown(
                f"**Avg Hourly Load Profile — "
                f"{sel_mn} (each year)**")
            fig3 = go.Figure()

            # Historical profiles from history_summary
            # (profile stored as avg_h00..avg_h23 columns)
            for _, row in df_hist.iterrows():
                try:
                    yr  = int(float(row["year"]))
                    mo_ = int(float(row["month"]))
                except Exception:
                    continue
                if mo_ != sel_mo:
                    continue
                hourly = [sf(row.get(f"avg_h{h:02d}"))
                          for h in range(24)]
                if not any(v is not None for v in hourly):
                    continue
                fig3.add_trace(go.Scatter(
                    x=list(range(24)), y=hourly,
                    name=str(yr),
                    line=dict(
                        color=YEAR_COLORS.get(yr, "#888"),
                        width=1.8,
                        dash="dot" if yr < 2023 else "solid"),
                    mode="lines",
                    opacity=0.88))

            # 2026 hourly profile
            if df_mo26 is not None and len(df_mo26) > 0:
                h26 = []
                recs = df_mo26.to_dict("records")
                for h in range(24):
                    vals = [
                        sf(r.get(f"pred_h{h:02d}"))
                        for r in recs
                        if sf(r.get(f"pred_h{h:02d}"))
                        is not None
                    ]
                    h26.append(
                        float(np.mean(vals)) if vals else None)
                if any(v is not None for v in h26):
                    fig3.add_trace(go.Scatter(
                        x=list(range(24)), y=h26,
                        name="2026 Forecast",
                        line=dict(
                            color=YEAR_COLORS[2026], width=3),
                        mode="lines+markers",
                        marker=dict(size=6,
                                    symbol="diamond")))

            fig3.update_layout(
                title=(f"{sel_mn} — Avg Hourly Profile "
                       f"by Year"),
                xaxis_title="Hour",
                yaxis_title="Avg Load (MW)",
                xaxis=dict(
                    tickmode="array",
                    tickvals=list(range(24)),
                    ticktext=[f"{h:02d}:00"
                              for h in range(24)]),
                height=390, **BL)
            st.plotly_chart(fig3, use_container_width=True)

            # ── Growth table ────────────────────────────────────
            st.subheader(f"{sel_mn} — Year-on-Year Growth Table")

            rows_tbl = []
            # Build ordered list: historical years + 2026
            ordered = []
            for _, row in df_hist.sort_values("year").iterrows():
                try:
                    yr  = int(float(row["year"]))
                    mo_ = int(float(row["month"]))
                except Exception:
                    continue
                if mo_ != sel_mo:
                    continue
                ordered.append({
                    "year": yr,
                    "avg":  sf(row.get("avg_load")),
                    "peak": sf(row.get("peak_load")),
                    "label": str(yr)
                })

            # Add 2026
            if df_mo26 is not None and len(df_mo26) > 0:
                avg26 = sf(pd.to_numeric(
                    df_mo26["predicted_avg"],
                    errors="coerce").mean())
                pk26  = sf(pd.to_numeric(
                    df_mo26["predicted_peak"],
                    errors="coerce").max())
                ordered.append({
                    "year": 2026,
                    "avg":  avg26,
                    "peak": pk26,
                    "label": "2026 (Forecast)"
                })

            for i, item in enumerate(ordered):
                av  = item["avg"]
                pk  = item["peak"]
                if i > 0 and av and ordered[i-1]["avg"]:
                    prev = ordered[i-1]["avg"]
                    yoy  = f"{(av - prev) / prev * 100:+.1f}%"
                else:
                    yoy = "—"
                rows_tbl.append({
                    "Year":           item["label"],
                    "Avg Load (MW)":  f"{av:,.0f}" if av else "—",
                    "Peak Load (MW)": f"{pk:,.0f}" if pk else "—",
                    "YoY Growth":     yoy,
                })
            st.dataframe(
                pd.DataFrame(rows_tbl),
                use_container_width=True,
                hide_index=True)

    # ══════════════════════════════════════════════════════════
    # TAB 3 — DAILY FORECAST
    # Data source: rolling_results.csv from Colab
    # ══════════════════════════════════════════════════════════
    with tab3:
        st.subheader("📈 Daily Forecast")

        if len(df_past) == 0 and len(df_future) == 0:
            no_data_card(
                "Daily forecast charts will appear here after "
                "you run TN_FORECAST_COLAB.py."
            )
        else:
            # Latest predicted-vs-actual day
            st.markdown("#### Today — Predicted vs Actual")
            if len(df_past) > 0:
                row    = df_past.iloc[-1]
                pred   = g24(row, "pred")
                actual = g24(row, "actual")
                mv     = sf(row.get("mape"))
                rv     = sf(row.get("rmse"))
                vp     = [v for v in pred if v is not None]

                m1, m2, m3, m4 = st.columns(4)
                if mv:
                    c = ("green" if mv < 5 else
                         "orange" if mv < 10 else "red")
                    m1.markdown(
                        f"<h3 style='color:{c}'>{mv:.2f}%</h3>"
                        f"<p style='color:#64748b;"
                        f"font-size:12px'>MAPE</p>",
                        unsafe_allow_html=True)
                if rv:
                    m2.markdown(
                        f"<h3>{rv:.0f} MW</h3>"
                        f"<p style='color:#64748b;"
                        f"font-size:12px'>RMSE</p>",
                        unsafe_allow_html=True)
                if vp:
                    m3.markdown(
                        f"<h3 style='color:#2563eb'>"
                        f"{max(vp):,.0f} MW</h3>"
                        f"<p style='color:#64748b;"
                        f"font-size:12px'>Peak</p>",
                        unsafe_allow_html=True)
                m4.markdown(
                    f"<h3>{row['date']}</h3>"
                    f"<p style='color:#64748b;"
                    f"font-size:12px'>Date</p>",
                    unsafe_allow_html=True)

                ft = go.Figure()
                if any(v is not None for v in actual):
                    ft.add_trace(go.Scatter(
                        x=hlbl, y=actual, name="Actual",
                        line=dict(color="#16a34a", width=3),
                        mode="lines+markers",
                        marker=dict(size=7),
                        fill="tozeroy",
                        fillcolor="rgba(22,163,74,0.07)"))
                ft.add_trace(go.Scatter(
                    x=hlbl, y=pred, name="Predicted",
                    line=dict(color="#2563eb", width=2.5,
                              dash="dash"),
                    mode="lines+markers",
                    marker=dict(size=6)))
                ft.update_layout(
                    title=f"Predicted vs Actual — {row['date']}",
                    xaxis_title="Hour",
                    yaxis_title="Load (MW)",
                    height=380, **BL)
                st.plotly_chart(ft, use_container_width=True)
            else:
                st.info("No actual data available yet.")

            # Tomorrow
            st.divider()
            st.markdown("#### Tomorrow — Next Day Forecast")
            if len(df_future) > 0:
                nr   = df_future.iloc[0]
                np_  = g24(nr, "pred")
                vnp  = [v for v in np_ if v is not None]

                n1, n2, n3, n4 = st.columns(4)
                if vnp:
                    n1.markdown(
                        f"<h3 style='color:#ea580c'>"
                        f"{max(vnp):,.0f} MW</h3>"
                        f"<p style='color:#64748b;"
                        f"font-size:12px'>Peak</p>",
                        unsafe_allow_html=True)
                    n2.markdown(
                        f"<h3>{min(vnp):,.0f} MW</h3>"
                        f"<p style='color:#64748b;"
                        f"font-size:12px'>Min</p>",
                        unsafe_allow_html=True)
                    n3.markdown(
                        f"<h3>{np.mean(vnp):,.0f} MW</h3>"
                        f"<p style='color:#64748b;"
                        f"font-size:12px'>Average</p>",
                        unsafe_allow_html=True)
                n4.markdown(
                    f"<h3 style='color:#7c3aed'>"
                    f"{nr['date']}</h3>"
                    f"<p style='color:#64748b;"
                    f"font-size:12px'>Date</p>",
                    unsafe_allow_html=True)

                fn2 = go.Figure()
                fn2.add_trace(go.Scatter(
                    x=hlbl, y=np_,
                    name="Forecast",
                    line=dict(color="#ea580c", width=3),
                    mode="lines+markers",
                    marker=dict(size=8, symbol="diamond"),
                    fill="tozeroy",
                    fillcolor="rgba(234,88,12,0.07)"))
                if vnp:
                    ph = np_.index(max(vnp))
                    fn2.add_annotation(
                        x=hlbl[ph], y=max(vnp),
                        text=f"Peak: {max(vnp):,.0f} MW",
                        showarrow=True, arrowhead=2,
                        arrowcolor="#ea580c",
                        font=dict(color="#ea580c", size=11),
                        bgcolor="white",
                        bordercolor="#ea580c",
                        borderwidth=1.5, ay=-40)
                fn2.update_layout(
                    title=f"Tomorrow — {nr['date']}",
                    xaxis_title="Hour",
                    yaxis_title="Load (MW)",
                    height=380, **BL)
                st.plotly_chart(fn2, use_container_width=True)
            else:
                st.info("No future forecast rows available.")

    # ══════════════════════════════════════════════════════════
    # TAB 4 — ACCURACY
    # ══════════════════════════════════════════════════════════
    with tab4:
        st.subheader("🎯 Model Accuracy")
        if len(df_m) == 0:
            no_data_card(
                "Accuracy charts appear once actual load data "
                "is available for comparison. "
                "Run Colab first."
            )
        else:
            c1, c2 = st.columns(2)
            with c1:
                fm = px.line(
                    df_m, x="date", y="mape",
                    title="MAPE % Over Days",
                    markers=True,
                    color_discrete_sequence=["#ea580c"])
                fm.add_hline(
                    y=df_m["mape"].mean(),
                    line_dash="dash", line_color="red",
                    annotation_text=(
                        f"Avg: {df_m['mape'].mean():.2f}%"))
                fm.update_layout(
                    height=310,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fm, use_container_width=True)
            with c2:
                fr = px.line(
                    df_m, x="date", y="rmse",
                    title="RMSE (MW) Over Days",
                    markers=True,
                    color_discrete_sequence=["#7c3aed"])
                fr.add_hline(
                    y=df_m["rmse"].mean(),
                    line_dash="dash", line_color="red",
                    annotation_text=(
                        f"Avg: {df_m['rmse'].mean():.0f} MW"))
                fr.update_layout(
                    height=310,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fr, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 5 — ALL RESULTS
    # ══════════════════════════════════════════════════════════
    with tab5:
        st.subheader("📋 All Results")
        if df_roll is None or len(df_roll) == 0:
            no_data_card(
                "Full results table appears after running Colab."
            )
        else:
            st.caption(f"{len(df_roll)} predicted days total")
            show_c = [
                "date", "month_name", "day", "mape", "rmse",
                "predicted_avg", "predicted_peak",
                "actual_avg", "actual_peak"
            ]
            avail = [c for c in show_c
                     if c in df_roll.columns]
            ds = df_roll[avail].copy()
            for col in ["mape", "rmse", "predicted_avg",
                        "predicted_peak", "actual_avg",
                        "actual_peak"]:
                if col in ds.columns:
                    ds[col] = pd.to_numeric(
                        ds[col], errors="coerce").round(1)
            ds.columns = [c.replace("_", " ").title()
                          for c in ds.columns]
            st.dataframe(
                ds,
                use_container_width=True,
                hide_index=True,
                height=480)
            st.download_button(
                "⬇ Download Results CSV",
                df_roll.to_csv(index=False).encode(),
                "TN_Q2_2026_results.csv",
                "text/csv",
                use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════
def main():
    for k in ["logged_in", "username", "role"]:
        if k not in st.session_state:
            st.session_state[k] = (
                False if k == "logged_in" else None)
    if not st.session_state["logged_in"]:
        show_login()
        return
    show_sidebar(
        st.session_state["username"],
        st.session_state["role"])
    show_dashboard(
        st.session_state["username"],
        st.session_state["role"])


if __name__ == "__main__":
    main()
