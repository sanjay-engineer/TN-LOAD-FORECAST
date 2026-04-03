# ================================================================
#  TN LOAD FORECASTING — VERSION 3
#  3 NEW CHANGES:
#  1. Next day prediction chart shown separately
#  2. Admin uploads, viewers only see results
#  3. wind100 real data supported
# ================================================================
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, zipfile
from datetime import datetime

st.set_page_config(page_title="TN Load Forecasting",
                   page_icon="⚡", layout="wide")

USERS_FILE   = "users.json"
SHARED_DIR   = "shared_results"
USER_RESULTS = os.path.join(SHARED_DIR, "rolling_results.csv")
USER_HISTORY = os.path.join(SHARED_DIR, "history_updated.csv")
os.makedirs(SHARED_DIR, exist_ok=True)

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()
def load_users():
    return json.load(open(USERS_FILE)) if os.path.exists(USERS_FILE) else {}
def save_users(u):
    json.dump(u, open(USERS_FILE,"w"), indent=2)

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
    return True,"Account created — you can now login"

def login_user(username, password):
    users = load_users()
    match = next((u for u in users if u.lower()==username.lower()),None)
    if not match: return False,"Username not found",None
    if users[match]["password"]!=hash_pw(password):
        return False,"Wrong password",None
    users[match]["last_login"] = str(datetime.now())
    save_users(users)
    return True, match, users[match].get("role","viewer")

def load_results():
    return pd.read_csv(USER_RESULTS) if os.path.exists(USER_RESULTS) else None

# ── LOGIN PAGE ────────────────────────────────────────────────
def show_login_page():
    st.markdown("<div style='text-align:center;padding:30px 0'>"
                "<h1>⚡</h1><h2 style='color:#2563eb'>"
                "TN Intelligent Load Forecasting</h2>"
                "<p style='color:#64748b'>Tamil Nadu Power Grid "
                "— LSTM Day-Ahead Prediction</p></div>",
                unsafe_allow_html=True)
    st.divider()
    t1, t2 = st.tabs(["🔑 Login","📝 Register"])
    with t1:
        st.subheader("Login to your account")
        with st.form("lf"):
            u = st.text_input("Username", placeholder="Enter username")
            p = st.text_input("Password", type="password",
                              placeholder="Enter password")
            s = st.form_submit_button("Login",
                use_container_width=True, type="primary")
        if s:
            if not u or not p:
                st.error("Enter both username and password")
            else:
                ok,res,role = login_user(u,p)
                if ok:
                    st.session_state.update(
                        logged_in=True, username=res, role=role)
                    st.success(f"Welcome {res}!")
                    st.rerun()
                else: st.error(f"Login failed: {res}")
    with t2:
        st.subheader("Create new account")
        with st.form("rf"):
            nu = st.text_input("Username", placeholder="3-20 chars")
            np_ = st.text_input("Password", type="password",
                                placeholder="Min 6 chars")
            cp = st.text_input("Confirm Password", type="password",
                               placeholder="Repeat password")
            rb = st.form_submit_button("Create Account",
                use_container_width=True, type="primary")
        if rb:
            if not nu or not np_ or not cp:
                st.error("Fill all fields")
            elif np_!=cp: st.error("Passwords do not match")
            else:
                ok,msg = register_user(nu,np_)
                (st.success if ok else st.error)(msg)
    st.divider()
    st.info("New user? Click Register.\n\n"
            "All users view results after login.\n"
            "Upload is for admin accounts only.")

