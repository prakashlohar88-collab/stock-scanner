import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import warnings
import database as db

warnings.filterwarnings('ignore')

# 1. पेज सेटअप
st.set_page_config(page_title="Alpha Momentum Web Scanner", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = None

# 2. ऑथेंटिकेशन साइडबार
def auth_sidebar():
    st.sidebar.title("🔐 User Portal")
    if not st.session_state.logged_in:
        auth_choice = st.sidebar.radio("विकल्प चुनें:", ["लॉगिन (Login)", "नया अकाउंट (Sign Up)"])
        if auth_choice == "लॉगिन (Login)":
            with st.sidebar.form("login_form"):
                u_input = st.text_input("Username या Email")
                pwd = st.text_input("Password", type="password")
                btn = st.form_submit_button("लॉगिन करें")
                if btn:
                    success, u_data, msg = db.authenticate_user(u_input, pwd)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_data = u_data
                        st.sidebar.success(msg)
                        st.rerun()
                    else:
                        st.sidebar.error(msg)
        elif auth_choice == "नया अकाउंट (Sign Up)":
            with st.sidebar.form("signup_form"):
                new_u = st.text_input("नया Username")
                new_email = st.text_input("Email ID")
                new_pwd = st.text_input("Password", type="password")
                btn = st.form_submit_button("अकाउंट बनाएँ (7-Day Pro Trial)")
                if btn:
                    if new_u and new_email and new_pwd:
                        ok, msg = db.register_user(new_u, new_email, new_pwd)
                        if ok:
                            st.sidebar.success(msg)
                        else:
                            st.sidebar.error(msg)
                    else:
                        st.sidebar.warning("कृपया सभी फ़ील्ड भरें!")
        st.stop()
    else:
        u = st.session_state.user_data
        st.sidebar.success(f"👤 स्वागत है, **{u['username']}**!")
        st.sidebar.info(f"🏆 **प्लान:** {u['status']}\n\n⏳ **समाप्ति:** {str(u['expiry'])[:10]}")
        if st.sidebar.button("लॉगआउट (Logout)"):
            st.session_state.logged_in = False
            st.session_state.user_data = None
            st.rerun()

auth_sidebar()

# 3. कोर टेक्निकल इंडिकेटर्स
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_supertrend(df, period=10, multiplier=4):
    high, low, close = df['High'].squeeze(), df['Low'].squeeze(), df['Close'].squeeze()
    tr1, tr2, tr3 = high - low, abs(high - close.shift(1)), abs(low - close.shift(1))
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(period).mean()
    hl2 = (high + low) / 2
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)
    in_uptrend = np.ones(len(df), dtype=bool)
    for i in range(1, len(df)):
        if close.iloc[i] > upperband.iloc[i-1]:
            in_uptrend[i] = True
        elif close.iloc[i] < lowerband.iloc[i-1]:
            in_uptrend[i] = False
        else:
            in_uptrend[i] = in_uptrend[i-1]
            if in_uptrend[i] and lowerband.iloc[i] < lowerband.iloc[i-1]:
                lowerband.iloc[i] = lowerband.iloc[i-1]
            if not in_uptrend[i] and upperband.iloc[i] > upperband.iloc[i-1]:
                upperband.iloc[i] = upperband.iloc[i-1]
    return pd.Series(in_uptrend, index=df.index), lowerband

def get_conviction_score(stock_3m, n_3m, vol_ratio, rsi_val, risk_metric):
    rs = stock_3m - n_3m
    pts_rs = 30 if rs >= 20 else (24 if rs >= 10 else (18 if rs >= 0 else 8))
    pts_vol = 25 if vol_ratio >= 2.5 else (20 if vol_ratio >= 1.8 else (15 if vol_ratio >= 1.2 else 8))
    pts_rr = 25 if risk_metric <= 10 else (20 if risk_metric <= 15 else (15 if risk_metric <= 20 else 10))
    pts_mom = 20 if 60 <= rsi_val <= 72 else (16 if 50 <= rsi_val < 60 else (12 if rsi_val > 72 else 6))
    return min(100, int(pts_rs + pts_vol + pts_rr + pts_mom))

