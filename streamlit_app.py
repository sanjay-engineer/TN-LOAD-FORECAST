# ================================================================
#  TN INTELLIGENT LOAD FORECASTING — STREAMLIT WEB APP
#  COMPLETE VERSION WITH ALL FEATURES
#
#  TABS:
#  1  📈  Daily Forecast      (today + tomorrow)
#  2  📊  Monthly Prediction  (bar+line, each month separate,
#                              per-day picker below each month)
#  3  🗓️  Prev Year Compare   (2026 vs 2025 per month)
#  4  📉  5-Year Comparison   (2021–2026 bar + line)
#  5  🎯  Accuracy            (MAPE / RMSE trend)
#  6  📋  All Results         (full data table + download)
#  7  📖  About
#
#  BUG FIXES vs previous version:
#  ✓ hex_to_rgba helper — no more fillcolor crash
#  ✓ All fillcolor calls use safe helper
#  ✓ Safe .get() with None guards throughout
#  ✓ Admin can upload each month's CSV individually
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import hashlib, json, os, calendar, requests, datetime as dtmod
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide",
)

# ── GitHub settings ────────────────────────────────────────────
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

FORECAST_MONTHS = [(2026, 4), (2026, 5), (2026, 6)]
MONTH_NAMES     = {4: 'April',   5: 'May',     6: 'June'}
MONTH_COLORS    = {4: '#2563eb', 5: '#16a34a', 6: '#ea580c'}
YEAR_COLORS     = {
    2020: '#94a3b8', 2021: '#64748b', 2022: '#818cf8',
    2023: '#f59e0b', 2024: '#10b981', 2025: '#6366f1',
    2026: '#ef4444',
}
COMPARE_YEARS   = [2021, 2022, 2023, 2024, 2025, 2026]

# ── Colour helper ──────────────────────────────────────────────
def rgba(hex_color: str, alpha: float = 0.10) -> str:
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f'rgba({r},{g},{b},{alpha})'

BLANK_LAYOUT = dict(
    plot_bgcolor  = "rgba(0,0,0,0)",
    paper_bgcolor = "rgba(0,0,0,0)",
    hovermode     = "x unified",
    yaxis         = dict(tickformat=","),
    legend        = dict(orientation="h", yanchor="bottom", y=1.02),
)


# ══════════════════════════════════════════════════════════════
#  USER SYSTEM
# ══════════════════════════════════════════════════════════════
def _hp(p): return hashlib.sha256(p.encode()).hexdigest()

def _lu():
    if not os.path.exists(USERS_FILE): return {}
    with open(USERS_FILE) as f: return json.load(f)

def _su(u):
    with open(USERS_FILE,"w") as f: json.dump(u,f,indent=2)

def register_user(u, p):
    if len(u)<3:  return False,"Username too short"
    if len(u)>20: return False,"Username too long"
    if not u.replace("_","").isalnum():
        return False,"Letters, numbers, underscore only"
    if len(p)<6: return False,"Password min 6 chars"
    users=_lu()
    if u.lower() in [x.lower() for x in users]:
        return False,"Username taken"
    users[u]={"password":_hp(p),"role":"viewer",
              "created":str(dtmod.date.today()),
              "last_login":None}
    _su(users); return True,"Account created — login now"

def login_user(u, p):
    users=_lu()
    m=next((x for x in users if x.lower()==u.lower()),None)
    if not m: return False,"Username not found",None
    if users[m]["password"]!=_hp(p):
        return False,"Wrong password",None
    users[m]["last_login"]=str(dtmod.datetime.now())
    _su(users); return True,m,users[m].get("role","viewer")

def make_admin(u, secret):
    if secret!="TN2025Admin": return False,"Wrong secret key"
    users=_lu()
    m=next((x for x in users if x.lower()==u.lower()),None)
    if not m: return False,f"User '{u}' not found"
    users[m]["role"]="admin"; _su(users)
    return True,f"'{m}' is now Admin"


# ══════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=120)
def gh_fetch(fname):
    try:
        r = requests.get(f"{GITHUB_RAW}/{fname}", timeout=10)
        return r.text if r.status_code==200 else None
    except: return None

@st.cache_data(ttl=120)
def load_results():
    data = gh_fetch("rolling_results.csv")
    if data:
        try: return pd.read_csv(StringIO(data)),"github"
        except: pass
    if os.path.exists(LOCAL_RESULTS):
        return pd.read_csv(LOCAL_RESULTS),"local"
    return None, None

@st.cache_data(ttl=120)
def load_monthly_csv(month_name, year):
    fname = f"{month_name.lower()}_{year}_results.csv"
    data  = gh_fetch(fname)
    if data:
        try: return pd.read_csv(StringIO(data))
        except: pass
    local = os.path.join(SHARED_DIR, fname)
    if os.path.exists(local): return pd.read_csv(local)
    return None

@st.cache_data(ttl=300)
def load_history_csv():
    """Load the uploaded history file if admin put it locally."""
    local = os.path.join(SHARED_DIR, "history_data.csv")
    if os.path.exists(local):
        try:
            df = pd.read_csv(local)
            df.columns = [c.strip() for c in df.columns]
            try: df['Datetime'] = pd.to_datetime(
                df['Datetime'], dayfirst=True)
            except: df['Datetime'] = pd.to_datetime(df['Datetime'])
            return df.sort_values('Datetime').reset_index(drop=True)
        except: pass
    return None

