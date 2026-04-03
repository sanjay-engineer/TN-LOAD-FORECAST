# ================================================================
#  TN LOAD FORECASTING — FINAL VERSION
#  ALL FIXES INCLUDED:
#  Fix 1: Next day chart works correctly
#  Fix 2: Admin setup done inside the app — no JSON editing
#  Fix 3: Simpler and cleaner for beginners
# ================================================================
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, zipfile
from datetime import datetime

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide"
)

# ── File paths ────────────────────────────────────────────────
USERS_FILE   = "users.json"
SHARED_DIR   = "shared_results"
RESULTS_FILE = os.path.join(SHARED_DIR, "rolling_results.csv")
HISTORY_FILE = os.path.join(SHARED_DIR, "history_updated.csv")
os.makedirs(SHARED_DIR, exist_ok=True)

# ── Password hashing ──────────────────────────────────────────
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ── User file functions ───────────────────────────────────────
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ── Register ──────────────────────────────────────────────────
def register_user(username, password, role="viewer"):
    if len(username) < 3:
        return False, "Username too short — need at least 3 characters"
    if len(username) > 20:
        return False, "Username too long — max 20 characters"
    if not username.replace("_","").isalnum():
        return False, "Use letters, numbers and underscore only"
    if len(password) < 6:
        return False, "Password too short — need at least 6 characters"
    users = load_users()
    if username.lower() in [u.lower() for u in users]:
        return False, "Username already taken — choose another"
    users[username] = {
        "password"  : hash_pw(password),
        "role"      : role,
        "created"   : str(datetime.now().date()),
        "last_login": None
    }
    save_users(users)
    return True, "Account created successfully"

# ── Login ─────────────────────────────────────────────────────
def login_user(username, password):
    users = load_users()
    match = next(
        (u for u in users if u.lower() == username.lower()), None)
    if not match:
        return False, "Username not found", None
    if users[match]["password"] != hash_pw(password):
        return False, "Wrong password — try again", None
    users[match]["last_login"] = str(datetime.now())
    save_users(users)
    return True, match, users[match].get("role", "viewer")

# ── Make admin ────────────────────────────────────────────────
def make_admin(username, admin_password, target_user):
    """
    FIX 2: Admin setup done inside the app.
    No JSON file editing needed.
    The first admin is created using a secret admin password.
    """
    ADMIN_SECRET = "TN2025Admin"   # Change this to your own secret
    if admin_password != ADMIN_SECRET:
        return False, "Wrong admin secret key"
    users = load_users()
    match = next(
        (u for u in users if u.lower() == target_user.lower()), None)
    if not match:
        return False, f"User '{target_user}' not found"
    users[match]["role"] = "admin"
    save_users(users)
    return True, f"'{match}' is now an admin"

def change_user_role(username, new_role):
    """Admin can change any user role from the app."""
    users = load_users()
    match = next(
        (u for u in users if u.lower() == username.lower()), None)
    if not match:
        return False, "User not found"
    users[match]["role"] = new_role
    save_users(users)
    return True, f"'{match}' role changed to {new_role}"

# ── Load data ─────────────────────────────────────────────────
def load_results():
    if not os.path.exists(RESULTS_FILE):
        return None
    return pd.read_csv(RESULTS_FILE)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return None
    return pd.read_csv(HISTORY_FILE)

def safe_float(val):
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except:
        return None

def get_24hrs(row, prefix):
    """Get 24 hour values from a result row."""
    vals = [safe_float(row.get(f'{prefix}_h{h:02d}'))
            for h in range(24)]
    return vals

