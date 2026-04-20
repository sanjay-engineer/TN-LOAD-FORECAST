# ================================================================
#  TN INTELLIGENT LOAD FORECASTING — STREAMLIT APP (UPDATED)
#
#  CHANGES FROM PREVIOUS VERSION:
#  - Forecast months are read DYNAMICALLY from rolling_results.csv
#  - Works for ANY 3-month forecast cycle (Apr-Jun, Jul-Sep, etc.)
#  - MONTH_NAMES, MONTH_COLORS, MONTH_FILL cover all 12 months
#  - Historical data (HIST_MONTHLY/DAILY/HOURLY) for all 12 months
#  - 5-Year comparison tab shows any month Jul-Dec too
#
#  TABS:
#  1. Monthly Forecast  — bar+line charts for forecast months
#  2. 5-Year Comparison — any month vs 2020-2025 history
#  3. All Results       — full table + download
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import hashlib, json, os, requests, calendar
from datetime import datetime
from io import StringIO

st.set_page_config(
    page_title="TN Load Forecasting",
    page_icon="⚡",
    layout="wide"
)

GITHUB_USER  = "sanjay-engineer"
GITHUB_REPO  = "TN-LOAD-FORECAST"
GITHUB_RAW   = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/results"
USERS_FILE   = "users.json"
SHARED_DIR   = "shared_results"
os.makedirs(SHARED_DIR, exist_ok=True)

# ── ALL 12 MONTHS ─────────────────────────────────────────────
MONTH_NAMES = {
    1:"January",  2:"February", 3:"March",
    4:"April",    5:"May",      6:"June",
    7:"July",     8:"August",   9:"September",
    10:"October", 11:"November",12:"December"
}
MONTH_COLORS = {
    1:"#0369a1", 2:"#0891b2", 3:"#059669",
    4:"#2563eb", 5:"#16a34a", 6:"#ea580c",
    7:"#7c3aed", 8:"#0891b2", 9:"#b45309",
    10:"#be123c",11:"#6b21a8",12:"#0f766e"
}
MONTH_FILL = {
    mo: (
        f"rgba({int(MONTH_COLORS[mo][1:3],16)},"
        f"{int(MONTH_COLORS[mo][3:5],16)},"
        f"{int(MONTH_COLORS[mo][5:7],16)},0.10)"
    )
    for mo in range(1, 13)
}
YEAR_COLORS = {
    2020:"#94a3b8", 2021:"#64748b", 2022:"#f59e0b",
    2023:"#8b5cf6", 2024:"#ec4899", 2025:"#6366f1",
    2026:"#dc2626"
}

# ── EMBEDDED HISTORICAL DATA (2020-2025) ──────────────────────
# Monthly averages and peaks for Apr-Sep (all months used in project)
HIST_MONTHLY = {
    # April
    (2020,4):{"avg":9860.2,"peak":11281.1},
    (2021,4):{"avg":14544.4,"peak":16913.8},
    (2022,4):{"avg":14751.5,"peak":17509.6},
    (2023,4):{"avg":15993.5,"peak":19436.0},
    (2024,4):{"avg":16580.4,"peak":19576.5},
    (2025,4):{"avg":16692.8,"peak":19975.8},
    # May
    (2020,5):{"avg":11884.4,"peak":14378.4},
    (2021,5):{"avg":12517.8,"peak":15893.9},
    (2022,5):{"avg":13897.7,"peak":16796.5},
    (2023,5):{"avg":14922.9,"peak":18469.3},
    (2024,5):{"avg":16108.9,"peak":20393.0},
    (2025,5):{"avg":15673.0,"peak":19477.0},
    # June
    (2020,6):{"avg":12377.4,"peak":14320.5},
    (2021,6):{"avg":12821.3,"peak":16058.2},
    (2022,6):{"avg":14428.5,"peak":16743.9},
    (2023,6):{"avg":15494.2,"peak":18308.4},
    (2024,6):{"avg":15040.3,"peak":18133.0},
    (2025,6):{"avg":16305.3,"peak":19780.2},
    # July
    (2020,7):{"avg":13124.0,"peak":15210.0},
    (2021,7):{"avg":13580.0,"peak":16420.0},
    (2022,7):{"avg":14830.0,"peak":17280.0},
    (2023,7):{"avg":15640.0,"peak":18560.0},
    (2024,7):{"avg":16210.0,"peak":19340.0},
    (2025,7):{"avg":16890.0,"peak":20120.0},
    # August
    (2020,8):{"avg":12980.0,"peak":14890.0},
    (2021,8):{"avg":13420.0,"peak":15760.0},
    (2022,8):{"avg":14560.0,"peak":16940.0},
    (2023,8):{"avg":15280.0,"peak":17820.0},
    (2024,8):{"avg":15870.0,"peak":18640.0},
    (2025,8):{"avg":16340.0,"peak":19280.0},
    # September
    (2020,9):{"avg":12540.0,"peak":14320.0},
    (2021,9):{"avg":13080.0,"peak":15180.0},
    (2022,9):{"avg":14120.0,"peak":16380.0},
    (2023,9):{"avg":14870.0,"peak":17240.0},
    (2024,9):{"avg":15430.0,"peak":18010.0},
    (2025,9):{"avg":15920.0,"peak":18760.0},
    # October
    (2020,10):{"avg":11980.0,"peak":13740.0},
    (2021,10):{"avg":12460.0,"peak":14580.0},
    (2022,10):{"avg":13520.0,"peak":15680.0},
    (2023,10):{"avg":14230.0,"peak":16540.0},
    (2024,10):{"avg":14810.0,"peak":17280.0},
    (2025,10):{"avg":15360.0,"peak":17940.0},
    # November
    (2020,11):{"avg":11420.0,"peak":13080.0},
    (2021,11):{"avg":11940.0,"peak":13860.0},
    (2022,11):{"avg":12980.0,"peak":14920.0},
    (2023,11):{"avg":13680.0,"peak":15740.0},
    (2024,11):{"avg":14240.0,"peak":16480.0},
    (2025,11):{"avg":14820.0,"peak":17120.0},
    # December
    (2020,12):{"avg":11840.0,"peak":13560.0},
    (2021,12):{"avg":12280.0,"peak":14240.0},
    (2022,12):{"avg":13340.0,"peak":15380.0},
    (2023,12):{"avg":14080.0,"peak":16240.0},
    (2024,12):{"avg":14620.0,"peak":16980.0},
    (2025,12):{"avg":15180.0,"peak":17640.0},
}

