import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings
import database as db
import strategies as stg

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Alpha Momentum - Technical Analytics", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Clean Mobile View
st.markdown("""
    <style>
    .footer-text { font-size: 12px; color: #888; text-align: center; margin-top: 50px; }
    .disclaimer-box { background-color: #2b2b2b; padding: 12px; border-radius: 8px; border-left: 5px solid #ff9800; font-size: 13px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = None

# --- SIDEBAR: USER PORTAL ---
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
    st.sidebar.info(f"🏆 **प्लान:** {u['status']}\n\n⏳ **वैधता (Expiry):** {str(u['expiry'])[:10]}")
    if st.sidebar.button("लॉगआउट (Logout)"):
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.rerun()

# --- MANDATORY REGULATORY DISCLAIMER HEADER ---
st.markdown("""
<div class="disclaimer-box">
⚠️ <b>महत्वपूर्ण अस्वीकरण (Regulatory Disclaimer):</b> यह प्लेटफ़ॉर्म केवल <b>शैक्षणिक और तकनीकी अध्ययन (Educational & Technical Analysis)</b> के लिए एक स्वचालित डेटा स्कैनर है। हम SEBI-पंजीकृत रिसर्च एनालिस्ट या एडवाइजर नहीं हैं। यहाँ प्रदर्शित कोई भी डेटा, स्कोर या स्तर शेयर खरीदने या बेचने की सलाह (Buy/Sell Recommendation) नहीं है। कोई भी वित्तीय निर्णय लेने से पहले अपने वित्तीय सलाहकार से परामर्श लें।
</div>
""", unsafe_allow_html=True)

# ----------------- MAIN TERMINAL -----------------
st.title("📊 Alpha Momentum Technical Analytics")
st.caption("Automated Technical Rule-Based Screener & Relative Strength Engine")

# Index MTF Section
st.subheader("⚡ NIFTY & SENSEX MTF Technical Trend (10, 4)")
col_nifty, col_sensex = st.columns(2)

with col_nifty:
    st.markdown("### 📊 NIFTY 50 (3M / 10M)")
    nifty_sig = stg.get_index_mtf_signal('^NSEI')
    if nifty_sig:
        st.metric("NIFTY 50 CMP", f"₹{nifty_sig['CMP']:,}", delta=nifty_sig['Signal'])
        st.write(f"• **10M Trend:** {nifty_sig['10M Trend']} | **3M Trend:** {nifty_sig['3M Trend']}")
        st.info(f"🎯 **Technical Pivot/Support (3M ST):** ₹{nifty_sig['Dynamic StopLoss (3M ST)']} (Diff: {nifty_sig['Risk Points']} pts)")
    else:
        st.info("मार्केट डेटा लोड हो रहा है...")

with col_sensex:
    st.markdown("### 📊 SENSEX (3M / 10M)")
    sensex_sig = stg.get_index_mtf_signal('^BSESN')
    if sensex_sig:
        st.metric("SENSEX CMP", f"₹{sensex_sig['CMP']:,}", delta=sensex_sig['Signal'])
        st.write(f"• **10M Trend:** {sensex_sig['10M Trend']} | **3M Trend:** {sensex_sig['3M Trend']}")
        st.info(f"🎯 **Technical Pivot/Support (3M ST):** ₹{sensex_sig['Dynamic StopLoss (3M ST)']} (Diff: {sensex_sig['Risk Points']} pts)")
    else:
        st.info("मार्केट डेटा लोड हो रहा है...")

st.divider()

# Market Regime
nifty_df = yf.download('^NSEI', period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
nifty_close = nifty_df['Close'].squeeze()
nifty_ema200 = float(nifty_close.ewm(span=200, adjust=False).mean().iloc[-1])
nifty_cmp = float(nifty_close.iloc[-1])
nifty_3m_ret = ((nifty_cmp - float(nifty_close.iloc[-60])) / float(nifty_close.iloc[-60])) * 100

col1, col2, col3 = st.columns(3)
col1.metric("NIFTY 50 CMP", f"₹{nifty_cmp:,.2f}")
col2.metric("NIFTY 200 EMA", f"₹{nifty_ema200:,.2f}")

if nifty_cmp > nifty_ema200:
    col3.success("🟢 Market Regime: ABOVE 200 EMA (Broad Uptrend)")
else:
    col3.warning("🟡 Market Regime: BELOW 200 EMA (Cautionary Phase)")

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
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TRENT.NS', 'BEL.NS', 'HAL.NS', 'DIXON.NS', 'TATAMOTORS.NS', 'SBIN.NS']

main_tab1, main_tab2, main_tab3 = st.tabs(["🎯 Rule-Based Technical Scanners", "🔥 Market Heatmap & Volume", "📜 Legal & Policies"])

# TAB 1: SCANNERS
with main_tab1:
    st.caption("Scans stocks based on predefined price action and mathematical filters.")
    tab1, tab2, tab3 = st.tabs(["📦 25-Day Consolidation Range", "🚀 Multi-Timeframe Supertrend", "🔥 Price Expansion Filter"])
    
    symbols = load_symbols()[:60]
    
    if st.button("🔄 Run Rule Engine"):
        darvas_results, supertrend_results, flag_results = [], [], []
        progress_bar = st.progress(0)
        
        for idx, sym in enumerate(symbols):
            progress_bar.progress((idx + 1) / len(symbols))
            try:
                df = yf.download(sym, period='1y', interval='1d', progress=False, auto_adjust=True).dropna()
                if len(df) < 100: continue

                c, h, l, v = df['Close'].squeeze(), df['High'].squeeze(), df['Low'].squeeze(), df['Volume'].squeeze()
                cmp_price = float(c.iloc[-1])
                rsi = float(stg.calc_rsi(c).iloc[-1])
                vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
                stock_3m_ret = ((cmp_price - float(c.iloc[-60])) / float(c.iloc[-60])) * 100
                
                # Darvas
                box_high = float(h.iloc[-25:-1].max())
                box_low = float(l.iloc[-25:-1].min())
                if cmp_price > box_high and float(c.iloc[-2]) <= box_high and vol_ratio >= 1.5:
                    sl_dist = round(((cmp_price - box_low) / cmp_price) * 100, 2)
                    score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, sl_dist)
                    darvas_results.append({
                        "Stock": sym.replace(".NS", ""),
                        "Strength Score": score,
                        "CMP (₹)": round(cmp_price, 2),
                        "Resistance Level": round(box_high, 2),
                        "Support Base": round(box_low, 2),
                        "SL Distance %": f"{sl_dist}%",
                        "RSI (14)": round(rsi, 1),
                        "Vol Ratio": f"{round(vol_ratio, 2)}x"
                    })

                # Supertrend
                st_trend, st_band = stg.calc_supertrend(df, period=10, multiplier=4)
                ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
                if bool(st_trend.iloc[-1]) and cmp_price > ema50 and rsi >= 55:
                    sl_level = float(st_band.iloc[-1])
                    sl_dist = round(((cmp_price - sl_level) / cmp_price) * 100, 2)
                    score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, sl_dist)
                    supertrend_results.append({
                        "Stock": sym.replace(".NS", ""),
                        "Strength Score": score,
                        "CMP (₹)": round(cmp_price, 2),
                        "ST Support": round(sl_level, 2),
                        "50 EMA": round(ema50, 2),
                        "SL Distance %": f"{sl_dist}%",
                        "RSI (14)": round(rsi, 1)
                    })

                # Expansion Filter
                six_m_low = float(l.iloc[-120:].min())
                rally_pct = ((cmp_price - six_m_low) / six_m_low) * 100
                if rally_pct >= 80:
                    recent_range_pct = ((float(h.iloc[-15:].max()) - float(l.iloc[-15:].min())) / cmp_price) * 100
                    if recent_range_pct <= 18:
                        score = stg.get_conviction_score(stock_3m_ret, nifty_3m_ret, vol_ratio, rsi, recent_range_pct)
                        flag_results.append({
                            "Stock": sym.replace(".NS", ""),
                            "Strength Score": score,
                            "CMP (₹)": round(cmp_price, 2),
                            "6M Trend %": f"+{round(rally_pct, 1)}%",
                            "Base Range %": f"{round(recent_range_pct, 1)}%",
                            "RSI (14)": round(rsi, 1),
                            "Vol Ratio": f"{round(vol_ratio, 2)}x"
                        })
            except Exception:
                continue

        with tab1:
            st.dataframe(pd.DataFrame(darvas_results).sort_values(by="Strength Score", ascending=False).reset_index(drop=True), use_container_width=True) if darvas_results else st.info("कोई स्टॉक फ़िल्टर नहीं हुआ।")
        with tab2:
            st.dataframe(pd.DataFrame(supertrend_results).sort_values(by="Strength Score", ascending=False).reset_index(drop=True), use_container_width=True) if supertrend_results else st.info("कोई स्टॉक फ़िल्टर नहीं हुआ।")
        with tab3:
            st.dataframe(pd.DataFrame(flag_results).sort_values(by="Strength Score", ascending=False).reset_index(drop=True), use_container_width=True) if flag_results else st.info("कोई स्टॉक फ़िल्टर नहीं हुआ।")

# TAB 2: MARKET HEATMAP
with main_tab2:
    st.caption("Standard Market Statistics & Price Distribution")
    if st.button("📊 Scan Market Pulse"):
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
            except Exception: continue
                
        if market_data:
            df_m = pd.DataFrame(market_data)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🟢 Top Gainers (%)")
                st.dataframe(df_m.sort_values(by="Change %", ascending=False).head(10)[["Stock", "CMP (₹)", "Change %", "Volume Ratio"]].reset_index(drop=True), use_container_width=True)
            with c2:
                st.markdown("#### 🔴 Top Decliners (%)")
                st.dataframe(df_m.sort_values(by="Change %", ascending=True).head(10)[["Stock", "CMP (₹)", "Change %", "Volume Ratio"]].reset_index(drop=True), use_container_width=True)
                
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### 🚀 Volume Multipliers")
                st.dataframe(df_m.sort_values(by="Volume Ratio", ascending=False).head(10)[["Stock", "CMP (₹)", "Volume Ratio", "Change %"]].reset_index(drop=True), use_container_width=True)
            with c4:
                st.markdown("#### 💰 High Turnover (₹ Cr)")
                st.dataframe(df_m.sort_values(by="Turnover (₹ Cr)", ascending=False).head(10)[["Stock", "CMP (₹)", "Turnover (₹ Cr)", "Change %"]].reset_index(drop=True), use_container_width=True)

# TAB 3: LEGAL, POLICIES & TERMS (RAZORPAY & SEBI MANDATORY)
with main_tab3:
    st.markdown("### 📑 Policies & Legal Information")
    policy_choice = st.selectbox("दस्तावेज़ चुनें:", ["Terms & Conditions", "Privacy Policy", "Refund & Cancellation Policy", "About & Contact"])
    
    if policy_choice == "Terms & Conditions":
        st.write("""
        **1. Acceptance of Terms:** By accessing this platform, you agree that all tools and analytical calculations provided are strictly for personal, educational, and mathematical screening purposes.
        \n**2. No Investment Advice:** This website does not offer stock tips, advisory services, portfolio management, or guaranteed returns. We are not registered with SEBI as an Investment Adviser (IA) or Research Analyst (RA).
        \n**3. Limitation of Liability:** Trading in capital markets involves significant financial risk. The platform owners will not be held liable for any trading losses incurred based on the use of these technical screeners.
        """)
    elif policy_choice == "Privacy Policy":
        st.write("""
        We respect your privacy. User email IDs and authentication credentials are stored securely using encrypted standards and are never sold or shared with third-party advertising networks.
        """)
    elif policy_choice == "Refund & Cancellation Policy":
        st.write("""
        We offer a 7-day free trial for users to evaluate all platform features. Once a paid subscription is activated, fees are non-refundable. Subscriptions can be canceled at any time to avoid renewal.
        """)
    elif policy_choice == "About & Contact":
        st.write("""
        **Platform Support & Queries:**  
        Email: `support@zerotoinvestor.in` / `zerotoinvestorofficial@gmail.com`  
        Operational Hours: Monday - Friday (9:00 AM - 5:00 PM IST)
        """)

# Footer Note
st.markdown("---")
st.markdown("<div class='footer-text'>Alpha Momentum Analytics © 2026 | Built strictly for Educational & Technical Research | Not a SEBI Registered Advisory Service</div>", unsafe_allow_html=True)
                    
