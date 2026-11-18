from indicators import add_indicators

def analyze(df):
    if len(df) < 60:
        raise ValueError("Not enough candles. Need at least 60 bars.")
    d = add_indicators(df).dropna()
    # Use last fully closed candle; MT5 bar zero is still forming.
    row = d.iloc[-2]
    signal = "HOLD"
    bullish = row.ema20 > row.ema50 and row.macd > row.macd_signal and 50 < row.rsi < 70
    bearish = row.ema20 < row.ema50 and row.macd < row.macd_signal and 30 < row.rsi < 50
    if bullish: signal = "BUY"
    elif bearish: signal = "SELL"
    return {
        "signal": signal, "ema20": float(row.ema20), "ema50": float(row.ema50),
        "rsi": float(row.rsi), "macd": float(row.macd), "atr": float(row.atr),
        "price": float(row.close), "bar_time": str(row.time)
    }