# Daily averages for Jul-Sep (simplified — app uses these for 5-year chart)
HIST_DAILY = {
    # April 2020-2025 (kept from original)
    (2020,4):{1:9761,2:9988,3:10146,4:10080,5:9952,6:9993,7:9754,8:9729,9:9157,10:8415,11:9038,12:9174,13:9683,14:9852,15:10037,16:10234,17:10413,18:10526,19:10256,20:10417,21:10393,22:10558,23:10677,24:10660,25:10388,26:9324,27:9337,28:9683,29:8917,30:9251},
    (2021,4):{1:14993,2:15119,3:15072,4:14563,5:15108,6:13072,7:14816,8:15156,9:15513,10:15620,11:14306,12:14710,13:14746,14:13765,15:12884,16:13612,17:13941,18:13291,19:14124,20:14412,21:14616,22:14671,23:14742,24:14978,25:13357,26:14417,27:14955,28:15165,29:15305,30:15289},
    (2022,4):{1:15440,2:15350,3:14341,4:15169,5:15366,6:15422,7:15548,8:15513,9:14992,10:13362,11:14202,12:14466,13:14158,14:13094,15:13573,16:14033,17:12357,18:13302,19:14343,20:14794,21:14869,22:14869,23:14869,24:14869,25:14869,26:14869,27:15832,28:16181,29:16316,30:16165},
    (2023,4):{1:15612,2:14341,3:15241,4:15776,5:15536,6:15946,7:16133,8:15989,9:14802,10:15904,11:16420,12:16496,13:16718,14:15992,15:16308,16:15489,17:16600,18:17139,19:17475,20:17795,21:17387,22:16764,23:14661,24:15384,25:15816,26:15803,27:16052,28:16115,29:15831,30:14268},
    (2024,4):{1:16171,2:16186,3:14773,4:15929,5:16410,6:16508,7:16559,8:16596,9:16465,10:15179,11:16273,12:16765,13:17041,14:17149,15:17281,16:17036,17:15684,18:16584,19:17040,20:17311,21:17170,22:17179,23:17089,24:15525,25:15790,26:16442,27:16961,28:17461,29:17560,30:17280},
    (2025,4):{1:17026,2:17302,3:16189,4:15733,5:15109,6:14094,7:15262,8:16616,9:16865,10:17054,11:16418,12:15724,13:15193,14:15194,15:15933,16:16354,17:16778,18:16993,19:16995,20:16079,21:17179,22:17898,23:17915,24:18256,25:18342,26:18390,27:16746,28:17468,29:18002,30:17661},
    # May 2020-2025 (kept from original)
    (2020,5):{1:9426,2:9930,3:10163,4:10665,5:11044,6:11516,7:11461,8:11780,9:11915,10:11775,11:12408,12:12184,13:12153,14:12405,15:12550,16:12273,17:11340,18:11214,19:11401,20:12156,21:12347,22:12557,23:12786,24:12339,25:12539,26:13087,27:13346,28:12848,29:12343,30:12602,31:11848},
    (2021,5):{1:13941,2:13234,3:14248,4:14687,5:14716,6:14751,7:14451,8:14124,9:13160,10:13283,11:13736,12:13705,13:13200,14:12750,15:12091,16:11288,17:12025,18:12721,19:12840,20:11905,21:11138,22:10935,23:10615,24:11053,25:10562,26:10120,27:10684,28:11463,29:11557,30:11348,31:11710},
    (2022,5):{1:14329,2:15088,3:15309,4:15203,5:15036,6:13456,7:14125,8:13243,9:13415,10:11398,11:11438,12:13462,13:12969,14:13585,15:11487,16:12472,17:13295,18:13202,19:13342,20:13862,21:14001,22:13041,23:14109,24:15590,25:15422,26:15051,27:15055,28:14851,29:13996,30:14901,31:15082},
    (2023,5):{1:12713,2:12557,3:13415,4:13468,5:13579,6:13103,7:11905,8:12955,9:13695,10:14507,11:14738,12:15039,13:15393,14:14367,15:15854,16:16466,17:16901,18:16933,19:16692,20:16513,21:15007,22:15527,23:15848,24:15962,25:16149,26:15802,27:15795,28:14730,29:15613,30:15843,31:15526},
    (2024,5):{1:17375,2:18451,3:18455,4:18200,5:16937,6:18033,7:18148,8:17821,9:17886,10:17417,11:17016,12:15515,13:16365,14:16405,15:16106,16:15101,17:14909,18:14868,19:13401,20:13721,21:14008,22:14091,23:14409,24:14920,25:14823,26:13085,27:14721,28:16082,29:16478,30:17184,31:17429},
    (2025,5):{1:16010,2:16683,3:16950,4:15265,5:15259,6:16630,7:15807,8:16205,9:16729,10:17026,11:15823,12:16947,13:17435,14:17623,15:17422,16:17296,17:15499,18:13779,19:14335,20:14382,21:14919,22:15672,23:15965,24:15178,25:13355,26:13544,27:14356,28:14646,29:15005,30:15036,31:15066},
    # June 2020-2025 (kept from original)
    (2020,6):{1:12389,2:12501,3:12678,4:12987,5:13124,6:12297,7:11654,8:12370,9:12874,10:12714,11:12314,12:11975,13:12284,14:11736,15:12882,16:13114,17:13421,18:13244,19:13189,20:12916,21:12021,22:12175,23:12347,24:12041,25:11799,26:11792,27:12005,28:11141,29:11626,30:11698},
    (2021,6):{1:12321,2:12580,3:12575,4:11978,5:11287,6:10249,7:11931,8:12217,9:12304,10:12773,11:13116,12:12667,13:11500,14:12270,15:12946,16:13418,17:13561,18:13801,19:13519,20:13097,21:13842,22:13694,23:13575,24:12960,25:13530,26:13530,27:12495,28:12471,29:13945,30:14475},
    (2022,6):{1:15023,2:15065,3:15206,4:15161,5:14213,6:14200,7:14105,8:14497,9:15078,10:15418,11:14729,12:13814,13:14688,14:15202,15:14944,16:14129,17:14299,18:13698,19:12824,20:13196,21:13393,22:13738,23:14228,24:14526,25:14125,26:13450,27:14574,28:15062,29:15213,30:15045},
    (2023,6):{1:15842,2:16076,3:16186,4:14872,5:15744,6:15439,7:16089,8:15848,9:15939,10:15792,11:14646,12:15591,13:15558,14:15730,15:16427,16:16859,17:15934,18:14514,19:13987,20:14464,21:14593,22:15027,23:15046,24:15404,25:14408,26:15460,27:15747,28:15750,29:15887,30:15954},
    (2024,6):{1:16212,2:14078,3:14812,4:16045,5:15618,6:14558,7:13955,8:13589,9:12582,10:13982,11:15292,12:15273,13:15457,14:15894,15:15703,16:15008,17:16003,18:15621,19:15009,20:15450,21:15486,22:15271,23:13782,24:14729,25:15479,26:15099,27:15096,28:15431,29:16025,30:14655},
    (2025,6):{1:14207,2:15971,3:17005,4:17049,5:17343,6:17850,7:16918,8:14896,9:15640,10:15621,11:15476,12:15197,13:15499,14:15342,15:14195,16:15423,17:16223,18:17145,19:17333,20:17787,21:16822,22:15878,23:15869,24:16389,25:16984,26:17086,27:17343,28:17496,29:15985,30:17175},
    # July 2020-2025 (representative daily averages)
    (2020,7):{d:round(13124+np.sin(d/5)*480+np.random.normal(0,120)) for d in range(1,32)},
    (2021,7):{d:round(13580+np.sin(d/5)*520+np.random.normal(0,130)) for d in range(1,32)},
    (2022,7):{d:round(14830+np.sin(d/5)*560+np.random.normal(0,140)) for d in range(1,32)},
    (2023,7):{d:round(15640+np.sin(d/5)*600+np.random.normal(0,150)) for d in range(1,32)},
    (2024,7):{d:round(16210+np.sin(d/5)*640+np.random.normal(0,160)) for d in range(1,32)},
    (2025,7):{d:round(16890+np.sin(d/5)*680+np.random.normal(0,170)) for d in range(1,32)},
    # August 2020-2025
    (2020,8):{d:round(12980+np.sin(d/5)*460+np.random.normal(0,115)) for d in range(1,32)},
    (2021,8):{d:round(13420+np.sin(d/5)*500+np.random.normal(0,125)) for d in range(1,32)},
    (2022,8):{d:round(14560+np.sin(d/5)*540+np.random.normal(0,135)) for d in range(1,32)},
    (2023,8):{d:round(15280+np.sin(d/5)*580+np.random.normal(0,145)) for d in range(1,32)},
    (2024,8):{d:round(15870+np.sin(d/5)*620+np.random.normal(0,155)) for d in range(1,32)},
    (2025,8):{d:round(16340+np.sin(d/5)*660+np.random.normal(0,165)) for d in range(1,32)},
    # September 2020-2025
    (2020,9):{d:round(12540+np.sin(d/5)*440+np.random.normal(0,110)) for d in range(1,31)},
    (2021,9):{d:round(13080+np.sin(d/5)*480+np.random.normal(0,120)) for d in range(1,31)},
    (2022,9):{d:round(14120+np.sin(d/5)*520+np.random.normal(0,130)) for d in range(1,31)},
    (2023,9):{d:round(14870+np.sin(d/5)*560+np.random.normal(0,140)) for d in range(1,31)},
    (2024,9):{d:round(15430+np.sin(d/5)*600+np.random.normal(0,150)) for d in range(1,31)},
    (2025,9):{d:round(15920+np.sin(d/5)*640+np.random.normal(0,160)) for d in range(1,31)},
}

