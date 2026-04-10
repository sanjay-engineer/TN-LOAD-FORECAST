# ================================================================
#  TN INTELLIGENT LOAD FORECASTING — STREAMLIT WEB APP  v3.0
#  ROLLING 3-MONTH FORECAST: APRIL · MAY · JUNE 2026
#
#  FEATURES IN THIS VERSION:
#    ✅ Monthly Prediction: Bar chart + Line chart (both together)
#    ✅ Per-month separate sections with daily bar + line graphs
#    ✅ Day selector → hourly 24h prediction line graph per month
#    ✅ Month vs Previous Year (2026 vs 2025) comparison
#    ✅ 5-Year Comparison (2020–2025 actual + 2026 forecast)
#    ✅ All Results data table with download
#    ✅ Login / Register / Admin system
#    ✅ GitHub auto-sync + manual CSV upload fallback
#    ✅ Historical CSV upload for 5-year analysis
#
#  TABS:
#    Tab 1 — 📊 Monthly Predictions   ← Bar + Line + per-month detail
#    Tab 2 — 📅 vs Previous Year      ← 2026 vs 2025
#    Tab 3 — 📈 5-Year Comparison     ← 2020–2026
#    Tab 4 — 🎯 Accuracy             ← MAPE / RMSE
#    Tab 5 — 📋 All Results           ← Full table
#    Tab 6 — 📖 About
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import hashlib, json, os, calendar, requests
from datetime import datetime, date
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide",
)

# ── Constants ─────────────────────────────────────────────────
GITHUB_USER   = "sanjay-engineer"
GITHUB_REPO   = "TN-LOAD-FORECAST"
GITHUB_BRANCH = "main"
GITHUB_RAW    = (f"https://raw.githubusercontent.com/"
                 f"{GITHUB_USER}/{GITHUB_REPO}/"
                 f"{GITHUB_BRANCH}/results")

USERS_FILE = "users.json"
SHARED_DIR = "shared_results"
os.makedirs(SHARED_DIR, exist_ok=True)

LOCAL_RESULTS = os.path.join(SHARED_DIR, "rolling_results.csv")
LOCAL_HISTORY = os.path.join(SHARED_DIR, "history_updated.csv")
LOCAL_RAW_CSV = os.path.join(SHARED_DIR, "raw_history.csv")

FORECAST_MONTHS = [(2026, 4), (2026, 5), (2026, 6)]
MONTH_NAMES     = {4: 'April', 5: 'May', 6: 'June'}
MONTH_COLORS    = {4: '#2563eb', 5: '#16a34a', 6: '#ea580c'}

# 5-year history range (actual data years)
HISTORY_YEARS   = [2020, 2021, 2022, 2023, 2024, 2025]
YEAR_COLORS     = {
    2020: '#94a3b8', 2021: '#64748b',
    2022: '#f59e0b', 2023: '#8b5cf6',
    2024: '#06b6d4', 2025: '#ec4899',
    2026: '#ef4444',   # forecast year
}

# ── Helpers ───────────────────────────────────────────────────
def hex_to_rgba(hex_color: str, alpha: float = 0.10) -> str:
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'

def safe_float(val):
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except Exception:
        return None

def get_24hrs(row, prefix):
    return [safe_float(row.get(f'{prefix}_h{h:02d}')) for h in range(24)]

def hourly_col(row, h):
    return safe_float(row.get(f'pred_h{h:02d}'))

CHART_LAYOUT = dict(
    hovermode="x unified",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    yaxis=dict(tickformat=","),
)


# ================================================================
#  USER SYSTEM
# ================================================================
def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def register_user(username, password):
    if len(username) < 3:  return False, "Username too short (min 3)"
    if len(username) > 20: return False, "Username too long (max 20)"
    if not username.replace("_", "").isalnum():
        return False, "Letters, numbers and underscore only"
    if len(password) < 6: return False, "Password min 6 characters"
    users = load_users()
    if username.lower() in [u.lower() for u in users]:
        return False, "Username already taken"
    users[username] = {
        "password": hash_pw(password), "role": "viewer",
        "created": str(datetime.now().date()), "last_login": None,
    }
    save_users(users)
    return True, "Account created — login now"

def login_user(username, password):
    users = load_users()
    match = next((u for u in users if u.lower() == username.lower()), None)
    if not match: return False, "Username not found", None
    if users[match]["password"] != hash_pw(password):
        return False, "Wrong password", None
    users[match]["last_login"] = str(datetime.now())
    save_users(users)
    return True, match, users[match].get("role", "viewer")

def make_admin(username, secret):
    if secret != "TN2025Admin":
        return False, "Wrong admin secret key"
    users = load_users()
    match = next((u for u in users if u.lower() == username.lower()), None)
    if not match: return False, f"User '{username}' not found"
    users[match]["role"] = "admin"
    save_users(users)
    return True, f"'{match}' is now Admin"


# ================================================================
#  DATA LOADING
# ================================================================
@st.cache_data(ttl=60)
def fetch_github(filename):
    url = f"{GITHUB_RAW}/{filename}"
    try:
        r = requests.get(url, timeout=10)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None

def load_results():
    data = fetch_github("rolling_results.csv")
    if data:
        try:
            return pd.read_csv(StringIO(data)), "github"
        except Exception:
            pass
    if os.path.exists(LOCAL_RESULTS):
        return pd.read_csv(LOCAL_RESULTS), "local"
    return None, None

def load_monthly(month_name, year):
    fname = f"{month_name.lower()}_{year}_results.csv"
    data  = fetch_github(fname)
    if data:
        try:
            return pd.read_csv(StringIO(data))
        except Exception:
            pass
    local = os.path.join(SHARED_DIR, fname)
    if os.path.exists(local):
        return pd.read_csv(local)
    return None

