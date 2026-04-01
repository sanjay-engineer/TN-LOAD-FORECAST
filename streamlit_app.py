# ================================================================
#  TN INTELLIGENT LOAD FORECASTING — COMPLETE ONLINE SYSTEM
#  
#  FEATURES:
#  ✓ User registration and login
#  ✓ Each user has their own private data
#  ✓ Upload CSV results from Colab
#  ✓ Full dashboard with charts
#  ✓ Rolling forecast history
#  ✓ Works on any device — phone or laptop
#  ✓ Free deployment on Streamlit Cloud
#
#  FILE: streamlit_app.py
#  RUN:  streamlit run streamlit_app.py
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, zipfile
from datetime import datetime

# ================================================================
#  PAGE CONFIGURATION
# ================================================================
st.set_page_config(
    page_title = "TN Load Forecasting",
    page_icon  = "⚡",
    layout     = "wide",
    initial_sidebar_state = "expanded"
)

# ================================================================
#  SECTION A — USER DATABASE
#  Users are stored in users.json file
#  Each user has: username, password (hashed), created date
# ================================================================

USERS_FILE   = "users.json"
RESULTS_DIR  = "user_results"   # each user gets their own folder

os.makedirs(RESULTS_DIR, exist_ok=True)


def hash_password(password):
    """Convert password to secure hash — never store plain text."""
    return hashlib.sha256(password.encode()).hexdigest()


def load_users():
    """Load all registered users from file."""
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    """Save users to file."""
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def register_user(username, password):
    """
    Register a new user.
    Returns (True, message) if success
    Returns (False, message) if failed
    """
    # Validate username
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(username) > 20:
        return False, "Username must be less than 20 characters"
    if not username.replace("_", "").isalnum():
        return False, "Username can only have letters, numbers, underscore"

    # Validate password
    if len(password) < 6:
        return False, "Password must be at least 6 characters"

    users = load_users()

    # Check if username already exists
    if username.lower() in [u.lower() for u in users]:
        return False, "Username already exists — choose another"

    # Save new user
    users[username] = {
        "password"  : hash_password(password),
        "created"   : str(datetime.now().date()),
        "last_login": None,
    }
    save_users(users)

    # Create personal results folder for this user
    user_folder = os.path.join(RESULTS_DIR, username)
    os.makedirs(user_folder, exist_ok=True)

    return True, "Account created successfully"


def login_user(username, password):
    """
    Check username and password.
    Returns (True, message) if correct
    Returns (False, message) if wrong
    """
    users = load_users()

    # Find user (case insensitive username)
    matched_user = None
    for u in users:
        if u.lower() == username.lower():
            matched_user = u
            break

    if matched_user is None:
        return False, "Username not found"

    if users[matched_user]["password"] != hash_password(password):
        return False, "Wrong password"

    # Update last login
    users[matched_user]["last_login"] = str(datetime.now())
    save_users(users)

    return True, matched_user   # return actual username with correct case


def get_user_folder(username):
    """Get the personal results folder for a user."""
    folder = os.path.join(RESULTS_DIR, username)
    os.makedirs(folder, exist_ok=True)
    return folder


# ================================================================
#  SECTION B — LOGIN AND REGISTER UI
# ================================================================

