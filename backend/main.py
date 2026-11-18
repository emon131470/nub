import os, json
from datetime import datetime, timezone, date
from threading import Lock
import MetaTrader5 as mt5
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from strategy import analyze
from risk_manager import *

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Restrict to your GitHub Pages URL before public deployment.
lock = Lock()
START_BALANCE = float(os.getenv("PAPER_START_BALANCE", "1000"))
STATE_FILE = os.path.join(os.path.dirname(__file__), "paper_state.json")
TIMEFRAMES = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
              "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {"balance": START_BALANCE, "open_trades": [], "closed_trades": [], "daily": {}}

state = load_state()

def save_state():
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

def ensure_mt5():
    if mt5.terminal_info() is None and not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}. Open MT5 desktop and log in to a DEMO account.")
    return True

def get_rates(symbol, timeframe, count=250):
    ensure_mt5()
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Cannot select {symbol}: {mt5.last_error()}")
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAMES[timeframe], 0, count)
    if rates is None or len(rates) < 70:
        raise RuntimeError(f"No sufficient rates for {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df

def tick_price(symbol, side):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: raise RuntimeError(f"No live tick for {symbol}")
    return float(tick.ask if side == "BUY" else tick.bid)

def floating(trade, price):
    info = mt5.symbol_info(trade["symbol"])
    if info and info.trade_tick_size and info.trade_tick_value:
        ticks = ((price-trade["entry"]) if trade["side"]=="BUY" else (trade["entry"]-price)) / info.trade_tick_size
        return ticks * info.trade_tick_value * trade["volume"]
    # Fallback is a price-difference estimate, not broker-accurate P/L.
    return (price-trade["entry"]) * (1 if trade["side"]=="BUY" else -1) * trade["volume"] * 100000

def daily_realized():
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(t["pnl"] for t in state["closed_trades"] if t.get("closed_day")==today)

def close_trade(trade, exit_price, reason):
    pnl = floating(trade, exit_price)
    state["balance"] += pnl
    trade.update({"exit": exit_price, "pnl": pnl, "reason": reason,
                  "closed_at": datetime.now(timezone.utc).isoformat(),
                  "closed_day": datetime.now(timezone.utc).date().isoformat()})
    state["closed_trades"].append(trade)
    state["open_trades"].remove(trade)

def update_open_trades():
    for trade in list(state["open_trades"]):
        tick = mt5.symbol_info_tick(trade["symbol"])
        if tick is None: continue
        # Long exits at bid; short exits at ask.
        px = float(tick.bid if trade["side"]=="BUY" else tick.ask)
        if trade["side"]=="BUY":
            if px <= trade["stop_loss"]: close_trade(trade, trade["stop_loss"], "STOP_LOSS")
            elif px >= trade["take_profit"]: close_trade(trade, trade["take_profit"], "TAKE_PROFIT")
        else:
            if px >= trade["stop_loss"]: close_trade(trade, trade["stop_loss"], "STOP_LOSS")
            elif px <= trade["take_profit"]: close_trade(trade, trade["take_profit"], "TAKE_PROFIT")

def state_payload():
    opens = []
    for t in state["open_trades"]:
        item = dict(t)
        try:
            tick = mt5.symbol_info_tick(t["symbol"])
            px = float(tick.bid if t["side"]=="BUY" else tick.ask) if tick else t["entry"]
            item["floating_pnl"] = floating(t, px)
        except Exception: item["floating_pnl"] = 0.0
        opens.append(item)
    closed = state["closed_trades"]
    wins = sum(1 for t in closed if t["pnl"] > 0)
    net = state["balance"] - START_BALANCE
    floating_total = sum(t["floating_pnl"] for t in opens)
    return {"balance":state["balance"], "equity":state["balance"]+floating_total,
            "net_profit":net, "return_pct":net/START_BALANCE*100,
            "win_rate":(wins/len(closed)*100 if closed else None),
            "open_trades":opens, "closed_trades":closed[-100:]}

@app.get("/api/status")
def status():
    connected = mt5.terminal_info() is not None
    return jsonify({"ok":True, "mt5_connected":connected, "mode":"PAPER_ONLY"})

@app.get("/api/state")
def get_state():
    try:
        ensure_mt5()
        update_open_trades()
    except Exception:
        pass
    save_state()
    return jsonify(state_payload())

@app.post("/api/scan")
def scan():
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol","EURUSD")).upper()
    timeframe = str(data.get("timeframe","M15")).upper()
    if timeframe not in TIMEFRAMES: return jsonify(error="Unsupported timeframe"), 400
    if not symbol.isalnum() or len(symbol)>20: return jsonify(error="Invalid symbol"), 400
    with lock:
        try:
            df = get_rates(symbol, timeframe)
            result = analyze(df)
            update_open_trades()
            message = f"{result['signal']} signal for {symbol}. "
            if result["signal"] in ("BUY","SELL"):
                if state["open_trades"]:
                    message += "Signal not opened: one-position limit is already reached."
                elif daily_realized() <= -(START_BALANCE * DAILY_LOSS_FRACTION):
                    message += "Daily paper loss limit reached; no new trade."
                else:
                    info = mt5.symbol_info(symbol)
                    price = tick_price(symbol, result["signal"])
                    sl, tp = build_levels(result["signal"], price, result["atr"])
                    risk_cash = state["balance"] * RISK_FRACTION
                    if info and info.trade_tick_size and info.trade_tick_value:
                        loss_per_lot = abs(price-sl)/info.trade_tick_size*info.trade_tick_value
                        volume = risk_cash/loss_per_lot if loss_per_lot > 0 else 0
                        step = info.volume_step or 0.01
                        volume = round(volume/step)*step
                        volume = max(info.volume_min, min(info.volume_max, volume))
                    else:
                        volume = 0.01
                    trade = {"symbol":symbol, "side":result["signal"], "entry":price,
                             "stop_loss":sl, "take_profit":tp, "volume":float(volume),
                             "opened_at":datetime.now(timezone.utc).isoformat()}
                    state["open_trades"].append(trade)
                    message += f"Paper {result['signal']} opened at {price:.5f}; SL {sl:.5f}, TP {tp:.5f}."
            else:
                message += "No trade opened; waiting for confirmation."
            save_state()
            return jsonify({"analysis":result,"message":message,"state":state_payload()})
        except Exception as e:
            return jsonify(error=str(e)), 503

@app.post("/api/reset")
def reset():
    # Local-only development reset; protect/remove this endpoint before exposing backend publicly.
    global state
    with lock:
        state = {"balance":START_BALANCE,"open_trades":[],"closed_trades":[],"daily":{}}
        save_state()
    return jsonify({"ok":True,"state":state_payload()})

if __name__ == "__main__":
    print("Paper trading backend only. No MT5 order_send() is used.")
    app.run(host="127.0.0.1", port=5000, debug=False)
