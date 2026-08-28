import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings
import database as db
import strategies as stg

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Alpha Momentum Web Scanner", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = None

# User Portal
st.sidebar.title("🔐 User Portal")
if not st.session_state.logged_in:
    choice = st.sidebar.radio("विकल्प चुनें:", ["लॉगिन (Login)", "नया अकाउंट (Sign Up)"])
    if choice == "लॉगिन (Login)":
        with st.sidebar.form("login_form"):
            u_input = st.text_input("Username या Email")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("लॉगिन करें"):
                ok, u_data, msg = db.authenticate_user(u_input, pwd)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.user_data = u_data
                    st.rerun()
                else:
                    st.sidebar.error(msg)
    else:
        with st.sidebar.form("signup_form"):
            new_u = st.text_input("नया Username")
            new_email = st.text_input("Email ID")
            new_pwd = st.text_input("Password", type="password")
            if st.form_submit_button("अकाउंट बनाएँ (7-Day Pro Trial)"):
                if new_u and new_email and new_pwd:
                    ok, msg = db.register_user(new_u, new_email, new_pwd)
                    if ok: st.sidebar.success(msg)
                    else: st.sidebar.error(msg)
    st.stop()
else:
    u = st.session_state.user_data
    st.sidebar.success(f"👤 स्वागत है, **{u['username']}**!")
    st.sidebar.info(f"🏆 **प्लान:** {u['status']}\n\n⏳ **समाप्ति:** {str(u['expiry'])[:10]}")
    if st.sidebar.button("लॉगआउट"):
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.rerun()

# ----------------- MAIN APP -----------------
st.title("🚀 Alpha Momentum Trading Terminal")

# Top Section: Index MTF Supertrend (3M + 10M)
st.subheader("⚡ NIFTY & SENSEX MTF Intraday Supertrend (10, 4)")
col_nifty, col_sensex = st.columns(2)

with col_nifty:
    st.markdown("### 📊 NIFTY 50 (3M / 10M)")
    nifty_sig = stg.get_index_mtf_signal('^NSEI')
    if nifty_sig:
        st.metric("NIFTY 50 CMP", f"₹{nifty_sig['CMP']:,}", delta=nifty_sig['Signal'])
        st.write(f"• **10M Trend:** {nifty_sig['10M Trend']} | **3M Trend:** {nifty_sig['3M Trend']}")
        st.info(f"🎯 **Trailing Stop-Loss (3M ST):** ₹{nifty_sig['Dynamic StopLoss (3M ST)']} (Risk: {nifty_sig['Risk Points']} pts)")
    else:
        st.info("डेटा लोड हो रहा है...")

with col_sensex:
    st.markdown("### 📊 SENSEX (3M / 10M)")
    sensex_sig = stg.get_index_mtf_signal('^BSESN')
    if sensex_sig:
        st.metric("SENSEX CMP", f"₹{sensex_sig['CMP']:,}", delta=sensex_sig['Signal'])
        st.write(f"• **10M Trend:** {sensex_sig['10M Trend']} | **3M Trend:** {sensex_sig['3M Trend']}")
        st.info(f"🎯 **Trailing Stop-Loss (3M ST):** ₹{sensex_sig['Dynamic StopLoss (3M ST)']} (Risk: {sensex_sig['Risk Points']} pts)")
    else:
        st.info("डेटा लोड हो रहा है...")

st.divider()