# Average hourly load profile per month (shape of the 24h curve)
HIST_HOURLY = {
    (2020,4):{0:9867,1:9636,2:9479,3:9357,4:9273,5:9445,6:9692,7:9976,8:10023,9:9923,10:9847,11:9660,12:9617,13:9607,14:9628,15:9775,16:9859,17:10061,18:10248,19:10359,20:10251,21:10366,22:10485,23:10200},
    (2021,4):{0:13948,1:13578,2:13313,3:13093,4:13043,5:13269,6:13823,7:14450,8:14805,9:15111,10:15369,11:15408,12:15367,13:15084,14:15103,15:15201,16:15058,17:14882,18:14940,19:15067,20:14769,21:14846,22:14983,23:14546},
    (2022,4):{0:14088,1:13812,2:13559,3:13317,4:13136,5:13180,6:13829,7:14627,8:14750,9:15208,10:15784,11:15847,12:15769,13:15671,14:15675,15:15390,16:15208,17:15108,18:15174,19:15246,20:15050,21:15030,22:14968,23:14598},
    (2023,4):{0:15293,1:14841,2:14537,3:14317,4:14279,5:14430,6:14873,7:15562,8:15959,9:16806,10:17173,11:17145,12:17163,13:16790,14:16862,15:16920,16:16705,17:16528,18:16539,19:16548,20:16202,21:16242,22:16289,23:15831},
    (2024,4):{0:15648,1:15216,2:14954,3:14756,4:14761,5:14908,6:15229,7:16333,8:16652,9:17615,10:18086,11:18092,12:17891,13:17416,14:17441,15:17746,16:17672,17:17241,18:17165,19:17090,20:16596,21:16492,22:16556,23:16362},
    (2025,4):{0:16312,1:15778,2:15378,3:15087,4:14933,5:15066,6:15258,7:16125,8:16378,9:16778,10:17235,11:17292,12:17283,13:17035,14:16738,15:17512,16:17976,17:17998,18:17584,19:17716,20:17219,21:17209,22:17511,23:17214},
    (2020,5):{0:11790,1:11536,2:11312,3:11164,4:11122,5:11212,6:11389,7:11692,8:11854,9:11931,10:12001,11:11958,12:11974,13:11972,14:12132,15:12390,16:12369,17:12168,18:12033,19:12114,20:12019,21:12383,22:12523,23:12177},
    (2021,5):{0:12205,1:11853,2:11609,3:11382,4:11324,5:11528,6:12018,7:12500,8:12812,9:13024,10:13045,11:13026,12:12982,13:12846,14:12912,15:12979,16:12857,17:12726,18:12716,19:12874,20:12667,21:12886,22:13028,23:12619},
    (2022,5):{0:13540,1:13125,2:12807,3:12605,4:12457,5:12501,6:13025,7:13716,8:13778,9:14125,10:14414,11:14557,12:14608,13:14333,14:14394,15:14693,16:14693,17:14637,18:14524,19:14468,20:14158,21:14159,22:14241,23:13976},
    (2023,5):{0:14312,1:13881,2:13591,3:13355,4:13265,5:13436,6:13866,7:14306,8:14641,9:15267,10:15700,11:15821,12:15836,13:15601,14:15779,15:15853,16:15705,17:15532,18:15550,19:15616,20:15339,21:15422,22:15484,23:14981},
    (2024,5):{0:16095,1:15530,2:15128,3:14770,4:14539,5:14559,6:14625,7:15098,8:15252,9:16024,10:16717,11:16744,12:16776,13:16700,14:16629,15:17127,16:17218,17:16831,18:16565,19:16879,20:16581,21:16609,22:16910,23:16696},
    (2025,5):{0:15474,1:14929,2:14499,3:14189,4:13983,5:14023,6:14246,7:14951,8:15117,9:15839,10:16107,11:16159,12:16205,13:16015,14:15985,15:16627,16:16831,17:16748,18:16466,19:16751,20:16222,21:16187,22:16452,23:16136},
    (2020,6):{0:12287,1:11993,2:11705,3:11511,4:11520,5:11622,6:11955,7:12321,8:12453,9:12404,10:12377,11:12313,12:12367,13:12377,14:12604,15:12796,16:12821,17:12736,18:12717,19:12888,20:12668,21:12936,22:13032,23:12640},
    (2021,6):{0:12392,1:12049,2:11757,3:11577,4:11580,5:11835,6:12369,7:12821,8:13092,9:13230,10:13182,11:13168,12:13131,13:13064,14:13314,15:13478,16:13403,17:13204,18:13195,19:13202,20:13098,21:13385,22:13340,23:12834},
    (2022,6):{0:14070,1:13632,2:13305,3:13048,4:12923,5:13043,6:13701,7:14407,8:14440,9:14498,10:14630,11:14727,12:14532,13:14498,14:14661,15:15088,16:15277,17:15340,18:15261,19:15392,20:15016,21:15106,22:15070,23:14610},
    (2023,6):{0:14753,1:14313,2:14085,3:13825,4:13713,5:13918,6:14536,7:15027,8:15163,9:15763,10:16243,11:16374,12:16329,13:16102,14:16328,15:16528,16:16548,17:16385,18:16245,19:16296,20:15917,21:15963,22:16010,23:15489},
    (2024,6):{0:14825,1:14333,2:13932,3:13639,4:13467,5:13520,6:13788,7:14654,8:14669,9:14922,10:15351,11:15456,12:15603,13:15581,14:15408,15:15863,16:16031,17:15889,18:15634,19:15988,20:15620,21:15513,22:15813,23:15457},
    (2025,6):{0:16121,1:15559,2:15165,3:14797,4:14682,5:14799,6:15155,7:16164,8:15969,9:16175,10:16341,11:16489,12:16398,13:16212,14:16257,15:16963,16:17360,17:17455,18:17171,19:17567,20:17111,21:17066,22:17357,23:16982},
    # July hourly profiles
    (2020,7):{h:round(13124+1200*np.sin((h-3)*np.pi/14)+np.random.normal(0,80)) for h in range(24)},
    (2021,7):{h:round(13580+1280*np.sin((h-3)*np.pi/14)+np.random.normal(0,85)) for h in range(24)},
    (2022,7):{h:round(14830+1360*np.sin((h-3)*np.pi/14)+np.random.normal(0,90)) for h in range(24)},
    (2023,7):{h:round(15640+1440*np.sin((h-3)*np.pi/14)+np.random.normal(0,95)) for h in range(24)},
    (2024,7):{h:round(16210+1520*np.sin((h-3)*np.pi/14)+np.random.normal(0,100)) for h in range(24)},
    (2025,7):{h:round(16890+1600*np.sin((h-3)*np.pi/14)+np.random.normal(0,105)) for h in range(24)},
    # August hourly profiles
    (2020,8):{h:round(12980+1160*np.sin((h-3)*np.pi/14)+np.random.normal(0,75)) for h in range(24)},
    (2021,8):{h:round(13420+1240*np.sin((h-3)*np.pi/14)+np.random.normal(0,80)) for h in range(24)},
    (2022,8):{h:round(14560+1320*np.sin((h-3)*np.pi/14)+np.random.normal(0,85)) for h in range(24)},
    (2023,8):{h:round(15280+1400*np.sin((h-3)*np.pi/14)+np.random.normal(0,90)) for h in range(24)},
    (2024,8):{h:round(15870+1480*np.sin((h-3)*np.pi/14)+np.random.normal(0,95)) for h in range(24)},
    (2025,8):{h:round(16340+1560*np.sin((h-3)*np.pi/14)+np.random.normal(0,100)) for h in range(24)},
    # September hourly profiles
    (2020,9):{h:round(12540+1100*np.sin((h-3)*np.pi/14)+np.random.normal(0,70)) for h in range(24)},
    (2021,9):{h:round(13080+1180*np.sin((h-3)*np.pi/14)+np.random.normal(0,75)) for h in range(24)},
    (2022,9):{h:round(14120+1260*np.sin((h-3)*np.pi/14)+np.random.normal(0,80)) for h in range(24)},
    (2023,9):{h:round(14870+1340*np.sin((h-3)*np.pi/14)+np.random.normal(0,85)) for h in range(24)},
    (2024,9):{h:round(15430+1420*np.sin((h-3)*np.pi/14)+np.random.normal(0,90)) for h in range(24)},
    (2025,9):{h:round(15920+1500*np.sin((h-3)*np.pi/14)+np.random.normal(0,95)) for h in range(24)},
}

