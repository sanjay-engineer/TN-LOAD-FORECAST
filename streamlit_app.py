# ================================================================
#  TN LOAD FORECASTING — STREAMLIT APP  (FIXED VERSION)
#  Fixes:
#  1. rgba color bug fixed
#  2. pandas 3.x ffill/bfill fixed
#  3. load_monthly() safe with fallback
#  4. df_future next-day index fixed
#  5. 5-year comparison charts added (all 3 months)
#  6. All tab logic corrected
#  7. Robust error handling throughout
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, zipfile, requests, calendar
from datetime import datetime
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide"
)

# ── GitHub settings ───────────────────────────────────────────
GITHUB_USER   = "sanjay-engineer"
GITHUB_REPO   = "TN-LOAD-FORECAST"
GITHUB_BRANCH = "main"
GITHUB_RAW    = (f"https://raw.githubusercontent.com/"
                 f"{GITHUB_USER}/{GITHUB_REPO}/"
                 f"{GITHUB_BRANCH}/results")

# ── Local file paths ──────────────────────────────────────────
USERS_FILE    = "users.json"
SHARED_DIR    = "shared_results"
LOCAL_RESULTS = os.path.join(SHARED_DIR, "rolling_results.csv")
LOCAL_HISTORY = os.path.join(SHARED_DIR, "history_updated.csv")
os.makedirs(SHARED_DIR, exist_ok=True)

# ── Month constants ───────────────────────────────────────────
FORECAST_MONTHS = [(2026, 4), (2026, 5), (2026, 6)]
MONTH_NAMES     = {4: 'April', 5: 'May', 6: 'June'}
# FIX 1: explicit rgba strings — no broken conversion
MONTH_COLORS    = {4: '#2563eb', 5: '#16a34a', 6: '#ea580c'}
MONTH_FILL      = {
    4: 'rgba(37,99,235,0.10)',
    5: 'rgba(22,163,74,0.10)',
    6: 'rgba(234,88,12,0.10)',
}
# Colors for 5-year comparison lines
YEAR_COLORS = {
    2020: '#94a3b8',
    2021: '#64748b',
    2022: '#f59e0b',
    2023: '#8b5cf6',
    2024: '#ec4899',
    2025: '#6366f1',
    2026: '#dc2626',
}

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
    if len(username) < 3:
        return False, "Username too short — need at least 3"
    if len(username) > 20:
        return False, "Username too long — max 20"
    if not username.replace("_", "").isalnum():
        return False, "Letters, numbers and underscore only"
    if len(password) < 6:
        return False, "Password too short — need at least 6"
    users = load_users()
    if username.lower() in [u.lower() for u in users]:
        return False, "Username already taken"
    users[username] = {
        "password"  : hash_pw(password),
        "role"      : "viewer",
        "created"   : str(datetime.now().date()),
        "last_login": None,
    }
    save_users(users)
    return True, "Account created — go to Login tab"

def login_user(username, password):
    users = load_users()
    match = next((u for u in users
                  if u.lower() == username.lower()), None)
    if not match:
        return False, "Username not found", None
    if users[match]["password"] != hash_pw(password):
        return False, "Wrong password", None
    users[match]["last_login"] = str(datetime.now())
    save_users(users)
    return True, match, users[match].get("role", "viewer")

def make_admin(username, secret):
    if secret != "TN2025Admin":
        return False, "Wrong admin secret key"
    users = load_users()
    match = next((u for u in users
                  if u.lower() == username.lower()), None)
    if not match:
        return False, f"User '{username}' not found"
    users[match]["role"] = "admin"
    save_users(users)
    return True, f"'{match}' is now Admin"

# ================================================================
#  DATA LOADING
# ================================================================
@st.cache_data(ttl=60)
def fetch_github(filename):
    """Fetch a file from GitHub. Returns text or None."""
    url = f"{GITHUB_RAW}/{filename}"
    try:
        r = requests.get(url, timeout=10)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None

