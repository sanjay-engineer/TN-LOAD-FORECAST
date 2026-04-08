# ================================================================
#  TN LOAD FORECASTING — STREAMLIT APP
#  AUTO VERSION — reads results from GitHub automatically
#
#  HOW IT WORKS:
#  When Colab runs and pushes files to GitHub,
#  this app reads them from GitHub directly.
#  No manual upload needed.
#  Just open the app — results are already there.
#
#  Users can still manually upload if they want.
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, zipfile, requests
from datetime import datetime
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide"
)

# ================================================================
#  SETTINGS — Fill your GitHub details here
# ================================================================
GITHUB_USER   = "sanjay-engineer"       # your GitHub username
GITHUB_REPO   = "TN-LOAD-FORECAST"   # your repository name
GITHUB_BRANCH = "main"

# GitHub raw file URL base
GITHUB_RAW = (f"https://raw.githubusercontent.com/"
              f"{GITHUB_USER}/{GITHUB_REPO}/"
              f"{GITHUB_BRANCH}/results")

# ================================================================
#  USER SYSTEM
# ================================================================
USERS_FILE  = "users.json"
SHARED_DIR  = "shared_results"
os.makedirs(SHARED_DIR, exist_ok=True)

LOCAL_RESULTS = os.path.join(SHARED_DIR, "rolling_results.csv")
LOCAL_HISTORY = os.path.join(SHARED_DIR, "history_updated.csv")

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
        return False, "Username too short (min 3)"
    if len(username) > 20:
        return False, "Username too long (max 20)"
    if not username.replace("_","").isalnum():
        return False, "Letters, numbers, underscore only"
    if len(password) < 6:
        return False, "Password min 6 characters"
    users = load_users()
    if username.lower() in [u.lower() for u in users]:
        return False, "Username already taken"
    users[username] = {
        "password"  : hash_pw(password),
        "role"      : "viewer",
        "created"   : str(datetime.now().date()),
        "last_login": None
    }
    save_users(users)
    return True, "Account created — login now"

def login_user(username, password):
    users = load_users()
    match = next(
        (u for u in users
         if u.lower() == username.lower()), None)
    if not match:
        return False, "Username not found", None
    if users[match]["password"] != hash_pw(password):
        return False, "Wrong password", None
    users[match]["last_login"] = str(datetime.now())
    save_users(users)
    return True, match, users[match].get("role","viewer")

def make_admin(username, secret):
    if secret != "TN2025Admin":
        return False, "Wrong admin secret key"
    users = load_users()
    match = next(
        (u for u in users
         if u.lower() == username.lower()), None)
    if not match:
        return False, f"User '{username}' not found"
    users[match]["role"] = "admin"
    save_users(users)
    return True, f"'{match}' is now Admin"

def change_role(username, new_role):
    users = load_users()
    match = next(
        (u for u in users
         if u.lower() == username.lower()), None)
    if not match:
        return False, "User not found"
    users[match]["role"] = new_role
    save_users(users)
    return True, f"Role changed to {new_role}"

# ================================================================
#  GITHUB AUTO-FETCH FUNCTIONS
#  Reads result files directly from GitHub
# ================================================================

@st.cache_data(ttl=60)
def fetch_from_github(filename):
    """
    Downloads a file from GitHub repository.
    Returns the content as text.
    ttl=60 means: cache for 60 seconds.
    After 60 seconds, fetches fresh data automatically.
    """
    url = f"{GITHUB_RAW}/{filename}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            return None
    except Exception:
        return None

def load_results_auto():
    """
    Tries to load results in this order:
    1. From GitHub (automatic — newest data)
    2. From local file (manually uploaded)
    3. Returns None if neither exists
    """

    # Try GitHub first
    github_data = fetch_from_github("rolling_results.csv")
    if github_data:
        try:
            df = pd.read_csv(StringIO(github_data))
            return df, "github"
        except Exception:
            pass

    # Try local file (manually uploaded)
    if os.path.exists(LOCAL_RESULTS):
        return pd.read_csv(LOCAL_RESULTS), "local"

    return None, None

