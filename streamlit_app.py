# ================================================================
# TN LOAD FORECASTING — STREAMLIT APP (COMPLETE WITH ROLLING FORECAST)
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
import calendar
from datetime import datetime
from io import StringIO

# ============ CONFIG ============
st.set_page_config(page_title="TN Load Forecasting", page_icon="⚡", layout="wide")

GITHUB_USER = "sanjay-engineer"
GITHUB_REPO = "TN-LOAD-FORECAST"
GITHUB_RAW = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/results"

MONTH_NAMES = {4: "April", 5: "May", 6: "June"}
MONTH_COLORS = {4: "#2563eb", 5: "#16a34a", 6: "#ea580c"}
MONTH_FILL = {4: "rgba(37,99,235,0.10)", 5: "rgba(22,163,74,0.10)", 6: "rgba(234,88,12,0.10)"}
YEAR_COLORS = {2020:"#94a3b8", 2021:"#64748b", 2022:"#f59e0b", 2023:"#8b5cf6", 
              2024:"#ec4899", 2025:"#6366f1", 2026:"#dc2626"}

BL = dict(
    template="plotly_white",
    font=dict(family="Arial", size=11, color="#1f2937"),
    xaxis=dict(showgrid=True, gridwidth=1, gridcolor="#e5e7eb"),
    yaxis=dict(showgrid=True, gridwidth=1, gridcolor="#e5e7eb"),
    hovermode="x unified",
    margin=dict(l=50, r=30, t=60, b=50)
)

# ============ EMBEDDED HISTORICAL DATA ============
HIST_MONTHLY = {
    (2020,4):{'avg':9860.2,'peak':11281.1},(2020,5):{'avg':11884.4,'peak':14378.4},(2020,6):{'avg':12377.4,'peak':14320.5},
    (2021,4):{'avg':14544.4,'peak':16913.8},(2021,5):{'avg':12517.8,'peak':15893.9},(2021,6):{'avg':12821.3,'peak':16058.2},
    (2022,4):{'avg':14751.5,'peak':17509.6},(2022,5):{'avg':13897.7,'peak':16796.5},(2022,6):{'avg':14428.5,'peak':16743.9},
    (2023,4):{'avg':15993.5,'peak':19436.0},(2023,5):{'avg':14922.9,'peak':18469.3},(2023,6):{'avg':15494.2,'peak':18308.4},
    (2024,4):{'avg':16580.4,'peak':19576.5},(2024,5):{'avg':16108.9,'peak':20393.0},(2024,6):{'avg':15040.3,'peak':18133.0},
    (2025,4):{'avg':16692.8,'peak':19975.8},(2025,5):{'avg':15673.0,'peak':19477.0},(2025,6):{'avg':16305.3,'peak':19780.2},
}