@st.cache_data(ttl=60)
def check_github_ok():
    try:
        r = requests.head(
            f"{GITHUB_RAW}/rolling_results.csv", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def load_results():
    """Load rolling_results.csv from GitHub or local."""
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
    """Load per-month results CSV. Returns None if not found."""
    fname = f"{month_name.lower()}_{year}_results.csv"
    data  = fetch_github(fname)
    if data:
        try:
            df = pd.read_csv(StringIO(data))
            if len(df) > 0:
                return df
        except Exception:
            pass
    local = os.path.join(SHARED_DIR, fname)
    if os.path.exists(local):
        df = pd.read_csv(local)
        if len(df) > 0:
            return df
    return None

@st.cache_data(ttl=300)
def load_history_data():
    """
    Load the full history CSV from GitHub results folder.
    Used for 5-year comparison charts.
    Falls back to local shared_results folder.
    """
    data = fetch_github("TN_load_processed.csv")
    if data:
        try:
            df = pd.read_csv(StringIO(data))
            df['Datetime'] = pd.to_datetime(
                df['Datetime'], dayfirst=True)
            return df
        except Exception:
            pass
    local = os.path.join(SHARED_DIR, "TN_load_processed.csv")
    if os.path.exists(local):
        df = pd.read_csv(local)
        df['Datetime'] = pd.to_datetime(
            df['Datetime'], dayfirst=True)
        return df
    return None

def safe_float(val):
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except Exception:
        return None

def get_24hrs(row, prefix):
    return [safe_float(row.get(f'{prefix}_h{h:02d}'))
            for h in range(24)]

# ================================================================
#  LOGIN PAGE
# ================================================================
def show_login_page():
    st.markdown("""
    <div style='text-align:center;padding:36px 0 16px 0'>
        <div style='font-size:50px'>⚡</div>
        <h2 style='color:#2563eb;margin:8px 0 4px 0'>
            TN Intelligent Load Forecasting</h2>
        <p style='color:#64748b;font-size:13px'>
            Tamil Nadu Power Grid — LSTM Forecast System</p>
    </div>""", unsafe_allow_html=True)
    st.divider()

    t1, t2, t3 = st.tabs([
        "🔑 Login", "📝 Register", "🔧 Admin Setup"])

    with t1:
        st.subheader("Login to your account")
        with st.form("lf"):
            u = st.text_input(
                "Username", placeholder="Enter username")
            p = st.text_input(
                "Password", type="password",
                placeholder="Enter password")
            s = st.form_submit_button(
                "Login", use_container_width=True,
                type="primary")
        if s:
            if not u or not p:
                st.error("Enter both username and password")
            else:
                ok, res, role = login_user(u, p)
                if ok:
                    st.session_state.update(
                        logged_in=True,
                        username=res,
                        role=role)
                    st.rerun()
                else:
                    st.error(f"❌ {res}")

    with t2:
        st.subheader("Create new account")
        st.info("After registering, go to **Admin Setup** "
                "to get upload access.")
        with st.form("rf"):
            nu  = st.text_input(
                "Username", placeholder="3-20 characters")
            np_ = st.text_input(
                "Password", type="password",
                placeholder="Minimum 6 characters")
            cp  = st.text_input(
                "Confirm Password", type="password",
                placeholder="Repeat password")
            rb  = st.form_submit_button(
                "Create Account",
                use_container_width=True,
                type="primary")
        if rb:
            if not nu or not np_ or not cp:
                st.error("Fill all three fields")
            elif np_ != cp:
                st.error("Passwords do not match")
            else:
                ok, msg = register_user(nu, np_)
                (st.success if ok else st.error)(msg)

    with t3:
        st.subheader("Make yourself Admin")
        st.info(
            "**Steps:**\n\n"
            "1. Register first in the Register tab\n"
            "2. Enter your username below\n"
            "3. Enter the secret key: **TN2025Admin**\n"
            "4. Click Make Admin\n"
            "5. Login — upload buttons will appear")
        with st.form("af"):
            au = st.text_input(
                "Your Username",
                placeholder="Username you registered with")
            ak = st.text_input(
                "Admin Secret Key", type="password",
                placeholder="TN2025Admin")
            ab = st.form_submit_button(
                "Make Admin", use_container_width=True)
        if ab:
            ok, msg = make_admin(au, ak)
            (st.success if ok else st.error)(msg)

    st.divider()
    if check_github_ok():
        st.success(
            "✅ GitHub connected — results load automatically")
    else:
        st.warning(
            "⚠ GitHub not connected — "
            "results must be uploaded manually")

# ================================================================
#  SIDEBAR
# ================================================================
def show_sidebar(username, role):
    with st.sidebar:
        bg    = "#7c3aed" if role == "admin" else "#2563eb"
        label = "Admin ✓" if role == "admin" else "Viewer"
        st.markdown(
            f"<div style='background:{bg};color:white;"
            f"padding:12px 16px;border-radius:10px;"
            f"margin-bottom:10px'>"
            f"<b>👤 {username}</b><br>"
            f"<span style='font-size:12px;opacity:.85'>"
            f"{label}</span></div>",
            unsafe_allow_html=True)
        st.divider()

        st.subheader("🔗 Data Source")
        github_ok = check_github_ok()
        if github_ok:
            st.success("✅ GitHub — Auto sync")
            st.caption("Results refresh every 60 seconds")
            if st.button("🔄 Refresh Now",
                         use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("⚠ GitHub not connected")
            st.caption(
                "Check GITHUB_USER and GITHUB_REPO "
                "settings in app code")

        st.divider()

        if role == "admin":
            with st.expander("📂 Manual Upload (backup)"):
                st.caption(
                    "Only needed if GitHub is offline")
                rf = st.file_uploader(
                    "rolling_results.csv",
                    type=["csv"], key="ru")
                if rf:
                    pd.read_csv(rf).to_csv(
                        LOCAL_RESULTS, index=False)
                    st.success("✓ Saved")
                hf = st.file_uploader(
                    "history_updated.csv",
                    type=["csv"], key="hu")
                if hf:
                    pd.read_csv(hf).to_csv(
                        LOCAL_HISTORY, index=False)
                    st.success("✓ Saved")
                # Upload per-month files
                for yr, mo in FORECAST_MONTHS:
                    mn    = MONTH_NAMES[mo]
                    fname = f"{mn.lower()}_{yr}_results.csv"
                    mf    = st.file_uploader(
                        fname, type=["csv"],
                        key=f"mf_{mo}")
                    if mf:
                        dest = os.path.join(
                            SHARED_DIR, fname)
                        pd.read_csv(mf).to_csv(
                            dest, index=False)
                        st.success(f"✓ {fname} saved")
                # Upload history for 5-year chart
                hst = st.file_uploader(
                    "TN_load_processed.csv",
                    type=["csv"], key="hst")
                if hst:
                    dest = os.path.join(
                        SHARED_DIR,
                        "TN_load_processed.csv")
                    pd.read_csv(hst).to_csv(
                        dest, index=False)
                    st.success("✓ History saved")

        st.divider()
        if st.button("🚪 Logout",
                     use_container_width=True):
            st.session_state.update(
                logged_in=False,
                username=None,
                role=None)
            st.rerun()

# ================================================================
#  5-YEAR COMPARISON CHART BUILDER
#  Uses history data already loaded — no GitHub needed
# ================================================================
def build_5year_chart(df_hist, month_num,
                      df_forecast=None):
    """
    Builds a plotly figure comparing the same month
    across all available years (2020-2026).
    df_hist    = TN_load_processed.csv data
    month_num  = 4, 5, or 6
    df_forecast= this year's forecast monthly CSV
    Returns fig
    """
    mn    = MONTH_NAMES[month_num]
    years = sorted(df_hist['Datetime'].dt.year.unique()
                   ) if df_hist is not None else []

    fig = go.Figure()

    # Historical years from loaded data
    if df_hist is not None:
        for yr in years:
            if yr == 2026:
                continue   # skip — forecast only
            mask = (
                (df_hist['Datetime'].dt.year == yr) &
                (df_hist['Datetime'].dt.month == month_num)
            )
            sub = df_hist[mask].copy()
            if len(sub) == 0:
                continue
            daily = (sub.groupby(
                sub['Datetime'].dt.day)['load']
                .mean()
                .reset_index())
            daily.columns = ['day', 'avg_load']

            fig.add_trace(go.Scatter(
                x=daily['day'],
                y=daily['avg_load'],
                name=str(yr),
                line=dict(color=YEAR_COLORS.get(
                    yr, '#64748b'),
                    width=1.8,
                    dash='dot' if yr < 2023
                    else 'solid'),
                mode='lines+markers',
                marker=dict(size=4),
                opacity=0.8 if yr < 2023 else 1.0))

    # 2026 forecast from monthly CSV
    if df_forecast is not None and len(df_forecast) > 0:
        df_f = df_forecast.sort_values('day')
        fig.add_trace(go.Scatter(
            x=df_f['day'],
            y=df_f['predicted_avg'],
            name='2026 (Forecast)',
            line=dict(color=YEAR_COLORS[2026],
                      width=3),
            mode='lines+markers',
            marker=dict(size=7, symbol='diamond'),
            fill='tozeroy',
            fillcolor='rgba(220,38,38,0.07)'))

    num_days = calendar.monthrange(2026, month_num)[1]

    fig.update_layout(
        title=(f"{mn} — Year-on-Year Comparison "
               f"(2020 to 2026)\nDaily Average Load (MW)"),
        xaxis_title=f"Day of {mn}",
        yaxis_title="Daily Average Load (MW)",
        xaxis=dict(tickmode='linear',
                   tick0=1, dtick=1,
                   range=[0, num_days + 1]),
        height=450,
        legend=dict(orientation="h",
                    yanchor="bottom", y=1.02,
                    title="Year"),
        hovermode="x unified",
        yaxis=dict(tickformat=","),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)")

    return fig


def build_5year_hourly_chart(df_hist, month_num,
                              df_forecast=None):
    """
    Builds a plotly figure of average hourly load profile
    for the same month across all years.
    """
    mn    = MONTH_NAMES[month_num]
    years = sorted(df_hist['Datetime'].dt.year.unique()
                   ) if df_hist is not None else []
    fig   = go.Figure()

    if df_hist is not None:
        for yr in years:
            if yr == 2026:
                continue
            mask = (
                (df_hist['Datetime'].dt.year == yr) &
                (df_hist['Datetime'].dt.month == month_num)
            )
            sub = df_hist[mask].copy()
            if len(sub) == 0:
                continue
            hourly = (sub.groupby(
                sub['Datetime'].dt.hour)['load']
                .mean()
                .reset_index())
            hourly.columns = ['hour', 'avg_load']

            fig.add_trace(go.Scatter(
                x=hourly['hour'],
                y=hourly['avg_load'],
                name=str(yr),
                line=dict(color=YEAR_COLORS.get(
                    yr, '#64748b'),
                    width=1.8,
                    dash='dot' if yr < 2023
                    else 'solid'),
                mode='lines',
                opacity=0.85))

    # 2026 forecast hourly profile
    if df_forecast is not None and len(df_forecast) > 0:
        hourly_2026 = []
        for h in range(24):
            col  = f'pred_h{h:02d}'
            vals = [safe_float(v)
                    for v in df_forecast[col].tolist()
                    if col in df_forecast.columns]
            vals = [v for v in vals if v is not None]
            hourly_2026.append(
                np.mean(vals) if vals else None)

        if any(v is not None for v in hourly_2026):
            fig.add_trace(go.Scatter(
                x=list(range(24)),
                y=hourly_2026,
                name='2026 (Forecast)',
                line=dict(color=YEAR_COLORS[2026],
                          width=3),
                mode='lines+markers',
                marker=dict(size=6,
                            symbol='diamond')))

    hlabels = [f"{h:02d}:00" for h in range(24)]
    fig.update_layout(
        title=(f"{mn} — Average Hourly Load Profile "
               f"by Year"),
        xaxis_title="Hour of Day",
        yaxis_title="Average Load (MW)",
        xaxis=dict(tickmode='array',
                   tickvals=list(range(24)),
                   ticktext=hlabels),
        height=400,
        legend=dict(orientation="h",
                    yanchor="bottom", y=1.02,
                    title="Year"),
        hovermode="x unified",
        yaxis=dict(tickformat=","),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)")

    return fig


def build_monthly_avg_bar(df_hist, month_num,
                           df_forecast=None):
    """
    Bar chart: one bar per year showing monthly avg load.
    Shows load growth trend over 6 years.
    """
    mn     = MONTH_NAMES[month_num]
    years  = []
    avgs   = []
    peaks  = []
    colors = []

    if df_hist is not None:
        for yr in sorted(
                df_hist['Datetime'].dt.year.unique()):
            if yr == 2026:
                continue
            mask = (
                (df_hist['Datetime'].dt.year == yr) &
                (df_hist['Datetime'].dt.month == month_num)
            )
            sub = df_hist[mask]
            if len(sub) == 0:
                continue
            years.append(str(yr))
            avgs.append(sub['load'].mean())
            peaks.append(sub['load'].max())
            colors.append(
                YEAR_COLORS.get(yr, '#64748b'))

    # Add 2026 forecast
    if df_forecast is not None and len(df_forecast) > 0:
        years.append('2026\n(Forecast)')
        avgs.append(df_forecast['predicted_avg'].mean())
        peaks.append(df_forecast['predicted_peak'].max())
        colors.append(YEAR_COLORS[2026])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=avgs,
        name='Monthly Avg Load',
        marker_color=colors,
        opacity=0.85,
        text=[f"{v:,.0f}" for v in avgs],
        textposition='outside'))
    fig.add_trace(go.Scatter(
        x=years, y=peaks,
        name='Monthly Peak Load',
        mode='lines+markers',
        line=dict(color='#dc2626', width=2,
                  dash='dot'),
        marker=dict(size=8, symbol='triangle-up',
                    color='#dc2626')))

    fig.update_layout(
        title=(f"{mn} — Monthly Avg and Peak Load "
               f"by Year (2020–2026)"),
        xaxis_title="Year",
        yaxis_title="Load (MW)",
        height=380,
        legend=dict(orientation="h",
                    yanchor="bottom", y=1.02),
        yaxis=dict(tickformat=","),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)")

    return fig

