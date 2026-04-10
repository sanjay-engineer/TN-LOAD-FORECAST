# ================================================================
#  TN LOAD FORECASTING — STREAMLIT APP
#  UPDATED FOR 3-MONTH FORECAST: APRIL, MAY, JUNE 2026
#
#  NEW TABS ADDED:
#  Tab 3 — 📅 3-Month Forecast (Apr + May + Jun combined)
#  Tab 4 — 📆 Monthly Detail  (each month separately)
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

# ── Settings ──────────────────────────────────────────────────
GITHUB_USER   = "sanjay-engineer"
GITHUB_REPO   = "TN-LOAD-FORECAST"
GITHUB_BRANCH = "main"
GITHUB_RAW    = (f"https://raw.githubusercontent.com/"
                 f"{GITHUB_USER}/{GITHUB_REPO}/"
                 f"{GITHUB_BRANCH}/results")

USERS_FILE  = "users.json"
SHARED_DIR  = "shared_results"
os.makedirs(SHARED_DIR, exist_ok=True)

LOCAL_RESULTS  = os.path.join(SHARED_DIR, "rolling_results.csv")
LOCAL_HISTORY  = os.path.join(SHARED_DIR, "history_updated.csv")

FORECAST_MONTHS = [(2026, 4), (2026, 5), (2026, 6)]
MONTH_NAMES     = {4:'April', 5:'May', 6:'June'}
MONTH_COLORS    = {4:'#2563eb', 5:'#16a34a', 6:'#ea580c'}

# ── User system ───────────────────────────────────────────────
def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(u):
    with open(USERS_FILE,"w") as f:
        json.dump(u,f,indent=2)

def register_user(username, password):
    if len(username)<3: return False,"Username too short (min 3)"
    if len(username)>20: return False,"Username too long (max 20)"
    if not username.replace("_","").isalnum():
        return False,"Letters, numbers and underscore only"
    if len(password)<6: return False,"Password min 6 characters"
    users = load_users()
    if username.lower() in [u.lower() for u in users]:
        return False,"Username already taken"
    users[username] = {"password":hash_pw(password),
                       "role":"viewer",
                       "created":str(datetime.now().date()),
                       "last_login":None}
    save_users(users)
    return True,"Account created — login now"

def login_user(username, password):
    users = load_users()
    match = next((u for u in users
                  if u.lower()==username.lower()),None)
    if not match: return False,"Username not found",None
    if users[match]["password"]!=hash_pw(password):
        return False,"Wrong password",None
    users[match]["last_login"] = str(datetime.now())
    save_users(users)
    return True,match,users[match].get("role","viewer")

def make_admin(username, secret):
    if secret!="TN2025Admin":
        return False,"Wrong admin secret key"
    users = load_users()
    match = next((u for u in users
                  if u.lower()==username.lower()),None)
    if not match: return False,f"User '{username}' not found"
    users[match]["role"]="admin"
    save_users(users)
    return True,f"'{match}' is now Admin"

# ── GitHub fetch ──────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_github(filename):
    url = f"{GITHUB_RAW}/{filename}"
    try:
        r = requests.get(url, timeout=10)
        return r.text if r.status_code==200 else None
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
    except:
        return None