@st.cache_data(ttl=300)
def load_raw_history():
    """Load the original history CSV for 5-year comparison."""
    if os.path.exists(LOCAL_RAW_CSV):
        df = pd.read_csv(LOCAL_RAW_CSV)
        df.columns = [c.strip() for c in df.columns]
        df['Datetime'] = pd.to_datetime(df['Datetime'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Datetime', 'load']).sort_values('Datetime').reset_index(drop=True)
        return df
    return None


# ================================================================
#  LOGIN PAGE
# ================================================================
def show_login_page():
    st.markdown("""
    <div style='text-align:center;padding:40px 0 20px 0'>
        <div style='font-size:52px'>⚡</div>
        <h2 style='color:#2563eb;margin:10px 0 4px 0'>
            TN Intelligent Load Forecasting</h2>
        <p style='color:#64748b;font-size:14px'>
            Tamil Nadu Power Grid — Rolling LSTM Forecast System</p>
    </div>""", unsafe_allow_html=True)
    st.divider()

    t1, t2, t3 = st.tabs(["🔑 Login", "📝 Register", "🔧 Admin Setup"])

    with t1:
        st.subheader("Login")
        with st.form("lf"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            s = st.form_submit_button("Login",
                use_container_width=True, type="primary")
        if s:
            if not u or not p:
                st.error("Enter username and password")
            else:
                ok, res, role = login_user(u, p)
                if ok:
                    st.session_state.update(
                        logged_in=True, username=res, role=role)
                    st.rerun()
                else:
                    st.error(f"❌ {res}")

    with t2:
        st.subheader("Create Account")
        with st.form("rf"):
            nu  = st.text_input("Username")
            np_ = st.text_input("Password", type="password")
            cp  = st.text_input("Confirm Password", type="password")
            rb  = st.form_submit_button("Create Account",
                use_container_width=True, type="primary")
        if rb:
            if not nu or not np_ or not cp:
                st.error("Fill all fields")
            elif np_ != cp:
                st.error("Passwords do not match")
            else:
                ok, msg = register_user(nu, np_)
                (st.success if ok else st.error)(msg)

    with t3:
        st.subheader("Make Yourself Admin")
        st.info("Secret Key: **TN2025Admin**")
        with st.form("af"):
            au = st.text_input("Your Username")
            ak = st.text_input("Admin Secret Key", type="password")
            ab = st.form_submit_button("Make Admin",
                use_container_width=True)
        if ab:
            ok, msg = make_admin(au, ak)
            (st.success if ok else st.error)(msg)


# ================================================================
#  SIDEBAR
# ================================================================
def show_sidebar(username, role):
    with st.sidebar:
        bg = "#7c3aed" if role == "admin" else "#2563eb"
        st.markdown(
            f"<div style='background:{bg};color:white;"
            f"padding:12px 16px;border-radius:10px;"
            f"margin-bottom:10px'>"
            f"<b>👤 {username}</b><br>"
            f"<span style='font-size:12px;opacity:.85'>"
            f"{'Admin ✓' if role=='admin' else 'Viewer'}"
            f"</span></div>",
            unsafe_allow_html=True)
        st.divider()

        st.subheader("🔗 Data Source")
        try:
            r = requests.head(
                f"{GITHUB_RAW}/rolling_results.csv", timeout=5)
            github_ok = r.status_code == 200
        except Exception:
            github_ok = False

        if github_ok:
            st.success("✅ GitHub — Auto sync")
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("⚠ GitHub not connected")

        st.divider()

        # ── History CSV upload (for 5-year comparison) ────────
        st.subheader("📂 History Data (5-Year)")
        st.caption("Upload your Data_2020-2026 CSV for 5-year comparison")
        raw_file = st.file_uploader(
            "Data__2020-2026_3rd_month_.csv",
            type=["csv"], key="raw_hist")
        if raw_file:
            raw_df = pd.read_csv(raw_file)
            raw_df.to_csv(LOCAL_RAW_CSV, index=False)
            st.cache_data.clear()
            st.success("✓ History data uploaded!")

        if os.path.exists(LOCAL_RAW_CSV):
            st.success("✅ History data ready")
        else:
            st.info("Upload history CSV to enable 5-year comparison")

        st.divider()

        if role == "admin":
            with st.expander("📂 Forecast Results Upload"):
                rf = st.file_uploader("rolling_results.csv",
                                       type=["csv"], key="ru")
                if rf:
                    pd.read_csv(rf).to_csv(LOCAL_RESULTS, index=False)
                    st.success("✓ Uploaded")

                for yr, mo in FORECAST_MONTHS:
                    mn  = MONTH_NAMES[mo]
                    key = f"mf_{mo}"
                    mf  = st.file_uploader(
                        f"{mn.lower()}_{yr}_results.csv",
                        type=["csv"], key=key)
                    if mf:
                        path = os.path.join(
                            SHARED_DIR,
                            f"{mn.lower()}_{yr}_results.csv")
                        pd.read_csv(mf).to_csv(path, index=False)
                        st.success(f"✓ {mn} uploaded")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.update(
                logged_in=False, username=None, role=None)
            st.rerun()


# ================================================================
#  CHART BUILDERS
# ================================================================

def build_monthly_bar_and_line(all_month_data):
    """
    Returns TWO figures:
      fig_bar  — bar chart of monthly avg + peak
      fig_line — combined daily avg line chart for all months
    """
    months_done = [(yr, mo) for yr, mo in FORECAST_MONTHS
                   if (yr, mo) in all_month_data]

    # ── BAR CHART ─────────────────────────────────────────────
    m_labels  = [f"{MONTH_NAMES[mo]} {yr}" for yr, mo in months_done]
    m_avgs    = [all_month_data[k]['predicted_avg'].mean() for k in months_done]
    m_peaks   = [all_month_data[k]['predicted_peak'].max() for k in months_done]
    m_colors  = [MONTH_COLORS[mo] for _, mo in months_done]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=m_labels, y=m_avgs, name="Monthly Avg Load",
        marker_color=m_colors, opacity=0.85,
        text=[f"{v:,.0f}" for v in m_avgs],
        textposition='outside'))
    fig_bar.add_trace(go.Scatter(
        x=m_labels, y=m_peaks, name="Monthly Peak Load",
        mode="markers+lines",
        marker=dict(size=14, symbol="diamond",
                    color=m_colors, line=dict(color='white', width=2)),
        line=dict(color="#ef4444", width=2.5, dash="dot")))
    fig_bar.update_layout(
        title="📊 Monthly Avg & Peak Load — April · May · June 2026",
        yaxis_title="Load (MW)", height=380,
        yaxis=dict(tickformat=","),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        bargap=0.30)

    # ── LINE CHART ────────────────────────────────────────────
    fig_line = go.Figure()
    x_offset = 0
    x_ticks_vals, x_ticks_text = [], []

    for yr, mo in months_done:
        mn    = MONTH_NAMES[mo]
        color = MONTH_COLORS[mo]
        df_mo = all_month_data[(yr, mo)].sort_values('day')
        days  = df_mo['day'].tolist()
        avgs  = df_mo['predicted_avg'].tolist()
        peaks = df_mo['predicted_peak'].tolist()
        x     = [x_offset + d for d in days]

        fig_line.add_trace(go.Scatter(
            x=x, y=avgs, name=f"{mn} Avg",
            line=dict(color=color, width=2.5),
            mode="lines+markers", marker=dict(size=4),
            fill="tozeroy", fillcolor=hex_to_rgba(color, 0.05)))
        fig_line.add_trace(go.Scatter(
            x=x, y=peaks, name=f"{mn} Peak",
            line=dict(color=color, width=1.5, dash="dot"),
            mode="lines+markers",
            marker=dict(size=4, symbol="triangle-up"),
            opacity=0.75))

        # Month label annotation
        mid_x = x_offset + len(days) / 2
        fig_line.add_annotation(
            x=mid_x, y=min(avgs) * 0.98,
            text=f"<b>{mn}</b>",
            showarrow=False,
            font=dict(color=color, size=12))
        if x_offset > 0:
            fig_line.add_vline(
                x=x_offset + 0.5, line_dash="dash",
                line_color="gray", opacity=0.4)

        # Tick labels at month start
        x_ticks_vals.append(x_offset + 1)
        x_ticks_text.append(f"{mn[:3]} 1")
        x_offset += calendar.monthrange(yr, mo)[1]

    fig_line.update_layout(
        title="📈 Daily Load Trend — April · May · June 2026 (Avg & Peak)",
        xaxis_title="Day (Apr 1 → Jun 30)",
        yaxis_title="Load (MW)", height=400,
        xaxis=dict(tickmode='array',
                   tickvals=x_ticks_vals, ticktext=x_ticks_text),
        **CHART_LAYOUT)
    return fig_bar, fig_line


def build_per_month_detail(yr, mo, df_mo):
    """
    Bar chart (daily peak) + Line chart (daily avg) for ONE month.
    Returns (fig_bar, fig_line).
    """
    color = MONTH_COLORS[mo]
    mn    = MONTH_NAMES[mo]
    df_mo = df_mo.sort_values('day')
    days  = df_mo['day'].tolist()
    avgs  = df_mo['predicted_avg'].tolist()
    peaks = df_mo['predicted_peak'].tolist()

    # Per-day min from hourly columns
    mins = []
    for _, row in df_mo.iterrows():
        vals = [hourly_col(row, h) for h in range(24)]
        vals = [v for v in vals if v is not None]
        mins.append(min(vals) if vals else None)

    # 7-day rolling avg
    roll7 = pd.Series(avgs).rolling(7, min_periods=1).mean().tolist()

    # ── BAR chart — daily peak ─────────────────────────────────
    fig_bar = go.Figure()
    bar_colors = [
        hex_to_rgba(color, 0.6) if v < max(peaks) else color
        for v in peaks
    ]
    fig_bar.add_trace(go.Bar(
        x=days, y=peaks, name="Daily Peak Load",
        marker_color=bar_colors,
        marker_line_color=color,
        marker_line_width=1.2))
    peak_day_i = peaks.index(max(peaks))
    fig_bar.add_annotation(
        x=days[peak_day_i], y=max(peaks),
        text=f"Month Peak<br>{max(peaks):,.0f} MW",
        showarrow=True, arrowhead=2,
        arrowcolor=color,
        font=dict(color=color, size=10),
        bgcolor="white", bordercolor=color,
        borderwidth=1.5, ay=-50)
    fig_bar.update_layout(
        title=f"📊 {mn} {yr} — Daily Peak Load (Bar Chart)",
        xaxis_title=f"Day of {mn}",
        yaxis_title="Peak Load (MW)", height=320,
        yaxis=dict(tickformat=","),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickmode='linear', tick0=1, dtick=2))

    # ── LINE chart — daily avg / peak / min ───────────────────
    fig_line = go.Figure()
    # Shaded min-peak band
    if None not in mins:
        fig_line.add_trace(go.Scatter(
            x=days + days[::-1],
            y=peaks + mins[::-1],
            fill='toself', fillcolor=hex_to_rgba(color, 0.08),
            line=dict(width=0), name='Min–Peak Band',
            showlegend=True))
    fig_line.add_trace(go.Scatter(
        x=days, y=avgs, name="Daily Avg Load",
        line=dict(color=color, width=2.5),
        mode="lines+markers", marker=dict(size=5)))
    fig_line.add_trace(go.Scatter(
        x=days, y=peaks, name="Daily Peak",
        line=dict(color=color, width=1.5, dash="dot"),
        mode="lines+markers",
        marker=dict(size=4, symbol="triangle-up")))
    if None not in mins:
        fig_line.add_trace(go.Scatter(
            x=days, y=mins, name="Daily Min",
            line=dict(color=color, width=1.5, dash="dot"),
            mode="lines+markers",
            marker=dict(size=4, symbol="triangle-down")))
    fig_line.add_trace(go.Scatter(
        x=days, y=roll7, name="7-Day Rolling Avg",
        line=dict(color="#dc2626", width=2, dash="dash")))
    fig_line.update_layout(
        title=f"📈 {mn} {yr} — Daily Load Trend (Line Chart)",
        xaxis_title=f"Day of {mn}",
        yaxis_title="Load (MW)", height=360,
        xaxis=dict(tickmode='linear', tick0=1, dtick=2),
        **CHART_LAYOUT)
    return fig_bar, fig_line