# ================================================================
#  MAIN DASHBOARD
# ================================================================
def show_dashboard(username, role):
    st.markdown(
        f"<h2 style='color:#2563eb'>"
        f"⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>"
        f"Tamil Nadu Power Grid · "
        f"Welcome <b>{username}</b> "
        f"({'Admin' if role=='admin' else 'Viewer'})</p>",
        unsafe_allow_html=True)
    st.divider()

    df, source = load_results()
    df_hist    = load_history_data()

    if df is None or len(df) == 0:
        st.info(
            "### No results yet\n\n"
            "Run **TN_3MONTH_FORECAST.py** in Colab "
            "and push results to GitHub.\n\n"
            "Or upload files manually using the "
            "sidebar → Manual Upload.")
        return

    if source == "github":
        st.success(
            "✅ Showing live results from GitHub — "
            "updates automatically when Colab runs")
    else:
        st.info("📁 Showing manually uploaded results")

    # Split rows: past (with actual) vs future (forecast)
    df['has_actual'] = df['actual_h00'].apply(
        lambda x: pd.notna(x) and
        str(x).strip() not in ['', 'nan', 'None'])
    df_past   = df[df['has_actual']].copy()
    df_future = df[~df['has_actual']].copy()
    df_m      = df_past[df_past['mape'].notna()].copy()

    hours   = list(range(24))
    hlabels = [f"{h:02d}:00" for h in hours]

    # Stat cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📅 Days with Actual", len(df_past))
    if len(df_m) > 0:
        c2.metric("🎯 Avg MAPE",
                  f"{df_m['mape'].mean():.2f}%")
        idx = df_m['mape'].idxmin()
        c3.metric("🏆 Best MAPE",
                  f"{df_m.loc[idx,'mape']:.2f}%",
                  str(df_m.loc[idx, 'date']),
                  delta_color="off")
        c4.metric("📊 Avg RMSE",
                  f"{df_m['rmse'].mean():.0f} MW")
    c5.metric("🔮 Months Forecast", "Apr·May·Jun 2026")
    st.divider()

    # ── Tabs ──────────────────────────────────────────────────
    (tab1, tab2, tab3,
     tab4, tab5, tab6) = st.tabs([
        "📈 Daily Forecast",
        "🎯 Accuracy",
        "📅 3-Month Forecast",
        "📆 5-Year Comparison",
        "📋 All Results",
        "📖 About",
    ])

    # ══════════════════════════════════════════════════════════
    #  TAB 1 — DAILY FORECAST
    # ══════════════════════════════════════════════════════════
    with tab1:

        # ── Today: predicted vs actual ────────────────────────
        st.subheader("📊 Today — Predicted vs Actual")

        if len(df_past) == 0:
            st.info("No actual data yet — "
                    "run Colab to generate results")
        else:
            row    = df_past.iloc[-1]
            pred   = get_24hrs(row, 'pred')
            actual = get_24hrs(row, 'actual')
            mv     = safe_float(row.get('mape'))
            rv     = safe_float(row.get('rmse'))
            vp     = [v for v in pred if v is not None]

            m1, m2, m3, m4 = st.columns(4)
            if mv is not None:
                col = ("green" if mv < 5 else
                       "orange" if mv < 10 else "red")
                m1.markdown(
                    f"<h3 style='color:{col}'>"
                    f"{mv:.2f}%</h3>"
                    f"<p style='color:#64748b;"
                    f"font-size:12px'>MAPE</p>",
                    unsafe_allow_html=True)
            if rv is not None:
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

            fig_today = go.Figure()
            has_act   = any(v is not None for v in actual)
            if has_act:
                fig_today.add_trace(go.Scatter(
                    x=hlabels, y=actual,
                    name="Actual Load",
                    line=dict(color="#16a34a", width=3),
                    mode="lines+markers",
                    marker=dict(size=7),
                    fill="tozeroy",
                    fillcolor="rgba(22,163,74,0.07)"))
            fig_today.add_trace(go.Scatter(
                x=hlabels, y=pred,
                name="Predicted Load",
                line=dict(color="#2563eb", width=2.5,
                          dash="dash"),
                mode="lines+markers",
                marker=dict(size=6)))
            fig_today.update_layout(
                title=f"Predicted vs Actual — {row['date']}",
                xaxis_title="Hour",
                yaxis_title="Load (MW)",
                hovermode="x unified", height=390,
                legend=dict(orientation="h",
                            yanchor="bottom", y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(
                fig_today, use_container_width=True)

        st.divider()

        # ── Tomorrow: next day forecast ───────────────────────
        st.subheader("🔮 Tomorrow — Next Day Forecast")
        st.caption(
            "The model's prediction for the next "
            "24 hours — no actual data yet")

        if len(df_future) == 0:
            st.info("No forecast data yet")
        else:
            # FIX 4: use iloc[0] — first future row = tomorrow
            nrow  = df_future.iloc[0]
            npred = get_24hrs(nrow, 'pred')
            vnp   = [v for v in npred if v is not None]

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
                f"{nrow['date']}</h3>"
                f"<p style='color:#64748b;"
                f"font-size:12px'>Forecast Date</p>",
                unsafe_allow_html=True)

            fig_next = go.Figure()
            fig_next.add_trace(go.Scatter(
                x=hlabels, y=npred,
                name="Next Day Forecast",
                line=dict(color="#ea580c", width=3),
                mode="lines+markers",
                marker=dict(size=8, symbol="diamond"),
                fill="tozeroy",
                fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph = npred.index(max(vnp))
                fig_next.add_annotation(
                    x=hlabels[ph], y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True, arrowhead=2,
                    arrowcolor="#ea580c",
                    font=dict(color="#ea580c", size=11),
                    bgcolor="white",
                    bordercolor="#ea580c",
                    borderwidth=1.5, ay=-40)
            fig_next.update_layout(
                title=f"Next Day Forecast — {nrow['date']}",
                xaxis_title="Hour",
                yaxis_title="Load (MW)",
                hovermode="x unified", height=390,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(
                fig_next, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    #  TAB 2 — ACCURACY
    # ══════════════════════════════════════════════════════════
    with tab2:

        if len(df_m) == 0:
            st.info("No accuracy data available yet")
        else:
            c1, c2 = st.columns(2)
            with c1:
                fm = px.line(
                    df_m, x="date", y="mape",
                    title="MAPE % Over Days — "
                          "Goes Down as Model Learns",
                    markers=True,
                    color_discrete_sequence=["#ea580c"])
                fm.add_hline(
                    y=df_m['mape'].mean(),
                    line_dash="dash", line_color="red",
                    annotation_text=
                    f"Avg: {df_m['mape'].mean():.2f}%")
                fm.update_layout(
                    height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(
                    fm, use_container_width=True)

            with c2:
                fr = px.line(
                    df_m, x="date", y="rmse",
                    title="RMSE (MW) Over Days",
                    markers=True,
                    color_discrete_sequence=["#7c3aed"])
                fr.add_hline(
                    y=df_m['rmse'].mean(),
                    line_dash="dash", line_color="red",
                    annotation_text=
                    f"Avg: {df_m['rmse'].mean():.0f} MW")
                fr.update_layout(
                    height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(
                    fr, use_container_width=True)

            # Actual vs predicted avg
            if ('actual_avg' in df_m.columns and
                    'predicted_avg' in df_m.columns):
                fa = go.Figure()
                fa.add_trace(go.Scatter(
                    x=df_m['date'],
                    y=pd.to_numeric(
                        df_m['actual_avg'],
                        errors='coerce'),
                    name="Actual Avg",
                    line=dict(color="#16a34a", width=2),
                    mode="lines+markers"))
                fa.add_trace(go.Scatter(
                    x=df_m['date'],
                    y=pd.to_numeric(
                        df_m['predicted_avg'],
                        errors='coerce'),
                    name="Predicted Avg",
                    line=dict(color="#2563eb", width=2,
                              dash="dash"),
                    mode="lines+markers"))
                fa.update_layout(
                    title="Actual vs Predicted "
                          "Daily Average Load",
                    height=300,
                    hovermode="x unified",
                    yaxis=dict(tickformat=","),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(
                    fa, use_container_width=True)

            st.subheader("View Any Past Day")
            sel = st.selectbox(
                "Select a date",
                df_m['date'].tolist()[::-1])
            if sel:
                r  = df_m[df_m['date'] == sel].iloc[0]
                p2 = get_24hrs(r, 'pred')
                a2 = get_24hrs(r, 'actual')
                fd = go.Figure()
                fd.add_trace(go.Scatter(
                    x=hlabels, y=a2, name="Actual",
                    line=dict(color="#16a34a", width=2),
                    mode="lines+markers"))
                fd.add_trace(go.Scatter(
                    x=hlabels, y=p2, name="Predicted",
                    line=dict(color="#2563eb", width=2,
                              dash="dash"),
                    mode="lines+markers"))
                mv2 = safe_float(r.get('mape'))
                rv2 = safe_float(r.get('rmse'))
                fd.update_layout(
                    title=(f"{sel} — "
                           f"MAPE: {mv2:.2f}% | "
                           f"RMSE: {rv2:.0f} MW"
                           if mv2 else sel),
                    height=320,
                    hovermode="x unified",
                    yaxis=dict(tickformat=","),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(
                    fd, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    #  TAB 3 — 3-MONTH COMBINED FORECAST
    # ══════════════════════════════════════════════════════════
    with tab3:
        st.subheader(
            "📅 April · May · June 2026 — "
            "Combined 3-Month Forecast")

        # Load all 3 monthly files
        all_month_data = {}
        for yr, mo in FORECAST_MONTHS:
            mn    = MONTH_NAMES[mo]
            df_mo = load_monthly(mn, yr)
            if df_mo is not None and len(df_mo) > 0:
                all_month_data[(yr, mo)] = df_mo

        if not all_month_data:
            st.info(
                "### Forecast data not found\n\n"
                "Run **TN_3MONTH_FORECAST.py** in Colab "
                "and push to GitHub.\n\n"
                "Or upload the monthly CSV files "
                "using the sidebar → Manual Upload.")
        else:
            # ── Combined line chart ───────────────────────────
            fig_comb = go.Figure()
            x_offset = 0

            for (yr, mo), df_mo in all_month_data.items():
                mn    = MONTH_NAMES[mo]
                color = MONTH_COLORS[mo]
                fill  = MONTH_FILL[mo]   # FIX 1: no broken conversion
                df_mo = df_mo.sort_values('day')
                days  = df_mo['day'].tolist()
                avgs  = df_mo['predicted_avg'].tolist()
                x     = [x_offset + d for d in days]

                fig_comb.add_trace(go.Scatter(
                    x=x, y=avgs,
                    name=f"{mn} {yr}",
                    line=dict(color=color, width=2.5),
                    mode="lines+markers",
                    marker=dict(size=5),
                    fill="tozeroy",
                    fillcolor=fill))

                if x_offset > 0:
                    fig_comb.add_vline(
                        x=x_offset + 0.5,
                        line_dash="dash",
                        line_color="gray",
                        opacity=0.5)

                # Month label
                mid_x = x_offset + len(days) / 2
                fig_comb.add_annotation(
                    x=mid_x, y=0,
                    yref="paper",
                    text=f"<b>{mn}</b>",
                    showarrow=False,
                    font=dict(color=color, size=12),
                    bgcolor="rgba(255,255,255,0.7)",
                    bordercolor=color,
                    borderwidth=1)

                x_offset += calendar.monthrange(yr, mo)[1]

            fig_comb.update_layout(
                title="April + May + June 2026 — "
                      "Daily Average Load (MW)",
                xaxis_title="Day (Apr 1 → Jun 30)",
                yaxis_title="Avg Load (MW)",
                hovermode="x unified", height=430,
                legend=dict(orientation="h",
                            yanchor="bottom", y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(
                fig_comb, use_container_width=True)

            # ── Monthly comparison bar chart ──────────────────
            m_labels = [f"{MONTH_NAMES[mo]} {yr}"
                        for yr, mo in all_month_data]
            m_avgs   = [
                all_month_data[k]['predicted_avg'].mean()
                for k in all_month_data]
            m_peaks  = [
                all_month_data[k]['predicted_peak'].max()
                for k in all_month_data]
            m_colors = [MONTH_COLORS[mo]
                        for _, mo in all_month_data]

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=m_labels, y=m_avgs,
                name="Monthly Avg Load",
                marker_color=m_colors, opacity=0.85,
                text=[f"{v:,.0f}" for v in m_avgs],
                textposition='outside'))
            fig_bar.add_trace(go.Scatter(
                x=m_labels, y=m_peaks,
                name="Monthly Peak Load",
                mode="markers+lines",
                marker=dict(size=12,
                            symbol="diamond",
                            color="#dc2626"),
                line=dict(color="#dc2626",
                          width=2, dash="dot")))
            fig_bar.update_layout(
                title="Monthly Summary — "
                      "Avg and Peak Load",
                yaxis_title="Load (MW)",
                height=360,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(
                fig_bar, use_container_width=True)

            # ── Summary metrics ───────────────────────────────
            st.subheader("Monthly Summary Statistics")
            cols = st.columns(len(all_month_data))
            for i, ((yr, mo), col) in enumerate(
                    zip(all_month_data, cols)):
                mn    = MONTH_NAMES[mo]
                df_mo = all_month_data[(yr, mo)]
                col.metric(
                    f"📅 {mn} {yr}",
                    f"{df_mo['predicted_avg'].mean():,.0f} MW",
                    f"Peak: "
                    f"{df_mo['predicted_peak'].max():,.0f} MW",
                    delta_color="off")

    # ══════════════════════════════════════════════════════════
    #  TAB 4 — 5-YEAR COMPARISON
    # ══════════════════════════════════════════════════════════
    with tab4:
        st.subheader(
            "📆 5-Year Comparison — "
            "Apr / May / Jun across 2020–2026")

        sel_month_name = st.selectbox(
            "Select Month to Compare",
            ["April", "May", "June"],
            key="month_sel_5yr")
        sel_mo = [k for k, v in MONTH_NAMES.items()
                  if v == sel_month_name][0]

        df_mo_2026 = load_monthly(sel_month_name, 2026)

        if df_hist is None:
            st.warning(
                "Historical data not found on GitHub.\n\n"
                "Upload **TN_load_processed.csv** "
                "using the sidebar → Manual Upload.\n\n"
                "This file is created by the Colab notebook.")
        else:
            st.caption(
                f"Showing {sel_month_name} daily average "
                f"load for each year. "
                f"2026 shows forecast from LSTM model.")

            # ── Chart 1: Daily avg all years ──────────────────
            fig1 = build_5year_chart(
                df_hist, sel_mo, df_mo_2026)
            st.plotly_chart(
                fig1, use_container_width=True)

            # ── Chart 2: Hourly profile all years ─────────────
            fig2 = build_5year_hourly_chart(
                df_hist, sel_mo, df_mo_2026)
            st.plotly_chart(
                fig2, use_container_width=True)

            # ── Chart 3: Year-by-year bar chart ───────────────
            fig3 = build_monthly_avg_bar(
                df_hist, sel_mo, df_mo_2026)
            st.plotly_chart(
                fig3, use_container_width=True)

            # ── Growth table ──────────────────────────────────
            st.subheader(
                f"{sel_month_name} — "
                f"Year-by-Year Growth Table")
            growth_rows = []
            years_avail = []
            avgs_avail  = []

            if df_hist is not None:
                for yr in sorted(
                        df_hist['Datetime'].dt.year.unique()):
                    if yr == 2026:
                        continue
                    mask = (
                        (df_hist['Datetime'].dt.year == yr) &
                        (df_hist['Datetime'].dt.month == sel_mo))
                    sub = df_hist[mask]
                    if len(sub) > 0:
                        years_avail.append(yr)
                        avgs_avail.append(sub['load'].mean())

            # Add 2026
            if (df_mo_2026 is not None and
                    len(df_mo_2026) > 0):
                years_avail.append(2026)
                avgs_avail.append(
                    df_mo_2026['predicted_avg'].mean())

            for i, (yr, avg) in enumerate(
                    zip(years_avail, avgs_avail)):
                if i > 0:
                    prev_avg = avgs_avail[i - 1]
                    yoy = ((avg - prev_avg) /
                           prev_avg * 100)
                    growth_str = f"{yoy:+.1f}%"
                else:
                    growth_str = "—"
                label = (f"{yr} (Forecast)"
                         if yr == 2026 else str(yr))
                growth_rows.append({
                    "Year"          : label,
                    "Avg Load (MW)" : f"{avg:,.0f}",
                    "YoY Growth"    : growth_str,
                })

            if growth_rows:
                df_growth = pd.DataFrame(growth_rows)
                st.dataframe(
                    df_growth,
                    use_container_width=True,
                    hide_index=True)

    # ══════════════════════════════════════════════════════════
    #  TAB 5 — ALL RESULTS
    # ══════════════════════════════════════════════════════════
    with tab5:
        st.subheader(f"All Results — {len(df)} rows")
        show_cols = ['date', 'mape', 'rmse',
                     'actual_avg', 'predicted_avg',
                     'actual_peak', 'predicted_peak']
        avail = [c for c in show_cols if c in df.columns]
        ds    = df[avail].copy()
        for col in ['mape', 'rmse', 'actual_avg',
                    'predicted_avg', 'predicted_peak']:
            if col in ds.columns:
                ds[col] = pd.to_numeric(
                    ds[col], errors='coerce').round(1)
        ds.columns = [c.replace('_', ' ').title()
                      for c in ds.columns]
        st.dataframe(
            ds, use_container_width=True,
            hide_index=True, height=450)
        st.download_button(
            "⬇ Download All Results CSV",
            df.to_csv(index=False).encode(),
            "TN_all_results.csv", "text/csv",
            use_container_width=True)

    # ══════════════════════════════════════════════════════════
    #  TAB 6 — ABOUT
    # ══════════════════════════════════════════════════════════
    with tab6:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
### System Overview
**Data** — 2020-01-01 to 2026-03-31
6+ years Tamil Nadu hourly grid data

**Model** — Stacked LSTM Neural Network
- LSTM Layer 1: 128 units
- LSTM Layer 2: 64 units
- Dense: 32 units → Output: 24 units
- Lookback: 168 hours (7 days)
- Features: 22 (including real wind100)

**Forecast Targets**
- April 2026: 30 days
- May 2026:   31 days
- June 2026:  30 days
- Total:      91 days

**Accuracy (typical)**
- MAPE below 5% = excellent
- Improves with each new month of data
            """)
        with c2:
            st.markdown("""
### Dashboard Tabs
| Tab | Contents |
|-----|----------|
| Daily Forecast | Today actual vs predicted + Tomorrow |
| Accuracy | MAPE/RMSE trend, past day viewer |
| 3-Month Forecast | Apr+May+Jun combined view |
| 5-Year Comparison | Each month vs all previous years |
| All Results | Complete data table + download |

### 5-Year Comparison
Shows the same month (April/May/June)
across 2020, 2021, 2022, 2023, 2024, 2025
and 2026 forecast together.

Highlights year-on-year load growth in
Tamil Nadu (avg ~4-6% growth per year).

### User Roles
**Admin** — Upload + view everything
**Viewer** — View everything (no upload)
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

    show_sidebar(
        st.session_state['username'],
        st.session_state['role'])
    show_dashboard(
        st.session_state['username'],
        st.session_state['role'])

if __name__ == "__main__":
    main()