def get_24hrs(row, prefix):
    return [safe_float(row.get(f'{prefix}_h{h:02d}'))
            for h in range(24)]

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
            Tamil Nadu Power Grid — LSTM Forecast System</p>
    </div>""", unsafe_allow_html=True)
    st.divider()

    t1,t2,t3 = st.tabs(["🔑 Login","📝 Register",
                         "🔧 Admin Setup"])
    with t1:
        st.subheader("Login")
        with st.form("lf"):
            u = st.text_input("Username")
            p = st.text_input("Password",type="password")
            s = st.form_submit_button("Login",
                use_container_width=True,type="primary")
        if s:
            if not u or not p:
                st.error("Enter username and password")
            else:
                ok,res,role = login_user(u,p)
                if ok:
                    st.session_state.update(
                        logged_in=True,username=res,role=role)
                    st.rerun()
                else:
                    st.error(f"❌ {res}")

    with t2:
        st.subheader("Create Account")
        with st.form("rf"):
            nu = st.text_input("Username")
            np_= st.text_input("Password",type="password")
            cp = st.text_input("Confirm Password",
                               type="password")
            rb = st.form_submit_button("Create Account",
                use_container_width=True,type="primary")
        if rb:
            if not nu or not np_ or not cp:
                st.error("Fill all fields")
            elif np_!=cp: st.error("Passwords do not match")
            else:
                ok,msg = register_user(nu,np_)
                (st.success if ok else st.error)(msg)

    with t3:
        st.subheader("Make Yourself Admin")
        st.info("Secret Key: **TN2025Admin**")
        with st.form("af"):
            au = st.text_input("Your Username")
            ak = st.text_input("Admin Secret Key",
                               type="password")
            ab = st.form_submit_button("Make Admin",
                use_container_width=True)
        if ab:
            ok,msg = make_admin(au,ak)
            (st.success if ok else st.error)(msg)

# ================================================================
#  SIDEBAR
# ================================================================
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
            r = requests.head(
                f"{GITHUB_RAW}/rolling_results.csv",
                timeout=5)
            github_ok = r.status_code == 200
        except Exception:
            github_ok = False

        if github_ok:
            st.success("✅ GitHub — Auto sync")
            if st.button("🔄 Refresh",
                         use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("⚠ GitHub not connected")

        st.divider()

        # Admin upload
        if role=="admin":
            with st.expander("📂 Manual Upload"):
                rf = st.file_uploader(
                    "rolling_results.csv",
                    type=["csv"],key="ru")
                if rf:
                    pd.read_csv(rf).to_csv(
                        LOCAL_RESULTS,index=False)
                    st.success("✓ Uploaded")
                hf = st.file_uploader(
                    "history_updated.csv",
                    type=["csv"],key="hu")
                if hf:
                    pd.read_csv(hf).to_csv(
                        LOCAL_HISTORY,index=False)
                    st.success("✓ Uploaded")

        st.divider()
        if st.button("🚪 Logout",
                     use_container_width=True):
            st.session_state.update(
                logged_in=False,username=None,role=None)
            st.rerun()

# ================================================================
#  DASHBOARD
# ================================================================
def show_dashboard(username, role):
    st.markdown(
        f"<h2 style='color:#2563eb'>"
        f"⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>"
        f"Tamil Nadu Power Grid · "
        f"Welcome <b>{username}</b></p>",
        unsafe_allow_html=True)
    st.divider()

    df, source = load_results()

    if df is None or len(df)==0:
        st.info("### No results yet\n\n"
                "Run the Colab notebook and push to GitHub.")
        return

    if source=="github":
        st.success("✅ Live results from GitHub")
    else:
        st.info("📁 Showing manually uploaded results")

    # Split rows
    df['has_actual'] = df['actual_h00'].apply(
        lambda x: pd.notna(x) and str(x)
        not in ['','nan','None'])
    df_past   = df[df['has_actual']].copy()
    df_future = df[~df['has_actual']].copy()
    df_m      = df_past[df_past['mape'].notna()].copy()

    hours   = list(range(24))
    hlabels = [f"{h:02d}:00" for h in hours]

    # Stat cards
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📅 Days Predicted",  len(df_past))
    if len(df_m)>0:
        c2.metric("🎯 Avg MAPE",
                  f"{df_m['mape'].mean():.2f}%")
        idx=df_m['mape'].idxmin()
        c3.metric("🏆 Best MAPE",
                  f"{df_m.loc[idx,'mape']:.2f}%",
                  str(df_m.loc[idx,'date']),
                  delta_color="off")
        c4.metric("📊 Avg RMSE",
                  f"{df_m['rmse'].mean():.0f} MW")
    c5.metric("🔮 Months Forecast", "Apr·May·Jun 2026")
    st.divider()

    # ── TABS ─────────────────────────────────────────────────
    tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
        "📈 Daily Forecast",
        "🎯 Accuracy",
        "📅 3-Month Forecast",
        "📆 Monthly Detail",
        "📋 All Results",
        "📖 About"
    ])

    # ══ TAB 1: DAILY FORECAST ════════════════════════════════
    with tab1:

        st.subheader("📊 Today — Predicted vs Actual")

        if len(df_past)==0:
            st.info("No actual data yet")
        else:
            row    = df_past.iloc[-1]
            pred   = get_24hrs(row,'pred')
            actual = get_24hrs(row,'actual')
            mv     = safe_float(row.get('mape'))
            rv     = safe_float(row.get('rmse'))
            vp     = [v for v in pred if v]

            m1,m2,m3,m4 = st.columns(4)
            if mv:
                col = ("green" if mv<5 else
                       "orange" if mv<10 else "red")
                m1.markdown(
                    f"<h3 style='color:{col}'>"
                    f"{mv:.2f}%</h3>"
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

            fig = go.Figure()
            if any(v is not None for v in actual):
                fig.add_trace(go.Scatter(
                    x=hlabels,y=actual,
                    name="Actual",
                    line=dict(color="#16a34a",width=3),
                    mode="lines+markers",
                    marker=dict(size=7),
                    fill="tozeroy",
                    fillcolor="rgba(22,163,74,0.07)"))
            fig.add_trace(go.Scatter(
                x=hlabels,y=pred,
                name="Predicted",
                line=dict(color="#2563eb",width=2.5,
                          dash="dash"),
                mode="lines+markers",
                marker=dict(size=6)))
            fig.update_layout(
                title=f"Daily Forecast — {row['date']}",
                xaxis_title="Hour",
                yaxis_title="Load (MW)",
                hovermode="x unified",height=380,
                legend=dict(orientation="h",
                            yanchor="bottom",y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig,use_container_width=True)

        st.divider()
        st.subheader("🔮 Tomorrow — Next Day Forecast")

        if len(df_future)>0:
            nrow  = df_future.iloc[0]
            npred = get_24hrs(nrow,'pred')
            vnp   = [v for v in npred if v]

            n1,n2,n3,n4 = st.columns(4)
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

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=hlabels,y=npred,
                name="Next Day Forecast",
                line=dict(color="#ea580c",width=3),
                mode="lines+markers",
                marker=dict(size=8,symbol="diamond"),
                fill="tozeroy",
                fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph = npred.index(max(vnp))
                fig2.add_annotation(
                    x=hlabels[ph],y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True,arrowhead=2,
                    arrowcolor="#ea580c",
                    font=dict(color="#ea580c",size=11),
                    bgcolor="white",
                    bordercolor="#ea580c",
                    borderwidth=1.5,ay=-40)
            fig2.update_layout(
                title=f"Tomorrow — {nrow['date']}",
                xaxis_title="Hour",
                yaxis_title="Load (MW)",
                hovermode="x unified",height=380,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2,
                use_container_width=True)

    # ══ TAB 2: ACCURACY ══════════════════════════════════════
    with tab2:
        if len(df_m)==0:
            st.info("No accuracy data yet")
        else:
            c1,c2 = st.columns(2)
            with c1:
                fm = px.line(df_m,x="date",y="mape",
                    title="MAPE % Over Days",markers=True,
                    color_discrete_sequence=["#ea580c"])
                fm.add_hline(y=df_m['mape'].mean(),
                    line_dash="dash",line_color="red",
                    annotation_text=
                    f"Avg: {df_m['mape'].mean():.2f}%")
                fm.update_layout(height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fm,
                    use_container_width=True)
            with c2:
                fr = px.line(df_m,x="date",y="rmse",
                    title="RMSE (MW) Over Days",
                    markers=True,
                    color_discrete_sequence=["#7c3aed"])
                fr.add_hline(y=df_m['rmse'].mean(),
                    line_dash="dash",line_color="red",
                    annotation_text=
                    f"Avg: {df_m['rmse'].mean():.0f} MW")
                fr.update_layout(height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fr,
                    use_container_width=True)

    # ══ TAB 3: 3-MONTH COMBINED FORECAST ═════════════════════
    with tab3:
        st.subheader(
            "📅 April · May · June 2026 — "
            "3-Month Combined Forecast")

        # Collect all 3 months from results
        all_month_data = {}
        for yr,mo in FORECAST_MONTHS:
            mn   = MONTH_NAMES[mo]
            df_mo = load_monthly(mn, yr)
            if df_mo is not None and len(df_mo)>0:
                all_month_data[(yr,mo)] = df_mo

        if not all_month_data:
            st.info(
                "3-month forecast data not found.\n\n"
                "Run the Colab notebook "
                "TN_3MONTH_FORECAST.py "
                "and push to GitHub.")
        else:
            # ── Combined daily avg chart ──────────────────────
            fig_comb = go.Figure()
            x_offset = 0

            for (yr,mo), df_mo in all_month_data.items():
                mn       = MONTH_NAMES[mo]
                color    = MONTH_COLORS[mo]
                df_mo    = df_mo.sort_values('day')
                days_x   = [x_offset+d
                            for d in df_mo['day'].tolist()]
                avgs     = df_mo['predicted_avg'].tolist()

                fig_comb.add_trace(go.Scatter(
                    x=days_x, y=avgs,
                    name=f"{mn} {yr}",
                    line=dict(color=color,width=2.5),
                    mode="lines+markers",
                    marker=dict(size=5),
                    fill="tozeroy",
                    fillcolor=color.replace(
                        '#','rgba(').replace(
                        ')',',0.07)') if '#' in color
                    else "rgba(0,0,0,0.05)"))

                if x_offset>0:
                    fig_comb.add_vline(
                        x=x_offset+0.5,
                        line_dash="dash",
                        line_color="gray",
                        opacity=0.5)

                x_offset += calendar.monthrange(yr,mo)[1]

            fig_comb.update_layout(
                title="April + May + June 2026 — "
                      "Daily Average Load (MW)",
                xaxis_title="Day (Apr 1 → Jun 30)",
                yaxis_title="Avg Load (MW)",
                hovermode="x unified",height=420,
                legend=dict(orientation="h",
                            yanchor="bottom",y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_comb,
                use_container_width=True)

            # ── Monthly comparison bar chart ──────────────────
            months_done = list(all_month_data.keys())
            month_labels= [f"{MONTH_NAMES[mo]} {yr}"
                           for yr,mo in months_done]
            month_avgs  = [
                all_month_data[k]['predicted_avg'].mean()
                for k in months_done]
            month_peaks = [
                all_month_data[k]['predicted_peak'].max()
                for k in months_done]
            month_colors= [MONTH_COLORS[mo]
                           for _,mo in months_done]

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=month_labels,y=month_avgs,
                name="Avg Load",
                marker_color=month_colors,
                opacity=0.85,
                text=[f"{v:,.0f}" for v in month_avgs],
                textposition='outside'))
            fig_bar.add_trace(go.Scatter(
                x=month_labels,y=month_peaks,
                name="Peak Load",
                mode="markers+lines",
                marker=dict(size=12,symbol="diamond"),
                line=dict(color="red",width=2,
                          dash="dot")))
            fig_bar.update_layout(
                title="Monthly Comparison — "
                      "Avg and Peak Load",
                yaxis_title="Load (MW)",height=350,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar,
                use_container_width=True)

            # ── Summary metrics ───────────────────────────────
            st.subheader("3-Month Summary")
            cols = st.columns(len(months_done))
            for i,((yr,mo),col) in enumerate(
                    zip(months_done,cols)):
                mn   = MONTH_NAMES[mo]
                df_mo = all_month_data[(yr,mo)]
                col.metric(
                    f"📅 {mn} {yr}",
                    f"{df_mo['predicted_avg'].mean():,.0f} MW avg",
                    f"Peak: {df_mo['predicted_peak'].max():,.0f} MW",
                    delta_color="off")

    # ══ TAB 4: MONTHLY DETAIL ════════════════════════════════
    with tab4:
        st.subheader("📆 Monthly Detail — "
                     "Forecast vs Previous Year")

        sel_month = st.selectbox(
            "Select Month",
            [f"{MONTH_NAMES[mo]} {yr}"
             for yr,mo in FORECAST_MONTHS])

        sel_yr = int(sel_month.split()[-1])
        sel_mo = next(mo for mo in MONTH_NAMES
                      if MONTH_NAMES[mo]==sel_month.split()[0])
        mn     = MONTH_NAMES[sel_mo]
        prev_yr= sel_yr - 1
        color  = MONTH_COLORS[sel_mo]

        df_mo = load_monthly(mn, sel_yr)

        if df_mo is None or len(df_mo)==0:
            st.info(f"No data for {mn} {sel_yr} yet")
        else:
            df_mo = df_mo.sort_values('day')
            num_days = calendar.monthrange(
                sel_yr, sel_mo)[1]

            # Stat cards
            mc1,mc2,mc3,mc4 = st.columns(4)
            mc1.metric("Days", len(df_mo))
            mc2.metric("Avg Load",
                f"{df_mo['predicted_avg'].mean():,.0f} MW")
            mc3.metric("Peak Load",
                f"{df_mo['predicted_peak'].max():,.0f} MW")
            peak_day = df_mo.loc[
                df_mo['predicted_peak'].idxmax(),'day']
            mc4.metric("Peak Day",
                f"{mn} {int(peak_day)}, {sel_yr}")
            st.divider()

            # ── Daily avg: this year vs prev year ─────────────
            fig_yr = go.Figure()
            fig_yr.add_trace(go.Scatter(
                x=df_mo['day'].tolist(),
                y=df_mo['predicted_avg'].tolist(),
                name=f"{mn} {sel_yr} (Forecast)",
                line=dict(color=color,width=2.5),
                mode="lines+markers",
                marker=dict(size=6),
                fill="tozeroy",
                fillcolor="rgba(0,0,0,0.05)"))

            # Try to get previous year data from rolling results
            df_prev_mo = load_monthly(mn, prev_yr)
            if df_prev_mo is not None and len(df_prev_mo)>0:
                df_prev_mo = df_prev_mo.sort_values('day')
                fig_yr.add_trace(go.Scatter(
                    x=df_prev_mo['day'].tolist(),
                    y=df_prev_mo['actual_avg'].tolist()
                    if 'actual_avg' in df_prev_mo.columns
                    else df_prev_mo['predicted_avg'].tolist(),
                    name=f"{mn} {prev_yr} (Prev Year)",
                    line=dict(color="#94a3b8",width=2,
                              dash="dash"),
                    mode="lines+markers",
                    marker=dict(size=5)))

            fig_yr.update_layout(
                title=(f"{mn} {sel_yr} Forecast — "
                       f"Daily Average Load"),
                xaxis_title=f"Day of {mn}",
                yaxis_title="Avg Load (MW)",
                hovermode="x unified",height=360,
                xaxis=dict(tickmode='linear',
                           tick0=1,dtick=1),
                yaxis=dict(tickformat=","),
                legend=dict(orientation="h",
                            yanchor="bottom",y=1.02),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_yr,
                use_container_width=True)

            # ── Hourly average profile for the month ──────────
            hourly_avgs = []
            for h in range(24):
                vals = [safe_float(row.get(f'pred_h{h:02d}'))
                        for _,row in df_mo.iterrows()]
                vals = [v for v in vals if v is not None]
                hourly_avgs.append(
                    np.mean(vals) if vals else 0)

            fig_hr = go.Figure()
            fig_hr.add_trace(go.Scatter(
                x=list(range(24)),y=hourly_avgs,
                name=f"{mn} {sel_yr} Avg Profile",
                line=dict(color=color,width=2.5),
                mode="lines+markers",
                marker=dict(size=7),
                fill="tozeroy",
                fillcolor="rgba(0,0,0,0.06)"))
            fig_hr.update_layout(
                title=f"Average Hourly Load Profile — "
                      f"{mn} {sel_yr}",
                xaxis_title="Hour of Day",
                yaxis_title="Avg Load (MW)",
                xaxis=dict(
                    tickmode='array',
                    tickvals=list(range(24)),
                    ticktext=[f"{h:02d}:00"
                              for h in range(24)]),
                height=320,
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_hr,
                use_container_width=True)

            # ── Day selector for individual day chart ─────────
            st.subheader(f"View Any Day in {mn} {sel_yr}")
            sel_day = st.slider(
                "Select Day", 1, num_days, 1)
            day_row = df_mo[df_mo['day']==sel_day]

            if len(day_row)>0:
                r     = day_row.iloc[0]
                dpred = get_24hrs(r,'pred')
                hdates= [f"{h:02d}:00" for h in range(24)]

                fig_d = go.Figure()
                fig_d.add_trace(go.Scatter(
                    x=hdates,y=dpred,
                    name=f"{mn} {sel_day} Forecast",
                    line=dict(color=color,width=2.5),
                    mode="lines+markers",
                    marker=dict(size=7,
                                symbol="diamond"),
                    fill="tozeroy",
                    fillcolor="rgba(0,0,0,0.07)"))
                vdp = [v for v in dpred if v]
                if vdp:
                    ph = dpred.index(max(vdp))
                    fig_d.add_annotation(
                        x=hdates[ph],y=max(vdp),
                        text=f"Peak: {max(vdp):,.0f} MW",
                        showarrow=True,arrowhead=2,
                        font=dict(color=color,size=11),
                        bgcolor="white",
                        bordercolor=color,
                        borderwidth=1.5,ay=-40)
                fig_d.update_layout(
                    title=(f"{mn} {sel_day}, {sel_yr} — "
                           f"Hourly Forecast  |  "
                           f"Avg: {r['predicted_avg']:,.0f} MW  "
                           f"|  Peak: {r['predicted_peak']:,.0f} MW"),
                    xaxis_title="Hour",
                    yaxis_title="Load (MW)",
                    hovermode="x unified",height=350,
                    yaxis=dict(tickformat=","),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_d,
                    use_container_width=True)

            # Full month table
            st.subheader(f"Full {mn} {sel_yr} Table")
            show_cols = ['day','date',
                         'predicted_avg','predicted_peak']
            avail = [c for c in show_cols
                     if c in df_mo.columns]
            ds = df_mo[avail].copy()
            for col in ['predicted_avg','predicted_peak']:
                if col in ds.columns:
                    ds[col] = pd.to_numeric(
                        ds[col],errors='coerce').round(1)
            ds.columns = [c.replace('_',' ').title()
                          for c in ds.columns]
            st.dataframe(ds,use_container_width=True,
                         hide_index=True,height=350)
            st.download_button(
                f"⬇ Download {mn} {sel_yr} CSV",
                df_mo.to_csv(index=False).encode(),
                f"{mn.lower()}_{sel_yr}_results.csv",
                "text/csv",
                use_container_width=True)

    # ══ TAB 5: ALL RESULTS ═══════════════════════════════════
    with tab5:
        st.subheader(f"All Results — {len(df)} rows")
        show_cols = ['date','mape','rmse',
                     'actual_avg','predicted_avg',
                     'actual_peak','predicted_peak']
        avail = [c for c in show_cols if c in df.columns]
        ds    = df[avail].copy()
        for c in ['mape','rmse','actual_avg',
                  'predicted_avg','predicted_peak']:
            if c in ds.columns:
                ds[c] = pd.to_numeric(
                    ds[c],errors='coerce').round(1)
        ds.columns = [c.replace('_',' ').title()
                      for c in ds.columns]
        st.dataframe(ds,use_container_width=True,
                     hide_index=True,height=440)
        st.download_button(
            "⬇ Download All Results",
            df.to_csv(index=False).encode(),
            "TN_all_results.csv","text/csv",
            use_container_width=True)

    # ══ TAB 6: ABOUT ═════════════════════════════════════════
    with tab6:
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("""
### System Overview
**Data** — 2020-01-01 to 2026-03-31
6+ years Tamil Nadu hourly load + weather

