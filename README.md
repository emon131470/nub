# MT5 AI Trading Bot — Version 1.0

**Paper trading only.** This starter project analyzes MT5 candles and simulates positions locally. It does not send real orders.

## Requirements
- Windows 10/11
- MetaTrader 5 desktop terminal installed and logged in to a **demo account**
- Python 3.10–3.12 (64-bit recommended)
- Git

## Run locally
1. Open MT5 and log in to a demo account. Keep the terminal open.
2. Open a terminal in the project folder:
   ```bash
   cd backend
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   py main.py
   ```
3. Open `index.html` in your browser, or publish the root files to GitHub Pages.
4. In the dashboard select a symbol/timeframe and click **Run market scan**.

The dashboard calls `http://127.0.0.1:5000`. When hosted on GitHub Pages, it still talks to the backend on the same computer where the browser is running. MT5 and Python must be running on that computer.

## GitHub Pages
- Create a GitHub repository and upload `index.html`, `style.css`, `script.js`, and `README.md` to the repository root.
- In repository Settings → Pages, choose Deploy from a branch → `main` → `/ (root)` → Save.
- Do not upload credentials, account passwords, API keys, or `paper_state.json`.

## Strategy (initial test rules)
- BUY: EMA20 > EMA50, MACD > MACD signal, RSI between 50 and 70.
- SELL: EMA20 < EMA50, MACD < MACD signal, RSI between 30 and 50.
- SL: 1.5 × ATR; TP: 2R.
- One open position maximum; 1% risk target; 3% daily realized-loss pause.
- Signals use the previous fully closed candle, not the forming candle.

This is a rules-based technical strategy, **not a machine-learning AI model**. It is an experimental baseline, not a proven profitable strategy.

## Important limitations
- This version has no live-order execution. There is no `mt5.order_send()` call.
- The paper engine is process-local and saves its state to `backend/paper_state.json`.
- MT5 Python integration is supported on Windows with a running desktop terminal; it will not run on GitHub Pages or standard GitHub Actions.
- Symbol names differ by broker (for example `EURUSD`, `EURUSD.a`, `EURUSDm`). Use the exact Market Watch symbol.
- Broker tick values, contract sizes, spread, commission, swaps, and slippage can affect results. The fallback P/L calculation is approximate.
- Do not expose the local backend directly to the public internet. CORS is permissive for this local prototype; restrict it before any remote deployment.
- The `/api/reset` endpoint is for local testing only.
- No profit is guaranteed. Test extensively in demo before considering any real-money use.
