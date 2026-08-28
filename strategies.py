import pandas as pd
import numpy as np
import yfinance as yf

# 1. RSI Indicator
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 2. Supertrend Indicator (10, 4)
def calc_supertrend(df, period=10, multiplier=4):
    high, low, close = df['High'].squeeze(), df['Low'].squeeze(), df['Close'].squeeze()
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
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
    
    st_val = pd.Series(np.where(in_uptrend, lowerband, upperband), index=df.index)
    return pd.Series(in_uptrend, index=df.index), st_val

# 3. Conviction Scoring Engine
def get_conviction_score(stock_3m, n_3m, vol_ratio, rsi_val, risk_metric):
    rs = stock_3m - n_3m
    pts_rs = 30 if rs >= 20 else (24 if rs >= 10 else (18 if rs >= 0 else 8))
    pts_vol = 25 if vol_ratio >= 2.5 else (20 if vol_ratio >= 1.8 else (15 if vol_ratio >= 1.2 else 8))
    pts_rr = 25 if risk_metric <= 10 else (20 if risk_metric <= 15 else (15 if risk_metric <= 20 else 10))
    pts_mom = 20 if 60 <= rsi_val <= 72 else (16 if 50 <= rsi_val < 60 else (12 if rsi_val > 72 else 6))
    return min(100, int(pts_rs + pts_vol + pts_rr + pts_mom))

# 4. Nifty & Sensex MTF Intraday Tracker (3m + 10m)
def get_index_mtf_signal(ticker_symbol):
    try:
        df_raw = yf.download(ticker_symbol, period='5d', interval='1m', progress=False, auto_adjust=True).dropna()
        if len(df_raw) < 30:
            return None
        resamp_3m = df_raw.resample('3min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        resamp_10m = df_raw.resample('10min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()

        trend_3m, st_val_3m = calc_supertrend(resamp_3m, period=10, multiplier=4)
        trend_10m, st_val_10m = calc_supertrend(resamp_10m, period=10, multiplier=4)

        t3 = bool(trend_3m.iloc[-1])
        t10 = bool(trend_10m.iloc[-1])
        cmp_p = float(resamp_3m['Close'].iloc[-1])
        sl_3m = float(st_val_3m.iloc[-1])

        if t10 and t3:
            signal = "STRONG LONG 🟢"
        elif (not t10) and (not t3):
            signal = "STRONG SHORT 🔴"
        else:
            signal = "NEUTRAL / CHOPPY ⚪"

        return {
            "CMP": round(cmp_p, 2),
            "Signal": signal,
            "10M Trend": "BULLISH 🟢" if t10 else "BEARISH 🔴",
            "3M Trend": "BULLISH 🟢" if t3 else "BEARISH 🔴",
            "Dynamic StopLoss (3M ST)": round(sl_3m, 2),
            "Risk Points": round(abs(cmp_p - sl_3m), 2)
        }
    except Exception:
        return None
        