@st.cache_data(ttl=86400)
def load_nifty500_symbols():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    csv_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        res = requests.get(csv_url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(res.text))
        return [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
    except Exception:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TRENT.NS', 'BEL.NS', 'HAL.NS', 'DIXON.NS']

# 4. डैशबोर्ड हेडर
st.title("🚀 Alpha Momentum Swing Scanner & Ranking Engine")
st.caption("3 Core A+ Trend Strategies | 100-Point Conviction Scoring | NIFTY 500")

nifty_df = yf.download('^NSEI', period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
nifty_close = nifty_df['Close'].squeeze()
nifty_ema200 = float(nifty_close.ewm(span=200, adjust=False).mean().iloc[-1])
nifty_cmp = float(nifty_close.iloc[-1])
nifty_3m_ret = ((nifty_cmp - float(nifty_close.iloc[-60])) / float(nifty_close.iloc[-60])) * 100
is_nifty_bullish = nifty_cmp > nifty_ema200

col1, col2, col3 = st.columns(3)
col1.metric("NIFTY 50 CMP", f"₹{nifty_cmp:,.2f}")
col2.metric("NIFTY 200 EMA", f"₹{nifty_ema200:,.2f}")
if is_nifty_bullish:
    col3.success("🟢 Market Regime: BULLISH (100% Capital Mode)")
else:
    col3.warning("🟡 Market Regime: CAUTION (50% Risk Mode)")

st.divider()

# 5. लाइव स्कैनर रनर
st.subheader("⚡ Live Market Scanner")
tab1, tab2, tab3 = st.tabs(["📦 Darvas Box Breakout", "🚀 MTF Supertrend Multiplier", "🔥 High-Tight Flag Contraction"])

symbols = load_nifty500_symbols()[:60]

if st.button("🔄 Run Scanner (Analyze Top Momentum Set)"):
    darvas_results, supertrend_results, flag_results = [], [], []
    progress_bar = st.progress(0)
    
    for idx, sym in enumerate(symbols):
        progress_bar.progress((idx + 1) / len(symbols))
        try:
            df = yf.download(sym, period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
            if len(df) < 100:
                continue

            c = df['Close'].squeeze()
            h = df['High'].squeeze()
            l = df['Low'].squeeze()
            v = df['Volume'].squeeze()

            cmp_price = float(c.iloc[-1])
            rsi_series = calc_rsi(c)
            rsi = float(rsi_series.iloc[-1])
            vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
            stock_3m_ret = ((cmp_price - float(c.iloc[-60])) / float(c.iloc[-60])) * 100
            
            # 1. Darvas Box Check
            box_high = float(h.iloc[-25:-1].max())
            box_low = float(l.iloc[-25:-1].min())
            if cmp_price > box_high and float(c.iloc[-2]) <= box_high and vol_ratio >= 1.5:
                risk_pct = round(((cmp_price - box_low) / cmp_price) * 100, 2)
                score = get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
                darvas_results.append({
                    "Stock": sym.replace(".NS", ""),
                    "Rank Score": score,
                    "CMP": round(cmp_price, 2),
                    "Box Breakout Level": round(box_high, 2),
                    "Stop Loss (Box Low)": round(box_low, 2),
                    "Risk %": risk_pct,
                    "RSI (14)": round(rsi, 1),
                    "Vol Surge": f"{round(vol_ratio, 2)}x"
                })

            # 2. MTF Supertrend Check
            st_trend, st_band = calc_supertrend(df, period=10, multiplier=4)
            ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
            if bool(st_trend.iloc[-1]) and cmp_price > ema50 and rsi >= 55:
                sl_level = float(st_band.iloc[-1])
                risk_pct = round(((cmp_price - sl_level) / cmp_price) * 100, 2)
                score = get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
                supertrend_results.append({
                    "Stock": sym.replace(".NS", ""),
                    "Rank Score": score,
                    "CMP": round(cmp_price, 2),
                    "Supertrend Support": round(sl_level, 2),
                    "50 EMA": round(ema50, 2),
                    "Risk %": risk_pct,
                    "RSI (14)": round(rsi, 1),
                    "Conviction": "High" if score >= 80 else "Moderate"
                })

            # 3. High Tight Flag Check
            six_m_low = float(l.iloc[-120:].min())
            rally_pct = ((cmp_price - six_m_low) / six_m_low) * 100
            if rally_pct >= 80:
                recent_range_pct = ((float(h.iloc[-15:].max()) - float(l.iloc[-15:].min())) / cmp_price) * 100
                if recent_range_pct <= 18:
                    score = get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, recent_range_pct)
                    flag_results.append({
                        "Stock": sym.replace(".NS", ""),
                        "Rank Score": score,
                        "CMP": round(cmp_price, 2),
                        "6M Rally %": f"+{round(rally_pct, 1)}%",
                        "Consolidation Range": f"{round(recent_range_pct, 1)}%",
                        "RSI (14)": round(rsi, 1),
                        "Vol Surge": f"{round(vol_ratio, 2)}x"
                    })
        except Exception:
            continue

    with tab1:
        if darvas_results:
            df_res = pd.DataFrame(darvas_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
            df_res.index = df_res.index + 1
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("Darvas Box Breakout रणनीति में फ़िलहाल कोई नया ब्रेकआउट नहीं मिला।")

    with tab2:
        if supertrend_results:
            df_res = pd.DataFrame(supertrend_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
            df_res.index = df_res.index + 1
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("MTF Supertrend में कोई एक्टिव सिग्नल नहीं मिला।")

    with tab3:
        if flag_results:
            df_res = pd.DataFrame(flag_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
            df_res.index = df_res.index + 1
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("High-Tight Flag Contraction में कोई स्टॉक नहीं मिला।")    pts_vol = 25 if vol_ratio >= 2.5 else (20 if vol_ratio >= 1.8 else (15 if vol_ratio >= 1.2 else 8))
    pts_rr = 25 if risk_metric <= 10 else (20 if risk_metric <= 15 else (15 if risk_metric <= 20 else 10))
    pts_mom = 20 if 60 <= rsi_val <= 72 else (16 if 50 <= rsi_val < 60 else (12 if rsi_val > 72 else 6))
    return min(100, int(pts_rs + pts_vol + pts_rr + pts_mom))

@st.cache_data(ttl=86400)
def load_nifty500_symbols():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    csv_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        res = requests.get(csv_url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(res.text))
        return [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
    except Exception:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TRENT.NS', 'BEL.NS', 'HAL.NS', 'DIXON.NS']

# 4. डैशबोर्ड हेडर
st.title("🚀 Alpha Momentum Swing Scanner & Ranking Engine")
st.caption("3 Core A+ Trend Strategies | 100-Point Conviction Scoring | NIFTY 500")

nifty_df = yf.download('^NSEI', period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
nifty_close = nifty_df['Close'].squeeze()
nifty_ema200 = float(nifty_close.ewm(span=200, adjust=False).mean().iloc[-1])
nifty_cmp = float(nifty_close.iloc[-1])
nifty_3m_ret = ((nifty_cmp - float(nifty_close.iloc[-60])) / float(nifty_close.iloc[-60])) * 100
is_nifty_bullish = nifty_cmp > nifty_ema200

col1, col2, col3 = st.columns(3)
col1.metric("NIFTY 50 CMP", f"₹{nifty_cmp:,.2f}")
col2.metric("NIFTY 200 EMA", f"₹{nifty_ema200:,.2f}")
if is_nifty_bullish:
    col3.success("🟢 Market Regime: BULLISH (100% Capital Mode)")
else:
    col3.warning("🟡 Market Regime: CAUTION (50% Risk Mode)")

st.divider()

# 5. लाइव स्कैनर रनर
st.subheader("⚡ Live Market Scanner")
tab1, tab2, tab3 = st.tabs(["📦 Darvas Box Breakout", "🚀 MTF Supertrend Multiplier", "🔥 High-Tight Flag Contraction"])

symbols = load_nifty500_symbols()[:60]

if st.button("🔄 Run Scanner (Analyze Top Momentum Set)"):
    darvas_results, supertrend_results, flag_results = [], [], []
    progress_bar = st.progress(0)
    
    for idx, sym in enumerate(symbols):
        progress_bar.progress((idx + 1) / len(symbols))
        try:
            df = yf.download(sym, period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
            if len(df) < 100:
                continue

            c = df['Close'].squeeze()
            h = df['High'].squeeze()
            l = df['Low'].squeeze()
            v = df['Volume'].squeeze()

            cmp_price = float(c.iloc[-1])
            rsi_series = calc_rsi(c)
            rsi = float(rsi_series.iloc[-1])
            vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
            stock_3m_ret = ((cmp_price - float(c.iloc[-60])) / float(c.iloc[-60])) * 100
            
            # 1. Darvas Box Check
            box_high = float(h.iloc[-25:-1].max())
            box_low = float(l.iloc[-25:-1].min())
            if cmp_price > box_high and float(c.iloc[-2]) <= box_high and vol_ratio >= 1.5:
                risk_pct = round(((cmp_price - box_low) / cmp_price) * 100, 2)
                score = get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
                darvas_results.append({
                    "Stock": sym.replace(".NS", ""),
                    "Rank Score": score,
                    "CMP": round(cmp_price, 2),
                    "Box Breakout Level": round(box_high, 2),
                    "Stop Loss (Box Low)": round(box_low, 2),
                    "Risk %": risk_pct,
                    "RSI (14)": round(rsi, 1),
                    "Vol Surge": f"{round(vol_ratio, 2)}x"
                })

            # 2. MTF Supertrend Check
            st_trend, st_band = calc_supertrend(df, period=10, multiplier=4)
            ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
            if bool(st_trend.iloc[-1]) and cmp_price > ema50 and rsi >= 55:
                sl_level = float(st_band.iloc[-1])
                risk_pct = round(((cmp_price - sl_level) / cmp_price) * 100, 2)
                score = get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
                supertrend_results.append({
                    "Stock": sym.replace(".NS", ""),
                    "Rank Score": score,
                    "CMP": round(cmp_price, 2),
                    "Supertrend Support": round(sl_level, 2),
                    "50 EMA": round(ema50, 2),
                    "Risk %": risk_pct,
                    "RSI (14)": round(rsi, 1),
                    "Conviction": "High" if score >= 80 else "Moderate"
                })

            # 3. High Tight Flag Check
            six_m_low = float(l.iloc[-120:].min())
            rally_pct = ((cmp_price - six_m_low) / six_m_low) * 100
            if rally_pct >= 80:
                recent_range_pct = ((float(h.iloc[-15:].max()) - float(l.iloc[-15:].min())) / cmp_price) * 100
                if recent_range_pct <= 18:
                    score = get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, recent_range_pct)
                    flag_results.append({
                        "Stock": sym.replace(".NS", ""),
                        "Rank Score": score,
                        "CMP": round(cmp_price, 2),
                        "6M Rally %": f"+{round(rally_pct, 1)}%",
                        "Consolidation Range": f"{round(recent_range_pct, 1)}%",
                        "RSI (14)": round(rsi, 1),
                        "Vol Surge": f"{round(vol_ratio, 2)}x"
                    })
        except Exception:
            continue

    with tab1:
        if darvas_results:
            df_res = pd.DataFrame(darvas_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
            df_res.index = df_res.index + 1
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("Darvas Box Breakout रणनीति में फ़िलहाल कोई नया ब्रेकआउट नहीं मिला।")

    with tab2:
        if supertrend_results:
            df_res = pd.DataFrame(supertrend_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
            df_res.index = df_res.index + 1
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("MTF Supertrend में कोई एक्टिव सिग्नल नहीं मिला।")

    with tab3:
        if flag_results:
            df_res = pd.DataFrame(flag_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
            df_res.index = df_res.index + 1
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("High-Tight Flag Contraction में कोई स्टॉक नहीं मिला।")
