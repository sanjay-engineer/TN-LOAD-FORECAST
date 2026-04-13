# ================================================================
#  TN LOAD FORECASTING — STREAMLIT APP (COMPLETE FINAL)
#
#  KEY FIX: Historical data (2020-2025) is EMBEDDED in this file.
#  5-Year comparison charts show IMMEDIATELY on first open.
#  No Colab needed for historical charts to work.
#
#  Forecast charts appear after running TN_3MONTH_FORECAST_V2.py
#
#  TABS:
#  1. Daily Forecast  — today vs actual + tomorrow hourly
#  2. Monthly Forecast— bar+line combined + each month separate
#                       with day picker (bar+line per day)
#  3. 5-Year Compare  — all 3 months vs 2020-2025 (always works)
#  4. Accuracy        — MAPE/RMSE trends
#  5. All Results     — full table + download
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import hashlib, json, os, requests, calendar
from datetime import datetime
from io import StringIO

st.set_page_config(page_title="TN Load Forecasting", page_icon="⚡", layout="wide")

GITHUB_USER  = "sanjay-engineer"
GITHUB_REPO  = "TN-LOAD-FORECAST"
GITHUB_RAW   = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/results"
USERS_FILE   = "users.json"
SHARED_DIR   = "shared_results"
os.makedirs(SHARED_DIR, exist_ok=True)

MONTH_NAMES  = {4:"April", 5:"May", 6:"June"}
MONTH_COLORS = {4:"#2563eb", 5:"#16a34a", 6:"#ea580c"}
MONTH_FILL   = {4:"rgba(37,99,235,0.10)", 5:"rgba(22,163,74,0.10)", 6:"rgba(234,88,12,0.10)"}
YEAR_COLORS  = {2020:"#94a3b8",2021:"#64748b",2022:"#f59e0b",2023:"#8b5cf6",2024:"#ec4899",2025:"#6366f1",2026:"#dc2626"}

# ── EMBEDDED HISTORICAL DATA (2020-2025) ──────────────────────
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