def show_login_page():
    """Show the login / register page."""

    # Header
    st.markdown("""
    <div style='text-align:center; padding: 30px 0 10px 0'>
        <h1 style='font-size:36px'>⚡</h1>
        <h2 style='color:#2563eb'>TN Intelligent Load Forecasting</h2>
        <p style='color:#64748b'>Tamil Nadu Power Grid — LSTM Day-Ahead Prediction</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Login / Register tabs
    tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])

    # ── LOGIN TAB ─────────────────────────────────────────────
    with tab_login:
        st.subheader("Login to your account")

        with st.form("login_form"):
            username = st.text_input(
                "Username",
                placeholder="Enter your username"
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password"
            )
            submit = st.form_submit_button(
                "Login", use_container_width=True, type="primary"
            )

        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                success, result = login_user(username, password)
                if success:
                    # Save login state
                    st.session_state['logged_in']  = True
                    st.session_state['username']   = result
                    st.session_state['user_folder']= get_user_folder(result)
                    st.success(f"Welcome back, {result}!")
                    st.rerun()
                else:
                    st.error(f"Login failed: {result}")

    # ── REGISTER TAB ──────────────────────────────────────────
    with tab_register:
        st.subheader("Create a new account")

        with st.form("register_form"):
            new_username = st.text_input(
                "Choose Username",
                placeholder="3-20 characters, letters and numbers only"
            )
            new_password = st.text_input(
                "Choose Password",
                type="password",
                placeholder="Minimum 6 characters"
            )
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Type password again"
            )
            reg_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True,
                type="primary"
            )

        if reg_submit:
            if not new_username or not new_password or not confirm_password:
                st.error("Please fill all fields")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            else:
                success, msg = register_user(new_username, new_password)
                if success:
                    st.success(
                        f"{msg}. You can now login with your username."
                    )
                else:
                    st.error(msg)

    # Info box at bottom
    st.divider()
    st.info(
        "**New here?** Click the Register tab to create your account.\n\n"
        "Each user gets their own private space to upload data and view results."
    )


# ================================================================
#  SECTION C — DATA FUNCTIONS
# ================================================================

def load_results(user_folder):
    """Load results CSV for current user."""
    path = os.path.join(user_folder, "rolling_results.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def save_results(user_folder, df):
    """Save results CSV for current user."""
    path = os.path.join(user_folder, "rolling_results.csv")
    df.to_csv(path, index=False)


def load_history(user_folder):
    """Load history CSV for current user."""
    path = os.path.join(user_folder, "history_updated.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


# ================================================================
#  SECTION D — SIDEBAR
# ================================================================

def show_sidebar(username, user_folder):
    """Show the sidebar with user info and file uploads."""

    with st.sidebar:
        # User info
        st.markdown(f"### 👤 {username}")
        st.caption(f"Logged in to your private space")
        st.divider()

        # Upload section
        st.subheader("📂 Upload Results")
        st.caption("After running Colab, upload your files here")

        # Upload rolling results
        results_file = st.file_uploader(
            "1. Upload rolling_results.csv",
            type=["csv"],
            key="results_upload",
            help="Created by TN_COMPLETE_COLAB.py in Google Colab"
        )

        if results_file is not None:
            df = pd.read_csv(results_file)
            save_results(user_folder, df)
            st.success(f"✓ Loaded {len(df)} days of results")

        # Upload history
        history_file = st.file_uploader(
            "2. Upload history_updated.csv",
            type=["csv"],
            key="history_upload",
            help="Your growing database from Colab"
        )

        if history_file is not None:
            df_h = pd.read_csv(history_file)
            path = os.path.join(user_folder, "history_updated.csv")
            df_h.to_csv(path, index=False)
            st.success(f"✓ History loaded: {len(df_h):,} rows")

        # Upload charts zip
        charts_zip = st.file_uploader(
            "3. Upload charts.zip",
            type=["zip"],
            key="charts_upload",
            help="Zip of all chart PNGs from Colab"
        )

        if charts_zip is not None:
            charts_folder = os.path.join(user_folder, "charts")
            os.makedirs(charts_folder, exist_ok=True)
            with zipfile.ZipFile(charts_zip, 'r') as z:
                z.extractall(charts_folder)
            st.success("✓ Charts extracted")

        st.divider()

        # How to get files
        with st.expander("❓ How to get these files"):
            st.markdown("""
1. Open **Google Colab**
2. Run `TN_COMPLETE_COLAB.py`
3. After it finishes, download:
   - `rolling_results.csv`
   - `history_updated.csv`
   - `charts.zip`
4. Upload them here
""")

        st.divider()

        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state['logged_in']  = False
            st.session_state['username']   = None
            st.session_state['user_folder']= None
            st.rerun()


# ================================================================
#  SECTION E — DASHBOARD PAGES
# ================================================================

def show_dashboard(username, user_folder):
    """Main dashboard shown after login."""

    # Top header
    st.markdown(
        f"<h2 style='color:#2563eb'>⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>Tamil Nadu Power Grid — "
        f"Welcome <b>{username}</b></p>",
        unsafe_allow_html=True
    )
    st.divider()

    # Load data
    df = load_results(user_folder)

    # ── EMPTY STATE ───────────────────────────────────────────
    if df is None or len(df) == 0:
        st.info(
            "### No results yet\n\n"
            "**Follow these steps:**\n"
            "1. Run `TN_COMPLETE_COLAB.py` in Google Colab\n"
            "2. Download `rolling_results.csv`, `history_updated.csv`, `charts.zip`\n"
            "3. Upload them using the sidebar on the left\n\n"
            "Your results will appear here instantly after upload."
        )
        return

    # Filter rows with MAPE data
    df_m = df[df['mape'].notna()].copy()

    # ── STAT CARDS ────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric(
            "📅 Days Predicted",
            len(df),
            help="Total days forecasted so far"
        )
    with c2:
        if len(df_m) > 0:
            avg = df_m['mape'].mean()
            st.metric(
                "🎯 Avg MAPE",
                f"{avg:.2f}%",
                help="Mean Absolute Percentage Error — lower is better"
            )
    with c3:
        if len(df_m) > 0:
            best_idx  = df_m['mape'].idxmin()
            best_mape = df_m.loc[best_idx, 'mape']
            best_date = df_m.loc[best_idx, 'date']
            st.metric(
                "🏆 Best MAPE",
                f"{best_mape:.2f}%",
                delta=f"on {best_date}",
                delta_color="off"
            )
    with c4:
        if len(df_m) > 0:
            st.metric(
                "📊 Avg RMSE",
                f"{df_m['rmse'].mean():.0f} MW",
                help="Root Mean Square Error in Megawatts"
            )
    with c5:
        st.metric(
            "📆 Latest Date",
            str(df['date'].iloc[-1])
        )

    st.divider()

    # ── MAIN TABS ─────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Latest Forecast",
        "🎯 Accuracy Trend",
        "📋 All Predictions",
        "📖 How It Works"
    ])

    # ════════════════════════════════════════════════════
    #  TAB 1 — LATEST FORECAST
    # ════════════════════════════════════════════════════
    with tab1:

        latest = df.iloc[-1]
        hours  = list(range(24))
        hlabels= [f"{h:02d}:00" for h in hours]

        pred   = [latest.get(f'pred_h{h:02d}')   for h in hours]
        actual = [latest.get(f'actual_h{h:02d}')  for h in hours]

        # Accuracy metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            mape_val = latest.get('mape')
            if pd.notna(mape_val):
                color = "green" if mape_val < 5 else "orange"
                st.markdown(
                    f"<h3 style='color:{color}'>{mape_val:.2f}%</h3>"
                    f"<p style='color:#64748b;font-size:12px'>MAPE</p>",
                    unsafe_allow_html=True
                )
        with m2:
            rmse_val = latest.get('rmse')
            if pd.notna(rmse_val):
                st.markdown(
                    f"<h3>{rmse_val:.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>RMSE</p>",
                    unsafe_allow_html=True
                )
        with m3:
            valid_pred = [v for v in pred if v is not None]
            if valid_pred:
                peak = max(valid_pred)
                st.markdown(
                    f"<h3 style='color:#2563eb'>{peak:,.0f} MW</h3>"
                    f"<p style='color:#64748b;font-size:12px'>Peak Predicted</p>",
                    unsafe_allow_html=True
                )
        with m4:
            st.markdown(
                f"<h3>{latest['date']}</h3>"
                f"<p style='color:#64748b;font-size:12px'>Forecast Date</p>",
                unsafe_allow_html=True
            )

        # Main chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hlabels, y=pred,
            name="Predicted Load",
            line=dict(color="#2563eb", width=2.5),
            mode="lines+markers",
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(37,99,235,0.07)"
        ))

        has_actual = any(
            v is not None and not (isinstance(v, float) and np.isnan(v))
            for v in actual
        )
        if has_actual:
            fig.add_trace(go.Scatter(
                x=hlabels, y=actual,
                name="Actual Load",
                line=dict(color="#16a34a", width=2.5),
                mode="lines+markers",
                marker=dict(size=6)
            ))

        fig.update_layout(
            title=dict(
                text=f"Day-Ahead Forecast — {latest['date']}",
                font=dict(size=16)
            ),
            xaxis_title="Hour of Day",
            yaxis_title="Load (MW)",
            hovermode="x unified",
            height=420,
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02
            ),
            yaxis=dict(tickformat=","),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Hourly table
        st.subheader("Hourly Breakdown")
        rows = []
        for h in hours:
            p = pred[h]
            a = actual[h]
            err = "—"
            if (p is not None and a is not None
                    and not np.isnan(float(p)) if p else False
                    and not np.isnan(float(a)) if a else False
                    and float(a) > 0):
                err = f"{abs((float(p)-float(a))/float(a)*100):.1f}%"
            rows.append({
                "Hour"          : f"{h:02d}:00",
                "Predicted (MW)": f"{float(p):,.0f}" if p else "—",
                "Actual (MW)"   : f"{float(a):,.0f}" if a else "—",
                "Error %"       : err,
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            height=300
        )

    # ════════════════════════════════════════════════════
    #  TAB 2 — ACCURACY TREND
    # ════════════════════════════════════════════════════
    with tab2:

        if len(df_m) == 0:
            st.info(
                "No accuracy data yet. "
                "Upload actual day data in Colab and re-upload results."
            )
        else:
            c1, c2 = st.columns(2)

            # MAPE trend
            with c1:
                fig_mape = px.line(
                    df_m, x="date", y="mape",
                    title="MAPE % — Goes Down as Model Learns",
                    markers=True,
                    color_discrete_sequence=["#ea580c"]
                )
                fig_mape.add_hline(
                    y=df_m['mape'].mean(),
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Avg: {df_m['mape'].mean():.2f}%"
                )
                fig_mape.update_layout(
                    xaxis_title="Date",
                    yaxis_title="MAPE %",
                    height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_mape, use_container_width=True)

            # RMSE trend
            with c2:
                fig_rmse = px.line(
                    df_m, x="date", y="rmse",
                    title="RMSE (MW) Over Days",
                    markers=True,
                    color_discrete_sequence=["#7c3aed"]
                )
                fig_rmse.add_hline(
                    y=df_m['rmse'].mean(),
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Avg: {df_m['rmse'].mean():.0f} MW"
                )
                fig_rmse.update_layout(
                    xaxis_title="Date",
                    yaxis_title="RMSE MW",
                    height=300,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_rmse, use_container_width=True)

            # Actual vs predicted avg
            if 'actual_avg' in df_m.columns:
                fig_avg = go.Figure()
                fig_avg.add_trace(go.Scatter(
                    x=df_m['date'], y=df_m['actual_avg'],
                    name="Actual Avg Load",
                    line=dict(color="#16a34a", width=2),
                    mode="lines+markers"
                ))
                fig_avg.add_trace(go.Scatter(
                    x=df_m['date'], y=df_m['predicted_avg'],
                    name="Predicted Avg Load",
                    line=dict(color="#2563eb", width=2, dash="dash"),
                    mode="lines+markers"
                ))
                fig_avg.update_layout(
                    title="Actual vs Predicted Average Daily Load",
                    xaxis_title="Date",
                    yaxis_title="Avg Load (MW)",
                    height=300,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_avg, use_container_width=True)

            # Pick any past day
            st.subheader("View Any Past Day")
            selected = st.selectbox(
                "Select a date",
                options=df_m['date'].tolist()[::-1],
                key="day_select"
            )
            if selected:
                row  = df_m[df_m['date'] == selected].iloc[0]
                p2   = [row.get(f'pred_h{h:02d}')   for h in range(24)]
                a2   = [row.get(f'actual_h{h:02d}')  for h in range(24)]
                hl2  = [f"{h:02d}:00" for h in range(24)]

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=hl2, y=p2, name="Predicted",
                    line=dict(color="#2563eb", width=2),
                    mode="lines+markers"
                ))
                fig2.add_trace(go.Scatter(
                    x=hl2, y=a2, name="Actual",
                    line=dict(color="#16a34a", width=2),
                    mode="lines+markers"
                ))
                mape2 = row.get('mape')
                rmse2 = row.get('rmse')
                title2 = (
                    f"{selected}  —  MAPE: {mape2:.2f}%  |  RMSE: {rmse2:.0f} MW"
                    if pd.notna(mape2) else selected
                )
                fig2.update_layout(
                    title=title2,
                    xaxis_title="Hour",
                    yaxis_title="Load (MW)",
                    height=320,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig2, use_container_width=True)

    # ════════════════════════════════════════════════════
    #  TAB 3 — ALL PREDICTIONS TABLE
    # ════════════════════════════════════════════════════
    with tab3:

        st.subheader(f"All Forecast Results — {len(df)} days")

        # Show clean table
        show_cols = ['day_number', 'date', 'trained_upto',
                     'mape', 'rmse', 'actual_avg',
                     'predicted_avg', 'actual_peak']
        available = [c for c in show_cols if c in df.columns]
        df_show   = df[available].copy()

        # Round numbers
        for col in ['mape', 'rmse', 'actual_avg',
                    'predicted_avg', 'actual_peak']:
            if col in df_show.columns:
                df_show[col] = pd.to_numeric(
                    df_show[col], errors='coerce'
                ).round(2)

        df_show.columns = [
            c.replace('_', ' ').title() for c in df_show.columns
        ]

        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            height=400
        )

        # Download button
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇ Download Full Results CSV",
            data=csv_bytes,
            file_name="TN_forecast_results.csv",
            mime="text/csv",
            use_container_width=True
        )

        # History info
        df_hist = load_history(user_folder)
        if df_hist is not None:
            st.info(
                f"**Database size:** {len(df_hist):,} hourly records  |  "
                f"**From:** {df_hist['Datetime'].iloc[0][:10] if 'Datetime' in df_hist.columns else 'N/A'}  "
                f"**To:** {df_hist['Datetime'].iloc[-1][:10] if 'Datetime' in df_hist.columns else 'N/A'}"
            )

    # ════════════════════════════════════════════════════
    #  TAB 4 — HOW IT WORKS
    # ════════════════════════════════════════════════════
    with tab4:

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("""
### How This System Works

**Step 1 — Historical Data (done once)**
Your 5-year Tamil Nadu load data from 2020 to 2024.
43,848 hourly records with 21 features.

**Step 2 — Training in Colab (done once)**
LSTM model trains on 5 years of data.
Takes 10-20 minutes in Google Colab.
Uses Google's free CPU.

**Step 3 — Predict + Add data (every day)**
Upload that day's actual CSV to Colab.
Model predicts next day — compares with actual.
Retrains with new day added — gets smarter.

**Step 4 — Upload results here**
Download 3 files from Colab.
Upload here using the sidebar.
Dashboard updates instantly.
            """)

        with c2:
            st.markdown("""
### Model Architecture
```
Input: 168 hours × 21 features
        ↓
LSTM Layer 1 — 128 units
        ↓
LSTM Layer 2 — 64 units
        ↓
Dense Layer — 32 units
        ↓
Output: 24 hourly MW values
```

### What MAPE means
If MAPE = 4% → prediction is 96% accurate.
Below 5% is excellent for power forecasting.
Model improves every day as more data is added.

### Technologies Used
- Python, TensorFlow, Keras
- Streamlit (this dashboard)
- Plotly (interactive charts)
- Google Colab (free training)
            """)

        st.divider()

        # Add new day instructions
        st.subheader("How to Add New Day Data")
        st.markdown("""
| Step | What you do |
|------|------------|
| 1 | Prepare new day CSV — 24 rows, same columns as your data |
| 2 | Upload it to Google Colab |
| 3 | In CELL 8, add filename to NEW_DAY_FILES list |
| 4 | Run CELL 8, 9, 10, 11 |
| 5 | Download the 3 output files |
| 6 | Upload them here using the sidebar |
| 7 | Dashboard shows updated results instantly |

The model retrains automatically each time. Gets smarter every day.
        """)


# ================================================================
#  SECTION F — MAIN APP — controls what page to show
# ================================================================

def main():
    """
    Main function — decides what to show:
    - If not logged in → show login/register page
    - If logged in → show dashboard
    """

    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in']   = False
        st.session_state['username']    = None
        st.session_state['user_folder'] = None

    # ── NOT LOGGED IN → show login page ──────────────────────
    if not st.session_state['logged_in']:
        show_login_page()
        return

    # ── LOGGED IN → show dashboard ────────────────────────────
    username    = st.session_state['username']
    user_folder = st.session_state['user_folder']

    # Show sidebar
    show_sidebar(username, user_folder)

    # Show main dashboard
    show_dashboard(username, user_folder)


# ── Run the app ───────────────────────────────────────────────
if __name__ == "__main__":
    main()
