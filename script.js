const API = "http://127.0.0.1:5000";
const $ = id => document.getElementById(id);
const money = n => "$" + Number(n || 0).toFixed(2);
async function request(path, options={}) {
  const r = await fetch(API + path, {headers:{"Content-Type":"application/json"}, ...options});
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || "Backend request failed");
  return data;
}
function connection(ok, msg) {
  $("connection").textContent = msg;
  $("statusDot").className = ok ? "online" : "offline";
}
async function refresh() {
  const s = await request("/api/state");
  $("balance").textContent = money(s.balance);
  $("equity").textContent = money(s.equity);
  $("pnl").textContent = money(s.net_profit);
  $("pnl").className = s.net_profit >= 0 ? "positive" : "negative";
  $("pnlPct").textContent = s.return_pct.toFixed(2) + "% return";
  $("winrate").textContent = s.win_rate === null ? "—" : s.win_rate.toFixed(1) + "%";
  $("tradeCount").textContent = `${s.closed_trades.length} closed trades`;
  $("openTrades").innerHTML = s.open_trades.length ? s.open_trades.map(t =>
    `<tr><td>${t.symbol}</td><td>${t.side}</td><td>${t.entry.toFixed(5)}</td><td>${t.stop_loss.toFixed(5)}</td><td>${t.take_profit.toFixed(5)}</td><td>${t.volume}</td><td class="${t.floating_pnl>=0?'positive':'negative'}">${money(t.floating_pnl)}</td></tr>`).join("") : '<tr><td colspan="7" class="empty">No open trades</td></tr>';
  $("history").innerHTML = s.closed_trades.length ? [...s.closed_trades].reverse().map(t =>
    `<tr><td>${new Date(t.closed_at).toLocaleString()}</td><td>${t.symbol}</td><td>${t.side}</td><td>${t.entry.toFixed(5)}</td><td>${t.exit.toFixed(5)}</td><td>${t.reason}</td><td class="${t.pnl>=0?'positive':'negative'}">${money(t.pnl)}</td></tr>`).join("") : '<tr><td colspan="7" class="empty">No closed trades yet</td></tr>';
}
async function check() {
  try { const s=await request("/api/status"); connection(true, `Connected • ${s.mt5_connected ? "MT5 ready" : "MT5 not connected"}`); await refresh(); }
  catch(e) { connection(false,"Backend disconnected"); $("signalText").textContent=e.message; }
}
$("connectBtn").onclick=check;
$("refreshBtn").onclick=()=>refresh().catch(e=>alert(e.message));
$("scanBtn").onclick=async()=>{
  $("scanBtn").disabled=true; $("scanBtn").textContent="Scanning…";
  try {
    const symbol=$("symbol").value, timeframe=$("timeframe").value;
    const d=await request("/api/scan",{method:"POST",body:JSON.stringify({symbol,timeframe})});
    const x=d.analysis;
    $("signalPill").textContent=x.signal;
    $("signalText").textContent=d.message;
    $("ema20").textContent=x.ema20?.toFixed(5) ?? "—";
    $("ema50").textContent=x.ema50?.toFixed(5) ?? "—";
    $("rsi").textContent=x.rsi?.toFixed(2) ?? "—";
    $("macd").textContent=x.macd?.toFixed(5) ?? "—";
    $("atr").textContent=x.atr?.toFixed(5) ?? "—";
    $("price").textContent=x.price?.toFixed(5) ?? "—";
    $("scanTime").textContent="Last scan: "+new Date().toLocaleString();
    await refresh();
  } catch(e) { $("signalText").textContent=e.message; connection(false,"Backend / MT5 error"); }
  finally { $("scanBtn").disabled=false; $("scanBtn").textContent="Run market scan"; }
};
check();