HIST_DAILY = {
    (2020,4):{1:9761.6,2:9988.2,3:10146.7,4:10080.5,5:9952.7,6:9993.9,7:9754.6,8:9729.3,9:9157.3,10:8415.5,11:9038.8,12:9174.6,13:9683.4,14:9852.3,15:10037.3,16:10234.5,17:10413.2,18:10526.4,19:10256.9,20:10417.1,21:10393.0,22:10558.7,23:10677.0,24:10660.2,25:10388.2,26:9324.4,27:9337.9,28:9683.2,29:8917.9,30:9251.3},
    (2020,5):{1:9426.8,2:9930.2,3:10163.6,4:10665.6,5:11044.4,6:11516.2,7:11461.8,8:11780.0,9:11915.8,10:11775.5,11:12408.6,12:12184.7,13:12153.6,14:12405.1,15:12550.6,16:12273.3,17:11340.4,18:11214.8,19:11401.8,20:12156.2,21:12347.6,22:12557.4,23:12786.2,24:12339.4,25:12539.7,26:13087.7,27:13346.7,28:12848.0,29:12343.2,30:12602.9,31:11848.0},
    (2020,6):{1:12389.4,2:12501.7,3:12678.8,4:12987.7,5:13124.7,6:12297.4,7:11654.6,8:12370.6,9:12874.7,10:12714.9,11:12314.5,12:11975.8,13:12284.6,14:11736.3,15:12882.7,16:13114.6,17:13421.0,18:13244.4,19:13189.7,20:12916.2,21:12021.1,22:12175.3,23:12347.0,24:12041.3,25:11799.3,26:11792.0,27:12005.2,28:11141.6,29:11626.7,30:11698.3},
    (2021,4):{1:14993.7,2:15119.2,3:15072.7,4:14563.4,5:15108.7,6:13072.9,7:14816.8,8:15156.9,9:15513.0,10:15620.5,11:14306.8,12:14710.2,13:14746.2,14:13765.3,15:12884.2,16:13612.9,17:13941.0,18:13291.1,19:14124.8,20:14412.3,21:14616.0,22:14671.0,23:14742.9,24:14978.6,25:13357.0,26:14417.8,27:14955.8,28:15165.7,29:15305.5,30:15289.3},
    (2021,5):{1:13941.3,2:13234.0,3:14248.3,4:14687.6,5:14716.9,6:14751.6,7:14451.0,8:14124.1,9:13160.4,10:13283.3,11:13736.6,12:13705.5,13:13200.3,14:12750.4,15:12091.0,16:11288.7,17:12025.0,18:12721.4,19:12840.4,20:11905.0,21:11138.3,22:10935.8,23:10615.3,24:11053.2,25:10562.9,26:10120.1,27:10684.9,28:11463.1,29:11557.9,30:11348.2,31:11710.7},
    (2021,6):{1:12321.8,2:12580.2,3:12575.1,4:11978.6,5:11287.0,6:10249.3,7:11931.2,8:12217.9,9:12304.3,10:12773.2,11:13116.3,12:12667.9,13:11500.3,14:12270.4,15:12946.6,16:13418.0,17:13561.0,18:13801.0,19:13519.7,20:13097.1,21:13842.3,22:13694.3,23:13575.8,24:12960.2,25:13530.2,26:13530.8,27:12495.4,28:12471.3,29:13945.3,30:14475.8},
    (2022,4):{1:15440.6,2:15350.1,3:14341.6,4:15169.6,5:15366.0,6:15422.7,7:15548.4,8:15513.9,9:14992.0,10:13362.7,11:14202.4,12:14466.8,13:14158.0,14:13094.4,15:13573.4,16:14033.1,17:12357.9,18:13302.2,19:14343.1,20:14794.7,21:14869.2,22:14869.2,23:14869.2,24:14869.2,25:14869.2,26:14869.2,27:15832.4,28:16181.7,29:16316.7,30:16165.3},
    (2022,5):{1:14329.4,2:15088.8,3:15309.4,4:15203.1,5:15036.1,6:13456.4,7:14125.7,8:13243.0,9:13415.3,10:11398.1,11:11438.8,12:13462.7,13:12969.9,14:13585.4,15:11487.1,16:12472.2,17:13295.7,18:13202.4,19:13342.3,20:13862.7,21:14001.8,22:13041.4,23:14109.7,24:15590.7,25:15422.1,26:15051.8,27:15055.5,28:14851.4,29:13996.8,30:14901.4,31:15082.5},
    (2022,6):{1:15023.1,2:15065.1,3:15206.6,4:15161.8,5:14213.2,6:14200.1,7:14105.5,8:14497.0,9:15078.2,10:15418.4,11:14729.7,12:13814.8,13:14688.0,14:15202.3,15:14944.6,16:14129.6,17:14299.1,18:13698.7,19:12824.8,20:13196.4,21:13393.8,22:13738.1,23:14228.6,24:14526.3,25:14125.4,26:13450.0,27:14574.6,28:15062.8,29:15213.8,30:15045.8},
    (2023,4):{1:15612.9,2:14341.8,3:15241.1,4:15776.7,5:15536.6,6:15946.2,7:16133.8,8:15989.4,9:14802.1,10:15904.6,11:16420.4,12:16496.4,13:16718.9,14:15992.0,15:16308.3,16:15489.1,17:16600.6,18:17139.0,19:17475.1,20:17795.5,21:17387.1,22:16764.0,23:14661.5,24:15384.5,25:15816.4,26:15803.4,27:16052.1,28:16115.9,29:15831.5,30:14268.6},
    (2023,5):{1:12713.3,2:12557.7,3:13415.1,4:13468.0,5:13579.6,6:13103.9,7:11905.0,8:12955.8,9:13695.5,10:14507.4,11:14738.5,12:15039.9,13:15393.3,14:14367.4,15:15854.0,16:16466.4,17:16901.0,18:16933.8,19:16692.4,20:16513.8,21:15007.7,22:15527.0,23:15848.8,24:15962.8,25:16149.0,26:15802.8,27:15795.0,28:14730.4,29:15613.7,30:15843.6,31:15526.6},
    (2023,6):{1:15842.8,2:16076.2,3:16186.5,4:14872.8,5:15744.3,6:15439.5,7:16089.4,8:15848.6,9:15939.4,10:15792.1,11:14646.7,12:15591.3,13:15558.1,14:15730.4,15:16427.5,16:16859.8,17:15934.2,18:14514.1,19:13987.5,20:14464.9,21:14593.5,22:15027.2,23:15046.4,24:15404.8,25:14408.0,26:15460.5,27:15747.4,28:15750.4,29:15887.4,30:15954.1},
    (2024,4):{1:16171.2,2:16186.6,3:14773.0,4:15929.5,5:16410.4,6:16508.2,7:16559.3,8:16596.0,9:16465.8,10:15179.4,11:16273.2,12:16765.8,13:17041.1,14:17149.6,15:17281.7,16:17036.9,17:15684.5,18:16584.2,19:17040.6,20:17311.6,21:17170.0,22:17179.8,23:17089.7,24:15525.7,25:15790.4,26:16442.5,27:16961.8,28:17461.4,29:17560.7,30:17280.8},
    (2024,5):{1:17375.2,2:18451.2,3:18455.2,4:18200.5,5:16937.8,6:18033.5,7:18148.0,8:17821.9,9:17886.5,10:17417.7,11:17016.5,12:15515.9,13:16365.0,14:16405.8,15:16106.8,16:15101.6,17:14909.6,18:14868.8,19:13401.4,20:13721.2,21:14008.2,22:14091.1,23:14409.8,24:14920.3,25:14823.8,26:13085.2,27:14721.1,28:16082.2,29:16478.5,30:17184.3,31:17429.9},
    (2024,6):{1:16212.1,2:14078.7,3:14812.2,4:16045.7,5:15618.2,6:14558.6,7:13955.0,8:13589.9,9:12582.1,10:13982.5,11:15292.5,12:15273.3,13:15457.7,14:15894.2,15:15703.3,16:15008.9,17:16003.0,18:15621.8,19:15009.7,20:15450.6,21:15486.4,22:15271.4,23:13782.6,24:14729.8,25:15479.9,26:15099.0,27:15096.5,28:15431.3,29:16025.7,30:14655.4},
    (2025,4):{1:17026.7,2:17302.2,3:16189.1,4:15733.9,5:15109.6,6:14094.5,7:15262.7,8:16616.8,9:16865.7,10:17054.5,11:16418.5,12:15724.3,13:15193.3,14:15194.5,15:15933.5,16:16354.4,17:16778.7,18:16993.1,19:16995.9,20:16079.3,21:17179.2,22:17898.7,23:17915.0,24:18256.0,25:18342.7,26:18390.3,27:16746.4,28:17468.8,29:18002.6,30:17661.9},
    (2025,5):{1:16010.6,2:16683.4,3:16950.7,4:15265.3,5:15259.5,6:16630.1,7:15807.0,8:16205.5,9:16729.4,10:17026.0,11:15823.9,12:16947.9,13:17435.8,14:17623.9,15:17422.9,16:17296.9,17:15499.3,18:13779.9,19:14335.9,20:14382.0,21:14919.4,22:15672.4,23:15965.7,24:15178.9,25:13355.5,26:13544.6,27:14356.9,28:14646.8,29:15005.1,30:15036.1,31:15066.0},
    (2025,6):{1:14207.6,2:15971.0,3:17005.9,4:17049.4,5:17343.3,6:17850.1,7:16918.3,8:14896.7,9:15640.1,10:15621.0,11:15476.2,12:15197.5,13:15499.2,14:15342.5,15:14195.9,16:15423.5,17:16223.7,18:17145.3,19:17333.5,20:17787.8,21:16822.5,22:15878.3,23:15869.2,24:16389.1,25:16984.9,26:17086.7,27:17343.6,28:17496.0,29:15985.8,30:17175.0},
}