HIST_HOURLY = {
    (2020,4):{0:9867.1,1:9636.1,2:9479.9,3:9357.6,4:9273.7,5:9445.0,6:9692.5,7:9976.4,8:10023.8,9:9923.6,10:9847.6,11:9660.3,12:9617.9,13:9607.8,14:9628.4,15:9775.4,16:9859.2,17:10061.4,18:10248.2,19:10359.6,20:10251.2,21:10366.5,22:10485.6,23:10200.3},
    (2020,5):{0:11790.8,1:11536.3,2:11312.1,3:11164.5,4:11122.7,5:11212.3,6:11389.6,7:11692.7,8:11854.2,9:11931.2,10:12001.7,11:11958.5,12:11974.3,13:11972.1,14:12132.4,15:12390.2,16:12369.1,17:12168.8,18:12033.1,19:12114.6,20:12019.1,21:12383.1,22:12523.8,23:12177.9},
    (2020,6):{0:12287.0,1:11993.8,2:11705.9,3:11511.4,4:11520.9,5:11622.5,6:11955.8,7:12321.7,8:12453.9,9:12404.9,10:12377.6,11:12313.4,12:12367.8,13:12377.6,14:12604.4,15:12796.6,16:12821.6,17:12736.8,18:12717.0,19:12888.9,20:12668.2,21:12936.7,22:13032.3,23:12640.9},
    (2021,4):{0:13948.1,1:13578.8,2:13313.9,3:13093.2,4:13043.5,5:13269.4,6:13823.5,7:14450.0,8:14805.1,9:15111.2,10:15369.6,11:15408.4,12:15367.5,13:15084.6,14:15103.1,15:15201.2,16:15058.6,17:14882.3,18:14940.8,19:15067.1,20:14769.1,21:14846.2,22:14983.3,23:14546.9},
    (2021,5):{0:12205.6,1:11853.6,2:11609.6,3:11382.2,4:11324.8,5:11528.9,6:12018.0,7:12500.5,8:12812.8,9:13024.5,10:13045.9,11:13026.5,12:12982.4,13:12846.4,14:12912.0,15:12979.5,16:12857.8,17:12726.4,18:12716.1,19:12874.0,20:12667.2,21:12886.1,22:13028.4,23:12619.0},
    (2021,6):{0:12392.3,1:12049.8,2:11757.5,3:11577.0,4:11580.7,5:11835.1,6:12369.1,7:12821.2,8:13092.5,9:13230.5,10:13182.8,11:13168.4,12:13131.0,13:13064.1,14:13314.7,15:13478.8,16:13403.9,17:13204.6,18:13195.1,19:13202.5,20:13098.5,21:13385.8,22:13340.1,23:12834.6},
    (2022,4):{0:14088.1,1:13812.9,2:13559.4,3:13317.6,4:13136.8,5:13180.3,6:13829.4,7:14627.4,8:14750.8,9:15208.4,10:15784.4,11:15847.5,12:15769.1,13:15671.0,14:15675.8,15:15390.6,16:15208.8,17:15108.7,18:15174.0,19:15246.6,20:15050.9,21:15030.0,22:14968.9,23:14598.7},
    (2022,5):{0:13540.9,1:13125.8,2:12807.9,3:12605.5,4:12457.2,5:12501.7,6:13025.0,7:13716.8,8:13778.4,9:14125.0,10:14414.6,11:14557.2,12:14608.1,13:14333.9,14:14394.8,15:14693.6,16:14693.1,17:14637.7,18:14524.3,19:14468.5,20:14158.1,21:14159.5,22:14241.9,23:13976.1},
    (2022,6):{0:14070.6,1:13632.5,2:13305.1,3:13048.8,4:12923.0,5:13043.3,6:13701.8,7:14407.9,8:14440.5,9:14498.3,10:14630.9,11:14727.4,12:14532.4,13:14498.6,14:14661.1,15:15088.8,16:15277.9,17:15340.1,18:15261.0,19:15392.6,20:15016.1,21:15106.0,22:15070.1,23:14610.2},
    (2023,4):{0:15293.0,1:14841.7,2:14537.5,3:14317.8,4:14279.6,5:14430.3,6:14873.2,7:15562.5,8:15959.8,9:16806.0,10:17173.7,11:17145.5,12:17163.7,13:16790.7,14:16862.8,15:16920.3,16:16705.6,17:16528.2,18:16539.2,19:16548.6,20:16202.1,21:16242.6,22:16289.2,23:15831.0},
    (2023,5):{0:14312.0,1:13881.0,2:13591.5,3:13355.8,4:13265.3,5:13436.5,6:13866.5,7:14306.3,8:14641.5,9:15267.4,10:15700.2,11:15821.5,12:15836.4,13:15601.5,14:15779.9,15:15853.7,16:15705.0,17:15532.0,18:15550.1,19:15616.9,20:15339.8,21:15422.2,22:15484.3,23:14981.6},
    (2023,6):{0:14753.0,1:14313.0,2:14085.3,3:13825.1,4:13713.4,5:13918.0,6:14536.0,7:15027.0,8:15163.7,9:15763.0,10:16243.4,11:16374.5,12:16329.2,13:16102.0,14:16328.8,15:16528.3,16:16548.1,17:16385.7,18:16245.8,19:16296.1,20:15917.7,21:15963.5,22:16010.6,23:15489.3},
    (2024,4):{0:15648.5,1:15216.0,2:14954.7,3:14756.5,4:14761.3,5:14908.8,6:15229.3,7:16333.2,8:16652.9,9:17615.8,10:18086.8,11:18092.5,12:17891.4,13:17416.0,14:17441.7,15:17746.1,16:17672.1,17:17241.9,18:17165.1,19:17090.8,20:16596.6,21:16492.6,22:16556.0,23:16362.7},
    (2024,5):{0:16095.2,1:15530.4,2:15128.6,3:14770.3,4:14539.6,5:14559.7,6:14625.7,7:15098.5,8:15252.6,9:16024.2,10:16717.9,11:16744.1,12:16776.6,13:16700.0,14:16629.2,15:17127.5,16:17218.0,17:16831.7,18:16565.7,19:16879.2,20:16581.2,21:16609.1,22:16910.6,23:16696.7},
    (2024,6):{0:14825.1,1:14333.2,2:13932.5,3:13639.4,4:13467.0,5:13520.1,6:13788.2,7:14654.2,8:14669.8,9:14922.9,10:15351.2,11:15456.9,12:15603.9,13:15581.8,14:15408.3,15:15863.2,16:16031.5,17:15889.1,18:15634.7,19:15988.5,20:15620.7,21:15513.8,22:15813.1,23:15457.4},
    (2025,4):{0:16312.9,1:15778.3,2:15378.6,3:15087.0,4:14933.8,5:15066.9,6:15258.0,7:16125.2,8:16378.7,9:16778.9,10:17235.6,11:17292.9,12:17283.7,13:17035.2,14:16738.5,15:17512.5,16:17976.3,17:17998.6,18:17584.8,19:17716.2,20:17219.3,21:17209.4,22:17511.2,23:17214.1},
    (2025,5):{0:15474.8,1:14929.6,2:14499.9,3:14189.7,4:13983.7,5:14023.2,6:14246.6,7:14951.2,8:15117.1,9:15839.9,10:16107.6,11:16159.2,12:16205.4,13:16015.4,14:15985.5,15:16627.2,16:16831.1,17:16748.0,18:16466.6,19:16751.7,20:16222.7,21:16187.8,22:16452.5,23:16136.2},
    (2025,6):{0:16121.6,1:15559.8,2:15165.9,3:14797.1,4:14682.4,5:14799.4,6:15155.4,7:16164.8,8:15969.0,9:16175.4,10:16341.7,11:16489.5,12:16398.6,13:16212.3,14:16257.7,15:16963.7,16:17360.4,17:17455.0,18:17171.7,19:17567.8,20:17111.5,21:17066.8,22:17357.6,23:16982.8},
}