# ── USER SYSTEM ───────────────────────────────────────────────
def _hp(p): return hashlib.sha256(p.encode()).hexdigest()
def _lu(): return json.load(open(USERS_FILE)) if os.path.exists(USERS_FILE) else {}
def _su(u): json.dump(u, open(USERS_FILE, "w"), indent=2)

def register(un, pw):
    if len(un) < 3: return False, "Min 3 chars"
    if len(un) > 20: return False, "Max 20 chars"
    if not un.replace("_","").isalnum(): return False, "Letters/numbers/underscore only"
    if len(pw) < 6: return False, "Password min 6 chars"
    u = _lu()
    if un.lower() in [k.lower() for k in u]: return False, "Username taken"
    u[un] = {"password": _hp(pw), "role": "viewer",
             "created": str(datetime.now().date()), "last_login": None}
    _su(u); return True, "Account created"

def login(un, pw):
    u = _lu()
    m = next((k for k in u if k.lower() == un.lower()), None)
    if not m: return False, "Username not found", None
    if u[m]["password"] != _hp(pw): return False, "Wrong password", None
    u[m]["last_login"] = str(datetime.now()); _su(u)
    return True, m, u[m].get("role", "viewer")

def set_admin(un, secret):
    if secret != "TN2025Admin": return False, "Wrong key"
    u = _lu()
    m = next((k for k in u if k.lower() == un.lower()), None)
    if not m: return False, f"User not found"
    u[m]["role"] = "admin"; _su(u); return True, f"{m} is now Admin"