def check_github_connection():
    """Check if GitHub has results files."""
    url = f"{GITHUB_RAW}/rolling_results.csv"
    try:
        r = requests.head(url, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

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
            TN Intelligent Load Forecasting
        </h2>
        <p style='color:#64748b;font-size:14px'>
            Tamil Nadu Power Grid —
            LSTM Day-Ahead Prediction
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "🔑 Login",
        "📝 Register",
        "🔧 Admin Setup"
    ])

    with tab1:
        st.subheader("Login")
        with st.form("lf"):
            u = st.text_input("Username",
                placeholder="Your username")
            p = st.text_input("Password",
                type="password",
                placeholder="Your password")
            s = st.form_submit_button(
                "Login",
                use_container_width=True,
                type="primary")
        if s:
            if not u or not p:
                st.error("Enter username and password")
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

    with tab2:
        st.subheader("Create Account")
        with st.form("rf"):
            nu = st.text_input("Username",
                placeholder="3-20 characters")
            np_= st.text_input("Password",
                type="password",
                placeholder="Min 6 characters")
            cp = st.text_input("Confirm Password",
                type="password",
                placeholder="Repeat password")
            rb = st.form_submit_button(
                "Create Account",
                use_container_width=True,
                type="primary")
        if rb:
            if not nu or not np_ or not cp:
                st.error("Fill all fields")
            elif np_ != cp:
                st.error("Passwords do not match")
            else:
                ok, msg = register_user(nu, np_)
                (st.success if ok else st.error)(msg)

    with tab3:
        st.subheader("Make Yourself Admin")
        st.info(
            "**Steps:**\n\n"
            "1. Register your account first\n"
            "2. Enter your username below\n"
            "3. Enter the secret key: **TN2025Admin**\n"
            "4. Click Make Admin\n"
            "5. Login — upload buttons appear")
        with st.form("af"):
            au = st.text_input("Your Username")
            ak = st.text_input("Admin Secret Key",
                               type="password")
            ab = st.form_submit_button(
                "Make Admin",
                use_container_width=True)
        if ab:
            ok, msg = make_admin(au, ak)
            (st.success if ok else st.error)(msg)

    st.divider()
    # Show GitHub connection status
    github_ok = check_github_connection()
    if github_ok:
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

        bg = "#7c3aed" if role=="admin" else "#2563eb"
        label = "Admin ✓" if role=="admin" else "Viewer"
        st.markdown(
            f"<div style='background:{bg};color:white;"
            f"padding:12px 16px;border-radius:10px;"
            f"margin-bottom:10px'>"
            f"<b>👤 {username}</b><br>"
            f"<span style='font-size:12px;opacity:.85'>"
            f"{label}</span></div>",
            unsafe_allow_html=True)

        st.divider()

        # GitHub status
        st.subheader("🔗 Data Source")
        github_ok = check_github_connection()
        if github_ok:
            st.success("✅ GitHub — Auto sync")
            st.caption(
                "Results update automatically when "
                "Colab pushes new data")
            if st.button("🔄 Refresh Now",
                         use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("⚠ GitHub not connected")
            st.caption(
                "Check GITHUB_USER and GITHUB_REPO "
                "in the app settings")

        st.divider()

        # Manual upload (admin only — backup option)
        if role == "admin":
            with st.expander("📂 Manual Upload (backup)"):
                st.caption(
                    "Only needed if GitHub is not connected")

                rf = st.file_uploader(
                    "rolling_results.csv",
                    type=["csv"], key="ru")
                if rf:
                    pd.read_csv(rf).to_csv(
                        LOCAL_RESULTS, index=False)
                    st.success("✓ Uploaded")

                hf = st.file_uploader(
                    "history_updated.csv",
                    type=["csv"], key="hu")
                if hf:
                    pd.read_csv(hf).to_csv(
                        LOCAL_HISTORY, index=False)
                    st.success("✓ Uploaded")

            st.divider()

            # Manage user roles
            with st.expander("👥 Manage Users"):
                users = load_users()
                for uname, udata in users.items():
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(
                            f"**{uname}** — "
                            f"{udata.get('role','viewer')}")
                    with c2:
                        nr = st.selectbox(
                            "Role",
                            ["viewer","admin"],
                            index=0 if udata.get(
                                'role','viewer')=='viewer'
                            else 1,
                            key=f"r_{uname}")
                        if st.button("Set",
                                     key=f"s_{uname}"):
                            change_role(uname, nr)
                            st.rerun()

        st.divider()
        if st.button("🚪 Logout",
                     use_container_width=True):
            st.session_state.update(
                logged_in=False,
                username=None,
                role=None)
            st.rerun()

# ================================================================
#  MAIN DASHBOARD
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

    # Load results (auto from GitHub or manual)
    df, source = load_results_auto()

    # Show data source
    if source == "github":
        st.success(
            "✅ Showing latest results from GitHub — "
            "updated automatically when Colab runs")
    elif source == "local":
        st.info("📁 Showing manually uploaded results")
    else:
        st.info(
            "### No results yet\n\n"
            "Run the Colab notebook first. "
            "Results will appear here automatically.")
        if role == "admin":
            st.markdown(
                "**Make sure:**\n"
                "- Cell 14 in Colab has your GitHub token\n"
                "- GITHUB_USER matches your username\n"
                "- GITHUB_REPO matches your repository name")
        return

    # Split past vs future rows
    df['has_actual'] = df['actual_h00'].apply(
        lambda x: pd.notna(x)
        and str(x) not in ['','nan','None'])
    df_past   = df[df['has_actual']].copy()
    df_future = df[~df['has_actual']].copy()
    df_m      = df_past[
        df_past['mape'].notna()].copy()

    hours   = list(range(24))
    hlabels = [f"{h:02d}:00" for h in hours]

    # ── Stat cards ────────────────────────────────────────
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📅 Days Predicted", len(df_past))
    if len(df_m) > 0:
        c2.metric("🎯 Avg MAPE",
                  f"{df_m['mape'].mean():.2f}%")
        idx = df_m['mape'].idxmin()
        c3.metric("🏆 Best MAPE",
                  f"{df_m.loc[idx,'mape']:.2f}%",
                  str(df_m.loc[idx,'date']),
                  delta_color="off")
        c4.metric("📊 Avg RMSE",
                  f"{df_m['rmse'].mean():.0f} MW")
    c5.metric("🔮 Next Forecast",
              str(df_future.iloc[-1]['date'])
              if len(df_future) > 0 else "—")
    st.divider()

    # ── Tabs ──────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Forecast",
        "🎯 Accuracy",
        "📋 All Results",
        "📖 About"
    ])

    # ══ TAB 1: FORECAST ═══════════════════════════════════
    with tab1:

        # Chart A — Today predicted vs actual
        st.subheader("📊 Today — Predicted vs Actual")

        if len(df_past) == 0:
            st.info("No actual data yet")
        else:
            row    = df_past.iloc[-1]
            pred   = get_24hrs(row, 'pred')
            actual = get_24hrs(row, 'actual')

            m1,m2,m3,m4 = st.columns(4)
            mv = safe_float(row.get('mape'))
            rv = safe_float(row.get('rmse'))
            vp = [v for v in pred if v]

            if mv is not None:
                col = ("green" if mv<5
                       else "orange" if mv<10
                       else "red")
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

            fig = go.Figure()
            if any(v is not None for v in actual):
                fig.add_trace(go.Scatter(
                    x=hlabels, y=actual,
                    name="Actual Load",
                    line=dict(color="#16a34a", width=3),
                    mode="lines+markers",
                    marker=dict(size=7),
                    fill="tozeroy",
                    fillcolor="rgba(22,163,74,0.07)"))
            fig.add_trace(go.Scatter(
                x=hlabels, y=pred,
                name="Predicted Load",
                line=dict(color="#2563eb",
                          width=2.5, dash="dash"),
                mode="lines+markers",
                marker=dict(size=6)))
            fig.update_layout(
                title=f"Predicted vs Actual — "
                      f"{row['date']}",
                xaxis_title="Hour",
                yaxis_title="Load (MW)",
                hovermode="x unified",
                height=400,
                legend=dict(orientation="h",
                            yanchor="bottom",
                            y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig,
                            use_container_width=True)

        st.divider()

        # Chart B — Tomorrow prediction
        st.subheader("🔮 Tomorrow — Next Day Forecast")
        st.caption(
            "Prediction for the next day. "
            "Updates automatically after each Colab run.")

        if len(df_future) > 0:
            nrow  = df_future.iloc[-1]
            npred = get_24hrs(nrow, 'pred')
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
                x=hlabels, y=npred,
                name="Next Day Forecast",
                line=dict(color="#ea580c", width=3),
                mode="lines+markers",
                marker=dict(size=8,
                            symbol="diamond"),
                fill="tozeroy",
                fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph = npred.index(max(vnp))
                fig2.add_annotation(
                    x=hlabels[ph], y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True, arrowhead=2,
                    arrowcolor="#ea580c",
                    font=dict(color="#ea580c",
                              size=12),
                    bgcolor="white",
                    bordercolor="#ea580c",
                    borderwidth=1.5,
                    ay=-40)
            fig2.update_layout(
                title=f"Next Day Forecast — "
                      f"{nrow['date']}",
                xaxis_title="Hour",
                yaxis_title="Load (MW)",
                hovermode="x unified",
                height=400,
                legend=dict(orientation="h",
                            yanchor="bottom",
                            y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2,
                            use_container_width=True)
        else:
            st.info("Next day prediction not available yet")

    # ══ TAB 2: ACCURACY ═══════════════════════════════════
    with tab2:
        if len(df_m) == 0:
            st.info("No accuracy data yet")
        else:
            c1, c2 = st.columns(2)
            with c1:
                fm = px.line(df_m, x="date", y="mape",
                    title="MAPE % Over Days",
                    markers=True,
                    color_discrete_sequence=["#ea580c"])
                fm.add_hline(
                    y=df_m['mape'].mean(),
                    line_dash="dash",
                    line_color="red",
                    annotation_text=
                    f"Avg: {df_m['mape'].mean():.2f}%")
                fm.update_layout(height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fm,
                    use_container_width=True)
            with c2:
                fr = px.line(df_m, x="date", y="rmse",
                    title="RMSE (MW) Over Days",
                    markers=True,
                    color_discrete_sequence=["#7c3aed"])
                fr.add_hline(
                    y=df_m['rmse'].mean(),
                    line_dash="dash",
                    line_color="red",
                    annotation_text=
                    f"Avg: {df_m['rmse'].mean():.0f} MW")
                fr.update_layout(height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fr,
                    use_container_width=True)

            if ('actual_avg' in df_m.columns
                    and 'predicted_avg' in df_m.columns):
                fa = go.Figure()
                fa.add_trace(go.Scatter(
                    x=df_m['date'],
                    y=pd.to_numeric(
                        df_m['actual_avg'],
                        errors='coerce'),
                    name="Actual Avg",
                    line=dict(color="#16a34a",
                              width=2),
                    mode="lines+markers"))
                fa.add_trace(go.Scatter(
                    x=df_m['date'],
                    y=pd.to_numeric(
                        df_m['predicted_avg'],
                        errors='coerce'),
                    name="Predicted Avg",
                    line=dict(color="#2563eb",
                              width=2, dash="dash"),
                    mode="lines+markers"))
                fa.update_layout(
                    title="Actual vs Predicted "
                          "Daily Average",
                    height=300,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fa,
                    use_container_width=True)

            st.subheader("View Any Past Day")
            sel = st.selectbox(
                "Select a date",
                df_m['date'].tolist()[::-1])
            if sel:
                r  = df_m[df_m['date']==sel].iloc[0]
                p2 = get_24hrs(r, 'pred')
                a2 = get_24hrs(r, 'actual')
                fd = go.Figure()
                fd.add_trace(go.Scatter(
                    x=hlabels, y=a2, name="Actual",
                    line=dict(color="#16a34a",
                              width=2),
                    mode="lines+markers"))
                fd.add_trace(go.Scatter(
                    x=hlabels, y=p2,
                    name="Predicted",
                    line=dict(color="#2563eb",
                              width=2, dash="dash"),
                    mode="lines+markers"))
                mv = safe_float(r.get('mape'))
                rv = safe_float(r.get('rmse'))
                fd.update_layout(
                    title=(f"{sel} — MAPE: "
                           f"{mv:.2f}% | "
                           f"RMSE: {rv:.0f} MW"
                           if mv else sel),
                    height=320,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fd,
                    use_container_width=True)

    # ══ TAB 3: ALL RESULTS ════════════════════════════════
    with tab3:
        st.subheader(f"All Results — "
                     f"{len(df_past)} days")
        cols  = ['day_number','date','trained_upto',
                 'mape','rmse','actual_avg',
                 'predicted_avg','actual_peak']
        avail = [c for c in cols if c in df_past.columns]
        ds    = df_past[avail].copy()
        for col in ['mape','rmse','actual_avg',
                    'predicted_avg','actual_peak']:
            if col in ds.columns:
                ds[col] = pd.to_numeric(
                    ds[col], errors='coerce').round(2)
        ds.columns = [
            c.replace('_',' ').title()
            for c in ds.columns]
        st.dataframe(ds, use_container_width=True,
                     hide_index=True, height=420)
        st.download_button(
            "⬇ Download Results CSV",
            df_past.to_csv(index=False).encode(),
            "TN_results.csv", "text/csv",
            use_container_width=True)

    # ══ TAB 4: ABOUT ══════════════════════════════════════
    with tab4:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
### How Auto-Sync Works
1. You run the Colab notebook
2. Cell 14 pushes results to GitHub
3. This app reads from GitHub
4. Open app — results are already updated

**No manual upload needed**

### Data Source
- GitHub repository: your results folder
- Updates every 60 seconds automatically
- Click **Refresh Now** in sidebar for instant update

### Model
- LSTM Neural Network
- 22 features including real wind100
- 168-hour lookback (7 days)
- Retrains every day with new data
            """)
        with c2:
            st.markdown("""
### User Roles
| Role | Can do |
|------|--------|
| **Admin** | See all + manual upload backup |
| **Viewer** | See all results and charts |

### Features (22 total)
temperature · humidity · rain
wind10 · **wind100** (real data)
radiation · cloud_cover
hour · month · day_of_week
is_summer · is_monsoon · is_holiday
load_lag_24 · load_lag_168 · and more

### Accuracy
- MAPE below 5% = excellent
- Model improves every day
- Each new day makes it smarter
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