# ── USER SYSTEM ───────────────────────────────────────────────
def _hp(p): return hashlib.sha256(p.encode()).hexdigest()
def _lu(): return json.load(open(USERS_FILE)) if os.path.exists(USERS_FILE) else {}
def _su(u): json.dump(u,open(USERS_FILE,"w"),indent=2)

def register(un,pw):
    if len(un)<3: return False,"Min 3 chars"
    if len(un)>20: return False,"Max 20 chars"
    if not un.replace("_","").isalnum(): return False,"Letters/numbers/underscore"
    if len(pw)<6: return False,"Password min 6 chars"
    u=_lu()
    if un.lower() in [k.lower() for k in u]: return False,"Username taken"
    u[un]={"password":_hp(pw),"role":"viewer","created":str(datetime.now().date()),"last_login":None}
    _su(u); return True,"Account created"

def login(un,pw):
    u=_lu()
    m=next((k for k in u if k.lower()==un.lower()),None)
    if not m: return False,"Username not found",None
    if u[m]["password"]!=_hp(pw): return False,"Wrong password",None
    u[m]["last_login"]=str(datetime.now()); _su(u)
    return True,m,u[m].get("role","viewer")

def set_admin(un,secret):
    if secret!="TN2025Admin": return False,"Wrong key"
    u=_lu()
    m=next((k for k in u if k.lower()==un.lower()),None)
    if not m: return False,f"User '{un}' not found"
    u[m]["role"]="admin"; _su(u); return True,f"'{m}' is now Admin"

# ── DATA LOADING ──────────────────────────────────────────────
@st.cache_data(ttl=60)
def gh_fetch(fn):
    try:
        r=requests.get(f"{GITHUB_RAW}/{fn}",timeout=10)
        return r.text if r.status_code==200 else None
    except: return None

@st.cache_data(ttl=60)
def gh_ok():
    try:
        r=requests.head(f"{GITHUB_RAW}/rolling_results.csv",timeout=5)
        return r.status_code==200
    except: return False

def read_csv(fn):
    d=gh_fetch(fn)
    if d:
        try:
            df=pd.read_csv(StringIO(d))
            if len(df)>0: return df
        except: pass
    loc=os.path.join(SHARED_DIR,fn)
    if os.path.exists(loc):
        df=pd.read_csv(loc)
        if len(df)>0: return df
    return None

def load_rolling(): return read_csv("rolling_results.csv")
def load_mo(mo): return read_csv(f"{MONTH_NAMES[mo].lower()}_2026_results.csv")
def sf(v):
    try: x=float(v); return None if np.isnan(x) else x
    except: return None
def g24(row,pfx): return [sf(row.get(f"{pfx}_h{h:02d}")) for h in range(24)]
def save_local(uf,fn):
    df=pd.read_csv(uf); df.to_csv(os.path.join(SHARED_DIR,fn),index=False); return len(df)