# ── SIDEBAR ───────────────────────────────────────────────────
def show_sidebar(username, role):
    with st.sidebar:
        color = "#7c3aed" if role=="admin" else "#2563eb"
        st.markdown(f"<div style='background:{color};color:white;"
                    f"padding:10px 14px;border-radius:8px;"
                    f"margin-bottom:8px'><b>👤 {username}</b><br>"
                    f"<span style='font-size:12px;opacity:.85'>"
                    f"Role: {'Admin' if role=='admin' else 'Viewer'}"
                    f"</span></div>", unsafe_allow_html=True)
        st.divider()

        # CHANGE 2: Only admin can upload
        if role=="admin":
            st.subheader("📂 Upload Results")
            st.caption("Uploads are shared with all viewers")
            rf = st.file_uploader("1. rolling_results.csv",
                                  type=["csv"], key="ru")
            if rf:
                pd.read_csv(rf).to_csv(USER_RESULTS, index=False)
                st.success("✓ Results saved")
            hf = st.file_uploader("2. history_updated.csv",
                                  type=["csv"], key="hu")
            if hf:
                pd.read_csv(hf).to_csv(USER_HISTORY, index=False)
                st.success("✓ History saved")
            cf = st.file_uploader("3. charts.zip",
                                  type=["zip"], key="cu")
            if cf:
                with zipfile.ZipFile(cf,'r') as z:
                    z.extractall(SHARED_DIR)
                st.success("✓ Charts extracted")
        else:
            st.subheader("📊 Data Status")
            if os.path.exists(USER_RESULTS):
                df_c = pd.read_csv(USER_RESULTS)
                st.success(f"✓ {len(df_c)} days available")
                if 'date' in df_c.columns:
                    st.caption(f"Latest: {df_c['date'].iloc[-1]}")
            else:
                st.warning("No results yet. Ask admin to upload.")
            st.info("You are a **Viewer**.\n\nYou can see all results.\n"
                    "Uploads are handled by admin.")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.update(
                logged_in=False, username=None, role=None)
            st.rerun()