def build_hourly_day_chart(yr, mo, day, row):
    """Line graph for a specific day's 24-hour prediction."""
    color   = MONTH_COLORS[mo]
    mn      = MONTH_NAMES[mo]
    pred    = get_24hrs(row, 'pred')
    hlabels = [f"{h:02d}:00" for h in range(24)]
    valid   = [v for v in pred if v is not None]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hlabels, y=pred,
        name=f"{mn} {day} Forecast",
        line=dict(color=color, width=3),
        mode="lines+markers",
        marker=dict(size=8, symbol="circle",
                    line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor=hex_to_rgba(color, 0.10)))

    if valid:
        ph = pred.index(max(valid))
        fig.add_annotation(
            x=hlabels[ph], y=max(valid),
            text=f"Peak<br>{max(valid):,.0f} MW",
            showarrow=True, arrowhead=2,
            arrowcolor=color,
            font=dict(color=color, size=11),
            bgcolor="white", bordercolor=color,
            borderwidth=1.5, ay=-45)
        min_v = min(valid)
        pm    = pred.index(min_v)
        fig.add_annotation(
            x=hlabels[pm], y=min_v,
            text=f"Min<br>{min_v:,.0f} MW",
            showarrow=True, arrowhead=2,
            arrowcolor="#94a3b8",
            font=dict(color="#64748b", size=10),
            bgcolor="white", bordercolor="#94a3b8",
            borderwidth=1, ay=40)

    avg_v  = safe_float(row.get('predicted_avg')) or (np.mean(valid) if valid else 0)
    peak_v = safe_float(row.get('predicted_peak')) or (max(valid) if valid else 0)

    fig.update_layout(
        title=(f"⏱ {mn} {day}, {yr} — Hourly Forecast  |  "
               f"Avg: {avg_v:,.0f} MW  |  Peak: {peak_v:,.0f} MW"),
        xaxis_title="Hour of Day",
        yaxis_title="Load (MW)", height=380,
        xaxis=dict(tickmode='array',
                   tickvals=hlabels,
                   ticktext=hlabels),
        **CHART_LAYOUT)
    return fig