**Model** — Stacked LSTM
- 2 layers: 128 + 64 units
- 168-hour lookback (7 days)
- 22 features including wind100
- Trained on full history

**Forecast**
- April 2026: 30 days
- May 2026: 31 days
- June 2026: 30 days
- Total: 91 days predicted
- Model retrains after each month
            """)
        with c2:
            st.markdown("""
### Charts Available
| Chart | Description |
|-------|-------------|
| Daily Forecast | Today vs Tomorrow |
| 3-Month Combined | Apr+May+Jun together |
| Monthly Detail | Each month with prev year |
| Day Selector | Any specific day chart |
| Accuracy | MAPE and RMSE trends |

### Features (22 total)
temperature · humidity · rain
wind10 · **wind100** (real data)
radiation · cloud_cover · hour
month · day_of_week · is_summer
is_holiday · load_lag_24/48/168
rolling_mean · rolling_std
            """)

# ================================================================
#  MAIN
# ================================================================
def main():
    for k in ['logged_in','username','role']:
        if k not in st.session_state:
            st.session_state[k] = (
                False if k=='logged_in' else None)
    if not st.session_state['logged_in']:
        show_login_page()
        return
    show_sidebar(st.session_state['username'],
                 st.session_state['role'])
    show_dashboard(st.session_state['username'],
                   st.session_state['role'])

if __name__ == "__main__":
    main()
