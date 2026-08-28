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

# Top Section: Index MTF Supertrend
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
        st.info("मार्केट डेटा लोड हो रहा है...")

with col_sensex:
    st.markdown("### 📊 SENSEX (3M / 10M)")
    sensex_sig = stg.get_index_mtf_signal('^BSESN')
    if sensex_sig:
        st.metric("SENSEX CMP", f"₹{sensex_sig['CMP']:,}", delta=sensex_sig['Signal'])
        st.write(f"• **10M Trend:** {sensex_sig['10M Trend']} | **3M Trend:** {sensex_sig['3M Trend']}")
        st.info(f"🎯 **Trailing Stop-Loss (3M ST):** ₹{sensex_sig['Dynamic StopLoss (3M ST)']} (Risk: {sensex_sig['Risk Points']} pts)")
    else:
        st.info("मार्केट डेटा लोड हो रहा है...")

st.divider()

# Market Regime Banner
nifty_df = yf.download('^NSEI', period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
nifty_close = nifty_df['Close'].squeeze()
nifty_ema200 = float(nifty_close.ewm(span=200, adjust=False).mean().iloc[-1])
nifty_cmp = float(nifty_close.iloc[-1])
nifty_3m_ret = ((nifty_cmp - float(nifty_close.iloc[-60])) / float(nifty_close.iloc[-60])) * 100

col1, col2, col3 = st.columns(3)
col1.metric("NIFTY 50 CMP", f"₹{nifty_cmp:,.2f}")
col2.metric("NIFTY 200 EMA", f"₹{nifty_ema200:,.2f}")
col3.success("🟢 Market Regime: BULLISH (100% Capital Mode)") if nifty_cmp > nifty_ema200 else col3.warning("🟡 Market Regime: CAUTION (50% Risk Mode)")

st.divider()

# Symbol Fetcher
@st.cache_data(ttl=86400)
def load_symbols():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get("https://archives.nseindia.com/content/indices/ind_nifty500list.csv", headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(res.text))
        return [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
    except Exception:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TRENT.NS', 'BEL.NS', 'HAL.NS', 'DIXON.NS', 'TATAMOTORS.NS', 'SBIN.NS', '360ONE.NS', 'AJANTPHARM.NS', 'BEML.NS', 'ASAHIINDIA.NS', 'ARE&M.NS', 'ACMESOLAR.NS', 'ADANIENT.NS', 'ABSLAMC.NS', 'ANURAS.NS', 'ASTRAL.NS']

main_tab1, main_tab2 = st.tabs(["🎯 A+ Momentum Swing Scanners", "🔥 Top 10 Market Heatmap (NIFTY 500)"])

# TAB 1: 3 CORE SWING SCANNERS
with main_tab1:
    st.subheader("⚡ Live Market Scanner")
    tab1, tab2, tab3 = st.tabs(["📦 Darvas Box Breakout", "🚀 MTF Supertrend Multiplier", "🔥 High-Tight Flag Contraction"])
    
    symbols = load_symbols()[:60]
    
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
                rsi = float(stg.calc_rsi(c).iloc[-1])
                vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
                stock_3m_ret = ((cmp_price - float(c.iloc[-60])) / float(c.iloc[-60])) * 100
                
                # 1. Darvas Box Strategy
                box_high = float(h.iloc[-25:-1].max())
                box_low = float(l.iloc[-25:-1].min())
                if cmp_price > box_high and float(c.iloc[-2]) <= box_high and vol_ratio >= 1.5:
                    risk_pct = round(((cmp_price - box_low) / cmp_price) * 100, 2)
                    score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
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

                # 2. MTF Supertrend Multiplier Strategy
                st_trend, st_band = stg.calc_supertrend(df, period=10, multiplier=4)
                ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
                if bool(st_trend.iloc[-1]) and cmp_price > ema50 and rsi >= 55:
                    sl_level = float(st_band.iloc[-1])
                    risk_pct = round(((cmp_price - sl_level) / cmp_price) * 100, 2)
                    score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
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

                # 3. High Tight Flag Contraction Strategy
                six_m_low = float(l.iloc[-120:].min())
                rally_pct = ((cmp_price - six_m_low) / six_m_low) * 100
                if rally_pct >= 80:
                    recent_range_pct = ((float(h.iloc[-15:].max()) - float(l.iloc[-15:].min())) / cmp_price) * 100
                    if recent_range_pct <= 18:
                        score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, recent_range_pct)
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

# TAB 2: TOP 10 MARKET HEATMAP
with main_tab2:
    st.caption("Top Gainers, Losers, High Volume, High Turnover Value, RSI Extreme Setups")
    if st.button("📊 Scan NIFTY 500 Market Pulse"):
        stock_list = load_symbols()[:80]
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
                turnover_cr = round((cmp_p * vol_curr) / 10000000, 2)
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
                st.dataframe(df_m.sort_values(by="Change %", ascending=False).head(10)[["Stock", "CMP (₹)", "Change %", "Volume Ratio"]].reset_index(drop=True), use_container_width=True)
            with c2:
                st.markdown("#### 🔴 Top 10 Losers")
                st.dataframe(df_m.sort_values(by="Change %", ascending=True).head(10)[["Stock", "CMP (₹)", "Change %", "Volume Ratio"]].reset_index(drop=True), use_container_width=True)
                
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### 🚀 Top 10 Volume Surges")
                st.dataframe(df_m.sort_values(by="Volume Ratio", ascending=False).head(10)[["Stock", "CMP (₹)", "Volume Ratio", "Change %"]].reset_index(drop=True), use_container_width=True)
            with c4:
                st.markdown("#### 💰 Top 10 High Turnover (₹ Cr)")
                st.dataframe(df_m.sort_values(by="Turnover (₹ Cr)", ascending=False).head(10)[["Stock", "CMP (₹)", "Turnover (₹ Cr)", "Change %"]].reset_index(drop=True), use_container_width=True)

            c5, c6 = st.columns(2)
            with c5:
                st.markdown("#### 🔥 Top 10 High RSI")
                st.dataframe(df_m.sort_values(by="RSI (14)", ascending=False).head(10)[["Stock", "CMP (₹)", "RSI (14)", "Change %"]].reset_index(drop=True), use_container_width=True)
            with c6:
                st.markdown("#### ❄️ Top 10 Low RSI")
                st.dataframe(df_m.sort_values(by="RSI (14)", ascending=True).head(10)[["Stock", "CMP (₹)", "RSI (14)", "Change %"]].reset_index(drop=True), use_container_width=True)