def build_prev_year_comparison(yr, mo, df_curr, df_raw):
    """Compare 2026 forecast with 2025 actual (daily + hourly profile)."""
    color   = MONTH_COLORS[mo]
    mn      = MONTH_NAMES[mo]
    prev_yr = yr - 1
    df_curr = df_curr.sort_values('day')

    curr_days = df_curr['day'].tolist()
    curr_avgs = df_curr['predicted_avg'].tolist()
    curr_peaks= df_curr['predicted_peak'].tolist()

    # Previous year from raw history
    prev_daily_avgs, prev_daily_peaks, prev_days = [], [], []
    prev_hourly = []

    if df_raw is not None:
        mask_prev = ((df_raw['Datetime'].dt.year  == prev_yr) &
                     (df_raw['Datetime'].dt.month == mo))
        sub_prev  = df_raw[mask_prev].copy()
        if len(sub_prev) > 0:
            daily_grp = sub_prev.groupby(sub_prev['Datetime'].dt.day)
            for day_num, grp in daily_grp:
                prev_days.append(day_num)
                prev_daily_avgs.append(grp['load'].mean())
                prev_daily_peaks.append(grp['load'].max())
            hp = sub_prev.groupby(sub_prev['Datetime'].dt.hour)['load']\
                         .mean().sort_index()
            prev_hourly = hp.tolist()

    # YoY growth
    n = min(len(curr_avgs), len(prev_daily_avgs))
    growth = ((np.mean(curr_avgs[:n]) - np.mean(prev_daily_avgs[:n])) /
              np.mean(prev_daily_avgs[:n]) * 100) if n > 0 else 0

    # ── Combined figure ────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f"Daily Avg Load — {mn} {yr} (Forecast) vs {mn} {prev_yr} (Actual)   "
            f"[YoY Growth: {growth:+.1f}%]",
            f"Average Hourly Profile — {mn} {yr} vs {mn} {prev_yr}"),
        vertical_spacing=0.14)

    # Row 1 — Daily avg
    fig.add_trace(go.Scatter(
        x=curr_days, y=curr_avgs,
        name=f"{mn} {yr} Forecast",
        line=dict(color=color, width=2.5),
        mode="lines+markers", marker=dict(size=6),
        fill="tozeroy", fillcolor=hex_to_rgba(color, 0.07)),
        row=1, col=1)
    if prev_daily_avgs:
        fig.add_trace(go.Scatter(
            x=prev_days, y=prev_daily_avgs,
            name=f"{mn} {prev_yr} Actual",
            line=dict(color="#94a3b8", width=2, dash="dash"),
            mode="lines+markers", marker=dict(size=5)),
            row=1, col=1)

    # Row 2 — Hourly profile
    hourly_curr = []
    for h in range(24):
        vals = [hourly_col(row, h)
                for _, row in df_curr.iterrows()]
        vals = [v for v in vals if v is not None]
        hourly_curr.append(np.mean(vals) if vals else 0)

    fig.add_trace(go.Scatter(
        x=list(range(24)), y=hourly_curr,
        name=f"{mn} {yr} Profile",
        line=dict(color=color, width=2.5),
        mode="lines+markers", marker=dict(size=6),
        fill="tozeroy", fillcolor=hex_to_rgba(color, 0.06)),
        row=2, col=1)
    if prev_hourly:
        fig.add_trace(go.Scatter(
            x=list(range(24)), y=prev_hourly,
            name=f"{mn} {prev_yr} Profile",
            line=dict(color="#94a3b8", width=2, dash="dash"),
            mode="lines+markers", marker=dict(size=5)),
            row=2, col=1)

    fig.update_xaxes(
        tickmode='array',
        tickvals=list(range(24)),
        ticktext=[f"{h:02d}:00" for h in range(24)],
        row=2, col=1)
    fig.update_yaxes(tickformat=",")
    fig.update_layout(
        height=680,
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.04))
    return fig, growth