def sf(v):
    try:
        x = float(v); return None if np.isnan(x) else x
    except: return None

def get24(row, prefix):
    return [sf(row.get(f'{prefix}_h{h:02d}')) for h in range(24)]


# ══════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════════════
def show_login():
    st.markdown("""
    <div style='text-align:center;padding:40px 0 20px'>
      <div style='font-size:54px'>⚡</div>
      <h2 style='color:#2563eb;margin:8px 0 4px'>
        TN Intelligent Load Forecasting</h2>
      <p style='color:#64748b;font-size:14px'>
        Tamil Nadu Power Grid · Rolling LSTM · Q2 2026</p>
    </div>""", unsafe_allow_html=True)
    st.divider()

    t1,t2,t3 = st.tabs(["🔑 Login","📝 Register","🔧 Admin"])
    with t1:
        with st.form("lf"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            s = st.form_submit_button("Login",
                use_container_width=True, type="primary")
        if s:
            if not u or not p: st.error("Enter both fields")
            else:
                ok,res,role=login_user(u,p)
                if ok:
                    st.session_state.update(
                        logged_in=True,username=res,role=role)
                    st.rerun()
                else: st.error(f"❌ {res}")

    with t2:
        with st.form("rf"):
            nu=st.text_input("Username")
            np_=st.text_input("Password",type="password")
            cp=st.text_input("Confirm Password",type="password")
            rb=st.form_submit_button("Create Account",
               use_container_width=True,type="primary")
        if rb:
            if not nu or not np_ or not cp: st.error("Fill all")
            elif np_!=cp: st.error("Passwords don't match")
            else:
                ok,msg=register_user(nu,np_)
                (st.success if ok else st.error)(msg)

    with t3:
        st.info("Secret Key: **TN2025Admin**")
        with st.form("af"):
            au=st.text_input("Username")
            ak=st.text_input("Admin Key",type="password")
            ab=st.form_submit_button("Make Admin",
               use_container_width=True)
        if ab:
            ok,msg=make_admin(au,ak)
            (st.success if ok else st.error)(msg)


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
def show_sidebar(username, role):
    with st.sidebar:
        bg = "#7c3aed" if role=="admin" else "#2563eb"
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

        # GitHub status
        st.subheader("🔗 Data Source")
        try:
            r=requests.head(f"{GITHUB_RAW}/rolling_results.csv",
                            timeout=5)
            ok = r.status_code==200
        except: ok=False
        if ok:
            st.success("✅ GitHub — Live")
            if st.button("🔄 Refresh",use_container_width=True):
                st.cache_data.clear(); st.rerun()
        else:
            st.warning("⚠ GitHub not connected")

        st.divider()

        if role=="admin":
            with st.expander("📂 Upload Results"):
                rf=st.file_uploader("rolling_results.csv",
                                     type=["csv"],key="rfu")
                if rf:
                    pd.read_csv(rf).to_csv(LOCAL_RESULTS,
                                           index=False)
                    st.success("✓ Saved")
                    st.cache_data.clear()
                for yr,mo in FORECAST_MONTHS:
                    mn=MONTH_NAMES[mo]; key=f"mf{mo}"
                    mf=st.file_uploader(
                        f"{mn.lower()}_{yr}_results.csv",
                        type=["csv"],key=key)
                    if mf:
                        p=os.path.join(
                            SHARED_DIR,
                            f"{mn.lower()}_{yr}_results.csv")
                        pd.read_csv(mf).to_csv(p,index=False)
                        st.success(f"✓ {mn} saved")
                        st.cache_data.clear()
                hf=st.file_uploader(
                    "history_data.csv (2020–2026)",
                    type=["csv"],key="hfu")
                if hf:
                    p=os.path.join(SHARED_DIR,"history_data.csv")
                    pd.read_csv(hf).to_csv(p,index=False)
                    st.success("✓ History saved")
                    st.cache_data.clear()

        st.divider()
        if st.button("🚪 Logout",use_container_width=True):
            st.session_state.update(
                logged_in=False,username=None,role=None)
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  HELPER: metric cards
# ══════════════════════════════════════════════════════════════
def metric_card(col, label, value, sub="", color="#2563eb"):
    col.markdown(
        f"<div style='background:white;border:1px solid #e2e8f0;"
        f"border-radius:10px;padding:14px 16px;"
        f"border-left:4px solid {color}'>"
        f"<p style='color:#64748b;font-size:12px;"
        f"margin:0 0 4px'>{label}</p>"
        f"<p style='color:{color};font-size:22px;"
        f"font-weight:700;margin:0'>{value}</p>"
        f"<p style='color:#94a3b8;font-size:11px;"
        f"margin:4px 0 0'>{sub}</p></div>",
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════
def show_dashboard(username, role):
    st.markdown(
        f"<h2 style='color:#2563eb;margin-bottom:2px'>"
        f"⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b;margin:0'>"
        f"Tamil Nadu Power Grid · Rolling LSTM · "
        f"Q2 2026 · Welcome <b>{username}</b></p>",
        unsafe_allow_html=True)
    st.divider()

    df, source = load_results()
    if df is None or len(df)==0:
        st.info("### No results yet\n\nRun the Colab notebook "
                "and upload / push to GitHub.")
        return

    if source=="github": st.success("✅ Live data from GitHub")
    else:                st.info("📁 Locally uploaded data")

    df['has_actual'] = df.get('actual_h00','').apply(
        lambda x: pd.notna(x) and str(x) not in ['','nan','None'])
    df_past   = df[df['has_actual']].copy()
    df_future = df[~df['has_actual']].copy()
    df_m      = (df_past[df_past['mape'].notna()].copy()
                 if 'mape' in df_past.columns else pd.DataFrame())
    hlabels   = [f"{h:02d}:00" for h in range(24)]

    # ── KPI strip ─────────────────────────────────────────────
    k1,k2,k3,k4,k5 = st.columns(5)
    metric_card(k1,"📅 Days Predicted",str(len(df_past)))
    if len(df_m):
        metric_card(k2,"🎯 Avg MAPE",
                    f"{df_m['mape'].mean():.2f}%",
                    color="#ea580c")
        idx=df_m['mape'].idxmin()
        metric_card(k3,"🏆 Best MAPE",
                    f"{df_m.loc[idx,'mape']:.2f}%",
                    str(df_m.loc[idx,'date']),
                    color="#16a34a")
        metric_card(k4,"📊 Avg RMSE",
                    f"{df_m['rmse'].mean():.0f} MW",
                    color="#7c3aed")
    metric_card(k5,"🔮 Forecast","Apr·May·Jun 2026",
                color="#2563eb")
    st.divider()

    # ── TABS ──────────────────────────────────────────────────
    (tab1,tab2,tab3,tab4,
     tab5,tab6,tab7) = st.tabs([
        "📈 Daily Forecast",
        "📊 Monthly Prediction",
        "🗓️ Prev Year Compare",
        "📉 5-Year Comparison",
        "🎯 Accuracy",
        "📋 All Results",
        "📖 About",
    ])

    # ══════════════════════════════════════════════════════════
    # TAB 1 — DAILY FORECAST
    # ══════════════════════════════════════════════════════════
    with tab1:
        st.subheader("📊 Latest Day — Predicted vs Actual")
        if len(df_past)==0:
            st.info("No actual data yet.")
        else:
            row    = df_past.iloc[-1]
            pred   = get24(row,'pred')
            actual = get24(row,'actual')
            vp     = [v for v in pred if v is not None]
            mv     = sf(row.get('mape'))
            rv     = sf(row.get('rmse'))

            c1,c2,c3,c4 = st.columns(4)
            if mv:
                col=(  "green" if mv<5 else
                     "orange" if mv<10 else "red")
                c1.markdown(
                    f"<h3 style='color:{col}'>{mv:.2f}%</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"MAPE</p>", unsafe_allow_html=True)
            if rv:
                c2.markdown(
                    f"<h3>{rv:.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"RMSE</p>", unsafe_allow_html=True)
            if vp:
                c3.markdown(
                    f"<h3 style='color:#2563eb'>"
                    f"{max(vp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Peak</p>", unsafe_allow_html=True)
            c4.markdown(
                f"<h3>{row['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>"
                f"Date</p>", unsafe_allow_html=True)

            fig=go.Figure()
            if any(v is not None for v in actual):
                fig.add_trace(go.Scatter(
                    x=hlabels,y=actual,name="Actual",
                    line=dict(color="#16a34a",width=3),
                    mode="lines+markers",marker=dict(size=7),
                    fill="tozeroy",
                    fillcolor="rgba(22,163,74,0.07)"))
            fig.add_trace(go.Scatter(
                x=hlabels,y=pred,name="Predicted",
                line=dict(color="#2563eb",width=2.5,dash="dash"),
                mode="lines+markers",marker=dict(size=6)))
            fig.update_layout(
                title=f"Hourly Forecast — {row['date']}",
                xaxis_title="Hour",yaxis_title="Load (MW)",
                height=380,**BLANK_LAYOUT)
            st.plotly_chart(fig,use_container_width=True)

        st.divider()
        st.subheader("🔮 Next Day Forecast")
        if len(df_future)>0:
            nr   = df_future.iloc[0]
            np_  = get24(nr,'pred')
            vnp  = [v for v in np_ if v is not None]
            n1,n2,n3,n4=st.columns(4)
            if vnp:
                n1.markdown(
                    f"<h3 style='color:#ea580c'>"
                    f"{max(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Peak</p>",unsafe_allow_html=True)
                n2.markdown(
                    f"<h3>{min(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Min</p>",unsafe_allow_html=True)
                n3.markdown(
                    f"<h3>{np.mean(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Avg</p>",unsafe_allow_html=True)
            n4.markdown(
                f"<h3 style='color:#7c3aed'>"
                f"{nr['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>"
                f"Date</p>",unsafe_allow_html=True)
            fig2=go.Figure()
            fig2.add_trace(go.Scatter(
                x=hlabels,y=np_,name="Forecast",
                line=dict(color="#ea580c",width=3),
                mode="lines+markers",
                marker=dict(size=8,symbol="diamond"),
                fill="tozeroy",
                fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph=np_.index(max(vnp))
                fig2.add_annotation(
                    x=hlabels[ph],y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True,arrowhead=2,
                    arrowcolor="#ea580c",ay=-40,
                    font=dict(color="#ea580c",size=11),
                    bgcolor="white",bordercolor="#ea580c",
                    borderwidth=1.5)
            fig2.update_layout(
                title=f"Next Day — {nr['date']}",
                xaxis_title="Hour",yaxis_title="Load (MW)",
                height=370,**BLANK_LAYOUT)
            st.plotly_chart(fig2,use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 2 — MONTHLY PREDICTION
    # (each month separate: bar + line + day picker)
    # ══════════════════════════════════════════════════════════
    with tab2:
        st.subheader("📊 Monthly Prediction — "
                     "April · May · June 2026")

        for yr, mo in FORECAST_MONTHS:
            mn    = MONTH_NAMES[mo]
            col   = MONTH_COLORS[mo]
            ndays = calendar.monthrange(yr, mo)[1]

            df_mo = load_monthly_csv(mn, yr)
            if df_mo is None or len(df_mo)==0:
                st.warning(f"No data for {mn} {yr} — "
                            f"upload or push to GitHub.")
                continue

            df_mo  = df_mo.sort_values('day')
            days   = df_mo['day'].tolist()
            avgs   = df_mo['predicted_avg'].tolist()
            peaks  = df_mo['predicted_peak'].tolist()
            mins_  = (df_mo['predicted_min'].tolist()
                      if 'predicted_min' in df_mo.columns
                      else [0]*len(days))
            roll7  = (pd.Series(avgs).rolling(7,min_periods=1)
                      .mean().tolist())
            has_act = ('actual_avg' in df_mo.columns and
                       df_mo['actual_avg'].notna().any())
            act_avgs  = (df_mo['actual_avg'].tolist()
                         if has_act else [])
            act_peaks = (df_mo['actual_peak'].tolist()
                         if has_act and 'actual_peak' in df_mo.columns
                         else [])

            # Month header
            st.markdown(
                f"<div style='background:white;"
                f"border-left:5px solid {col};"
                f"padding:14px 20px;margin:20px 0 10px;"
                f"border-radius:0 8px 8px 0;"
                f"box-shadow:0 1px 4px rgba(0,0,0,0.08)'>"
                f"<h3 style='color:{col};margin:0'>"
                f"📅 {mn} {yr}</h3></div>",
                unsafe_allow_html=True)

            # Month KPIs
            kc1,kc2,kc3,kc4 = st.columns(4)
            metric_card(kc1,"Days",str(ndays),color=col)
            metric_card(kc2,"Avg Load",
                        f"{np.mean(avgs):,.0f} MW",color=col)
            metric_card(kc3,"Peak Load",
                        f"{max(peaks):,.0f} MW",color=col)
            if df_mo['mape'].notna().any() if 'mape' in df_mo.columns else False:
                metric_card(kc4,"Avg MAPE",
                            f"{df_mo['mape'].mean():.2f}%",
                            color="#ea580c")
            st.markdown("<br>", unsafe_allow_html=True)

            # ── BAR CHART ────────────────────────────────────
            st.markdown(f"**Bar Chart — {mn} {yr} "
                        f"Daily Load**")
            fig_bar = go.Figure()
            # Predicted bar
            fig_bar.add_trace(go.Bar(
                x=days, y=avgs,
                name=f"Predicted Avg",
                marker_color=col, opacity=0.85,
                offsetgroup=0))
            # Actual bar
            if has_act:
                fig_bar.add_trace(go.Bar(
                    x=days, y=act_avgs,
                    name="Actual Avg",
                    marker_color="#94a3b8", opacity=0.85,
                    offsetgroup=1))
            # Peak line overlay
            fig_bar.add_trace(go.Scatter(
                x=days, y=peaks,
                name="Predicted Peak",
                mode="lines+markers",
                line=dict(color=col,width=2,dash="dot"),
                marker=dict(size=5,symbol="triangle-up"),
                yaxis="y"))
            fig_bar.update_layout(
                barmode="group",
                xaxis_title=f"Day of {mn}",
                yaxis_title="Load (MW)",
                height=370,
                xaxis=dict(tickmode='linear',tick0=1,dtick=2),
                **BLANK_LAYOUT)
            st.plotly_chart(fig_bar, use_container_width=True)

            # ── LINE CHART ───────────────────────────────────
            st.markdown(f"**Line Chart — {mn} {yr} "
                        f"Avg · Peak · Min · Rolling**")
            fig_line = go.Figure()
            # Min-Peak band
            fig_line.add_trace(go.Scatter(
                x=days+days[::-1],
                y=peaks+mins_[::-1],
                fill='toself',
                fillcolor=rgba(col, 0.08),
                line=dict(width=0),
                name='Min–Peak Band',
                showlegend=True))
            fig_line.add_trace(go.Scatter(
                x=days, y=avgs,
                name="Avg Load",
                line=dict(color=col,width=2.5),
                mode="lines+markers",
                marker=dict(size=5)))
            fig_line.add_trace(go.Scatter(
                x=days, y=peaks,
                name="Peak Load",
                line=dict(color=col,width=1.5,dash="dot"),
                mode="lines+markers",
                marker=dict(size=4,symbol="triangle-up")))
            if any(v>0 for v in mins_):
                fig_line.add_trace(go.Scatter(
                    x=days, y=mins_,
                    name="Min Load",
                    line=dict(color=col,width=1.5,dash="dot"),
                    mode="lines+markers",
                    marker=dict(size=4,symbol="triangle-down")))
            fig_line.add_trace(go.Scatter(
                x=days, y=roll7,
                name="7-Day Rolling Avg",
                line=dict(color="#dc2626",width=2.2,dash="dash")))
            if has_act:
                fig_line.add_trace(go.Scatter(
                    x=days, y=act_avgs,
                    name="Actual Avg",
                    line=dict(color="#334155",width=2,dash="dashdot"),
                    mode="lines+markers",marker=dict(size=5)))
            # Peak annotation
            pk_i = peaks.index(max(peaks))
            fig_line.add_annotation(
                x=days[pk_i], y=max(peaks),
                text=f"Peak {max(peaks):,.0f} MW",
                showarrow=True, arrowhead=2,
                arrowcolor=col, ay=-45,
                font=dict(color=col,size=10),
                bgcolor="white", bordercolor=col,
                borderwidth=1.5)
            fig_line.update_layout(
                xaxis_title=f"Day of {mn}",
                yaxis_title="Load (MW)",
                height=380,
                xaxis=dict(tickmode='linear',tick0=1,dtick=2),
                **BLANK_LAYOUT)
            st.plotly_chart(fig_line, use_container_width=True)

            # ── INDIVIDUAL DAY PICKER ─────────────────────────
            st.markdown(
                f"**🔍 Day-Level View — Select a Day in "
                f"{mn} {yr}**")
            sel_day = st.slider(
                f"Day of {mn}",
                min_value=1, max_value=ndays, value=1,
                key=f"slider_{mo}")

            day_row = df_mo[df_mo['day']==sel_day]
            if len(day_row)>0:
                r     = day_row.iloc[0]
                dpred = get24(r,'pred')
                dact  = get24(r,'actual')
                vdp   = [v for v in dpred if v is not None]

                # Day KPIs
                dk1,dk2,dk3,dk4 = st.columns(4)
                avg_v  = sf(r.get('predicted_avg')) or (
                    np.mean(vdp) if vdp else 0)
                peak_v = sf(r.get('predicted_peak')) or (
                    max(vdp) if vdp else 0)
                metric_card(dk1,"Date",str(r['date']),color=col)
                metric_card(dk2,"Predicted Avg",
                            f"{avg_v:,.0f} MW",color=col)
                metric_card(dk3,"Predicted Peak",
                            f"{peak_v:,.0f} MW",color=col)
                if pd.notna(r.get('mape')):
                    metric_card(dk4,"MAPE",
                                f"{r['mape']:.2f}%",
                                color="#ea580c")
                st.markdown("<br>", unsafe_allow_html=True)

                fig_day = go.Figure()
                fig_day.add_trace(go.Scatter(
                    x=list(range(24)), y=dpred,
                    name=f"Predicted — {mn} {sel_day}",
                    line=dict(color=col,width=2.8),
                    mode="lines+markers",
                    marker=dict(size=8,symbol="circle"),
                    fill="tozeroy",
                    fillcolor=rgba(col, 0.08)))
                if any(v is not None for v in dact):
                    fig_day.add_trace(go.Scatter(
                        x=list(range(24)), y=dact,
                        name="Actual",
                        line=dict(color="#334155",width=2,
                                  dash="dash"),
                        mode="lines+markers",
                        marker=dict(size=7)))
                if vdp:
                    ph = dpred.index(max(vdp))
                    fig_day.add_annotation(
                        x=ph, y=max(vdp),
                        text=f"Peak: {max(vdp):,.0f} MW",
                        showarrow=True, arrowhead=2,
                        arrowcolor=col, ay=-45,
                        font=dict(color=col,size=11),
                        bgcolor="white",bordercolor=col,
                        borderwidth=1.5)
                fig_day.update_layout(
                    title=(f"{mn} {sel_day}, {yr} — "
                           f"24-Hour Load Forecast  |  "
                           f"Avg: {avg_v:,.0f} MW  |  "
                           f"Peak: {peak_v:,.0f} MW"),
                    xaxis_title="Hour of Day",
                    yaxis_title="Load (MW)",
                    height=370,
                    xaxis=dict(
                        tickmode='array',
                        tickvals=list(range(24)),
                        ticktext=[f"{h:02d}:00"
                                  for h in range(24)]),
                    **BLANK_LAYOUT)
                st.plotly_chart(fig_day,
                    use_container_width=True)

            st.markdown("---")  # separator between months

    # ══════════════════════════════════════════════════════════
    # TAB 3 — PREVIOUS YEAR COMPARISON (2025 vs 2026)
    # ══════════════════════════════════════════════════════════
    with tab3:
        st.subheader("🗓️ Previous Year Comparison — "
                     "2026 Forecast vs 2025 Actual")

        df_hist = load_history_csv()

        if df_hist is None:
            st.info("Upload **history_data.csv** (2020–2026) "
                    "via Admin → Upload Results to enable "
                    "this comparison.")
        else:
            df_hist['year']  = df_hist['Datetime'].dt.year
            df_hist['month'] = df_hist['Datetime'].dt.month
            df_hist['day_n'] = df_hist['Datetime'].dt.day

            sel_mo_py = st.selectbox(
                "Select Month",
                [f"{MONTH_NAMES[mo]} 2026"
                 for _,mo in FORECAST_MONTHS],
                key="py_sel")
            sel_mo_n = next(
                mo for mo in MONTH_NAMES
                if MONTH_NAMES[mo]==sel_mo_py.split()[0])
            mn  = MONTH_NAMES[sel_mo_n]
            col = MONTH_COLORS[sel_mo_n]

            df_mo = load_monthly_csv(mn, 2026)

            sub25 = df_hist[(df_hist['year']==2025) &
                            (df_hist['month']==sel_mo_n)]
            p25 = (sub25.groupby('day_n')['load']
                   .agg(['mean','max','min'])
                   .reset_index()
                   .rename(columns={'day_n':'day',
                                    'mean':'avg25',
                                    'max':'peak25',
                                    'min':'min25'}))

            if df_mo is None or len(df_mo)==0:
                st.info(f"No forecast data for {mn} 2026 yet.")
            else:
                df_mo  = df_mo.sort_values('day')
                merged = df_mo.merge(p25, on='day', how='left')
                days   = merged['day'].tolist()
                avgs26 = merged['predicted_avg'].tolist()
                pk26   = merged['predicted_peak'].tolist()
                avgs25 = merged['avg25'].tolist()
                pk25   = merged['peak25'].tolist()

                growth = ((np.mean(avgs26)-np.nanmean(avgs25)) /
                          np.nanmean(avgs25)*100
                          if np.nanmean(avgs25) else 0)

                # KPIs
                pc1,pc2,pc3,pc4 = st.columns(4)
                metric_card(pc1,"2026 Avg",
                    f"{np.mean(avgs26):,.0f} MW",color=col)
                metric_card(pc2,"2025 Avg",
                    f"{np.nanmean(avgs25):,.0f} MW",
                    color="#475569")
                metric_card(pc3,"YoY Growth",
                    f"{growth:+.1f}%",
                    color="#16a34a" if growth>0 else "#ef4444")
                metric_card(pc4,"2026 Peak",
                    f"{max(pk26):,.0f} MW",color=col)
                st.markdown("<br>", unsafe_allow_html=True)

                # Bar chart
                st.markdown(f"**Bar Chart — {mn} 2026 vs 2025**")
                fig_pb = go.Figure()
                fig_pb.add_trace(go.Bar(
                    x=days, y=avgs26,
                    name=f"{mn} 2026 (Forecast)",
                    marker_color=col, opacity=0.85,
                    offsetgroup=0))
                fig_pb.add_trace(go.Bar(
                    x=days, y=avgs25,
                    name=f"{mn} 2025 (Actual)",
                    marker_color="#94a3b8", opacity=0.85,
                    offsetgroup=1))
                fig_pb.update_layout(
                    barmode="group",
                    xaxis_title=f"Day of {mn}",
                    yaxis_title="Avg Load (MW)",
                    height=370,**BLANK_LAYOUT)
                st.plotly_chart(fig_pb,
                    use_container_width=True)

                # Line chart
                st.markdown(f"**Line Chart — {mn} 2026 vs 2025**")
                fig_pl = go.Figure()
                fig_pl.add_trace(go.Scatter(
                    x=days, y=avgs26,
                    name=f"{mn} 2026 Forecast",
                    line=dict(color=col,width=2.8),
                    mode="lines+markers",
                    marker=dict(size=5),
                    fill="tozeroy",
                    fillcolor=rgba(col,0.08)))
                fig_pl.add_trace(go.Scatter(
                    x=days, y=avgs25,
                    name=f"{mn} 2025 Actual",
                    line=dict(color="#64748b",width=2.2,
                              dash="dash"),
                    mode="lines+markers",
                    marker=dict(size=5)))
                fig_pl.update_layout(
                    xaxis_title=f"Day of {mn}",
                    yaxis_title="Avg Load (MW)",
                    height=370,**BLANK_LAYOUT)
                st.plotly_chart(fig_pl,
                    use_container_width=True)

                # Peak comparison
                st.markdown(
                    f"**Peak Load Comparison — "
                    f"{mn} 2026 vs 2025**")
                fig_pk = go.Figure()
                fig_pk.add_trace(go.Scatter(
                    x=days, y=pk26,
                    name="2026 Peak Forecast",
                    line=dict(color=col,width=2.5),
                    mode="lines+markers",
                    marker=dict(size=5,symbol="triangle-up")))
                fig_pk.add_trace(go.Scatter(
                    x=days, y=pk25,
                    name="2025 Peak Actual",
                    line=dict(color="#64748b",width=2,dash="dash"),
                    mode="lines+markers",
                    marker=dict(size=5,symbol="triangle-down")))
                fig_pk.update_layout(
                    xaxis_title=f"Day of {mn}",
                    yaxis_title="Peak Load (MW)",
                    height=330,**BLANK_LAYOUT)
                st.plotly_chart(fig_pk,
                    use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 4 — 5-YEAR COMPARISON
    # ══════════════════════════════════════════════════════════
    with tab4:
        st.subheader("📉 5-Year Comparison — 2021 to 2026")

        df_hist2 = load_history_csv()
        if df_hist2 is None:
            st.info("Upload **history_data.csv** (2020–2026) "
                    "via Admin panel to enable this chart.")
        else:
            df_hist2['year']  = df_hist2['Datetime'].dt.year
            df_hist2['month'] = df_hist2['Datetime'].dt.month
            df_hist2['day_n'] = df_hist2['Datetime'].dt.day

            sel_mo_5y = st.selectbox(
                "Select Month",
                [MONTH_NAMES[mo] for _,mo in FORECAST_MONTHS],
                key="5y_sel")
            sel_mo_n5 = next(
                mo for mo in MONTH_NAMES
                if MONTH_NAMES[mo]==sel_mo_5y)
            col5 = MONTH_COLORS[sel_mo_n5]

            # Collect daily avg per year
            year_daily  = {}
            year_monthly = {}
            for yr in COMPARE_YEARS:
                if yr==2026:
                    df_mo5 = load_monthly_csv(
                        sel_mo_5y, 2026)
                    if df_mo5 is not None and len(df_mo5):
                        df_mo5 = df_mo5.sort_values('day')
                        year_daily[yr] = list(zip(
                            df_mo5['day'].tolist(),
                            df_mo5['predicted_avg'].tolist()))
                        year_monthly[yr] = (
                            df_mo5['predicted_avg'].mean(),
                            df_mo5['predicted_peak'].max(),
                            df_mo5['predicted_avg'].min())
                else:
                    s=df_hist2[(df_hist2['year']==yr) &
                               (df_hist2['month']==sel_mo_n5)]
                    if len(s):
                        dly=(s.groupby('day_n')['load']
                             .agg(['mean','max','min'])
                             .reset_index())
                        year_daily[yr]=list(zip(
                            dly['day_n'].tolist(),
                            dly['mean'].tolist()))
                        year_monthly[yr]=(
                            s['load'].mean(),
                            s['load'].max(),
                            s['load'].min())

            if not year_daily:
                st.info("No data loaded yet.")
            else:
                # ── Line chart: daily avg per year ────────────
                st.markdown(
                    f"**Daily Avg Load — {sel_mo_5y} "
                    f"(Each Year)**")
                fig_5l = go.Figure()
                for yr in sorted(year_daily.keys()):
                    pts  = year_daily[yr]
                    d_x  = [p[0] for p in pts]
                    d_y  = [p[1] for p in pts]
                    lw   = 3.0 if yr==2026 else 1.8
                    ms   = 6   if yr==2026 else 3
                    lab  = (f"{yr} (Forecast)"
                            if yr==2026 else str(yr))
                    fig_5l.add_trace(go.Scatter(
                        x=d_x, y=d_y, name=lab,
                        line=dict(
                            color=YEAR_COLORS.get(yr,'#888'),
                            width=lw),
                        mode="lines+markers",
                        marker=dict(size=ms)))
                fig_5l.update_layout(
                    xaxis_title=f"Day of {sel_mo_5y}",
                    yaxis_title="Avg Load (MW)",
                    height=400,**BLANK_LAYOUT)
                st.plotly_chart(fig_5l,
                    use_container_width=True)

                # ── Bar chart: monthly avg per year ───────────
                st.markdown(
                    f"**Monthly Avg & Peak — {sel_mo_5y} "
                    f"(Each Year)**")
                yr_list = sorted(year_monthly.keys())
                yr_avgs = [year_monthly[y][0] for y in yr_list]
                yr_pks  = [year_monthly[y][1] for y in yr_list]
                yr_cols = [YEAR_COLORS.get(y,'#888')
                           for y in yr_list]

                fig_5b = go.Figure()
                fig_5b.add_trace(go.Bar(
                    x=[str(y) for y in yr_list],
                    y=yr_avgs,
                    name="Monthly Avg Load",
                    marker_color=yr_cols, opacity=0.88,
                    text=[f"{v:,.0f}" for v in yr_avgs],
                    textposition='outside'))
                fig_5b.add_trace(go.Scatter(
                    x=[str(y) for y in yr_list],
                    y=yr_pks, name="Monthly Peak",
                    mode="markers+lines",
                    marker=dict(size=12,symbol="diamond",
                                color="#dc2626"),
                    line=dict(color="#dc2626",width=2.2,
                              dash="dot")))
                fig_5b.update_layout(
                    xaxis_title="Year",
                    yaxis_title="Load (MW)",
                    height=370,
                    yaxis=dict(tickformat=","),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_5b,
                    use_container_width=True)

                # ── Growth table ───────────────────────────────
                st.markdown(f"**Year-on-Year Growth — "
                            f"{sel_mo_5y}**")
                rows_tbl = []
                yr_s = sorted(year_monthly.keys())
                for i, yr in enumerate(yr_s):
                    avg_v = year_monthly[yr][0]
                    pk_v  = year_monthly[yr][1]
                    if i>0:
                        prev  = year_monthly[yr_s[i-1]][0]
                        g = (avg_v-prev)/prev*100 if prev else 0
                        g_str = f"{g:+.1f}%"
                    else:
                        g_str = "—"
                    rows_tbl.append({
                        'Year':yr,
                        'Monthly Avg MW':f"{avg_v:,.0f}",
                        'Monthly Peak MW':f"{pk_v:,.0f}",
                        'YoY Growth':g_str,
                        'Note':'Forecast' if yr==2026 else 'Actual'
                    })
                st.dataframe(pd.DataFrame(rows_tbl),
                             use_container_width=True,
                             hide_index=True)

    # ══════════════════════════════════════════════════════════
    # TAB 5 — ACCURACY
    # ══════════════════════════════════════════════════════════
    with tab5:
        df_acc = df[['date','mape','rmse']].dropna(
            subset=['mape']).copy() if 'mape' in df.columns \
            else pd.DataFrame()
        if len(df_acc)==0:
            st.info("No accuracy data yet — actuals needed.")
        else:
            a1,a2,a3 = st.columns(3)
            metric_card(a1,"Avg MAPE",
                f"{df_acc['mape'].mean():.2f}%",color="#ea580c")
            metric_card(a2,"Avg RMSE",
                f"{df_acc['rmse'].mean():.0f} MW",
                color="#7c3aed")
            metric_card(a3,"Best MAPE",
                f"{df_acc['mape'].min():.2f}%",color="#16a34a")
            st.markdown("<br>",unsafe_allow_html=True)

            fig_m=px.line(df_acc,x='date',y='mape',
                title='MAPE % Over Days',markers=True,
                color_discrete_sequence=['#ea580c'])
            fig_m.add_hline(y=df_acc['mape'].mean(),
                line_dash='dash',line_color='red',
                annotation_text=
                f"Avg:{df_acc['mape'].mean():.2f}%")
            fig_m.update_layout(height=330,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_m,use_container_width=True)

            fig_r=px.line(df_acc,x='date',y='rmse',
                title='RMSE (MW) Over Days',markers=True,
                color_discrete_sequence=['#7c3aed'])
            fig_r.add_hline(y=df_acc['rmse'].mean(),
                line_dash='dash',line_color='red',
                annotation_text=
                f"Avg:{df_acc['rmse'].mean():.0f} MW")
            fig_r.update_layout(height=330,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_r,use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 6 — ALL RESULTS
    # ══════════════════════════════════════════════════════════
    with tab6:
        st.subheader(f"📋 All Results — {len(df)} rows")

        # Per-month accordion
        for yr, mo in FORECAST_MONTHS:
            mn  = MONTH_NAMES[mo]
            col = MONTH_COLORS[mo]
            df_mo6 = load_monthly_csv(mn, yr)
            if df_mo6 is None: continue
            with st.expander(
                    f"{mn} {yr} — {len(df_mo6)} days",
                    expanded=False):
                show=['day','date','predicted_avg',
                      'predicted_peak','actual_avg',
                      'actual_peak','mape','rmse']
                av=[c for c in show if c in df_mo6.columns]
                ds=df_mo6[av].copy()
                for c in ['predicted_avg','predicted_peak',
                          'actual_avg','actual_peak']:
                    if c in ds.columns:
                        ds[c]=pd.to_numeric(
                            ds[c],errors='coerce').round(1)
                for c in ['mape','rmse']:
                    if c in ds.columns:
                        ds[c]=pd.to_numeric(
                            ds[c],errors='coerce').round(2)
                ds.columns=[c.replace('_',' ').title()
                            for c in ds.columns]
                st.dataframe(ds,use_container_width=True,
                             hide_index=True)
                st.download_button(
                    f"⬇ Download {mn} {yr}",
                    df_mo6.to_csv(index=False).encode(),
                    f"{mn.lower()}_{yr}_results.csv",
                    "text/csv",
                    use_container_width=True,
                    key=f"dl_{mo}")

        st.divider()
        st.subheader("Full Combined Table")
        show_c=['date','month_name','predicted_avg',
                'predicted_peak','actual_avg',
                'actual_peak','mape','rmse']
        avc=[c for c in show_c if c in df.columns]
        dsc=df[avc].copy()
        for c in ['predicted_avg','predicted_peak',
                  'actual_avg','actual_peak']:
            if c in dsc.columns:
                dsc[c]=pd.to_numeric(
                    dsc[c],errors='coerce').round(1)
        dsc.columns=[c.replace('_',' ').title()
                     for c in dsc.columns]
        st.dataframe(dsc,use_container_width=True,
                     hide_index=True,height=450)
        st.download_button(
            "⬇ Download All Results CSV",
            df.to_csv(index=False).encode(),
            "TN_Q2_2026_all_results.csv","text/csv",
            use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 7 — ABOUT
    # ══════════════════════════════════════════════════════════
    with tab7:
        c1,c2=st.columns(2)
        with c1:
            st.markdown("""
### System Overview
**Data** · Jan 2020 – Jun 2026  
6+ years Tamil Nadu hourly load + weather

**Model** · Stacked LSTM (Rolling Retrain)
- 2 LSTM layers: 128 + 64 units
- 168-hour lookback (7 days)
- 22 features including wind100
- Auto-regressive rolling forecast
- Model retrains after each month

**Rolling Strategy**
| Month | Training Window |
|-------|----------------|
| April 2026 | Jan 2020 → Mar 2026 |
| May 2026 | Jan 2020 → Apr 2026 |
| June 2026 | Jan 2020 → May 2026 |

**Features (22)**  
temperature · humidity · rain · wind10 · wind100  
radiation · cloud_cover · hour · day_of_week  
month · day_of_year · is_summer · is_monsoon  
Week_day · is_holiday · load_lag_24/48/168  
load_roll_mean_24/168 · load_roll_std_24
            """)
        with c2:
            st.markdown("""
### Dashboard Tabs

| Tab | Content |
|-----|---------|
| 📈 Daily Forecast | Today & tomorrow 24-h forecast |
| 📊 Monthly Prediction | Bar + Line charts per month, day picker |
| 🗓️ Prev Year Compare | 2026 vs 2025 — bar, line, peak |
| 📉 5-Year Comparison | 2021–2026 line + bar + growth table |
| 🎯 Accuracy | MAPE & RMSE trends |
| 📋 All Results | Full data + per-month download |

### Monthly Prediction features
- **Bar chart** — daily avg (predicted vs actual side by side)
- **Line chart** — avg · peak · min · 7-day rolling avg
- **Min–Peak shaded band**
- **Day slider** → individual 24-hour line chart
- Annotations for peak day and peak hour

### Admin Features
Upload CSVs via sidebar to populate all charts  
without needing GitHub connection
            """)


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    for k in ['logged_in','username','role']:
        if k not in st.session_state:
            st.session_state[k]=(
                False if k=='logged_in' else None)
    if not st.session_state['logged_in']:
        show_login(); return
    show_sidebar(st.session_state['username'],
                 st.session_state['role'])
    show_dashboard(st.session_state['username'],
                   st.session_state['role'])

if __name__=="__main__":
    main()