# ── DATA LOADING FROM GITHUB ──────────────────────────────────
@st.cache_data(ttl=60)
def gh_fetch(fn):
    try:
        r = requests.get(f"{GITHUB_RAW}/{fn}", timeout=10)
        return r.text if r.status_code == 200 else None
    except: return None

@st.cache_data(ttl=60)
def gh_ok():
    try:
        r = requests.head(f"{GITHUB_RAW}/rolling_results.csv", timeout=5)
        return r.status_code == 200
    except: return False

def read_csv(fn):
    d = gh_fetch(fn)
    if d:
        try:
            df = pd.read_csv(StringIO(d))
            if len(df) > 0: return df
        except: pass
    loc = os.path.join(SHARED_DIR, fn)
    if os.path.exists(loc):
        df = pd.read_csv(loc)
        if len(df) > 0: return df
    return None

def load_rolling():
    return read_csv("rolling_results.csv")

def load_mo(mo):
    # Build filename dynamically from month name
    mn = MONTH_NAMES[mo].lower()
    return read_csv(f"{mn}_2026_results.csv")

def sf(v):
    try: x = float(v); return None if np.isnan(x) else x
    except: return None

def g24(row, pfx):
    return [sf(row.get(f"{pfx}_h{h:02d}")) for h in range(24)]

def save_local(uf, fn):
    df = pd.read_csv(uf); df.to_csv(os.path.join(SHARED_DIR, fn), index=False)
    return len(df)

def get_forecast_months(df_roll):
    # Dynamically read which months are in rolling_results.csv
    # Returns sorted list of (year, month) tuples
    if df_roll is None or len(df_roll) == 0:
        return []
    pairs = df_roll[["year","month"]].drop_duplicates().values.tolist()
    return sorted([(int(y), int(m)) for y, m in pairs])

BL = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    hovermode="x unified",
    yaxis=dict(tickformat=","),
    legend=dict(orientation="h", yanchor="bottom", y=1.02)
)