BL=dict(plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",hovermode="x unified",yaxis=dict(tickformat=","),legend=dict(orientation="h",yanchor="bottom",y=1.02))

# ── LOGIN ─────────────────────────────────────────────────────
def show_login():
    st.markdown("<div style='text-align:center;padding:30px 0 10px 0'><div style='font-size:48px'>⚡</div><h2 style='color:#2563eb;margin:6px 0'>TN Intelligent Load Forecasting</h2><p style='color:#64748b;font-size:13px'>Tamil Nadu Power Grid — LSTM Forecast System</p></div>",unsafe_allow_html=True)
    st.divider()
    t1,t2,t3=st.tabs(["🔑 Login","📝 Register","🔧 Admin Setup"])
    with t1:
        with st.form("lf"):
            u=st.text_input("Username"); p=st.text_input("Password",type="password")
            s=st.form_submit_button("Login",use_container_width=True,type="primary")
        if s:
            if not u or not p: st.error("Enter both")
            else:
                ok,res,role=login(u,p)
                if ok: st.session_state.update(logged_in=True,username=res,role=role); st.rerun()
                else: st.error(f"❌ {res}")
    with t2:
        with st.form("rf"):
            nu=st.text_input("Username",placeholder="3-20 chars"); np_=st.text_input("Password",type="password"); cp=st.text_input("Confirm Password",type="password")
            rb=st.form_submit_button("Create Account",use_container_width=True,type="primary")
        if rb:
            if not nu or not np_ or not cp: st.error("Fill all fields")
            elif np_!=cp: st.error("Passwords don't match")
            else:
                ok,msg=register(nu,np_); (st.success if ok else st.error)(msg)
    with t3:
        st.info("Register first. Secret key: **TN2025Admin**")
        with st.form("af"):
            au=st.text_input("Your Username"); ak=st.text_input("Admin Key",type="password")
            if st.form_submit_button("Make Admin",use_container_width=True):
                ok,msg=set_admin(au,ak); (st.success if ok else st.error)(msg)
    st.divider()
    #st.success("GitHub connected")
    if gh_ok():
        st.success("GitHub connected")
    else:
        st.warning("GitHub offline — use sidebar upload after login")
# ── SIDEBAR ───────────────────────────────────────────────────
def show_sidebar(un,role):
    with st.sidebar:
        bg="#7c3aed" if role=="admin" else "#2563eb"
        st.markdown(f"<div style='background:{bg};color:white;padding:10px 14px;border-radius:8px;margin-bottom:8px'><b>👤 {un}</b><br><span style='font-size:12px;opacity:.85'>{'Admin ✓' if role=='admin' else 'Viewer'}</span></div>",unsafe_allow_html=True)
        st.divider()
        st.subheader("🔗 Data Source")
        if gh_ok():
            st.success("GitHub — Auto sync")
            if st.button("🔄 Refresh",use_container_width=True): st.cache_data.clear(); st.rerun()
        else:
            st.warning("⚠ GitHub offline")
        if role=="admin":
            st.divider()
            with st.expander("📂 Manual Upload"):
                for fn,k in [("rolling_results.csv","ru"),("april_2026_results.csv","a26"),("may_2026_results.csv","m26"),("june_2026_results.csv","j26")]:
                    uf=st.file_uploader(fn,type=["csv"],key=k)
                    if uf: n=save_local(uf,fn); st.success(f"✓ {fn} ({n} rows)")
        st.divider()
        if st.button("🚪 Logout",use_container_width=True):
            st.session_state.update(logged_in=False,username=None,role=None); st.rerun()

# ── DASHBOARD ─────────────────────────────────────────────────
def show_dashboard(un,role):
    st.markdown(f"<h2 style='color:#2563eb'>⚡ TN Load Forecasting Dashboard</h2><p style='color:#64748b'>Tamil Nadu Power Grid · Welcome <b>{un}</b></p>",unsafe_allow_html=True)
    st.divider()
    df_roll=load_rolling()
    hlbl=[f"{h:02d}:00" for h in range(24)]
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("📅 Data Years","2020–2025"); c2.metric("📊 History Rows","54,768"); c3.metric("🔮 Target","Apr·May·Jun 2026")
    if df_roll is not None and len(df_roll)>0:
        df_roll['ha']=df_roll['actual_h00'].apply(lambda x:pd.notna(x) and str(x).strip() not in ['','nan','None'])
        df_past=df_roll[df_roll['ha']].copy(); df_future=df_roll[~df_roll['ha']].copy()
        df_m=df_past[df_past['mape'].notna()].copy() if 'mape' in df_past.columns else pd.DataFrame()
        c4.metric("✅ Forecast Days",len(df_roll))
        if len(df_m)>0: c5.metric("🎯 Avg MAPE",f"{df_m['mape'].mean():.2f}%")
        else: c5.metric("🎯 MAPE","—")
    else:
        df_past=df_future=df_m=pd.DataFrame()
        c4.metric("✅ Forecast Days","Run Colab"); c5.metric("🎯 MAPE","—")
    if df_roll is None or len(df_roll)==0:
        st.info("**5-Year Comparison tab works now.** Run Colab to see forecast tabs (Monthly Forecast, Daily).")
    st.divider()

    tab1,tab2,tab3,tab4,tab5=st.tabs(["📈 Daily Forecast","📅 Monthly Forecast","📊 5-Year Comparison","🎯 Accuracy","📋 All Results"])

    # TAB 1 — DAILY
    with tab1:
        st.subheader("📊 Today — Predicted vs Actual")
        if len(df_past)==0: st.info("No actual data. Run Colab first.")
        else:
            row=df_past.iloc[-1]; pred=g24(row,'pred'); actual=g24(row,'actual')
            mv=sf(row.get('mape')); rv=sf(row.get('rmse')); vp=[v for v in pred if v]
            m1,m2,m3,m4=st.columns(4)
            if mv:
                col="green" if mv<5 else "orange" if mv<10 else "red"
                m1.markdown(f"<h3 style='color:{col}'>{mv:.2f}%</h3><p style='color:#64748b;font-size:12px'>MAPE</p>",unsafe_allow_html=True)
            if rv: m2.markdown(f"<h3>{rv:.0f} MW</h3><p style='color:#64748b;font-size:12px'>RMSE</p>",unsafe_allow_html=True)
            if vp: m3.markdown(f"<h3 style='color:#2563eb'>{max(vp):,.0f} MW</h3><p style='color:#64748b;font-size:12px'>Peak</p>",unsafe_allow_html=True)
            m4.markdown(f"<h3>{row['date']}</h3><p style='color:#64748b;font-size:12px'>Date</p>",unsafe_allow_html=True)
            ft=go.Figure()
            if any(v for v in actual): ft.add_trace(go.Scatter(x=hlbl,y=actual,name="Actual",line=dict(color="#16a34a",width=3),mode="lines+markers",marker=dict(size=7),fill="tozeroy",fillcolor="rgba(22,163,74,0.07)"))
            ft.add_trace(go.Scatter(x=hlbl,y=pred,name="Predicted",line=dict(color="#2563eb",width=2.5,dash="dash"),mode="lines+markers",marker=dict(size=6)))
            ft.update_layout(title=f"Predicted vs Actual — {row['date']}",xaxis_title="Hour",yaxis_title="Load (MW)",height=380,**BL)
            st.plotly_chart(ft,use_container_width=True)
        st.divider()
        st.subheader("🔮 Tomorrow — Next Day Forecast")
        if len(df_future)==0: st.info("No forecast data yet.")
        else:
            nr=df_future.iloc[0]; np_=g24(nr,'pred'); vnp=[v for v in np_ if v]
            n1,n2,n3,n4=st.columns(4)
            if vnp:
                n1.markdown(f"<h3 style='color:#ea580c'>{max(vnp):,.0f} MW</h3><p style='color:#64748b;font-size:12px'>Peak</p>",unsafe_allow_html=True)
                n2.markdown(f"<h3>{min(vnp):,.0f} MW</h3><p style='color:#64748b;font-size:12px'>Min</p>",unsafe_allow_html=True)
                n3.markdown(f"<h3>{np.mean(vnp):,.0f} MW</h3><p style='color:#64748b;font-size:12px'>Average</p>",unsafe_allow_html=True)
            n4.markdown(f"<h3 style='color:#7c3aed'>{nr['date']}</h3><p style='color:#64748b;font-size:12px'>Date</p>",unsafe_allow_html=True)
            fn2=go.Figure()
            fn2.add_trace(go.Scatter(x=hlbl,y=np_,name="Forecast",line=dict(color="#ea580c",width=3),mode="lines+markers",marker=dict(size=8,symbol="diamond"),fill="tozeroy",fillcolor="rgba(234,88,12,0.07)"))
            if vnp:
                ph=np_.index(max(vnp))
                fn2.add_annotation(x=hlbl[ph],y=max(vnp),text=f"Peak:{max(vnp):,.0f} MW",showarrow=True,arrowhead=2,arrowcolor="#ea580c",font=dict(color="#ea580c",size=11),bgcolor="white",bordercolor="#ea580c",borderwidth=1.5,ay=-40)
            fn2.update_layout(title=f"Tomorrow — {nr['date']}",xaxis_title="Hour",yaxis_title="Load (MW)",height=380,**BL)
            st.plotly_chart(fn2,use_container_width=True)

    # TAB 2 — MONTHLY FORECAST
    with tab2:
        st.subheader("📅 Monthly Forecast — April · May · June 2026")
        mo_data={}
        for mo in [4,5,6]:
            df_mo=load_mo(mo)
            if df_mo is not None and len(df_mo)>0:
                df_mo['day']=pd.to_numeric(df_mo['day'],errors='coerce')
                df_mo=df_mo.dropna(subset=['day']).sort_values('day')
                df_mo['day']=df_mo['day'].astype(int)
                mo_data[mo]=df_mo
        if not mo_data:
            st.info("**Forecast data not yet available.** Run TN_3MONTH_FORECAST_V2.py in Colab.\n\nWhile waiting, check the **5-Year Comparison** tab — it works now.")
        else:
            # Combined bar + line
            st.markdown("### Combined 3-Month View")
            cb,cl=st.columns(2)
            with cb:
                fc=go.Figure(); xoff=0
                for mo,df_mo in mo_data.items():
                    xs=[xoff+d for d in df_mo['day']]; avgs=pd.to_numeric(df_mo['predicted_avg'],errors='coerce').tolist()
                    fc.add_trace(go.Bar(x=xs,y=avgs,name=MONTH_NAMES[mo],marker_color=MONTH_COLORS[mo],opacity=0.85,width=0.8))
                    if xoff>0: fc.add_vline(x=xoff+0.5,line_dash="dash",line_color="gray",opacity=0.4)
                    xoff+=calendar.monthrange(2026,mo)[1]
                fc.update_layout(title="Apr+May+Jun 2026 — Daily Avg (Bar)",xaxis_title="Day",yaxis_title="Avg Load (MW)",height=360,**BL)
                st.plotly_chart(fc,use_container_width=True)
            with cl:
                fl=go.Figure(); xoff=0
                for mo,df_mo in mo_data.items():
                    xs=[xoff+d for d in df_mo['day']]; avgs=pd.to_numeric(df_mo['predicted_avg'],errors='coerce').tolist()
                    fl.add_trace(go.Scatter(x=xs,y=avgs,name=MONTH_NAMES[mo],line=dict(color=MONTH_COLORS[mo],width=2.5),mode="lines+markers",marker=dict(size=4),fill="tozeroy",fillcolor=MONTH_FILL[mo]))
                    if xoff>0: fl.add_vline(x=xoff+0.5,line_dash="dash",line_color="gray",opacity=0.4)
                    xoff+=calendar.monthrange(2026,mo)[1]
                fl.update_layout(title="Apr+May+Jun 2026 — Daily Trend (Line)",xaxis_title="Day (Apr→Jun)",yaxis_title="Avg Load (MW)",height=360,**BL)
                st.plotly_chart(fl,use_container_width=True)
            st.divider()
            # Each month separately
            for mo in [4,5,6]:
                if mo not in mo_data: continue
                mn=MONTH_NAMES[mo]; color=MONTH_COLORS[mo]; fill=MONTH_FILL[mo]
                df_mo=mo_data[mo]; ndays=int(df_mo['day'].max())
                days=df_mo['day'].tolist()
                avgs=pd.to_numeric(df_mo['predicted_avg'],errors='coerce').tolist()
                peaks=pd.to_numeric(df_mo['predicted_peak'],errors='coerce').tolist()
                prev_avgs=[HIST_DAILY.get((2025,mo),{}).get(d) for d in days]
                st.markdown(f"<div style='background:{color};color:white;padding:10px 18px;border-radius:8px;margin:18px 0 10px 0'><b>📅 {mn} 2026</b> — {ndays} days &nbsp;|&nbsp; Avg: {np.nanmean([v for v in avgs if v]):,.0f} MW &nbsp;|&nbsp; Peak: {np.nanmax([v for v in peaks if v]):,.0f} MW</div>",unsafe_allow_html=True)
                m1,m2,m3=st.columns(3)
                m1.metric("Monthly Avg",f"{np.nanmean([v for v in avgs if v]):,.0f} MW")
                m2.metric("Monthly Peak",f"{np.nanmax([v for v in peaks if v]):,.0f} MW")
                peak_day=days[([v for v in peaks]).index(max(v for v in peaks if v))]
                m3.metric("Peak Day",f"{mn} {peak_day}")
                # Bar chart
                bc,lc=st.columns(2)
                with bc:
                    fb=go.Figure()
                    fb.add_trace(go.Bar(x=days,y=avgs,name=f"{mn} 2026",marker_color=color,opacity=0.85,text=[f"{v:,.0f}" if v else "" for v in avgs],textposition='outside'))
                    fb.add_trace(go.Bar(x=days,y=prev_avgs,name=f"{mn} 2025",marker_color=YEAR_COLORS[2025],opacity=0.5))
                    fb.add_trace(go.Scatter(x=days,y=peaks,name="2026 Peak",mode="lines+markers",line=dict(color="#dc2626",width=2,dash="dot"),marker=dict(size=5,color="#dc2626")))
                    fb.update_layout(title=f"{mn} 2026 vs 2025 (Bar)",xaxis_title=f"Day",yaxis_title="Load (MW)",xaxis=dict(tickmode='linear',tick0=1,dtick=1),barmode='group',height=360,**BL)
                    st.plotly_chart(fb,use_container_width=True)
                with lc:
                    fl2=go.Figure()
                    fl2.add_trace(go.Scatter(x=days,y=avgs,name=f"{mn} 2026 Forecast",line=dict(color=color,width=2.5),mode="lines+markers",marker=dict(size=5),fill="tozeroy",fillcolor=fill))
                    fl2.add_trace(go.Scatter(x=days,y=prev_avgs,name=f"{mn} 2025 Actual",line=dict(color=YEAR_COLORS[2025],width=1.8,dash="dash"),mode="lines+markers",marker=dict(size=4)))
                    fl2.add_trace(go.Scatter(x=days,y=peaks,name="2026 Peak",line=dict(color="#dc2626",width=1.5,dash="dot"),mode="lines"))
                    fl2.update_layout(title=f"{mn} 2026 vs 2025 (Line)",xaxis_title=f"Day",yaxis_title="Load (MW)",xaxis=dict(tickmode='linear',tick0=1,dtick=1),height=360,**BL)
                    st.plotly_chart(fl2,use_container_width=True)
                # Day picker
                st.markdown(f"**🔍 View a specific day in {mn} 2026**")
                sel=st.slider(f"Select day — {mn}",1,ndays,1,key=f"sl_{mo}")
                drow=df_mo[df_mo['day']==sel]
                if len(drow)>0:
                    dr=drow.iloc[0]; dp=g24(dr,'pred'); dp=[v if v else 0 for v in dp]; vdp=[v for v in dp if v]
                    d1,d2,d3=st.columns(3)
                    if vdp:
                        d1.metric("Avg Load",f"{np.mean(vdp):,.0f} MW"); d2.metric("Peak Load",f"{max(vdp):,.0f} MW"); d3.metric("Peak Hour",f"{dp.index(max(vdp)):02d}:00")
                    db2,dl2=st.columns(2)
                    with db2:
                        fdb=go.Figure(); fdb.add_trace(go.Bar(x=hlbl,y=dp,name="Hourly Load",marker_color=color,opacity=0.85))
                        fdb.update_layout(title=f"{mn} {sel} — Hourly (Bar)",xaxis_title="Hour",yaxis_title="Load (MW)",height=280,**BL)
                        st.plotly_chart(fdb,use_container_width=True)
                    with dl2:
                        fdl=go.Figure(); fdl.add_trace(go.Scatter(x=hlbl,y=dp,name="Hourly Load",line=dict(color=color,width=2.5),mode="lines+markers",marker=dict(size=7,symbol="diamond"),fill="tozeroy",fillcolor=fill))
                        if vdp:
                            ph=dp.index(max(vdp)); fdl.add_annotation(x=hlbl[ph],y=max(vdp),text=f"Peak:{max(vdp):,.0f}",showarrow=True,arrowhead=2,font=dict(color=color,size=10),bgcolor="white",bordercolor=color,borderwidth=1,ay=-35)
                        fdl.update_layout(title=f"{mn} {sel} — Hourly (Line)",xaxis_title="Hour",yaxis_title="Load (MW)",height=280,**BL)
                        st.plotly_chart(fdl,use_container_width=True)
                st.divider()

    # TAB 3 — 5-YEAR COMPARISON (always works — data embedded)
    with tab3:
        st.subheader("📊 5-Year Comparison — 2020 to 2026")
        st.caption("Historical data (2020–2025) embedded in app — charts always visible. 2026 forecast appears after running Colab.")
        sel_mn=st.selectbox("Select Month",["April","May","June"],key="s5")
        sel_mo=[k for k,v in MONTH_NAMES.items() if v==sel_mn][0]
        color=MONTH_COLORS[sel_mo]; ndays=calendar.monthrange(2026,sel_mo)[1]; df_mo26=load_mo(sel_mo)
        # Chart 1: Daily line all years
        fig1=go.Figure()
        for yr in range(2020,2026):
            dd=HIST_DAILY.get((yr,sel_mo),{})
            if not dd: continue
            ds=sorted(dd.keys()); av=[dd[d] for d in ds]
            fig1.add_trace(go.Scatter(x=ds,y=av,name=str(yr),line=dict(color=YEAR_COLORS[yr],width=1.8,dash='dot' if yr<2023 else 'solid'),mode='lines+markers',marker=dict(size=4),opacity=0.85))
        if df_mo26 is not None and len(df_mo26)>0:
            df_s=df_mo26.sort_values('day')
            fig1.add_trace(go.Scatter(x=df_s['day'].tolist(),y=pd.to_numeric(df_s['predicted_avg'],errors='coerce').tolist(),name='2026 Forecast',line=dict(color=YEAR_COLORS[2026],width=3),mode='lines+markers',marker=dict(size=7,symbol='diamond'),fill='tozeroy',fillcolor='rgba(220,38,38,0.07)'))
        else:
            fig1.add_annotation(x=ndays//2,y=0,yref="paper",text="<b>2026 forecast — run Colab to see</b>",showarrow=False,font=dict(size=12,color="#dc2626"),bgcolor="rgba(255,255,255,0.8)",bordercolor="#dc2626",borderwidth=1)
        fig1.update_layout(title=f"{sel_mn} — Daily Avg Load 2020–2026 (Line)",xaxis_title=f"Day of {sel_mn}",yaxis_title="Avg Load (MW)",xaxis=dict(tickmode='linear',tick0=1,dtick=1,range=[0,ndays+1]),height=420,**BL)
        st.plotly_chart(fig1,use_container_width=True)
        # Chart 2: Monthly avg bar per year
        yls,yas,yps,ycs=[],[],[],[]
        for yr in range(2020,2026):
            d=HIST_MONTHLY.get((yr,sel_mo));
            if not d: continue
            yls.append(str(yr)); yas.append(d['avg']); yps.append(d['peak']); ycs.append(YEAR_COLORS[yr])
        if df_mo26 is not None and len(df_mo26)>0:
            yls.append("2026\n(Forecast)"); yas.append(float(pd.to_numeric(df_mo26['predicted_avg'],errors='coerce').mean())); yps.append(float(pd.to_numeric(df_mo26['predicted_peak'],errors='coerce').max())); ycs.append(YEAR_COLORS[2026])
        else:
            yls.append("2026\n(Pending)"); yas.append(None); yps.append(None); ycs.append('#e5e7eb')
        fig2=go.Figure()
        fig2.add_trace(go.Bar(x=yls,y=yas,name="Monthly Avg",marker_color=ycs,opacity=0.88,text=[f"{v:,.0f}" if v else "Run Colab" for v in yas],textposition='outside'))
        fig2.add_trace(go.Scatter(x=yls,y=yps,name="Monthly Peak",mode='lines+markers',line=dict(color='#dc2626',width=2,dash='dot'),marker=dict(size=9,symbol='triangle-up',color='#dc2626')))
        fig2.update_layout(title=f"{sel_mn} — Monthly Avg & Peak by Year (Bar)",xaxis_title="Year",yaxis_title="Load (MW)",height=380,**BL)
        st.plotly_chart(fig2,use_container_width=True)
        # Chart 3: Hourly profile all years
        fig3=go.Figure()
        for yr in range(2020,2026):
            hd=HIST_HOURLY.get((yr,sel_mo),{})
            if not hd: continue
            hs=sorted(hd.keys()); hv=[hd[h] for h in hs]
            fig3.add_trace(go.Scatter(x=hs,y=hv,name=str(yr),line=dict(color=YEAR_COLORS[yr],width=1.8,dash='dot' if yr<2023 else 'solid'),mode='lines',opacity=0.88))
        if df_mo26 is not None and len(df_mo26)>0:
            h26=[np.nanmean([sf(r.get(f'pred_h{h:02d}')) for r in df_mo26.to_dict('records') if sf(r.get(f'pred_h{h:02d}')) is not None]) for h in range(24)]
            if any(v for v in h26): fig3.add_trace(go.Scatter(x=list(range(24)),y=h26,name='2026 Forecast',line=dict(color=YEAR_COLORS[2026],width=3),mode='lines+markers',marker=dict(size=6,symbol='diamond')))
        fig3.update_layout(title=f"{sel_mn} — Avg Hourly Profile by Year",xaxis_title="Hour",yaxis_title="Avg Load (MW)",xaxis=dict(tickmode='array',tickvals=list(range(24)),ticktext=[f"{h:02d}:00" for h in range(24)]),height=380,**BL)
        st.plotly_chart(fig3,use_container_width=True)
        # Growth table
        st.subheader(f"{sel_mn} — Year-on-Year Growth Table")
        rows=[]
        for i,(yr,av) in enumerate(zip([int(l.split('\n')[0].split('(')[0].strip()) for l in yls],yas)):
            pk=yps[i]; yoy=(f"{(av-yas[i-1])/yas[i-1]*100:+.1f}%" if i>0 and av and yas[i-1] else "—")
            rows.append({"Year":yls[i].replace('\n',' '),"Avg Load (MW)":f"{av:,.0f}" if av else "—","Peak Load (MW)":f"{pk:,.0f}" if pk else "—","YoY Growth":yoy})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    # TAB 4 — ACCURACY
    with tab4:
        if len(df_m)==0: st.info("Accuracy data appears after running Colab with actual daily files.")
        else:
            c1,c2=st.columns(2)
            with c1:
                fm=px.line(df_m,x="date",y="mape",title="MAPE % Over Days",markers=True,color_discrete_sequence=["#ea580c"])
                fm.add_hline(y=df_m['mape'].mean(),line_dash="dash",line_color="red",annotation_text=f"Avg:{df_m['mape'].mean():.2f}%")
                fm.update_layout(height=300,plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fm,use_container_width=True)
            with c2:
                fr=px.line(df_m,x="date",y="rmse",title="RMSE (MW) Over Days",markers=True,color_discrete_sequence=["#7c3aed"])
                fr.add_hline(y=df_m['rmse'].mean(),line_dash="dash",line_color="red",annotation_text=f"Avg:{df_m['rmse'].mean():.0f} MW")
                fr.update_layout(height=300,plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fr,use_container_width=True)

    # TAB 5 — ALL RESULTS
    with tab5:
        if df_roll is None or len(df_roll)==0: st.info("Results appear after running Colab.")
        else:
            st.subheader(f"All Results — {len(df_roll)} rows")
            cols=['date','month_name','day','mape','rmse','predicted_avg','predicted_peak','actual_avg','actual_peak']
            avail=[c for c in cols if c in df_roll.columns]; ds=df_roll[avail].copy()
            for col in ['mape','rmse','predicted_avg','predicted_peak','actual_avg','actual_peak']:
                if col in ds.columns: ds[col]=pd.to_numeric(ds[col],errors='coerce').round(1)
            ds.columns=[c.replace('_',' ').title() for c in ds.columns]
            st.dataframe(ds,use_container_width=True,hide_index=True,height=460)
            st.download_button("⬇ Download Results CSV",df_roll.to_csv(index=False).encode(),"TN_results.csv","text/csv",use_container_width=True)

def main():
    for k in ['logged_in','username','role']:
        if k not in st.session_state: st.session_state[k]=False if k=='logged_in' else None
    if not st.session_state['logged_in']: show_login(); return
    show_sidebar(st.session_state['username'],st.session_state['role'])
    show_dashboard(st.session_state['username'],st.session_state['role'])

if __name__=="__main__": main()