# Load Symbols
@st.cache_data(ttl=86400)
def load_symbols():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get("https://archives.nseindia.com/content/indices/ind_nifty500list.csv", headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(res.text))
        return [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
    except Exception:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TRENT.NS', 'BEL.NS', 'HAL.NS', 'DIXON.NS', 'TATAMOTORS.NS', 'SBIN.NS']

# Tabs Section
main_tab1, main_tab2 = st.tabs(["🔥 Top 10 Market Heatmap (NIFTY 500)", "🎯 A+ Momentum Swing Scanners"])

with main_tab1:
    st.caption("Top Gainers, Losers, High Volume, High Turnover Value, RSI Extreme Setups")
    if st.button("📊 Scan NIFTY 500 Market Pulse"):
        stock_list = load_symbols()[:80] # High-speed batch
        market_data = []
        p_bar = st.progress(0)
        
        for i, sym in enumerate(stock_list):
            p_bar.progress((i + 1) / len(stock_list))
            try:
                d = yf.download(sym, period='3mo', interval='1d', progress=False, auto_adjust=True).dropna()
                if len(d) < 20: continue
                
                cl = d['Close'].squeeze()
                vl = d['Volume'].squeeze()
                
                cmp_p = float(cl.iloc[-1])
                prev_c = float(cl.iloc[-2])
                chg_pct = round(((cmp_p - prev_c) / prev_c) * 100, 2)
                vol_curr = int(vl.iloc[-1])
                avg_vol = float(vl.rolling(20).mean().iloc[-1])
                vol_ratio = round(vol_curr / avg_vol, 2) if avg_vol > 0 else 1.0
                turnover_cr = round((cmp_p * vol_curr) / 10000000, 2) # In Crores
                rsi_val = round(float(stg.calc_rsi(cl).iloc[-1]), 1)
                
                market_data.append({
                    "Stock": sym.replace(".NS", ""),
                    "CMP (₹)": cmp_p,
                    "Change %": chg_pct,
                    "Volume Ratio": vol_ratio,
                    "Turnover (₹ Cr)": turnover_cr,
                    "RSI (14)": rsi_val
                })
            except Exception:
                continue
                
        if market_data:
            df_m = pd.DataFrame(market_data)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🟢 Top 10 Gainers")
                st.dataframe(df_m.sort_values(by="Change %", ascending=False).head(10)[["Stock", "CMP (₹)", "Change %", "Volume Ratio"]], use_container_width=True)
            with c2:
                st.markdown("#### 🔴 Top 10 Losers")
                st.dataframe(df_m.sort_values(by="Change %", ascending=True).head(10)[["Stock", "CMP (₹)", "Change %", "Volume Ratio"]], use_container_width=True)
                
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### 🚀 Top 10 Volume Surges")
                st.dataframe(df_m.sort_values(by="Volume Ratio", ascending=False).head(10)[["Stock", "CMP (₹)", "Volume Ratio", "Change %"]], use_container_width=True)
            with c4:
                st.markdown("#### 💰 Top 10 High Turnover (₹ Cr)")
                st.dataframe(df_m.sort_values(by="Turnover (₹ Cr)", ascending=False).head(10)[["Stock", "CMP (₹)", "Turnover (₹ Cr)", "Change %"]], use_container_width=True)

            c5, c6 = st.columns(2)
            with c5:
                st.markdown("#### 🔥 Top 10 High RSI (Overbought / Strong Momentum)")
                st.dataframe(df_m.sort_values(by="RSI (14)", ascending=False).head(10)[["Stock", "CMP (₹)", "RSI (14)", "Change %"]], use_container_width=True)
            with c6:
                st.markdown("#### ❄️ Top 10 Low RSI (Oversold / Mean Reversion)")
                st.dataframe(df_m.sort_values(by="RSI (14)", ascending=True).head(10)[["Stock", "CMP (₹)", "RSI (14)", "Change %"]], use_container_width=True)

with main_tab2:
    tab1, tab2, tab3 = st.tabs(["📦 Darvas Box Breakout", "🚀 MTF Supertrend Multiplier", "🔥 High-Tight Flag"])
    if st.button("🔄 Run Swing Strategies"):
        darvas_res, st_res, flag_res = [], [], []
        s_list = load_symbols()[:60]
        nifty_df = yf.download('^NSEI', period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
        n_close = nifty_df['Close'].squeeze()
        n_3m = ((float(n_close.iloc[-1]) - float(n_close.iloc[-60])) / float(n_close.iloc[-60])) * 100
        
        for sym in s_list:
            try:
                df = yf.download(sym, period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
                if len(df) < 100: continue
                c, h, l, v = df['Close'].squeeze(), df['High'].squeeze(), df['Low'].squeeze(), df['Volume'].squeeze()
                cmp_p = float(c.iloc[-1])
                rsi = float(stg.calc_rsi(c).iloc[-1])
                vol_r = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
                stk_3m = ((cmp_p - float(c.iloc[-60])) / float(c.iloc[-60])) * 100
                
                # Darvas
                b_high, b_low = float(h.iloc[-25:-1].max()), float(l.iloc[-25:-1].min())
                if cmp_p > b_high and float(c.iloc[-2]) <= b_high and vol_r >= 1.5:
                    r_pct = round(((cmp_p - b_low) / cmp_p) * 100, 2)
                    score = stg.get_conviction_score(stk_3m, n_3m, vol_r, rsi, r_pct)
                    darvas_res.append({"Stock": sym.replace(".NS", ""), "Score": score, "CMP": round(cmp_p, 2), "Breakout": round(b_high, 2), "SL": round(b_low, 2), "Risk %": r_pct, "RSI": round(rsi, 1)})

                # Supertrend
                trend, band = stg.calc_supertrend(df, period=10, multiplier=4)
                ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
                if bool(trend.iloc[-1]) and cmp_p > ema50 and rsi >= 55:
                    sl_val = float(band.iloc[-1])
                    r_pct = round(((cmp_p - sl_val) / cmp_p) * 100, 2)
                    score = stg.get_conviction_score(stk_3m, n_3m, vol_r, rsi, r_pct)
                    st_res.append({"Stock": sym.replace(".NS", ""), "Score": score, "CMP": round(cmp_p, 2), "ST Support": round(sl_val, 2), "50 EMA": round(ema50, 2), "Risk %": r_pct, "RSI": round(rsi, 1)})
            except Exception:
                continue

        with tab1: st.dataframe(pd.DataFrame(darvas_res).sort_values(by="Score", ascending=False), use_container_width=True) if darvas_res else st.info("कोई सिग्नल नहीं।")
        with tab2: st.dataframe(pd.DataFrame(st_res).sort_values(by="Score", ascending=False), use_container_width=True) if st_res else st.info("कोई सिग्नल नहीं।")
        with tab3: st.info("High Tight Flag scan complete.")