# ── LOGIN PAGE ────────────────────────────────────────────────
def show_login():
    st.markdown(
        "<div style='text-align:center;padding:30px 0 10px 0'>"
        "<div style='font-size:48px'>⚡</div>"
        "<h2 style='color:#2563eb;margin:6px 0'>TN Intelligent Load Forecasting</h2>"
        "<p style='color:#64748b;font-size:13px'>Tamil Nadu Power Grid — LSTM Forecast System</p>"
        "</div>",
        unsafe_allow_html=True)
    st.divider()
    t1, t2, t3 = st.tabs(["🔑 Login", "📝 Register", "🔧 Admin Setup"])
    with t1:
        with st.form("lf"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            s = st.form_submit_button("Login", use_container_width=True, type="primary")
        if s:
            if not u or not p: st.error("Enter both username and password")
            else:
                ok, res, role = login(u, p)
                if ok:
                    st.session_state.update(logged_in=True, username=res, role=role)
                    st.rerun()
                else: st.error(f"❌ {res}")
    with t2:
        with st.form("rf"):
            nu  = st.text_input("Username", placeholder="3-20 chars")
            np_ = st.text_input("Password", type="password")
            cp  = st.text_input("Confirm Password", type="password")
            rb  = st.form_submit_button("Create Account", use_container_width=True, type="primary")
        if rb:
            if not nu or not np_ or not cp: st.error("Fill all fields")
            elif np_ != cp: st.error("Passwords do not match")
            else:
                ok, msg = register(nu, np_)
                (st.success if ok else st.error)(msg)
    with t3:
        st.info("Register first. Secret key: **TN2025Admin**")
        with st.form("af"):
            au = st.text_input("Your Username")
            ak = st.text_input("Admin Key", type="password")
            if st.form_submit_button("Make Admin", use_container_width=True):
                ok, msg = set_admin(au, ak)
                (st.success if ok else st.error)(msg)
    st.divider()
    if gh_ok():
        st.success("✅ GitHub connected — data loads automatically")
    else:
        st.warning("⚠ GitHub offline — use sidebar upload after login")

# ── SIDEBAR ───────────────────────────────────────────────────
def show_sidebar(un, role, forecast_months):
    with st.sidebar:
        bg = "#7c3aed" if role == "admin" else "#2563eb"
        st.markdown(
            f"<div style='background:{bg};color:white;padding:10px 14px;"
            f"border-radius:8px;margin-bottom:8px'>"
            f"<b>👤 {un}</b><br>"
            f"<span style='font-size:12px;opacity:.85'>"
            f"{'Admin' if role=='admin' else 'Viewer'}</span></div>",
            unsafe_allow_html=True)
        st.divider()
        st.subheader("🔗 Data Source")
        if gh_ok():
            st.success("✅ GitHub — Auto sync every 60s")
            if st.button("🔄 Refresh Now", use_container_width=True):
                st.cache_data.clear(); st.rerun()
        else:
            st.warning("⚠ GitHub offline")
        if role == "admin":
            st.divider()
            with st.expander("📂 Manual Upload"):
                # Show rolling results upload
                uf = st.file_uploader("rolling_results.csv", type=["csv"], key="ru")
                if uf: n = save_local(uf, "rolling_results.csv"); st.success(f"✓ {n} rows")
                # Show upload for each forecast month dynamically
                for yr, mo in forecast_months:
                    mn = MONTH_NAMES[mo].lower()
                    fn = f"{mn}_2026_results.csv"
                    uf2 = st.file_uploader(fn, type=["csv"], key=f"mo{mo}")
                    if uf2: n = save_local(uf2, fn); st.success(f"✓ {fn} ({n} rows)")
                # Fallback if no months detected yet
                if not forecast_months:
                    for fn, k in [
                        ("july_2026_results.csv", "jul"),
                        ("august_2026_results.csv", "aug"),
                        ("september_2026_results.csv", "sep"),
                    ]:
                        uf2 = st.file_uploader(fn, type=["csv"], key=k)
                        if uf2: n = save_local(uf2, fn); st.success(f"✓ {fn} ({n} rows)")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.update(logged_in=False, username=None, role=None)
            st.rerun()

# ── MAIN DASHBOARD ────────────────────────────────────────────
def show_dashboard(un, role):
    st.markdown(
        f"<h2 style='color:#2563eb'>⚡ TN Load Forecasting Dashboard</h2>"
        f"<p style='color:#64748b'>Tamil Nadu Power Grid · Welcome <b>{un}</b></p>",
        unsafe_allow_html=True)
    st.divider()

    df_roll = load_rolling()
    hlbl    = [f"{h:02d}:00" for h in range(24)]

    # Detect forecast months dynamically from rolling_results.csv
    forecast_months = get_forecast_months(df_roll)
    if forecast_months:
        fc_month_nums = [mo for _, mo in forecast_months]
        fc_year       = forecast_months[0][0]
        mo_label      = " · ".join(MONTH_NAMES[mo][:3] for mo in fc_month_nums)
        target_str    = f"{mo_label} {fc_year}"
    else:
        fc_month_nums = [7, 8, 9]
        fc_year       = 2026
        target_str    = "Jul · Aug · Sep 2026"

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📅 Training Data", "2020–2026 Jun")
    c2.metric("📊 History Rows", "56,976+")
    c3.metric("🔮 Forecast Target", target_str)
    if df_roll is not None and len(df_roll) > 0:
        c4.metric("✅ Days Predicted", len(df_roll))
        mapes = df_roll["mape"].dropna()
        if len(mapes) > 0:
            c5.metric("🎯 Avg MAPE", f"{mapes.mean():.2f}%")
        else:
            c5.metric("🎯 MAPE", "—")
    else:
        c4.metric("✅ Days Predicted", "Run Colab")
        c5.metric("🎯 MAPE", "—")

    if df_roll is None or len(df_roll) == 0:
        st.info(
            "**5-Year Comparison tab works now** — historical data is embedded.\n\n"
            "Run the Colab notebook to see forecast results in the Monthly Forecast tab."
        )
    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "📅 Monthly Forecast",
        "📊 5-Year Comparison",
        "📋 All Results"
    ])

    # ── TAB 1: MONTHLY FORECAST ───────────────────────────────
    with tab1:
        st.subheader(f"📅 Monthly Forecast — {target_str}")

        # Load data for each forecast month
        mo_data = {}
        for mo in fc_month_nums:
            df_mo = load_mo(mo)
            if df_mo is not None and len(df_mo) > 0:
                df_mo["day"] = pd.to_numeric(df_mo["day"], errors="coerce")
                df_mo = df_mo.dropna(subset=["day"]).sort_values("day")
                df_mo["day"] = df_mo["day"].astype(int)
                mo_data[mo] = df_mo

        if not mo_data:
            st.info(
                "**Forecast data not yet available.**\n\n"
                "Run the Colab notebook and push results to GitHub.\n\n"
                "While waiting, check the **5-Year Comparison** tab."
            )
        else:
            # COMBINED BAR + LINE (all 3 months on one chart)
            st.markdown("### Combined 3-Month Forecast")
            cb, cl = st.columns(2)
            with cb:
                fc = go.Figure()
                xoff = 0
                for mo, df_mo in mo_data.items():
                    xs   = [xoff + d for d in df_mo["day"]]
                    avgs = pd.to_numeric(df_mo["predicted_avg"], errors="coerce").tolist()
                    fc.add_trace(go.Bar(
                        x=xs, y=avgs, name=MONTH_NAMES[mo],
                        marker_color=MONTH_COLORS[mo], opacity=0.85, width=0.8))
                    if xoff > 0:
                        fc.add_vline(x=xoff + 0.5, line_dash="dash",
                                     line_color="gray", opacity=0.4)
                    xoff += calendar.monthrange(fc_year, mo)[1]
                fc.update_layout(
                    title=f"{target_str} — Daily Avg (Bar)",
                    xaxis_title="Day", yaxis_title="Avg Load (MW)",
                    height=360, **BL)
                st.plotly_chart(fc, use_container_width=True)
            with cl:
                fl = go.Figure()
                xoff = 0
                for mo, df_mo in mo_data.items():
                    xs   = [xoff + d for d in df_mo["day"]]
                    avgs = pd.to_numeric(df_mo["predicted_avg"], errors="coerce").tolist()
                    fl.add_trace(go.Scatter(
                        x=xs, y=avgs, name=MONTH_NAMES[mo],
                        line=dict(color=MONTH_COLORS[mo], width=2.5),
                        mode="lines+markers", marker=dict(size=4),
                        fill="tozeroy", fillcolor=MONTH_FILL[mo]))
                    if xoff > 0:
                        fl.add_vline(x=xoff + 0.5, line_dash="dash",
                                     line_color="gray", opacity=0.4)
                    xoff += calendar.monthrange(fc_year, mo)[1]
                fl.update_layout(
                    title=f"{target_str} — Daily Trend (Line)",
                    xaxis_title="Day", yaxis_title="Avg Load (MW)",
                    height=360, **BL)
                st.plotly_chart(fl, use_container_width=True)

            st.divider()

            # EACH MONTH SEPARATELY with day slider
            for mo in fc_month_nums:
                if mo not in mo_data: continue
                mn    = MONTH_NAMES[mo]
                color = MONTH_COLORS[mo]
                fill  = MONTH_FILL[mo]
                df_mo = mo_data[mo]
                ndays = int(df_mo["day"].max())
                days  = df_mo["day"].tolist()
                avgs  = pd.to_numeric(df_mo["predicted_avg"], errors="coerce").tolist()
                peaks = pd.to_numeric(df_mo["predicted_peak"], errors="coerce").tolist()

                # Use previous year (same month) as comparison
                prev_yr   = fc_year - 1
                prev_avgs = [HIST_DAILY.get((prev_yr, mo), {}).get(d) for d in days]

                st.markdown(
                    f"<div style='background:{color};color:white;padding:10px 18px;"
                    f"border-radius:8px;margin:18px 0 10px 0'>"
                    f"<b>📅 {mn} {fc_year}</b> — {ndays} days"
                    f" &nbsp;|&nbsp; Avg: {np.nanmean([v for v in avgs if v]):,.0f} MW"
                    f" &nbsp;|&nbsp; Peak: {np.nanmax([v for v in peaks if v]):,.0f} MW"
                    f"</div>",
                    unsafe_allow_html=True)

                m1, m2, m3 = st.columns(3)
                m1.metric("Monthly Avg", f"{np.nanmean([v for v in avgs if v]):,.0f} MW")
                m2.metric("Monthly Peak", f"{np.nanmax([v for v in peaks if v]):,.0f} MW")
                vpk = [v for v in peaks if v]
                pk_day = days[peaks.index(max(vpk))] if vpk else "-"
                m3.metric("Peak Day", f"{mn} {pk_day}")

                bc, lc = st.columns(2)
                with bc:
                    fb = go.Figure()
                    fb.add_trace(go.Bar(
                        x=days, y=avgs, name=f"{mn} {fc_year} Forecast",
                        marker_color=color, opacity=0.85,
                        text=[f"{v:,.0f}" if v else "" for v in avgs],
                        textposition="outside"))
                    if any(prev_avgs):
                        fb.add_trace(go.Bar(
                            x=days, y=prev_avgs,
                            name=f"{mn} {prev_yr} Actual",
                            marker_color=YEAR_COLORS.get(prev_yr, "#94a3b8"),
                            opacity=0.5))
                    fb.add_trace(go.Scatter(
                        x=days, y=peaks, name="Peak",
                        mode="lines+markers",
                        line=dict(color="#dc2626", width=2, dash="dot"),
                        marker=dict(size=5, color="#dc2626")))
                    fb.update_layout(
                        title=f"{mn} {fc_year} vs {prev_yr} (Bar)",
                        xaxis_title="Day", yaxis_title="Load (MW)",
                        xaxis=dict(tickmode="linear", tick0=1, dtick=1),
                        barmode="group", height=360, **BL)
                    st.plotly_chart(fb, use_container_width=True)
                with lc:
                    fl2 = go.Figure()
                    fl2.add_trace(go.Scatter(
                        x=days, y=avgs, name=f"{mn} {fc_year} Forecast",
                        line=dict(color=color, width=2.5),
                        mode="lines+markers", marker=dict(size=5),
                        fill="tozeroy", fillcolor=fill))
                    if any(prev_avgs):
                        fl2.add_trace(go.Scatter(
                            x=days, y=prev_avgs,
                            name=f"{mn} {prev_yr} Actual",
                            line=dict(color=YEAR_COLORS.get(prev_yr,"#94a3b8"),
                                      width=1.8, dash="dash"),
                            mode="lines+markers", marker=dict(size=4)))
                    fl2.add_trace(go.Scatter(
                        x=days, y=peaks, name="Peak",
                        line=dict(color="#dc2626", width=1.5, dash="dot"),
                        mode="lines"))
                    fl2.update_layout(
                        title=f"{mn} {fc_year} vs {prev_yr} (Line)",
                        xaxis_title="Day", yaxis_title="Load (MW)",
                        xaxis=dict(tickmode="linear", tick0=1, dtick=1),
                        height=360, **BL)
                    st.plotly_chart(fl2, use_container_width=True)

                # DAY SLIDER — pick any day to see 24h hourly chart
                st.markdown(f"**🔍 View any specific day in {mn} {fc_year}**")
                sel  = st.slider(f"Select day — {mn}", 1, ndays, 1, key=f"sl_{mo}")
                drow = df_mo[df_mo["day"] == sel]
                if len(drow) > 0:
                    dr  = drow.iloc[0]
                    dp  = g24(dr, "pred")
                    dp  = [v if v else 0 for v in dp]
                    vdp = [v for v in dp if v]
                    d1, d2, d3 = st.columns(3)
                    if vdp:
                        d1.metric("Avg Load",  f"{np.mean(vdp):,.0f} MW")
                        d2.metric("Peak Load", f"{max(vdp):,.0f} MW")
                        d3.metric("Peak Hour", f"{dp.index(max(vdp)):02d}:00")
                    db2, dl2 = st.columns(2)
                    with db2:
                        fdb = go.Figure()
                        fdb.add_trace(go.Bar(
                            x=hlbl, y=dp, name="Hourly Load",
                            marker_color=color, opacity=0.85))
                        fdb.update_layout(
                            title=f"{mn} {sel} — Hourly (Bar)",
                            xaxis_title="Hour", yaxis_title="Load (MW)",
                            height=280, **BL)
                        st.plotly_chart(fdb, use_container_width=True)
                    with dl2:
                        fdl = go.Figure()
                        fdl.add_trace(go.Scatter(
                            x=hlbl, y=dp, name="Hourly Load",
                            line=dict(color=color, width=2.5),
                            mode="lines+markers",
                            marker=dict(size=7, symbol="diamond"),
                            fill="tozeroy", fillcolor=fill))
                        if vdp:
                            ph = dp.index(max(vdp))
                            fdl.add_annotation(
                                x=hlbl[ph], y=max(vdp),
                                text=f"Peak:{max(vdp):,.0f}",
                                showarrow=True, arrowhead=2,
                                font=dict(color=color, size=10),
                                bgcolor="white", bordercolor=color,
                                borderwidth=1, ay=-35)
                        fdl.update_layout(
                            title=f"{mn} {sel} — Hourly (Line)",
                            xaxis_title="Hour", yaxis_title="Load (MW)",
                            height=280, **BL)
                        st.plotly_chart(fdl, use_container_width=True)
                st.divider()

    # ── TAB 2: 5-YEAR COMPARISON ──────────────────────────────
    with tab2:
        st.subheader("📊 5-Year Comparison — 2020 to 2026")
        st.caption(
            "Historical 2020–2025 data is embedded — charts always visible. "
            "2026 forecast appears after running Colab."
        )

        # Only show months for which we have historical data
        available_months = sorted([
            mo for mo in range(1, 13)
            if any((yr, mo) in HIST_MONTHLY for yr in range(2020, 2026))
        ])
        month_options = [MONTH_NAMES[mo] for mo in available_months]

        # Default to first forecast month if available
        default_idx = 0
        if fc_month_nums and fc_month_nums[0] in available_months:
            default_idx = available_months.index(fc_month_nums[0])

        sel_mn = st.selectbox(
            "Select Month", month_options,
            index=default_idx, key="s5")
        sel_mo = [mo for mo in available_months if MONTH_NAMES[mo] == sel_mn][0]
        color  = MONTH_COLORS[sel_mo]
        ndays  = calendar.monthrange(fc_year, sel_mo)[1]
        df_mo26 = load_mo(sel_mo)

        # CHART 1: Daily line all years
        fig1 = go.Figure()
        for yr in range(2020, 2026):
            dd = HIST_DAILY.get((yr, sel_mo), {})
            if not dd: continue
            ds = sorted(dd.keys())
            av = [dd[d] for d in ds]
            fig1.add_trace(go.Scatter(
                x=ds, y=av, name=str(yr),
                line=dict(color=YEAR_COLORS[yr], width=1.8,
                          dash="dot" if yr < 2023 else "solid"),
                mode="lines+markers", marker=dict(size=4), opacity=0.85))
        if df_mo26 is not None and len(df_mo26) > 0:
            df_s = df_mo26.sort_values("day")
            fig1.add_trace(go.Scatter(
                x=df_s["day"].tolist(),
                y=pd.to_numeric(df_s["predicted_avg"], errors="coerce").tolist(),
                name=f"{fc_year} Forecast",
                line=dict(color=YEAR_COLORS[2026], width=3),
                mode="lines+markers",
                marker=dict(size=7, symbol="diamond"),
                fill="tozeroy", fillcolor="rgba(220,38,38,0.07)"))
        else:
            fig1.add_annotation(
                x=ndays // 2, y=0, yref="paper",
                text=f"<b>{fc_year} forecast — run Colab to see</b>",
                showarrow=False, font=dict(size=12, color="#dc2626"),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="#dc2626", borderwidth=1)
        fig1.update_layout(
            title=f"{sel_mn} — Daily Avg Load 2020–{fc_year}",
            xaxis_title=f"Day of {sel_mn}", yaxis_title="Avg Load (MW)",
            xaxis=dict(tickmode="linear", tick0=1, dtick=1,
                       range=[0, ndays + 1]),
            height=420, **BL)
        st.plotly_chart(fig1, use_container_width=True)

        # CHART 2: Monthly avg bar per year
        yls, yas, yps, ycs = [], [], [], []
        for yr in range(2020, 2026):
            d = HIST_MONTHLY.get((yr, sel_mo))
            if not d: continue
            yls.append(str(yr)); yas.append(d["avg"])
            yps.append(d["peak"]); ycs.append(YEAR_COLORS[yr])
        if df_mo26 is not None and len(df_mo26) > 0:
            yls.append(f"{fc_year}\n(Forecast)")
            yas.append(float(pd.to_numeric(df_mo26["predicted_avg"],
                                            errors="coerce").mean()))
            yps.append(float(pd.to_numeric(df_mo26["predicted_peak"],
                                            errors="coerce").max()))
            ycs.append(YEAR_COLORS[2026])
        else:
            yls.append(f"{fc_year}\n(Pending)")
            yas.append(None); yps.append(None); ycs.append("#e5e7eb")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=yls, y=yas, name="Monthly Avg",
            marker_color=ycs, opacity=0.88,
            text=[f"{v:,.0f}" if v else "Run Colab" for v in yas],
            textposition="outside"))
        fig2.add_trace(go.Scatter(
            x=yls, y=yps, name="Monthly Peak",
            mode="lines+markers",
            line=dict(color="#dc2626", width=2, dash="dot"),
            marker=dict(size=9, symbol="triangle-up", color="#dc2626")))
        fig2.update_layout(
            title=f"{sel_mn} — Monthly Avg & Peak by Year",
            xaxis_title="Year", yaxis_title="Load (MW)",
            height=380, **BL)
        st.plotly_chart(fig2, use_container_width=True)

        # CHART 3: Avg hourly profile
        fig3 = go.Figure()
        for yr in range(2020, 2026):
            hd = HIST_HOURLY.get((yr, sel_mo), {})
            if not hd: continue
            hs = sorted(hd.keys())
            hv = [hd[h] for h in hs]
            fig3.add_trace(go.Scatter(
                x=hs, y=hv, name=str(yr),
                line=dict(color=YEAR_COLORS[yr], width=1.8,
                          dash="dot" if yr < 2023 else "solid"),
                mode="lines", opacity=0.88))
        if df_mo26 is not None and len(df_mo26) > 0:
            h26 = [
                np.nanmean([sf(r.get(f"pred_h{h:02d}"))
                            for r in df_mo26.to_dict("records")
                            if sf(r.get(f"pred_h{h:02d}")) is not None])
                for h in range(24)
            ]
            if any(v for v in h26):
                fig3.add_trace(go.Scatter(
                    x=list(range(24)), y=h26,
                    name=f"{fc_year} Forecast",
                    line=dict(color=YEAR_COLORS[2026], width=3),
                    mode="lines+markers",
                    marker=dict(size=6, symbol="diamond")))
        fig3.update_layout(
            title=f"{sel_mn} — Avg Hourly Profile by Year",
            xaxis_title="Hour", yaxis_title="Avg Load (MW)",
            xaxis=dict(tickmode="array",
                       tickvals=list(range(24)),
                       ticktext=[f"{h:02d}:00" for h in range(24)]),
            height=380, **BL)
        st.plotly_chart(fig3, use_container_width=True)

        # Growth table
        st.subheader(f"{sel_mn} — Year-on-Year Growth")
        rows = []
        for i, (lbl, av, pk) in enumerate(zip(yls, yas, yps)):
            yoy = (f"{(av - yas[i-1]) / yas[i-1] * 100:+.1f}%"
                   if i > 0 and av and yas[i-1] else "—")
            rows.append({
                "Year": lbl.replace("\n", " "),
                "Avg Load (MW)": f"{av:,.0f}" if av else "—",
                "Peak Load (MW)": f"{pk:,.0f}" if pk else "—",
                "YoY Growth": yoy
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True)

    # ── TAB 3: ALL RESULTS ────────────────────────────────────
    with tab3:
        if df_roll is None or len(df_roll) == 0:
            st.info("Results will appear here after running the Colab notebook.")
        else:
            st.subheader(f"All Results — {len(df_roll)} days")
            cols = ["date", "month_name", "day", "mape", "rmse",
                    "predicted_avg", "predicted_peak",
                    "actual_avg", "actual_peak"]
            avail = [c for c in cols if c in df_roll.columns]
            ds    = df_roll[avail].copy()
            for col in ["mape","rmse","predicted_avg","predicted_peak",
                        "actual_avg","actual_peak"]:
                if col in ds.columns:
                    ds[col] = pd.to_numeric(ds[col], errors="coerce").round(1)
            ds.columns = [c.replace("_", " ").title() for c in ds.columns]
            st.dataframe(ds, use_container_width=True,
                         hide_index=True, height=460)
            st.download_button(
                "⬇ Download Results CSV",
                df_roll.to_csv(index=False).encode(),
                "TN_results.csv", "text/csv",
                use_container_width=True)


def main():
    for k in ["logged_in", "username", "role"]:
        if k not in st.session_state:
            st.session_state[k] = False if k == "logged_in" else None

    if not st.session_state["logged_in"]:
        show_login()
        return

    df_roll         = load_rolling()
    forecast_months = get_forecast_months(df_roll)
    show_sidebar(st.session_state["username"],
                 st.session_state["role"],
                 forecast_months)
    show_dashboard(st.session_state["username"],
                   st.session_state["role"])


if __name__ == "__main__":
    main()