# ============ FUNCTIONS ============
@st.cache_data(ttl=60)
def gh_fetch(filename):
    try:
        url = f"{GITHUB_RAW}/{filename}"
        r = requests.get(url, timeout=10)
        return r.text if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=60)
def load_rolling_results():
    csv_text = gh_fetch("rolling_results.csv")
    return pd.read_csv(StringIO(csv_text)) if csv_text else None

@st.cache_data(ttl=60)
def load_april():
    csv_text = gh_fetch("april_2026_results.csv")
    return pd.read_csv(StringIO(csv_text)) if csv_text else None

@st.cache_data(ttl=60)
def load_may():
    csv_text = gh_fetch("may_2026_results.csv")
    return pd.read_csv(StringIO(csv_text)) if csv_text else None

@st.cache_data(ttl=60)
def load_june():
    csv_text = gh_fetch("june_2026_results.csv")
    return pd.read_csv(StringIO(csv_text)) if csv_text else None

def safe_float(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return None
    try: return float(val)
    except: return None

# ============ MAIN APP ============
def main():
    st.markdown("""
    <div style='text-align:center; padding: 20px 0;'>
        <h1>⚡ Tamil Nadu Load Forecasting</h1>
        <p style='font-size:16px; color:#666;'>Intelligent Day-Ahead Prediction using LSTM</p>
        <hr style='margin: 20px 0;'>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Rolling Forecast",
        "🏷️ Monthly Breakdown",
        "📈 5-Year Comparison",
        "📉 Daily Forecast",
        "🎯 Accuracy",
        "📋 All Results"
    ])
    
    df_roll = load_rolling_results()
    df_apr = load_april()
    df_may = load_may()
    df_jun = load_june()
    
    # TAB 1: ROLLING FORECAST
    with tab1:
        st.subheader("📊 3-Month Rolling Forecast — April, May, June 2026")
        st.caption("Day-by-day predictions with rolling LSTM model. Auto-updates every 60 seconds from GitHub.")
        
        if df_roll is None or len(df_roll) == 0:
            st.info("⏳ Rolling forecast data pending. Run Colab notebook to generate predictions.")
        else:
            df_roll['predicted_avg'] = pd.to_numeric(df_roll['predicted_avg'], errors='coerce')
            df_roll['predicted_peak'] = pd.to_numeric(df_roll['predicted_peak'], errors='coerce')
            df_roll['day'] = pd.to_numeric(df_roll['day'], errors='coerce')
            df_roll['month'] = pd.to_numeric(df_roll['month'], errors='coerce')
            
            # Combined line chart
            fig_combined = go.Figure()
            for m in [4, 5, 6]:
                df_m = df_roll[df_roll['month'] == m].sort_values('day')
                fig_combined.add_trace(go.Scatter(
                    x=df_m['day'].tolist(),
                    y=df_m['predicted_avg'].tolist(),
                    name=MONTH_NAMES[m],
                    mode='lines+markers',
                    line=dict(color=MONTH_COLORS[m], width=3),
                    fill='tozeroy',
                    fillcolor=MONTH_FILL[m],
                    marker=dict(size=6)
                ))
            fig_combined.update_layout(
                title='Rolling Forecast: Daily Average Load (3 Months)',
                xaxis_title='Day of Month',
                yaxis_title='Average Load (MW)',
                height=420,
                **BL
            )
            st.plotly_chart(fig_combined, use_container_width=True)
            
            # Bar charts per month
            col1, col2, col3 = st.columns(3)
            
            for col, month, month_num in [(col1, 'April', 4), (col2, 'May', 5), (col3, 'June', 6)]:
                with col:
                    df_m = df_roll[df_roll['month'] == month_num].sort_values('day')
                    if len(df_m) > 0:
                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(
                            x=df_m['day'].tolist(),
                            y=df_m['predicted_avg'].tolist(),
                            marker=dict(color=df_m['predicted_avg'].tolist(), colorscale='RdYlGn_r', showscale=False),
                            text=[f"{v:.0f}" for v in df_m['predicted_avg'].tolist()],
                            textposition='outside'
                        ))
                        fig_bar.update_layout(
                            title=f'{month} 2026 — Daily Avg',
                            xaxis_title='Day',
                            yaxis_title='MW',
                            height=380,
                            showlegend=False,
                            **BL
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                        st.metric('Month Avg', f"{df_m['predicted_avg'].mean():.0f} MW")
                        st.metric('Peak', f"{df_m['predicted_peak'].max():.0f} MW")
    
    # TAB 2: MONTHLY BREAKDOWN
    with tab2:
        st.subheader("🏷️ Monthly Breakdown with Day Picker")
        
        sel_month = st.selectbox('Select Month', ['April', 'May', 'June'], key='month_tab2')
        month_num = [k for k, v in MONTH_NAMES.items() if v == sel_month][0]
        
        if month_num == 4: df_month = df_apr
        elif month_num == 5: df_month = df_may
        else: df_month = df_jun
        
        if df_month is None or len(df_month) == 0:
            st.info(f"⏳ {sel_month} data pending")
        else:
            ndays = calendar.monthrange(2026, month_num)[1]
            sel_day = st.slider(f'Select day in {sel_month}', 1, ndays, 1)
            
            df_day = df_month[pd.to_numeric(df_month.get('day', 0), errors='coerce') == sel_day]
            
            if len(df_day) > 0:
                row = df_day.iloc[0]
                hours = list(range(24))
                preds = [safe_float(row.get(f'pred_h{h:02d}')) or 0 for h in hours]
                
                fig_hourly = go.Figure()
                fig_hourly.add_trace(go.Bar(
                    x=hours,
                    y=preds,
                    marker=dict(color=preds, colorscale='Viridis', showscale=True),
                    text=[f"{p:.0f}" for p in preds],
                    textposition='outside'
                ))
                fig_hourly.update_layout(
                    title=f'{sel_month} {sel_day}, 2026 — Hourly Load',
                    xaxis_title='Hour',
                    yaxis_title='Load (MW)',
                    height=400,
                    **BL
                )
                st.plotly_chart(fig_hourly, use_container_width=True)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric('Day Avg', f"{np.mean(preds):.0f} MW")
                with col2: st.metric('Day Peak', f"{np.max(preds):.0f} MW")
                with col3: st.metric('Day Min', f"{np.min(preds):.0f} MW")
                with col4: st.metric('Day Range', f"{np.max(preds) - np.min(preds):.0f} MW")
    
    # TAB 3: 5-YEAR COMPARISON
    with tab3:
        st.subheader("📈 5-Year Comparison — 2020 to 2026")
        st.caption("Historical data (2020–2025) embedded. 2026 appears after Colab execution.")
        
        sel_month_str = st.selectbox('Select Month', ['April', 'May', 'June'], key='month_tab3')
        sel_mo = [k for k, v in MONTH_NAMES.items() if v == sel_month_str][0]
        
        if sel_mo == 4: df_mo26 = df_apr
        elif sel_mo == 5: df_mo26 = df_may
        else: df_mo26 = df_jun
        
        ndays = calendar.monthrange(2026, sel_mo)[1]
        
        # Daily line chart
        fig1 = go.Figure()
        for yr in range(2020, 2027):
            dd = HIST_DAILY.get((yr, sel_mo), {})
            if dd:
                ds = sorted(dd.keys())
                av = [dd[d] for d in ds]
                fig1.add_trace(go.Scatter(
                    x=ds, y=av, name=str(yr),
                    line=dict(color=YEAR_COLORS[yr], width=2, dash='dot' if yr < 2025 else 'solid'),
                    mode='lines+markers', marker=dict(size=4), opacity=0.85
                ))
        
        if df_mo26 is not None and len(df_mo26) > 0:
            df_mo26['day'] = pd.to_numeric(df_mo26['day'], errors='coerce')
            df_mo26['predicted_avg'] = pd.to_numeric(df_mo26['predicted_avg'], errors='coerce')
            df_s = df_mo26.sort_values('day')
            fig1.add_trace(go.Scatter(
                x=df_s['day'].tolist(), y=df_s['predicted_avg'].tolist(),
                name='2026 Forecast', line=dict(color=YEAR_COLORS[2026], width=3),
                mode='lines+markers', marker=dict(size=7, symbol='diamond'),
                fill='tozeroy', fillcolor='rgba(220,38,38,0.07)'
            ))
        
        fig1.update_layout(
            title=f'{sel_month_str} — Daily Avg Load 2020–2026',
            xaxis_title=f'Day',
            yaxis_title='Avg Load (MW)',
            height=420,
            **BL
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # Bar comparison
        yls, yas, ycs = [], [], []
        for yr in range(2020, 2027):
            d = HIST_MONTHLY.get((yr, sel_mo))
            if d:
                yls.append(str(yr))
                yas.append(d['avg'])
                ycs.append(YEAR_COLORS[yr])
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=yls, y=yas, marker_color=ycs, text=[f"{v:,.0f}" for v in yas], textposition='outside'))
        fig2.update_layout(
            title=f'{sel_month_str} — Avg Load by Year',
            xaxis_title='Year',
            yaxis_title='Avg Load (MW)',
            height=380,
            **BL
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # TAB 4: DAILY FORECAST
    with tab4:
        st.subheader("📉 Daily Forecast")
        
        if df_roll is not None and len(df_roll) > 0:
            latest = df_roll.iloc[-1]
            st.metric('Latest Forecast Date', latest.get('date', 'N/A'))
            
            col1, col2, col3 = st.columns(3)
            with col1: st.metric('Day Avg', f"{safe_float(latest.get('predicted_avg', 0)):.0f} MW")
            with col2: st.metric('Day Peak', f"{safe_float(latest.get('predicted_peak', 0)):.0f} MW")
            with col3: st.metric('Day Min', f"{safe_float(latest.get('predicted_min', 0)):.0f} MW")
        else:
            st.info("⏳ Forecast data pending")
    
    # TAB 5: ACCURACY
    with tab5:
        st.subheader("🎯 Accuracy Trends")
        
        if df_roll is not None and len(df_roll) > 0:
            df_roll['mape'] = pd.to_numeric(df_roll['mape'], errors='coerce')
            df_roll['rmse'] = pd.to_numeric(df_roll['rmse'], errors='coerce')
            df_roll['day_num'] = range(1, len(df_roll) + 1)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_roll['day_num'], y=df_roll['mape'], name='MAPE (%)',
                                    line=dict(color='#f59e0b', width=2), fill='tozeroy'))
            fig.update_layout(title='MAPE Trend', xaxis_title='Day',
                            yaxis_title='MAPE (%)', height=400, **BL)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("⏳ Accuracy data pending")
    
    # TAB 6: ALL RESULTS
    with tab6:
        st.subheader("📋 All Results")
        
        if df_roll is None or len(df_roll) == 0:
            st.info("⏳ Results pending")
        else:
            cols = ['date', 'month_name', 'day', 'predicted_avg', 'predicted_peak']
            avail = [c for c in cols if c in df_roll.columns]
            ds = df_roll[avail].copy()
            
            for col in ['predicted_avg', 'predicted_peak']:
                if col in ds.columns:
                    ds[col] = pd.to_numeric(ds[col], errors='coerce').round(1)
            
            ds.columns = [c.replace('_', ' ').title() for c in ds.columns]
            st.dataframe(ds, use_container_width=True, height=500)
            
            csv = df_roll.to_csv(index=False)
            st.download_button('⬇ Download CSV', csv.encode(), 'TN_rolling_results.csv', 'text/csv', use_container_width=True)

if __name__ == "__main__":
    main()