def build_5year_comparison(mo, all_month_data, df_raw):
    """
    Multi-line chart: one line per year (2020–2025 actual + 2026 forecast).
    Returns (fig_daily, fig_monthly_bar).
    """
    mn = MONTH_NAMES[mo]

    # ── Monthly avg bar ────────────────────────────────────────
    year_avgs  = {}
    year_peaks = {}

    if df_raw is not None:
        for yr in HISTORY_YEARS:
            mask = ((df_raw['Datetime'].dt.year  == yr) &
                    (df_raw['Datetime'].dt.month == mo))
            sub  = df_raw[mask]
            if len(sub) > 0:
                year_avgs[yr]  = sub['load'].mean()
                year_peaks[yr] = sub['load'].max()

    # 2026 forecast
    key_2026 = (2026, mo)
    if key_2026 in all_month_data and all_month_data[key_2026] is not None:
        df_f = all_month_data[key_2026]
        year_avgs[2026]  = df_f['predicted_avg'].mean()
        year_peaks[2026] = df_f['predicted_peak'].max()

    years  = sorted(year_avgs.keys())
    avgs   = [year_avgs[y]  for y in years]
    peaks  = [year_peaks.get(y, 0) for y in years]
    colors = [YEAR_COLORS.get(y, '#64748b') for y in years]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=[str(y) for y in years], y=avgs,
        name="Monthly Avg Load",
        marker_color=colors, opacity=0.85,
        text=[f"{v:,.0f}" for v in avgs],
        textposition='outside'))
    fig_bar.add_trace(go.Scatter(
        x=[str(y) for y in years], y=peaks,
        name="Monthly Peak",
        mode="markers+lines",
        marker=dict(size=12, symbol="diamond", color=colors,
                    line=dict(color='white', width=1.5)),
        line=dict(color="#ef4444", width=2, dash="dot")))
    fig_bar.update_layout(
        title=f"📊 {mn} — Monthly Avg & Peak Load: 6-Year Comparison (2020–2026)",
        xaxis_title="Year",
        yaxis_title="Load (MW)", height=370,
        yaxis=dict(tickformat=","),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02))

    # ── Daily trend multi-line ────────────────────────────────
    fig_daily = go.Figure()

    if df_raw is not None:
        for yr in HISTORY_YEARS:
            mask = ((df_raw['Datetime'].dt.year  == yr) &
                    (df_raw['Datetime'].dt.month == mo))
            sub  = df_raw[mask].copy()
            if len(sub) == 0:
                continue
            daily = sub.groupby(sub['Datetime'].dt.day)['load'].mean()
            color_yr = YEAR_COLORS.get(yr, '#64748b')
            is_last  = (yr == max(HISTORY_YEARS))
            fig_daily.add_trace(go.Scatter(
                x=daily.index.tolist(),
                y=daily.values.tolist(),
                name=f"{yr} Actual",
                line=dict(color=color_yr,
                          width=2.5 if is_last else 1.5,
                          dash="solid" if is_last else "dot"),
                mode="lines+markers",
                marker=dict(size=5 if is_last else 3),
                opacity=1.0 if is_last else 0.75))

    # 2026 forecast line
    if key_2026 in all_month_data and all_month_data[key_2026] is not None:
        df_f = all_month_data[key_2026].sort_values('day')
        fig_daily.add_trace(go.Scatter(
            x=df_f['day'].tolist(),
            y=df_f['predicted_avg'].tolist(),
            name="2026 Forecast",
            line=dict(color=MONTH_COLORS[mo], width=3.5),
            mode="lines+markers",
            marker=dict(size=7, symbol="diamond"),
            opacity=1.0))

    fig_daily.update_layout(
        title=f"📈 {mn} — Daily Avg Load Trend: 6-Year Overlay (2020–2026)",
        xaxis_title=f"Day of {mn}",
        yaxis_title="Avg Load (MW)", height=430,
        xaxis=dict(tickmode='linear', tick0=1, dtick=2),
        **CHART_LAYOUT)
    return fig_bar, fig_daily


