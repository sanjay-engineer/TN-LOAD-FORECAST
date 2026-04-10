# ================================================================
#  TN INTELLIGENT LOAD FORECASTING — STREAMLIT WEB APP
#  ROLLING 3-MONTH FORECAST: APRIL · MAY · JUNE 2026
#
#  FIXES:
#    ✓ Hex→RGBA colour conversion bug fixed
#    ✓ Monthly Graph tab added (new Tab 4)
#    ✓ Per-month hourly profile chart added
#    ✓ Weekday vs Weekend bar chart added
#    ✓ All fillcolor bugs corrected
#    ✓ Safe column access everywhere
#    ✓ Better error handling throughout
#
#  TABS:
#    Tab 1 — 📈 Daily Forecast
#    Tab 2 — 🎯 Accuracy
#    Tab 3 — 📅 3-Month Combined
#    Tab 4 — 📊 Monthly Graph      ← NEW
#    Tab 5 — 📆 Monthly Detail
#    Tab 6 — 📋 All Results
#    Tab 7 — 📖 About
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, calendar, requests
from datetime import datetime
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide",
)

# ── Settings ──────────────────────────────────────────────────
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

FORECAST_MONTHS = [(2026, 4), (2026, 5), (2026, 6)]
MONTH_NAMES     = {4: 'April',   5: 'May',     6: 'June'}
MONTH_COLORS    = {4: '#2563eb', 5: '#16a34a', 6: '#ea580c'}