# ================================================================
#  LOGIN PAGE
# ================================================================
def show_login_page():
    st.markdown("""
    <div style='text-align:center; padding:40px 0 20px 0'>
        <div style='font-size:52px'>⚡</div>
        <h2 style='color:#2563eb; margin:10px 0 4px 0'>
            TN Intelligent Load Forecasting
        </h2>
        <p style='color:#64748b; font-size:14px'>
            Tamil Nadu Power Grid — LSTM Day-Ahead Prediction System
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    tab_login, tab_register, tab_admin = st.tabs([
        "🔑 Login",
        "📝 Register",
        "🔧 Admin Setup"
    ])

    # ── LOGIN ─────────────────────────────────────────────────
    with tab_login:
        st.subheader("Login to your account")
        with st.form("login_form"):
            username = st.text_input(
                "Username", placeholder="Enter your username")
            password = st.text_input(
                "Password", type="password",
                placeholder="Enter your password")
            login_btn = st.form_submit_button(
                "🔑 Login",
                use_container_width=True,
                type="primary")

        if login_btn:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                ok, result, role = login_user(username, password)
                if ok:
                    st.session_state['logged_in'] = True
                    st.session_state['username']  = result
                    st.session_state['role']      = role
                    st.success(f"Welcome back, {result}!")
                    st.rerun()
                else:
                    st.error(f"❌ {result}")

    # ── REGISTER ──────────────────────────────────────────────
    with tab_register:
        st.subheader("Create a new account")
        st.info(
            "After registering, you will be a **Viewer** by default.\n\n"
            "To become Admin — go to the **Admin Setup** tab.")

        with st.form("register_form"):
            new_user = st.text_input(
                "Choose Username",
                placeholder="3 to 20 characters")
            new_pass = st.text_input(
                "Choose Password",
                type="password",
                placeholder="Minimum 6 characters")
            conf_pass = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Type password again")
            reg_btn = st.form_submit_button(
                "📝 Create Account",
                use_container_width=True,
                type="primary")

        if reg_btn:
            if not new_user or not new_pass or not conf_pass:
                st.error("Please fill all 3 fields")
            elif new_pass != conf_pass:
                st.error("Passwords do not match — type again")
            else:
                ok, msg = register_user(new_user, new_pass)
                if ok:
                    st.success(f"✅ {msg} — Now go to Login tab")
                else:
                    st.error(f"❌ {msg}")

    # ── ADMIN SETUP — FIX 2 ───────────────────────────────────
    with tab_admin:
        st.subheader("🔧 Make yourself Admin")
        st.info(
            "**How this works:**\n\n"
            "1. First register your account in the Register tab\n"
            "2. Come here and enter your username\n"
            "3. Enter the Admin Secret Key\n"
            "4. Click Make Admin\n"
            "5. Login — you will see upload buttons\n\n"
            "**Admin Secret Key is:  TN2025Admin**\n\n"
            "You can change this key in the code if you want.")

        with st.form("admin_form"):
            target = st.text_input(
                "Your Username",
                placeholder="Enter the username you registered with")
            secret = st.text_input(
                "Admin Secret Key",
                type="password",
                placeholder="Enter the secret key shown above")
            admin_btn = st.form_submit_button(
                "🔧 Make Admin",
                use_container_width=True)

        if admin_btn:
            if not target or not secret:
                st.error("Enter both username and secret key")
            else:
                ok, msg = make_admin("", secret, target)
                if ok:
                    st.success(
                        f"✅ {msg}\n\n"
                        f"Now go to Login tab and login. "
                        f"You will see upload buttons.")
                else:
                    st.error(f"❌ {msg}")

        st.divider()
        st.caption(
            "If you want to change the secret key — open "
            "streamlit_app_final.py in Notepad → find the line:\n"
            "ADMIN_SECRET = 'TN2025Admin'\n"
            "Change the value to anything you want → save → "
            "upload to GitHub → reboot app.")

    st.divider()
    st.caption(
        "Viewer accounts can see all charts and results. "
        "Admin accounts can also upload data from Colab.")

# ================================================================
#  SIDEBAR — shows differently for admin and viewer
# ================================================================
def show_sidebar(username, role):
    with st.sidebar:

        # User badge
        bg = "#7c3aed" if role == "admin" else "#2563eb"
        label = "Admin ✓" if role == "admin" else "Viewer"
        st.markdown(
            f"<div style='background:{bg};color:white;"
            f"padding:12px 16px;border-radius:10px;"
            f"margin-bottom:10px'>"
            f"<b>👤 {username}</b><br>"
            f"<span style='font-size:12px;opacity:0.85'>"
            f"{label}</span></div>",
            unsafe_allow_html=True)

        st.divider()

        # ── ADMIN SEES UPLOAD SECTION ─────────────────────────
        if role == "admin":
            st.subheader("📂 Upload Colab Results")
            st.caption(
                "Upload files downloaded from Colab.\n"
                "All viewers will see these results.")

            # Upload rolling results
            rf = st.file_uploader(
                "① rolling_results.csv",
                type=["csv"], key="rf")
            if rf is not None:
                df = pd.read_csv(rf)
                df.to_csv(RESULTS_FILE, index=False)
                st.success(f"✅ Loaded {len(df)} days")

            # Upload history
            hf = st.file_uploader(
                "② history_updated.csv",
                type=["csv"], key="hf")
            if hf is not None:
                dfh = pd.read_csv(hf)
                dfh.to_csv(HISTORY_FILE, index=False)
                st.success(f"✅ {len(dfh):,} rows loaded")

            # Upload charts zip
            cf = st.file_uploader(
                "③ charts.zip",
                type=["zip"], key="cf")
            if cf is not None:
                charts_dir = os.path.join(SHARED_DIR, "charts")
                os.makedirs(charts_dir, exist_ok=True)
                with zipfile.ZipFile(cf, 'r') as z:
                    z.extractall(charts_dir)
                st.success("✅ Charts extracted")

            st.divider()

            # ── Admin can manage user roles ────────────────────
            with st.expander("👥 Manage User Roles"):
                users = load_users()
                if users:
                    for uname, udata in users.items():
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(
                                f"**{uname}** — "
                                f"{udata.get('role','viewer')}")
                        with col2:
                            new_role = st.selectbox(
                                "Role",
                                ["viewer", "admin"],
                                index=0 if udata.get(
                                    'role','viewer')=='viewer'
                                else 1,
                                key=f"role_{uname}"
                            )
                            if st.button("Set",
                                         key=f"set_{uname}"):
                                change_user_role(uname, new_role)
                                st.success(f"Updated {uname}")
                                st.rerun()

        # ── VIEWER SEES DATA STATUS ───────────────────────────
        else:
            st.subheader("📊 Data Status")
            if os.path.exists(RESULTS_FILE):
                df_c = pd.read_csv(RESULTS_FILE)
                df_actual = df_c[df_c['mape'].notna()]
                st.success(
                    f"✅ {len(df_actual)} days with results")
                if 'date' in df_c.columns:
                    st.info(
                        f"Latest date:\n"
                        f"**{df_c['date'].iloc[-1]}**")
            else:
                st.warning(
                    "No results uploaded yet.\n\n"
                    "Ask your admin to upload the latest "
                    "Colab results.")
            st.divider()
            st.info(
                "You are a **Viewer**.\n\n"
                "You can see all charts, results and "
                "predictions.\n\n"
                "Data is uploaded by the admin.")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            for k in ['logged_in','username','role']:
                st.session_state[k] = (
                    False if k == 'logged_in' else None)
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
        f"Welcome <b>{username}</b> "
        f"({'Admin' if role=='admin' else 'Viewer'})</p>",
        unsafe_allow_html=True)
    st.divider()

    df = load_results()

    # Empty state
    if df is None or len(df) == 0:
        if role == "admin":
            st.info(
                "### No results yet\n\n"
                "Upload **rolling_results.csv** "
                "using the sidebar on the left.")
        else:
            st.info(
                "### No results available yet\n\n"
                "The admin has not uploaded results yet.\n"
                "Please check back later.")
        return

    # Split into rows with actual vs future prediction
    # FIX 1: rows where actual_h00 has a value = past days
    #         rows where actual_h00 is empty = next day prediction
    df['has_actual'] = df['actual_h00'].apply(
        lambda x: pd.notna(x) and str(x) not in ['', 'nan', 'None'])
    df_past   = df[df['has_actual']].copy()
    df_future = df[~df['has_actual']].copy()
    df_m      = df_past[df_past['mape'].notna()].copy()

    # ── STAT CARDS ────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("📅 Days Predicted",
              len(df_past),
              help="Days with actual vs predicted comparison")

    if len(df_m) > 0:
        avg_mape = df_m['mape'].mean()
        c2.metric("🎯 Avg MAPE",
                  f"{avg_mape:.2f}%",
                  help="Lower is better — below 5% is excellent")
        idx = df_m['mape'].idxmin()
        c3.metric("🏆 Best MAPE",
                  f"{df_m.loc[idx,'mape']:.2f}%",
                  delta=str(df_m.loc[idx,'date']),
                  delta_color="off")
        c4.metric("📊 Avg RMSE",
                  f"{df_m['rmse'].mean():.0f} MW")

    next_date = (df_future.iloc[-1]['date']
                 if len(df_future) > 0 else "—")
    c5.metric("🔮 Next Forecast", next_date)

    st.divider()

    # ── TABS ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Forecast",
        "🎯 Accuracy",
        "📋 All Results",
        "📖 About"
    ])

    hours   = list(range(24))
    hlabels = [f"{h:02d}:00" for h in hours]

    # ════════════════════════════════════════════════════
    #  TAB 1 — FORECAST
    #  Shows TWO charts:
    #  A) Today: predicted vs actual
    #  B) Tomorrow: next day prediction (FIX 1)
    # ════════════════════════════════════════════════════
    with tab1:

        # ── CHART A: Today ────────────────────────────────────
        st.subheader("📊 Today — Predicted vs Actual Load")

        if len(df_past) == 0:
            st.info(
                "No actual data yet.\n\n"
                "Run Colab, download results and upload here.")
        else:
            row    = df_past.iloc[-1]
            pred   = get_24hrs(row, 'pred')
            actual = get_24hrs(row, 'actual')

            # Metrics row
            m1, m2, m3, m4 = st.columns(4)
            mape_v = safe_float(row.get('mape'))
            rmse_v = safe_float(row.get('rmse'))
            vp     = [v for v in pred if v is not None]

            if mape_v is not None:
                color = (
                    "green" if mape_v < 5
                    else "orange" if mape_v < 10
                    else "red")
                m1.markdown(
                    f"<h3 style='color:{color}'>"
                    f"{mape_v:.2f}%</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"MAPE</p>",
                    unsafe_allow_html=True)
            if rmse_v is not None:
                m2.markdown(
                    f"<h3>{rmse_v:.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"RMSE</p>",
                    unsafe_allow_html=True)
            if vp:
                m3.markdown(
                    f"<h3 style='color:#2563eb'>"
                    f"{max(vp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Peak Predicted</p>",
                    unsafe_allow_html=True)
            m4.markdown(
                f"<h3>{row['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>"
                f"Date</p>",
                unsafe_allow_html=True)

            # Chart A
            fig_a = go.Figure()
            has_actual = any(v is not None for v in actual)
            if has_actual:
                fig_a.add_trace(go.Scatter(
                    x=hlabels, y=actual,
                    name="Actual Load",
                    line=dict(color="#16a34a", width=3),
                    mode="lines+markers",
                    marker=dict(size=7),
                    fill="tozeroy",
                    fillcolor="rgba(22,163,74,0.07)"))
            fig_a.add_trace(go.Scatter(
                x=hlabels, y=pred,
                name="Predicted Load",
                line=dict(color="#2563eb", width=2.5,
                          dash="dash"),
                mode="lines+markers",
                marker=dict(size=6)))
            fig_a.update_layout(
                title=f"Predicted vs Actual — {row['date']}",
                xaxis_title="Hour of Day",
                yaxis_title="Load (MW)",
                hovermode="x unified",
                height=400,
                legend=dict(orientation="h",
                            yanchor="bottom", y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_a, use_container_width=True)

        st.divider()

        # ── CHART B: Tomorrow — FIX 1 ─────────────────────────
        st.subheader("🔮 Tomorrow — Next Day Prediction")
        st.caption(
            "This is the model's prediction for the next day. "
            "It is saved by Colab automatically in "
            "rolling_results.csv as the last row.")

        if len(df_future) == 0:
            st.warning(
                "⚠ Next day prediction not found.\n\n"
                "**Why?** Your current Colab notebook saves "
                "only comparison data.\n\n"
                "**Fix:** Update CELL 8 in Colab using the "
                "code in the file  **COLAB_CELL8_FIX.py** "
                "— download it below and follow the "
                "instructions inside.")
        else:
            nrow  = df_future.iloc[-1]
            npred = get_24hrs(nrow, 'pred')
            vnp   = [v for v in npred if v is not None]

            # Metrics row
            n1, n2, n3, n4 = st.columns(4)
            if vnp:
                n1.markdown(
                    f"<h3 style='color:#ea580c'>"
                    f"{max(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Peak</p>",
                    unsafe_allow_html=True)
                n2.markdown(
                    f"<h3>{min(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Min</p>",
                    unsafe_allow_html=True)
                n3.markdown(
                    f"<h3>{np.mean(vnp):,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>"
                    f"Average</p>",
                    unsafe_allow_html=True)
            n4.markdown(
                f"<h3 style='color:#7c3aed'>"
                f"{nrow['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>"
                f"Forecast Date</p>",
                unsafe_allow_html=True)

            # Chart B
            fig_b = go.Figure()
            fig_b.add_trace(go.Scatter(
                x=hlabels, y=npred,
                name="Next Day Forecast",
                line=dict(color="#ea580c", width=3),
                mode="lines+markers",
                marker=dict(size=8, symbol="diamond"),
                fill="tozeroy",
                fillcolor="rgba(234,88,12,0.07)"))

            # Peak annotation
            if vnp:
                ph = npred.index(max(vnp))
                fig_b.add_annotation(
                    x=hlabels[ph], y=max(vnp),
                    text=f"Peak: {max(vnp):,.0f} MW",
                    showarrow=True, arrowhead=2,
                    arrowcolor="#ea580c",
                    font=dict(color="#ea580c", size=12),
                    bgcolor="white",
                    bordercolor="#ea580c",
                    borderwidth=1.5,
                    ay=-40)

            fig_b.update_layout(
                title=(f"Next Day Forecast — {nrow['date']}"),
                xaxis_title="Hour of Day",
                yaxis_title="Load (MW)",
                hovermode="x unified",
                height=400,
                legend=dict(orientation="h",
                            yanchor="bottom", y=1.02),
                yaxis=dict(tickformat=","),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_b, use_container_width=True)

            # Next day hourly table
            st.subheader("Next Day — Hourly Table")
            rows = []
            for h in hours:
                v = npred[h]
                is_peak = (v is not None and vnp
                           and v == max(vnp))
                rows.append({
                    "Hour"          : f"{h:02d}:00",
                    "Predicted (MW)": (f"{v:,.0f}"
                                       if v else "—"),
                    "Note"          : ("🔴 Peak hour"
                                       if is_peak
                                       else "")
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                height=280)

    # ════════════════════════════════════════════════════
    #  TAB 2 — ACCURACY TREND
    # ════════════════════════════════════════════════════
    with tab2:

        if len(df_m) == 0:
            st.info("No accuracy data yet.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                fm = px.line(
                    df_m, x="date", y="mape",
                    title="MAPE % Over Days — "
                          "Should Go Down Over Time",
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
                st.plotly_chart(fm, use_container_width=True)

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
                st.plotly_chart(fr, use_container_width=True)

            # Actual vs predicted average
            if ('actual_avg' in df_m.columns
                    and 'predicted_avg' in df_m.columns):
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
                    title="Actual vs Predicted — Daily Average",
                    height=300, hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fa, use_container_width=True)

            # View any past day
            st.subheader("View Any Past Day in Detail")
            sel = st.selectbox(
                "Select a date to see its chart",
                df_m['date'].tolist()[::-1])
            if sel:
                r   = df_m[df_m['date'] == sel].iloc[0]
                p2  = get_24hrs(r, 'pred')
                a2  = get_24hrs(r, 'actual')
                fd  = go.Figure()
                fd.add_trace(go.Scatter(
                    x=hlabels, y=a2, name="Actual",
                    line=dict(color="#16a34a", width=2),
                    mode="lines+markers"))
                fd.add_trace(go.Scatter(
                    x=hlabels, y=p2, name="Predicted",
                    line=dict(color="#2563eb", width=2,
                              dash="dash"),
                    mode="lines+markers"))
                mv = safe_float(r.get('mape'))
                rv = safe_float(r.get('rmse'))
                title = (
                    f"{sel} — MAPE: {mv:.2f}% | "
                    f"RMSE: {rv:.0f} MW"
                    if mv is not None else sel)
                fd.update_layout(
                    title=title, height=320,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fd, use_container_width=True)

    # ════════════════════════════════════════════════════
    #  TAB 3 — ALL RESULTS
    # ════════════════════════════════════════════════════
    with tab3:
        st.subheader(f"All Results — {len(df_past)} days")
        cols  = ['day_number', 'date', 'trained_upto',
                 'mape', 'rmse', 'actual_avg',
                 'predicted_avg', 'actual_peak']
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
        st.dataframe(
            ds, use_container_width=True,
            hide_index=True, height=420)
        st.download_button(
            "⬇ Download Results CSV",
            df_past.to_csv(index=False).encode(),
            "TN_results.csv", "text/csv",
            use_container_width=True)

    # ════════════════════════════════════════════════════
    #  TAB 4 — ABOUT
    # ════════════════════════════════════════════════════
    with tab4:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
### System Overview
**Data** — 5 years Tamil Nadu power grid load
(2020–2024) · 22 features including real wind100

**Model** — LSTM Neural Network
- 2 LSTM layers (128 + 64 units)
- 168-hour lookback (7 days)
- Predicts next 24 hours
- Trained in Google Colab (free)

**Rolling Forecast**
- Add actual data each day
- Model retrains automatically
- MAPE improves over time
- Continues forever
            """)
        with c2:
            st.markdown("""
### User Roles
| Role | Can do |
|------|--------|
| **Admin** | Upload + View everything |
| **Viewer** | View everything (no upload) |

### How to become Admin
1. Register your account
2. Click **Admin Setup** tab on login page
3. Enter your username
4. Enter Admin Secret Key:  **TN2025Admin**
5. Click Make Admin
6. Login — upload buttons appear

### Features (22 total)
temperature · humidity · rain
wind10 · **wind100** (real data)
radiation · cloud_cover
hour · month · day_of_week
is_summer · is_monsoon · is_holiday
load_lag_24 · load_lag_168 · and more
            """)

# ================================================================
#  MAIN
# ================================================================
def main():
    # Initialise session
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username']  = None
        st.session_state['role']      = None

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
