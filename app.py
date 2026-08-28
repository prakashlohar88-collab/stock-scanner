import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings
import database as db
import strategies as stg

warnings.filterwarnings('ignore')

# 1. पेज सेटअप
st.set_page_config(page_title="Alpha Momentum Web Scanner", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = None

# 2. यूजर ऑथेंटिकेशन
def auth_sidebar():
    st.sidebar.title("🔐 User Portal")
    if not st.session_state.logged_in:
        auth_choice = st.sidebar.radio("विकल्प चुनें:", ["लॉगिन (Login)", "नया अकाउंट (Sign Up)"])
        if auth_choice == "लॉगिन (Login)":
            with st.sidebar.form("login_form"):
                u_input = st.text_input("Username या Email")
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("लॉगिन करें"):
                    success, u_data, msg = db.authenticate_user(u_input, pwd)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_data = u_data
                        st.rerun()
                    else:
                        st.sidebar.error(msg)
        elif auth_choice == "नया अकाउंट (Sign Up)":
            with st.sidebar.form("signup_form"):
                new_u = st.text_input("नया Username")
                new_email = st.text_input("Email ID")
                new_pwd = st.text_input("Password", type="password")
                if st.form_submit_button("अकाउंट बनाएँ (7-Day Pro Trial)"):
                    if new_u and new_email and new_pwd:
                        ok, msg = db.register_user(new_u, new_email, new_pwd)
                        if ok:
                            st.sidebar.success(msg)
                        else:
                            st.sidebar.error(msg)
                    else:
                        st.sidebar.warning("सभी फ़ील्ड भरें!")
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

# 3. सिंबल लोडर
@st.cache_data(ttl=86400)
def load_nifty500_symbols():
    headers = {'User-Agent': 'Mozilla/5.0'}
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

col1, col2, col3 = st.columns(3)
col1.metric("NIFTY 50 CMP", f"₹{nifty_cmp:,.2f}")
col2.metric("NIFTY 200 EMA", f"₹{nifty_ema200:,.2f}")
col3.success("🟢 Market Regime: BULLISH") if nifty_cmp > nifty_ema200 else col3.warning("🟡 Market Regime: CAUTION")

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

            c, h, l, v = df['Close'].squeeze(), df['High'].squeeze(), df['Low'].squeeze(), df['Volume'].squeeze()
            cmp_price = float(c.iloc[-1])
            rsi = float(stg.calc_rsi(c).iloc[-1])
            vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
            stock_3m_ret = ((cmp_price - float(c.iloc[-60])) / float(c.iloc[-60])) * 100
            
            # Darvas Strategy
            box_high, box_low = float(h.iloc[-25:-1].max()), float(l.iloc[-25:-1].min())
            if cmp_price > box_high and float(c.iloc[-2]) <= box_high and vol_ratio >= 1.5:
                risk_pct = round(((cmp_price - box_low) / cmp_price) * 100, 2)
                score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
                darvas_results.append({"Stock": sym.replace(".NS", ""), "Rank Score": score, "CMP": round(cmp_price, 2), "Box Breakout Level": round(box_high, 2), "Stop Loss": round(box_low, 2), "Risk %": risk_pct, "RSI": round(rsi, 1), "Vol Surge": f"{round(vol_ratio, 2)}x"})

            # Supertrend Strategy
            st_trend, st_band = stg.calc_supertrend(df, period=10, multiplier=4)
            ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
            if bool(st_trend.iloc[-1]) and cmp_price > ema50 and rsi >= 55:
                sl_level = float(st_band.iloc[-1])
                risk_pct = round(((cmp_price - sl_level) / cmp_price) * 100, 2)
                score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, risk_pct)
                supertrend_results.append({"Stock": sym.replace(".NS", ""), "Rank Score": score, "CMP": round(cmp_price, 2), "Supertrend Support": round(sl_level, 2), "50 EMA": round(ema50, 2), "Risk %": risk_pct, "RSI": round(rsi, 1)})

            # High Tight Flag Strategy
            six_m_low = float(l.iloc[-120:].min())
            rally_pct = ((cmp_price - six_m_low) / six_m_low) * 100
            if rally_pct >= 80:
                recent_range_pct = ((float(h.iloc[-15:].max()) - float(l.iloc[-15:].min())) / cmp_price) * 100
                if recent_range_pct <= 18:
                    score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, recent_range_pct)
                    flag_results.append({"Stock": sym.replace(".NS", ""), "Rank Score": score, "CMP": round(cmp_price, 2), "6M Rally %": f"+{round(rally_pct, 1)}%", "Consolidation Range": f"{round(recent_range_pct, 1)}%", "RSI": round(rsi, 1), "Vol Surge": f"{round(vol_ratio, 2)}x"})
        except Exception:
            continue

    with tab1:
        st.dataframe(pd.DataFrame(darvas_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True), use_container_width=True) if darvas_results else st.info("कोई नया Darvas ब्रेकआउट नहीं मिला।")

    with tab2:
        st.dataframe(pd.DataFrame(supertrend_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True), use_container_width=True) if supertrend_results else st.info("कोई एक्टिव Supertrend सिग्नल नहीं मिला।")

    with tab3:
        st.dataframe(pd.DataFrame(flag_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True), use_container_width=True) if flag_results else st.info("कोई High-Tight Flag स्टॉक नहीं मिला।")
