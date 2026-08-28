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
        auth_choice = st.sidebar.radio("चुनें:", ["लॉगिन (Login)", "नया अकाउंट (Sign Up)"])
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
                        st.sidebar.warning("सभी फ़ील्ड भरें!")
    else:
        u = st.session_state.user_data
        st.sidebar.success(f"👤 स्वागत है, **{u['username']}**!")
        st.sidebar.info(f"💳 प्लान: **{u['status']}**\n\n⏳ समाप्ति: {u['expiry'][:10]}")
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
    upperband, lowerband = hl2 + (multiplier * atr), hl2 - (multiplier * atr)
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
    return min(100, pts_rs + pts_vol + pts_rr + pts_mom)

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
@st.cache_data(ttl=3600)
def run_live_scan(symbol_list):
    sig_darvas, sig_mtf, sig_52w = [], [], []
    batch_size = 50
    total_b = (len(symbol_list) + batch_size - 1) // batch_size
    
    for b in range(total_b):
        batch = symbol_list[b*batch_size : (b+1)*batch_size]
        try:
            d_d = yf.download(batch, period='2y', interval='1d', group_by='ticker', progress=False, auto_adjust=True)
            d_w = yf.download(batch, period='2y', interval='1wk', group_by='ticker', progress=False, auto_adjust=True)
        except Exception:
            continue
            
        for sym in batch:
            s_name = sym.replace('.NS', '')
            try:
                df_d = d_d[sym].dropna() if len(batch) > 1 else d_d.dropna()
                df_w = d_w[sym].dropna() if len(batch) > 1 else d_w.dropna()
                if len(df_d) < 250 or len(df_w) < 50:
                    continue
                
                close_d, high_d, low_d, vol_d = df_d['Close'].squeeze(), df_d['High'].squeeze(), df_d['Low'].squeeze(), df_d['Volume'].squeeze()
                cmp, prev_c = float(close_d.iloc[-1]), float(close_d.iloc[-2])
                ema200 = float(close_d.ewm(span=200, adjust=False).mean().iloc[-1])
                
                st_3m = ((cmp - float(close_d.iloc[-60])) / float(close_d.iloc[-60])) * 100
                vol_avg = float(vol_d.iloc[-21:-1].mean())
                v_rat = float(vol_d.iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
                rsi = calc_rsi(close_d, 14)
                rsi_l = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50
                
                st_w, _ = calc_supertrend(df_w, 10, 4)
                st_w_ok = bool(st_w.iloc[-1])
                st_d, lband_d = calc_supertrend(df_d, 10, 4)
                
                # 1. Darvas Box
                h70, l40 = float(high_d.iloc[-71:-1].max()), float(low_d.iloc[-41:-1].min())
                dist_l40 = ((cmp - l40) / cmp) * 100
                if (cmp > h70) and (prev_c <= h70):
                    sc = get_conviction_score(st_3m, nifty_3m_ret, v_rat, rsi_l, dist_l40)
                    sig_darvas.append({
                        "Rank Score": sc, "Stock": s_name, "CMP": cmp, "70D High": h70, 
                        "Trail Low": l40, "-15% SL": round(cmp*0.85, 2), "Vol Ratio": f"{v_rat:.1f}x", "RS vs Nifty": f"{st_3m - nifty_3m_ret:+.1f}%"
                    })
                
                # 2. MTF Supertrend
                flip = (not st_d.iloc[-2]) and (st_d.iloc[-1])
                dist_st = ((cmp - float(lband_d.iloc[-1])) / cmp) * 100
                if flip and st_w_ok and (cmp > ema200):
                    sc = get_conviction_score(st_3m, nifty_3m_ret, v_rat, rsi_l, dist_st)
                    sig_mtf.append({
                        "Rank Score": sc, "Stock": s_name, "CMP": cmp, "200 EMA": ema200, 
                        "ST Support": round(float(lband_d.iloc[-1]), 2), "-15% SL": round(cmp*0.85, 2), "Vol Ratio": f"{v_rat:.1f}x", "RS vs Nifty": f"{st_3m - nifty_3m_ret:+.1f}%"
                    })
                
                # 3. 52W High Base
                h52, h3m, l3m = float(high_d.iloc[-251:-1].max()), float(high_d.iloc[-61:-1].max()), float(low_d.iloc[-61:-1].min())
                bw = ((h3m - l3m) / l3m) * 100
                if (bw <= 20) and (cmp >= (h52 * 0.98)) and (cmp > ema200) and st_w_ok:
                    if (prev_c < h52 * 0.98) or (cmp > h3m and prev_c <= h3m):
                        sc = get_conviction_score(st_3m, nifty_3m_ret, v_rat, rsi_l, bw)
                        sig_52w.append({
                            "Rank Score": sc, "Stock": s_name, "CMP": cmp, "52W High": h52, 
                            "Base Width": f"{bw:.1f}%", "-15% SL": round(cmp*0.85, 2), "Vol Ratio": f"{v_rat:.1f}x", "RS vs Nifty": f"{st_3m - nifty_3m_ret:+.1f}%"
                        })
            except Exception:
                continue
    return sig_darvas, sig_mtf, sig_52w

symbols = load_nifty500_symbols()
with st.spinner("लाइव सिग्नल्स लोड हो रहे हैं..."):
    d_res, m_res, b_res = run_live_scan(symbols)

# 6. पेवॉल टेबल रेंडरिंग
def render_paywalled_table(sig_list, title):
    if not sig_list:
        st.info(f"{title} में आज कोई नया सिग्नल नहीं मिला।")
        return
    
    df = pd.DataFrame(sig_list).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
    df.index += 1
    df.index.name = "Rank"
    
    is_pro = st.session_state.logged_in and st.session_state.user_data.get('is_active_pro', False)
    
    if is_pro:
        st.dataframe(df.head(10), use_container_width=True)
    else:
        free_preview = df.head(1).copy()
        st.dataframe(free_preview, use_container_width=True)
        st.warning(f"🔒 बाकी के **{min(len(df), 10) - 1} प्रीमियम सिग्नल्स लॉक्ड हैं**।")
        st.markdown("""
        <div style="background-color: #1e293b; padding: 18px; border-radius: 8px; border: 1px solid #334155; margin-top: 10px;">
            <h4 style="margin: 0; color: #38bdf8;">👑 Pro Membership में अनलॉक करें:</h4>
            <ul style="margin: 8px 0; color: #cbd5e1;">
                <li>तीनों स्कैनर्स के पूरे <b>Top 10 Ranked Signals</b></li>
                <li>सटीक <b>-15% Disaster SL</b> और <b>Trailing Exits</b></li>
                <li><b>VIP Telegram Real-Time Alerts</b> (मार्केट बंद होते ही सीधे अलर्ट)</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📦 Darvas Box Breakout", "🚀 MTF Supertrend Rider", "🎯 52W High Base Breakout"])

with tab1:
    st.subheader("Darvas Box Breakouts (70D High)")
    render_paywalled_table(d_res, "Darvas Box")

with tab2:
    st.subheader("MTF Supertrend Riders (10,4)")
    render_paywalled_table(m_res, "MTF Supertrend")

with tab3:
    st.subheader("52-Week High Base Breakouts")
    render_paywalled_table(b_res, "52W High Base")