# ── Colour helper ─────────────────────────────────────────────
def hex_to_rgba(hex_color: str, alpha: float = 0.10) -> str:
    """Convert #rrggbb to rgba(r,g,b,alpha) — fixes original bug."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


# ── User system ───────────────────────────────────────────────
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


# ── Data loading ──────────────────────────────────────────────
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

def safe_float(val):
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except Exception:
        return None

def get_24hrs(row, prefix):
    return [safe_float(row.get(f'{prefix}_h{h:02d}'))
            for h in range(24)]

def hourly_col(row, h):
    """Get predicted load for hour h from a result row."""
    v = row.get(f'pred_h{h:02d}')
    return safe_float(v)


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

        if role == "admin":
            with st.expander("📂 Manual Upload"):
                rf = st.file_uploader("rolling_results.csv",
                                       type=["csv"], key="ru")
                if rf:
                    pd.read_csv(rf).to_csv(LOCAL_RESULTS, index=False)
                    st.success("✓ Uploaded")
                hf = st.file_uploader("history_updated.csv",
                                       type=["csv"], key="hu")
                if hf:
                    pd.read_csv(hf).to_csv(LOCAL_HISTORY, index=False)
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
#  CHART LAYOUT DEFAULTS
# ================================================================
CHART_LAYOUT = dict(
    hovermode="x unified",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    yaxis=dict(tickformat=","),
)


# ================================================================
#  DASHBOARD
# ================================================================
def show_dashboard(username, role):
    st.markdown(
        f"<h2 style='color:#2563eb'>"
        f"⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>"
        f"Tamil Nadu Power Grid · "
        f"Rolling LSTM · Welcome <b>{username}</b></p>",
        unsafe_allow_html=True)
    st.divider()

    df, source = load_results()

    if df is None or len(df) == 0:
        st.info("### No results yet\n\n"
                "Run the Colab notebook and push to GitHub.")
        return

    if source == "github":
        st.success("✅ Live results from GitHub")
    else:
        st.info("📁 Showing manually uploaded results")

    df['has_actual'] = df['actual_h00'].apply(
        lambda x: pd.notna(x) and str(x) not in ['', 'nan', 'None'])
    df_past   = df[df['has_actual']].copy()
    df_future = df[~df['has_actual']].copy()
    df_m      = df_past[df_past['mape'].notna()].copy() \
                if 'mape' in df_past.columns else pd.DataFrame()

    hours   = list(range(24))
    hlabels = [f"{h:02d}:00" for h in hours]

    # ── KPI cards ─────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📅 Days Predicted", len(df_past))
    if len(df_m) > 0:
        c2.metric("🎯 Avg MAPE",  f"{df_m['mape'].mean():.2f}%")
        idx = df_m['mape'].idxmin()
        c3.metric("🏆 Best MAPE",
                  f"{df_m.loc[idx,'mape']:.2f}%",
                  str(df_m.loc[idx,'date']),
                  delta_color="off")
        c4.metric("📊 Avg RMSE",  f"{df_m['rmse'].mean():.0f} MW")
    c5.metric("🔮 Months Forecast", "Apr · May · Jun 2026")
    st.divider()

    # ── Tabs ──────────────────────────────────────────────────
    (tab1, tab2, tab3, tab4,
     tab5, tab6, tab7) = st.tabs([
        "📈 Daily Forecast",
        "🎯 Accuracy",
        "📅 3-Month Combined",
        "📊 Monthly Graph",
        "📆 Monthly Detail",
        "📋 All Results",
        "📖 About",
    ])

    # ══ TAB 1 — DAILY FORECAST ═══════════════════════════════
    with tab1:
        st.subheader("📊 Today — Predicted vs Actual")

        if len(df_past) == 0:
            st.info("No actual data yet")
        else:
            row    = df_past.iloc[-1]
            pred   = get_24hrs(row, 'pred')
            actual = get_24hrs(row, 'actual')
            mv     = safe_float(row.get('mape'))
            rv     = safe_float(row.get('rmse'))
            vp     = [v for v in pred if v is not None]

            m1, m2, m3, m4 = st.columns(4)
            if mv:
                col = "green" if mv < 5 else "orange" if mv < 10 else "red"
                m1.markdown(
                    f"<h3 style='color:{col}'>{mv:.2f}%</h3>"
                    f"<p style='color:#64748b;font-size:12px'>MAPE</p>",
                    unsafe_allow_html=True)
            if rv:
                m2.markdown(
                    f"<h3>{rv:.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>RMSE</p>",
                    unsafe_allow_html=True)
            if vp:
                m3.markdown(
                    f"<h3 style='color:#2563eb'>{max(vp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>Peak</p>",
                    unsafe_allow_html=True)
            m4.markdown(
                f"<h3>{row['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>Date</p>",
                unsafe_allow_html=True)

            fig = go.Figure()
            if any(v is not None for v in actual):
                fig.add_trace(go.Scatter(
                    x=hlabels, y=actual, name="Actual",
                    line=dict(color="#16a34a", width=3),
                    mode="lines+markers", marker=dict(size=7),
                    fill="tozeroy",
                    fillcolor="rgba(22,163,74,0.07)"))
            fig.add_trace(go.Scatter(
                x=hlabels, y=pred, name="Predicted",
                line=dict(color="#2563eb", width=2.5, dash="dash"),
                mode="lines+markers", marker=dict(size=6)))
            fig.update_layout(
                title=f"Daily Forecast — {row['date']}",
                xaxis_title="Hour", yaxis_title="Load (MW)",
                height=380, **CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("🔮 Tomorrow — Next Day Forecast")

        if len(df_future) > 0:
            nrow  = df_future.iloc[0]
            npred = get_24hrs(nrow, 'pred')
            vnp   = [v for v in npred if v is not None]

            n1, n2, n3, n4 = st.columns(4)
            if vnp:
                n1.markdown(
                    f"<h3 style='color:#ea580c'>{max(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>Peak</p>",
                    unsafe_allow_html=True)
                n2.markdown(
                    f"<h3>{min(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>Min</p>",
                    unsafe_allow_html=True)
                n3.markdown(
                    f"<h3>{np.mean(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>Avg</p>",
                    unsafe_allow_html=True)
            n4.markdown(
                f"<h3 style='color:#7c3aed'>{nrow['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>Date</p>",
                unsafe_allow_html=True)

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=hlabels, y=npred, name="Next Day Forecast",
                line=dict(color="#ea580c", width=3),
                mode="lines+markers",
                marker=dict(size=8, symbol="diamond"),
                fill="tozeroy", fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph = npred.index(max(vnp))
                fig2.add_annotation(
                    x=hlabels[ph], y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True, arrowhead=2,
                    arrowcolor="#ea580c",
                    font=dict(color="#ea580c", size=11),
                    bgcolor="white", bordercolor="#ea580c",
                    borderwidth=1.5, ay=-40)
            fig2.update_layout(
                title=f"Tomorrow — {nrow['date']}",
                xaxis_title="Hour", yaxis_title="Load (MW)",
                height=380, **CHART_LAYOUT)
            st.plotly_chart(fig2, use_container_width=True)

    # ══ TAB 2 — ACCURACY ════════════════════════════════════
    with tab2:
        if len(df_m) == 0:
            st.info("No accuracy data yet — "
                    "run the Colab notebook with real actuals.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                fm = px.line(df_m, x="date", y="mape",
                             title="MAPE % Over Days",
                             markers=True,
                             color_discrete_sequence=["#ea580c"])
                fm.add_hline(y=df_m['mape'].mean(),
                             line_dash="dash", line_color="red",
                             annotation_text=
                             f"Avg: {df_m['mape'].mean():.2f}%")
                fm.update_layout(height=320,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fm, use_container_width=True)
            with c2:
                fr = px.line(df_m, x="date", y="rmse",
                             title="RMSE (MW) Over Days",
                             markers=True,
                             color_discrete_sequence=["#7c3aed"])
                fr.add_hline(y=df_m['rmse'].mean(),
                             line_dash="dash", line_color="red",
                             annotation_text=
                             f"Avg: {df_m['rmse'].mean():.0f} MW")
                fr.update_layout(height=320,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fr, use_container_width=True)

    # ══ TAB 3 — 3-MONTH COMBINED ════════════════════════════
    with tab3:
        st.subheader("📅 April · May · June 2026 — 3-Month Combined Forecast")

        all_month_data = {}
        for yr, mo in FORECAST_MONTHS:
            mn    = MONTH_NAMES[mo]
            df_mo = load_monthly(mn, yr)
            if df_mo is not None and len(df_mo) > 0:
                all_month_data[(yr, mo)] = df_mo

        if not all_month_data:
            st.info("3-month forecast data not found.\n\n"
                    "Run the Colab notebook and push to GitHub.")
        else:
            # ── Combined daily avg line chart ─────────────────
            fig_comb = go.Figure()
            x_offset = 0
            for (yr, mo), df_mo in all_month_data.items():
                mn    = MONTH_NAMES[mo]
                color = MONTH_COLORS[mo]
                df_mo = df_mo.sort_values('day')
                days_x = [x_offset + d for d in df_mo['day'].tolist()]
                avgs   = df_mo['predicted_avg'].tolist()

                fig_comb.add_trace(go.Scatter(
                    x=days_x, y=avgs,
                    name=f"{mn} {yr}",
                    line=dict(color=color, width=2.5),
                    mode="lines+markers",
                    marker=dict(size=5),
                    fill="tozeroy",
                    fillcolor=hex_to_rgba(color, 0.07)))
                if x_offset > 0:
                    fig_comb.add_vline(
                        x=x_offset + 0.5, line_dash="dash",
                        line_color="gray", opacity=0.5)
                x_offset += calendar.monthrange(yr, mo)[1]

            fig_comb.update_layout(
                title="Apr + May + Jun 2026 — Daily Avg Load (MW)",
                xaxis_title="Day (Apr 1 → Jun 30)",
                yaxis_title="Avg Load (MW)",
                height=420, **CHART_LAYOUT)
            st.plotly_chart(fig_comb, use_container_width=True)

            # ── Monthly comparison bar + peak line ────────────
            months_done  = list(all_month_data.keys())
            m_labels     = [f"{MONTH_NAMES[mo]} {yr}"
                            for yr, mo in months_done]
            m_avgs       = [all_month_data[k]['predicted_avg'].mean()
                            for k in months_done]
            m_peaks      = [all_month_data[k]['predicted_peak'].max()
                            for k in months_done]
            m_colors     = [MONTH_COLORS[mo] for _, mo in months_done]

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=m_labels, y=m_avgs, name="Avg Load",
                marker_color=m_colors, opacity=0.85,
                text=[f"{v:,.0f}" for v in m_avgs],
                textposition='outside'))
            fig_bar.add_trace(go.Scatter(
                x=m_labels, y=m_peaks, name="Peak Load",
                mode="markers+lines",
                marker=dict(size=12, symbol="diamond"),
                line=dict(color="red", width=2, dash="dot")))
            fig_bar.update_layout(
                title="Monthly Comparison — Avg and Peak Load",
                yaxis_title="Load (MW)", height=350,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar, use_container_width=True)

            # ── 3-month summary metrics ───────────────────────
            st.subheader("3-Month Summary")
            cols = st.columns(len(months_done))
            for (yr, mo), col_ui in zip(months_done, cols):
                mn    = MONTH_NAMES[mo]
                df_mo = all_month_data[(yr, mo)]
                col_ui.metric(
                    f"📅 {mn} {yr}",
                    f"{df_mo['predicted_avg'].mean():,.0f} MW avg",
                    f"Peak: {df_mo['predicted_peak'].max():,.0f} MW",
                    delta_color="off")

    # ══ TAB 4 — MONTHLY GRAPH (NEW) ═════════════════════════
    with tab4:
        st.subheader("📊 Monthly Graph — Full Analysis Per Month")

        sel_mo_str = st.selectbox(
            "Select Month",
            [f"{MONTH_NAMES[mo]} {yr}" for yr, mo in FORECAST_MONTHS],
            key="mg_sel")

        sel_yr = int(sel_mo_str.split()[-1])
        sel_mo = next(mo for mo in MONTH_NAMES
                      if MONTH_NAMES[mo] == sel_mo_str.split()[0])
        mn       = MONTH_NAMES[sel_mo]
        color    = MONTH_COLORS[sel_mo]
        fc       = hex_to_rgba(color, 0.10)
        num_days = calendar.monthrange(sel_yr, sel_mo)[1]

        df_mo = load_monthly(mn, sel_yr)

        if df_mo is None or len(df_mo) == 0:
            st.info(f"No data for {mn} {sel_yr} — "
                    f"run Colab and push to GitHub.")
        else:
            df_mo = df_mo.sort_values('day')
            days  = df_mo['day'].tolist()
            avgs  = df_mo['predicted_avg'].tolist()
            peaks = df_mo['predicted_peak'].tolist()

            # Per-day min load
            mins = []
            for _, row in df_mo.iterrows():
                vals = [hourly_col(row, h) for h in range(24)]
                vals = [v for v in vals if v is not None]
                mins.append(min(vals) if vals else None)

            # 7-day rolling avg
            roll7 = pd.Series(avgs).rolling(7, min_periods=1).mean().tolist()

            # ── KPI cards ─────────────────────────────────────
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Days", num_days)
            k2.metric("Avg Load", f"{np.mean(avgs):,.0f} MW")
            k3.metric("Peak Load", f"{max(peaks):,.0f} MW")
            peak_day_i = peaks.index(max(peaks))
            k4.metric("Peak Day", f"{mn} {days[peak_day_i]}, {sel_yr}")
            st.divider()

            # ── Chart A: Daily Avg / Peak / Min / Rolling ─────
            st.markdown(f"#### 📈 Daily Load Trend — {mn} {sel_yr}")
            fig_a = go.Figure()
            # Min–Peak shaded band
            fig_a.add_trace(go.Scatter(
                x=days + days[::-1],
                y=peaks + (mins[::-1] if None not in mins else peaks[::-1]),
                fill='toself',
                fillcolor=hex_to_rgba(color, 0.08),
                line=dict(width=0),
                name='Min–Peak Band',
                showlegend=True))
            # Avg line
            fig_a.add_trace(go.Scatter(
                x=days, y=avgs, name="Avg Load",
                line=dict(color=color, width=2.5),
                mode="lines+markers", marker=dict(size=5)))
            # Peak line
            fig_a.add_trace(go.Scatter(
                x=days, y=peaks, name="Peak Load",
                line=dict(color=color, width=1.5, dash="dot"),
                mode="lines+markers",
                marker=dict(size=4, symbol="triangle-up")))
            # Min line
            if None not in mins:
                fig_a.add_trace(go.Scatter(
                    x=days, y=mins, name="Min Load",
                    line=dict(color=color, width=1.5, dash="dot"),
                    mode="lines+markers",
                    marker=dict(size=4, symbol="triangle-down")))
            # 7-day rolling avg
            fig_a.add_trace(go.Scatter(
                x=days, y=roll7, name="7-Day Rolling Avg",
                line=dict(color="#dc2626", width=2, dash="dash")))
            # Peak annotation
            fig_a.add_annotation(
                x=days[peak_day_i], y=max(peaks),
                text=f"Month Peak<br>{max(peaks):,.0f} MW",
                showarrow=True, arrowhead=2,
                arrowcolor=color,
                font=dict(color=color, size=10),
                bgcolor="white", bordercolor=color,
                borderwidth=1.5, ay=-50)
            fig_a.update_layout(
                xaxis_title=f"Day of {mn}",
                yaxis_title="Load (MW)",
                height=380,
                xaxis=dict(tickmode='linear', tick0=1, dtick=2),
                **CHART_LAYOUT)
            st.plotly_chart(fig_a, use_container_width=True)

            # ── Chart B: Average Hourly Profile ──────────────
            st.markdown(f"#### 🕐 Average Hourly Load Profile — {mn} {sel_yr}")
            hourly_avgs = []
            for h in range(24):
                vals = [hourly_col(row, h)
                        for _, row in df_mo.iterrows()]
                vals = [v for v in vals if v is not None]
                hourly_avgs.append(np.mean(vals) if vals else 0)

            fig_b = go.Figure()
            fig_b.add_trace(go.Scatter(
                x=list(range(24)), y=hourly_avgs,
                name=f"{mn} Avg Profile",
                line=dict(color=color, width=2.5),
                mode="lines+markers", marker=dict(size=6),
                fill="tozeroy", fillcolor=fc))
            # Annotate evening peak
            ep_h = hourly_avgs.index(max(hourly_avgs))
            fig_b.add_annotation(
                x=ep_h, y=max(hourly_avgs),
                text=f"Peak Hour<br>{max(hourly_avgs):,.0f} MW",
                showarrow=True, arrowhead=2,
                arrowcolor=color,
                font=dict(color=color, size=10),
                bgcolor="white", bordercolor=color,
                borderwidth=1.5, ay=-45)
            fig_b.update_layout(
                xaxis_title="Hour of Day",
                yaxis_title="Avg Load (MW)",
                height=320,
                xaxis=dict(
                    tickmode='array',
                    tickvals=list(range(24)),
                    ticktext=[f"{h:02d}:00" for h in range(24)]),
                **CHART_LAYOUT)
            st.plotly_chart(fig_b, use_container_width=True)

            # ── Chart C: Weekday vs Weekend ───────────────────
            st.markdown(f"#### 📊 Weekday vs Weekend Load — {mn} {sel_yr}")
            wd_avgs, we_avgs = [], []
            for i, d in enumerate(days):
                try:
                    import datetime as dt_mod
                    dow = dt_mod.date(sel_yr, sel_mo, int(d)).weekday()
                    if dow >= 5:
                        we_avgs.append(avgs[i])
                    else:
                        wd_avgs.append(avgs[i])
                except Exception:
                    pass
            wd_m = np.mean(wd_avgs) if wd_avgs else 0
            we_m = np.mean(we_avgs) if we_avgs else 0

            fig_c = go.Figure()
            fig_c.add_trace(go.Bar(
                x=['Weekday', 'Weekend'],
                y=[wd_m, we_m],
                marker_color=[color, '#94a3b8'],
                opacity=0.85,
                text=[f"{wd_m:,.0f} MW", f"{we_m:,.0f} MW"],
                textposition='outside'))
            fig_c.update_layout(
                title=f"Weekday vs Weekend Average Load — {mn} {sel_yr}",
                yaxis_title="Avg Load (MW)", height=320,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_c, use_container_width=True)

            # ── Month data table ──────────────────────────────
            with st.expander(f"📋 {mn} {sel_yr} Full Table"):
                show_cols = ['day', 'date',
                             'predicted_avg', 'predicted_peak']
                avail = [c for c in show_cols if c in df_mo.columns]
                ds    = df_mo[avail].copy()
                for c in ['predicted_avg', 'predicted_peak']:
                    if c in ds.columns:
                        ds[c] = pd.to_numeric(ds[c],
                            errors='coerce').round(1)
                ds.columns = [c.replace('_', ' ').title()
                              for c in ds.columns]
                st.dataframe(ds, use_container_width=True,
                             hide_index=True)
                st.download_button(
                    f"⬇ Download {mn} {sel_yr} CSV",
                    df_mo.to_csv(index=False).encode(),
                    f"{mn.lower()}_{sel_yr}_results.csv",
                    "text/csv",
                    use_container_width=True)

    # ══ TAB 5 — MONTHLY DETAIL ══════════════════════════════
    with tab5:
        st.subheader("📆 Monthly Detail — Forecast vs Previous Year")

        sel_month = st.selectbox(
            "Select Month",
            [f"{MONTH_NAMES[mo]} {yr}"
             for yr, mo in FORECAST_MONTHS],
            key="md_sel")

        sel_yr2 = int(sel_month.split()[-1])
        sel_mo2 = next(mo for mo in MONTH_NAMES
                       if MONTH_NAMES[mo] == sel_month.split()[0])
        mn2       = MONTH_NAMES[sel_mo2]
        prev_yr   = sel_yr2 - 1
        color2    = MONTH_COLORS[sel_mo2]
        num_days2 = calendar.monthrange(sel_yr2, sel_mo2)[1]

        df_mo2 = load_monthly(mn2, sel_yr2)

        if df_mo2 is None or len(df_mo2) == 0:
            st.info(f"No data for {mn2} {sel_yr2} yet")
        else:
            df_mo2 = df_mo2.sort_values('day')

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Days", len(df_mo2))
            mc2.metric("Avg Load",
                f"{df_mo2['predicted_avg'].mean():,.0f} MW")
            mc3.metric("Peak Load",
                f"{df_mo2['predicted_peak'].max():,.0f} MW")
            if 'day' in df_mo2.columns:
                pd_idx = df_mo2['predicted_peak'].idxmax()
                peak_day2 = df_mo2.loc[pd_idx, 'day']
                mc4.metric("Peak Day",
                    f"{mn2} {int(peak_day2)}, {sel_yr2}")
            st.divider()

            # Daily avg: this year vs prev year
            fig_yr = go.Figure()
            fig_yr.add_trace(go.Scatter(
                x=df_mo2['day'].tolist(),
                y=df_mo2['predicted_avg'].tolist(),
                name=f"{mn2} {sel_yr2} (Forecast)",
                line=dict(color=color2, width=2.5),
                mode="lines+markers", marker=dict(size=6),
                fill="tozeroy",
                fillcolor=hex_to_rgba(color2, 0.07)))

            df_prev2 = load_monthly(mn2, prev_yr)
            if df_prev2 is not None and len(df_prev2) > 0:
                df_prev2 = df_prev2.sort_values('day')
                y_prev = (df_prev2['actual_avg'].tolist()
                          if 'actual_avg' in df_prev2.columns
                          else df_prev2['predicted_avg'].tolist())
                fig_yr.add_trace(go.Scatter(
                    x=df_prev2['day'].tolist(), y=y_prev,
                    name=f"{mn2} {prev_yr} (Prev Year)",
                    line=dict(color="#94a3b8", width=2, dash="dash"),
                    mode="lines+markers", marker=dict(size=5)))

            fig_yr.update_layout(
                title=f"{mn2} {sel_yr2} Forecast — Daily Avg Load",
                xaxis_title=f"Day of {mn2}",
                yaxis_title="Avg Load (MW)",
                height=360,
                xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                **CHART_LAYOUT)
            st.plotly_chart(fig_yr, use_container_width=True)

            # Hourly average profile
            hourly_a2 = []
            for h in range(24):
                vals = [hourly_col(row, h)
                        for _, row in df_mo2.iterrows()]
                vals = [v for v in vals if v is not None]
                hourly_a2.append(np.mean(vals) if vals else 0)

            fig_hr = go.Figure()
            fig_hr.add_trace(go.Scatter(
                x=list(range(24)), y=hourly_a2,
                name=f"{mn2} {sel_yr2} Profile",
                line=dict(color=color2, width=2.5),
                mode="lines+markers", marker=dict(size=7),
                fill="tozeroy",
                fillcolor=hex_to_rgba(color2, 0.06)))
            fig_hr.update_layout(
                title=f"Average Hourly Load Profile — {mn2} {sel_yr2}",
                xaxis_title="Hour of Day",
                yaxis_title="Avg Load (MW)",
                height=320,
                xaxis=dict(
                    tickmode='array',
                    tickvals=list(range(24)),
                    ticktext=[f"{h:02d}:00" for h in range(24)]),
                **CHART_LAYOUT)
            st.plotly_chart(fig_hr, use_container_width=True)

            # Day selector
            st.subheader(f"View Any Day in {mn2} {sel_yr2}")
            sel_day = st.slider("Select Day", 1, num_days2, 1)
            day_row = df_mo2[df_mo2['day'] == sel_day]

            if len(day_row) > 0:
                r     = day_row.iloc[0]
                dpred = get_24hrs(r, 'pred')
                hdates= [f"{h:02d}:00" for h in range(24)]

                fig_d = go.Figure()
                fig_d.add_trace(go.Scatter(
                    x=hdates, y=dpred,
                    name=f"{mn2} {sel_day} Forecast",
                    line=dict(color=color2, width=2.5),
                    mode="lines+markers",
                    marker=dict(size=7, symbol="diamond"),
                    fill="tozeroy",
                    fillcolor=hex_to_rgba(color2, 0.07)))
                vdp = [v for v in dpred if v is not None]
                if vdp:
                    ph = dpred.index(max(vdp))
                    fig_d.add_annotation(
                        x=hdates[ph], y=max(vdp),
                        text=f"Peak: {max(vdp):,.0f} MW",
                        showarrow=True, arrowhead=2,
                        font=dict(color=color2, size=11),
                        bgcolor="white", bordercolor=color2,
                        borderwidth=1.5, ay=-40)
                avg_v  = safe_float(r.get('predicted_avg')) or 0
                peak_v = safe_float(r.get('predicted_peak')) or 0
                fig_d.update_layout(
                    title=(f"{mn2} {sel_day}, {sel_yr2} — "
                           f"Hourly Forecast  |  "
                           f"Avg: {avg_v:,.0f} MW  |  "
                           f"Peak: {peak_v:,.0f} MW"),
                    xaxis_title="Hour", yaxis_title="Load (MW)",
                    height=350, **CHART_LAYOUT)
                st.plotly_chart(fig_d, use_container_width=True)

            # Full month table
            st.subheader(f"Full {mn2} {sel_yr2} Table")
            show_cols2 = ['day','date','predicted_avg','predicted_peak']
            avail2 = [c for c in show_cols2 if c in df_mo2.columns]
            ds2    = df_mo2[avail2].copy()
            for c in ['predicted_avg', 'predicted_peak']:
                if c in ds2.columns:
                    ds2[c] = pd.to_numeric(ds2[c],
                        errors='coerce').round(1)
            ds2.columns = [c.replace('_', ' ').title()
                           for c in ds2.columns]
            st.dataframe(ds2, use_container_width=True,
                         hide_index=True, height=350)
            st.download_button(
                f"⬇ Download {mn2} {sel_yr2} CSV",
                df_mo2.to_csv(index=False).encode(),
                f"{mn2.lower()}_{sel_yr2}_results.csv",
                "text/csv",
                use_container_width=True)

    # ══ TAB 6 — ALL RESULTS ═════════════════════════════════
    with tab6:
        st.subheader(f"All Results — {len(df)} rows")
        show_cols3 = ['date','mape','rmse','actual_avg',
                      'predicted_avg','actual_peak','predicted_peak']
        avail3 = [c for c in show_cols3 if c in df.columns]
        ds3    = df[avail3].copy()
        for c in ['mape','rmse','actual_avg',
                  'predicted_avg','predicted_peak']:
            if c in ds3.columns:
                ds3[c] = pd.to_numeric(ds3[c],
                    errors='coerce').round(1)
        ds3.columns = [c.replace('_', ' ').title()
                       for c in ds3.columns]
        st.dataframe(ds3, use_container_width=True,
                     hide_index=True, height=460)
        st.download_button(
            "⬇ Download All Results",
            df.to_csv(index=False).encode(),
            "TN_all_results.csv", "text/csv",
            use_container_width=True)

    # ══ TAB 7 — ABOUT ═══════════════════════════════════════
    with tab7:
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
### Charts & Tabs

| Tab | Description |
|-----|-------------|
| Daily Forecast | Today vs Tomorrow |
| Accuracy | MAPE and RMSE trends |
| 3-Month Combined | Apr+May+Jun together |
| Monthly Graph | Full per-month analysis |
| Monthly Detail | Month vs prev year |
| All Results | Complete data table |

### Monthly Graph includes
- Daily Avg / Peak / Min trend
- 7-day rolling average
- Min–Peak shaded band
- Avg Hourly Profile (0–23h)
- Weekday vs Weekend comparison

### Features (22 total)
temperature · humidity · rain
wind10 · **wind100** (real data)
radiation · cloud_cover · hour
month · day_of_week · is_summer
is_holiday · load_lag 24/48/168
rolling_mean · rolling_std
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