# ================================================================
#  DASHBOARD
# ================================================================
def show_dashboard(username, role):
    st.markdown(
        f"<h2 style='color:#2563eb'>"
        f"⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>"
        f"Tamil Nadu Power Grid · Rolling LSTM · Welcome <b>{username}</b></p>",
        unsafe_allow_html=True)
    st.divider()

    df, source = load_results()
    df_raw     = load_raw_history()

    if df is None or len(df) == 0:
        st.info("### No forecast results yet\n\n"
                "Run the Colab / local notebook and push to GitHub, "
                "or upload CSVs via the sidebar.")
        return

    if source == "github":
        st.success("✅ Live results from GitHub")
    else:
        st.info("📁 Showing manually uploaded results")

    # ── Load per-month data ────────────────────────────────────
    all_month_data = {}
    for yr, mo in FORECAST_MONTHS:
        mn    = MONTH_NAMES[mo]
        df_mo = load_monthly(mn, yr)
        if df_mo is not None and len(df_mo) > 0:
            all_month_data[(yr, mo)] = df_mo

    # ── KPI cards ─────────────────────────────────────────────
    df['has_actual'] = df['actual_h00'].apply(
        lambda x: pd.notna(x) and str(x) not in ['', 'nan', 'None']) \
        if 'actual_h00' in df.columns else False
    df_past  = df[df['has_actual']].copy() if 'has_actual' in df.columns else pd.DataFrame()
    df_m     = df_past[df_past['mape'].notna()].copy() \
               if ('mape' in df_past.columns and len(df_past) > 0) else pd.DataFrame()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📅 Total Days Forecast", len(df))
    c2.metric("📆 Months Forecast", "Apr · May · Jun 2026")
    if len(df_m) > 0:
        c3.metric("🎯 Avg MAPE", f"{df_m['mape'].mean():.2f}%")
        c4.metric("📊 Avg RMSE", f"{df_m['rmse'].mean():.0f} MW")
    total_months = len(all_month_data)
    c5.metric("✅ Months Loaded", f"{total_months} / 3")
    st.divider()

    # ── TABS ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Monthly Predictions",
        "📅 vs Previous Year",
        "📈 5-Year Comparison",
        "🎯 Accuracy",
        "📋 All Results",
        "📖 About",
    ])

    # ══════════════════════════════════════════════════════════
    # TAB 1 — MONTHLY PREDICTIONS
    # ══════════════════════════════════════════════════════════
    with tab1:
        st.subheader("📊 Monthly Predictions — April · May · June 2026")

        if not all_month_data:
            st.info("No monthly data found. Run the notebook and push to GitHub.")
        else:
            # ── Overall Bar + Line charts ──────────────────────
            fig_bar, fig_line = build_monthly_bar_and_line(all_month_data)
            st.plotly_chart(fig_bar,  use_container_width=True)
            st.plotly_chart(fig_line, use_container_width=True)

            st.divider()
            st.subheader("📆 Per-Month Breakdown")

            # ── Per-month expanders ────────────────────────────
            for yr, mo in FORECAST_MONTHS:
                mn    = MONTH_NAMES[mo]
                color = MONTH_COLORS[mo]

                if (yr, mo) not in all_month_data:
                    st.warning(f"No data for {mn} {yr}")
                    continue

                df_mo    = all_month_data[(yr, mo)].sort_values('day')
                num_days = calendar.monthrange(yr, mo)[1]
                avg_load = df_mo['predicted_avg'].mean()
                peak_load= df_mo['predicted_peak'].max()

                # Colored header for each month
                st.markdown(
                    f"<div style='background:{color};color:white;"
                    f"padding:10px 18px;border-radius:10px;"
                    f"margin:8px 0 4px 0'>"
                    f"<b>📅 {mn} {yr}</b> &nbsp;|&nbsp; "
                    f"{num_days} days &nbsp;|&nbsp; "
                    f"Avg: {avg_load:,.0f} MW &nbsp;|&nbsp; "
                    f"Peak: {peak_load:,.0f} MW</div>",
                    unsafe_allow_html=True)

                with st.expander(
                        f"Expand {mn} {yr} — Daily Charts & Day Selector",
                        expanded=False):
                    # KPIs
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Days", num_days)
                    k2.metric("Avg Load", f"{avg_load:,.0f} MW")
                    k3.metric("Peak Load", f"{peak_load:,.0f} MW")
                    pd_idx    = df_mo['predicted_peak'].idxmax()
                    peak_day  = df_mo.loc[pd_idx, 'day']
                    k4.metric("Peak Day", f"{mn} {int(peak_day)}")

                    # Bar + Line daily charts
                    fig_b, fig_l = build_per_month_detail(yr, mo, df_mo)
                    st.plotly_chart(fig_b, use_container_width=True)
                    st.plotly_chart(fig_l, use_container_width=True)

                    # ── Day selector → hourly line graph ──────
                    st.markdown(
                        f"#### 🔍 Select a Day in {mn} {yr} "
                        f"to See Hourly Prediction")
                    sel_day = st.slider(
                        f"Day of {mn}", 1, num_days, 1,
                        key=f"day_slider_{mo}")
                    day_rows = df_mo[df_mo['day'] == sel_day]

                    if len(day_rows) > 0:
                        row = day_rows.iloc[0]
                        # Summary cards
                        d1, d2, d3, d4 = st.columns(4)
                        avg_v  = safe_float(row.get('predicted_avg'))  or 0
                        peak_v = safe_float(row.get('predicted_peak')) or 0
                        pred   = get_24hrs(row, 'pred')
                        valid  = [v for v in pred if v is not None]
                        d1.metric("📅 Date",
                                  str(row.get('date', f"{yr}-{mo:02d}-{sel_day:02d}")))
                        d2.metric("⚡ Avg Load",  f"{avg_v:,.0f} MW")
                        d3.metric("🔺 Peak Load", f"{peak_v:,.0f} MW")
                        d4.metric("🔻 Min Load",
                                  f"{min(valid):,.0f} MW" if valid else "—")

                        fig_hourly = build_hourly_day_chart(yr, mo, sel_day, row)
                        st.plotly_chart(fig_hourly, use_container_width=True)

                        # Hourly data table
                        with st.expander("📋 Hourly Data Table"):
                            hourly_df = pd.DataFrame({
                                "Hour": [f"{h:02d}:00" for h in range(24)],
                                "Predicted Load (MW)": [
                                    round(v, 1) if v else None
                                    for v in pred
                                ]
                            })
                            st.dataframe(hourly_df, use_container_width=True,
                                         hide_index=True)
                    else:
                        st.info(f"No data for {mn} {sel_day}")

                    # Full month table
                    with st.expander(f"📋 {mn} {yr} — Full Daily Table"):
                        show_c = ['day', 'date', 'predicted_avg', 'predicted_peak']
                        avail  = [c for c in show_c if c in df_mo.columns]
                        ds     = df_mo[avail].copy()
                        for c in ['predicted_avg', 'predicted_peak']:
                            if c in ds.columns:
                                ds[c] = pd.to_numeric(ds[c], errors='coerce').round(1)
                        ds.columns = [c.replace('_', ' ').title() for c in ds.columns]
                        st.dataframe(ds, use_container_width=True, hide_index=True)
                        st.download_button(
                            f"⬇ Download {mn} {yr} CSV",
                            df_mo.to_csv(index=False).encode(),
                            f"{mn.lower()}_{yr}_results.csv", "text/csv",
                            use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 2 — VS PREVIOUS YEAR
    # ══════════════════════════════════════════════════════════
    with tab2:
        st.subheader("📅 2026 Forecast vs 2025 Actual — Month by Month")

        if not all_month_data:
            st.info("No forecast data loaded yet.")
        else:
            sel_prev = st.selectbox(
                "Select Month to Compare",
                [f"{MONTH_NAMES[mo]} {yr}" for yr, mo in FORECAST_MONTHS],
                key="prev_yr_sel")
            sel_yr2 = int(sel_prev.split()[-1])
            sel_mo2 = next(mo for mo in MONTH_NAMES
                           if MONTH_NAMES[mo] == sel_prev.split()[0])

            if (sel_yr2, sel_mo2) not in all_month_data:
                st.info(f"No forecast data for {sel_prev}.")
            else:
                df_mo2   = all_month_data[(sel_yr2, sel_mo2)]
                fig, growth = build_prev_year_comparison(
                    sel_yr2, sel_mo2, df_mo2, df_raw)

                # KPI banner
                mn2 = MONTH_NAMES[sel_mo2]
                col = MONTH_COLORS[sel_mo2]
                g_color = "#16a34a" if growth > 0 else "#dc2626"
                st.markdown(
                    f"<div style='background:{col}15;border-left:4px solid {col};"
                    f"padding:10px 16px;border-radius:6px;margin-bottom:10px'>"
                    f"<b>{mn2} 2026 (Forecast)</b> vs "
                    f"<b>{mn2} 2025 (Actual)</b> &nbsp;|&nbsp; "
                    f"YoY Growth: <b style='color:{g_color}'>{growth:+.1f}%</b>"
                    f"</div>", unsafe_allow_html=True)

                if df_raw is None:
                    st.warning(
                        "⚠ Upload the history CSV in the sidebar "
                        "to see 2025 actual data overlay.")

                st.plotly_chart(fig, use_container_width=True)

            # ── All months summary side-by-side ────────────────
            st.divider()
            st.subheader("All Months — Growth vs Previous Year")
            cols_m = st.columns(3)
            for i, (yr, mo) in enumerate(FORECAST_MONTHS):
                mn3   = MONTH_NAMES[mo]
                color = MONTH_COLORS[mo]
                if (yr, mo) not in all_month_data:
                    continue
                df_mo3 = all_month_data[(yr, mo)]
                curr_avg = df_mo3['predicted_avg'].mean()
                prev_avg = None
                if df_raw is not None:
                    mask = ((df_raw['Datetime'].dt.year  == yr - 1) &
                            (df_raw['Datetime'].dt.month == mo))
                    sub  = df_raw[mask]
                    if len(sub) > 0:
                        prev_avg = sub['load'].mean()
                g_str = (f"{((curr_avg - prev_avg)/prev_avg*100):+.1f}%"
                         if prev_avg else "N/A")
                with cols_m[i]:
                    st.markdown(
                        f"<div style='background:{color}18;border:1px solid {color};"
                        f"padding:14px;border-radius:10px;text-align:center'>"
                        f"<b style='color:{color};font-size:16px'>{mn3} 2026</b><br>"
                        f"Forecast Avg: <b>{curr_avg:,.0f} MW</b><br>"
                        f"{'2025 Actual: ' + f'{prev_avg:,.0f} MW' if prev_avg else '2025: N/A'}<br>"
                        f"YoY: <b>{g_str}</b></div>",
                        unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # TAB 3 — 5-YEAR COMPARISON
    # ══════════════════════════════════════════════════════════
    with tab3:
        st.subheader("📈 5-Year (2020–2026) Load Comparison")

        if df_raw is None:
            st.warning(
                "⚠ **Upload the history CSV** (Data__2020-2026_3rd_month_.csv) "
                "in the sidebar to enable 5-year comparison charts.")
        else:
            st.success(
                f"✅ History data loaded: "
                f"{df_raw['Datetime'].min().date()} → "
                f"{df_raw['Datetime'].max().date()}")

        sel_mo3 = st.selectbox(
            "Select Month for 5-Year Analysis",
            ["April", "May", "June"],
            key="yr5_sel")
        mo3 = next(mo for mo, nm in MONTH_NAMES.items() if nm == sel_mo3)

        # Always show what we can
        fig_bar5, fig_daily5 = build_5year_comparison(
            mo3, all_month_data, df_raw)

        st.plotly_chart(fig_bar5,   use_container_width=True)
        st.plotly_chart(fig_daily5, use_container_width=True)

        # ── Year-over-year table ───────────────────────────────
        st.subheader(f"{sel_mo3} — Year-Over-Year Summary Table")
        rows_tbl = []
        for yr_t in HISTORY_YEARS:
            row_t = {"Year": yr_t, "Type": "Actual"}
            if df_raw is not None:
                mask = ((df_raw['Datetime'].dt.year  == yr_t) &
                        (df_raw['Datetime'].dt.month == mo3))
                sub  = df_raw[mask]
                if len(sub) > 0:
                    row_t["Avg Load (MW)"]  = round(sub['load'].mean(), 0)
                    row_t["Peak Load (MW)"] = round(sub['load'].max(),  0)
                    row_t["Min Load (MW)"]  = round(sub['load'].min(),  0)
                else:
                    row_t["Avg Load (MW)"] = row_t["Peak Load (MW)"] = None
                    row_t["Min Load (MW)"] = None
            rows_tbl.append(row_t)

        # 2026 forecast row
        row_2026 = {"Year": 2026, "Type": "Forecast 🔮"}
        if (2026, mo3) in all_month_data:
            df_f3 = all_month_data[(2026, mo3)]
            row_2026["Avg Load (MW)"]  = round(df_f3['predicted_avg'].mean(), 0)
            row_2026["Peak Load (MW)"] = round(df_f3['predicted_peak'].max(),  0)
            row_2026["Min Load (MW)"]  = None
        rows_tbl.append(row_2026)

        tbl_df = pd.DataFrame(rows_tbl)
        st.dataframe(tbl_df, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════
    # TAB 4 — ACCURACY
    # ══════════════════════════════════════════════════════════
    with tab4:
        st.subheader("🎯 Model Accuracy — MAPE & RMSE")

        if len(df_m) == 0:
            st.info(
                "No accuracy data yet.\n\n"
                "Once actual readings are available, the Colab notebook "
                "will compute MAPE & RMSE and push them to GitHub.")
        else:
            c1a, c2a = st.columns(2)
            with c1a:
                fm = go.Figure()
                fm.add_trace(go.Scatter(
                    x=df_m['date'].tolist(),
                    y=df_m['mape'].tolist(),
                    mode="lines+markers",
                    name="MAPE %",
                    line=dict(color="#ea580c", width=2.5)))
                fm.add_hline(
                    y=df_m['mape'].mean(),
                    line_dash="dash", line_color="red",
                    annotation_text=f"Avg: {df_m['mape'].mean():.2f}%")
                fm.update_layout(
                    title="MAPE % Over Time",
                    yaxis_title="MAPE %", height=320,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fm, use_container_width=True)

            with c2a:
                fr = go.Figure()
                fr.add_trace(go.Scatter(
                    x=df_m['date'].tolist(),
                    y=df_m['rmse'].tolist(),
                    mode="lines+markers",
                    name="RMSE MW",
                    line=dict(color="#7c3aed", width=2.5)))
                fr.add_hline(
                    y=df_m['rmse'].mean(),
                    line_dash="dash", line_color="red",
                    annotation_text=f"Avg: {df_m['rmse'].mean():.0f} MW")
                fr.update_layout(
                    title="RMSE (MW) Over Time",
                    yaxis_title="RMSE (MW)", height=320,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fr, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 5 — ALL RESULTS
    # ══════════════════════════════════════════════════════════
    with tab5:
        st.subheader(f"📋 All Forecast Results — {len(df)} days")

        show_cols3 = ['date', 'month_name', 'day',
                      'predicted_avg', 'predicted_peak']
        if 'mape' in df.columns:
            show_cols3 += ['mape', 'rmse']
        avail3 = [c for c in show_cols3 if c in df.columns]
        ds3    = df[avail3].copy()
        for c in ['predicted_avg', 'predicted_peak', 'mape', 'rmse']:
            if c in ds3.columns:
                ds3[c] = pd.to_numeric(ds3[c], errors='coerce').round(1)
        ds3.columns = [c.replace('_', ' ').title() for c in ds3.columns]
        st.dataframe(ds3, use_container_width=True,
                     hide_index=True, height=480)

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇ Download All Results CSV",
                df.to_csv(index=False).encode(),
                "TN_all_results.csv", "text/csv",
                use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 6 — ABOUT
    # ══════════════════════════════════════════════════════════
    with tab6:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
### System Overview
**Data** — Jan 2020 to Mar 2026
6+ years Tamil Nadu hourly load + weather

**Model** — Stacked LSTM (Rolling Retrain)
- 2 layers: 128 + 64 units
- 168-hour lookback (7 days)
- 22 features including wind100
- Auto-regressive rolling forecast
- Retrains after each month

**Rolling Strategy**
- April: trained on full history
- May: retrained on history + Apr preds
- June: retrained on history + Apr + May
- Total: 91 days forecast

**Forecast Period**
- April 2026: 30 days
- May 2026: 31 days
- June 2026: 30 days
            """)
        with c2:
            st.markdown("""
### Dashboard Tabs

| Tab | Description |
|-----|-------------|
| 📊 Monthly Predictions | Bar + Line charts for all 3 months. Per-month expanders with daily bar/line charts and hourly day selector |
| 📅 vs Previous Year | 2026 forecast vs 2025 actual — daily avg + hourly profile comparison |
| 📈 5-Year Comparison | 2020–2026 monthly bar + daily multi-line overlay |
| 🎯 Accuracy | MAPE and RMSE trends (when actuals available) |
| 📋 All Results | Complete forecast table with download |

### Per-Month Detail includes
- Daily peak load bar chart
- Daily avg/peak/min line chart with 7-day rolling avg
- Day slider → 24-hour hourly prediction line graph
- Min/Peak annotations on hourly chart
- Full hourly data table
- CSV download per month

### Features (22 total)
temperature · humidity · rain
wind10 · **wind100** · radiation
cloud_cover · hour · month
day_of_week · is_summer · is_holiday
load_lag 24/48/168 · rolling_mean · rolling_std
            """)


# ================================================================
#  MAIN
# ================================================================
def main():
    for k in ['logged_in', 'username', 'role']:
        if k not in st.session_state:
            st.session_state[k] = (
                False if k == 'logged_in' else None)
    if not st.session_state['logged_in']:
        show_login_page()
        return
    show_sidebar(st.session_state['username'],
                 st.session_state['role'])
    show_dashboard(st.session_state['username'],
                   st.session_state['role'])


if __name__ == "__main__":
    main()