# ── DASHBOARD ─────────────────────────────────────────────────
def show_dashboard(username, role):
    st.markdown(f"<h2 style='color:#2563eb'>"
                f"⚡ TN Load Forecasting Dashboard</h2>"
                f"<p style='color:#64748b'>Welcome <b>{username}</b> "
                f"({'Admin' if role=='admin' else 'Viewer'})</p>",
                unsafe_allow_html=True)
    st.divider()

    df = load_results()
    if df is None or len(df)==0:
        msg = ("Upload `rolling_results.csv` in the sidebar."
               if role=="admin"
               else "Admin has not uploaded results yet.")
        st.info(f"### No results yet\n\n{msg}")
        return

    df_m = df[df['mape'].notna()].copy()
    hours   = list(range(24))
    hlabels = [f"{h:02d}:00" for h in hours]

    # Stat cards
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📅 Days", len(df))
    if len(df_m)>0:
        c2.metric("🎯 Avg MAPE",f"{df_m['mape'].mean():.2f}%")
        idx=df_m['mape'].idxmin()
        c3.metric("🏆 Best MAPE",f"{df_m.loc[idx,'mape']:.2f}%",
                  str(df_m.loc[idx,'date']),delta_color="off")
        c4.metric("📊 Avg RMSE",f"{df_m['rmse'].mean():.0f} MW")
    c5.metric("📆 Latest",str(df['date'].iloc[-1]))
    st.divider()

    tab1,tab2,tab3,tab4 = st.tabs([
        "📈 Forecast","🎯 Accuracy","📋 All Results","📖 How It Works"])

    # ══ TAB 1 — FORECAST ══════════════════════════════════════
    with tab1:

        # Rows with actual data = past days
        df_actual = df[df['actual_h00'].notna()].copy()
        # Rows without actual = future predictions (CHANGE 1)
        df_future = df[df['actual_h00'].isna()].copy()

        def get_series(row, prefix):
            vals = [row.get(f'{prefix}_h{h:02d}') for h in hours]
            return [float(v) if v is not None and pd.notna(v)
                    else None for v in vals]

        # ── PART A: Today predicted vs actual ─────────────────
        st.subheader("📊 Today — Predicted vs Actual")
        if len(df_actual)==0:
            st.info("No actual data yet.")
        else:
            row = df_actual.iloc[-1]
            pred   = get_series(row, 'pred')
            actual = get_series(row, 'actual')

            m1,m2,m3,m4 = st.columns(4)
            mv = row.get('mape')
            rv = row.get('rmse')
            vp = [v for v in pred if v]
            if pd.notna(mv):
                col="green" if float(mv)<5 else "orange"
                m1.markdown(f"<h3 style='color:{col}'>{float(mv):.2f}%</h3>"
                            f"<p style='color:#64748b;font-size:12px'>MAPE</p>",
                            unsafe_allow_html=True)
            if pd.notna(rv):
                m2.markdown(f"<h3>{float(rv):.0f} MW</h3>"
                            f"<p style='color:#64748b;font-size:12px'>RMSE</p>",
                            unsafe_allow_html=True)
            if vp:
                m3.markdown(f"<h3 style='color:#2563eb'>{max(vp):,.0f} MW</h3>"
                            f"<p style='color:#64748b;font-size:12px'>Peak Predicted</p>",
                            unsafe_allow_html=True)
            m4.markdown(f"<h3>{row['date']}</h3>"
                        f"<p style='color:#64748b;font-size:12px'>Date</p>",
                        unsafe_allow_html=True)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hlabels, y=actual,
                name="Actual Load",
                line=dict(color="#16a34a",width=3),
                mode="lines+markers",marker=dict(size=7),
                fill="tozeroy",fillcolor="rgba(22,163,74,0.07)"))
            fig.add_trace(go.Scatter(x=hlabels, y=pred,
                name="Predicted Load",
                line=dict(color="#2563eb",width=2.5,dash="dash"),
                mode="lines+markers",marker=dict(size=6)))
            fig.update_layout(
                title=f"Predicted vs Actual — {row['date']}",
                xaxis_title="Hour",yaxis_title="Load (MW)",
                hovermode="x unified",height=380,
                legend=dict(orientation="h",yanchor="bottom",y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ── CHANGE 1: PART B — Next day prediction ────────────
        st.subheader("🔮 Tomorrow — Next Day Forecast")
        st.caption("Model's prediction for the next day — "
                   "actual will appear after that day's data is added")

        if len(df_future)>0:
            nrow  = df_future.iloc[-1]
            npred = get_series(nrow, 'pred')
            vnp   = [v for v in npred if v is not None]

            n1,n2,n3,n4 = st.columns(4)
            if vnp:
                n1.markdown(f"<h3 style='color:#ea580c'>{max(vnp):,.0f} MW</h3>"
                            f"<p style='color:#64748b;font-size:12px'>Peak Forecast</p>",
                            unsafe_allow_html=True)
                n2.markdown(f"<h3>{min(vnp):,.0f} MW</h3>"
                            f"<p style='color:#64748b;font-size:12px'>Min Forecast</p>",
                            unsafe_allow_html=True)
                n3.markdown(f"<h3>{np.mean(vnp):,.0f} MW</h3>"
                            f"<p style='color:#64748b;font-size:12px'>Avg Forecast</p>",
                            unsafe_allow_html=True)
            n4.markdown(f"<h3 style='color:#7c3aed'>{nrow['date']}</h3>"
                        f"<p style='color:#64748b;font-size:12px'>Forecast For</p>",
                        unsafe_allow_html=True)

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=hlabels,y=npred,
                name="Next Day Prediction",
                line=dict(color="#ea580c",width=3),
                mode="lines+markers",
                marker=dict(size=7,symbol="diamond"),
                fill="tozeroy",fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph = npred.index(max(vnp))
                fig2.add_annotation(
                    x=hlabels[ph],y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True,arrowhead=2,
                    arrowcolor="#ea580c",
                    font=dict(color="#ea580c",size=11),
                    bgcolor="white",bordercolor="#ea580c",
                    borderwidth=1)
            fig2.update_layout(
                title=f"Next Day Forecast — {nrow['date']}",
                xaxis_title="Hour",yaxis_title="Load (MW)",
                hovermode="x unified",height=380,
                legend=dict(orientation="h",yanchor="bottom",y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

            # Hourly next day table
            st.subheader("Next Day Hourly Table")
            rows=[]
            for h in hours:
                v = npred[h]
                rows.append({
                    "Hour":f"{h:02d}:00",
                    "Predicted (MW)":f"{v:,.0f}" if v else "—",
                    "Status":"🔴 Peak" if v and vnp and v==max(vnp)
                             else "🟢 Normal" if v else "—"})
            st.dataframe(pd.DataFrame(rows),
                         use_container_width=True,
                         hide_index=True,height=300)
        else:
            st.info("Next day prediction will appear here after "
                    "you run Colab and upload results.")

    # ══ TAB 2 — ACCURACY ══════════════════════════════════════
    with tab2:
        if len(df_m)==0:
            st.info("No accuracy data yet")
        else:
            c1,c2 = st.columns(2)
            with c1:
                fm = px.line(df_m,x="date",y="mape",
                    title="MAPE % Over Days",markers=True,
                    color_discrete_sequence=["#ea580c"])
                fm.add_hline(y=df_m['mape'].mean(),line_dash="dash",
                    line_color="red",
                    annotation_text=f"Avg: {df_m['mape'].mean():.2f}%")
                fm.update_layout(height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fm,use_container_width=True)
            with c2:
                fr = px.line(df_m,x="date",y="rmse",
                    title="RMSE (MW) Over Days",markers=True,
                    color_discrete_sequence=["#7c3aed"])
                fr.add_hline(y=df_m['rmse'].mean(),line_dash="dash",
                    line_color="red",
                    annotation_text=f"Avg: {df_m['rmse'].mean():.0f} MW")
                fr.update_layout(height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fr,use_container_width=True)

            if 'actual_avg' in df_m.columns:
                fa = go.Figure()
                fa.add_trace(go.Scatter(x=df_m['date'],
                    y=df_m['actual_avg'],name="Actual Avg",
                    line=dict(color="#16a34a",width=2),
                    mode="lines+markers"))
                fa.add_trace(go.Scatter(x=df_m['date'],
                    y=df_m['predicted_avg'],name="Predicted Avg",
                    line=dict(color="#2563eb",width=2,dash="dash"),
                    mode="lines+markers"))
                fa.update_layout(title="Actual vs Predicted Daily Avg",
                    height=300,hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fa,use_container_width=True)

            st.subheader("View Any Past Day")
            sel = st.selectbox("Select date",
                               df_m['date'].tolist()[::-1])
            if sel:
                r   = df_m[df_m['date']==sel].iloc[0]
                p2  = [float(r.get(f'pred_h{h:02d}',0) or 0)
                       for h in range(24)]
                a2  = [float(r.get(f'actual_h{h:02d}',0) or 0)
                       for h in range(24)]
                hl2 = [f"{h:02d}:00" for h in range(24)]
                fd  = go.Figure()
                fd.add_trace(go.Scatter(x=hl2,y=a2,name="Actual",
                    line=dict(color="#16a34a",width=2),
                    mode="lines+markers"))
                fd.add_trace(go.Scatter(x=hl2,y=p2,name="Predicted",
                    line=dict(color="#2563eb",width=2,dash="dash"),
                    mode="lines+markers"))
                m=r.get('mape'); rv=r.get('rmse')
                fd.update_layout(
                    title=(f"{sel} — MAPE: {float(m):.2f}% | "
                           f"RMSE: {float(rv):.0f} MW"
                           if pd.notna(m) else sel),
                    height=320,hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fd,use_container_width=True)

    # ══ TAB 3 — ALL RESULTS ═══════════════════════════════════
    with tab3:
        st.subheader(f"All Results — {len(df)} days")
        cols=['day_number','date','trained_upto','mape','rmse',
              'actual_avg','predicted_avg','actual_peak']
        av=[c for c in cols if c in df.columns]
        ds=df[av].copy()
        for c in ['mape','rmse','actual_avg','predicted_avg',
                  'actual_peak']:
            if c in ds.columns:
                ds[c]=pd.to_numeric(ds[c],errors='coerce').round(2)
        ds.columns=[c.replace('_',' ').title() for c in ds.columns]
        st.dataframe(ds,use_container_width=True,
                     hide_index=True,height=420)
        st.download_button("⬇ Download CSV",
            df.to_csv(index=False).encode(),
            "TN_results.csv","text/csv",
            use_container_width=True)

    # ══ TAB 4 — HOW IT WORKS ══════════════════════════════════
    with tab4:
        c1,c2=st.columns(2)
        with c1:
            st.markdown("""
### How This Works
**Data** — 5 years TN load · 22 features
**Training** — LSTM in Google Colab (free)
**Forecast** — Predicts next 24 hours
**Rolling** — Retrains every day · gets smarter

### User Roles
| Role | Can do |
|------|--------|
| Admin | Upload + View |
| Viewer | View only |

**To make someone admin:**
Open `users.json` → find their username
Change `"role": "viewer"` to `"role": "admin"`
Save the file
            """)
        with c2:
            st.markdown("""
### Features Used (22 total)
**Weather:** temperature, humidity, rain,
wind10, **wind100** (real data), radiation,
cloud_cover

**Time:** hour, day_of_week, month,
day_of_year, is_summer, is_monsoon

**Calendar:** Week_day, is_holiday

**Lag:** load_lag_24, load_lag_48,
load_lag_168, rolling_mean_24,
rolling_mean_168, rolling_std_24

### wind100 Note
Real wind100 data is now used directly.
No estimation from wind10 anymore.
More accurate for TN wind farm modelling.
            """)

# ── MAIN ──────────────────────────────────────────────────────
def main():
    for k in ['logged_in','username','role']:
        if k not in st.session_state:
            st.session_state[k] = (False if k=='logged_in' else None)
    if not st.session_state['logged_in']:
        show_login_page()
        return
    show_sidebar(st.session_state['username'],
                 st.session_state['role'])
    show_dashboard(st.session_state['username'],
                   st.session_state['role'])

if __name__=="__main__":
    main()
